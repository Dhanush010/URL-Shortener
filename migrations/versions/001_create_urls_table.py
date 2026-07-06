"""Create urls and click_events tables.

Revision ID: 001
Revises:
Create Date: 2026-07-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "urls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("short_code", sa.String(length=10), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("api_key", sa.String(length=64), nullable=True),
        sa.Column("click_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("short_code"),
    )
    op.create_index("idx_urls_short_code", "urls", ["short_code"], unique=True)
    op.create_index("idx_urls_api_key", "urls", ["api_key"], unique=False)
    op.create_index("idx_urls_created_at", "urls", [sa.text("created_at DESC")], unique=False)

    op.create_table(
        "click_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("short_code", sa.String(length=10), nullable=False),
        sa.Column(
            "clicked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_clicks_short_code", "click_events", ["short_code"], unique=False)
    op.create_index(
        "idx_clicks_clicked_at",
        "click_events",
        [sa.text("clicked_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_clicks_clicked_at", table_name="click_events")
    op.drop_index("idx_clicks_short_code", table_name="click_events")
    op.drop_table("click_events")

    op.drop_index("idx_urls_created_at", table_name="urls")
    op.drop_index("idx_urls_api_key", table_name="urls")
    op.drop_index("idx_urls_short_code", table_name="urls")
    op.drop_table("urls")
