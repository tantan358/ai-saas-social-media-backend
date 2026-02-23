from sqlalchemy.orm import Session
from app.modules.campaigns.models import Campaign, Post, Approval, CampaignStatus, PostStatus
from app.modules.campaigns.schemas import CampaignCreate, CampaignUpdate, PostCreate, PostUpdate, ApprovalCreate
from app.modules.ai.service import AIService
from fastapi import HTTPException, status
from typing import List, Optional


class CampaignService:
    @staticmethod
    def create_campaign(
        db: Session,
        campaign_data: CampaignCreate,
        tenant_id: str,
        user_id: str
    ) -> Campaign:
        """Create a new campaign"""
        campaign = Campaign(
            name=campaign_data.name,
            description=campaign_data.description,
            language=campaign_data.language,
            tenant_id=tenant_id,
            created_by=user_id,
            status=CampaignStatus.DRAFT
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign
    
    @staticmethod
    def get_campaigns(
        db: Session,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Campaign]:
        """Get all campaigns for a tenant"""
        return db.query(Campaign).filter(
            Campaign.tenant_id == tenant_id
        ).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_campaign(db: Session, campaign_id: str, tenant_id: str) -> Campaign:
        """Get a specific campaign"""
        campaign = db.query(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.tenant_id == tenant_id
        ).first()
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        return campaign
    
    @staticmethod
    def update_campaign(
        db: Session,
        campaign_id: str,
        tenant_id: str,
        campaign_data: CampaignUpdate
    ) -> Campaign:
        """Update a campaign"""
        campaign = CampaignService.get_campaign(db, campaign_id, tenant_id)
        
        update_data = campaign_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(campaign, field, value)
        
        db.commit()
        db.refresh(campaign)
        return campaign
    
    @staticmethod
    def generate_ai_plan(
        db: Session,
        campaign_id: int,
        tenant_id: int
    ) -> Campaign:
        """Generate AI plan for campaign"""
        campaign = CampaignService.get_campaign(db, campaign_id, tenant_id)
        
        if campaign.status != CampaignStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign must be in draft status to generate AI plan"
            )
        
        # Generate AI plan
        ai_plan = AIService.generate_campaign_plan(
            campaign_name=campaign.name,
            description=campaign.description,
            language=campaign.language
        )
        
        campaign.ai_plan = ai_plan
        campaign.status = CampaignStatus.AI_PLAN_CREATED
        db.commit()
        db.refresh(campaign)
        return campaign
    
    @staticmethod
    def approve_plan(
        db: Session,
        campaign_id: int,
        tenant_id: int,
        user_id: int,
        approved: bool,
        comments: Optional[str] = None
    ) -> Approval:
        """Approve or reject AI plan"""
        campaign = CampaignService.get_campaign(db, campaign_id, tenant_id)
        
        if campaign.status != CampaignStatus.AI_PLAN_CREATED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign must have AI plan created"
            )
        
        approval = Approval(
            tenant_id=tenant_id,
            campaign_id=campaign_id,
            approval_type="plan_approval",
            approved_by=user_id,
            approved=approved,
            comments=comments
        )
        db.add(approval)
        
        if approved:
            campaign.status = CampaignStatus.PLAN_APPROVED
        else:
            campaign.status = CampaignStatus.DRAFT
        
        db.commit()
        db.refresh(approval)
        return approval
    
    @staticmethod
    def generate_posts(
        db: Session,
        campaign_id: int,
        tenant_id: int
    ) -> List[Post]:
        """Generate posts from approved plan"""
        campaign = CampaignService.get_campaign(db, campaign_id, tenant_id)
        
        if campaign.status != CampaignStatus.PLAN_APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign plan must be approved first"
            )
        
        if not campaign.ai_plan:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign must have an AI plan"
            )
        
        # Generate posts using AI
        generated_posts = AIService.generate_posts(
            campaign_plan=campaign.ai_plan,
            language=campaign.language
        )
        
        # Create post records
        posts = []
        for post_data in generated_posts:
            post = Post(
                tenant_id=tenant_id,
                campaign_id=campaign_id,
                content=post_data.get("content", ""),
                platform=post_data.get("platform"),
                status=PostStatus.PENDING_APPROVAL,
                metadata=post_data.get("metadata")
            )
            db.add(post)
            posts.append(post)
        
        campaign.status = CampaignStatus.POSTS_GENERATED
        db.commit()
        
        for post in posts:
            db.refresh(post)
        
        return posts
    
    @staticmethod
    def approve_post(
        db: Session,
        post_id: int,
        tenant_id: int,
        user_id: int,
        approved: bool,
        comments: Optional[str] = None
    ) -> Approval:
        """Approve or reject a post"""
        post = db.query(Post).filter(
            Post.id == post_id,
            Post.tenant_id == tenant_id
        ).first()
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found"
            )
        
        approval = Approval(
            tenant_id=tenant_id,
            campaign_id=post.campaign_id,
            post_id=post_id,
            approval_type="post_approval",
            approved_by=user_id,
            approved=approved,
            comments=comments
        )
        db.add(approval)
        
        if approved:
            post.status = PostStatus.APPROVED
        else:
            post.status = PostStatus.DRAFT
        
        db.commit()
        db.refresh(approval)
        return approval
    
    @staticmethod
    def get_posts(
        db: Session,
        campaign_id: int,
        tenant_id: int
    ) -> List[Post]:
        """Get all posts for a campaign"""
        return db.query(Post).filter(
            Post.campaign_id == campaign_id,
            Post.tenant_id == tenant_id
        ).all()
