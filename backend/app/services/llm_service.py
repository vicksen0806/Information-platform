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
    crawled_contents: list[dict],  # [{keyword, content, group?}]
) -> dict:
    """
    Call LLM to generate a structured digest. Returns {title, summary_md, tokens_used}.
    Runs synchronously (called from Celery worker).
    crawled_contents items may include optional 'group' key for section grouping.
    """
    from collections import defaultdict
    client = _build_client(config)

    # Group content blocks by group_name; ungrouped keywords go under None
    groups: dict[str | None, list[tuple[str, str]]] = defaultdict(list)
    for item in crawled_contents:
        kw = item.get("keyword", "其他")
        raw = item.get("content", "")
        group = item.get("group")  # may be absent or None
        if len(raw) > 6000:
            text = raw[:4000] + "\n...\n" + raw[-2000:]
        else:
            text = raw
        groups[group].append((kw, text))

    # Build content string: named groups first (sorted), then ungrouped
    content_parts = []
    has_groups = any(g is not None for g in groups)

    for group_name in sorted(groups.keys(), key=lambda g: (g is None, g or "")):
        items = groups[group_name]
        if has_groups and group_name is not None:
            content_parts.append(f"【分组：{group_name}】")
        for kw, text in items:
            content_parts.append(f"=== 关键词：{kw} ===\n{text}")

    combined_content = "\n\n".join(content_parts)
    keywords_str = "、".join(keywords) if keywords else "（未设置关键词）"

    group_instruction = ""
    if has_groups:
        group_instruction = (
            "关键词已按分组标注。在「## 详细」中，先用 `## 分组名` 作为二级标题列出分组，"
            "再在其下用 `### 关键词` 列出各关键词内容。未分组的关键词直接用 `### 关键词` 即可。\n"
        )

    default_system_prompt = (
        "你是一个专业的信息助理，负责将用户关注的各类关键词的抓取内容整理成结构清晰的每日摘要。\n"
        "输出必须严格使用以下 Markdown 结构：\n\n"
        "# 今日信息摘要\n\n"
        "## 总结\n"
        "（2-4句话，概括今日所有关键词的整体动态，让用户30秒内了解全局）\n\n"
        "## 详细\n\n"
        f"{group_instruction}"
        "每个关键词节：\n"
        "### [关键词]\n"
        "- **[要点标题]**：具体内容说明 ([来源](URL))\n\n"
        "重要规则：\n"
        "1. 每个关键词单独一节，只写与该关键词相关的内容\n"
        "2. 每条要点必须在末尾附上原文来源链接 ([来源](URL))，URL取自 'Source: URL' 字段\n"
        "3. 没有来源链接时省略链接\n"
        "请用中文输出，语言简洁准确。"
    )
    system_prompt = (config.prompt_template.strip() if getattr(config, "prompt_template", None) else None) or default_system_prompt

    user_prompt = (
        f"用户关注的关键词：{keywords_str}\n\n"
        f"以下是按关键词分组的今日抓取内容：\n\n{combined_content}\n\n"
        "请严格按照系统提示的 Markdown 结构生成摘要。"
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

    return {
        "title": title,
        "summary_md": full_text,
        "tokens_used": tokens_used,
        "llm_model": config.model_name,
    }


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
