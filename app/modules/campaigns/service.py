from sqlalchemy.orm import Session
from app.modules.campaigns.models import (
    Campaign,
    Post,
    MonthlyPlan,
    CampaignStatus,
    PostStatus,
    PostPlatform,
    SchedulingMode,
)

# Campaign statuses that allow AI monthly plan generation or regeneration (before approval/schedule/publish).
ALLOWED_PLAN_GENERATION_STATUSES = frozenset({
    CampaignStatus.DRAFT,
    CampaignStatus.PLANNING_GENERATED,
    CampaignStatus.PLANNING_EDITING,
})

# Campaign statuses that block "Reset Planning" (scheduled/published or later).
RESET_PLAN_BLOCKED_STATUSES = frozenset({
    CampaignStatus.SCHEDULED,
    CampaignStatus.PUBLISHING,
    CampaignStatus.COMPLETED,
    CampaignStatus.CANCELLED,
})
from app.modules.campaigns.schemas import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    MonthlyPlanResponse,
    MonthlyPlanPost,
    GeneratePlanRequest,
    GeneratePlanResponse,
    GenerationOptions,
    resolve_generation_options,
)
from app.modules.ai.service import AIService, validate_content_language
from app.modules.planning.services.distribution_service import distribute_posts_across_weeks
from app.modules.campaigns.constants import (
    MIN_POSTS_PER_WEEK_DEFAULT,
    MAX_POSTS_PER_WEEK_DEFAULT,
)
from app.modules.scheduling.services.window_scheduler import assign_dates_and_times_for_campaign
from app.modules.clients.models import Client
from app.modules.agencies.models import Agency
from fastapi import HTTPException, status
from typing import List, Optional, Any
from datetime import datetime, timezone, date, time


def _ensure_client_in_agency(db: Session, client_id: str, agency_id: str) -> Client:
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.agency_id == agency_id,
    ).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found or does not belong to your agency",
        )
    return client


