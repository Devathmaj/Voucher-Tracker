"""
Canonical Event model.

An Event represents a single real-world certification promotion (e.g.
"Microsoft AI Skills Fest – 50% off AZ-900").  Many Posts from different
sources can reference the same Event via the ``event_id`` foreign key on the
Post model.

Posts are NEVER merged.  Provenance is preserved through the 1-to-many
relationship between Event and Post.
"""
import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voucherbot.models.base import Base


class EventStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"


class MatchConfidence(enum.Enum):
    """How an event was created or last updated."""
    EXACT = "EXACT"          # deterministic doc dedup (same URL / content_hash)
    AUTO_MERGED = "AUTO_MERGED"    # score >= auto_merge_threshold
    POSSIBLE_MATCH = "POSSIBLE_MATCH"  # score in [possible_match_threshold, auto_merge_threshold)
    NEW = "NEW"              # score below possible_match_threshold → new event


class Event(Base):
    """Canonical certification promotion entity."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- Core promotion fields (populated / updated from AI extraction) ---
    vendor: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    promotion_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    promotion_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    certifications: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)  # list[str]
    voucher_code: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    discount: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    registration_url: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    regions: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)  # list[str]

    # --- Lifecycle ---
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="eventstatus", create_type=False),
        default=EventStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    # --- Audit / provenance ---
    # JSONB list of merge-log entries; each entry records what changed, when,
    # from which source, and at what match score.  Never overwritten — only
    # appended to.  Format:
    # [{"timestamp": "...", "source_type": "BLOG", "post_id": 42,
    #   "match_score": 90, "fields_updated": ["end_date"], "match_confidence": "AUTO_MERGED"}]
    merge_log: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # --- Relationships ---
    posts = relationship("Post", back_populates="event", lazy="select")
