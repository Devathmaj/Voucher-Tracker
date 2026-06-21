from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from voucherbot.models.base import Base
from datetime import datetime
from typing import Optional

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    title: Mapped[str]
    url: Mapped[str]
    content: Mapped[Optional[str]]
    published_at: Mapped[Optional[datetime]]
    score: Mapped[Optional[int]]
    is_alert: Mapped[bool] = mapped_column(default=False)
