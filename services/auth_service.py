from sqlalchemy.ext.asyncio import AsyncSession
from services.user_service import UserService
from services.repositories.base_repository import BaseRepository
from schemas.user_schemas import UserRegister
from core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from fastapi import HTTPException, Request
from models import User
from services.repositories.user_repository import UserRepository
from fastapi.security import OAuth2PasswordRequestForm
from utils.rate_limit import check_failed_login_limit, add_failed_login_attempt, reset_failed_login_attempts
from core.exceptions import InvalidTokenError
from schemas.user_schemas import RefreshTokenRequest

class AuthService:
    def __init__(self, db: AsyncSession = None):
        self.db = db
        self.user = UserService(db)
        self.base_repo = BaseRepository(db)
        self.user_repo = UserRepository(db)

    async def register_user(self, user: UserRegister):
        existing_user = await self.user_repo.get_user_by_email(user.email)

        if existing_user:
            raise HTTPException(status_code=400, detail="Email already exists")
        
        hashed_password = hash_password(user.password)

        new_user = User(
            name=user.name,
            age=user.age,
            email=user.email,
            hashed_password=hashed_password
        )

        objects = [new_user]

        await self.base_repo.add_unique_objects(
            objects=objects,
            detail="Email already exists",
            refresh_obj=new_user
        )

        return {
            "message": "User registered successfully",
            "user": new_user
        }

    async def login_user(self, request: Request, form_data: OAuth2PasswordRequestForm):
        email = form_data.username
        password = form_data.password
        
        ip = request.client.host
        key = f"failed_login:{ip}:{email}"
        await check_failed_login_limit(key, limit=5)

        user_to_login = await self.user_repo.get_user_by_email(email)

        if not user_to_login:
            await add_failed_login_attempt(key, window=60)
            raise HTTPException(status_code=401, detail="Incorrect credentials")

        if not verify_password(password, user_to_login.hashed_password):
            await add_failed_login_attempt(key, window=60)
            raise HTTPException(status_code=401, detail="Incorrect credentials")
        
        await reset_failed_login_attempts(key)

        access_token = create_access_token({"user_id": user_to_login.id})
        refresh_token = create_refresh_token({"user_id": user_to_login.id})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    async def refresh_token(self, data: RefreshTokenRequest):
        payload = decode_token(data.refresh_token)

        if payload.get("type") != "refresh":
            raise InvalidTokenError()
        
        user_id = payload.get("user_id")
        if not user_id:
            raise InvalidTokenError()
        
        new_access_token = create_access_token({"user_id": user_id})

        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    