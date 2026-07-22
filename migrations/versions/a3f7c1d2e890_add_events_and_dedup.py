"""Add events table; add content_hash and event_id to posts

Revision ID: a3f7c1d2e890
Revises: b1f3e2a9d047
Create Date: 2026-07-20

Changes
-------
1. Create ``eventstatus`` and ``matchconfidence`` enums.
2. Create ``events`` table (canonical promotion entity).
3. Add ``content_hash`` (VARCHAR 40, nullable) to ``posts``.
4. Add partial UNIQUE index on ``posts.content_hash WHERE content_hash IS NOT NULL``.
   This enforces cross-source document deduplication without touching NULL rows,
   which means existing posts (with no hash) remain valid and a future backfill
   can populate hashes incrementally.
5. Add ``event_id`` (nullable FK → events.id) to ``posts``.

Downgrade removes all of the above in reverse order.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "a3f7c1d2e890"
down_revision: Union[str, Sequence[str], None] = "b1f3e2a9d047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 2. Create events table
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vendor", sa.String(), nullable=True),
        sa.Column("promotion_name", sa.String(), nullable=True),
        sa.Column("promotion_type", sa.String(), nullable=True),
        sa.Column(
            "certifications", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("voucher_code", sa.String(), nullable=True),
        sa.Column("discount", sa.String(), nullable=True),
        sa.Column("registration_url", sa.String(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("regions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "EXPIRED", "ARCHIVED", name="eventstatus"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("merge_log", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_status", "events", ["status"], unique=False)
    op.create_index("ix_events_vendor", "events", ["vendor"], unique=False)
    op.create_index("ix_events_voucher_code", "events", ["voucher_code"], unique=False)
    op.create_index(
        "ix_events_registration_url", "events", ["registration_url"], unique=False
    )

    # 3. Add content_hash to posts (nullable — existing rows remain valid)
    op.add_column("posts", sa.Column("content_hash", sa.String(40), nullable=True))

    # 4. Partial unique index: enforces cross-source doc dedup, ignores NULLs
    op.execute(
        "CREATE UNIQUE INDEX uq_posts_content_hash "
        "ON posts (content_hash) "
        "WHERE content_hash IS NOT NULL"
    )
    op.create_index("ix_posts_content_hash", "posts", ["content_hash"], unique=False)

    # 5. Add event_id FK to posts (nullable — existing rows remain detached)
    op.add_column(
        "posts",
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True),
    )
    op.create_index("ix_posts_event_id", "posts", ["event_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_posts_event_id", table_name="posts")
    op.drop_column("posts", "event_id")

    op.drop_index("ix_posts_content_hash", table_name="posts")
    op.execute("DROP INDEX IF EXISTS uq_posts_content_hash")
    op.drop_column("posts", "content_hash")

    op.drop_index("ix_events_registration_url", table_name="events")
    op.drop_index("ix_events_voucher_code", table_name="events")
    op.drop_index("ix_events_vendor", table_name="events")
    op.drop_index("ix_events_status", table_name="events")
    op.drop_table("events")

    op.execute("DROP TYPE IF EXISTS matchconfidence")
    op.execute("DROP TYPE IF EXISTS eventstatus")
