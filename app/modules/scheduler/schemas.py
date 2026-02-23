from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.modules.scheduler.models import ScheduledPostStatus


class ScheduledPostBase(BaseModel):
    post_id: int
    social_account_id: int
    scheduled_at: datetime


class ScheduledPostCreate(ScheduledPostBase):
    pass


class ScheduledPostResponse(ScheduledPostBase):
    id: int
    status: ScheduledPostStatus
    published_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
