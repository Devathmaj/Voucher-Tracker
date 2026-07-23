"""Add url_pattern column to vendor_mappings

Revision ID: i9j0k1l2m3n4
Revises: h4d5e6f7a8b9
Create Date: 2026-07-23

Changes
-------
1. Add ``url_pattern`` column to ``vendor_mappings`` (nullable).
2. Make ``source_name_pattern`` nullable.
3. Add unique index on ``url_pattern``.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, Sequence[str], None] = "h4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vendor_mappings",
        sa.Column("url_pattern", sa.String(), nullable=True),
    )
    op.alter_column(
        "vendor_mappings",
        "source_name_pattern",
        existing_type=sa.String(),
        nullable=True,
    )
    op.create_index(
        "ix_vendor_mappings_url_pattern",
        "vendor_mappings",
        ["url_pattern"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_vendor_mappings_url_pattern", table_name="vendor_mappings")
    op.alter_column(
        "vendor_mappings",
        "source_name_pattern",
        existing_type=sa.String(),
        nullable=False,
    )
    op.drop_column("vendor_mappings", "url_pattern")
