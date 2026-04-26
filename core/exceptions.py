class AppError(Exception):
    status_code = 400
    detail = "Application error"

class UserNotFoundError(AppError):
    status_code = 404
    detail = "User not found"

class PostNotFoundError(AppError):
    status_code = 404
    detail = "Post not found"

class PermissionDeniedError(AppError):
    status_code = 403
    detail = "Not enough permissions"

class InvalidTokenError(AppError):
    status_code = 401
    detail = "Invalid token"

class ExpiredTokenError(AppError):
    status_code = 401
    detail = "Token has expired"

class CommentNotFoundError(AppError):
    status_code = 404
    detail = "Comment not found"

class ChatNotFoundError(AppError):
    status_code = 404
    detail = "Chat not found"

class MessageNotFoundError(AppError):
    status_code = 404
    detail = "Message not found"

class FileNotFoundError(AppError):
    status_code = 404
    detail = "File not found"

class AttachmentNotFoundError(AppError):
    status_code = 404
    detail = "Attachment not found"

class SelfFollowError(AppError):
    status_code = 400
    detail = "You cannot follow yourself"

class AlreadyFollowingError(AppError):
    status_code = 400
    detail = "You are already following this user"

class AlreadyUnfollowingError(AppError):
    status_code = 400
    detail = "You are not following this user"

class NotFoundError(AppError):
    status_code = 404
    detail = "Not found"
