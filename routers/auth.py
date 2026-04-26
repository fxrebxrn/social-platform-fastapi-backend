from fastapi import HTTPException, APIRouter, Depends
from schemas.user_schemas import UserRegister, RefreshTokenRequest
from models import User
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from utils.query_helpers import get_user_by_email
from core.security import hash_password, verify_password, create_access_token, decode_token, create_refresh_token
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Request
from utils.rate_limit import check_failed_login_limit, add_failed_login_attempt, reset_failed_login_attempts
from typing import Annotated
from schemas.user_schemas import MessageWithUser
from schemas.util_schemas import TokenOutResponse, RefreshTokenOutResponse
from core.exceptions import InvalidTokenError

router = APIRouter(prefix="/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

@router.post("/register", response_model=MessageWithUser)
async def register_user(user: UserRegister, db: Annotated[AsyncSession, Depends(get_db)]):
    existing_user = await get_user_by_email(db, user.email)

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    hashed_password = hash_password(user.password)

    new_user = User(
        name=user.name,
        age=user.age,
        email=user.email,
        hashed_password=hashed_password
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {
        "message": "User registered successfully",
        "user": new_user
    }

@router.post("/login", response_model=TokenOutResponse)
async def login_user(request: Request, db: Annotated[AsyncSession, Depends(get_db)], form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    email = form_data.username
    password = form_data.password
    
    ip = request.client.host
    key = f"failed_login:{ip}:{email}"
    await check_failed_login_limit(key, limit=5)
    
    user_to_login = await get_user_by_email(db, email)

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

@router.post("/refresh", response_model=RefreshTokenOutResponse)
async def refresh_token(data: RefreshTokenRequest):
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
