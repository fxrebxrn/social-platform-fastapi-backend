from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    age = Column(Integer)
    email = Column(String, unique=True, nullable=False)
    avatar_url = Column(String, nullable=True)
    role = Column(String, default="user")
    hashed_password = Column(String, nullable=False)
    posts = relationship("Post", back_populates="user", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan")
    following = relationship("Follow", foreign_keys="Follow.follower_id", back_populates="follower", cascade="all, delete-orphan")
    followers = relationship("Follow", foreign_keys="Follow.following_id", back_populates="following_user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", foreign_keys="Notification.user_id", cascade="all, delete-orphan")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_online = Column(Boolean, default=True)

class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (Index("ix_posts_user_id_created_at", "user_id", "created_at"),)

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="post", cascade="all, delete-orphan")
    attachments = relationship("PostAttachment", back_populates="post", cascade="all, delete-orphan")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (Index("ix_comments_post_id_created_at", "post_id", "created_at"),)

    id = Column(Integer, primary_key=True)
    text = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True, index=True)
    user = relationship("User", back_populates="comments")
    post = relationship("Post", back_populates="comments")
    parent = relationship("Comment", remote_side=[id], back_populates="replies")
    replies = relationship("Comment", back_populates="parent", cascade="all, delete-orphan")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="unique_like"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    user = relationship("User", back_populates="likes")
    post = relationship("Post", back_populates="likes")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Follow(Base):
    __tablename__ = "follows"

    __table_args__ = (
        UniqueConstraint("follower_id", "following_id", name="unique_follow"),
    )

    id = Column(Integer, primary_key=True)
    follower_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    following_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    follower = relationship("User", foreign_keys=[follower_id], back_populates="following")
    following_user = relationship("User", foreign_keys=[following_id], back_populates="followers")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_id_created_at", "user_id", "created_at"), 
                      Index("ix_notifications_user_id_is_read", "user_id", "is_read"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True, index=True)
    message = Column(String, nullable=False)
    notification_type = Column(String, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id], back_populates="notifications")
    sender = relationship("User", foreign_keys=[sender_id])
    post = relationship("Post", foreign_keys=[post_id])
    comment = relationship("Comment", foreign_keys=[comment_id])

class Chat(Base):
    __tablename__ = "chats"
    __table_args__ = (
        UniqueConstraint("user1_id", "user2_id", name="unique_chat"),
        Index("ix_chats_user1_id_updated_at", "user1_id", "updated_at"),
        Index("ix_chats_user2_id_updated_at", "user2_id", "updated_at"),
    )

    id = Column(Integer, primary_key=True)
    user1_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user2_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    user1 = relationship("User", foreign_keys=[user1_id])
    user2 = relationship("User", foreign_keys=[user2_id])

class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_chat_id_created_at", "chat_id", "created_at"), 
                      Index("ix_messages_chat_id_is_read", "chat_id", "is_read"), 
                      Index("ix_messages_chat_id_is_read_sender_id", "chat_id", "is_read", "sender_id"),)

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False, index=True)
    text = Column(String, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")

class Attachment(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True)
    file_url = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    original_name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PostAttachment(Attachment):
    __tablename__ = "post_attachments"

    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    post = relationship("Post", back_populates="attachments")

class MessageAttachment(Attachment):
    __tablename__ = "message_attachments"

    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)
    message = relationship("Message", back_populates="attachments")
