from fastapi import HTTPException, Request
from core.redis_client import redis_client

async def check_rate_limit(key: str, limit: int, window: int):
    current = await redis_client.incr(key)

    if current == 1:
        await redis_client.expire(key, window)

    if current > limit:
        raise HTTPException(
            status_code=429, 
            detail="Too many requests"
            )

def rate_limit_dependency(action: str, limit: int, window: int):
    async def dependency(request: Request):
        ip = request.client.host
        await check_rate_limit(
            key=f"rate_limit:{action}:{ip}",
            limit=limit,
            window=window
        )
    return dependency

async def check_failed_login_limit(key: str, limit: int):
    current = await redis_client.get(key)
    current = int(current) if current else 0

    if current >= limit:
        raise HTTPException(
            status_code=429, 
            detail="Too many failed login attempts. Try again later."
            )
    
async def add_failed_login_attempt(key: str, window: int):
    current = await redis_client.incr(key)

    if current == 1:
        await redis_client.expire(key, window)

async def reset_failed_login_attempts(key: str):
    await redis_client.delete(key)
