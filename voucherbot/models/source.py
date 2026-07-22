import enum
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import String, Integer, Boolean, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from voucherbot.models.base import Base


class SourceType(enum.Enum):
    REDDIT = "REDDIT"
    RSS = "RSS"
    BLOG = "BLOG"
    EVENT = "EVENT"
    FORUM = "FORUM"
    WEBSITE = "WEBSITE"
    API = "API"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    type: Mapped[SourceType] = mapped_column(Enum(SourceType), index=True)
    base_url: Mapped[Optional[str]] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    last_checked_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    next_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    avg_runtime_ms: Mapped[Optional[int]] = mapped_column(Integer)
    consecutive_failures: Mapped[Optional[int]] = mapped_column(Integer)
    backoff_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    priority_tier: Mapped[Optional[str]] = mapped_column(String(1))
    config: Mapped[Optional[Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    posts = relationship("Post", back_populates="source")
