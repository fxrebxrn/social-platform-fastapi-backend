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

async def fetch_first_by_stmt(db: AsyncSession, stmt):
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_user_by_id_or_404():
    pass

async def get_scalar_result(db: AsyncSession, stmt):
    result = await db.execute(stmt)
    return result.scalar()
