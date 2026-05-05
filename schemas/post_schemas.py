from pydantic import BaseModel, Field, field_serializer, ConfigDict
from datetime import datetime
from schemas.user_schemas import UserShort
from typing import Optional, List
from schemas.util_schemas import AttachmentOut, CursorOut

class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=50)

class PostAttachmentOut(BaseModel):
    id: int
    file_url: str
    file_type: str
    original_name: str

    model_config = ConfigDict(from_attributes=True)

class PostWithUser(BaseModel):
    id: int
    title: str
    created_at: datetime
    user: UserShort
    attachments: list[PostAttachmentOut]

    model_config = ConfigDict(from_attributes=True)

class PostUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=50)

class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    parent_id: int | None = None

class WithMessagePostOut(BaseModel):
    message: str
    post: PostWithUser

    model_config = ConfigDict(from_attributes=True)

class NewCommentResponse(BaseModel):
    id: int
    text: str
    created_at: datetime
    user: UserShort
    parent_id: Optional[int] = None
    post_id: int

    model_config = ConfigDict(from_attributes=True)

class WithMessageCommentOut(BaseModel):
    message: str
    comment: NewCommentResponse

    model_config = ConfigDict(from_attributes=True)

class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    text: str
    parent_id: Optional[int]
    created_at: datetime
    user: UserShort
    replies: List["CommentOut"] = []

class PostCommentsResponse(BaseModel):
    comments: List[CommentOut]

class PostData(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    attachments: List[AttachmentOut] = []

class FullPostResponse(BaseModel):
    post: PostData
    author: UserShort
    likes_count: int
    comments: List[CommentOut]
    is_liked: bool

    model_config = ConfigDict(from_attributes=True)

class FeedResponse(CursorOut):
    model_config = ConfigDict(from_attributes=True)

    items: list[PostWithUser]
