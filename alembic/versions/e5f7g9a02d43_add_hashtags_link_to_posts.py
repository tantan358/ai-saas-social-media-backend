"""add_hashtags_link_to_posts

Revision ID: e5f7g9a02d43
Revises: d4e6f8a91c32
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa


revision = "e5f7g9a02d43"
down_revision = "d4e6f8a91c32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("hashtags", sa.String(500), nullable=True),
    )
    op.add_column(
        "posts",
        sa.Column("link", sa.String(2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("posts", "link")
    op.drop_column("posts", "hashtags")
