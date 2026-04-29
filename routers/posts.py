from fastapi import APIRouter, Depends, UploadFile, File
from schemas.post_schemas import PostCreate, PaginatedPostResponse, PostUpdate, CommentCreate, WithMessagePostOut, WithMessageCommentOut, PostWithUser, PostCommentsResponse, FullPostResponse
from models import User
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from services.post_service import PostService
from typing import Annotated
from core.security import get_current_user
from schemas.util_schemas import AttachmentResponse, MessageResponse
from services.attachment_service import AttachmentService

router = APIRouter(prefix="/posts", tags=["Posts"])

@router.post("/", response_model=WithMessagePostOut)
async def create_post(post: PostCreate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    return await service.new_post(post, current_user)

@router.post("/{post_id}/comments", response_model=WithMessageCommentOut)
async def add_comment(post_id: int, comment: CommentCreate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    return await service.add_comment(post_id, comment, current_user)

@router.post("/{post_id}/attachments", response_model=AttachmentResponse)
async def upload_attachments_for_post(post_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)], files: list[UploadFile] = File(...)):
    service = PostService(db)
    return await service.add_attachments(post_id, files, current_user)

@router.post("/{post_id}/like", response_model=MessageResponse)
async def add_like(post_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    return await service.add_like(post_id, current_user)

@router.get("/user/{user_id}", response_model=list[PostWithUser])
async def get_user_posts(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    return await service.get_user_posts(user_id)

@router.get("/{post_id}/likes/count", response_model=MessageResponse)
async def get_likes_on_post(post_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    return await service.get_likes_on_post(post_id)

@router.get("/{post_id}/like-status", response_model=MessageResponse)
async def like_status(post_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    return await service.like_status(post_id, current_user)

@router.get("/my", response_model=list[PostWithUser])
async def get_my_posts(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    return await service.get_my_posts(current_user)

@router.get("/feed", response_model=PaginatedPostResponse)
async def get_user_feed(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)], limit: int = 50, offset: int = 0):
    service = PostService(db)
    return await service.get_user_feed(current_user, limit, offset)

@router.get("/{post_id}/comments", response_model=PostCommentsResponse)
async def get_post_comments(post_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    return await service.get_post_comments(post_id)

@router.get("/{post_id}", response_model=FullPostResponse)
async def get_full_post(post_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    return await service.get_full_post_data(post_id, current_user.id)

@router.put("/{post_id}", response_model=WithMessagePostOut)
async def update_post(post_id: int, post: PostUpdate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    return await service.update_post(post_id, post, current_user)

@router.delete("/attachments/{attachment_id}", response_model=MessageResponse)
async def remove_att_from_post(attachment_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = AttachmentService(db)
    return await service.delete_post_attachment(attachment_id, current_user)

@router.delete("/{post_id}/like", response_model=MessageResponse)
async def remove_like(post_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    return await service.remove_like(post_id, current_user)

@router.delete("/{post_id}", response_model=MessageResponse)
async def delete_post(post_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    return await service.delete_post(post_id, current_user)

@router.delete("/comments/{comment_id}", response_model=MessageResponse)
async def delete_comment(comment_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = PostService(db)
    return await service.delete_comment(comment_id, current_user)
