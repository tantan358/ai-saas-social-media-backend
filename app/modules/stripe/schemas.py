from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.modules.stripe.models import SubscriptionStatus


class SubscriptionResponse(BaseModel):
    id: int
    tenant_id: int
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    status: SubscriptionStatus
    plan_name: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class CreateCheckoutSessionRequest(BaseModel):
    plan_id: str  # Stripe price ID
    success_url: str
    cancel_url: str
