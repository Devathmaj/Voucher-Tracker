import enum
from datetime import datetime
from typing import Optional, List, Any
from sqlalchemy import String, Integer, Boolean, DateTime, Enum, ForeignKey, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from voucherbot.models.base import Base

class PostStatus(enum.Enum):
    NEW = "NEW"
    FILTERED = "FILTERED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    NOTIFIED = "NOTIFIED"
    FAILED = "FAILED"
    DUPLICATE = "DUPLICATE"

class Subreddit(Base):
    __tablename__ = "reddit_subreddits"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_utc: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    priority: Mapped[int] = mapped_column(Integer, default=0)

    posts = relationship("RedditPost", back_populates="subreddit")


class RedditKeyword(Base):
    __tablename__ = "reddit_keywords"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String, unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[Optional[str]] = mapped_column(String)


class RedditPost(Base):
    __tablename__ = "reddit_posts"

    id: Mapped[str] = mapped_column(String, primary_key=True) # Reddit submission ID
    subreddit_id: Mapped[int] = mapped_column(ForeignKey("reddit_subreddits.id"))
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String)
    permalink: Mapped[str] = mapped_column(String)
    
    author: Mapped[str] = mapped_column(String)
    author_id: Mapped[Optional[str]] = mapped_column(String)
    is_mod: Mapped[bool] = mapped_column(Boolean, default=False)
    distinguished: Mapped[Optional[str]] = mapped_column(String)
    
    score: Mapped[int] = mapped_column(Integer, default=0)
    num_comments: Mapped[int] = mapped_column(Integer, default=0)
    
    created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    edited_utc: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    thumbnail: Mapped[Optional[str]] = mapped_column(String)
    preview_images: Mapped[Optional[Any]] = mapped_column(JSONB)
    video_url: Mapped[Optional[str]] = mapped_column(String)
    gallery: Mapped[Optional[Any]] = mapped_column(JSONB)
    link_flair: Mapped[Optional[str]] = mapped_column(String)
    post_flair: Mapped[Optional[str]] = mapped_column(String)
    
    raw_json: Mapped[Optional[Any]] = mapped_column(JSONB)
    
    status: Mapped[PostStatus] = mapped_column(Enum(PostStatus), default=PostStatus.NEW, index=True)
    embedding = mapped_column(Vector(1536)) # Example embedding size (OpenAI)

    subreddit = relationship("Subreddit", back_populates="posts")
    analysis = relationship("RedditAiAnalysis", back_populates="post", uselist=False)
    notifications = relationship("RedditNotification", back_populates="post")


class RedditAiAnalysis(Base):
    __tablename__ = "reddit_ai_analysis"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("reddit_posts.id"), unique=True)
    
    relevance_score: Mapped[Optional[float]] = mapped_column(Float)
    category: Mapped[Optional[str]] = mapped_column(String)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    keywords: Mapped[Optional[Any]] = mapped_column(JSONB)
    
    model_used: Mapped[Optional[str]] = mapped_column(String)
    prompt_version: Mapped[Optional[str]] = mapped_column(String)
    tokens: Mapped[Optional[int]] = mapped_column(Integer)
    cost: Mapped[Optional[float]] = mapped_column(Float) # Alternatively Numeric for exact cost
    processing_ms: Mapped[Optional[int]] = mapped_column(Integer)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    post = relationship("RedditPost", back_populates="analysis")


class RedditNotification(Base):
    __tablename__ = "reddit_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("reddit_posts.id"))
    channel: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String) # e.g., SENT, FAILED
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    post = relationship("RedditPost", back_populates="notifications")
