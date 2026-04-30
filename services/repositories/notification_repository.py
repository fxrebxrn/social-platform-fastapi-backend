from fastapi import APIRouter, Depends, HTTPException
from models import User, Notification
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from core.database import get_db
from utils.query_helpers import fetch_all_by_stmt, get_scalar_result, fetch_first_by_stmt
from core.security import get_current_user
from schemas.util_schemas import MessageResponse, NotificationResponse
from typing import Annotated
from utils.redis_cache import redis_get, redis_set, redis_delete

class NotificationRepository():
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_my(self, current_user):
        stmt = select(Notification).where(Notification.user_id == current_user.id).order_by(Notification.created_at.desc())
        return await fetch_all_by_stmt(self.db, stmt)
    
    async def get_count_my(self, current_user):
        stmt = select(func.count()).select_from(Notification).where(Notification.user_id == current_user.id, Notification.is_read == False)
        return await get_scalar_result(self.db, stmt)
    
    async def get_by_id(self, notification_id):
        stmt = select(Notification).where(Notification.id == notification_id)
        return await fetch_first_by_stmt(self.db, stmt)
    
    async def read_all(self, current_user):
        stmt = update(Notification).where(Notification.user_id == current_user.id, Notification.is_read == False).values(is_read=True)
        await self.db.execute(stmt)
        return await self.db.commit()
        