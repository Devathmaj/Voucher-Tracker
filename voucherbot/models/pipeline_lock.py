from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from voucherbot.models.base import Base


class PipelineLock(Base):
    __tablename__ = "pipeline_lock"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    holder: Mapped[Optional[str]] = mapped_column(String)
    acquired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
