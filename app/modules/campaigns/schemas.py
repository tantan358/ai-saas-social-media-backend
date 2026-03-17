from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date, time
from app.modules.campaigns.models import CampaignStatus, PostStatus
from app.modules.campaigns.constants import (
    ALLOWED_CHANNELS,
    get_default_channels_config,
    POSTS_PER_CHANNEL_MIN,
    POSTS_PER_CHANNEL_MAX,
    DEFAULT_POSTS_PER_CHANNEL_PER_WEEK,
)

ALLOWED_DISTRIBUTION_STRATEGIES = frozenset({"balanced", "linkedin_priority", "instagram_priority"})
ALLOWED_CONTENT_LENGTHS = frozenset({"short", "medium", "long"})
ALLOWED_CAMPAIGN_GOALS = frozenset({
    "awareness", "engagement", "leads", "sales", "brand_loyalty",
    "traffic", "conversions", "community", "thought_leadership",
})

# Content objectives (for objective_mode by_day / by_post and for storing per post)
ALLOWED_CONTENT_OBJECTIVES = frozenset({
    "lead_generation", "education", "product_promotion", "brand_authority",
    "conversion", "positioning",
})
ALLOWED_OBJECTIVE_MODES = frozenset({"mixed", "by_day", "by_post"})
WEEKDAY_KEYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


class CampaignBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    language: str = Field(default="es", pattern="^(es|en)$")


class CampaignCreate(CampaignBase):
    client_id: str


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[CampaignStatus] = None


class CampaignResponse(CampaignBase):
    id: str
    client_id: str
    status: CampaignStatus
    ai_plan: Optional[Dict[str, Any]] = None
    approved_at: Optional[datetime] = None
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CampaignDetailResponse(CampaignResponse):
    """Campaign with agency and client names for detail view."""
    agency_name: Optional[str] = None
    client_name: Optional[str] = None


class PostBase(BaseModel):
    title: Optional[str] = None
    content: str = Field(..., min_length=1)
    platform: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class PostCreate(PostBase):
    campaign_id: str


class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    hashtags: Optional[str] = Field(None, max_length=500)
    link: Optional[str] = Field(None, max_length=2048)
    status: Optional[PostStatus] = None
    scheduled_at: Optional[datetime] = None


class PostResponse(PostBase):
    id: str
    monthly_plan_id: str
    week_number: int
    status: PostStatus
    hashtags: Optional[str] = None
    link: Optional[str] = None
    content_objective: Optional[str] = None
    approved_at: Optional[datetime] = None
    scheduled_date: Optional[date] = None
    scheduled_time: Optional[time] = None
    scheduling_window_id: Optional[str] = None
    published_at: Optional[datetime] = None
    published_post_id: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApprovalCreate(BaseModel):
    campaign_id: str
    post_id: Optional[str] = None
    approval_type: str = Field(..., pattern="^(plan_approval|post_approval)$")
    approved: bool
    comments: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: str
    campaign_id: str
    post_id: Optional[str] = None
    approval_type: str
    approved: bool
    comments: Optional[str] = None
    approved_by: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Monthly plan (get plan / generate plan) ---
# MonthlyPlanPost: slim post shape when nested inside a plan (no monthly_plan_id, timestamps, etc.).
# PostResponse is the full post; nothing in schemas.py previously did this nested shape.
class MonthlyPlanPost(BaseModel):
    id: str
    week_number: int
    title: Optional[str] = None
    content: str
    platform: Optional[str] = None
    status: PostStatus
    hashtags: Optional[str] = None
    link: Optional[str] = None
    content_objective: Optional[str] = None


# Stored generation config (audit/debugging). Shape: posts_per_channel_per_week (or legacy posts_per_week), channels,
# campaign_goal_mix, content_variation, language, content_length, call_to_action_required.
# Returned as optional dict in MonthlyPlanResponse.
# MonthlyPlanResponse: a plan with its posts and optional generation config.
class MonthlyPlanResponse(BaseModel):
    id: str
    campaign_id: str
    posts: List[MonthlyPlanPost]
    created_at: datetime
    updated_at: Optional[datetime] = None
    generation_config: Optional[Dict[str, Any]] = None
    total_posts: Optional[int] = None
    distribution_json: Optional[List[int]] = None


