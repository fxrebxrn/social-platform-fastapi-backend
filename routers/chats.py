from fastapi import HTTPException, APIRouter, Depends, UploadFile, File
from models import User, Message, Chat, MessageAttachment
from schemas.chat_schemas import MessageCreate, ChatListResponse, WithMessageResponse, ChatResponse, MessageItem, ChatListItem
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, update
from core.database import get_db
from sqlalchemy import func
from sqlalchemy.orm import selectinload, aliased
from utils.query_helpers import get_user_by_id_or_404, get_chat_if_participant
from core.security import get_current_user
import os
import uuid
from core.exceptions import MessageNotFoundError, ChatNotFoundError, PermissionDeniedError
from schemas.util_schemas import MessageResponse
from typing import Annotated
from schemas.util_schemas import AttachmentResponse
import aiofiles
from utils.redis_cache import redis_set, redis_get, redis_delete_by_prefix, redis_delete
from utils.media import delete_media_file, generate_filename

router = APIRouter(prefix="/chats", tags=["Chats"])

@router.post("/{chat_id}/messages", response_model=WithMessageResponse)
async def new_message(chat_id: int, message: MessageCreate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    chat = await get_chat_if_participant(db, chat_id, current_user.id)
    partner_id = chat.user1_id if chat.user2_id == current_user.id else chat.user2_id

    new_message = Message(
        sender_id=current_user.id,
        chat_id=chat.id,
        text=message.text
    )

    db.add(new_message)
    chat.updated_at = func.now()
    await db.commit()
    await redis_delete_by_prefix(f"chat:{chat_id}")
    await redis_delete_by_prefix(f"user:{current_user.id}:all-chats")
    await redis_delete_by_prefix(f"user:{partner_id}:all-chats")
    
    stmt = (
        select(Message)
        .options(selectinload(Message.attachments), selectinload(Message.sender), selectinload(Message.chat))
        .where(Message.id == new_message.id)
    )
    result = await db.execute(stmt)
    full_message = result.scalars().first()

    return {
        "message": "Message sent successfully",
        "data": full_message
    }

@router.post("/{message_id}/attachments", response_model=AttachmentResponse)
async def upload_attachments_for_message(message_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)], files: list[UploadFile] = File(...)):
    stmt = select(Message).where(Message.id == message_id)
    result = await db.execute(stmt)
    message = result.scalars().first()

    if not message:
        raise MessageNotFoundError()
    
    chat = await get_chat_if_participant(db, message.chat_id, current_user.id)
    partner_id = chat.user1_id if chat.user2_id == current_user.id else chat.user2_id

    if message.sender_id != current_user.id:
        raise PermissionDeniedError() 

    stmt_limit = select(func.count()).select_from(MessageAttachment).where(MessageAttachment.message_id == message_id)
    result_limit = await db.execute(stmt_limit)
    limit_count = result_limit.scalar() or 0

    if limit_count + len(files) > 5:
        raise HTTPException(status_code=400, detail=f"Maximum 5 attachments per message. Already uploaded: {limit_count}")

    allowed_types = ["image/jpeg", "image/png", "image/webp", "video/mp4", "audio/mpeg", "application/pdf", "text/plain"]
    for file in files:
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Invalid file type: {file.filename}")

    os.makedirs("media/message_attachments", exist_ok=True)
    created_attachments = []
    saved_file_paths = []

    try:
        for file in files:
            content = await file.read()
            if len(content) > 10 * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"File too large: {file.filename}")

            filename = generate_filename(file.filename)
            relative_path = f"message_attachments/{filename}"
            full_path = os.path.join("media", relative_path)

            async with aiofiles.open(full_path, "wb") as buffer:
                await buffer.write(content)
            
            saved_file_paths.append(full_path) 

            attachment = MessageAttachment(
                message_id=message.id,
                file_url=relative_path,
                file_type=file.content_type, 
                original_name=file.filename
            )
            db.add(attachment)
            created_attachments.append(attachment)

        await db.commit()
        await redis_delete_by_prefix(f"chat:{message.chat_id}")
        await redis_delete_by_prefix(f"user:{current_user.id}:all-chats")
        await redis_delete_by_prefix(f"user:{partner_id}:all-chats")
        
        for att in created_attachments:
            await db.refresh(att)

    except Exception as e:
        await db.rollback()
        for path in saved_file_paths:
            if os.path.exists(path):
                os.remove(path)
        raise e

    return {
        "message": "Attachments uploaded successfully",
        "items": created_attachments
    }

