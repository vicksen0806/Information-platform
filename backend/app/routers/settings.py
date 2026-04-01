from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.user_llm_config import UserLlmConfig
from app.core.dependencies import get_current_user
from app.core.security import encrypt_api_key, decrypt_api_key, mask_api_key
from app.schemas.llm_config import LlmConfigCreate, LlmConfigResponse, LlmTestResult
from app.config import settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/llm", response_model=LlmConfigResponse)
async def get_llm_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserLlmConfig).where(UserLlmConfig.user_id == current_user.id)
    )
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
    result = await db.execute(
        select(UserLlmConfig).where(UserLlmConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()

    encrypted_key = encrypt_api_key(data.api_key)
    base_url = data.base_url or settings.LLM_PROVIDER_BASE_URLS.get(data.provider)

    if config:
        config.provider = data.provider
        config.api_key_enc = encrypted_key
        config.model_name = data.model_name
        config.base_url = base_url
    else:
        config = UserLlmConfig(
            user_id=current_user.id,
            provider=data.provider,
            api_key_enc=encrypted_key,
            model_name=data.model_name,
            base_url=base_url,
        )
        db.add(config)

    await db.flush()
    return LlmConfigResponse(
        provider=config.provider,
        api_key_masked=mask_api_key(data.api_key),
        model_name=config.model_name,
        base_url=config.base_url,
    )


@router.delete("/llm", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserLlmConfig).where(UserLlmConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if config:
        await db.delete(config)


@router.post("/llm/test", response_model=LlmTestResult)
async def test_llm_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserLlmConfig).where(UserLlmConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="LLM config not set")

    from app.services.llm_service import test_llm_connection
    return await test_llm_connection(config)
