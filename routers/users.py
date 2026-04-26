from fastapi import HTTPException, APIRouter, Depends, UploadFile, File
from typing import Annotated
from schemas.user_schemas import UserUpdate, UserMyProfileResponse, UserProfileResponse, UserShort, UserProfileResponse, AvatarResponse, MessageWithUser
from models import User, Follow, Notification, Post
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from core.database import get_db
from utils.serializers import users_to_dicts, user_to_dict
from utils.query_helpers import fetch_all_by_stmt, get_user_by_id, get_user_by_id_or_404, get_followers_count, get_following_count, get_scalar_result
from core.security import get_current_user, get_current_admin, ALLOWED_ROLES
from utils.redis_cache import redis_get, redis_set, invalidate_user_cache, redis_delete
from schemas.util_schemas import MessageResponse
import os
import uuid
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from core.exceptions import PermissionDeniedError, UserNotFoundError, SelfFollowError, AlreadyFollowingError, AlreadyUnfollowingError
from utils.media import delete_media_file

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/{user_id}/follow", response_model=MessageResponse)
async def follow_user(user_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    user_to_follow = await get_user_by_id_or_404(db, user_id)

    if current_user.id == user_id:
        raise SelfFollowError()

    stmt = select(Follow).where(Follow.follower_id == current_user.id, Follow.following_id == user_id)
    result = await db.execute(stmt)
    existing_follow = result.scalars().first()

    if existing_follow:
        raise AlreadyFollowingError()
    
    new_follow = Follow(
        follower_id=current_user.id,
        following_id=user_id
    )

    new_notify = Notification(
        user_id=user_id,
        sender_id=current_user.id,
        message=f"{current_user.name} followed you",
        notification_type="follow"
    )

    db.add(new_notify)
    db.add(new_follow)
    await db.commit()
    await db.refresh(new_follow)

    await redis_delete(f"user:{user_id}:followers")
    await redis_delete(f"user:{current_user.id}:following")
    await redis_delete(f"user:{user_id}:profile")
    await redis_delete(f"user:{current_user.id}:profile")
    await redis_delete(f"user:{user_id}:notifications:all")
    await redis_delete(f"user:{user_id}:notifications:unread-count")

    return {
        "message": f"You are now following user {user_to_follow.name}"
    }

@router.get("/search/{name}", response_model=list[UserShort])
async def search_users(name: str, db: Annotated[AsyncSession, Depends(get_db)], limit: int = 10, offset: int = 0):
    if len(name) < 3 or len(name) > 50:
        raise HTTPException(status_code=400, detail="Name must be between 3 and 50 characters")
    
    cache_key = f"user:{name}:search"
    cached = await redis_get(cache_key)
    
    if cached:
        return cached
    
    stmt = select(User).where(User.name.ilike(f"%{name}%")).limit(limit).offset(offset)
    users = await fetch_all_by_stmt(db, stmt)

    users_data = users_to_dicts(users)
    await redis_set(cache_key, users_data, ttl=300)

    return users_data

@router.get("/{user_id}/followers", response_model=list[UserShort])
async def user_followers(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    cache_key = f"user:{user_id}:followers"
    cached = await redis_get(cache_key)

    if cached:
        return cached
    
    await get_user_by_id_or_404(db, user_id)

    stmt = select(User).join(Follow, Follow.follower_id == User.id).where(Follow.following_id == user_id)
    result = await db.execute(stmt)
    users = result.scalars().all()

    users_data = users_to_dicts(users)
    await redis_set(cache_key, users_data, ttl=300)

    return users_data

@router.get("/{user_id}/following", response_model=list[UserShort])
async def user_following(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    cache_key = f"user:{user_id}:following"
    cached = await redis_get(cache_key)
    
    if cached is not None:
        return cached

    await get_user_by_id_or_404(db, user_id)

    stmt = select(User).join(Follow, Follow.following_id == User.id).where(Follow.follower_id == user_id)
    result = await db.execute(stmt)
    users = result.scalars().all()

    users_data = users_to_dicts(users)
    await redis_set(cache_key, users_data, ttl=300)

    return users_data

async def get_user_profile_data(user_id: int, db: AsyncSession) -> dict:
    cache_key = f"user:{user_id}:profile"
    cached = await redis_get(cache_key)
    
    if cached:
        return cached

    user = await get_user_by_id_or_404(db, user_id)
    
    stmt_posts = select(func.count()).select_from(Post).where(Post.user_id == user_id)
    count_posts = await get_scalar_result(db, stmt_posts)

    profile_data = {
        "id": user.id,
        "name": user.name,
        "role": user.role,
        "avatar_url": user.avatar_url,
        "followers_count": await get_followers_count(db, user_id),
        "following_count": await get_following_count(db, user_id),
        "posts_count": count_posts
    }
    
    await redis_set(cache_key, profile_data, ttl=300)
    return profile_data

@router.get("/me/profile", response_model=UserMyProfileResponse)
async def get_my_profile(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_user_profile_data(current_user.id, db)

@router.get("/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(user_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    profile_data = await get_user_profile_data(user_id, db)
    
    is_following = False
    if current_user.id != user_id:
        stmt_following = select(Follow).where(
            Follow.follower_id == current_user.id, 
            Follow.following_id == user_id
        )
        result = await db.execute(stmt_following)
        is_following = bool(result.scalars().first())

    return {**profile_data, "is_following": is_following}

@router.patch("/me/avatar", response_model=AvatarResponse)
async def change_avatar(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)], avatar: UploadFile = File(...)):
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

    await db.commit()
    await db.refresh(current_user)
    await avatar.close()

    await redis_delete(f"user:{current_user.id}:profile")

    return {
        "message": "Avatar uploaded successfully",
        "avatar_url": current_user.avatar_url
    }

@router.patch("/{user_id}/role", response_model=MessageWithUser)
async def update_user_role(user_id: int, new_role: str, current_user: Annotated[User, Depends(get_current_admin)], db: Annotated[AsyncSession, Depends(get_db)]):
    user_to_update = await get_user_by_id_or_404(db, user_id)

    if new_role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Role does not exist")

    if user_id == current_user.id and new_role != "admin":
        raise HTTPException(status_code=400, detail="You cannot remove your own admin role")

    user_to_update.role = new_role

    await db.commit()
    await db.refresh(user_to_update)

    await redis_delete(f"user:{user_to_update.id}:profile")

    return {
        "message": "User role updated successfully",
        "user": user_to_update
    }

@router.put("/{user_id}", response_model=MessageWithUser)
async def update_user(user_id: int, user: UserUpdate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    if current_user.role != "admin":
        raise PermissionDeniedError()
    
    user_to_update = await get_user_by_id(db, user_id)

    if not user_to_update:
        raise UserNotFoundError()

    duplicate_email = await db.execute(select(User).where(User.email == user.email))
    duplicate_email = duplicate_email.scalars().first()
    if duplicate_email and duplicate_email.id != user_to_update.id:
        raise HTTPException(status_code=400, detail="Email already exists")

    user_to_update.name = user.name
    user_to_update.age = user.age
    user_to_update.email = user.email

    await db.commit()
    await db.refresh(user_to_update)

    await redis_delete(f"user:{user_to_update.id}:profile")

    return {
        "message": "User updated successfully",
        "user": user_to_update
    }

@router.delete("/me/avatar", response_model=MessageResponse)
async def remove_avatar(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    if not current_user.avatar_url:
        raise HTTPException(status_code=404, detail="Avatar not found")
    
    delete_media_file(current_user.avatar_url)

    current_user.avatar_url = None

    await db.commit()
    await db.refresh(current_user)

    await redis_delete(f"user:{current_user.id}:profile")
    await redis_delete(f"user:{current_user.id}:posts")

    return {
        "message": "Avatar deleted successfully"
    }

@router.delete("/{user_id}/follow", response_model=MessageResponse)
async def unfollow_user(user_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    user_to_unfollow = await get_user_by_id_or_404(db, user_id)

    stmt = select(Follow).where(Follow.follower_id == current_user.id, Follow.following_id == user_id)
    result = await db.execute(stmt)
    follow = result.scalars().first()

    if not follow:
        raise AlreadyUnfollowingError()
    
    await db.delete(follow)
    await db.commit()

    await redis_delete(f"user:{user_id}:followers")
    await redis_delete(f"user:{current_user.id}:following")
    await redis_delete(f"user:{user_id}:profile")
    await redis_delete(f"user:{current_user.id}:profile")

    return {
        "message": f"You are no longer following user {user_to_unfollow.name}"
    }
