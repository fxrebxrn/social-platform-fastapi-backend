from sqlalchemy.ext.asyncio import AsyncSession
from models import Post, Like, Comment, Follow
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from utils.query_helpers import fetch_all_by_stmt, fetch_first_by_stmt, get_scalar_result

class PostRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, post_id: int):
        stmt = select(Post).options(selectinload(Post.attachments)).where(Post.id == post_id)
        return await fetch_first_by_stmt(self.db, stmt)
    
    async def get_by_id_n_user(self, post_id: int):
        stmt = select(Post).options(selectinload(Post.user), selectinload(Post.attachments)).where(Post.id == post_id)
        return await fetch_first_by_stmt(self.db, stmt)

    async def get_likes_count(self, post_id: int):
        stmt = select(func.count()).select_from(Like).where(Like.post_id == post_id)
        return await get_scalar_result(self.db, stmt)
    
    async def get_comments_by_post_id(self, post_id: int):
        stmt = select(Comment).options(selectinload(Comment.user)).where(Comment.post_id == post_id).order_by(Comment.created_at.desc())
        return await fetch_all_by_stmt(self.db, stmt)
    
    async def get_comments_by_comment_id(self, comment_id: int):
        stmt = select(Comment).options(selectinload(Comment.user)).where(Comment.id == comment_id)
        return await fetch_first_by_stmt(self.db, stmt)
    
    async def get_posts_by_user_id(self, user_id: int):
        stmt = select(Post).where(Post.user_id == user_id).options(selectinload(Post.attachments), selectinload(Post.user))
        return await fetch_all_by_stmt(self.db, stmt)

    async def get_following_ids(self, user_id):
        stmt = select(Follow.following_id).where(Follow.follower_id == user_id)
        return await fetch_all_by_stmt(self.db, stmt)
    
    async def get_count_posts_by_following(self, following_ids):
        stmt = select(func.count()).select_from(Post).where(Post.user_id.in_(following_ids))
        return await get_scalar_result(self.db, stmt)

    async def get_posts_by_following_limit_offset(self, following_ids, limit: int, offset: int):
        stmt = (select(Post).options(selectinload(Post.user), selectinload(Post.attachments)).where(Post.user_id.in_(following_ids)).order_by(Post.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                    )
        return await fetch_all_by_stmt(self.db, stmt)
