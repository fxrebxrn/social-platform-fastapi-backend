from passlib.context import CryptContext
from jose import jwt, ExpiredSignatureError
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from models import User
from config.settings import settings
import logging
from core.exceptions import PermissionDeniedError, InvalidTokenError, ExpiredTokenError
from typing import Annotated
from services.repositories.user_repository import UserRepository

ALLOWED_ROLES = ["user", "admin", "moderator", "helper"]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

logger = logging.getLogger(__name__)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except ExpiredSignatureError:
        raise ExpiredTokenError()
    except Exception:
        raise InvalidTokenError()

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[AsyncSession, Depends(get_db)]):
    payload = decode_token(token)
    user_id = payload.get("user_id")

    if not user_id:
        logger.warning(f"Invalid token, user not found: {user_id}")
        raise InvalidTokenError()

    service = UserRepository(db)

    user = await service.get_by_id(user_id)

    if not user:
        logger.warning(f"Invalid token, user not found: {user_id}")
        raise InvalidTokenError()
    
    return user

async def get_current_admin(current_admin: Annotated[User, Depends(get_current_user)]):
    if current_admin.role != "admin":
        raise PermissionDeniedError()
    return current_admin

def require_roles(*roles):
    async def role_checker(current_user: Annotated[User, Depends(get_current_user)]):
        if current_user.role not in roles:
            raise PermissionDeniedError()
        return current_user
    return role_checker
