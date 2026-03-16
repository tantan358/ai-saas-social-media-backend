"""add_content_objective_to_posts

Revision ID: d4e6f8a91c32
Revises: c3d5e7f90b21
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa


revision = "d4e6f8a91c32"
down_revision = "c3d5e7f90b21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("content_objective", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("posts", "content_objective")
