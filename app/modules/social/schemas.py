from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from app.modules.social.models import PlatformType


class SocialAccountBase(BaseModel):
    platform: PlatformType
    account_name: str = Field(..., min_length=1, max_length=255)


class SocialAccountCreate(SocialAccountBase):
    access_token: str
    refresh_token: Optional[str] = None
    account_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SocialAccountResponse(SocialAccountBase):
    id: int
    account_id: Optional[str] = None
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class PostPublishRequest(BaseModel):
    post_id: int
    social_account_id: int
