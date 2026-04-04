from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.user_llm_config import UserLlmConfig
from app.models.user_schedule_config import UserScheduleConfig
from app.models.user_notification_config import UserNotificationConfig
from app.core.dependencies import get_current_user
from app.core.security import encrypt_api_key, decrypt_api_key, mask_api_key
from app.schemas.llm_config import LlmConfigCreate, LlmConfigResponse, LlmTestResult
from app.schemas.schedule import ScheduleConfigResponse, ScheduleConfigUpsert
from app.schemas.notification import NotificationConfigResponse, NotificationConfigUpsert, NotificationTestResult
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
    else:
        if not data.api_key:
            raise HTTPException(status_code=400, detail="API Key required for first-time setup")
        config = UserLlmConfig(
            user_id=current_user.id,
            provider=data.provider,
            api_key_enc=encrypt_api_key(data.api_key),
            model_name=data.model_name,
            base_url=base_url,
        )
        db.add(config)
    await db.flush()
    plain_key = decrypt_api_key(config.api_key_enc)
    return LlmConfigResponse(
        provider=config.provider,
        api_key_masked=mask_api_key(plain_key),
        model_name=config.model_name,
        base_url=config.base_url,
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
