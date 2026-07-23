from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from voucherbot.models.base import Base


class VendorMapping(Base):
    __tablename__ = "vendor_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    url_pattern: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_name_pattern: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, index=True
    )
    vendor: Mapped[str] = mapped_column(String, nullable=False)
