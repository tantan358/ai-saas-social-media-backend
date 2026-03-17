from sqlalchemy import Column, String, Text, DateTime, Date, Time, ForeignKey, Enum, Boolean, JSON, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import CHAR
import enum
import uuid
from app.database import Base


class SchedulingMode(str, enum.Enum):
    MANUAL = "manual"
    AUTO_WINDOWED = "auto_windowed"


class DayOfWeek(str, enum.Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class PostPlatform(str, enum.Enum):
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    PLANNING_GENERATED = "planning_generated"
    PLANNING_EDITING = "planning_editing"
    PLANNING_APPROVED = "planning_approved"
    # Legacy / future
    POSTS_GENERATED = "posts_generated"
    POSTS_APPROVED = "posts_approved"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PostStatus(str, enum.Enum):
    GENERATED = "generated"
    EDITED = "edited"
    READY_FOR_FINAL_REVIEW = "ready_for_final_review"
    APPROVED_FINAL = "approved_final"
    SCHEDULED = "scheduled"
    PAUSED = "paused"
    CANCELED = "canceled"


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(CHAR(36), ForeignKey("clients.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    language = Column(String(10), default="es", nullable=False)  # es or en
    status = Column(Enum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False)
    ai_plan = Column(JSON)  # legacy / optional
    approved_at = Column(DateTime(timezone=True), nullable=True)  # set when plan approved
    created_by = Column(CHAR(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    client = relationship("Client", back_populates="campaigns")
    monthly_plans = relationship(
        "MonthlyPlan", back_populates="campaign", cascade="all, delete-orphan"
    )
    publication_windows = relationship(
        "PublicationWindow",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class MonthlyPlan(Base):
    """One plan per campaign (4 weeks). Stores generation config and scheduling settings."""

    __tablename__ = "monthly_plans"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(CHAR(36), ForeignKey("campaigns.id"), nullable=False, index=True)
    generation_config = Column(JSON, nullable=True)  # config used to generate this plan
    total_posts = Column(Integer, nullable=True)
    min_posts_per_week = Column(Integer, default=3, nullable=False)
    max_posts_per_week = Column(Integer, default=5, nullable=False)
    distribution_json = Column(JSON, nullable=True)  # e.g. [3, 3, 3, 3] for weeks 1-4
    scheduling_mode = Column(
        Enum(SchedulingMode), default=SchedulingMode.MANUAL, nullable=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    campaign = relationship("Campaign", back_populates="monthly_plans")
    posts = relationship(
        "Post", back_populates="monthly_plan", cascade="all, delete-orphan"
    )


class PublicationWindow(Base):
    """Allowed time windows per campaign and platform for scheduling posts."""

    __tablename__ = "publication_windows"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(CHAR(36), ForeignKey("campaigns.id"), nullable=False, index=True)
    # Store platform as plain string to avoid ENUM lookup issues between DB and SQLAlchemy
    platform = Column(String(50), nullable=False)
    # Store day_of_week as plain string (e.g. "monday") to avoid ENUM mismatches with existing data
    day_of_week = Column(String(50), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    priority = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    campaign = relationship("Campaign", back_populates="publication_windows")
    posts_scheduled = relationship(
        "Post",
        back_populates="scheduling_window",
        foreign_keys="Post.scheduling_window_id",
    )


class Post(Base):
    __tablename__ = "posts"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False, index=True)
    campaign_id = Column(
        CHAR(36), ForeignKey("campaigns.id"), nullable=True, index=True
    )
    monthly_plan_id = Column(
        CHAR(36), ForeignKey("monthly_plans.id"), nullable=False, index=True
    )
    week_number = Column(Integer, nullable=False)  # 1-4
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)
    hashtags = Column(String(500), nullable=True)
    link = Column(String(2048), nullable=True)
    status = Column(Enum(PostStatus), default=PostStatus.GENERATED, nullable=False)
    # Store platform as plain string to avoid ENUM lookup mismatch; use PostPlatform for validation in code
    platform = Column(String(50), nullable=True)  # linkedin | instagram
    content_objective = Column(String(50), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    scheduled_date = Column(Date, nullable=True)
    scheduled_time = Column(Time, nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    scheduling_window_id = Column(
        CHAR(36), ForeignKey("publication_windows.id"), nullable=True, index=True
    )
    published_at = Column(DateTime(timezone=True))
    published_post_id = Column(String(255))
    extra_data = Column("metadata", JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    monthly_plan = relationship("MonthlyPlan", back_populates="posts")
    scheduling_window = relationship(
        "PublicationWindow", back_populates="posts_scheduled", foreign_keys=[scheduling_window_id]
    )


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False, index=True)
    campaign_id = Column(CHAR(36), ForeignKey("campaigns.id"), nullable=False, index=True)
    post_id = Column(CHAR(36), ForeignKey("posts.id"), nullable=True)
    approval_type = Column(String(50), nullable=False)
    approved_by = Column(CHAR(36), ForeignKey("users.id"), nullable=False)
    approved = Column(Boolean, nullable=False)
    comments = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SchedulingLog(Base):
    """Audit log for when and why posts were scheduled (e.g. auto_windowed)."""

    __tablename__ = "scheduling_logs"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(CHAR(36), ForeignKey("campaigns.id"), nullable=False, index=True)
    post_id = Column(CHAR(36), ForeignKey("posts.id"), nullable=False, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    window_id = Column(
        CHAR(36), ForeignKey("publication_windows.id"), nullable=True, index=True
    )
    scheduling_reason = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
