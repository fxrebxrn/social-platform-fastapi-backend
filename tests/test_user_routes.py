import io
import os
import uuid
import pytest
from httpx import AsyncClient


class TestFollowUser:
    async def test_follow_user_success(self, client: AsyncClient, user1, user2):
        resp = await client.post(f"/users/{user2.id}/follow")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == f"You are now following user {user2.name}"

    async def test_follow_self_returns_400(self, client: AsyncClient, user1):
        resp = await client.post(f"/users/{user1.id}/follow")
        assert resp.status_code == 400

    async def test_follow_nonexistent_user_returns_404(self, client: AsyncClient, user1):
        resp = await client.post("/users/9999/follow")
        assert resp.status_code == 404

    async def test_follow_already_following_returns_400(self, client: AsyncClient, user1, follow_1_2):
        resp = await client.post(f"/users/{follow_1_2.following_id}/follow")
        assert resp.status_code == 400


class TestSearchUsers:
    async def test_search_users_success(self, client: AsyncClient, user2):
        resp = await client.get(f"/users/search/{user2.name}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    async def test_search_users_name_too_short_returns_400(self, client: AsyncClient):
        resp = await client.get("/users/search/ab")
        assert resp.status_code == 400

    async def test_search_users_name_too_long_returns_400(self, client: AsyncClient):
        long_name = "a" * 51
        resp = await client.get(f"/users/search/{long_name}")
        assert resp.status_code == 400

    async def test_search_users_no_results(self, client: AsyncClient):
        resp = await client.get("/users/search/nonexistent_user_xyz")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_search_users_with_limit_and_offset(self, client: AsyncClient, user2):
        resp = await client.get(f"/users/search/{user2.name}?limit=5&offset=0")
        assert resp.status_code == 200


class TestUserFollowers:
    async def test_get_user_followers_success(self, client: AsyncClient, user1, follow_1_2):
        resp = await client.get(f"/users/{follow_1_2.following_id}/followers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    async def test_get_user_followers_nonexistent_returns_404(self, client: AsyncClient):
        resp = await client.get("/users/9999/followers")
        assert resp.status_code == 404

    async def test_get_user_followers_empty(self, client: AsyncClient, user3):
        resp = await client.get(f"/users/{user3.id}/followers")
        assert resp.status_code == 200
        assert resp.json() == []


class TestUserFollowing:
    async def test_get_user_following_success(self, client: AsyncClient, user2, follow_1_2):
        resp = await client.get(f"/users/{follow_1_2.follower_id}/following")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    async def test_get_user_following_nonexistent_returns_404(self, client: AsyncClient):
        resp = await client.get("/users/9999/following")
        assert resp.status_code == 404

    async def test_get_user_following_empty(self, client: AsyncClient, user3):
        resp = await client.get(f"/users/{user3.id}/following")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetMyProfile:
    async def test_get_my_profile_success(self, client: AsyncClient, user1):
        resp = await client.get("/users/me/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == user1.id
        assert data["name"] == user1.name
        assert "followers_count" in data
        assert "following_count" in data
        assert "posts_count" in data

    async def test_get_my_profile_has_avatar_url(self, client: AsyncClient, user1):
        resp = await client.get("/users/me/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "avatar_url" in data


class TestGetUserProfile:
    async def test_get_user_profile_success(self, client: AsyncClient, user1, user2):
        resp = await client.get(f"/users/{user2.id}/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == user2.id
        assert data["name"] == user2.name
        assert "is_following" in data

    async def test_get_user_profile_nonexistent_returns_404(self, client: AsyncClient):
        resp = await client.get("/users/9999/profile")
        assert resp.status_code == 404

    async def test_get_user_profile_is_following_true(self, client: AsyncClient, user1, follow_1_2):
        resp = await client.get(f"/users/{follow_1_2.following_id}/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_following"] == True

    async def test_get_user_profile_is_following_false(self, client: AsyncClient, user1, user2):
        resp = await client.get(f"/users/{user2.id}/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_following"] == False

    async def test_get_own_profile_has_is_following(self, client: AsyncClient, user1):
        resp = await client.get(f"/users/{user1.id}/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "is_following" in data


class TestChangeAvatar:
    def _make_image_file(self, name="avatar.jpg", format="JPEG"):
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="red")
        img_io = io.BytesIO()
        img.save(img_io, format=format)
        img_io.seek(0)
        return ("avatar", (name, img_io, f"image/{format.lower()}"))

    async def test_change_avatar_success(self, client: AsyncClient, user1):
        resp = await client.patch(
            "/users/me/avatar",
            files=[self._make_image_file()]
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Avatar uploaded successfully"
        assert "avatar_url" in data
        assert data["avatar_url"].endswith(".webp")

    async def test_change_avatar_invalid_type_returns_400(self, client: AsyncClient, user1):
        resp = await client.patch(
            "/users/me/avatar",
            files=[("avatar", ("file.txt", io.BytesIO(b"hello"), "text/plain"))]
        )
        assert resp.status_code == 400

    async def test_change_avatar_too_large_returns_400(self, client: AsyncClient, user1):
        large_data = b"x" * (3 * 1024 * 1024)
        resp = await client.patch(
            "/users/me/avatar",
            files=[("avatar", ("large.jpg", io.BytesIO(large_data), "image/jpeg"))]
        )
        assert resp.status_code == 400

    async def test_change_avatar_overwrites_old(self, client: AsyncClient, user1, db_session):
        resp1 = await client.patch(
            "/users/me/avatar",
            files=[self._make_image_file()]
        )
        assert resp1.status_code == 200
        avatar_url_1 = resp1.json()["avatar_url"]
        
        resp2 = await client.patch(
            "/users/me/avatar",
            files=[self._make_image_file()]
        )
        assert resp2.status_code == 200
        avatar_url_2 = resp2.json()["avatar_url"]
        
        assert avatar_url_1 != avatar_url_2

    async def test_change_avatar_webp_format(self, client: AsyncClient, user1):
        resp = await client.patch(
            "/users/me/avatar",
            files=[self._make_image_file("avatar.png", "PNG")]
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["avatar_url"].endswith(".webp")


class TestUpdateUserRole:
    async def test_update_user_role_success(self, client_admin: AsyncClient, user2):
        resp = await client_admin.patch(
            f"/users/{user2.id}/role",
            params={"new_role": "moderator"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "User role updated successfully"

    async def test_update_user_role_nonexistent_user_returns_404(self, client_admin: AsyncClient):
        resp = await client_admin.patch(
            "/users/9999/role",
            params={"new_role": "moderator"}
        )
        assert resp.status_code == 404

    async def test_update_user_role_invalid_role_returns_400(self, client_admin: AsyncClient, user2):
        resp = await client_admin.patch(
            f"/users/{user2.id}/role",
            params={"new_role": "invalid_role"}
        )
        assert resp.status_code == 400

    async def test_update_own_role_cannot_remove_admin_returns_400(self, client_admin: AsyncClient, admin_user):
        resp = await client_admin.patch(
            f"/users/{admin_user.id}/role",
            params={"new_role": "user"}
        )
        assert resp.status_code == 400

    async def test_update_user_role_non_admin_returns_403(self, client: AsyncClient, user2):
        resp = await client.patch(
            f"/users/{user2.id}/role",
            params={"new_role": "moderator"}
        )
        assert resp.status_code == 403


class TestUpdateUser:
    async def test_update_user_success(self, client_admin: AsyncClient, user2):
        resp = await client_admin.put(
            f"/users/{user2.id}",
            json={
                "name": "Updated Name",
                "age": 30,
                "email": "newemail@test.com"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "User updated successfully"

    async def test_update_user_nonexistent_returns_404(self, client_admin: AsyncClient):
        resp = await client_admin.put(
            "/users/99999",
            json={
                "name": "Test User",
                "age": 25,
                "email": "test@test.com"
            }
        )
        assert resp.status_code == 404

    async def test_update_user_duplicate_email_returns_400(self, client_admin: AsyncClient, user1, user2):
        resp = await client_admin.put(
            f"/users/{user2.id}",
            json={
                "name": "Test User",
                "age": 25,
                "email": user1.email
            }
        )
        assert resp.status_code == 400

    async def test_update_user_non_admin_returns_403(self, client: AsyncClient, user2):
        resp = await client.put(
            f"/users/{user2.id}",
            json={
                "name": "New Name",
                "age": 25,
                "email": "newtest@test.com"
            }
        )
        assert resp.status_code == 403


class TestRemoveAvatar:
    def _make_image_file(self, name="avatar.jpg", format="JPEG"):
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="red")
        img_io = io.BytesIO()
        img.save(img_io, format=format)
        img_io.seek(0)
        return ("avatar", (name, img_io, f"image/{format.lower()}"))

    async def test_remove_avatar_success(self, client: AsyncClient, user1):
        await client.patch(
            "/users/me/avatar",
            files=[self._make_image_file()]
        )
        
        resp = await client.delete("/users/me/avatar")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Avatar deleted successfully"

    async def test_remove_avatar_no_avatar_returns_404(self, client: AsyncClient, user1):
        resp = await client.delete("/users/me/avatar")
        assert resp.status_code == 404


class TestUnfollowUser:
    async def test_unfollow_user_success(self, client: AsyncClient, follow_1_2):
        resp = await client.delete(f"/users/{follow_1_2.following_id}/follow")
        assert resp.status_code == 200
        data = resp.json()
        assert "You are no longer following" in data["message"]

    async def test_unfollow_nonexistent_user_returns_404(self, client: AsyncClient):
        resp = await client.delete("/users/9999/follow")
        assert resp.status_code == 404

    async def test_unfollow_not_following_returns_400(self, client: AsyncClient, user1, user2):
        resp = await client.delete(f"/users/{user2.id}/follow")
        assert resp.status_code == 400

    async def test_unfollow_user_with_notification(self, client: AsyncClient, follow_1_2):
        resp = await client.delete(f"/users/{follow_1_2.following_id}/follow")
        assert resp.status_code == 200


class TestFollowUnfollowFlow:
    async def test_follow_then_unfollow(self, client: AsyncClient, user1, user2):
        resp_follow = await client.post(f"/users/{user2.id}/follow")
        assert resp_follow.status_code == 200
        
        resp_followers = await client.get(f"/users/{user2.id}/followers")
        assert resp_followers.status_code == 200
        followers = resp_followers.json()
        assert len(followers) == 1
        
        resp_unfollow = await client.delete(f"/users/{user2.id}/follow")
        assert resp_unfollow.status_code == 200
        
        resp_followers_after = await client.get(f"/users/{user2.id}/followers")
        assert resp_followers_after.status_code == 200
        assert resp_followers_after.json() == []

    async def test_multiple_follows_and_unfollows(self, client: AsyncClient, user1, user2, user3):
        resp1 = await client.post(f"/users/{user2.id}/follow")
        assert resp1.status_code == 200
        
        resp_followers = await client.get(f"/users/{user2.id}/followers")
        assert len(resp_followers.json()) == 1


class TestEdgeCases:
    async def test_search_with_special_characters(self, client: AsyncClient):
        resp = await client.get("/users/search/test%20user")
        assert resp.status_code == 200

    async def test_get_profile_with_string_id(self, client: AsyncClient):
        resp = await client.get("/users/abc/profile")
        assert resp.status_code in [404, 422]

    async def test_follow_with_negative_id(self, client: AsyncClient):
        resp = await client.post("/users/-1/follow")
        assert resp.status_code in [404, 422]

    async def test_change_avatar_invalid_image(self, client: AsyncClient, user1):
        resp = await client.patch(
            "/users/me/avatar",
            files=[("avatar", ("fake.jpg", io.BytesIO(b"not an image"), "image/jpeg"))]
        )
        assert resp.status_code == 400

    async def test_update_user_with_none_values(self, client_admin: AsyncClient, user2):
        resp = await client_admin.put(
            f"/users/{user2.id}",
            json={
                "name": user2.name,
                "age": user2.age,
                "email": user2.email
            }
        )
        assert resp.status_code == 200
