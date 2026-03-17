"""milestone3_scheduling_windows

Add balanced weekly distribution, publication_windows, scheduling_logs,
and update monthly_plans / posts for scheduling.

Revision ID: f6a8b0c13e54
Revises: e5f7g9a02d43
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa

revision = "f6a8b0c13e54"
down_revision = "e5f7g9a02d43"
branch_labels = None
depends_on = None

# New post status enum (Milestone 3)
POST_STATUS_NEW = (
    "generated",
    "edited",
    "ready_for_final_review",
    "approved_final",
    "scheduled",
    "paused",
    "canceled",
)

POST_PLATFORM_ENUM = ("linkedin", "instagram")
DAY_OF_WEEK_ENUM = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
SCHEDULING_MODE_ENUM = ("manual", "auto_windowed")


def upgrade() -> None:
    # 1. monthly_plans: new columns
    op.add_column(
        "monthly_plans",
        sa.Column("total_posts", sa.Integer(), nullable=True),
    )
    op.add_column(
        "monthly_plans",
        sa.Column("min_posts_per_week", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "monthly_plans",
        sa.Column("max_posts_per_week", sa.Integer(), nullable=False, server_default="5"),
    )
    op.add_column(
        "monthly_plans",
        sa.Column("distribution_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "monthly_plans",
        sa.Column(
            "scheduling_mode",
            sa.Enum(*SCHEDULING_MODE_ENUM, name="scheduling_mode"),
            nullable=False,
            server_default="manual",
        ),
    )

    # 2. publication_windows table (before posts references it)
    op.create_table(
        "publication_windows",
        sa.Column("id", sa.CHAR(36), nullable=False),
        sa.Column("campaign_id", sa.CHAR(36), nullable=False),
        sa.Column(
            "platform",
            sa.Enum(*POST_PLATFORM_ENUM, name="postplatform"),
            nullable=False,
        ),
        sa.Column(
            "day_of_week",
            sa.Enum(*DAY_OF_WEEK_ENUM, name="dayofweek"),
            nullable=False,
        ),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_publication_windows_campaign_id", "publication_windows", ["campaign_id"])

    # 3. posts: new columns and enum changes
    op.add_column("posts", sa.Column("scheduled_date", sa.Date(), nullable=True))
    op.add_column("posts", sa.Column("scheduled_time", sa.Time(), nullable=True))
    op.add_column(
        "posts",
        sa.Column("scheduling_window_id", sa.CHAR(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_posts_scheduling_window_id",
        "posts",
        "publication_windows",
        ["scheduling_window_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_posts_scheduling_window_id", "posts", ["scheduling_window_id"])

    # Ensure scheduled_at is explicitly nullable (may already be)
    op.alter_column(
        "posts",
        "scheduled_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )

    # Migrate posts.status to new enum: extend enum, backfill, then restrict
    op.execute(
        "ALTER TABLE posts MODIFY COLUMN status ENUM("
        "'draft','generated','edited','approved','pending_approval','scheduled','published','failed','cancelled',"
        "'DRAFT','GENERATED','EDITED','APPROVED','PENDING_APPROVAL','SCHEDULED','PUBLISHED','FAILED','CANCELLED',"
        "'ready_for_final_review','approved_final','paused','canceled')"
    )
    op.execute(
        "UPDATE posts SET status = 'approved_final' WHERE status IN ('APPROVED','approved')"
    )
    op.execute(
        "UPDATE posts SET status = 'ready_for_final_review' WHERE status IN ('PENDING_APPROVAL','pending_approval')"
    )
    op.execute(
        "UPDATE posts SET status = 'canceled' WHERE status IN ('CANCELLED','cancelled')"
    )
    op.execute(
        "UPDATE posts SET status = 'generated' WHERE status IN ('DRAFT','draft','PUBLISHED','published','FAILED','failed')"
    )
    op.execute(
        "ALTER TABLE posts MODIFY COLUMN status ENUM("
        "'generated','edited','ready_for_final_review','approved_final',"
        "'scheduled','paused','canceled')"
    )

    # posts.platform: add enum column, backfill from existing varchar, drop varchar, rename enum column to platform
    op.add_column(
        "posts",
        sa.Column(
            "platform_enum",
            sa.Enum(*POST_PLATFORM_ENUM, name="postplatform_posts"),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE posts SET platform_enum = LOWER(TRIM(platform)) "
        "WHERE platform IS NOT NULL AND LOWER(TRIM(platform)) IN ('linkedin','instagram')"
    )
    op.drop_column("posts", "platform")
    op.alter_column(
        "posts",
        "platform_enum",
        new_column_name="platform",
    )

    # 4. scheduling_logs table
    op.create_table(
        "scheduling_logs",
        sa.Column("id", sa.CHAR(36), nullable=False),
        sa.Column("campaign_id", sa.CHAR(36), nullable=False),
        sa.Column("post_id", sa.CHAR(36), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_id", sa.CHAR(36), nullable=True),
        sa.Column("scheduling_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["window_id"], ["publication_windows.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_scheduling_logs_campaign_id", "scheduling_logs", ["campaign_id"])
    op.create_index("ix_scheduling_logs_post_id", "scheduling_logs", ["post_id"])
    op.create_index("ix_scheduling_logs_window_id", "scheduling_logs", ["window_id"])

    # 5. Seed default publication windows for existing campaigns
    # Mon–Fri 09:00–17:00 per platform (linkedin, instagram) for each campaign
    import uuid as uuid_mod
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id FROM campaigns"))
    campaign_ids = [row[0] for row in result]
    for cid in campaign_ids:
        for platform in POST_PLATFORM_ENUM:
            for day in DAY_OF_WEEK_ENUM:
                if day in ("saturday", "sunday"):
                    continue
                wid = str(uuid_mod.uuid4())
                conn.execute(
                    sa.text(
                        "INSERT INTO publication_windows (id, campaign_id, platform, day_of_week, start_time, end_time, priority, is_active) "
                        "VALUES (:id, :cid, :platform, :day, '09:00:00', '17:00:00', 1, 1)"
                    ),
                    {"id": wid, "cid": cid, "platform": platform, "day": day},
                )


def downgrade() -> None:
    # Remove seed data (windows for campaigns) - optional; table drop will remove all
    op.drop_index("ix_scheduling_logs_window_id", "scheduling_logs")
    op.drop_index("ix_scheduling_logs_post_id", "scheduling_logs")
    op.drop_index("ix_scheduling_logs_campaign_id", "scheduling_logs")
    op.drop_table("scheduling_logs")

    # posts: restore platform as VARCHAR, restore old status enum
    op.add_column(
        "posts",
        sa.Column("platform_varchar", sa.String(50), nullable=True),
    )
    op.execute(
        "UPDATE posts SET platform_varchar = platform WHERE platform IS NOT NULL"
    )
    op.drop_column("posts", "platform")
    op.alter_column(
        "posts",
        "platform_varchar",
        new_column_name="platform",
    )

    op.execute(
        "ALTER TABLE posts MODIFY COLUMN status ENUM("
        "'DRAFT','GENERATED','EDITED','APPROVED','PENDING_APPROVAL',"
        "'SCHEDULED','PUBLISHED','FAILED','CANCELLED')"
    )

    # Restore posts.status to old enum: extend, backfill, restrict
    op.execute(
        "ALTER TABLE posts MODIFY COLUMN status ENUM("
        "'generated','edited','ready_for_final_review','approved_final','scheduled','paused','canceled',"
        "'DRAFT','GENERATED','EDITED','APPROVED','PENDING_APPROVAL','SCHEDULED','PUBLISHED','FAILED','CANCELLED')"
    )
    op.execute("UPDATE posts SET status = 'APPROVED' WHERE status = 'approved_final'")
    op.execute("UPDATE posts SET status = 'PENDING_APPROVAL' WHERE status = 'ready_for_final_review'")
    op.execute("UPDATE posts SET status = 'CANCELLED' WHERE status = 'canceled'")
    op.execute("UPDATE posts SET status = 'GENERATED' WHERE status IN ('generated','edited','paused')")
    op.execute("UPDATE posts SET status = 'SCHEDULED' WHERE status = 'scheduled'")
    op.execute(
        "ALTER TABLE posts MODIFY COLUMN status ENUM("
        "'DRAFT','GENERATED','EDITED','APPROVED','PENDING_APPROVAL',"
        "'SCHEDULED','PUBLISHED','FAILED','CANCELLED')"
    )

    op.drop_index("ix_posts_scheduling_window_id", "posts")
    op.drop_constraint("fk_posts_scheduling_window_id", "posts", type_="foreignkey")
    op.drop_column("posts", "scheduling_window_id")
    op.drop_column("posts", "scheduled_time")
    op.drop_column("posts", "scheduled_date")

    op.drop_index("ix_publication_windows_campaign_id", "publication_windows")
    op.drop_table("publication_windows")

    op.drop_column("monthly_plans", "scheduling_mode")
    op.drop_column("monthly_plans", "distribution_json")
    op.drop_column("monthly_plans", "max_posts_per_week")
    op.drop_column("monthly_plans", "min_posts_per_week")
    op.drop_column("monthly_plans", "total_posts")
