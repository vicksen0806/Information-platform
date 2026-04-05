"""Web Push notification router."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models.user import User
from app.models.push_subscription import PushSubscription
from app.core.dependencies import get_current_user
from app.config import settings

router = APIRouter(prefix="/push", tags=["push"])


class SubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """Return the VAPID public key for the frontend to use during subscription."""
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="Web Push not configured on this server")
    return {"vapid_public_key": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe", status_code=201)
async def subscribe(
    data: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a push subscription for the current user."""
    # Check if already subscribed with this endpoint
    existing = await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == data.endpoint)
    )
    if existing.scalar_one_or_none():
        return {"message": "Already subscribed"}

    sub = PushSubscription(
        user_id=current_user.id,
        endpoint=data.endpoint,
        p256dh=data.p256dh,
        auth=data.auth,
    )
    db.add(sub)
    await db.commit()
    return {"message": "Subscribed successfully"}


@router.delete("/unsubscribe")
async def unsubscribe(
    data: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a push subscription."""
    await db.execute(
        delete(PushSubscription).where(
            PushSubscription.endpoint == data.endpoint,
            PushSubscription.user_id == current_user.id,
        )
    )
    await db.commit()
    return {"message": "Unsubscribed"}


@router.delete("/unsubscribe-all")
async def unsubscribe_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove all push subscriptions for the current user."""
    await db.execute(
        delete(PushSubscription).where(PushSubscription.user_id == current_user.id)
    )
    await db.commit()
    return {"message": "All subscriptions removed"}
