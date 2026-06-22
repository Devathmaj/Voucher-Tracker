"""Add ai_result column to posts

Revision ID: b1f3e2a9d047
Revises: ca84fdb8ee85
Create Date: 2026-07-17 22:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b1f3e2a9d047'
down_revision: Union[str, Sequence[str], None] = 'ca84fdb8ee85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ai_result JSONB column to posts table."""
    op.add_column(
        'posts',
        sa.Column(
            'ai_result',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        )
    )


def downgrade() -> None:
    """Remove ai_result column from posts table."""
    op.drop_column('posts', 'ai_result')
