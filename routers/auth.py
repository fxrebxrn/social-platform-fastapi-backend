from fastapi import APIRouter, Depends
from schemas.user_schemas import UserRegister, RefreshTokenRequest
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Request
from typing import Annotated
from schemas.user_schemas import MessageWithUser
from schemas.util_schemas import TokenOutResponse, RefreshTokenOutResponse
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

@router.post("/register", response_model=MessageWithUser)
async def register_user(user: UserRegister, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    return await service.register_user(user)

@router.post("/login", response_model=TokenOutResponse)
async def login_user(request: Request, db: Annotated[AsyncSession, Depends(get_db)], form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    service = AuthService(db)
    return await service.login_user(request, form_data)

@router.post("/refresh", response_model=RefreshTokenOutResponse)
async def refresh_token(data: RefreshTokenRequest):
    service = AuthService()
    return await service.refresh_token(data)
