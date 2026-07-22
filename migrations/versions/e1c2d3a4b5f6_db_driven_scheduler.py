"""DB-driven scheduler: source scheduling columns and pipeline lock

Revision ID: e1c2d3a4b5f6
Revises: a3f7c1d2e890
Create Date: 2026-07-20

Changes
-------
1. Add scheduling columns to ``sources`` (all nullable for safe rollout).
2. Create ``pipeline_lock`` single-row lease table.
3. Seed the ``pipeline`` lock row.
4. Backfill ``next_due_at`` and ``priority_tier`` on existing sources.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1c2d3a4b5f6"
down_revision: Union[str, Sequence[str], None] = "a3f7c1d2e890"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sources",
        sa.Column("avg_runtime_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "sources",
        sa.Column("consecutive_failures", sa.Integer(), nullable=True),
    )
    op.add_column(
        "sources",
        sa.Column("backoff_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sources",
        sa.Column("priority_tier", sa.String(length=1), nullable=True),
    )

    op.create_table(
        "pipeline_lock",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("holder", sa.String(), nullable=True),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("name"),
    )
    op.execute(
        sa.text(
            "INSERT INTO pipeline_lock (name, holder, acquired_at, expires_at) "
            "VALUES ('pipeline', NULL, NULL, NULL)"
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE sources
            SET next_due_at = CASE
                WHEN last_checked_utc IS NOT NULL
                     AND (config->>'poll_interval_minutes') ~ '^[0-9]+$'
                THEN last_checked_utc
                     + ((config->>'poll_interval_minutes')::int * interval '1 minute')
                ELSE now()
            END
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE sources
            SET priority_tier = CASE
                WHEN priority = 1 THEN 'A'
                WHEN priority = 2 THEN 'B'
                ELSE 'C'
            END
            """
        )
    )


def downgrade() -> None:
    op.drop_table("pipeline_lock")
    op.drop_column("sources", "priority_tier")
    op.drop_column("sources", "backoff_until")
    op.drop_column("sources", "consecutive_failures")
    op.drop_column("sources", "avg_runtime_ms")
    op.drop_column("sources", "next_due_at")
