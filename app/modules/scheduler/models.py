from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import CHAR
import enum
import uuid
from app.database import Base


class ScheduledPostStatus(str, enum.Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    FAILED = "failed"


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    
    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False, index=True)
    post_id = Column(CHAR(36), ForeignKey("posts.id"), nullable=False, index=True)
    social_account_id = Column(CHAR(36), ForeignKey("social_accounts.id"), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(Enum(ScheduledPostStatus), default=ScheduledPostStatus.PENDING, nullable=False)
    published_at = Column(DateTime(timezone=True))
    error_message = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships will be resolved via string references to avoid circular imports

    # Relationships will be resolved via string references to avoid circular imports

    # Relationships will be resolved via string references to avoid circular imports
