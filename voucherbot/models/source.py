from sqlalchemy.orm import Mapped, mapped_column
from voucherbot.models.base import Base

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    type: Mapped[str]
    base_url: Mapped[str]
    enabled: Mapped[bool] = mapped_column(default=True)
