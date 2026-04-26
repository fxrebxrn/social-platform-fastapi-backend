from fastapi import APIRouter, Depends, HTTPException
from models import User, Notification
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from core.database import get_db
from utils.query_helpers import fetch_all_by_stmt
from core.security import get_current_user
from schemas.util_schemas import MessageResponse, NotificationResponse
from typing import Annotated
from utils.redis_cache import redis_get, redis_set, redis_delete

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("/", response_model=list[NotificationResponse])
async def my_notifications(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    cache_key = f"user:{current_user.id}:notifications:all"
    cached = await redis_get(cache_key)

    if cached:
        return cached
    
    stmt = select(Notification).where(Notification.user_id == current_user.id).order_by(Notification.created_at.desc())
    notifications = await fetch_all_by_stmt(db, stmt)

    notifications_data = [NotificationResponse.model_validate(n).model_dump(mode="json") for n in notifications]

    await redis_set(cache_key, notifications_data, ttl=150)
    
    return notifications_data

@router.get("/unread-count", response_model=MessageResponse)
async def get_unread_count(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    cache_key = f"user:{current_user.id}:notifications:unread-count"
    cached = await redis_get(cache_key)

    if cached:
        return cached
    
    stmt = select(func.count()).select_from(Notification).where(Notification.user_id == current_user.id, Notification.is_read == False)
    result = await db.execute(stmt)
    unread = result.scalar()

    unread_data = {
        "message": unread
    }

    await redis_set(cache_key, unread_data, ttl=150)

    return unread_data

@router.patch("/{notification_id}/read", response_model=MessageResponse)
async def read_notification(notification_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    stmt = select(Notification).where(Notification.id == notification_id)
    result = await db.execute(stmt)
    notification = result.scalars().first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    if notification.is_read:
        return {"message": "Notification already read"}

    notification.is_read = True
    
    await db.commit()
    await db.refresh(notification)
    await redis_delete(f"user:{current_user.id}:notifications:all")
    await redis_delete(f"user:{current_user.id}:notifications:unread-count")

    return {
        "message": "Notification marked as read"
    }

@router.patch("/read-all", response_model=MessageResponse)
async def read_all_notification(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    stmt = update(Notification).where(Notification.user_id == current_user.id, Notification.is_read == False).values(is_read=True)

    await db.execute(stmt)
    await db.commit()
    await redis_delete(f"user:{current_user.id}:notifications:all")
    await redis_delete(f"user:{current_user.id}:notifications:unread-count")

    return {
        "message": "All notifications marked as read"
    }
