import pytest
from httpx import AsyncClient

class TestNotificationList:
    async def test_get_my_notifications_success(self, client: AsyncClient, notification1):
        resp = await client.get("/notifications/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["message"] == "You have a new message"
        assert data[0]["notification_type"] == "message"

    async def test_get_my_notifications_empty(self, client_user3: AsyncClient):
        resp = await client_user3.get("/notifications/")
        assert resp.status_code == 200
        assert resp.json() == []


class TestUnreadNotificationCount:
    async def test_get_unread_count_success(self, client: AsyncClient, notification1, notification_read):
        resp = await client.get("/notifications/unread-count")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == 1

    async def test_get_unread_count_zero(self, client_user3: AsyncClient):
        resp = await client_user3.get("/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json()["message"] == 0


class TestReadNotification:
    async def test_read_notification_success(self, client: AsyncClient, notification1):
        resp = await client.patch(f"/notifications/{notification1.id}/read")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Notification marked as read"

    async def test_read_notification_already_read(self, client: AsyncClient, notification_read):
        resp = await client.patch(f"/notifications/{notification_read.id}/read")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Notification already read"

    async def test_read_notification_not_found(self, client: AsyncClient):
        resp = await client.patch("/notifications/999/read")
        assert resp.status_code == 404

    async def test_read_notification_forbidden(self, client_user3: AsyncClient, notification1):
        resp = await client_user3.patch(f"/notifications/{notification1.id}/read")
        assert resp.status_code == 403


class TestReadAllNotifications:
    async def test_read_all_notifications_success(self, client: AsyncClient, notification1, notification_read):
        resp = await client.patch("/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["message"] == "All notifications marked as read"

    async def test_read_all_notifications_no_notifications(self, client_user3: AsyncClient):
        resp = await client_user3.patch("/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["message"] == "All notifications marked as read"
