from fastapi import HTTPException, APIRouter, Depends, UploadFile, File
from schemas.post_schemas import PostCreate, PaginatedPostResponse, PostUpdate, CommentCreate, WithMessagePostOut, WithMessageCommentOut, PostWithUser, PostCommentsResponse, FullPostResponse, CommentOut
from models import Post, User, Comment, Like, Follow, Notification, PostAttachment
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from core.database import get_db
from utils.query_helpers import get_user_by_id_or_404, get_comment_by_id_or_404, fetch_all_by_stmt, get_like_by_user_and_post, fetch_first_by_stmt_or_404
from utils.comment_tree import build_comment_tree
from services.post_service import PostService
from typing import Annotated
from core.security import get_current_user
from utils.redis_cache import redis_delete, redis_set, redis_get
import os
import uuid
from schemas.util_schemas import AttachmentResponse, MessageResponse
from schemas.user_schemas import UserShort
from core.exceptions import PermissionDeniedError
from utils.media import delete_media_file, generate_filename, get_attachment_type

router = APIRouter(prefix="/posts", tags=["Posts"])

@router.post("/", response_model=WithMessagePostOut)
async def create_post(post: PostCreate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    new_post = Post(
        title=post.title,
        user_id=current_user.id
    )

    db.add(new_post)
    await db.commit()
    await db.refresh(new_post)
    await redis_delete(f"user:{current_user.id}:posts")

    stmt = select(Post).where(Post.id == new_post.id).options(selectinload(Post.attachments), selectinload(Post.user))
    created_post = await fetch_first_by_stmt_or_404(db, stmt)

    return {
        "message": "Post created",
        "post": created_post
    }

@router.post("/{post_id}/comments", response_model=WithMessageCommentOut)
async def add_comment(post_id: int, comment: CommentCreate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    post = await service.get_post_by_id_or_raise(post_id)

    parent_comment = None

    if comment.parent_id is not None and comment.parent_id < 1:
        raise HTTPException(status_code=400, detail="Invalid parent comment ID")

    if comment.parent_id is not None:
        parent_comment = await get_comment_by_id_or_404(db, comment.parent_id)
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

    db.add(new_comment)

    if post.user_id != current_user.id:
        post_notify = Notification(
            user_id=post.user_id,
            sender_id=current_user.id,
            message=f"{current_user.name} commented on your post",
            notification_type="comment"
        )
        await redis_delete(f"user:{post.user_id}:notifications:all")
        await redis_delete(f"user:{post.user_id}:notifications:unread-count")
        db.add(post_notify)

    if parent_comment and parent_comment.user_id != current_user.id and parent_comment.user_id != post.user_id:
        reply_notify = Notification(
            user_id=parent_comment.user_id,
            sender_id=current_user.id,
            message=f"{current_user.name} replied to your comment",
            notification_type="reply"
        )
        await redis_delete(f"user:{parent_comment.user_id}:notifications:all")
        await redis_delete(f"user:{parent_comment.user_id}:notifications:unread-count")
        db.add(reply_notify)

    await db.commit()
    await db.refresh(new_comment)
    await redis_delete(f"post:{post_id}:comments")
    await redis_delete(f"post:{post_id}:full")
    await redis_delete(f"user:{current_user.id}:notifications:all")
    await redis_delete(f"user:{current_user.id}:notifications:unread-count")

    stmt = select(Comment).options(selectinload(Comment.user)).where(Comment.id == new_comment.id)
    created_comment = await fetch_first_by_stmt_or_404(db, stmt)

    return {
        "message": "Comment added successfully",
        "comment": created_comment
    }

@router.post("/{post_id}/attachments", response_model=AttachmentResponse)
async def upload_attachments_for_post(post_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)], files: list[UploadFile] = File(...)):
    service = PostService(db)
    post = await service.get_post_by_id_or_raise(post_id)
    service.ensure_can_modify_post(post, current_user)

    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum of 5 attachments allowed")
    
    allowed_types = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "video/mp4",
        "audio/mpeg",
        "application/pdf",
        "text/plain"
    ]

    stmt_limit = select(func.count()).select_from(PostAttachment).where(PostAttachment.post_id == post_id)
    result_limit = await db.execute(stmt_limit)
    limit_count = result_limit.scalar()

    if limit_count + len(files) > 5:
        raise HTTPException(status_code=400, detail=f"Maximum 5 attachments per post. Already uploaded: {limit_count}")

    os.makedirs("media/post_attachments", exist_ok=True)

    created_attachments = []

    for file in files:
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Invalid file type")
        
        content = await file.read()

        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"File size must be less than 10 MB - {file.filename}")
        
        filename = generate_filename(file.filename)
        file_path = os.path.join("media", "post_attachments", filename)

        with open(file_path, "wb") as buffer:
            buffer.write(content)

        attachment = PostAttachment(
            post_id=post.id,
            file_url=f"post_attachments/{filename}",
            file_type=get_attachment_type(file.content_type),
            original_name=file.filename
        )

        db.add(attachment)
        created_attachments.append(attachment)
        await file.close()

    await db.commit()
    for att in created_attachments:
        await db.refresh(att)

    await redis_delete(f"post:{post_id}:full")

    return {
        "message": "Attachments upload successfully",
        "items": created_attachments
    }

