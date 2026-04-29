import os
import uuid
from fastapi import HTTPException, UploadFile

ALLOWED_ATTACHMENT_TYPES = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "video/mp4",
        "audio/mpeg",
        "application/pdf",
        "text/plain"
    ]

def delete_media_file(relative_path: str | None):
    if not relative_path:
        return

    file_path = os.path.join("media", relative_path)

    if os.path.exists(file_path):
        os.remove(file_path)

def generate_filename(original_filename: str) -> str:
    extension = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "bin"
    return f"{uuid.uuid4()}.{extension}"

def get_attachment_type(content_type: str) -> str:
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("video/"):
        return "video"
    if content_type.startswith("audio/"):
        return "audio"
    return "document"

async def save_upload_file(file: UploadFile, folder: str, max_size_mb: int) -> dict:
    content = await file.read()
    original_name = file.filename or "unknown"

    if len(content) > max_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File size must be less than {max_size_mb} MB - {original_name}")
    
    os.makedirs(os.path.join(f"media", folder), exist_ok=True)
    
    filename = generate_filename(original_name)
    file_path = os.path.join("media", folder, filename)

    with open(file_path, "wb") as f:
        f.write(content)
    
    await file.close()
    
    return {
        "relative_path": f"{folder}/{filename}",
        "original_name": original_name
    }

def validate_attachment_type(content_type: str):
    if content_type not in ALLOWED_ATTACHMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid file type - {content_type}")
