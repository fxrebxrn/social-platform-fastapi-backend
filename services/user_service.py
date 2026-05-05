from sqlalchemy.ext.asyncio import AsyncSession
from services.repositories.base_repository import BaseRepository
from services.repositories.user_repository import UserRepository
from services.attachment_service import AttachmentService
from models import User, Notification, Follow
from core.exceptions import SelfFollowError, AlreadyFollowingError, UserNotFoundError, PermissionDeniedError, AlreadyUnfollowingError
from utils.redis_cache import invalidate_notify_cache, invalidate_follow_cache
from fastapi import HTTPException
from utils.redis_cache import redis_get, redis_set, redis_delete
from schemas.user_schemas import UserShort, UserUpdate
from services.repositories.post_repository import PostRepository
from core.security import ALLOWED_ROLES

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)
        self.att = AttachmentService(db)
        self.base_repo = BaseRepository(db)
        self.post_repo = PostRepository(db)

    async def get_by_id_or_raise(self, user_id: int):
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        return user

    async def follow_user(self, user_id: int, current_user: User):
        user_to_follow = await self.get_by_id_or_raise(user_id)

        if current_user.id == user_id:
            raise SelfFollowError()

        existing_follow = await self.repo.get_following(current_user, user_id)

        if existing_follow:
            raise AlreadyFollowingError()
        
        new_follow = Follow(
            follower_id=current_user.id,
            following_id=user_id
        )

        new_notify = Notification(
            user_id=user_id,
            sender_id=current_user.id,
            message=f"{current_user.name} followed you",
            notification_type="follow"
        )

        objects = [new_follow, new_notify]

        await self.base_repo.add_unique_objects(
            objects=objects,
            detail="Already following this user",
            refresh_obj=new_follow
        )

        await invalidate_follow_cache(user_id, current_user)
        await invalidate_notify_cache(user_id)

        return {
            "message": f"You are now following user {user_to_follow.name}"
        }
    
    async def search_users(self, name: str, limit: int, offset: int):
        if limit > 50:
            limit = 50
        
        if len(name) < 3 or len(name) > 50:
            raise HTTPException(status_code=400, detail="Name must be between 3 and 50 characters")
        
        cache_key = f"user:{name}:search"
        cached = await redis_get(cache_key)
        
        if cached:
            return cached
        
        users = await self.repo.search_user_by_letters(name, limit, offset)

        users_data = [
            UserShort.model_validate(u).model_dump(mode="json") for u in users
        ]
        await redis_set(cache_key, users_data, ttl=300)

        return users_data
    
    async def user_followers(self, user_id: int):
        cache_key = f"user:{user_id}:followers"
        cached = await redis_get(cache_key)

        if cached:
            return cached
        
        await self.get_by_id_or_raise(user_id)

        users = await self.repo.get_user_followers(user_id)

        users_data = [
            UserShort.model_validate(u).model_dump(mode="json") for u in users
        ]
        await redis_set(cache_key, users_data, ttl=300)

        return users_data

    async def user_followings(self, user_id: int):
        cache_key = f"user:{user_id}:following"
        cached = await redis_get(cache_key)
        
        if cached is not None:
            return cached

        await self.get_by_id_or_raise(user_id)

        users = await self.repo.get_user_followings(user_id)

        users_data = [
            UserShort.model_validate(u).model_dump(mode="json") for u in users
        ]
        await redis_set(cache_key, users_data, ttl=300)

        return users_data
    
    async def get_user_profile_data(self, user_id: int) -> dict:
        cache_key = f"user:{user_id}:profile"
        cached = await redis_get(cache_key)
        
        if cached:
            return cached

        user = await self.get_by_id_or_raise(user_id)
        
        count_posts = await self.post_repo.get_count_posts_by_user(user_id)

        profile_data = {
            "id": user.id,
            "name": user.name,
            "role": user.role,
            "avatar_url": user.avatar_url,
            "followers_count": await self.repo.get_followers_count(user_id),
            "following_count": await self.repo.get_following_count(user_id),
            "posts_count": count_posts
        }
        
        await redis_set(cache_key, profile_data, ttl=300)
        return profile_data
    
    async def get_user_profile(self, user_id: int, current_user: User):
        profile_data = await self.get_user_profile_data(user_id)
        
        is_following = False
        if current_user.id != user_id:
            is_following = await self.repo.get_following(current_user, user_id)

        return {**profile_data, "is_following": bool(is_following)}
    
    async def update_user_role(self, user_id: int, new_role: str, current_user: User):
        user_to_update = await self.get_by_id_or_raise(user_id)

        if new_role not in ALLOWED_ROLES:
            raise HTTPException(status_code=400, detail="Role does not exist")

        if user_id == current_user.id and new_role != "admin":
            raise HTTPException(status_code=400, detail="You cannot remove your own admin role")

        user_to_update.role = new_role

        await self.base_repo.commit_refresh(user_to_update)

        await redis_delete(f"user:{user_to_update.id}:profile")

        return {
            "message": "User role updated successfully",
            "user": user_to_update
        }
    
    async def update_user(self, user_id: int, user: UserUpdate, current_user: User):
        if current_user.role != "admin":
            raise PermissionDeniedError()
        
        user_to_update = await self.get_by_id_or_raise(user_id)

        duplicate_email = await self.repo.get_user_by_email(user.email)
        if duplicate_email and duplicate_email.id != user_to_update.id:
            raise HTTPException(status_code=400, detail="Email already exists")

        user_to_update.name = user.name
        user_to_update.email = user.email

        await self.base_repo.commit_refresh(user_to_update)

        await redis_delete(f"user:{user_to_update.id}:profile")

        return {
            "message": "User updated successfully",
            "user": user_to_update
        }
    
    async def unfollow_user(self, user_id: int, current_user: User):
        user_to_unfollow = await self.get_by_id_or_raise(user_id)

        follow = await self.repo.get_following(current_user, user_id)

        if not follow:
            raise AlreadyUnfollowingError()
        
        await self.base_repo.delete(follow)

        await invalidate_follow_cache(user_id, current_user)

        return {
            "message": f"You are no longer following user {user_to_unfollow.name}"
        }
