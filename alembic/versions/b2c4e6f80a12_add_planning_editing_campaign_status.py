"""add_planning_editing_campaign_status

Revision ID: b2c4e6f80a12
Revises: 814f32e35f53
Create Date: 2026-03-15

"""
from alembic import op


revision = "b2c4e6f80a12"
down_revision = "490df0e4bf39"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE campaigns MODIFY COLUMN status ENUM("
        "'DRAFT','AI_PLAN_CREATED','PLAN_APPROVED','PLANNING_GENERATED','PLANNING_EDITING','PLANNING_APPROVED',"
        "'POSTS_GENERATED','POSTS_APPROVED','SCHEDULED','PUBLISHING','COMPLETED','CANCELLED')"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE campaigns MODIFY COLUMN status ENUM("
        "'DRAFT','AI_PLAN_CREATED','PLAN_APPROVED','PLANNING_GENERATED','PLANNING_APPROVED',"
        "'POSTS_GENERATED','POSTS_APPROVED','SCHEDULED','PUBLISHING','COMPLETED','CANCELLED')"
    )
