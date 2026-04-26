from models import User, Post, Comment, Message

def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "age": user.age,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "is_adult": user.age >= 18,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }

def users_to_dicts(users: list[User]):
    return [user_to_dict(u) for u in users]

def post_to_dict(post: Post) -> dict:
    return {
        "id": post.id,
        "title": post.title,
        "user_id": post.user_id,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
        "attachments": [
            {
                "id": att.id,
                "file_url": att.file_url,
                "file_type": att.file_type,
                "original_name": att.original_name
            }
            for att in post.attachments
        ] if post.attachments else []
    }

def posts_to_dicts(posts: list[Post]):
    return [post_to_dict(p) for p in posts]

def comment_to_dict(comment: Comment) -> dict:
    return {
        "id": comment.id,
        "text": comment.text,
        "post_id": comment.post_id,
        "parent_id": comment.parent_id,
        "user": {
            "id": comment.user.id,
            "name": comment.user.name
        },
        "created_at": comment.created_at
    }

def message_to_dict(message: Message) -> dict:
    return {
        "id": message.id,
        "chat_id": message.chat_id,
        "sender": {
            "id": message.sender.id,
            "name": message.sender.name
        },
        "text": message.text,
        "attachments": [
            {
                "id": att.id,
                "file_url": att.file_url,
                "file_type": att.file_type,
                "original_name": att.original_name
            }
            for att in message.attachments
        ],
        "is_read": message.is_read,
        "created_at": message.created_at
    }

def messages_to_dicts(messages: list[Message]):
    return [message_to_dict(m) for m in messages]

def comments_to_dicts(comments: list[Comment]):
    return [comment_to_dict(c) for c in comments]