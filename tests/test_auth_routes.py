import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from core.redis_client import redis_client

@pytest.fixture(autouse=True)
def mock_password_helpers():
    with patch("services.auth_service.hash_password", side_effect=lambda v: f"hashed-{v}"), \
         patch("services.auth_service.verify_password", side_effect=lambda plain, hashed: hashed == f"hashed-{plain}"):
        yield

class TestRegisterRoutes:
    async def test_register_user_success(self, client: AsyncClient):
        payload = {
            "name": "New User",
            "age": 22,
            "email": "newuser@test.com",
            "password": "strongpass"
        }

        resp = await client.post("/auth/register", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "User registered successfully"
        assert data["user"]["name"] == "New User"
        assert data["user"]["id"] > 0

    async def test_register_user_with_invalid_email(self, client: AsyncClient):
        payload = {
            "name": "User",
            "age": 20,
            "email": "invalid-email",
            "password": "strongpass"
        }

        resp = await client.post("/auth/register", json=payload)
        assert resp.status_code == 422

    async def test_register_user_with_short_password(self, client: AsyncClient):
        payload = {
            "name": "User",
            "age": 20,
            "email": "user@test.com",
            "password": "short"
        }

        resp = await client.post("/auth/register", json=payload)
        assert resp.status_code == 422

    async def test_register_user_duplicate_email(self, client: AsyncClient, user1):
        payload = {
            "name": "Another User",
            "age": 28,
            "email": user1.email,
            "password": "anotherpass"
        }

        resp = await client.post("/auth/register", json=payload)
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Email already exists"


class TestLoginRoutes:
    async def test_login_success(self, client: AsyncClient):
        register_payload = {
            "name": "Login User",
            "age": 24,
            "email": "loginuser@test.com",
            "password": "loginpass123"
        }
        await client.post("/auth/register", json=register_payload)

        login_payload = {
            "username": register_payload["email"],
            "password": register_payload["password"]
        }
        resp = await client.post("/auth/login", data=login_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "bearer"

    async def test_login_invalid_password(self, client: AsyncClient):
        register_payload = {
            "name": "Wrong Pass User",
            "age": 26,
            "email": "wrongpass@test.com",
            "password": "correctpass123"
        }
        await client.post("/auth/register", json=register_payload)

        resp = await client.post(
            "/auth/login",
            data={"username": register_payload["email"], "password": "badpass"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Incorrect credentials"

    async def test_login_invalid_email(self, client: AsyncClient):
        resp = await client.post(
            "/auth/login",
            data={"username": "notfound@test.com", "password": "anything"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Incorrect credentials"

    async def test_login_too_many_failed_attempts(self, client: AsyncClient):
        with patch.object(redis_client, "get", new_callable=AsyncMock, return_value="5"):
            resp = await client.post(
                "/auth/login",
                data={"username": "anything@test.com", "password": "wrong"}
            )

        assert resp.status_code == 429
        assert resp.json()["detail"] == "Too many failed login attempts. Try again later."


class TestRefreshRoutes:
    async def test_refresh_token_success(self, client: AsyncClient):
        register_payload = {
            "name": "Refresh User",
            "age": 30,
            "email": "refreshuser@test.com",
            "password": "refreshpass123"
        }
        await client.post("/auth/register", json=register_payload)

        login_resp = await client.post(
            "/auth/login",
            data={"username": register_payload["email"], "password": register_payload["password"]}
        )
        login_data = login_resp.json()

        resp = await client.post("/auth/refresh", json={"refresh_token": login_data["refresh_token"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        assert data["token_type"] == "bearer"

    async def test_refresh_token_with_access_token(self, client: AsyncClient):
        register_payload = {
            "name": "Refresh Fail User",
            "age": 31,
            "email": "refreshfail@test.com",
            "password": "refreshpass321"
        }
        await client.post("/auth/register", json=register_payload)

        login_resp = await client.post(
            "/auth/login",
            data={"username": register_payload["email"], "password": register_payload["password"]}
        )
        login_data = login_resp.json()

        resp = await client.post("/auth/refresh", json={"refresh_token": login_data["access_token"]})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    async def test_refresh_token_invalid_token(self, client: AsyncClient):
        resp = await client.post("/auth/refresh", json={"refresh_token": "invalid.token.value"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"
