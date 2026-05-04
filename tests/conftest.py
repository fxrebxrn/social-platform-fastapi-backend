import pytest
import pytest_asyncio
import os
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from httpx import AsyncClient, ASGITransport
from main import app
from core.database import Base, get_db
from core.security import get_current_user, get_current_admin
from models import User, Chat, Message, MessageAttachment, Follow, Notification, Post, Comment, Like, PostAttachment
from routers import chats, users, posts
from utils import redis_cache
from services import post_service
import asyncio
from core.redis_client import redis_client

# Mock redis
patch.object(redis_client, "get", new_callable=AsyncMock, return_value=None).start()
patch.object(redis_client, "set", new_callable=AsyncMock).start()
patch.object(redis_client, "delete", new_callable=AsyncMock).start()
patch.object(redis_client, "scan", new_callable=AsyncMock, return_value=(0, [])).start()
patch.object(redis_client, "sadd", new_callable=AsyncMock).start()
patch.object(redis_client, "incr", new_callable=AsyncMock, return_value=1).start()
patch.object(redis_client, "expire", new_callable=AsyncMock).start()

pytest_plugins = ("pytest_asyncio",)

@pytest.fixture(autouse=True)
async def cleanup_redis():
    yield
    try:
        if redis_client:
            # Пытаемся закрыть соединения
            await redis_client.connection_pool.disconnect()
    except RuntimeError as e:
        # Если цикл закрыт, Redis не сможет вежливо закрыть сокет, 
        # и это нормально для стадии завершения тестов.
        if "Event loop is closed" not in str(e):
            raise
    except Exception:
        pass

@pytest_asyncio.fixture(autouse=True)
async def mock_settings():
    """Mock settings for tests"""
    with patch('config.settings.settings') as mock_settings:
        mock_settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
        mock_settings.DEBUG = False
        yield

