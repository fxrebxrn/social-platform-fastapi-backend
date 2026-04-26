from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class MessageResponse(BaseModel):
    message: str | int | bool

    model_config = ConfigDict(from_attributes=True)

class AttachmentOut(BaseModel):
    id: int
    file_url: str
    file_type: str
    original_name: str

    model_config = ConfigDict(from_attributes=True)

class AttachmentResponse(BaseModel):
    message: str
    items: list[AttachmentOut]

    model_config = ConfigDict(from_attributes=True)

class NotificationResponse(BaseModel):
    id: int
    sender_id: Optional[int] = None
    message: str
    notification_type: str
    post_id: Optional[int] = None
    comment_id: Optional[int] = None
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class RefreshTokenOutResponse(BaseModel):
    access_token: str
    token_type: str

    model_config = ConfigDict(from_attributes=True)

class TokenOutResponse(RefreshTokenOutResponse):
    pass
    refresh_token: str

    model_config = ConfigDict(from_attributes=True)
