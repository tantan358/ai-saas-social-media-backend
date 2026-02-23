from fastapi import APIRouter, Depends, Request, status, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.modules.stripe.schemas import SubscriptionResponse, CreateCheckoutSessionRequest
from app.modules.stripe.service import StripeService
from app.config import settings
from app.dependencies import get_current_tenant
from app.modules.tenants.models import Tenant
import stripe
import json

router = APIRouter(prefix="/stripe", tags=["stripe"])


@router.post("/create-checkout-session")
def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Create Stripe checkout session"""
    return StripeService.create_checkout_session(
        current_tenant.id,
        request.plan_id,
        request.success_url,
        request.cancel_url
    )


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription(
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Get current tenant's subscription"""
    subscription = StripeService.get_subscription(db, current_tenant.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found"
        )
    return subscription


@router.post("/cancel-subscription", response_model=SubscriptionResponse)
def cancel_subscription(
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Cancel subscription"""
    return StripeService.cancel_subscription(db, current_tenant.id)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    StripeService.handle_webhook(event, db)
    
    return {"status": "success"}
