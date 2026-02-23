from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.modules.scheduler.schemas import ScheduledPostCreate, ScheduledPostResponse
from app.modules.scheduler.service import SchedulerService
from app.modules.scheduler.models import ScheduledPostStatus
from app.dependencies import get_current_tenant
from app.modules.tenants.models import Tenant

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.post("", response_model=ScheduledPostResponse, status_code=status.HTTP_201_CREATED)
def schedule_post(
    schedule_data: ScheduledPostCreate,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Schedule a post for future publishing"""
    return SchedulerService.schedule_post(db, schedule_data, current_tenant.id)


@router.get("", response_model=List[ScheduledPostResponse])
def get_scheduled_posts(
    status: Optional[ScheduledPostStatus] = Query(None),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Get scheduled posts for current tenant"""
    return SchedulerService.get_scheduled_posts(db, current_tenant.id, status)


@router.post("/{scheduled_post_id}/pause", response_model=ScheduledPostResponse)
def pause_scheduled_post(
    scheduled_post_id: int,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Pause a scheduled post"""
    return SchedulerService.pause_scheduled_post(db, scheduled_post_id, current_tenant.id)


@router.post("/{scheduled_post_id}/cancel", response_model=ScheduledPostResponse)
def cancel_scheduled_post(
    scheduled_post_id: int,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Cancel a scheduled post"""
    return SchedulerService.cancel_scheduled_post(db, scheduled_post_id, current_tenant.id)
