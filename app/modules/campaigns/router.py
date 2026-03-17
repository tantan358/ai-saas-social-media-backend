from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.modules.campaigns.schemas import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignDetailResponse,
    PostResponse,
    GetPlanResponse,
    GeneratePlanRequest,
    GeneratePlanResponse,
    ScheduleCampaignRequest,
    ScheduleCampaignResponse,
    ScheduleAutoResponse,
    ScheduleByWeekResponse,
    ScheduleByDateResponse,
    ScheduleItemResponse,
    PublicationWindowCreate,
    PublicationWindowBulkCreate,
    PublicationWindowResponse,
    CampaignCalendarResponse,
    CalendarByWeek,
    CalendarByDate,
    CalendarPostItem,
)
from app.modules.campaigns.service import CampaignService
from app.dependencies import get_current_user, get_current_agency_id
from app.modules.auth.models import User

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    campaign_data: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    agency_id: str = Depends(get_current_agency_id),
):
    """Create a new campaign for a client."""
    return CampaignService.create_campaign(
        db, campaign_data, agency_id, current_user.id
    )


@router.get("", response_model=List[CampaignResponse])
def get_campaigns(
    client_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Get campaigns for the current agency, optionally filtered by client."""
    return CampaignService.get_campaigns(db, agency_id, client_id=client_id, skip=skip, limit=limit)


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Get a campaign with agency and client names."""
    campaign, agency_name, client_name = CampaignService.get_campaign_with_names(
        db, campaign_id, agency_id
    )
    return CampaignDetailResponse(
        **CampaignResponse.model_validate(campaign).model_dump(),
        agency_name=agency_name,
        client_name=client_name,
    )


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: str,
    campaign_data: CampaignUpdate,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Update a campaign."""
    return CampaignService.update_campaign(db, campaign_id, agency_id, campaign_data)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Delete a campaign and its plans/posts. Returns 204 on success."""
    CampaignService.delete_campaign(db, campaign_id, agency_id)
    return None


@router.get("/{campaign_id}/plan", response_model=GetPlanResponse)
def get_plan(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Get the monthly plan for a campaign (plan is null if none exists yet)."""
    return CampaignService.get_plan(db, campaign_id, agency_id)


@router.post("/{campaign_id}/generate-plan", response_model=GeneratePlanResponse)
def generate_plan(
    campaign_id: str,
    body: Optional[GeneratePlanRequest] = Body(None),
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Generate or regenerate AI monthly plan (4 weeks, configurable posts per week/channels). Optional body for generation options."""
    return CampaignService.generate_plan(db, campaign_id, agency_id, body)


@router.post("/{campaign_id}/approve-plan", response_model=CampaignResponse)
def approve_plan(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Approve the monthly plan; all posts marked approved and editing locked. If plan uses auto_windowed scheduling, posts are assigned datetimes and campaign is marked scheduled."""
    return CampaignService.approve_plan(db, campaign_id, agency_id)


@router.post("/{campaign_id}/schedule", response_model=ScheduleCampaignResponse)
def schedule_campaign(
    campaign_id: str,
    body: Optional[ScheduleCampaignRequest] = Body(None),
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Assign scheduled_date, scheduled_time, scheduled_at to approved posts using publication windows; set status to scheduled. Use after approval (or for manual scheduling)."""
    plan_start_date = body.plan_start_date if body else None
    result = CampaignService.schedule_campaign(db, campaign_id, agency_id, plan_start_date)
    return ScheduleCampaignResponse(
        campaign_id=result["campaign_id"],
        assigned_count=result["assigned_count"],
        plan_start_date=result.get("plan_start_date"),
        schedule_by_week=result.get("schedule_by_week", {}),
    )


@router.post("/{campaign_id}/schedule-auto", response_model=ScheduleAutoResponse)
def schedule_auto_campaign(
    campaign_id: str,
    body: Optional[ScheduleCampaignRequest] = Body(None),
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Auto-schedule approved_final posts using publication windows and balanced distribution. Returns schedule grouped by week and by date."""
    plan_start_date = body.plan_start_date if body else None
    result = CampaignService.schedule_auto_campaign(db, campaign_id, agency_id, plan_start_date)
    by_week = [
        ScheduleByWeekResponse(
            week=x["week"],
            by_date=[ScheduleByDateResponse(date=bd["date"], posts=[ScheduleItemResponse(**p) for p in bd["posts"]]) for bd in x["by_date"]],
        )
        for x in result.get("by_week", [])
    ]
    by_date = [
        ScheduleByDateResponse(date=bd["date"], posts=[ScheduleItemResponse(**p) for p in bd["posts"]])
        for bd in result.get("by_date", [])
    ]
    return ScheduleAutoResponse(
        campaign_id=result["campaign_id"],
        assigned_count=result["assigned_count"],
        plan_start_date=result.get("plan_start_date"),
        by_week=by_week,
        by_date=by_date,
    )


@router.get("/{campaign_id}/schedule-auto-debug")
def schedule_auto_campaign_debug(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """
    Debug endpoint: run auto-scheduling for a campaign and return detailed diagnostics
    without relying on the frontend UI.
    """
    return CampaignService.schedule_auto_campaign_debug(db, campaign_id, agency_id, None)


@router.get("/{campaign_id}/calendar", response_model=CampaignCalendarResponse)
def get_campaign_calendar(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Get campaign calendar: posts grouped by week and by date; includes platform, title, status, client, campaign."""
    data = CampaignService.get_campaign_calendar(db, campaign_id, agency_id)
    by_week = [
        CalendarByWeek(
            week=x["week"],
            by_date=[CalendarByDate(date=bd["date"], posts=[CalendarPostItem(**p) for p in bd["posts"]]) for bd in x["by_date"]],
        )
        for x in data["by_week"]
    ]
    by_date = [
        CalendarByDate(date=bd["date"], posts=[CalendarPostItem(**p) for p in bd["posts"]])
        for bd in data["by_date"]
    ]
    return CampaignCalendarResponse(
        campaign_id=data["campaign_id"],
        campaign_name=data.get("campaign_name"),
        client_name=data.get("client_name"),
        by_week=by_week,
        by_date=by_date,
    )


@router.get("/{campaign_id}/publication-windows", response_model=List[PublicationWindowResponse])
def get_publication_windows(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """List publication windows for this campaign."""
    windows = CampaignService.get_publication_windows(db, campaign_id, agency_id)
    return [
        PublicationWindowResponse(
            id=w.id,
            campaign_id=w.campaign_id,
            platform=w.platform.value if hasattr(w.platform, "value") else str(w.platform),
            day_of_week=w.day_of_week.value if hasattr(w.day_of_week, "value") else str(w.day_of_week),
            start_time=w.start_time,
            end_time=w.end_time,
            priority=w.priority,
            is_active=w.is_active,
            created_at=w.created_at,
        )
        for w in windows
    ]


@router.post("/{campaign_id}/publication-windows", response_model=List[PublicationWindowResponse], status_code=status.HTTP_201_CREATED)
def save_publication_windows(
    campaign_id: str,
    body: PublicationWindowBulkCreate,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Save custom publication windows for this campaign (replaces existing)."""
    created = CampaignService.save_publication_windows(db, campaign_id, agency_id, body.windows)
    return [
        PublicationWindowResponse(
            id=w.id,
            campaign_id=w.campaign_id,
            platform=w.platform.value if hasattr(w.platform, "value") else str(w.platform),
            day_of_week=w.day_of_week.value if hasattr(w.day_of_week, "value") else str(w.day_of_week),
            start_time=w.start_time,
            end_time=w.end_time,
            priority=w.priority,
            is_active=w.is_active,
            created_at=w.created_at,
        )
        for w in created
    ]


@router.post("/{campaign_id}/reset-plan", response_model=CampaignResponse)
def reset_plan(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Remove the current planning and generated posts; campaign returns to draft so user can generate again."""
    return CampaignService.reset_plan(db, campaign_id, agency_id)


@router.get("/{campaign_id}/posts", response_model=List[PostResponse])
def get_campaign_posts(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Get all posts for a campaign (grouped by week in service)."""
    posts = CampaignService.get_posts_by_campaign(db, campaign_id, agency_id)
    return [PostResponse.model_validate(p) for p in posts]


# Legacy endpoints (optional): generate-posts, approve-post - can be removed or kept for backward compat
