import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.user_llm_config import UserLlmConfig
from app.models.user_schedule_config import UserScheduleConfig
from app.models.user_notification_config import UserNotificationConfig
from app.models.user_email_config import UserEmailConfig
from app.models.notification_route import NotificationRoute
from app.core.dependencies import get_current_user
from app.core.security import encrypt_api_key, decrypt_api_key, mask_api_key
from app.schemas.llm_config import LlmConfigCreate, LlmConfigResponse, LlmTestResult
from app.schemas.schedule import ScheduleConfigResponse, ScheduleConfigUpsert
from app.schemas.notification import NotificationConfigResponse, NotificationConfigUpsert, NotificationTestResult, NotificationRouteCreate, NotificationRouteResponse
from app.schemas.email_config import EmailConfigCreate, EmailConfigResponse, EmailTestResult
from app.config import settings

router = APIRouter(prefix="/settings", tags=["settings"])


# ── LLM ───────────────────────────────────────────────────────────────────────

@router.get("/llm", response_model=LlmConfigResponse)
async def get_llm_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserLlmConfig).where(UserLlmConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="LLM config not set")
    plain_key = decrypt_api_key(config.api_key_enc)
    return LlmConfigResponse(
        provider=config.provider,
        api_key_masked=mask_api_key(plain_key),
        model_name=config.model_name,
        base_url=config.base_url,
        prompt_template=config.prompt_template,
        summary_style=getattr(config, "summary_style", "concise") or "concise",
        embedding_model=getattr(config, "embedding_model", None),
    )


