import enum
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import String, Integer, Boolean, DateTime, Enum, ForeignKey, Text, UniqueConstraint, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from voucherbot.models.base import Base
from voucherbot.models.event import EventStatus  # noqa: F401 – re-exported for convenience


class PostStatus(enum.Enum):
    NEW = "NEW"
    FILTERED = "FILTERED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    # Kept for DB enum compatibility; app uses ``is_notified`` instead.
    NOTIFIED = "NOTIFIED"
    FAILED = "FAILED"


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_posts_source_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    external_id: Mapped[str] = mapped_column(String, index=True)
    url: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    content: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    author: Mapped[Optional[str]] = mapped_column(String)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[PostStatus] = mapped_column(Enum(PostStatus), default=PostStatus.NEW, index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    raw_data: Mapped[Optional[Any]] = mapped_column(JSONB)
    ai_result: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    # True after a voucher alert email was successfully sent (status stays PROCESSED).
    is_notified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # --- Deduplication ---
    # SHA-1 of normalised(title) + normalised(url).  Nullable so existing rows
    # remain valid; the unique partial index (WHERE content_hash IS NOT NULL)
    # enforces cross-source dedup without touching historical data.
    content_hash: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    # --- Event linkage ---
    # Nullable FK to the canonical Event this post was matched to.  NULL means
    # the post has not yet been processed by the EventMatcher (or the AI
    # classified it as non-voucher content).
    event_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("events.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    source = relationship("Source", back_populates="posts")
    event = relationship("Event", back_populates="posts")


class VoucherPost(Base):
    """Read-only mapping of the ``voucher_posts`` view (AI-confirmed vouchers)."""

    __tablename__ = "voucher_posts"
    __table_args__ = {"info": {"is_view": True}}

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer)
    external_id: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    content: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    author: Mapped[Optional[str]] = mapped_column(String)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus, create_constraint=False, native_enum=True),
    )
    score: Mapped[int] = mapped_column(Integer)
    raw_data: Mapped[Optional[Any]] = mapped_column(JSONB)
    ai_result: Mapped[Optional[Any]] = mapped_column(JSONB)
    content_hash: Mapped[Optional[str]] = mapped_column(String(40))
    event_id: Mapped[Optional[int]] = mapped_column(Integer)
    is_notified: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vendor: Mapped[Optional[str]] = mapped_column(String)
    promotion_name: Mapped[Optional[str]] = mapped_column(String)
    promotion_type: Mapped[Optional[str]] = mapped_column(String)
    voucher_code: Mapped[Optional[str]] = mapped_column(String)
    discount: Mapped[Optional[str]] = mapped_column(String)
    registration_url: Mapped[Optional[str]] = mapped_column(String)
    reason: Mapped[Optional[str]] = mapped_column(String)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
