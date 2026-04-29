from sqlalchemy.ext.asyncio import AsyncSession
from models import Chat, Message
from sqlalchemy import select, func, or_, update
from sqlalchemy.orm import selectinload, aliased
from utils.query_helpers import fetch_first_by_stmt, get_scalar_result, fetch_all_by_stmt

class ChatRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, chat_id: int):
        stmt = select(Chat).where(Chat.id == chat_id)
        return await fetch_first_by_stmt(self.db, stmt)
    
    async def get_full_message(self, message_id):
        stmt = (
            select(Message)
            .options(selectinload(Message.attachments), selectinload(Message.sender), selectinload(Message.chat))
            .where(Message.id == message_id)
        )
        return await fetch_first_by_stmt(self.db, stmt)
    
    async def get_message_by_id(self, message_id):
        stmt = select(Message).where(Message.id == message_id)
        return await fetch_first_by_stmt(self.db, stmt)

    async def get_chat_by_users(self, user1, user2):
        stmt = select(Chat).where(Chat.user1_id == user1, Chat.user2_id == user2)
        return await fetch_first_by_stmt(self.db, stmt)
    
    async def get_messages(self, chat_id, limit, offset):
        stmt = select(Message).options(selectinload(Message.sender), selectinload(Message.attachments)).where(Message.chat_id == chat_id).order_by(Message.created_at.asc()).limit(limit).offset(offset)
        return await fetch_all_by_stmt(self.db, stmt)
    
    async def get_unread_count(self, chat_id, current_user):
        stmt = select(func.count()).select_from(Message).where(Message.chat_id == chat_id, Message.sender_id != current_user.id, Message.is_read == False)
        return await get_scalar_result(self.db, stmt)

    async def get_all_chats(self, current_user, limit, offset) -> list[dict]:
        unread_subq = (
            select(Message.chat_id, func.count(Message.id).label("count"))
            .where(Message.sender_id != current_user.id, Message.is_read == False)
            .group_by(Message.chat_id)
            .subquery()
        )

        last_msg_subq = (
            select(
                Message,
                func.row_number().over(
                    partition_by=Message.chat_id, 
                    order_by=Message.id.desc()
                ).label("rn")
            )
            .subquery()
        )
        last_msg_alias = aliased(Message, last_msg_subq)

        stmt = (
            select(
                Chat, 
                func.coalesce(unread_subq.c.count, 0).label("unread_count"),
                last_msg_alias
            )
            .outerjoin(unread_subq, Chat.id == unread_subq.c.chat_id)
            .outerjoin(last_msg_subq, (Chat.id == last_msg_subq.c.chat_id) & (last_msg_subq.c.rn == 1))
            .options(
                selectinload(Chat.user1), 
                selectinload(Chat.user2),
                selectinload(last_msg_alias.sender),
                selectinload(last_msg_alias.attachments)
            )
            .where(or_(Chat.user1_id == current_user.id, Chat.user2_id == current_user.id))
            .order_by(Chat.updated_at.desc()).limit(limit).offset(offset)
        )

        result = await self.db.execute(stmt)
        
        result_data = []
        for chat, unread_count, last_message in result.all():
            partner = chat.user1 if chat.user2_id == current_user.id else chat.user2
            
            result_data.append({
                "chat_id": chat.id,
                "partner": partner,
                "last_message": last_message,
                "unread_count": unread_count,
                "created_at": chat.created_at,
                "updated_at": chat.updated_at
            })

        return result_data 
    
    async def read_all(self, chat_id, current_user):
        stmt = update(Message).where(Message.chat_id == chat_id, Message.sender_id != current_user.id, Message.is_read == False).values(is_read=True)
        return await self.db.execute(stmt)
    
    async def get_chat_and_att_and_messages(self, chat_id):
        stmt = select(Chat).options(selectinload(Chat.messages).selectinload(Message.attachments)).where(Chat.id == chat_id)
        return await fetch_first_by_stmt(self.db, stmt)
