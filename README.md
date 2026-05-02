# Social Platform API (FastAPI)

A REST API for a social platform built with **FastAPI**.

It includes support for:

- registration and authentication (JWT access + refresh);
- user profiles, roles, and avatars;
- follow/unfollow relationships;
- posts, comments (including nested comments), likes, and media attachments;
- private chats, messages, and message attachments;
- notifications;
- Redis caching and login rate limiting.

---

## Tech Stack

- **Python / FastAPI**
- **SQLAlchemy (async)**
- **Alembic**
- **PostgreSQL** (via `DATABASE_URL`)
- **Redis**
- **JWT** (`python-jose`)
- **Pydantic Settings**

---

## Project Structure

- `main.py` — FastAPI app entry point, router registration, global exception handlers.
- `routers/` — API endpoints by domain:
  - `auth.py`
  - `users.py`
  - `posts.py`
  - `chats.py`
  - `notifications.py`
- `models.py` — SQLAlchemy models.
- `core/` — database, security, exceptions, Redis client.
- `schemas/` — Pydantic request/response schemas.
- `services/` — business logic layer (e.g., post-related logic).
- `utils/` — helper utilities.
- `alembic/` — migrations.
- `tests/` — API tests.

---

## Quick Start

### 1) Clone the repository

```bash
git clone <your-repo-url>
cd social-platform-fastapi-backend
```

### 2) Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3) Install dependencies

Use pinned dependencies from `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 4) Environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=change_me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/social_db

DEBUG=true
APP_ENV=dev

REDIS_HOST=localhost
REDIS_PORT=6379
```

### 5) Run migrations

```bash
alembic upgrade head
```

### 6) Start the API

```bash
uvicorn main:app --reload
```

After startup:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## Docker

Run the project with Docker Compose:

```bash
docker compose up --build
```

The app will automatically:
- start PostgreSQL
- start Redis
- run Alembic migrations
- start FastAPI

Sevices:
- FastAPI: http://localhost:8000
- Open API docs: http://localhost:8000/docs
- PostgreSQL: localhost:5434
- Redis: localhost:6379

## Authentication

JWT is used for auth:

- `POST /auth/login` returns:
  - `access_token`
  - `refresh_token`
- `POST /auth/refresh` issues a new `access_token` from a `refresh_token`.

For protected endpoints, pass the header:

```http
Authorization: Bearer <access_token>
```

---

## Main Endpoint Groups

### Auth (`/auth`)

- `POST /register` — register user.
- `POST /login` — login.
- `POST /refresh` — refresh access token.

### Users (`/users`)

- `GET /me/profile` — my profile.
- `GET /{user_id}/profile` — user profile.
- `GET /search/{name}` — search users.
- `POST /{user_id}/follow` / `DELETE /{user_id}/follow` — follow/unfollow.
- `GET /{user_id}/followers` and `GET /{user_id}/following`.
- `PATCH /me/avatar` / `DELETE /me/avatar` — avatar management.
- `PUT /{user_id}` — update user (admin only).
- `PATCH /{user_id}/role` — change user role (admin only).

### Posts (`/posts`)

- `POST /` — create post.
- `DELETE /{post_id}` / `PUT /{post_id}` — delete/update post.
- `GET /my`, `GET /user/{user_id}` — post lists.
- `GET /feed` — subscription-based feed.
- `POST /{post_id}/comments` — add comment.
- `GET /{post_id}/comments` — list comments.
- `POST /{post_id}/like`, `DELETE /{post_id}/like` — like/unlike.
- `GET /{post_id}/likes/count`, `GET /{post_id}/like-status`.
- `POST /{post_id}/attachments` — upload attachments (up to 5).
- `DELETE /attachments/{attachment_id}` — remove attachment.

### Chats (`/chats`)

- `POST /{user_id}` — create chat with user.
- `GET /` — list user chats.
- `GET /{chat_id}/messages` — list chat messages.
- `POST /{chat_id}/messages` — send message.
- `PATCH /{chat_id}/read` — mark incoming messages as read.
- `GET /{chat_id}/unread-count` — unread message count.
- `POST /{message_id}/attachments` — upload message attachments.
- `DELETE /attachments/{attachment_id}` — remove attachment.

### Notifications (`/notifications`)

- `GET /` — my notifications.
- `GET /unread-count` — unread notifications count.
- `PATCH /{notification_id}/read` — mark a notification as read.
- `PATCH /read-all` — mark all notifications as read.

---

## Media Files

The app serves the `media` directory at:

- `/media/...`

Examples:

- avatars: `media/avatars/...`
- post attachments: `media/post_attachments/...`
- message attachments: `media/message_attachments/...`

---

## Caching and Limits

- Redis is used to cache frequently requested data (profiles, feeds, notifications, chats, etc.).
- Related cache keys are invalidated when data changes.
- Login (`/auth/login`) has rate limiting by IP and email for failed attempts.

---

## Roles

Supported roles:

- `user`
- `admin`
- `moderator`
- `helper`

Some endpoints are restricted to `admin`.

---

## Testing

Run tests with:

```bash
pytest
```

Tests use in-memory SQLite and Redis mocks.

---

## AI help

- Documentation
- Mentor/Teacher
- Tests

---