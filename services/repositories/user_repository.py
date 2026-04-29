from sqlalchemy.ext.asyncio import AsyncSession
from utils.query_helpers import fetch_first_by_stmt, get_scalar_result, fetch_all_by_stmt
from models import User, Follow
from sqlalchemy import select, func

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int):
        stmt = select(User).where(User.id == user_id)
        return await fetch_first_by_stmt(self.db, stmt)

    async def get_user_by_email(self, email: str):
        stmt = select(User).where(User.email == email)
        return await fetch_first_by_stmt(self.db, stmt)
    
    async def get_followers_count(self, user_id: int):
        stmt = select(func.count()).select_from(Follow).where(Follow.following_id == user_id)
        return await get_scalar_result(self.db, stmt)

    async def get_following_count(self, user_id: int):
        stmt = select(func.count()).select_from(Follow).where(Follow.follower_id == user_id)
        return await get_scalar_result(self.db, stmt)
    
    async def get_following(self, current_user, user_id):
        stmt = select(Follow).where(Follow.follower_id == current_user.id, Follow.following_id == user_id)
        return await fetch_first_by_stmt(self.db, stmt)
    
    async def search_user_by_letters(self, name: str, limit: int, offset: int):
        stmt = select(User).where(User.name.ilike(f"%{name}%")).limit(limit).offset(offset)
        return await fetch_all_by_stmt(self.db, stmt)
    
    async def get_user_followers(self, user_id):
        stmt = select(User).join(Follow, Follow.follower_id == User.id).where(Follow.following_id == user_id)
        return await fetch_all_by_stmt(self.db, stmt)
    
    async def get_user_followings(self, user_id):
        stmt = select(User).join(Follow, Follow.following_id == User.id).where(Follow.follower_id == user_id)
        return await fetch_all_by_stmt(self.db, stmt)
    
    