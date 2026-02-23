from pydantic import BaseModel, Field
from datetime import datetime


class TenantBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)


class TenantCreate(TenantBase):
    pass


class TenantResponse(TenantBase):
    id: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