@router.post("/{user_id}", response_model=ChatResponse)
async def new_chat(user_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot start a chat with yourself")
    
    await get_user_by_id_or_404(db, user_id)

    user1 = min(current_user.id, user_id)
    user2 = max(current_user.id, user_id)

    stmt = select(Chat).where(Chat.user1_id == user1, Chat.user2_id == user2)
    result = await db.execute(stmt)
    existing_chat = result.scalars().first()

    if existing_chat:
        return {
            "message": "Chat already exists",
            "chat_id": existing_chat.id
        }
    
    new_chat = Chat(
        user1_id=user1,
        user2_id=user2
    )

    db.add(new_chat)
    await db.commit()
    await db.refresh(new_chat)
    await redis_delete_by_prefix(f"user:{current_user.id}:all-chats")
    await redis_delete_by_prefix(f"user:{user_id}:all-chats")

    return {
        "message": "Chat created successfully",
        "chat_id": new_chat.id
    }

@router.get("/{chat_id}/messages", response_model=list[MessageItem])
async def get_messages_from_chat(chat_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)], limit: int = 50, offset: int = 0):
    cache_key = f"chat:{chat_id}:messages:{limit}:{offset}"
    cached = await redis_get(cache_key)
    
    if cached:
        return cached
    
    if limit > 50:
        limit = 50

    await get_chat_if_participant(db, chat_id, current_user.id)

    stmt = select(Message).options(selectinload(Message.sender), selectinload(Message.attachments)).where(Message.chat_id == chat_id).order_by(Message.created_at.asc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    messages = result.scalars().all()

    messages_data = [
        MessageItem.model_validate(m).model_dump(mode="json") for m in messages
    ]

    await redis_set(cache_key, messages_data, 60)
    
    return messages_data

@router.get("/{chat_id}/unread-count", response_model=MessageResponse)
async def get_count_of_unread_messages(chat_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    cache_key = f"chat:{chat_id}:user:{current_user.id}:unread-count"
    cached = await redis_get(cache_key)
    
    if cached:
        return cached
    
    await get_chat_if_participant(db, chat_id, current_user.id)

    stmt = select(func.count()).select_from(Message).where(Message.chat_id == chat_id, Message.sender_id != current_user.id, Message.is_read == False)
    result = await db.execute(stmt)
    count = result.scalar()

    count_data = {
        "message": count
    }

    await redis_set(cache_key, count_data, 60)

    return count_data

@router.get("/", response_model=ChatListResponse)
async def get_all_user_chats(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)], limit: int = 50, offset: int = 0):
    if limit > 50:
        limit = 50
    
    cache_key = f"user:{current_user.id}:all-chats:{limit}:{offset}"
    cached = await redis_get(cache_key)
    
    if cached:
        return cached
    
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

    result = await db.execute(stmt)
    
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

    validated_items = []
    for item in result_data:
        validated_item = ChatListItem.model_validate(item).model_dump(mode="json")
        validated_items.append(validated_item)

    final_response = {"items": validated_items}

    await redis_set(cache_key, final_response, 60)

    return final_response

