import pytest
from httpx import AsyncClient
from models import Post, Comment, Like, PostAttachment, User, Follow
from sqlalchemy.ext.asyncio import AsyncSession
from io import BytesIO

class TestCreatePost:
    @pytest.mark.asyncio
    async def test_create_post_success(self, client: AsyncClient):
        response = await client.post("/posts/", json={"title": "New post"})
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Post created"
        assert data["post"]["title"] == "New post"

    @pytest.mark.asyncio
    async def test_create_post_empty_title(self, client: AsyncClient):
        response = await client.post("/posts/", json={"title": ""})
        assert response.status_code == 422

class TestAddComment:
    @pytest.mark.asyncio
    async def test_add_comment_success(self, client: AsyncClient, post1: Post):
        response = await client.post(f"/posts/{post1.id}/comments", json={"text": "New comment"})
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Comment added successfully"
        assert data["comment"]["text"] == "New comment"

    @pytest.mark.asyncio
    async def test_add_comment_invalid_post_id(self, client: AsyncClient):
        response = await client.post("/posts/999/comments", json={"text": "Comment"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_add_comment_empty_text(self, client: AsyncClient, post1: Post):
        response = await client.post(f"/posts/{post1.id}/comments", json={"text": ""})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_add_comment_with_parent(self, client: AsyncClient, post1: Post, comment1: Comment):
        response = await client.post(f"/posts/{post1.id}/comments", json={"text": "Reply", "parent_id": comment1.id})
        assert response.status_code == 200
        data = response.json()
        assert data["comment"]["parent_id"] == comment1.id

    @pytest.mark.asyncio
    async def test_add_comment_invalid_parent_id(self, client: AsyncClient, post1: Post):
        response = await client.post(f"/posts/{post1.id}/comments", json={"text": "Comment", "parent_id": 0})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_add_comment_parent_not_in_post(self, client: AsyncClient, post1: Post, user2: User, db_session, post2: Post):
        from models import Comment
        comment = Comment(text="Other comment", user_id=user2.id, post_id=post2.id)
        db_session.add(comment)
        await db_session.commit()
        response = await client.post(f"/posts/{post1.id}/comments", json={"text": "Reply", "parent_id": comment.id})
        assert response.status_code == 400

class TestUploadAttachments:
    @pytest.mark.asyncio
    async def test_upload_attachment_success(self, client: AsyncClient, post1: Post):
        files = {"files": ("test.txt", BytesIO(b"content"), "text/plain")}
        response = await client.post(f"/posts/{post1.id}/attachments", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Attachments upload successfully"
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_upload_attachment_invalid_post(self, client: AsyncClient):
        files = {"files": ("test.txt", BytesIO(b"content"), "text/plain")}
        response = await client.post("/posts/999/attachments", files=files)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_attachment_invalid_type(self, client: AsyncClient, post1: Post):
        files = {"files": ("test.exe", BytesIO(b"content"), "application/octet-stream")}
        response = await client.post(f"/posts/{post1.id}/attachments", files=files)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_attachment_too_large(self, client: AsyncClient, post1: Post):
        large_content = b"x" * (11 * 1024 * 1024)
        files = {"files": ("large.txt", BytesIO(large_content), "text/plain")}
        response = await client.post(f"/posts/{post1.id}/attachments", files=files)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_attachment_too_many(self, client: AsyncClient, post1: Post):
        files = [("files", ("test.txt", BytesIO(b"content"), "text/plain")) for _ in range(6)]
        response = await client.post(f"/posts/{post1.id}/attachments", files=files)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_attachment_not_owner(self, client_user3: AsyncClient, post1: Post):
        files = {"files": ("test.txt", BytesIO(b"content"), "text/plain")}
        response = await client_user3.post(f"/posts/{post1.id}/attachments", files=files)
        assert response.status_code == 403

class TestAddLike:
    @pytest.mark.asyncio
    async def test_add_like_success(self, client: AsyncClient, post2: Post):
        response = await client.post(f"/posts/{post2.id}/like")
        assert response.status_code == 200
        data = response.json()
        assert "successfully added" in data["message"]

    @pytest.mark.asyncio
    async def test_add_like_invalid_post(self, client: AsyncClient):
        response = await client.post("/posts/999/like")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_add_like_already_exists(self, client: AsyncClient, like1: Like):
        response = await client.post(f"/posts/{like1.post_id}/like")
        assert response.status_code == 400

class TestGetUserPosts:
    @pytest.mark.asyncio
    async def test_get_user_posts_success(self, client: AsyncClient, user1: User, post1: Post):
        response = await client.get(f"/posts/user/{user1.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test post 1"

    @pytest.mark.asyncio
    async def test_get_user_posts_invalid_user(self, client: AsyncClient):
        response = await client.get("/posts/user/999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_user_posts_empty(self, client: AsyncClient, user3: User):
        response = await client.get(f"/posts/user/{user3.id}")
        assert response.status_code == 200
        assert response.json() == []

class TestGetLikesCount:
    @pytest.mark.asyncio
    async def test_get_likes_count_success(self, client: AsyncClient, post2: Post, like1: Like):
        response = await client.get(f"/posts/{post2.id}/likes/count")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == 1

    @pytest.mark.asyncio
    async def test_get_likes_count_invalid_post(self, client: AsyncClient):
        response = await client.get("/posts/999/likes/count")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_likes_count_zero(self, client: AsyncClient, post1: Post):
        response = await client.get(f"/posts/{post1.id}/likes/count")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == 0

class TestLikeStatus:
    @pytest.mark.asyncio
    async def test_like_status_liked(self, client: AsyncClient, like1: Like):
        response = await client.get(f"/posts/{like1.post_id}/like-status")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] is True

    @pytest.mark.asyncio
    async def test_like_status_not_liked(self, client: AsyncClient, post1: Post):
        response = await client.get(f"/posts/{post1.id}/like-status")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] is False

    @pytest.mark.asyncio
    async def test_like_status_invalid_post(self, client: AsyncClient):
        response = await client.get("/posts/999/like-status")
        assert response.status_code == 404

class TestGetMyPosts:
    @pytest.mark.asyncio
    async def test_get_my_posts_success(self, client: AsyncClient, post1: Post):
        response = await client.get("/posts/my")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test post 1"

    @pytest.mark.asyncio
    async def test_get_my_posts_empty(self, client_user3: AsyncClient):
        response = await client_user3.get("/posts/my")
        assert response.status_code == 200
        assert response.json() == []

class TestGetUserFeed:
    @pytest.mark.asyncio
    async def test_get_user_feed_success(self, client: AsyncClient, follow_1_2: Follow, post2: Post):
        response = await client.get("/posts/feed")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 50
        assert data["has_more"] is False
        assert data["next_cursor"] is None
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Test post 2"

    @pytest.mark.asyncio
    async def test_get_user_feed_no_follows(self, client_user3: AsyncClient):
        response = await client_user3.get("/posts/feed")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 50
        assert data["has_more"] is False
        assert data["next_cursor"] is None
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_get_user_feed_with_limit(self, client: AsyncClient, follow_1_2: Follow, post2: Post):
        response = await client.get("/posts/feed?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["has_more"] is False
        assert data["next_cursor"] is None
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_get_user_feed_limit_too_high(self, client: AsyncClient, follow_1_2: Follow, post2: Post):
        response = await client.get("/posts/feed?limit=100")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 50
        assert data["has_more"] is False
        assert data["next_cursor"] is None

    @pytest.mark.asyncio
    async def test_get_user_feed_cursor_pagination(self, client: AsyncClient, follow_1_2: Follow, post2: Post, db_session: AsyncSession, user2: User):
        from models import Post

        extra_posts = []
        for i in range(3):
            extra_post = Post(title=f"Feed post {i}", user_id=user2.id)
            db_session.add(extra_post)
            extra_posts.append(extra_post)
        await db_session.flush()

        first_response = await client.get("/posts/feed?limit=1")
        assert first_response.status_code == 200
        first_data = first_response.json()
        assert first_data["limit"] == 1
        assert first_data["has_more"] is True
        assert first_data["next_cursor"] is not None
        assert len(first_data["items"]) == 1

        cursor = first_data["next_cursor"]
        next_response = await client.get(
            "/posts/feed",
            params={
                "limit": 1,
                "cursor_id": cursor["id"],
                "cursor_created_at": cursor["created_at"]
            }
        )
        assert next_response.status_code == 200
        next_data = next_response.json()
        assert next_data["limit"] == 1
        assert len(next_data["items"]) == 1
        assert next_data["next_cursor"] is not None or next_data["has_more"] is False

class TestGetPostComments:
    @pytest.mark.asyncio
    async def test_get_post_comments_success(self, client: AsyncClient, post1: Post, comment1: Comment):
        response = await client.get(f"/posts/{post1.id}/comments")
        assert response.status_code == 200
        data = response.json()
        assert len(data["comments"]) == 1
        assert data["comments"][0]["text"] == "Test comment"

    @pytest.mark.asyncio
    async def test_get_post_comments_invalid_post(self, client: AsyncClient):
        response = await client.get("/posts/999/comments")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_post_comments_empty(self, client: AsyncClient, post2: Post):
        response = await client.get(f"/posts/{post2.id}/comments")
        assert response.status_code == 200
        data = response.json()
        assert data["comments"] == []

class TestGetFullPost:
    @pytest.mark.asyncio
    async def test_get_full_post_success(self, client: AsyncClient, post1: Post):
        response = await client.get(f"/posts/{post1.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["post"]["title"] == "Test post 1"

    @pytest.mark.asyncio
    async def test_get_full_post_invalid_post(self, client: AsyncClient):
        response = await client.get("/posts/999")
        assert response.status_code == 404

class TestUpdatePost:
    @pytest.mark.asyncio
    async def test_update_post_success(self, client: AsyncClient, post1: Post):
        response = await client.put(f"/posts/{post1.id}", json={"title": "Updated title"})
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Post updated successfully"
        assert data["post"]["title"] == "Updated title"

    @pytest.mark.asyncio
    async def test_update_post_invalid_post(self, client: AsyncClient):
        response = await client.put("/posts/999", json={"title": "Title"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_post_same_title(self, client: AsyncClient, post1: Post):
        response = await client.put(f"/posts/{post1.id}", json={"title": "Test post 1"})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_post_not_owner(self, client_user3: AsyncClient, post1: Post):
        response = await client_user3.put(f"/posts/{post1.id}", json={"title": "Title"})
        assert response.status_code == 403

class TestRemoveAttachment:
    @pytest.mark.asyncio
    async def test_remove_attachment_success(self, client: AsyncClient, attachment1: PostAttachment):
        response = await client.delete(f"/posts/attachments/{attachment1.id}")
        assert response.status_code == 200
        data = response.json()
        assert "deleted successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_remove_attachment_invalid_id(self, client: AsyncClient):
        response = await client.delete("/posts/attachments/999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_remove_attachment_not_owner(self, client_user3: AsyncClient, attachment1: PostAttachment):
        response = await client_user3.delete(f"/posts/attachments/{attachment1.id}")
        assert response.status_code == 403

class TestRemoveLike:
    @pytest.mark.asyncio
    async def test_remove_like_success(self, client: AsyncClient, like1: Like):
        response = await client.delete(f"/posts/{like1.post_id}/like")
        assert response.status_code == 200
        data = response.json()
        assert "removed" in data["message"]

    @pytest.mark.asyncio
    async def test_remove_like_invalid_post(self, client: AsyncClient):
        response = await client.delete("/posts/999/like")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_remove_like_not_liked(self, client: AsyncClient, post1: Post):
        response = await client.delete(f"/posts/{post1.id}/like")
        assert response.status_code == 404

class TestDeletePost:
    @pytest.mark.asyncio
    async def test_delete_post_success(self, client: AsyncClient, post1: Post):
        response = await client.delete(f"/posts/{post1.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Post deleted"

    @pytest.mark.asyncio
    async def test_delete_post_invalid_post(self, client: AsyncClient):
        response = await client.delete("/posts/999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_post_not_owner(self, client_user3: AsyncClient, post1: Post):
        response = await client_user3.delete(f"/posts/{post1.id}")
        assert response.status_code == 403

class TestDeleteComment:
    @pytest.mark.asyncio
    async def test_delete_comment_success(self, client: AsyncClient, comment1: Comment):
        response = await client.delete(f"/posts/comments/{comment1.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Comment deleted"

    @pytest.mark.asyncio
    async def test_delete_comment_invalid_id(self, client: AsyncClient):
        response = await client.delete("/posts/comments/999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_comment_not_owner(self, client_user3: AsyncClient, comment1: Comment):
        response = await client_user3.delete(f"/posts/comments/{comment1.id}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_comment_as_admin(self, client_admin: AsyncClient, comment1: Comment):
        response = await client_admin.delete(f"/posts/comments/{comment1.id}")
        assert response.status_code == 200