from sqlalchemy.ext.asyncio import AsyncSession
from schemas.util_schemas import NotificationResponse
from utils.redis_cache import redis_get, redis_set, invalidate_notify_cache
from services.repositories.base_repository import BaseRepository
from services.repositories.notification_repository import NotificationRepository
from core.exceptions import PermissionDeniedError, NotificationNotFoundError
from models import User

class NotificationService():
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = NotificationRepository(db)
        self.base_repo = BaseRepository(db)

    async def my_notifications(self, current_user: User):
        cache_key = f"user:{current_user.id}:notifications:all"
        cached = await redis_get(cache_key)

        if cached:
            return cached
        
        notifications = await self.repo.get_all_my(current_user)

        notifications_data = [NotificationResponse.model_validate(n).model_dump(mode="json") for n in notifications]

        await redis_set(cache_key, notifications_data, ttl=150)
        
        return notifications_data

    async def get_unread_count(self, current_user: User):
        cache_key = f"user:{current_user.id}:notifications:unread-count"
        cached = await redis_get(cache_key)

        if cached:
            return cached
        
        unread = await self.repo.get_count_my(current_user)

        unread_data = {
            "message": unread
        }

        await redis_set(cache_key, unread_data, ttl=150)

        return unread_data
    
    async def read_notification(self, notification_id: int, current_user: User):
        notification = await self.repo.get_by_id(notification_id)

        if not notification:
            raise NotificationNotFoundError()
        
        if notification.user_id != current_user.id:
            raise PermissionDeniedError()
        
        if notification.is_read:
            return {"message": "Notification already read"}

        notification.is_read = True
        
        await self.base_repo.commit_refresh(notification)
        await invalidate_notify_cache(current_user.id)

        return {
            "message": "Notification marked as read"
        }
    
    async def read_all_notification(self, current_user: User):
        await self.repo.read_all(current_user)
        await invalidate_notify_cache(current_user.id)

        return {
            "message": "All notifications marked as read"
        }
