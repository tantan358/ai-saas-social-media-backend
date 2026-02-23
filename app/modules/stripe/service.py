from sqlalchemy.orm import Session
from app.modules.stripe.models import Subscription, SubscriptionStatus
from app.config import settings
import stripe
from typing import Optional
from datetime import datetime

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    @staticmethod
    def create_checkout_session(
        tenant_id: int,
        plan_id: str,
        success_url: str,
        cancel_url: str
    ) -> dict:
        """Create Stripe checkout session"""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price": plan_id,
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "tenant_id": str(tenant_id)
                }
            )
            return {
                "session_id": session.id,
                "url": session.url
            }
        except Exception as e:
            raise Exception(f"Failed to create checkout session: {str(e)}")
    
    @staticmethod
    def handle_webhook(event: dict, db: Session) -> None:
        """Handle Stripe webhook events"""
        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})
        
        if event_type == "checkout.session.completed":
            # Subscription created
            tenant_id = int(data.get("metadata", {}).get("tenant_id", 0))
            customer_id = data.get("customer")
            subscription_id = data.get("subscription")
            
            if tenant_id and subscription_id:
                StripeService.create_or_update_subscription(
                    db, tenant_id, subscription_id, customer_id
                )
        
        elif event_type == "customer.subscription.updated":
            # Subscription updated
            subscription_id = data.get("id")
            customer_id = data.get("customer")
            status = data.get("status")
            
            subscription = db.query(Subscription).filter(
                Subscription.stripe_subscription_id == subscription_id
            ).first()
            
            if subscription:
                subscription.status = SubscriptionStatus(status)
                subscription.current_period_start = datetime.fromtimestamp(
                    data.get("current_period_start", 0)
                )
                subscription.current_period_end = datetime.fromtimestamp(
                    data.get("current_period_end", 0)
                )
                subscription.cancel_at_period_end = data.get("cancel_at_period_end", False)
                db.commit()
        
        elif event_type == "customer.subscription.deleted":
            # Subscription cancelled
            subscription_id = data.get("id")
            subscription = db.query(Subscription).filter(
                Subscription.stripe_subscription_id == subscription_id
            ).first()
            
            if subscription:
                subscription.status = SubscriptionStatus.CANCELLED
                db.commit()
    
    @staticmethod
    def create_or_update_subscription(
        db: Session,
        tenant_id: int,
        subscription_id: str,
        customer_id: str
    ) -> Subscription:
        """Create or update subscription from Stripe"""
        subscription = db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id
        ).first()
        
        # Get subscription details from Stripe
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        
        if subscription:
            subscription.stripe_subscription_id = subscription_id
            subscription.stripe_customer_id = customer_id
            subscription.status = SubscriptionStatus(stripe_sub.status)
            subscription.plan_name = stripe_sub.items.data[0].price.nickname or "Basic"
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_sub.current_period_start
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_sub.current_period_end
            )
        else:
            subscription = Subscription(
                tenant_id=tenant_id,
                stripe_subscription_id=subscription_id,
                stripe_customer_id=customer_id,
                status=SubscriptionStatus(stripe_sub.status),
                plan_name=stripe_sub.items.data[0].price.nickname or "Basic",
                current_period_start=datetime.fromtimestamp(stripe_sub.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_sub.current_period_end)
            )
            db.add(subscription)
        
        db.commit()
        db.refresh(subscription)
        return subscription
    
    @staticmethod
    def get_subscription(db: Session, tenant_id: int) -> Optional[Subscription]:
        """Get subscription for tenant"""
        return db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id
        ).first()
    
    @staticmethod
    def cancel_subscription(db: Session, tenant_id: int) -> Subscription:
        """Cancel subscription"""
        subscription = db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id
        ).first()
        
        if not subscription:
            raise Exception("Subscription not found")
        
        if subscription.stripe_subscription_id:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            subscription.cancel_at_period_end = True
            db.commit()
            db.refresh(subscription)
        
        return subscription
