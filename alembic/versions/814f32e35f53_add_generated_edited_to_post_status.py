"""add_generated_edited_to_post_status

Revision ID: 814f32e35f53
Revises: a1b2c3d4e5f6
Create Date: 2026-03-15 22:10:58.114508

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '814f32e35f53'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure posts.status ENUM includes GENERATED and EDITED (fixes generate-plan 500)
    op.execute(
        "ALTER TABLE posts MODIFY COLUMN status ENUM("
        "'DRAFT','GENERATED','EDITED','APPROVED','PENDING_APPROVAL',"
        "'SCHEDULED','PUBLISHED','FAILED','CANCELLED')"
    )
    # Ensure campaigns.status ENUM includes PLANNING_* (match milestone2)
    op.execute(
        "ALTER TABLE campaigns MODIFY COLUMN status ENUM("
        "'DRAFT','AI_PLAN_CREATED','PLAN_APPROVED','PLANNING_GENERATED','PLANNING_APPROVED',"
        "'POSTS_GENERATED','POSTS_APPROVED','SCHEDULED','PUBLISHING','COMPLETED','CANCELLED')"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE posts MODIFY COLUMN status ENUM("
        "'DRAFT','PENDING_APPROVAL','APPROVED','SCHEDULED','PUBLISHED','FAILED','CANCELLED')"
    )
    op.execute(
        "ALTER TABLE campaigns MODIFY COLUMN status ENUM("
        "'DRAFT','AI_PLAN_CREATED','PLAN_APPROVED','POSTS_GENERATED','POSTS_APPROVED',"
        "'SCHEDULED','PUBLISHING','COMPLETED','CANCELLED')"
    )
