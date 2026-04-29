from core.redis_client import redis_client
import json

async def redis_set(key: str, value: dict, ttl: int = 60):
    await redis_client.set(key, json.dumps(value), ex=ttl)

async def redis_get(key: str):
    data = await redis_client.get(key)

    if not data:
        return None
    
    return json.loads(data)

async def redis_delete(key: str):
    await redis_client.delete(key)

async def redis_sadd(key: str, value: str):
    await redis_client.sadd(key, value)

async def redis_delete_by_prefix(prefix: str):
    cursor = 0
    while True:
        cursor, keys = await redis_client.scan(cursor=cursor, match=f"{prefix}*")
        if keys:
            await redis_client.delete(*keys)
        if cursor == 0:
            break

async def invalidate_user_cache(user_id: int):
    await redis_delete(f"user:{user_id}:followers")
    await redis_delete(f"user:{user_id}:following")
    await redis_delete(f"user:{user_id}:profile")
    await redis_delete(f"user:{user_id}:posts")
    await redis_delete_by_prefix(f"user:{user_id}:feed")

async def invalidate_post_cache(post_id: int):
    await redis_delete(f"post:{post_id}:full")
    await redis_delete(f"post:{post_id}:likes")

async def redis_delete_many(keys: list[str]):
    await redis_client.delete(*keys)

async def invalidate_notify_cache(user_id: int):
    await redis_delete(f"user:{user_id}:notifications:all")
    await redis_delete(f"user:{user_id}:notifications:unread-count")

async def invalidate_follow_cache(user_id: int, current_user):
    await redis_delete(f"user:{user_id}:followers")
    await redis_delete(f"user:{current_user.id}:following")
    await redis_delete(f"user:{user_id}:profile")
    await redis_delete(f"user:{current_user.id}:profile")
