from models import User, Post, Comment, Like, Follow, Chat
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from sqlalchemy import select, func
from core.exceptions import NotFoundError, UserNotFoundError, CommentNotFoundError, ChatNotFoundError

async def fetch_all_by_stmt(db: AsyncSession, stmt):
    result = await db.execute(stmt)
    return result.scalars().all()

async def fetch_first_by_stmt_or_404(db: AsyncSession, stmt):
    result = await db.execute(stmt)
    fetch = result.scalars().first()

    if not fetch:
        raise NotFoundError()
    return fetch

async def get_user_by_id(db: AsyncSession, user_id: int):
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_user_by_id_or_404(db: AsyncSession, user_id: int):
    user = await get_user_by_id(db, user_id)
    if not user:
        raise UserNotFoundError()
    return user

async def get_user_by_name(db: AsyncSession, name: str):
    stmt = select(User).where(User.name.ilike(name))
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_user_or_404(db: AsyncSession, name: str):
    user = await get_user_by_name(db, name)
    if not user:
        raise UserNotFoundError()
    return user

async def get_user_by_email(db: AsyncSession, email: str):
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_comment_by_id_or_404(db: AsyncSession, comment_id: int):
    stmt = select(Comment).where(Comment.id == comment_id)
    result = await db.execute(stmt)
    comment = result.scalars().first()

    if not comment:
        raise CommentNotFoundError()
    return comment

async def get_like_by_user_and_post(db: AsyncSession, user_id: int, post_id: int):
    stmt = select(Like).where(Like.user_id == user_id, Like.post_id == post_id)
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_followers_count(db: AsyncSession, user_id: int):
    stmt = select(func.count()).select_from(Follow).where(Follow.following_id == user_id)
    result = await db.execute(stmt)
    followers_count = result.scalar()

    return followers_count

async def get_following_count(db: AsyncSession, user_id: int):
    stmt = select(func.count()).select_from(Follow).where(Follow.follower_id == user_id)
    result = await db.execute(stmt)
    followings_count = result.scalar()

    return followings_count

async def get_chat_if_participant(db: AsyncSession, chat_id: int, current_user_id: int):
    stmt = select(Chat).where(Chat.id == chat_id)
    result = await db.execute(stmt)
    chat = result.scalars().first()

    if not chat:
        raise ChatNotFoundError()
    
    if current_user_id not in [chat.user1_id, chat.user2_id]:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    return chat

async def get_scalar_result(db: AsyncSession, stmt):
    result = await db.execute(stmt)
    return result.scalar()
