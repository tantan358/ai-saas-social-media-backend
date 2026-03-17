from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.modules.campaigns.schemas import PostUpdate, PostResponse, PostScheduleUpdate
from app.modules.campaigns.service import CampaignService
from app.dependencies import get_current_agency_id

router = APIRouter(prefix="/posts", tags=["posts"])


@router.put("/{post_id}", response_model=PostResponse)
def update_post(
    post_id: str,
    data: PostUpdate,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Update post title, content, hashtags, and/or link. Sets status to edited. Locked after plan approval."""
    return CampaignService.update_post(
        db,
        post_id,
        agency_id,
        title=data.title,
        content=data.content,
        hashtags=data.hashtags,
        link=data.link,
    )


@router.put("/{post_id}/schedule", response_model=PostResponse)
def schedule_post(
    post_id: str,
    data: PostScheduleUpdate,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Manual override: set scheduled_date, scheduled_time for one post. Only for approved_final or scheduled; cannot edit canceled. Creates scheduling audit log."""
    return CampaignService.schedule_post_manual(
        db,
        post_id,
        agency_id,
        scheduled_date=data.scheduled_date,
        scheduled_time=data.scheduled_time,
        scheduling_note=data.scheduling_note,
    )
