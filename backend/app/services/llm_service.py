from openai import OpenAI
from app.config import settings
from app.schemas.llm_config import LlmTestResult


def _build_client(config) -> OpenAI:
    """Build an OpenAI-compatible client from UserLlmConfig."""
    from app.core.security import decrypt_api_key
    api_key = decrypt_api_key(config.api_key_enc)
    base_url = config.base_url or settings.LLM_PROVIDER_BASE_URLS.get(config.provider)
    return OpenAI(api_key=api_key, base_url=base_url)


def generate_digest_sync(
    config,
    keywords: list[str],
    crawled_contents: list[dict],  # [{keyword, content}]
    feedback_hint: str | None = None,
) -> dict:
    """
    Call LLM to generate a structured digest. Returns {title, summary_md, tokens_used}.
    Runs synchronously (called from Celery worker).
    """
    client = _build_client(config)

    content_parts = []
    for item in crawled_contents:
        kw = item.get("keyword", "其他")
        raw = item.get("content", "")
        if len(raw) > 6000:
            text = raw[:4000] + "\n...\n" + raw[-2000:]
        else:
            text = raw
        content_parts.append(f"=== 关键词：{kw} ===\n{text}")

    combined_content = "\n\n".join(content_parts)
    keywords_str = "、".join(keywords) if keywords else "（未设置关键词）"

    style = getattr(config, "summary_style", "concise") or "concise"
    style_instruction = {
        "concise": "请用中文输出，语言简洁准确，每个要点一句话点到为止。",
        "detailed": "请用中文输出，每个要点展开2-3句详细说明，包含背景、数据和影响分析。",
        "academic": "请用中文输出，使用正式学术语气，客观陈述事实，引用数据和来源，避免口语表达。",
    }.get(style, "请用中文输出，语言简洁准确。")

    default_system_prompt = (
        "你是一个专业的信息助理，负责将用户关注的各类关键词的抓取内容整理成彼此独立的关键词卡片。\n"
        "输出必须严格使用以下 Markdown 结构：\n\n"
        "每个关键词必须单独成段，使用以下格式：\n"
        "## [关键词]\n"
        "- **[要点标题]**：具体内容说明 ([来源](URL))\n\n"
        "重要规则：\n"
        "1. 不要输出任何总总结、总览、跨关键词对比、分组标题或前言\n"
        "2. 每个关键词单独一节，只写与该关键词相关的内容，不要提及其他关键词\n"
        "3. 每个关键词至少输出 2 条要点；如果信息很少，就如实说明今日新增有限\n"
        "4. 标题顺序尽量与输入关键词顺序一致\n"
        "5. 每条要点必须在末尾附上原文来源链接 ([来源](URL))，URL取自 'Source: URL' 字段\n"
        "6. 没有来源链接时省略链接\n"
        f"{style_instruction}"
    )
    system_prompt = (config.prompt_template.strip() if getattr(config, "prompt_template", None) else None) or default_system_prompt

    user_prompt = (
        f"用户关注的关键词：{keywords_str}\n\n"
        f"以下是按关键词分组的今日抓取内容：\n\n{combined_content}\n\n"
        "请严格按照系统提示的 Markdown 结构生成摘要。"
        + (f"\n\n[用户偏好参考：{feedback_hint}]" if feedback_hint else "")
    )

    response = client.chat.completions.create(
        model=config.model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=3000,
        timeout=90,
    )

    full_text = response.choices[0].message.content or ""
    tokens_used = response.usage.total_tokens if response.usage else 0

    # Extract title from first # heading
    lines = full_text.strip().splitlines()
    title = "今日信息摘要"
    if lines and lines[0].startswith("#"):
        title = lines[0].lstrip("#").strip()

    # Score importance: quick follow-up call (max 20 tokens)
    importance_score: float | None = None
    try:
        score_response = client.chat.completions.create(
            model=config.model_name,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"以下是一份信息摘要的标题和开头内容，请给它的重要性打分（0.0~1.0），"
                        f"1.0表示非常重要/紧急，0.0表示普通日常信息。"
                        f"只输出一个数字，不要其他任何内容。\n\n"
                        f"标题：{title}\n摘要前200字：{full_text[:200]}"
                    ),
                }
            ],
            temperature=0.0,
            max_tokens=10,
            timeout=15,
        )
        score_str = (score_response.choices[0].message.content or "").strip()
        score_val = float(score_str)
        if 0.0 <= score_val <= 1.0:
            importance_score = round(score_val, 2)
    except Exception:
        pass  # scoring is optional

    return {
        "title": title,
        "summary_md": full_text,
        "tokens_used": tokens_used,
        "llm_model": config.model_name,
        "importance_score": importance_score,
    }


