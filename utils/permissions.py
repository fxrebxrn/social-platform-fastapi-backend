from models import Post, User
from core.exceptions import PermissionDeniedError

def ensure_can_modify_post(post: Post, user: User):
    if post.user_id != user.id and user.role not in ["admin", "moderator"]:
        raise PermissionDeniedError()
