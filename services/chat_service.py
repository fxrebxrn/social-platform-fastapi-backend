from sqlalchemy.ext.asyncio import AsyncSession
from services.repositories.chat_repository import ChatRepository
from services.repositories.base_repository import BaseRepository
from core.exceptions import ChatNotFoundError, MessageNotFoundError, PermissionDeniedError
from fastapi import HTTPException, UploadFile
from models import User, Message, Chat
from schemas.chat_schemas import MessageCreate, MessageItem, ChatListItem
from sqlalchemy import func
from utils.redis_cache import redis_delete_many, redis_delete_by_prefix, invalidate_chat_cache, redis_get, redis_set
from services.attachment_service import AttachmentService
from services.user_service import UserService
from services.repositories.attachment_repository import AttachmentRepository

class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ChatRepository(db)
        self.base_repo = BaseRepository(db)
        self.att = AttachmentService(db)
        self.user = UserService(db)
        self.att_repo = AttachmentRepository(db)

    async def get_if_participant(self, chat_id: int, current_user_id: int):
        chat = await self.repo.get_by_id(chat_id)
        
        if not chat:
            raise ChatNotFoundError()
        
        if current_user_id not in [chat.user1_id, chat.user2_id]:
            raise HTTPException(status_code=403, detail="Forbidden")
        
        return chat
    
    async def new_message(self, chat_id: int, message: MessageCreate, current_user: User):
        chat = await self.get_if_participant(chat_id, current_user.id)
        partner_id = chat.user1_id if chat.user2_id == current_user.id else chat.user2_id

        new_message = Message(
            sender_id=current_user.id,
            chat_id=chat.id,
            text=message.text
        )

        self.db.add(new_message)
        chat.updated_at = func.now()
        await self.db.commit()
        await invalidate_chat_cache(chat_id, current_user.id, partner_id)
        
        full_message = await self.repo.get_full_message(new_message.id)

        return {
            "message": "Message sent successfully",
            "data": full_message
        }
    

    async def upload_attachments_for_message(self, message_id: int, current_user: User, files: list[UploadFile]):
        message = await self.repo.get_message_by_id(message_id)

        if not message:
            raise MessageNotFoundError()
        
        chat = await self.get_if_participant(message.chat_id, current_user.id)
        partner_id = chat.user1_id if chat.user2_id == current_user.id else chat.user2_id

        if message.sender_id != current_user.id:
            raise PermissionDeniedError()
        
        return await self.att.upload_att_chat(partner_id, message, current_user, files)
    
    async def new_chat(self, user_id: int, current_user: User):
        if current_user.id == user_id:
            raise HTTPException(status_code=400, detail="You cannot start a chat with yourself")
        
        await self.user.get_by_id_or_raise(user_id)

        user1 = min(current_user.id, user_id)
        user2 = max(current_user.id, user_id)

        existing_chat = await self.repo.get_chat_by_users(user1, user2)

        if existing_chat:
            return {
                "message": "Chat already exists",
                "chat_id": existing_chat.id
            }
        
        new_chat = Chat(
            user1_id=user1,
            user2_id=user2
        )

        await self.base_repo.add(new_chat)
        await redis_delete_by_prefix(f"user:{current_user.id}:all-chats")
        await redis_delete_by_prefix(f"user:{user_id}:all-chats")

        return {
            "message": "Chat created successfully",
            "chat_id": new_chat.id
        }
    
    async def get_messages_from_chat(self, chat_id: int, current_user: User, limit: int, offset: int):
        cache_key = f"chat:{chat_id}:messages:{limit}:{offset}"
        cached = await redis_get(cache_key)
        
        if cached:
            return cached
        
        if limit > 50:
            limit = 50

        await self.get_if_participant(chat_id, current_user.id)

        messages = await self.repo.get_messages(chat_id, limit, offset)

        messages_data = [
            MessageItem.model_validate(m).model_dump(mode="json") for m in messages
        ]

        await redis_set(cache_key, messages_data, 60)
        
        return messages_data

    async def get_count_of_unread_messages(self, chat_id: int, current_user: User):
        cache_key = f"chat:{chat_id}:user:{current_user.id}:unread-count"
        cached = await redis_get(cache_key)
        
        if cached:
            return cached
        
        await self.get_if_participant(chat_id, current_user.id)

        count = await self.repo.get_unread_count(chat_id, current_user)

        count_data = {
            "message": count
        }

        await redis_set(cache_key, count_data, 60)

        return count_data
    
    async def get_all_user_chats(self, current_user: User, limit: int, offset: int):
        cache_key = f"user:{current_user.id}:all-chats:{limit}:{offset}"
        cached = await redis_get(cache_key)
        
        if cached:
            return cached
        
        if limit > 50:
            limit = 50 
        
        result_data = await self.repo.get_all_chats(current_user, limit, offset)

        validated_items = []
        for item in result_data:
            validated_item = ChatListItem.model_validate(item).model_dump(mode="json")
            validated_items.append(validated_item)

        final_response = {"items": validated_items}

        await redis_set(cache_key, final_response, 60)

        return final_response
    
    async def read_all_messages_in_chat(self, chat_id: int, current_user: User):
        chat = await self.get_if_participant(chat_id, current_user.id)
        partner_id = chat.user1_id if chat.user2_id == current_user.id else chat.user2_id

        await self.repo.read_all(chat_id, current_user)
        await self.db.commit()
        await invalidate_chat_cache(chat_id, current_user, partner_id)

        return {
            "message": "All messages marked as read"
        }
    
    async def remove_att_from_message(self, attachment_id: int, current_user: User):
        att = await self.att_repo.get_att_message(attachment_id)

        if not att:
            raise HTTPException(status_code=404, detail="Attachment not found")

        chat = await self.get_if_participant(att.message.chat_id, current_user.id)
        partner_id = chat.user1_id if chat.user2_id == current_user.id else chat.user2_id

        if att.message.sender_id != current_user.id:
            raise HTTPException(status_code=403, detail="You are not the sender of this message")
        
        return await self.att.remove_att_message(att, partner_id, current_user)
    
    async def remove_message(self, message_id: int, current_user: User):
        message = await self.att_repo.get_messages_by_id(message_id)

        if not message:
            raise MessageNotFoundError()

        chat = await self.get_if_participant(message.chat_id, current_user.id)
        partner_id = chat.user1_id if chat.user2_id == current_user.id else chat.user2_id

        if message.sender_id != current_user.id:
            raise PermissionDeniedError()

        return await self.att.remove_att_from_deleted_message(message_id, message, current_user, partner_id)
    
    async def delete_chat(self, chat_id: int, current_user: User):
        await self.get_if_participant(chat_id, current_user.id)

        chat = await self.repo.get_chat_and_att_and_messages(chat_id)

        if not chat:
            raise ChatNotFoundError()
        
        partner_id = chat.user1_id if chat.user2_id == current_user.id else chat.user2_id

        return await self.att.remove_att_from_chat(chat, current_user, partner_id)
