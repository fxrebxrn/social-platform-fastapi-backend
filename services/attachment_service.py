from sqlalchemy.ext.asyncio import AsyncSession
from services.attachment_repository import AttachmentRepository
from models import Post, PostAttachment, User
from fastapi import UploadFile, HTTPException
from utils.media import validate_attachment_type, save_upload_file, get_attachment_type, delete_media_file
from utils.redis_cache import redis_delete
from utils.permissions import ensure_can_modify_post
from core.exceptions import AttachmentNotFoundError
from services.base_repository import BaseRepository
import os
import uuid
from PIL import Image, UnidentifiedImageError
from io import BytesIO

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
