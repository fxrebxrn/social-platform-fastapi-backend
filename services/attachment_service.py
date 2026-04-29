from sqlalchemy.ext.asyncio import AsyncSession
from services.repositories.attachment_repository import AttachmentRepository
from models import Post, PostAttachment, User, MessageAttachment
from fastapi import UploadFile, HTTPException
from utils.media import validate_attachment_type, save_upload_file, get_attachment_type, delete_media_file, generate_filename
from utils.redis_cache import redis_delete
from utils.permissions import ensure_can_modify_post
from core.exceptions import AttachmentNotFoundError
from services.repositories.base_repository import BaseRepository
import os
import uuid
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import aiofiles
from utils.redis_cache import invalidate_chat_cache

class AttachmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AttachmentRepository(db)
        self.base_repo = BaseRepository(db)

    async def get_post_attachment_or_raise(self, attachment_id: int):
        attachment = await self.repo.get_post_attachment_with_post(attachment_id)
        if not attachment:
            raise AttachmentNotFoundError()
        
        return attachment

    async def add_post_attachments(self, post: Post, files: list[UploadFile]):
        if len(files) > 5:
            raise HTTPException(status_code=400, detail="Maximum of 5 attachments allowed")

        limit_count = await self.repo.get_post_attachment_count(post.id)

        if limit_count + len(files) > 5:
            raise HTTPException(status_code=400, detail=f"Maximum 5 attachments per post. Already uploaded: {limit_count}")

        created_attachments = []
        saved_paths = []
        try:
            for file in files:
                validate_attachment_type(file.content_type or "")
                
                saved = await save_upload_file(file, "post_attachments", 10)

                attachment = PostAttachment(
                    post_id=post.id,
                    file_url=saved["relative_path"],
                    file_type=get_attachment_type(file.content_type or ""),
                    original_name=saved["original_name"]
                )

                self.db.add(attachment)
                created_attachments.append(attachment)
                saved_paths.append(saved["relative_path"])

            await self.db.commit()
            for att in created_attachments:
                await self.db.refresh(att)

            await redis_delete(f"post:{post.id}:full")

        except Exception:
            await self.db.rollback()
            for path in saved_paths:
                delete_media_file(path)
            raise

        return {
            "message": "Attachments upload successfully",
            "items": created_attachments
        }
    
    async def delete_post_attachment(self, attachment_id: int, current_user: User):
        att = await self.get_post_attachment_or_raise(attachment_id)

        ensure_can_modify_post(att.post, current_user)

        post_id = att.post_id

        delete_media_file(att.file_url)

        await self.base_repo.delete(att)
        await redis_delete(f"post:{post_id}:full")

        return {
            "message": f"Attachment from post {post_id} deleted successfully"
        }

    async def change_avatar(self, current_user: User, avatar: UploadFile):
        allowed_types = ["image/jpeg", "image/png", "image/webp"]

        if avatar.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Invalid avatar type")

        content = await avatar.read()
        if len(content) > 2 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Avatar size must be less than 2 MB")
        
        try:
            image = Image.open(BytesIO(content))
            image.load()
        except UnidentifiedImageError:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        image.thumbnail((512, 512))

        if image.mode != "RGB":
            image = image.convert("RGB")

        os.makedirs("media/avatars", exist_ok=True)
        
        filename = f"{uuid.uuid4()}.webp"
        file_path = os.path.join("media", "avatars", filename)

        if current_user.avatar_url:
            old_path_avatar = os.path.join("media", current_user.avatar_url)
            if os.path.exists(old_path_avatar):
                os.remove(old_path_avatar)

        image.save(file_path, format="WEBP", quality=85)

        current_user.avatar_url = f"avatars/{filename}"

        await self.base_repo.commit_refresh(current_user)
        await avatar.close()

        await redis_delete(f"user:{current_user.id}:profile")

        return {
            "message": "Avatar uploaded successfully",
            "avatar_url": current_user.avatar_url
        }

    async def remove_avatar(self, current_user: User):
        if not current_user.avatar_url:
            raise HTTPException(status_code=404, detail="Avatar not found")
        
        delete_media_file(current_user.avatar_url)

        current_user.avatar_url = None

        await self.base_repo.commit_refresh(current_user)

        await redis_delete(f"user:{current_user.id}:profile")
        await redis_delete(f"user:{current_user.id}:posts")

        return {
            "message": "Avatar deleted successfully"
        }

    async def upload_att_chat(self, partner_id: int, message, current_user: User, files: list[UploadFile]):
        limit_count = await self.repo.get_count_message_att_by_id(message.id) or 0

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
                self.db.add(attachment)
                created_attachments.append(attachment)

            await self.db.commit()
            await invalidate_chat_cache(message.chat_id, current_user.id, partner_id)
            
            for att in created_attachments:
                await self.db.refresh(att)

        except Exception as e:
            await self.db.rollback()
            for path in saved_file_paths:
                if os.path.exists(path):
                    os.remove(path)
            raise e

        return {
            "message": "Attachments uploaded successfully",
            "items": created_attachments
        }

    async def remove_att_message(self, att, partner_id, current_user: User):

        delete_media_file(att.file_url)

        message_id = att.message_id

        await self.base_repo.delete(att)
        await invalidate_chat_cache(att.message.chat_id, current_user.id, partner_id)

        return {
            "message": f"Attachment from message {message_id} deleted successfully"
        }
    
    async def remove_att_from_deleted_message(self, message_id, message, current_user: User, partner_id: int):
        try:
            for attachment in message.attachments:
                if attachment.file_url:
                    full_path = os.path.join("media", attachment.file_url)
                    if os.path.exists(full_path):
                        os.remove(full_path)

            await self.base_repo.delete(message)
            await invalidate_chat_cache(message.chat_id, current_user.id, partner_id)

        except Exception as e:
            await self.db.rollback()
            raise e 
        
        return {"message": f"Message {message_id} deleted successfully"}
    
    async def remove_att_from_chat(self, chat, current_user, partner_id):
        files_to_delete = []
        for msg in chat.messages:
            for attach in msg.attachments:
                if attach.file_url:
                    files_to_delete.append(os.path.join("media", attach.file_url))

        try:
            await self.base_repo.delete(chat)
            await invalidate_chat_cache(chat.id, current_user.id, partner_id)

            for path in files_to_delete:
                if os.path.exists(path):
                    os.remove(path)
                    
        except Exception as e:
            await self.db.rollback()
            raise e

        return {"message": f"Chat {chat.id} and all related files deleted successfully"}
