from pydantic import BaseModel, Field, field_serializer, field_validator, ConfigDict
from datetime import datetime
from schemas.util_schemas import AttachmentOut

class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)

class ChatPartner(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)

class MessageItem(BaseModel):
    id: int
    chat_id: int
    sender: ChatPartner
    text: str
    attachments: list[AttachmentOut] | None
    is_read: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ChatListItem(BaseModel):
    chat_id: int
    partner: ChatPartner
    last_message: MessageItem | None
    unread_count: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ChatListResponse(BaseModel):
    items: list[ChatListItem]

    model_config = ConfigDict(from_attributes=True)

class ChatResponse(BaseModel):
    message: str
    chat_id: int

    model_config = ConfigDict(from_attributes=True)

class WithMessageResponse(BaseModel):
    message: str
    data: MessageItem

    model_config = ConfigDict(from_attributes=True)