@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Создает таблицы и чистую сессию для каждого теста"""
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)
    TestingSessionLocal = async_sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=engine,
        expire_on_commit=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()
    
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession, user1: User):
    """Настроенный клиент с подменой зависимостей"""
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return user1

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def user1(db_session: AsyncSession) -> User:
    user = User(name="vasya_test", email="vasya@test.com", hashed_password="123")
    db_session.add(user)
    await db_session.flush()
    return user

@pytest_asyncio.fixture
async def user2(db_session: AsyncSession) -> User:
    user = User(name="petya_test", email="petya@test.com", hashed_password="123")
    db_session.add(user)
    await db_session.flush()
    return user

@pytest_asyncio.fixture
async def user3(db_session: AsyncSession) -> User:
    user = User(name="masha_test", email="masha@test.com", hashed_password="123")
    db_session.add(user)
    await db_session.flush()
    return user

@pytest_asyncio.fixture
async def chat_1_2(db_session: AsyncSession, user1: User, user2: User) -> Chat:
    chat = Chat(user1_id=user1.id, user2_id=user2.id)
    db_session.add(chat)
    await db_session.flush()
    return chat

@pytest_asyncio.fixture
async def chat_2_3(db_session: AsyncSession, user2: User, user3: User) -> Chat:
    chat = Chat(user1_id=user2.id, user2_id=user3.id)
    db_session.add(chat)
    await db_session.flush()
    return chat

@pytest_asyncio.fixture
async def message_from_user1(db_session: AsyncSession, user1: User, chat_1_2: Chat) -> Message:
    msg = Message(sender_id=user1.id, chat_id=chat_1_2.id, text="Hello from user1")
    db_session.add(msg)
    await db_session.flush()
    return msg

@pytest_asyncio.fixture
async def message_from_user2(db_session: AsyncSession, user2: User, chat_1_2: Chat) -> Message:
    msg = Message(sender_id=user2.id, chat_id=chat_1_2.id, text="Hello from user2")
    db_session.add(msg)
    await db_session.flush()
    return msg

@pytest_asyncio.fixture
async def attachment_on_message(db_session: AsyncSession, message_from_user1: Message) -> MessageAttachment:
    os.makedirs("media/message_attachments", exist_ok=True)
    fname = f"{uuid.uuid4()}.txt"
    fpath = os.path.join("media/message_attachments", fname)
    with open(fpath, "w") as f:
        f.write("content")
    att = MessageAttachment(
        message_id=message_from_user1.id,
        file_url=f"message_attachments/{fname}",
        file_type="text/plain",
        original_name="file.txt",
    )
    db_session.add(att)
    await db_session.flush()
    return att

@pytest_asyncio.fixture
async def empty_chat(db_session: AsyncSession, user1: User, user3: User) -> Chat:
    chat = Chat(user1_id=user1.id, user2_id=user3.id)
    db_session.add(chat)
    await db_session.flush()
    return chat

@pytest_asyncio.fixture(scope="function")
async def client_user3(db_session: AsyncSession, user3: User):
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return user3

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest_asyncio.fixture(scope="function")
async def admin_user(db_session: AsyncSession) -> User:
    user = User(name="admin_test", email="admin@test.com", hashed_password="123", role="admin")
    db_session.add(user)
    await db_session.flush()
    return user

@pytest_asyncio.fixture(scope="function")
async def client_admin(db_session: AsyncSession, admin_user: User):
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return admin_user

    async def override_get_current_admin():
        return admin_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_admin] = override_get_current_admin
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def follow_1_2(db_session: AsyncSession, user1: User, user2: User) -> Follow:
    follow = Follow(follower_id=user1.id, following_id=user2.id)
    db_session.add(follow)
    await db_session.flush()
    return follow

@pytest_asyncio.fixture
async def notification_follow(db_session: AsyncSession, user1: User, user2: User) -> Notification:
    notif = Notification(
        user_id=user2.id,
        sender_id=user1.id,
        message=f"{user1.name} followed you",
        notification_type="follow"
    )
    db_session.add(notif)
    await db_session.flush()
    return notif

@pytest_asyncio.fixture
async def notification1(db_session: AsyncSession, user1: User, user2: User) -> Notification:
    notif = Notification(
        user_id=user1.id,
        sender_id=user2.id,
        message="You have a new message",
        notification_type="message"
    )
    db_session.add(notif)
    await db_session.flush()
    return notif

@pytest_asyncio.fixture
async def notification_read(db_session: AsyncSession, user1: User, user2: User) -> Notification:
    notif = Notification(
        user_id=user1.id,
        sender_id=user2.id,
        message="Read notification",
        notification_type="message",
        is_read=True
    )
    db_session.add(notif)
    await db_session.flush()
    return notif

@pytest_asyncio.fixture
async def post1(db_session: AsyncSession, user1: User) -> Post:
    post = Post(title="Test post 1", user_id=user1.id)
    db_session.add(post)
    await db_session.flush()
    return post

@pytest_asyncio.fixture
async def post2(db_session: AsyncSession, user2: User) -> Post:
    post = Post(title="Test post 2", user_id=user2.id)
    db_session.add(post)
    await db_session.flush()
    return post

@pytest_asyncio.fixture
async def comment1(db_session: AsyncSession, user1: User, post1: Post) -> Comment:
    comment = Comment(text="Test comment", user_id=user1.id, post_id=post1.id)
    db_session.add(comment)
    await db_session.flush()
    return comment

@pytest_asyncio.fixture
async def like1(db_session: AsyncSession, user1: User, post2: Post) -> Like:
    like = Like(user_id=user1.id, post_id=post2.id)
    db_session.add(like)
    await db_session.flush()
    return like

@pytest_asyncio.fixture
async def attachment1(db_session: AsyncSession, post1: Post) -> PostAttachment:
    os.makedirs("media/post_attachments", exist_ok=True)
    fname = f"{uuid.uuid4()}.txt"
    fpath = os.path.join("media/post_attachments", fname)
    with open(fpath, "w") as f:
        f.write("content")
    att = PostAttachment(
        post_id=post1.id,
        file_url=f"post_attachments/{fname}",
        file_type="text/plain",
        original_name="file.txt",
    )
    db_session.add(att)
    await db_session.flush()
    return att