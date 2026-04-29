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

async def get_user_by_id():
    pass

async def get_user_by_id_or_404():
    pass

async def get_user_by_email():
    pass

async def fetch_first_by_stmt(db: AsyncSession, stmt):
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_comment_by_id_or_404(db: AsyncSession, comment_id: int):
    stmt = select(Comment).where(Comment.id == comment_id)
    result = await db.execute(stmt)
    comment = result.scalars().first()

    if not comment:
        raise CommentNotFoundError()
    return comment

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
