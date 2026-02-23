from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import CHAR
import enum
import uuid
from app.database import Base


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    AI_PLAN_CREATED = "ai_plan_created"
    PLAN_APPROVED = "plan_approved"
    POSTS_GENERATED = "posts_generated"
    POSTS_APPROVED = "posts_approved"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Campaign(Base):
    __tablename__ = "campaigns"
    
    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    language = Column(String(10), default="es", nullable=False)  # es or en
    status = Column(Enum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False)
    ai_plan = Column(JSON)  # Store AI-generated plan
    created_by = Column(CHAR(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    posts = relationship("Post", back_populates="campaign", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"
    
    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False, index=True)
    campaign_id = Column(CHAR(36), ForeignKey("campaigns.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    status = Column(Enum(PostStatus), default=PostStatus.DRAFT, nullable=False)
    platform = Column(String(50))  # linkedin, instagram
    scheduled_at = Column(DateTime(timezone=True))
    published_at = Column(DateTime(timezone=True))
    published_post_id = Column(String(255))  # ID from social platform
    extra_data = Column("metadata", JSON)  # Additional platform-specific data (mapped to 'metadata' column in DB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    campaign = relationship("Campaign", back_populates="posts")


class Approval(Base):
    __tablename__ = "approvals"
    
    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False, index=True)
    campaign_id = Column(CHAR(36), ForeignKey("campaigns.id"), nullable=False, index=True)
    post_id = Column(CHAR(36), ForeignKey("posts.id"), nullable=True)  # null for plan approval
    approval_type = Column(String(50), nullable=False)  # plan_approval, post_approval
    approved_by = Column(CHAR(36), ForeignKey("users.id"), nullable=False)
    approved = Column(Boolean, nullable=False)
    comments = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
