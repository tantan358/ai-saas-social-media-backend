from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.modules.campaigns.schemas import (
    CampaignCreate, CampaignUpdate, CampaignResponse,
    PostResponse, ApprovalCreate, ApprovalResponse
)
from app.modules.campaigns.service import CampaignService
from app.dependencies import get_current_user, get_current_tenant
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    campaign_data: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Create a new campaign"""
    return CampaignService.create_campaign(
        db, campaign_data, current_tenant.id, current_user.id
    )


@router.get("", response_model=List[CampaignResponse])
def get_campaigns(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Get all campaigns for current tenant"""
    return CampaignService.get_campaigns(db, current_tenant.id, skip, limit)


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Get a specific campaign"""
    return CampaignService.get_campaign(db, campaign_id, current_tenant.id)


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: str,
    campaign_data: CampaignUpdate,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Update a campaign"""
    return CampaignService.update_campaign(
        db, campaign_id, current_tenant.id, campaign_data
    )


@router.post("/{campaign_id}/generate-plan", response_model=CampaignResponse)
def generate_ai_plan(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Generate AI plan for campaign"""
    return CampaignService.generate_ai_plan(db, campaign_id, current_tenant.id)


@router.post("/{campaign_id}/approve-plan", response_model=ApprovalResponse)
def approve_plan(
    campaign_id: int,
    approved: bool,
    comments: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Approve or reject AI plan"""
    return CampaignService.approve_plan(
        db, campaign_id, current_tenant.id, current_user.id, approved, comments
    )


@router.post("/{campaign_id}/generate-posts", response_model=List[PostResponse])
def generate_posts(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Generate posts from approved plan"""
    return CampaignService.generate_posts(db, campaign_id, current_tenant.id)


@router.get("/{campaign_id}/posts", response_model=List[PostResponse])
def get_posts(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Get all posts for a campaign"""
    return CampaignService.get_posts(db, campaign_id, current_tenant.id)


@router.post("/posts/{post_id}/approve", response_model=ApprovalResponse)
def approve_post(
    post_id: int,
    approved: bool,
    comments: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Approve or reject a post"""
    return CampaignService.approve_post(
        db, post_id, current_tenant.id, current_user.id, approved, comments
    )
