"""Schema freeze: ensure keywords table exists

Revision ID: g3b9c0d1e2f3
Revises: f2a8b9c0d1e2
Create Date: 2026-07-21

Frozen baseline for production. Captures the ``keywords`` table that previously
existed only via ``create_all``, so ``alembic upgrade head`` fully reproduces
the schema without relying on ORM create_all.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "g3b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f2a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = inspect(bind).get_table_names()
    if "keywords" in existing:
        return

    op.create_table(
        "keywords",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("keyword", sa.String(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_keywords_keyword", "keywords", ["keyword"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_keywords_keyword", table_name="keywords")
    op.drop_table("keywords")
