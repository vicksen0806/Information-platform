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
    crawled_contents: list[dict],  # [{source_name, content}]
) -> dict:
    """
    Call LLM to generate a digest. Returns {title, summary_md, tokens_used}.
    Runs synchronously (called from Celery worker).
    """
    client = _build_client(config)

    # Build context from crawled content (truncate to stay within token limits)
    content_blocks = []
    for item in crawled_contents:
        name = item.get("source_name", "未知来源")
        text = item.get("content", "")[:3000]  # Truncate per source
        content_blocks.append(f"### 来源：{name}\n{text}")

    combined_content = "\n\n".join(content_blocks)
    keywords_str = "、".join(keywords) if keywords else "（未设置关键词）"

    system_prompt = (
        "你是一个信息助理，负责从用户提供的网页内容中提炼与用户关注的关键词相关的信息，"
        "并生成一份简洁、结构清晰的每日信息摘要。"
        "摘要应使用 Markdown 格式，包含一个标题、分类整理的要点以及简短的结论。"
        "如果某个来源没有与关键词相关的内容，可以跳过。"
        "请用中文输出。"
    )

    user_prompt = (
        f"用户关注的关键词：{keywords_str}\n\n"
        f"以下是今日抓取的内容：\n\n{combined_content}\n\n"
        "请生成今日信息摘要，第一行写标题（以 # 开头），后面写正文。"
    )

    response = client.chat.completions.create(
        model=config.model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
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