@router.put("/llm", response_model=LlmConfigResponse)
async def upsert_llm_config(
    data: LlmConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserLlmConfig).where(UserLlmConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    base_url = data.base_url or settings.LLM_PROVIDER_BASE_URLS.get(data.provider)
    if config:
        config.provider = data.provider
        if data.api_key:
            config.api_key_enc = encrypt_api_key(data.api_key)
        config.model_name = data.model_name
        config.base_url = base_url
        config.prompt_template = data.prompt_template or None
        config.summary_style = data.summary_style
        config.embedding_model = data.embedding_model or None
    else:
        if not data.api_key:
            raise HTTPException(status_code=400, detail="API Key required for first-time setup")
        config = UserLlmConfig(
            user_id=current_user.id,
            provider=data.provider,
            api_key_enc=encrypt_api_key(data.api_key),
            model_name=data.model_name,
            base_url=base_url,
            prompt_template=data.prompt_template or None,
            summary_style=data.summary_style,
            embedding_model=data.embedding_model or None,
        )
        db.add(config)
    await db.flush()
    plain_key = decrypt_api_key(config.api_key_enc)
    return LlmConfigResponse(
        provider=config.provider,
        api_key_masked=mask_api_key(plain_key),
        model_name=config.model_name,
        base_url=config.base_url,
        prompt_template=config.prompt_template,
        summary_style=config.summary_style or "concise",
        embedding_model=getattr(config, "embedding_model", None),
    )


@router.delete("/llm", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserLlmConfig).where(UserLlmConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if config:
        await db.delete(config)


@router.post("/llm/test", response_model=LlmTestResult)
async def test_llm_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserLlmConfig).where(UserLlmConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="LLM config not set")
    from app.services.llm_service import test_llm_connection
    return await test_llm_connection(config)


# ── Schedule ──────────────────────────────────────────────────────────────────

@router.get("/schedule", response_model=ScheduleConfigResponse)
async def get_schedule(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserScheduleConfig).where(UserScheduleConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if not config:
        # Return defaults without saving
        return ScheduleConfigResponse(schedule_hour=8, schedule_minute=0, timezone="Asia/Shanghai", is_active=True)
    return config


@router.put("/schedule", response_model=ScheduleConfigResponse)
async def upsert_schedule(
    data: ScheduleConfigUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserScheduleConfig).where(UserScheduleConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if config:
        config.schedule_hour = data.schedule_hour
        config.schedule_minute = data.schedule_minute
        config.timezone = data.timezone
        config.is_active = data.is_active
    else:
        config = UserScheduleConfig(
            user_id=current_user.id,
            schedule_hour=data.schedule_hour,
            schedule_minute=data.schedule_minute,
            timezone=data.timezone,
            is_active=data.is_active,
        )
        db.add(config)
    await db.flush()
    await db.refresh(config)
    return config


# ── Notification ──────────────────────────────────────────────────────────────

@router.get("/notification", response_model=NotificationConfigResponse)
async def get_notification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserNotificationConfig).where(UserNotificationConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Notification config not set")
    return config


@router.put("/notification", response_model=NotificationConfigResponse)
async def upsert_notification(
    data: NotificationConfigUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserNotificationConfig).where(UserNotificationConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if config:
        if data.webhook_url:  # Only update URL if a new one is provided
            config.webhook_url = data.webhook_url
        config.webhook_type = data.webhook_type
        config.is_active = data.is_active
    else:
        if not data.webhook_url:
            raise HTTPException(status_code=400, detail="Webhook URL required for first-time setup")
        config = UserNotificationConfig(
            user_id=current_user.id,
            webhook_url=data.webhook_url,
            webhook_type=data.webhook_type,
            is_active=data.is_active,
        )
        db.add(config)
    await db.flush()
    await db.refresh(config)
    return config


@router.delete("/notification", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserNotificationConfig).where(UserNotificationConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if config:
        await db.delete(config)


@router.post("/notification/test", response_model=NotificationTestResult)
async def test_notification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserNotificationConfig).where(UserNotificationConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Notification config not set")

    from app.services.notification_service import send_digest_notification
    import asyncio
    loop = asyncio.get_event_loop()
    success, message = await loop.run_in_executor(
        None,
        send_digest_notification,
        config,
        ["Test keyword"],
        "## Test\nThis is a test notification from Info Platform.",
        "now",
    )
    return NotificationTestResult(success=success, message=message)


# ── Email (SMTP) ──────────────────────────────────────────────────────────────

@router.get("/email", response_model=EmailConfigResponse)
async def get_email_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserEmailConfig).where(UserEmailConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Email config not set")
    return config


@router.put("/email", response_model=EmailConfigResponse)
async def upsert_email_config(
    data: EmailConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserEmailConfig).where(UserEmailConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if config:
        config.smtp_host = data.smtp_host
        config.smtp_port = data.smtp_port
        config.smtp_user = data.smtp_user
        if data.smtp_password:
            config.smtp_password_enc = encrypt_api_key(data.smtp_password)
        config.smtp_from = data.smtp_from
        config.smtp_to = data.smtp_to
        config.is_active = data.is_active
    else:
        if not data.smtp_password:
            raise HTTPException(status_code=400, detail="SMTP password required for first-time setup")
        config = UserEmailConfig(
            user_id=current_user.id,
            smtp_host=data.smtp_host,
            smtp_port=data.smtp_port,
            smtp_user=data.smtp_user,
            smtp_password_enc=encrypt_api_key(data.smtp_password),
            smtp_from=data.smtp_from,
            smtp_to=data.smtp_to,
            is_active=data.is_active,
        )
        db.add(config)
    await db.flush()
    await db.refresh(config)
    return config


@router.delete("/email", status_code=status.HTTP_204_NO_CONTENT)
async def delete_email_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserEmailConfig).where(UserEmailConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if config:
        await db.delete(config)


@router.post("/email/test", response_model=EmailTestResult)
async def test_email_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserEmailConfig).where(UserEmailConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Email config not set")

    from app.services.notification_service import send_email_notification
    import asyncio
    loop = asyncio.get_event_loop()
    success, message = await loop.run_in_executor(
        None,
        send_email_notification,
        config,
        ["Test keyword"],
        "## Test\nThis is a test email from Info Platform.",
        "now",
    )
    return EmailTestResult(success=success, message=message)


# ── Schedule: next crawl ──────────────────────────────────────────────────────

@router.get("/schedule/next-crawl")
async def get_next_crawl(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone, timedelta
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    result = await db.execute(select(UserScheduleConfig).where(UserScheduleConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()

    if not config or not config.is_active:
        return {"is_active": False, "next_crawl_at": None, "seconds_until": None}

    try:
        tz = ZoneInfo(config.timezone)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")

    now_local = datetime.now(tz)
    target = now_local.replace(hour=config.schedule_hour, minute=config.schedule_minute, second=0, microsecond=0)
    if target <= now_local:
        target += timedelta(days=1)

    seconds_until = int((target - now_local).total_seconds())
    return {
        "is_active": True,
        "next_crawl_at": target.isoformat(),
        "seconds_until": seconds_until,
        "schedule_time": f"{config.schedule_hour:02d}:{config.schedule_minute:02d}",
        "timezone": config.timezone,
    }


# ── RSS Feed Token ─────────────────────────────────────────────────────────────

@router.get("/feed-token")
async def get_feed_token(current_user: User = Depends(get_current_user)):
    """Return a stateless HMAC-based RSS feed token for the current user."""
    import hmac
    import hashlib
    user_id_hex = current_user.id.hex  # 32 hex chars
    sig = hmac.new(settings.SECRET_KEY.encode(), current_user.id.bytes, hashlib.sha256).hexdigest()[:16]
    token = user_id_hex + sig  # 48 chars total
    return {
        "feed_token": token,
        "feed_url": f"/api/v1/public/feed/{token}.rss",
    }


# ── Notification Routes (per-group webhook) ───────────────────────────────────

@router.get("/notification-routes", response_model=list[NotificationRouteResponse])
async def list_notification_routes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NotificationRoute)
        .where(NotificationRoute.user_id == current_user.id)
        .order_by(NotificationRoute.created_at)
    )
    return result.scalars().all()


@router.post("/notification-routes", response_model=NotificationRouteResponse, status_code=201)
async def create_notification_route(
    data: NotificationRouteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    route = NotificationRoute(
        user_id=current_user.id,
        group_name=data.group_name or None,
        webhook_type=data.webhook_type,
        webhook_url=data.webhook_url,
        is_active=data.is_active,
    )
    db.add(route)
    await db.flush()
    await db.refresh(route)
    return route


@router.delete("/notification-routes/{route_id}", status_code=204)
async def delete_notification_route(
    route_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NotificationRoute).where(
            NotificationRoute.id == route_id,
            NotificationRoute.user_id == current_user.id,
        )
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    await db.delete(route)