@router.patch("/{chat_id}/read", response_model=MessageResponse)
async def read_all_messages_in_chat(chat_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    chat = await get_chat_if_participant(db, chat_id, current_user.id)
    partner_id = chat.user1_id if chat.user2_id == current_user.id else chat.user2_id

    stmt = update(Message).where(Message.chat_id == chat_id, Message.sender_id != current_user.id, Message.is_read == False).values(is_read=True)

    await db.execute(stmt)
    await db.commit()
    await redis_delete_by_prefix(f"chat:{chat_id}")
    await redis_delete_by_prefix(f"user:{current_user.id}:all-chats")
    await redis_delete_by_prefix(f"user:{partner_id}:all-chats")


    return {
        "message": "All messages marked as read"
    }

@router.delete("/attachments/{attachment_id}", response_model=MessageResponse)
async def remove_att_from_message(attachment_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    stmt_att = select(MessageAttachment).options(selectinload(MessageAttachment.message)).where(MessageAttachment.id == attachment_id)
    result_att = await db.execute(stmt_att)
    att = result_att.scalars().first()

    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    chat = await get_chat_if_participant(db, att.message.chat_id, current_user.id)
    partner_id = chat.user1_id if chat.user2_id == current_user.id else chat.user2_id

    if att.message.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the sender of this message")

    delete_media_file(att.file_url)

    message_id = att.message_id

    await db.delete(att)
    await db.commit()
    await redis_delete_by_prefix(f"chat:{att.message.chat_id}")
    await redis_delete_by_prefix(f"user:{current_user.id}:all-chats")
    await redis_delete_by_prefix(f"user:{partner_id}:all-chats")

    return {
        "message": f"Attachment from message {message_id} deleted successfully"
    }

@router.delete("/messages/{message_id}", response_model=MessageResponse)
async def remove_message(message_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    stmt = select(Message).options(selectinload(Message.attachments)).where(Message.id == message_id)
    result = await db.execute(stmt)
    message = result.scalars().first()

    if not message:
        raise MessageNotFoundError()

    chat = await get_chat_if_participant(db, message.chat_id, current_user.id)
    partner_id = chat.user1_id if chat.user2_id == current_user.id else chat.user2_id

    if message.sender_id != current_user.id:
        raise PermissionDeniedError()

    try:
        for attachment in message.attachments:
            if attachment.file_url:
                full_path = os.path.join("media", attachment.file_url)
                if os.path.exists(full_path):
                    os.remove(full_path)

        await db.delete(message)
        await db.commit()
        await redis_delete_by_prefix(f"chat:{message.chat_id}")
        await redis_delete_by_prefix(f"user:{current_user.id}:all-chats")
        await redis_delete_by_prefix(f"user:{partner_id}:all-chats")

    except Exception as e:
        await db.rollback()
        raise e 

    return {"message": f"Message {message_id} deleted successfully"}

@router.delete("/{chat_id}", response_model=MessageResponse)
async def delete_chat(chat_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await get_chat_if_participant(db, chat_id, current_user.id)

    stmt = (select(Chat).options(selectinload(Chat.messages).selectinload(Message.attachments)).where(Chat.id == chat_id))
    result = await db.execute(stmt)
    chat = result.scalars().first()

    if not chat:
        raise ChatNotFoundError()
    
    partner_id = chat.user1_id if chat.user2_id == current_user.id else chat.user2_id

    files_to_delete = []
    for msg in chat.messages:
        for attach in msg.attachments:
            if attach.file_url:
                files_to_delete.append(os.path.join("media", attach.file_url))

    try:
        await db.delete(chat)
        await db.commit()
        await redis_delete_by_prefix(f"chat:{chat_id}")
        await redis_delete_by_prefix(f"user:{current_user.id}:all-chats")
        await redis_delete_by_prefix(f"user:{partner_id}:all-chats")

        for path in files_to_delete:
            if os.path.exists(path):
                os.remove(path)
                
    except Exception as e:
        await db.rollback()
        raise e

    return {"message": f"Chat {chat_id} and all related files deleted successfully"}