def generate_embedding_sync(config, text: str) -> list[float] | None:
    """
    Generate a 1536-dim embedding vector for the given text.
    Returns None if embedding_model is not configured or call fails.
    Runs synchronously (called from Celery worker).
    """
    embedding_model = getattr(config, "embedding_model", None)
    if not embedding_model:
        return None
    try:
        client = _build_client(config)
        # Truncate text to avoid token limit on embedding models
        resp = client.embeddings.create(
            model=embedding_model,
            input=text[:8000],
        )
        vec = resp.data[0].embedding
        if len(vec) != 1536:
            return None  # Only store 1536-dim vectors
        return vec
    except Exception:
        return None  # Embedding is optional, never block digest flow


def recommend_keywords_sync(
    config,
    recent_keywords: list[str],
    active_keywords: list[str] | None = None,
) -> list[dict]:
    """
    Ask LLM to suggest new keywords based on the user's recently used keywords.
    Returns [{text, reason}] — up to 10 suggestions.
    """
    client = _build_client(config)
    recent_kw_str = "、".join(recent_keywords[:50]) if recent_keywords else "（暂无）"
    active_kw_str = "、".join((active_keywords or [])[:30]) if active_keywords else "（暂无）"
    prompt = (
        f"用户近15天实际使用/抓取过的关键词：{recent_kw_str}\n"
        f"用户当前已选关键词：{active_kw_str}\n\n"
        "请基于“近15天实际使用/抓取过的所有关键词”来理解用户最近半个月的持续关注方向，"
        "推荐10个新的、有价值的关键词。\n"
        "要求：\n"
        "1. 推荐范围要覆盖用户近半个月的整体关注面，不要只围绕当前已选的少数关键词做近义词扩写\n"
        "2. 推荐词不能与“当前已选关键词”重复，也尽量不要只是简单加前后缀的变体\n"
        "3. 优先推荐更具体、可持续跟踪、有信息增量的主题词\n"
        "4. 每个推荐词附上一句简短理由（≤20字）\n"
        "5. 严格按以下JSON格式输出，不要其他内容：\n"
        '[{"text": "关键词1", "reason": "理由"}, {"text": "关键词2", "reason": "理由"}, ...]'
    )
    try:
        response = client.chat.completions.create(
            model=config.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
            timeout=30,
        )
        import json, re
        raw = response.choices[0].message.content or ""
        # Extract JSON array from response
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        items = json.loads(match.group())
        return [
            {"text": str(item.get("text", ""))[:100], "reason": str(item.get("reason", ""))[:100]}
            for item in items
            if item.get("text")
        ][:10]
    except Exception:
        return []


async def test_llm_connection(config) -> LlmTestResult:
    """Test that the LLM config is valid by sending a minimal request."""
    import asyncio

    def _test():
        try:
            client = _build_client(config)
            response = client.chat.completions.create(
                model=config.model_name,
                messages=[{"role": "user", "content": "Hi, reply with OK only."}],
                max_tokens=10,
            )
            return True, f"Connection successful. Model replied: {response.choices[0].message.content}"
        except Exception as e:
            return False, str(e)[:300]

    loop = asyncio.get_event_loop()
    success, message = await loop.run_in_executor(None, _test)
    return LlmTestResult(success=success, message=message)
