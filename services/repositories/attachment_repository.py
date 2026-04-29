from sqlalchemy.ext.asyncio import AsyncSession
from models import PostAttachment, MessageAttachment, Message
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
    
    async def get_count_message_att_by_id(self, message_id):
        stmt = select(func.count()).select_from(MessageAttachment).where(MessageAttachment.message_id == message_id)
        return await get_scalar_result(self.db, stmt)

    async def get_att_message(self, attachment_id):
        stmt = select(MessageAttachment).options(selectinload(MessageAttachment.message)).where(MessageAttachment.id == attachment_id)
        return await fetch_first_by_stmt(self.db, stmt)

    async def get_messages_by_id(self, message_id):
        stmt = select(Message).options(selectinload(Message.attachments)).where(Message.id == message_id)
        return await fetch_first_by_stmt(self.db, stmt)
