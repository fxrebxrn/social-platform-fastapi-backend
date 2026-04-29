from models import User, Post, Comment, Notification, Like
from sqlalchemy.ext.asyncio import AsyncSession
from utils.query_helpers import get_comment_by_id_or_404, get_user_by_id_or_404
from utils.comment_tree import build_comment_tree
from utils.redis_cache import redis_get, redis_set, redis_delete, redis_delete_many, invalidate_notify_cache
from core.exceptions import PostNotFoundError, PermissionDeniedError
from schemas.post_schemas import PostData, UserShort, CommentOut, PostCreate, CommentCreate, PostWithUser, PostUpdate
from services.post_repository import PostRepository
from utils.media import delete_media_file
from fastapi import UploadFile, HTTPException
from services.attachment_service import AttachmentService
from utils.permissions import ensure_can_modify_post as check_can_modify_post
from services.base_repository import BaseRepository
from services.user_service import UserService

class PostService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PostRepository(db)
        self.att = AttachmentService(db)
        self.base_repo = BaseRepository(db)
        self.user = UserService(db)

    async def get_post_by_id_or_raise(self, post_id: int):
        post = await self.repo.get_by_id(post_id)
        if not post:
            raise PostNotFoundError()
        return post

    async def get_post_with_author(self, post_id: int):
        post = await self.repo.get_by_id_n_user(post_id)
        if not post:
            raise PostNotFoundError()
        return post
    
    async def get_post_comments_tree(self, post_id: int):
        comments = await self.repo.get_comments_by_post_id(post_id)
        return build_comment_tree(comments)

    async def get_full_post_data(self, post_id: int, current_user_id: int):
        cache_key = f"post:{post_id}:full"
        cached = await redis_get(cache_key)
        
        if not cached:
            post = await self.get_post_with_author(post_id)

            post_data = PostData.model_validate(post).model_dump(mode='json')
            author_data = UserShort.model_validate(post.user).model_dump(mode='json')
            comments_data = [CommentOut.model_validate(c).model_dump(mode='json') 
                            for c in await self.get_post_comments_tree(post_id)]

            cached = {
                "post": post_data,
                "author": author_data,
                "likes_count": await self.repo.get_likes_count(post_id),
                "comments": comments_data
            }
            await redis_set(cache_key, cached, ttl=60)

        return {
            **cached, 
            "is_liked": bool(await self.repo.get_like_by_user_and_post(current_user_id, post_id))
        }

    def ensure_can_modify_post(self, post, user):
        check_can_modify_post(post, user)
        
    async def delete_post(self, post_id: int, current_user: User):
        post = await self.get_post_by_id_or_raise(post_id)
        
        self.ensure_can_modify_post(post, current_user)

        for att in post.attachments:
            delete_media_file(att.file_url)

        await self.base_repo.delete(post)
        
        keys = [
            f"post:{post.id}:full",
            f"post:{post.id}:likes",
            f"post:{post.id}:comments"
        ]
        await redis_delete_many(keys)

        return {
            "message": "Post deleted"
        }
    
    async def add_attachments(self, post_id, files: list[UploadFile], current_user: User):
        post = await self.get_post_by_id_or_raise(post_id)
        self.ensure_can_modify_post(post, current_user)

        return await self.att.add_post_attachments(post, files)

    async def new_post(self, post: PostCreate, current_user: User):
        new_post = Post(
            title=post.title,
            user_id=current_user.id
        )

        await self.base_repo.add(new_post)
        await redis_delete(f"user:{current_user.id}:posts")

        created_post = await self.repo.get_by_id_n_user(new_post.id)

        return {
            "message": "Post created",
            "post": created_post
        }

    async def add_comment(self, post_id: int, comment: CommentCreate, current_user: User):
        post = await self.get_post_by_id_or_raise(post_id)

        parent_comment = None

        if comment.parent_id is not None and comment.parent_id < 1:
            raise HTTPException(status_code=400, detail="Invalid parent comment ID")

        if comment.parent_id is not None:
            parent_comment = await get_comment_by_id_or_404(self.db, comment.parent_id)
            if parent_comment.post_id != post_id:
                raise HTTPException(status_code=400, detail="Parent comment does not belong to the post")
            
            new_comment = Comment(
                text=comment.text,
                user_id=current_user.id,
                post_id=post_id,
                parent_id=comment.parent_id
            )
        else:
            new_comment = Comment(
                text=comment.text,
                user_id=current_user.id,
                post_id=post_id
            )

        self.db.add(new_comment)

        if post.user_id != current_user.id:
            post_notify = Notification(
                user_id=post.user_id,
                sender_id=current_user.id,
                message=f"{current_user.name} commented on your post",
                notification_type="comment"
            )
            await invalidate_notify_cache(post.user_id)
            self.db.add(post_notify)

        if parent_comment and parent_comment.user_id != current_user.id and parent_comment.user_id != post.user_id:
            reply_notify = Notification(
                user_id=parent_comment.user_id,
                sender_id=current_user.id,
                message=f"{current_user.name} replied to your comment",
                notification_type="reply"
            )
            await invalidate_notify_cache(parent_comment.user_id)
            self.db.add(reply_notify)

        await self.base_repo.commit_refresh(new_comment)
        await redis_delete(f"post:{post_id}:comments")
        await redis_delete(f"post:{post_id}:full")

        created_comment = await self.repo.get_comments_by_comment_id(new_comment.id)

        return {
            "message": "Comment added successfully",
            "comment": created_comment
        }

    async def add_like(self, post_id: int, current_user: User):
        post = await self.get_post_by_id_or_raise(post_id)

        if await self.repo.get_like_by_user_and_post(current_user.id, post_id):
            raise HTTPException(status_code=400, detail="Like already exists")
        
        new_like = Like(
            user_id=current_user.id,
            post_id=post_id
        )

        if post.user_id != current_user.id:
            new_notify = Notification(
                user_id=post.user_id,
                sender_id=current_user.id,
                post_id=post.id,
                message=f"User {current_user.name} liked your post: {post.title}",
                notification_type="like"
            )
            await invalidate_notify_cache(post.user_id)
            self.db.add(new_notify)

        await self.base_repo.add(new_like)
        await redis_delete(f"post:{post_id}:full")
        await redis_delete(f"post:{post_id}:likes")

        return {
            "message": f"Like successfully added on post {post_id}"
        }
    
    async def get_user_posts(self, user_id: int):
        cache_key = f"user:{user_id}:posts"
        cached = await redis_get(cache_key)

        if cached:
            return cached
        
        await self.user.get_by_id_or_raise(user_id)
        
        posts = await self.repo.get_posts_by_user_id(user_id)

        posts_data = [
            PostWithUser.model_validate(p).model_dump(mode="json") for p in posts
        ]

        await redis_set(cache_key, posts_data, ttl=60)

        return posts_data

    async def get_likes_on_post(self, post_id: int):
        cache_key = f"post:{post_id}:likes"
        cached = await redis_get(cache_key)

        if cached:
            return cached
        
        await self.get_post_by_id_or_raise(post_id)
        
        count_likes = await self.repo.get_likes_count(post_id)

        cached_data = {
            "message": count_likes
        }

        await redis_set(cache_key, cached_data, ttl=30)

        return cached_data
    
    async def like_status(self, post_id: int, current_user: User):
        cache_key = f"post:{post_id}:user:{current_user.id}:like-status"
        cached = await redis_get(cache_key)
        if cached:
            return cached
    
        await self.get_post_by_id_or_raise(post_id)

        like = await self.repo.get_like_by_user_and_post(current_user.id, post_id)

        like_data = {
            "message": bool(like)
        }

        await redis_set(cache_key, like_data, ttl=600)

        return like_data
    
    async def get_my_posts(self, current_user: User):
        cache_key = f"user:{current_user.id}:posts"
        cached = await redis_get(cache_key)

        if cached:
            return cached
        
        posts = await self.repo.get_posts_by_user_id(current_user.id)

        posts_data = [
            PostWithUser.model_validate(p).model_dump(mode="json") for p in posts
        ]

        await redis_set(cache_key, posts_data, ttl=60)

        return posts_data

    async def get_user_feed(self, current_user: User, limit: int = 50, offset: int = 0):
        cache_key = f"user:{current_user.id}:feed:{limit}:{offset}"
        cached = await redis_get(cache_key)

        if cached:
            return cached
        
        if limit > 50:
            limit = 50
        
        following_ids = await self.repo.get_following_ids(current_user.id)

        if not following_ids:
            return {
                "items": [],
                "limit": limit,
                "offset": offset,
                "total": 0
            }
        
        total = await self.repo.get_count_posts_by_following(following_ids)
        posts = await self.repo.get_posts_by_following_limit_offset(following_ids, limit, offset)

        items_json = [PostWithUser.model_validate(p).model_dump(mode='json') for p in posts]
        
        response_data = {
            "items": items_json,
            "limit": limit,
            "offset": offset,
            "total": total
        }
        
        await redis_set(cache_key, response_data, ttl=300)
        return response_data

    async def get_post_comments(self, post_id: int):
        cache_key = f"post:{post_id}:comments"
        cached = await redis_get(cache_key)

        if cached:
            return cached
        
        await self.get_post_by_id_or_raise(post_id)
        
        tree = await self.get_post_comments_tree(post_id)

        tree_json = [CommentOut.model_validate(c).model_dump(mode='json') for c in tree]

        comments_data = {
            "comments": tree_json
        }

        await redis_set(cache_key, comments_data, ttl=300)

        return comments_data

    async def update_post(self, post_id: int, post: PostUpdate, current_user: User):
        post_to_update = await self.get_post_by_id_or_raise(post_id)

        self.ensure_can_modify_post(post_to_update, current_user)

        if post_to_update.title.strip() == post.title.strip():
            raise HTTPException(status_code=400, detail="New title must be different from the current one")

        post_to_update.title = post.title

        await self.base_repo.commit_refresh(post_to_update)
        await redis_delete(f"post:{post_id}:full")

        updated_post = await self.repo.get_by_id_n_user(post_id)

        return {
            "message": "Post updated successfully",
            "post": updated_post
        }

    async def remove_like(self, post_id: int, current_user: User):
        await self.get_post_by_id_or_raise(post_id)

        like = await self.repo.get_like_by_user_and_post(current_user.id, post_id)

        if not like:
            raise HTTPException(status_code=404, detail="Like not found")
        
        await self.base_repo.delete(like)
        await redis_delete(f"post:{post_id}:full")
        await redis_delete(f"post:{post_id}:likes")

        return {
            "message": f"Like has been removed from post {post_id}"
        }
    
    async def delete_comment(self, comment_id: int, current_user: User):
        comment = await get_comment_by_id_or_404(self.db, comment_id)

        if comment.user_id != current_user.id and current_user.role not in ["admin", "moderator"]:
            raise PermissionDeniedError()
        
        await self.base_repo.delete(comment)
        await redis_delete(f"post:{comment.post_id}:full")
        await redis_delete(f"post:{comment.post_id}:comments")

        return {
            "message": "Comment deleted"
        }