class ChannelConfig(BaseModel):
    """Per-channel configuration. Channel names must be in ALLOWED_CHANNELS (see constants)."""
    name: str = Field(..., description="Channel identifier (e.g. linkedin, instagram)")
    posts_per_week: int = Field(
        ...,
        ge=POSTS_PER_CHANNEL_MIN,
        le=POSTS_PER_CHANNEL_MAX,
        description="Posts per week for this channel (1-7)",
    )

    @field_validator("name")
    @classmethod
    def name_must_be_allowed_channel(cls, v: str) -> str:
        key = v.lower() if isinstance(v, str) else v
        if key not in ALLOWED_CHANNELS:
            raise ValueError(
                f"channel name must be one of {sorted(ALLOWED_CHANNELS)}, got {v!r}"
            )
        return key


# GeneratePlanRequest: optional body for POST generate-plan.
# Primary shape: channels = list of { name, posts_per_week }. Total output = sum(posts_per_week) * 4 weeks.
class GeneratePlanRequest(BaseModel):
    channels: Optional[List[ChannelConfig]] = Field(
        None,
        description="List of channels with posts_per_week each. Total per week = sum(posts_per_week). Extensible for future channels.",
    )
    campaign_goal_mix: Optional[List[str]] = Field(None, description="Marketing goals for content mix (used when objective_mode=mixed)")
    objective_mode: Optional[str] = Field(
        None,
        description="mixed = use campaign_goal_mix; by_day = use objective_by_day; by_post = use objective_by_post",
    )
    objective_by_day: Optional[Dict[str, str]] = Field(
        None,
        description="Day -> objective (keys: monday..sunday). Required when objective_mode=by_day.",
    )
    objective_by_post: Optional[List[str]] = Field(
        None,
        description="Objectives in slot order; cycles if shorter than total posts. Required when objective_mode=by_post.",
    )
    content_variation: Optional[bool] = Field(None, description="Vary content types/themes")
    language: Optional[str] = Field(None, pattern="^(es|en)$", description="Content language")
    content_length: Optional[str] = Field(None, description="short | medium | long")
    call_to_action_required: Optional[bool] = Field(None, description="Include CTA in posts")

    @field_validator("channels", mode="before")
    @classmethod
    def normalize_channels(cls, v: Any) -> Any:
        """Accept channels as list of { name, posts_per_week } or legacy list of strings (default 4 posts/week)."""
        if v is None:
            return v
        if not isinstance(v, list):
            return v
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"name": item.lower(), "posts_per_week": DEFAULT_POSTS_PER_CHANNEL_PER_WEEK})
            elif isinstance(item, dict):
                result.append(item)
            else:
                result.append(item)
        return result

    @field_validator("channels")
    @classmethod
    def channels_unique_and_non_empty(cls, v: Optional[List[ChannelConfig]]) -> Optional[List[ChannelConfig]]:
        if v is None:
            return v
        if len(v) == 0:
            raise ValueError("channels must contain at least one channel")
        seen = set()
        out = []
        for c in v:
            if c.name in seen:
                raise ValueError(f"duplicate channel name: {c.name!r}")
            seen.add(c.name)
            out.append(c)
        return out

    @field_validator("campaign_goal_mix")
    @classmethod
    def campaign_goals_allowed(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None or not v:
            return v
        lower = [g.lower() for g in v]
        invalid = set(lower) - ALLOWED_CAMPAIGN_GOALS
        if invalid:
            raise ValueError(
                f"campaign_goal_mix contains invalid goals: {invalid}. "
                f"Allowed: {sorted(ALLOWED_CAMPAIGN_GOALS)}"
            )
        return list(dict.fromkeys(lower))

    @field_validator("content_length")
    @classmethod
    def content_length_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v.lower() not in ALLOWED_CONTENT_LENGTHS:
            raise ValueError("content_length must be one of: short, medium, long")
        return v.lower()

    @field_validator("objective_mode")
    @classmethod
    def objective_mode_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v.lower() not in ALLOWED_OBJECTIVE_MODES:
            raise ValueError("objective_mode must be one of: mixed, by_day, by_post")
        return v.lower()

    @field_validator("objective_by_day")
    @classmethod
    def objective_by_day_valid(cls, v: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        if v is None or not v:
            return v
        out = {}
        for day, obj in v.items():
            d = day.lower() if isinstance(day, str) else day
            if d not in WEEKDAY_KEYS:
                raise ValueError(f"objective_by_day key must be one of {WEEKDAY_KEYS}, got {day!r}")
            o = (obj or "").lower().strip()
            if o not in ALLOWED_CONTENT_OBJECTIVES:
                raise ValueError(f"objective_by_day[{day!r}] must be one of {sorted(ALLOWED_CONTENT_OBJECTIVES)}, got {obj!r}")
            out[d] = o
        return out

    @field_validator("objective_by_post")
    @classmethod
    def objective_by_post_valid(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None or not v:
            return v
        out = []
        for i, obj in enumerate(v):
            o = (obj or "").lower().strip()
            if o not in ALLOWED_CONTENT_OBJECTIVES:
                raise ValueError(
                    f"objective_by_post[{i}] must be one of {sorted(ALLOWED_CONTENT_OBJECTIVES)}, got {obj!r}"
                )
            out.append(o)
        return out

    @model_validator(mode="after")
    def objective_mode_consistency(self) -> "GeneratePlanRequest":
        if self.objective_mode == "by_day" and (not self.objective_by_day or len(self.objective_by_day) == 0):
            raise ValueError("objective_by_day is required when objective_mode=by_day")
        if self.objective_mode == "by_post" and (not self.objective_by_post or len(self.objective_by_post) == 0):
            raise ValueError("objective_by_post is required when objective_mode=by_post")
        return self


# Resolved generation options (all required) after merging request with campaign defaults.
# posts_per_channel_per_week: each selected channel -> posts per week (1-7). Total per week may be 7-14.
class GenerationOptions(BaseModel):
    posts_per_channel_per_week: Dict[str, int] = Field(
        ...,
        description="Per-channel weekly limit (1-7). Keys = channel names from channels.",
    )
    channels: List[str] = Field(..., min_length=1)
    distribution_strategy: str = Field(...)
    campaign_goal_mix: List[str] = Field(default_factory=list)
    objective_mode: str = Field(..., description="mixed | by_day | by_post")
    objective_by_day: Optional[Dict[str, str]] = Field(None, description="Day -> content objective; used when objective_mode=by_day")
    objective_by_post: Optional[List[str]] = Field(None, description="Objective per slot order; used when objective_mode=by_post")
    content_variation: bool = True
    language: str = Field(..., pattern="^(es|en)$")
    content_length: str = Field(...)
    call_to_action_required: bool = False

    class Config:
        frozen = True


def resolve_generation_options(
    request: Optional[GeneratePlanRequest],
    campaign_language: str,
) -> GenerationOptions:
    """Build options from request. Total output = sum(channel.posts_per_week) * 4 weeks per channel."""
    r = request
    if r and r.channels and len(r.channels) > 0:
        channels = [c.name for c in r.channels]
        per_channel = {c.name: c.posts_per_week for c in r.channels}
    else:
        channels, per_channel = get_default_channels_config()

    objective_mode = (
        (r.objective_mode or "mixed").lower()
        if r and r.objective_mode is not None
        else "mixed"
    )
    if objective_mode not in ALLOWED_OBJECTIVE_MODES:
        objective_mode = "mixed"
    objective_by_day = r.objective_by_day if r and r.objective_by_day else None
    objective_by_post = r.objective_by_post if r and r.objective_by_post else None

    return GenerationOptions(
        posts_per_channel_per_week=per_channel,
        channels=channels,
        distribution_strategy="balanced",
        campaign_goal_mix=(
            r.campaign_goal_mix
            if r and r.campaign_goal_mix is not None
            else ["awareness", "engagement"]
        ),
        objective_mode=objective_mode,
        objective_by_day=objective_by_day,
        objective_by_post=objective_by_post,
        content_variation=(
            r.content_variation if r and r.content_variation is not None else True
        ),
        language=(
            r.language if r and r.language is not None else campaign_language
        ),
        content_length=(
            r.content_length if r and r.content_length is not None else "medium"
        ),
        call_to_action_required=(
            r.call_to_action_required if r and r.call_to_action_required is not None else False
        ),
    )


# GetPlanResponse: used when returning current plan (plan may be null). Not in schemas before.
class GetPlanResponse(BaseModel):
    plan: Optional[MonthlyPlanResponse] = None


# Schedule campaign: optional plan start date (first day of plan month).
class ScheduleCampaignRequest(BaseModel):
    plan_start_date: Optional[date] = Field(
        None,
        description="First day of the plan month (e.g. 2026-04-01). If omitted, first day of next month is used.",
    )


# Response from POST .../schedule: assigned count and schedule grouped by week.
class ScheduleCampaignResponse(BaseModel):
    campaign_id: str
    assigned_count: int
    plan_start_date: Optional[str] = None
    schedule_by_week: Dict[str, Any] = Field(default_factory=dict)


# --- Schedule-auto: response grouped by week and by date ---
class ScheduleItemResponse(BaseModel):
    post_id: str
    platform: Optional[str] = None
    title: Optional[str] = None
    status: str
    scheduled_at: str
    scheduled_date: Optional[str] = None
    day_of_week: Optional[str] = None


class ScheduleByDateResponse(BaseModel):
    date: str  # ISO date
    posts: List[ScheduleItemResponse] = Field(default_factory=list)


class ScheduleByWeekResponse(BaseModel):
    week: int
    by_date: List[ScheduleByDateResponse] = Field(default_factory=list, alias="by_date")

    class Config:
        populate_by_name = True


class ScheduleAutoResponse(BaseModel):
    campaign_id: str
    assigned_count: int
    plan_start_date: Optional[str] = None
    by_week: List[ScheduleByWeekResponse] = Field(default_factory=list)
    by_date: List[ScheduleByDateResponse] = Field(default_factory=list)


# --- Manual post schedule (PUT /posts/{id}/schedule) ---
class PostScheduleUpdate(BaseModel):
    scheduled_date: date
    scheduled_time: time
    scheduling_note: Optional[str] = Field(None, max_length=500)


# --- Publication windows ---
class PublicationWindowCreate(BaseModel):
    platform: str = Field(..., pattern="^(linkedin|instagram)$")
    day_of_week: str = Field(
        ...,
        pattern="^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$",
    )
    start_time: time
    end_time: time
    priority: int = Field(1, ge=0, le=10)
    is_active: bool = True


class PublicationWindowBulkCreate(BaseModel):
    windows: List[PublicationWindowCreate] = Field(..., min_length=1, max_length=50)


class PublicationWindowResponse(BaseModel):
    id: str
    campaign_id: str
    platform: str
    day_of_week: str
    start_time: time
    end_time: time
    priority: int
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Calendar (GET /campaigns/{id}/calendar) ---
class CalendarPostItem(BaseModel):
    post_id: str
    platform: Optional[str] = None
    title: Optional[str] = None
    status: str
    week_number: int
    scheduled_at: Optional[str] = None
    scheduled_date: Optional[str] = None
    client_name: Optional[str] = None
    campaign_name: Optional[str] = None


class CalendarByDate(BaseModel):
    date: str
    posts: List[CalendarPostItem] = Field(default_factory=list)


class CalendarByWeek(BaseModel):
    week: int
    by_date: List[CalendarByDate] = Field(default_factory=list)


class CampaignCalendarResponse(BaseModel):
    campaign_id: str
    campaign_name: Optional[str] = None
    client_name: Optional[str] = None
    by_week: List[CalendarByWeek] = Field(default_factory=list)
    by_date: List[CalendarByDate] = Field(default_factory=list)


# GeneratePlanResponse: response of generate-plan endpoint (campaign + new plan + mode).
class GeneratePlanResponse(BaseModel):
    campaign: CampaignResponse
    plan: MonthlyPlanResponse
    generation_mode: str
