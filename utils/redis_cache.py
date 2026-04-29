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

async def redis_delete_many(keys: list[str]):
    await redis_client.delete(*keys)

async def invalidate_notify_cache(user_id: int):
    keys = [
        f"user:{user_id}:notifications:all",
        f"user:{user_id}:notifications:unread-count"
    ]
    await redis_delete_many(keys)

async def invalidate_follow_cache(user_id: int, current_user):
    keys = [
        f"user:{user_id}:followers",
        f"user:{current_user.id}:following",
        f"user:{user_id}:profile",
        f"user:{current_user.id}:profile"
    ]
    await redis_delete_many(keys)

async def invalidate_user_cache(user_id: int):
    keys = [
        f"user:{user_id}:followers",
        f"user:{user_id}:following",
        f"user:{user_id}:profile",
        f"user:{user_id}:posts"
    ]
    await redis_delete_many(keys)
    await redis_delete_by_prefix(f"user:{user_id}:feed")

async def invalidate_post_cache(post_id: int):
    keys = [
        f"post:{post_id}:full",
        f"post:{post_id}:likes"
    ]
    await redis_delete_many(keys)

async def invalidate_chat_cache(chat_id: int, current_user_id: int, partner_id: int):
    await redis_delete_by_prefix(f"chat:{chat_id}")
    await redis_delete_by_prefix(f"user:{current_user_id}:all-chats")
    await redis_delete_by_prefix(f"user:{partner_id}:all-chats")