@router.post("/{post_id}/like", response_model=MessageResponse)
async def add_like(post_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    post = await service.get_post_by_id_or_raise(post_id)

    if await get_like_by_user_and_post(db, current_user.id, post_id):
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
        await redis_delete(f"user:{post.user_id}:notifications:all")
        await redis_delete(f"user:{post.user_id}:notifications:unread-count")
        db.add(new_notify)

    
    db.add(new_like)
    await db.commit()
    await db.refresh(new_like)
    await redis_delete(f"post:{post_id}:full")
    await redis_delete(f"post:{post_id}:likes")

    return {
        "message": f"Like successfully added on post {post_id}"
    }

@router.get("/user/{user_id}", response_model=list[PostWithUser])
async def get_user_posts(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    cache_key = f"user:{user_id}:posts"
    cached = await redis_get(cache_key)

    if cached:
        return cached
    
    await get_user_by_id_or_404(db, user_id)
    
    stmt = select(Post).where(Post.user_id == user_id).options(selectinload(Post.attachments), selectinload(Post.user))
    posts = await fetch_all_by_stmt(db, stmt)

    posts_data = [
        PostWithUser.model_validate(p).model_dump(mode="json") for p in posts
    ]

    await redis_set(cache_key, posts_data, ttl=60)

    return posts_data

@router.get("/{post_id}/likes/count", response_model=MessageResponse)
async def get_likes_on_post(post_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    cache_key = f"post:{post_id}:likes"
    cached = await redis_get(cache_key)

    if cached:
        return cached
    
    service = PostService(db)
    await service.get_post_by_id_or_raise(post_id)
    
    stmt = select(func.count()).select_from(Like).where(Like.post_id == post_id)
    result = await db.execute(stmt)
    count_likes = result.scalar()

    cached_data = {
        "message": count_likes
    }

    await redis_set(cache_key, cached_data, ttl=30)

    return cached_data

@router.get("/{post_id}/like-status", response_model=MessageResponse)
async def like_status(post_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    cache_key = f"post:{post_id}:user:{current_user.id}:like-status"
    cached = await redis_get(cache_key)
    if cached:
        return cached
    
    service = PostService(db)
    await service.get_post_by_id_or_raise(post_id)

    like = await get_like_by_user_and_post(db, current_user.id, post_id)

    like_data = {
        "message": bool(like)
    }

    await redis_set(cache_key, like_data, ttl=600)

    return like_data

@router.get("/my", response_model=list[PostWithUser])
async def get_my_posts(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    cache_key = f"user:{current_user.id}:posts"
    cached = await redis_get(cache_key)

    if cached:
        return cached
    
    stmt = select(Post).where(Post.user_id == current_user.id).options(selectinload(Post.attachments), selectinload(Post.user))
    posts = await fetch_all_by_stmt(db, stmt)

    posts_data = [
        PostWithUser.model_validate(p).model_dump(mode="json") for p in posts
    ]

    await redis_set(cache_key, posts_data, ttl=60)

    return posts_data

@router.get("/feed", response_model=PaginatedPostResponse)
async def get_user_feed(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)], limit: int = 50, offset: int = 0):
    cache_key = f"user:{current_user.id}:feed:{limit}:{offset}"
    cached = await redis_get(cache_key)

    if cached:
        return cached
    
    if limit > 50:
        limit = 50
    
    stmt_following = select(Follow.following_id).where(Follow.follower_id == current_user.id)
    result_following = await db.execute(stmt_following)
    following_ids = result_following.scalars().all()

    if not following_ids:
        return {
            "items": [],
            "limit": limit,
            "offset": offset,
            "total": 0
        }
    
    stmt_count = select(func.count()).select_from(Post).where(Post.user_id.in_(following_ids))
    result_count = await db.execute(stmt_count)
    total = result_count.scalar()

    stmt_post = (select(Post)
                 .options(selectinload(Post.user), selectinload(Post.attachments))
                 .where(Post.user_id.in_(following_ids))
                 .order_by(Post.created_at.desc())
                 .limit(limit)
                 .offset(offset)
                 )
    result_post = await db.execute(stmt_post)
    posts = result_post.scalars().all()

    items_json = [PostWithUser.model_validate(p).model_dump(mode='json') for p in posts]
    
    response_data = {
        "items": items_json,
        "limit": limit,
        "offset": offset,
        "total": total
    }
    
    await redis_set(cache_key, response_data, ttl=300)
    return response_data

@router.get("/{post_id}/comments", response_model=PostCommentsResponse)
async def get_post_comments(post_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    cache_key = f"post:{post_id}:comments"
    cached = await redis_get(cache_key)

    if cached:
        return cached
    
    service = PostService(db)
    await service.get_post_by_id_or_raise(post_id)
    
    stmt = select(Comment).options(selectinload(Comment.user)).where(Comment.post_id == post_id).order_by(Comment.created_at.desc())
    comments = await fetch_all_by_stmt(db, stmt)
    
    tree = build_comment_tree(comments)

    tree_json = [CommentOut.model_validate(c).model_dump(mode='json') for c in tree]

    comments_data = {
        "comments": tree_json
    }

    await redis_set(cache_key, comments_data, ttl=300)

    return comments_data

@router.get("/{post_id}", response_model=FullPostResponse)
async def get_full_post(post_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)

    return await service.get_full_post_data(post_id, current_user.id)

@router.put("/{post_id}", response_model=WithMessagePostOut)
async def update_post(post_id: int, post: PostUpdate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    post_to_update = await service.get_post_by_id_or_raise(post_id)

    service.ensure_can_modify_post(post_to_update, current_user)

    if post_to_update.title.strip() == post.title.strip():
        raise HTTPException(status_code=400, detail="New title must be different from the current one")

    post_to_update.title = post.title

    await db.commit()
    await db.refresh(post_to_update)
    await redis_delete(f"post:{post_id}:full")

    stmt = select(Post).where(Post.id == post_to_update.id).options(selectinload(Post.attachments), selectinload(Post.user))
    updated_post = await fetch_first_by_stmt_or_404(db, stmt)

    return {
        "message": "Post updated successfully",
        "post": updated_post
    }

@router.delete("/attachments/{attachment_id}", response_model=MessageResponse)
async def remove_att_from_post(attachment_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    stmt_att = select(PostAttachment).options(selectinload(PostAttachment.post).selectinload(Post.attachments)).where(PostAttachment.id == attachment_id)
    result_att = await db.execute(stmt_att)
    att = result_att.scalars().first()

    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    service = PostService(db)
    service.ensure_can_modify_post(att.post, current_user)
    for a in att.post.attachments:
        delete_media_file(a.file_url)

    post_id = att.post_id

    await db.delete(att)
    await db.commit()
    await redis_delete(f"post:{post_id}:full")

    return {
        "message": f"Attachment from post {post_id} deleted successfully"
    }

@router.delete("/{post_id}/like", response_model=MessageResponse)
async def remove_like(post_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    await service.get_post_by_id_or_raise(post_id)

    like = await get_like_by_user_and_post(db, current_user.id, post_id)

    if not like:
        raise HTTPException(status_code=404, detail="Like not found")
    
    await db.delete(like)
    await db.commit()
    await redis_delete(f"post:{post_id}:full")
    await redis_delete(f"post:{post_id}:likes")

    return {
        "message": f"Like has been removed from post {post_id}"
    }

@router.delete("/{post_id}", response_model=MessageResponse)
async def delete_post(post_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    post = await service.get_post_by_id_or_raise(post_id)

    service.ensure_can_modify_post(post, current_user)
    
    await db.delete(post)
    await db.commit()
    await redis_delete(f"post:{post_id}:full")
    await redis_delete(f"post:{post_id}:likes")

    return {
        "message": "Post deleted"
    }

@router.delete("/comments/{comment_id}", response_model=MessageResponse)
async def delete_comment(comment_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    comment = await get_comment_by_id_or_404(db, comment_id)

    if comment.user_id != current_user.id and current_user.role not in ["admin", "moderator"]:
        raise PermissionDeniedError()
    
    await db.delete(comment)
    await db.commit()
    await redis_delete(f"post:{comment.post_id}:full")
    await redis_delete(f"post:{comment.post_id}:comments")

    return {
        "message": "Comment deleted"
    }
