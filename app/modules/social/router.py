from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.modules.social.schemas import SocialAccountCreate, SocialAccountResponse, PostPublishRequest
from app.modules.social.service import SocialService
from app.modules.campaigns.schemas import PostResponse
from app.dependencies import get_current_tenant
from app.modules.tenants.models import Tenant

router = APIRouter(prefix="/social", tags=["social"])


@router.post("/accounts", response_model=SocialAccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    account_data: SocialAccountCreate,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Connect a social media account"""
    return SocialService.create_account(db, account_data, current_tenant.id)


@router.get("/accounts", response_model=List[SocialAccountResponse])
def get_accounts(
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Get all social accounts for current tenant"""
    return SocialService.get_accounts(db, current_tenant.id)


@router.post("/publish", response_model=PostResponse)
def publish_post(
    request: PostPublishRequest,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Publish a post to social media"""
    return SocialService.publish_post(
        db, request.post_id, request.social_account_id, current_tenant.id
    )
