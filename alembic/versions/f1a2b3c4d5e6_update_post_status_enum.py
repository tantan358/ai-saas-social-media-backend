"""update_post_status_enum

Revision ID: f1a2b3c4d5e6
Revises: d4e6f8a91c32
Create Date: 2026-03-17

This migration aligns the MySQL ENUM values for posts.status with the
current PostStatus enum in app.modules.campaigns.models.

Previously, the column used legacy values like 'DRAFT' / 'APPROVED'.
The application now uses statuses such as 'GENERATED' and
'APPROVED_FINAL', which caused DataError(1265) when approving plans.
"""

from alembic import op


revision = "f1a2b3c4d5e6"
down_revision = "f6a8b0c13e54"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Map legacy post statuses into the new set so we don't lose data when
    # we change the ENUM definition. The mapping is conservative and only
    # touches known legacy values.
    op.execute(
        "UPDATE posts SET status = 'GENERATED' "
        "WHERE status IN ('DRAFT', 'PENDING_APPROVAL')"
    )
    op.execute(
        "UPDATE posts SET status = 'APPROVED_FINAL' "
        "WHERE status IN ('APPROVED', 'PUBLISHED')"
    )
    op.execute(
        "UPDATE posts SET status = 'CANCELED' "
        "WHERE status = 'CANCELLED'"
    )
    # FAILED remains unsupported in the new enum; map it to PAUSED so we
    # keep a non-terminal state.
    op.execute(
        "UPDATE posts SET status = 'PAUSED' "
        "WHERE status = 'FAILED'"
    )

    # Now redefine the ENUM to match app.modules.campaigns.models.PostStatus
    # (names: GENERATED, EDITED, READY_FOR_FINAL_REVIEW, APPROVED_FINAL,
    # SCHEDULED, PAUSED, CANCELED).
    op.execute(
        """
        ALTER TABLE posts
        MODIFY COLUMN status ENUM(
          'GENERATED',
          'EDITED',
          'READY_FOR_FINAL_REVIEW',
          'APPROVED_FINAL',
          'SCHEDULED',
          'PAUSED',
          'CANCELED'
        ) NOT NULL
        """
    )


def downgrade() -> None:
    # Best‑effort downgrade: map new values back into the original legacy set
    # and restore the original ENUM definition.
    op.execute(
        "UPDATE posts SET status = 'DRAFT' WHERE status = 'GENERATED'"
    )
    op.execute(
        "UPDATE posts SET status = 'PENDING_APPROVAL' "
        "WHERE status = 'READY_FOR_FINAL_REVIEW'"
    )
    op.execute(
        "UPDATE posts SET status = 'APPROVED' "
        "WHERE status = 'APPROVED_FINAL'"
    )
    op.execute(
        "UPDATE posts SET status = 'CANCELLED' "
        "WHERE status = 'CANCELED'"
    )

    op.execute(
        """
        ALTER TABLE posts
        MODIFY COLUMN status ENUM(
          'DRAFT',
          'PENDING_APPROVAL',
          'APPROVED',
          'SCHEDULED',
          'PUBLISHED',
          'FAILED',
          'CANCELLED'
        ) NOT NULL
        """
    )

