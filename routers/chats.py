from fastapi import APIRouter, Depends, UploadFile, File, Query
from models import User
from schemas.chat_schemas import MessageCreate, ChatListResponse, WithMessageResponse, ChatResponse, AllMessagesReponse
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from schemas.util_schemas import MessageResponse
from typing import Annotated
from schemas.util_schemas import AttachmentResponse
from services.chat_service import ChatService
from datetime import datetime

router = APIRouter(prefix="/chats", tags=["Chats"])

@router.post("/{chat_id}/messages", response_model=WithMessageResponse)
async def new_message(chat_id: int, message: MessageCreate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = ChatService(db)
    return await service.new_message(chat_id, message, current_user)

@router.post("/{message_id}/attachments", response_model=AttachmentResponse)
async def upload_attachments_for_message(message_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)], files: list[UploadFile] = File(...)):
    service = ChatService(db)
    return await service.upload_attachments_for_message(message_id, current_user, files)

@router.post("/{user_id}", response_model=ChatResponse)
async def new_chat(user_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = ChatService(db)
    return await service.new_chat(user_id, current_user)

@router.get("/{chat_id}/messages", response_model=AllMessagesReponse)
async def get_messages_from_chat(chat_id: int,
                                current_user: Annotated[User, Depends(get_current_user)],
                                db: Annotated[AsyncSession, Depends(get_db)], 
                                limit: int = Query(50, ge=1, le=50),
                                cursor_created_at: datetime | None = None, 
                                cursor_id: int | None = None):
    service = ChatService(db)
    return await service.get_chat_messages(chat_id, current_user, limit, cursor_created_at, cursor_id)

@router.get("/{chat_id}/unread-count", response_model=MessageResponse)
async def get_count_of_unread_messages(chat_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = ChatService(db)
    return await service.get_count_of_unread_messages(chat_id, current_user)

@router.get("/", response_model=ChatListResponse)
async def get_all_user_chats(current_user: Annotated[User, Depends(get_current_user)], 
                            db: Annotated[AsyncSession, Depends(get_db)], 
                            limit: int = Query(50, ge=1, le=50),
                            cursor_updated_at: datetime | None = None, 
                            cursor_id: int | None = None):
    service = ChatService(db)
    return await service.get_all_user_chats(current_user, limit, cursor_updated_at, cursor_id)

@router.patch("/{chat_id}/read", response_model=MessageResponse)
async def read_all_messages_in_chat(chat_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = ChatService(db)
    return await service.read_all_messages_in_chat(chat_id, current_user)

@router.delete("/attachments/{attachment_id}", response_model=MessageResponse)
async def remove_att_from_message(attachment_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = ChatService(db)
    return await service.remove_att_from_message(attachment_id, current_user)

@router.delete("/messages/{message_id}", response_model=MessageResponse)
async def remove_message(message_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = ChatService(db)
    return await service.remove_message(message_id, current_user)

@router.delete("/{chat_id}", response_model=MessageResponse)
async def delete_chat(chat_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = ChatService(db)
    return await service.delete_chat(chat_id, current_user)
