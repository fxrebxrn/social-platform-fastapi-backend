from sqlalchemy.ext.asyncio import AsyncSession
from services.attachment_repository import AttachmentRepository
from models import Post, PostAttachment, User
from fastapi import UploadFile, HTTPException
from utils.media import validate_attachment_type, save_upload_file, get_attachment_type, delete_media_file
from utils.redis_cache import redis_delete
from utils.permissions import ensure_can_modify_post
from core.exceptions import AttachmentNotFoundError
from services.base_repository import BaseRepository

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
