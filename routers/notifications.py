from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from schemas.util_schemas import MessageResponse, NotificationResponse
from typing import Annotated
from services.notification_service import NotificationService
from models import User

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("/", response_model=list[NotificationResponse])
async def my_notifications(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = NotificationService(db)
    return await service.my_notifications(current_user)

@router.get("/unread-count", response_model=MessageResponse)
async def get_unread_count(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = NotificationService(db)
    return await service.get_unread_count(current_user)

@router.patch("/{notification_id}/read", response_model=MessageResponse)
async def read_notification(notification_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = NotificationService(db)
    return await service.read_notification(notification_id, current_user)

@router.patch("/read-all", response_model=MessageResponse)
async def read_all_notification(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = NotificationService(db)
    return await service.read_all_notification(current_user)
