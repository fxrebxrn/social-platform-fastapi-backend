import io
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient

def _user1_url(user2_id: int) -> str:
    return f"/chats/{user2_id}"

class TestNewChat:
    async def test_create_chat_success(self, client: AsyncClient, user1, user2):
        resp = await client.post(_user1_url(user2.id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Chat created successfully"
        assert "chat_id" in data

    async def test_create_chat_already_exists(self, client: AsyncClient, user1, chat_1_2):
        resp = await client.post(_user1_url(2))
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Chat already exists"
        assert data["chat_id"] == chat_1_2.id

    async def test_create_chat_with_self_returns_400(self, client: AsyncClient, user1):
        resp = await client.post(_user1_url(user1.id))
        assert resp.status_code == 400

    async def test_create_chat_with_nonexistent_user_returns_404(
        self, client: AsyncClient, user1
    ):
        resp = await client.post(_user1_url(9999))
        assert resp.status_code == 404

    async def test_chat_order_is_normalised(self, client: AsyncClient, user1, user2):
        resp1 = await client.post(_user1_url(user2.id))
        chat_id = resp1.json()["chat_id"]
        resp2 = await client.post(_user1_url(user2.id))
        assert resp2.json()["chat_id"] == chat_id

class TestNewMessage:
    async def test_send_message_success(self, client: AsyncClient, user1, chat_1_2):
        resp = await client.post(
            f"/chats/{chat_1_2.id}/messages",
            json={"text": "Привет!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Message sent successfully"
        assert data["data"]["text"] == "Привет!"
        assert data["data"]["sender"]["id"] == user1.id

    async def test_send_message_empty_text_returns_422(
        self, client: AsyncClient, user1, chat_1_2
    ):
        resp = await client.post(
            f"/chats/{chat_1_2.id}/messages",
            json={"text": ""},
        )
        assert resp.status_code == 422

    async def test_send_message_too_long_returns_422(
        self, client: AsyncClient, user1, chat_1_2
    ):
        resp = await client.post(
            f"/chats/{chat_1_2.id}/messages",
            json={"text": "a" * 1001},
        )
        assert resp.status_code == 422

    async def test_send_message_to_foreign_chat_returns_403(
        self, client: AsyncClient, user1, chat_2_3
    ):
        """user1 не является участником chat_2_3."""
        resp = await client.post(
            f"/chats/{chat_2_3.id}/messages",
            json={"text": "Hack!"},
        )
        assert resp.status_code == 403

    async def test_send_message_to_nonexistent_chat_returns_404(
        self, client: AsyncClient, user1
    ):
        resp = await client.post("/chats/9999/messages", json={"text": "Hi"})
        assert resp.status_code == 404

class TestUploadAttachments:
    def _make_file(self, name="file.txt", content_type="text/plain", data=b"hello"):
        return ("files", (name, io.BytesIO(data), content_type))

    async def test_upload_single_attachment_success(
        self, client: AsyncClient, user1, message_from_user1
    ):
        resp = await client.post(
            f"/chats/{message_from_user1.id}/attachments",
            files=[self._make_file()],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Attachments uploaded successfully"
        assert len(data["items"]) == 1

    async def test_upload_disallowed_file_type_returns_400(
        self, client: AsyncClient, user1, message_from_user1
    ):
        resp = await client.post(
            f"/chats/{message_from_user1.id}/attachments",
            files=[self._make_file("evil.exe", "application/octet-stream")],
        )
        assert resp.status_code == 400

    async def test_upload_too_many_attachments_returns_400(
        self, client: AsyncClient, user1, message_from_user1
    ):
        files = [self._make_file(f"f{i}.txt") for i in range(6)]
        resp = await client.post(
            f"/chats/{message_from_user1.id}/attachments",
            files=files,
        )
        assert resp.status_code == 400

    async def test_upload_to_other_users_message_returns_403(
        self, client: AsyncClient, user1, message_from_user2
    ):
        resp = await client.post(
            f"/chats/{message_from_user2.id}/attachments",
            files=[self._make_file()],
        )
        assert resp.status_code == 403

    async def test_upload_to_nonexistent_message_returns_404(
        self, client: AsyncClient, user1
    ):
        resp = await client.post(
            "/chats/9999/attachments",
            files=[self._make_file()],
        )
        assert resp.status_code == 404

    async def test_upload_large_file_returns_400(
        self, client: AsyncClient, user1, message_from_user1
    ):
        big_data = b"x" * (10 * 1024 * 1024 + 1)
        resp = await client.post(
            f"/chats/{message_from_user1.id}/attachments",
            files=[self._make_file("big.txt", "text/plain", big_data)],
        )
        assert resp.status_code == 400

class TestGetAllChats:
    async def test_get_chats_returns_list(self, client: AsyncClient, user1, chat_1_2):
        resp = await client.get("/chats/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 1

    async def test_get_chats_empty_when_no_chats(self, client_user3: AsyncClient):
        resp = await client_user3.get("/chats/")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    async def test_get_chats_limit_capped_at_50(self, client: AsyncClient, user1):
        resp = await client.get("/chats/?limit=200")
        assert resp.status_code == 200

    async def test_get_chats_pagination(self, client: AsyncClient, user1, chat_1_2):
        resp_offset = await client.get("/chats/?limit=50&offset=100")
        assert resp_offset.status_code == 200
        assert resp_offset.json()["items"] == []

    async def test_chats_not_in_others_list(
        self, client: AsyncClient, user1, chat_2_3
    ):
        resp = await client.get("/chats/")
        assert resp.status_code == 200
        ids = [item["chat_id"] for item in resp.json()["items"]]
        assert chat_2_3.id not in ids

class TestGetMessages:
    async def test_get_messages_success(
        self, client: AsyncClient, user1, chat_1_2, message_from_user1
    ):
        resp = await client.get(f"/chats/{chat_1_2.id}/messages")
        assert resp.status_code == 200
        msgs = resp.json()
        assert isinstance(msgs, list)
        assert any(m["id"] == message_from_user1.id for m in msgs)

    async def test_get_messages_from_foreign_chat_returns_403(
        self, client: AsyncClient, user1, chat_2_3
    ):
        resp = await client.get(f"/chats/{chat_2_3.id}/messages")
        assert resp.status_code == 403

    async def test_get_messages_nonexistent_chat_returns_404(
        self, client: AsyncClient, user1
    ):
        resp = await client.get("/chats/9999/messages")
        assert resp.status_code == 404

    async def test_get_messages_empty_chat(
        self, client: AsyncClient, user1, empty_chat
    ):
        resp = await client.get(f"/chats/{empty_chat.id}/messages")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_messages_limit_capped(
        self, client: AsyncClient, user1, chat_1_2
    ):
        resp = await client.get(f"/chats/{chat_1_2.id}/messages?limit=200")
        assert resp.status_code == 200

class TestUnreadCount:
    async def test_unread_count_zero_when_no_messages(
        self, client: AsyncClient, user1, empty_chat
    ):
        resp = await client.get(f"/chats/{empty_chat.id}/unread-count")
        assert resp.status_code == 200
        assert resp.json()["message"] == 0

    async def test_unread_count_includes_partner_messages(
        self, client: AsyncClient, user1, chat_1_2, message_from_user2
    ):
        resp = await client.get(f"/chats/{chat_1_2.id}/unread-count")
        assert resp.status_code == 200
        assert resp.json()["message"] == 1

    async def test_own_messages_not_counted_as_unread(
        self, client: AsyncClient, user1, chat_1_2, message_from_user1
    ):
        resp = await client.get(f"/chats/{chat_1_2.id}/unread-count")
        assert resp.status_code == 200
        assert resp.json()["message"] == 0

    async def test_unread_count_foreign_chat_returns_403(
        self, client: AsyncClient, user1, chat_2_3
    ):
        resp = await client.get(f"/chats/{chat_2_3.id}/unread-count")
        assert resp.status_code == 403

    async def test_unread_count_nonexistent_chat_returns_404(
        self, client: AsyncClient, user1
    ):
        resp = await client.get("/chats/9999/unread-count")
        assert resp.status_code == 404

class TestReadMessages:
    async def test_read_all_messages_success(
        self, client: AsyncClient, user1, chat_1_2, message_from_user2
    ):
        resp = await client.patch(f"/chats/{chat_1_2.id}/read")
        assert resp.status_code == 200
        assert resp.json()["message"] == "All messages marked as read"

    async def test_read_marks_messages_as_read(
        self, client: AsyncClient, user1, chat_1_2, message_from_user2
    ):
        # До: 1 непрочитанное
        before = await client.get(f"/chats/{chat_1_2.id}/unread-count")
        assert before.json()["message"] == 1

        await client.patch(f"/chats/{chat_1_2.id}/read")

        # После: 0 непрочитанных
        after = await client.get(f"/chats/{chat_1_2.id}/unread-count")
        assert after.json()["message"] == 0

    async def test_read_foreign_chat_returns_403(
        self, client: AsyncClient, user1, chat_2_3
    ):
        resp = await client.patch(f"/chats/{chat_2_3.id}/read")
        assert resp.status_code == 403

    async def test_read_nonexistent_chat_returns_404(
        self, client: AsyncClient, user1
    ):
        resp = await client.patch("/chats/9999/read")
        assert resp.status_code == 404

class TestDeleteChat:
    async def test_delete_chat_success(
        self, client: AsyncClient, user1, chat_1_2
    ):
        resp = await client.delete(f"/chats/{chat_1_2.id}")
        assert resp.status_code == 200
        assert str(chat_1_2.id) in resp.json()["message"]

    async def test_delete_chat_removes_messages(
        self, client: AsyncClient, user1, chat_1_2, message_from_user1
    ):
        await client.delete(f"/chats/{chat_1_2.id}")
        resp = await client.get(f"/chats/{chat_1_2.id}/messages")
        assert resp.status_code == 404

    async def test_delete_chat_removes_attachment_files(
        self, client: AsyncClient, user1, chat_1_2, attachment_on_message
    ):
        file_path = os.path.join("media", attachment_on_message.file_url)
        assert os.path.exists(file_path)

        await client.delete(f"/chats/{chat_1_2.id}")
        assert not os.path.exists(file_path)

    async def test_delete_foreign_chat_returns_403(
        self, client: AsyncClient, user1, chat_2_3
    ):
        resp = await client.delete(f"/chats/{chat_2_3.id}")
        assert resp.status_code == 403

    async def test_delete_nonexistent_chat_returns_404(
        self, client: AsyncClient, user1
    ):
        resp = await client.delete("/chats/9999")
        assert resp.status_code == 404

class TestDeleteMessage:
    async def test_delete_own_message_success(
        self, client: AsyncClient, user1, chat_1_2, message_from_user1
    ):
        resp = await client.delete(f"/chats/messages/{message_from_user1.id}")
        assert resp.status_code == 200
        assert str(message_from_user1.id) in resp.json()["message"]

    async def test_delete_other_users_message_returns_403(
        self, client: AsyncClient, user1, chat_1_2, message_from_user2
    ):
        resp = await client.delete(f"/chats/messages/{message_from_user2.id}")
        assert resp.status_code == 403

    async def test_delete_nonexistent_message_returns_404(
        self, client: AsyncClient, user1
    ):
        resp = await client.delete("/chats/messages/9999")
        assert resp.status_code == 404

    async def test_delete_message_removes_attachment_file(
        self, client: AsyncClient, user1, message_from_user1, attachment_on_message
    ):
        file_path = os.path.join("media", attachment_on_message.file_url)
        assert os.path.exists(file_path)

        await client.delete(f"/chats/messages/{message_from_user1.id}")
        assert not os.path.exists(file_path)

    async def test_delete_message_in_foreign_chat_returns_403(
        self, client: AsyncClient, user1, chat_2_3, db_session
    ):
        from models import Message
        msg = Message(sender_id=2, chat_id=chat_2_3.id, text="foreign msg")
        db_session.add(msg)
        await db_session.commit()

        resp = await client.delete(f"/chats/messages/{msg.id}")
        assert resp.status_code == 403

class TestDeleteAttachment:
    async def test_delete_own_attachment_success(
        self, client: AsyncClient, user1, attachment_on_message
    ):
        resp = await client.delete(f"/chats/attachments/{attachment_on_message.id}")
        assert resp.status_code == 200

    async def test_delete_attachment_removes_file_from_disk(
        self, client: AsyncClient, user1, attachment_on_message
    ):
        file_path = os.path.join("media", attachment_on_message.file_url)
        assert os.path.exists(file_path)

        await client.delete(f"/chats/attachments/{attachment_on_message.id}")
        assert not os.path.exists(file_path)

    async def test_delete_others_attachment_returns_403(
        self, client: AsyncClient, user1, chat_1_2, message_from_user2, db_session
    ):
        import uuid, os
        from models import MessageAttachment
        os.makedirs("media/message_attachments", exist_ok=True)
        fname = f"{uuid.uuid4()}.txt"
        fpath = os.path.join("media/message_attachments", fname)
        with open(fpath, "w") as f:
            f.write("content")
        att = MessageAttachment(
            message_id=message_from_user2.id,
            file_url=f"message_attachments/{fname}",
            file_type="text/plain",
            original_name="other.txt",
        )
        db_session.add(att)
        await db_session.commit()

        resp = await client.delete(f"/chats/attachments/{att.id}")
        assert resp.status_code == 403

    async def test_delete_nonexistent_attachment_returns_404(
        self, client: AsyncClient, user1
    ):
        resp = await client.delete("/chats/attachments/9999")
        assert resp.status_code == 404

    async def test_delete_attachment_in_foreign_chat_returns_403(
        self, client: AsyncClient, user1, chat_2_3, db_session
    ):
        import uuid, os
        from models import Message, MessageAttachment
        os.makedirs("media/message_attachments", exist_ok=True)
        msg = Message(sender_id=2, chat_id=chat_2_3.id, text="msg")
        db_session.add(msg)
        await db_session.commit()

        fname = f"{uuid.uuid4()}.txt"
        fpath = os.path.join("media/message_attachments", fname)
        with open(fpath, "w") as f:
            f.write("x")
        att = MessageAttachment(
            message_id=msg.id,
            file_url=f"message_attachments/{fname}",
            file_type="text/plain",
            original_name="f.txt",
        )
        db_session.add(att)
        await db_session.commit()

        resp = await client.delete(f"/chats/attachments/{att.id}")
        assert resp.status_code == 403
