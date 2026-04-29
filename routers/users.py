from fastapi import APIRouter, Depends, UploadFile, File
from typing import Annotated
from schemas.user_schemas import UserUpdate, UserMyProfileResponse, UserProfileResponse, UserShort, UserProfileResponse, AvatarResponse, MessageWithUser
from models import User
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user, get_current_admin
from schemas.util_schemas import MessageResponse
from services.user_service import UserService
from services.attachment_service import AttachmentService

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/{user_id}/follow", response_model=MessageResponse)
async def follow_user(user_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = UserService(db)
    return await service.follow_user(user_id, current_user)

@router.get("/search/{name}", response_model=list[UserShort])
async def search_users(name: str, db: Annotated[AsyncSession, Depends(get_db)], limit: int = 10, offset: int = 0):
    service = UserService(db)
    return await service.search_users(name, limit, offset)

@router.get("/{user_id}/followers", response_model=list[UserShort])
async def user_followers(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    service = UserService(db)
    return await service.user_followers(user_id)

@router.get("/{user_id}/following", response_model=list[UserShort])
async def user_following(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    service = UserService(db)
    return await service.user_followings(user_id)

@router.get("/me/profile", response_model=UserMyProfileResponse)
async def get_my_profile(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = UserService(db)
    return await service.get_user_profile_data(current_user.id)

@router.get("/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(user_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = UserService(db)
    return await service.get_user_profile(user_id, current_user)

@router.patch("/me/avatar", response_model=AvatarResponse)
async def change_avatar(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)], avatar: UploadFile = File(...)):
    service = AttachmentService(db)
    return await service.change_avatar(current_user, avatar)

@router.patch("/{user_id}/role", response_model=MessageWithUser)
async def update_user_role(user_id: int, new_role: str, current_user: Annotated[User, Depends(get_current_admin)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = UserService(db)
    return await service.update_user_role(user_id, new_role, current_user)

@router.put("/{user_id}", response_model=MessageWithUser)
async def update_user(user_id: int, user: UserUpdate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = UserService(db)
    return await service.update_user(user_id, user, current_user)

@router.delete("/me/avatar", response_model=MessageResponse)
async def remove_avatar(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = AttachmentService(db)
    return await service.remove_avatar(current_user)

@router.delete("/{user_id}/follow", response_model=MessageResponse)
async def unfollow_user(user_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = UserService(db)
    return await service.unfollow_user(user_id, current_user)
