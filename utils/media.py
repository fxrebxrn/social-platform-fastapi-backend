import os
import uuid

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