class CampaignService:
    @staticmethod
    def get_plan(
        db: Session,
        campaign_id: str,
        agency_id: str,
    ) -> "GetPlanResponse":
        """
        Return the existing monthly plan (if any) for a campaign.
        If no plan exists yet, returns plan=null to match frontend's GetPlanResponse.
        """
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        # Assume at most one monthly plan per campaign.
        plan = (
            db.query(MonthlyPlan)
            .filter(MonthlyPlan.campaign_id == campaign.id)
            .first()
        )
        if not plan:
            from app.modules.campaigns.schemas import GetPlanResponse  # local import to avoid cycle

            return GetPlanResponse(plan=None)

        posts = sorted(plan.posts, key=lambda p: (p.week_number, p.id))
        from app.modules.campaigns.schemas import MonthlyPlanPost, MonthlyPlanResponse, GetPlanResponse  # local import

        plan_schema = MonthlyPlanResponse(
            id=plan.id,
            campaign_id=plan.campaign_id,
            posts=[
                MonthlyPlanPost(
                    id=p.id,
                    week_number=p.week_number,
                    title=p.title,
                    content=p.content,
                    platform=p.platform.value if p.platform else None,
                    status=p.status,
                    hashtags=getattr(p, "hashtags", None),
                    link=getattr(p, "link", None),
                    content_objective=getattr(p, "content_objective", None),
                )
                for p in posts
            ],
            created_at=plan.created_at,
            updated_at=plan.updated_at,
            generation_config=plan.generation_config,
            total_posts=plan.total_posts,
            distribution_json=plan.distribution_json,
        )
        return GetPlanResponse(plan=plan_schema)

    @staticmethod
    def create_campaign(
        db: Session,
        campaign_data: CampaignCreate,
        agency_id: str,
        user_id: str,
    ) -> Campaign:
        client = _ensure_client_in_agency(db, campaign_data.client_id, agency_id)
        # Get tenant_id from client's agency
        tenant_id = client.agency.tenant_id
        campaign = Campaign(
            tenant_id=tenant_id,
            name=campaign_data.name,
            description=campaign_data.description,
            language=campaign_data.language,
            client_id=campaign_data.client_id,
            created_by=user_id,
            status=CampaignStatus.DRAFT,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign

    @staticmethod
    def get_campaigns(
        db: Session,
        agency_id: str,
        client_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Campaign]:
        q = db.query(Campaign).join(Client).filter(Client.agency_id == agency_id)
        if client_id:
            q = q.filter(Campaign.client_id == client_id)
        return q.offset(skip).limit(limit).all()

    @staticmethod
    def get_campaign(
        db: Session,
        campaign_id: str,
        agency_id: str,
        with_names: bool = False,
    ) -> Campaign:
        campaign = (
            db.query(Campaign)
            .join(Client)
            .filter(
                Campaign.id == campaign_id,
                Client.agency_id == agency_id,
            )
            .first()
        )
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found",
            )
        return campaign

    @staticmethod
    def get_campaign_with_names(
        db: Session,
        campaign_id: str,
        agency_id: str,
    ) -> tuple[Campaign, str, str]:
        campaign = (
            db.query(Campaign, Agency.name.label("agency_name"), Client.name.label("client_name"))
            .join(Client, Campaign.client_id == Client.id)
            .join(Agency, Client.agency_id == Agency.id)
            .filter(Campaign.id == campaign_id, Client.agency_id == agency_id)
            .first()
        )
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found",
            )
        c, agency_name, client_name = campaign
        return c, agency_name or "", client_name or ""

    @staticmethod
    def update_campaign(
        db: Session,
        campaign_id: str,
        agency_id: str,
        campaign_data: CampaignUpdate,
    ) -> Campaign:
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        update_data = campaign_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(campaign, field, value)
        db.commit()
        db.refresh(campaign)
        return campaign

    @staticmethod
    def delete_campaign(db: Session, campaign_id: str, agency_id: str) -> None:
        """Delete a campaign and its related plans/posts (cascade). Fails if not found or wrong agency."""
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        db.delete(campaign)
        db.commit()

    @staticmethod
    def generate_plan(
        db: Session,
        campaign_id: str,
        agency_id: str,
        request: Optional[GeneratePlanRequest] = None,
    ) -> GeneratePlanResponse:
        """
        Generate or regenerate the AI monthly plan for a campaign.
        When the campaign already has a non-approved plan, it is fully replaced:
        existing MonthlyPlan(s) and their Post rows are deleted (cascade), then
        a new plan and posts are created. Only one active plan per campaign;
        GET plan and GET posts therefore return only the latest plan.
        Optional request body provides generation parameters; defaults used when omitted.
        Regeneration is blocked after approval (PLANNING_APPROVED and beyond); use reset_plan first.
        """
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        if campaign.status not in ALLOWED_PLAN_GENERATION_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approved planning cannot be regenerated directly. Reset or reopen planning first.",
            )
        options = resolve_generation_options(request, campaign.language)
        # Full replacement: delete existing plan(s) and their posts (cascade); old data is removed, not archived.
        for existing_plan in list(campaign.monthly_plans):
            db.delete(existing_plan)
        db.flush()
        try:
            raw_posts = AIService.generate_monthly_plan_posts(
                campaign_name=campaign.name,
                description=campaign.description or "",
                options=options,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        for p in raw_posts:
            validate_content_language(p.get("content", ""), options.language)

        total_posts = len(raw_posts)

        # When total_posts is an exact multiple of 4 weeks, prefer a perfectly even
        # weekly distribution (e.g. 24 -> [6, 6, 6, 6]). This matches per-channel
        # generation where we compute a fixed posts-per-week total up front
        # (sum of posts_per_channel_per_week) and expect every week to have the
        # same volume. For other totals (e.g. 13, 14, 15) we fall back to the
        # balanced distribution helper which spreads "extra" posts.
        if total_posts > 0 and total_posts % 4 == 0:
            per_week = total_posts // 4
            distribution = [per_week] * 4
        else:
            distribution = distribute_posts_across_weeks(
                total_posts,
                min_per_week=MIN_POSTS_PER_WEEK_DEFAULT,
                max_per_week=MAX_POSTS_PER_WEEK_DEFAULT,
            )
        # Build week_number for each post in order: first distribution[0] -> week 1, etc.
        week_assignments: List[int] = []
        for w in range(4):
            week_assignments.extend([w + 1] * distribution[w])

        # Store generation config for audit/debugging
        generation_config = options.model_dump()
        plan = MonthlyPlan(
            campaign_id=campaign.id,
            generation_config=generation_config,
            total_posts=total_posts,
            distribution_json=distribution,
        )
        db.add(plan)
        db.flush()
        # Resolve tenant_id for posts via campaign -> client -> agency.
        tenant_id = campaign.client.agency.tenant_id  # type: ignore[assignment]
        for i, p in enumerate(raw_posts):
            extra = {}
            if p.get("hashtags") is not None:
                extra["hashtags"] = p["hashtags"] if isinstance(p["hashtags"], list) else []
            if p.get("link") is not None and str(p.get("link", "")).strip():
                extra["link"] = str(p.get("link", "")).strip()
            if p.get("campaign_goal_tag") is not None:
                extra["campaign_goal_tag"] = str(p.get("campaign_goal_tag", ""))
            platform_raw = p.get("platform")
            platform = (
                PostPlatform(platform_raw.lower())
                if platform_raw and str(platform_raw).lower() in ("linkedin", "instagram")
                else None
            )
            week_number = week_assignments[i] if i < len(week_assignments) else 1
            post = Post(
                tenant_id=tenant_id,
                campaign_id=campaign.id,
                monthly_plan_id=plan.id,
                week_number=week_number,
                title=p.get("title"),
                content=p.get("content", ""),
                platform=platform,
                status=PostStatus.GENERATED,
                content_objective=p.get("content_objective"),
                extra_data=extra if extra else None,
            )
            db.add(post)
        campaign.status = CampaignStatus.PLANNING_GENERATED
        db.commit()
        db.refresh(campaign)
        db.refresh(plan)
        plan_posts = sorted(plan.posts, key=lambda p: (p.week_number, p.id))
        campaign_schema = CampaignResponse.model_validate(campaign)
        plan_schema = MonthlyPlanResponse(
            id=plan.id,
            campaign_id=plan.campaign_id,
            posts=[
                MonthlyPlanPost(
                    id=p.id,
                    week_number=p.week_number,
                    title=p.title,
                    content=p.content,
                    platform=p.platform.value if p.platform else None,
                    status=p.status,
                    hashtags=getattr(p, "hashtags", None),
                    link=getattr(p, "link", None),
                    content_objective=getattr(p, "content_objective", None),
                )
                for p in plan_posts
            ],
            created_at=plan.created_at,
            updated_at=plan.updated_at,
            generation_config=plan.generation_config,
            total_posts=plan.total_posts,
            distribution_json=plan.distribution_json,
        )
        # Backend currently always uses mock generator (see AIService.generate_monthly_plan_posts).
        return GeneratePlanResponse(
            campaign=campaign_schema,
            plan=plan_schema,
            generation_mode="mock",
        )

    @staticmethod
    def approve_plan(
        db: Session,
        campaign_id: str,
        agency_id: str,
    ) -> Campaign:
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        if campaign.status not in (
            CampaignStatus.PLANNING_GENERATED,
            CampaignStatus.PLANNING_EDITING,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign must have a generated plan to approve",
            )
        now = datetime.now(timezone.utc)
        campaign.status = CampaignStatus.PLANNING_APPROVED
        campaign.approved_at = now
        for plan in campaign.monthly_plans:
            for post in plan.posts:
                post.status = PostStatus.APPROVED_FINAL
                post.approved_at = now
        db.commit()
        db.refresh(campaign)

        # If any plan uses auto_windowed scheduling, assign dates/times and mark campaign as scheduled
        for plan in campaign.monthly_plans:
            if plan.scheduling_mode == SchedulingMode.AUTO_WINDOWED:
                try:
                    assign_dates_and_times_for_campaign(db, campaign_id, plan_start_date=None)
                    db.refresh(campaign)
                    campaign.status = CampaignStatus.SCHEDULED
                    db.commit()
                    db.refresh(campaign)
                except ValueError:
                    pass  # e.g. no posts to assign
                break
        return campaign

    @staticmethod
    def reset_plan(
        db: Session,
        campaign_id: str,
        agency_id: str,
    ) -> Campaign:
        """
        Remove the campaign's monthly plan and all generated posts; set status to DRAFT.
        Not allowed when campaign is scheduled, publishing, or completed.
        """
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        if campaign.status in RESET_PLAN_BLOCKED_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset planning is not allowed when the campaign is scheduled or published.",
            )
        for existing_plan in list(campaign.monthly_plans):
            db.delete(existing_plan)
        campaign.status = CampaignStatus.DRAFT
        campaign.approved_at = None
        db.flush()
        db.commit()
        db.refresh(campaign)
        return campaign

    @staticmethod
    def get_posts_by_campaign(
        db: Session,
        campaign_id: str,
        agency_id: str,
    ) -> List[Post]:
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        out = []
        for plan in campaign.monthly_plans:
            for post in plan.posts:
                out.append(post)
        return sorted(out, key=lambda p: (p.week_number, p.id))

    @staticmethod
    def update_post(
        db: Session,
        post_id: str,
        agency_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        hashtags: Optional[str] = None,
        link: Optional[str] = None,
    ) -> Post:
        post = (
            db.query(Post)
            .join(MonthlyPlan)
            .join(Campaign)
            .join(Client)
            .filter(
                Post.id == post_id,
                Client.agency_id == agency_id,
            )
            .first()
        )
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found",
            )
        campaign = post.monthly_plan.campaign
        if campaign.status == CampaignStatus.PLANNING_APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Editing is locked after plan approval",
            )
        if campaign.status == CampaignStatus.PLANNING_GENERATED:
            campaign.status = CampaignStatus.PLANNING_EDITING
        if title is not None:
            post.title = title
        if content is not None:
            post.content = content
        if hashtags is not None:
            post.hashtags = hashtags if hashtags.strip() else None
        if link is not None:
            post.link = link.strip() or None
        post.status = PostStatus.EDITED
        db.commit()
        db.refresh(post)
        return post

    @staticmethod
    def schedule_campaign(
        db: Session,
        campaign_id: str,
        agency_id: str,
        plan_start_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """
        Assign scheduled_date, scheduled_time, scheduled_at, and scheduling_window_id
        to all approved_final posts using publication windows; set post status to scheduled
        and campaign status to scheduled. Use after final approval (manual or auto).
        """
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        if campaign.status not in (
            CampaignStatus.PLANNING_APPROVED,
            CampaignStatus.SCHEDULED,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign must be approved before scheduling posts.",
            )
        try:
            result = assign_dates_and_times_for_campaign(
                db, campaign_id, plan_start_date=plan_start_date
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        if result["assigned_count"] > 0:
            db.refresh(campaign)
            campaign.status = CampaignStatus.SCHEDULED
            db.commit()
            db.refresh(campaign)
        return result

    @staticmethod
    def schedule_auto_campaign(
        db: Session,
        campaign_id: str,
        agency_id: str,
        plan_start_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """
        Auto-schedule only for campaigns with planning approved; only posts with
        status approved_final. Uses balanced distribution and publication windows.
        Returns schedule grouped by week and by date.
        """
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        if campaign.status not in (
            CampaignStatus.PLANNING_APPROVED,
            CampaignStatus.SCHEDULED,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign planning must be approved before auto-scheduling.",
            )
        try:
            result = assign_dates_and_times_for_campaign(
                db, campaign_id, plan_start_date=plan_start_date
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        if result["assigned_count"] > 0:
            db.refresh(campaign)
            campaign.status = CampaignStatus.SCHEDULED
            db.commit()
            db.refresh(campaign)

        # Build by_week (each week has by_date) and by_date (flat)
        schedule_by_week = result.get("schedule_by_week") or {}
        by_week_list: List[dict] = []
        all_by_date: dict[str, list] = {}
        for week_num in sorted(schedule_by_week.keys()):
            items = schedule_by_week[week_num]
            by_date_in_week: dict[str, list] = {}
            for item in items:
                d = item.get("scheduled_date") or (item.get("scheduled_at", "")[:10])
                if d:
                    by_date_in_week.setdefault(d, []).append(item)
                    all_by_date.setdefault(d, []).append(item)
            by_week_list.append({
                "week": week_num,
                "by_date": [
                    {"date": d, "posts": by_date_in_week[d]}
                    for d in sorted(by_date_in_week.keys())
                ],
            })
        by_date_list = [
            {"date": d, "posts": all_by_date[d]}
            for d in sorted(all_by_date.keys())
        ]
        result["by_week"] = by_week_list
        result["by_date"] = by_date_list
        return result

    @staticmethod
    def get_campaign_calendar(
        db: Session,
        campaign_id: str,
        agency_id: str,
    ) -> dict[str, Any]:
        """Return calendar grouped by week and by date; include platform, title, status, client, campaign."""
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        _, agency_name, client_name = CampaignService.get_campaign_with_names(
            db, campaign_id, agency_id
        )
        posts = CampaignService.get_posts_by_campaign(db, campaign_id, agency_id)
        by_week: dict[int, dict[str, list]] = {}
        by_date_flat: dict[str, list] = {}
        for p in posts:
            item = {
                "post_id": p.id,
                "platform": p.platform.value if p.platform else None,
                "title": p.title,
                "status": p.status.value if hasattr(p.status, "value") else str(p.status),
                "week_number": p.week_number,
                "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
                "scheduled_date": p.scheduled_date.isoformat() if p.scheduled_date else None,
                "client_name": client_name,
                "campaign_name": campaign.name,
            }
            wn = p.week_number
            by_week.setdefault(wn, {})
            if p.scheduled_date:
                d = p.scheduled_date.isoformat()
                by_week[wn].setdefault(d, []).append(item)
                by_date_flat.setdefault(d, []).append(item)
            else:
                by_week[wn].setdefault("_unscheduled", []).append(item)
        by_week_list = []
        for w in sorted(by_week.keys()):
            dated = [{"date": d, "posts": posts_list} for d, posts_list in sorted(by_week[w].items()) if d != "_unscheduled"]
            if "_unscheduled" in by_week[w]:
                dated.append({"date": "_unscheduled", "posts": by_week[w]["_unscheduled"]})
            by_week_list.append({"week": w, "by_date": dated})
        by_date_list = [
            {"date": d, "posts": by_date_flat[d]}
            for d in sorted(by_date_flat.keys())
        ]
        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "client_name": client_name,
            "by_week": by_week_list,
            "by_date": by_date_list,
        }

    @staticmethod
    def get_publication_windows(
        db: Session,
        campaign_id: str,
        agency_id: str,
    ) -> List[Any]:
        """List publication windows for a campaign."""
        from app.modules.campaigns.models import PublicationWindow
        CampaignService.get_campaign(db, campaign_id, agency_id)
        windows = (
            db.query(PublicationWindow)
            .filter(PublicationWindow.campaign_id == campaign_id)
            .order_by(PublicationWindow.platform, PublicationWindow.day_of_week, PublicationWindow.start_time)
            .all()
        )
        return windows

    @staticmethod
    def save_publication_windows(
        db: Session,
        campaign_id: str,
        agency_id: str,
        windows: List[Any],
    ) -> List[Any]:
        """Replace campaign publication windows with the given list (schema objects with platform, day_of_week, start_time, end_time, priority, is_active)."""
        from app.modules.campaigns.models import PublicationWindow, PostPlatform, DayOfWeek
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        existing = (
            db.query(PublicationWindow)
            .filter(PublicationWindow.campaign_id == campaign_id)
            .all()
        )
        for w in existing:
            db.delete(w)
        db.flush()
        created = []
        for w in windows:
            platform_str = getattr(w, "platform", "linkedin")
            day_str = getattr(w, "day_of_week", "monday")
            platform_enum = PostPlatform(platform_str) if isinstance(platform_str, str) else platform_str
            day_enum = DayOfWeek(day_str) if isinstance(day_str, str) else day_str
            pw = PublicationWindow(
                campaign_id=campaign_id,
                platform=platform_enum,
                day_of_week=day_enum,
                start_time=getattr(w, "start_time", time(9, 0)),
                end_time=getattr(w, "end_time", time(17, 0)),
                priority=getattr(w, "priority", 1),
                is_active=getattr(w, "is_active", True),
            )
            db.add(pw)
            created.append(pw)
        db.commit()
        for p in created:
            db.refresh(p)
        return created

    @staticmethod
    def schedule_post_manual(
        db: Session,
        post_id: str,
        agency_id: str,
        scheduled_date: date,
        scheduled_time: "time",
        scheduling_note: Optional[str] = None,
    ) -> Post:
        """Manual override: set scheduled_date, scheduled_time, scheduled_at for one post. Audit log created."""
        from app.modules.campaigns.models import SchedulingLog
        post = (
            db.query(Post)
            .join(MonthlyPlan)
            .join(Campaign)
            .join(Client)
            .filter(
                Post.id == post_id,
                Client.agency_id == agency_id,
            )
            .first()
        )
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found",
            )
        if post.status == PostStatus.CANCELED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot schedule a canceled post.",
            )
        if post.status not in (PostStatus.APPROVED_FINAL, PostStatus.SCHEDULED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only approved_final or already scheduled posts can be (re)scheduled.",
            )
        from datetime import timezone as tz
        dt = datetime.combine(scheduled_date, scheduled_time, tzinfo=tz.utc)
        post.scheduled_date = scheduled_date
        post.scheduled_time = scheduled_time
        post.scheduled_at = dt
        post.status = PostStatus.SCHEDULED
        log = SchedulingLog(
            campaign_id=post.campaign_id,
            post_id=post.id,
            scheduled_at=dt,
            window_id=None,
            scheduling_reason=scheduling_note or "manual_override",
        )
        db.add(log)
        db.commit()
        db.refresh(post)
        return post
