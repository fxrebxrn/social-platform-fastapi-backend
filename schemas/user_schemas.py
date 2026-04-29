from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from schemas.util_schemas import MessageResponse

decline_names = ["admin", "root", "test"]

class UserBase(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    age: int = Field(ge=0, le=120)
    email: str = Field(min_length=5)

    @field_validator("name")
    def name_validator(cls, v):
        if not v.strip():
            raise ValueError("Invalid name")
        if v.strip().lower() in decline_names:
            raise ValueError("Invalid name")
        return v.strip().title()
    @field_validator("email")
    def email_validator(cls, v):
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email")
        return v

class UserUpdate(UserBase):
    pass

class UserRegister(UserBase):
    password: str = Field(min_length=8)

class UserLogin(BaseModel):
    email: str
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class UserShort(BaseModel):
    id: int
    name: str
    avatar_url: Optional[str] = None
    role: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class UserMyProfileResponse(BaseModel):
    id: int
    name: str
    role: str
    avatar_url: Optional[str] = None
    followers_count: int 
    following_count: int 
    posts_count: int

    model_config = ConfigDict(from_attributes=True)

class UserProfileResponse(UserMyProfileResponse):
    pass
    is_following: bool

class AvatarResponse(MessageResponse):
    pass
    avatar_url: str

class MessageWithUser(BaseModel):
    message: str
    user: UserShort
