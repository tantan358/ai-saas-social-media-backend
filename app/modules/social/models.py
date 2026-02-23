from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Enum, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import CHAR
import enum
import uuid
from app.database import Base


class PlatformType(str, enum.Enum):
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    
    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False, index=True)
    platform = Column(Enum(PlatformType), nullable=False)
    account_name = Column(String(255), nullable=False)
    account_id = Column(String(255))  # Platform-specific account ID
    access_token = Column(Text)  # Encrypted in production
    refresh_token = Column(Text)  # Encrypted in production
    token_expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True, nullable=False)
    extra_data = Column("metadata", JSON)  # Additional platform-specific data (mapped to 'metadata' column in DB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
