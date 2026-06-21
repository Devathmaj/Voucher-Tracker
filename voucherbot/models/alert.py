from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from voucherbot.models.base import Base
from datetime import datetime
from typing import Optional
import enum

class NotificationMethod(str, enum.Enum):
    EMAIL = "EMAIL"
    DISCORD = "DISCORD"
    TELEGRAM = "TELEGRAM"

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    method: Mapped[NotificationMethod]
    sent_at: Mapped[Optional[datetime]]
    status: Mapped[Optional[str]]
