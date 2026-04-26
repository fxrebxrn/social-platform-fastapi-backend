from models import Post, Comment, Like
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from utils.query_helpers import fetch_all_by_stmt, get_like_by_user_and_post
from utils.serializers import post_to_dict
from utils.comment_tree import build_comment_tree
from utils.redis_cache import redis_get, redis_set
from core.exceptions import PostNotFoundError, PermissionDeniedError
from schemas.post_schemas import PostData, UserShort, CommentOut

class PostService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_post_by_id_or_raise(self, post_id: int):
        stmt = select(Post).where(Post.id == post_id).options(selectinload(Post.attachments))
        result = await self.db.execute(stmt)
        post = result.scalars().first()
        if not post:
            raise PostNotFoundError()
        return post

    async def get_post_with_author(self, post_id: int):
        stmt_post = select(Post).options(selectinload(Post.user), selectinload(Post.attachments)).where(Post.id == post_id)
        result_post = await self.db.execute(stmt_post)
        post = result_post.scalars().first()

        if not post:
            raise PostNotFoundError()
        
        return post
        
    async def get_likes_count(self, post_id: int):
        stmt = select(func.count()).select_from(Like).where(Like.post_id == post_id)
        result = await self.db.execute(stmt)
        likes_count = result.scalar()

        return likes_count
    
    async def is_post_liked(self, post_id: int, user_id: int):
        like = await get_like_by_user_and_post(self.db, user_id, post_id)

        return bool(like)
    
    async def get_post_comments(self, post_id: int):
        stmt_comments = select(Comment).options(selectinload(Comment.user)).where(Comment.post_id == post_id).order_by(Comment.created_at.desc())
        comments = await fetch_all_by_stmt(self.db, stmt_comments)

        return build_comment_tree(comments)

    async def get_full_post_data(self, post_id: int, current_user_id: int):
        cache_key = f"post:{post_id}:full"
        cached = await redis_get(cache_key)
        
        if not cached:
            post = await self.get_post_with_author(post_id)

            post_data = PostData.model_validate(post).model_dump(mode='json')
            author_data = UserShort.model_validate(post.user).model_dump(mode='json')
            comments_data = [CommentOut.model_validate(c).model_dump(mode='json') 
                            for c in await self.get_post_comments(post_id)]

            cached = {
                "post": post_data,
                "author": author_data,
                "likes_count": await self.get_likes_count(post_id),
                "comments": comments_data
            }
            await redis_set(cache_key, cached, ttl=60)

        return {
            **cached, 
            "is_liked": await self.is_post_liked(post_id, current_user_id),
        }

    def ensure_can_modify_post(self, post, user):
        if post.user_id != user.id and user.role not in ["admin", "moderator"]:
            raise PermissionDeniedError()
