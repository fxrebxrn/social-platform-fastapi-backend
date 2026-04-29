from sqlalchemy.ext.asyncio import AsyncSession
from models import PostAttachment
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from utils.query_helpers import fetch_first_by_stmt, get_scalar_result

class AttachmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_post_attachment_count(self, post_id: int):
        stmt = select(func.count()).select_from(PostAttachment).where(PostAttachment.post_id == post_id)
        return await get_scalar_result(self.db, stmt)
    
    async def get_post_attachment_with_post(self, attachment_id: int):
        stmt = select(PostAttachment).options(selectinload(PostAttachment.post)).where(PostAttachment.id == attachment_id)
        return await fetch_first_by_stmt(self.db, stmt)
