from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.modules.campaigns.models import CampaignStatus, PostStatus


class CampaignBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    language: str = Field(default="es", pattern="^(es|en)$")


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[CampaignStatus] = None


class CampaignResponse(CampaignBase):
    id: str
    status: CampaignStatus
    ai_plan: Optional[Dict[str, Any]] = None
    created_by: str
    tenant_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class PostBase(BaseModel):
    content: str = Field(..., min_length=1)
    platform: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class PostCreate(PostBase):
    campaign_id: int


class PostUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1)
    status: Optional[PostStatus] = None
    scheduled_at: Optional[datetime] = None


class PostResponse(PostBase):
    id: int
    campaign_id: int
    status: PostStatus
    published_at: Optional[datetime] = None
    published_post_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ApprovalCreate(BaseModel):
    campaign_id: int
    post_id: Optional[int] = None
    approval_type: str = Field(..., pattern="^(plan_approval|post_approval)$")
    approved: bool
    comments: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: int
    campaign_id: int
    post_id: Optional[int] = None
    approval_type: str
    approved: bool
    comments: Optional[str] = None
    approved_by: int
    created_at: datetime
    
    class Config:
        from_attributes = True
