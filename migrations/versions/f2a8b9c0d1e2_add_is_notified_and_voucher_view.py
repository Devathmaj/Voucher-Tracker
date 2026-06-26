"""Add posts.is_notified and voucher_posts view

Revision ID: f2a8b9c0d1e2
Revises: e1c2d3a4b5f6
Create Date: 2026-07-21

Changes
-------
1. Add ``is_notified`` boolean on ``posts`` (default false).
2. Backfill: rows with status NOTIFIED → is_notified=true, status=PROCESSED.
3. Create ``voucher_posts`` view: AI-confirmed vouchers only.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e1c2d3a4b5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column(
            "is_notified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_posts_is_notified", "posts", ["is_notified"], unique=False)

    # Preserve prior NOTIFIED semantics as a flag; keep workflow status as PROCESSED.
    op.execute(
        sa.text(
            """
            UPDATE posts
            SET is_notified = true,
                status = 'PROCESSED'
            WHERE status = 'NOTIFIED'
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE VIEW voucher_posts AS
            SELECT
                p.id,
                p.source_id,
                p.external_id,
                p.url,
                p.title,
                p.content,
                p.summary,
                p.author,
                p.published_at,
                p.status,
                p.score,
                p.raw_data,
                p.ai_result,
                p.content_hash,
                p.event_id,
                p.is_notified,
                p.created_at,
                p.updated_at,
                p.ai_result->>'vendor' AS vendor,
                p.ai_result->>'promotion_name' AS promotion_name,
                p.ai_result->>'promotion_type' AS promotion_type,
                p.ai_result->>'voucher_code' AS voucher_code,
                p.ai_result->>'discount' AS discount,
                p.ai_result->>'registration_url' AS registration_url,
                p.ai_result->>'reason' AS reason,
                CASE
                    WHEN p.ai_result ? 'confidence'
                         AND (p.ai_result->>'confidence') ~ '^[0-9]+(\\.[0-9]+)?$'
                    THEN (p.ai_result->>'confidence')::double precision
                    ELSE NULL
                END AS confidence
            FROM posts p
            WHERE (p.ai_result->>'is_voucher') = 'true'
              AND p.status = 'PROCESSED'
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS voucher_posts"))
    op.drop_index("ix_posts_is_notified", table_name="posts")
    op.drop_column("posts", "is_notified")
