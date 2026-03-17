"""
Publication window scheduling: assign real scheduled datetimes to posts
using campaign publication windows (or platform defaults).

Rules:
- Each post is scheduled only once.
- Different posts are distributed across different valid time windows.
- Spread posts across available week days; avoid stacking all on one day.
- Pick a random or evenly spaced minute within the window; avoid collisions.
"""

from __future__ import annotations

import random
from datetime import date, time, datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Default sample windows: (day_of_week, start_time, end_time)
# Times are naive; we combine with UTC dates.
DEFAULT_WINDOWS_LINKEDIN = [
    ("tuesday", time(10, 0), time(12, 0)),
    ("thursday", time(14, 0), time(16, 0)),
    ("friday", time(9, 0), time(11, 0)),
]

DEFAULT_WINDOWS_INSTAGRAM = [
    ("monday", time(11, 0), time(13, 0)),
    ("wednesday", time(15, 0), time(17, 0)),
    ("saturday", time(18, 0), time(20, 0)),
]

# Python weekday: Monday=0 .. Sunday=6
DAY_NAME_TO_WEEKDAY = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def get_default_windows_for_platform(platform: str) -> list[dict]:
    """
    Return default publication windows for a platform.

    LinkedIn: Tuesday 10:00-12:00, Thursday 14:00-16:00, Friday 09:00-11:00
    Instagram: Monday 11:00-13:00, Wednesday 15:00-17:00, Saturday 18:00-20:00

    Each item: {"day_of_week": str, "start_time": time, "end_time": time}
    """
    platform_lower = (platform or "").strip().lower()
    if platform_lower == "linkedin":
        return [
            {"day_of_week": d, "start_time": s, "end_time": e}
            for d, s, e in DEFAULT_WINDOWS_LINKEDIN
        ]
    if platform_lower == "instagram":
        return [
            {"day_of_week": d, "start_time": s, "end_time": e}
            for d, s, e in DEFAULT_WINDOWS_INSTAGRAM
        ]
    return []


def pick_datetime_within_window(
    week_number: int,
    day_of_week: str,
    start_time: time,
    end_time: time,
    plan_start_date: date,
    slot_index: int = 0,
    total_slots: int = 1,
    tz: timezone = timezone.utc,
) -> datetime:
    """
    Pick a single datetime inside the given window for the given plan week.

    - week_number: 1-4 (week 1 = first 7 days of plan month, etc.)
    - day_of_week: "monday" .. "sunday"
    - start_time, end_time: naive time (interpreted in tz)
    - plan_start_date: first day of the plan month (e.g. 2026-04-01)
    - slot_index, total_slots: when multiple posts share the same window,
      use evenly spaced minutes to avoid collision (slot_index 0 of 3 = early third)

    Returns timezone-aware datetime in tz.
    """
    target_weekday = DAY_NAME_TO_WEEKDAY.get((day_of_week or "").strip().lower())
    if target_weekday is None:
        target_weekday = 0  # monday fallback

    # Week 1 = days 0-6, week 2 = 7-13, week 3 = 14-20, week 4 = 21-27
    week_start = plan_start_date + timedelta(days=(week_number - 1) * 7)
    week_end = week_start + timedelta(days=6)

    # Find the date in this week that matches day_of_week
    d = week_start
    while d <= week_end:
        if d.weekday() == target_weekday:
            break
        d += timedelta(days=1)
    else:
        d = week_start  # fallback to first day of week

    # Pick a minute between start_time and end_time (evenly spaced if total_slots > 1)
    start_minutes = start_time.hour * 60 + start_time.minute
    end_minutes = end_time.hour * 60 + end_time.minute
    if end_minutes <= start_minutes:
        end_minutes += 24 * 60
    span = end_minutes - start_minutes
    if total_slots > 1 and span >= total_slots:
        # Evenly space: slot 0 gets first slot, etc.
        offset_minutes = (span * slot_index) // total_slots
    else:
        offset_minutes = random.randint(0, max(0, span - 1)) if span > 1 else 0
    chosen_minutes = start_minutes + offset_minutes
    if chosen_minutes >= 24 * 60:
        chosen_minutes -= 24 * 60
        d += timedelta(days=1)
    chosen_time = time(chosen_minutes // 60, chosen_minutes % 60, 0)

    dt = datetime.combine(d, chosen_time, tzinfo=tz)
    return dt


def assign_dates_and_times_for_campaign(
    db: Session,
    campaign_id: str,
    plan_start_date: date | None = None,
) -> dict:
    """
    Assign scheduled_date, scheduled_time, scheduled_at, scheduling_window_id,
    and status=scheduled to all approved_final posts in the campaign, using
    publication windows (campaign's or platform defaults). Spread posts across
    days and windows; avoid collisions.

    If plan_start_date is None, uses the first day of the next month (from today).

    Returns a summary dict: {
        "campaign_id": str,
        "assigned_count": int,
        "schedule_by_week": { 1: [...], 2: [...], 3: [...], 4: [...] },
    }
    """
    from app.modules.campaigns.models import (
        Campaign,
        Post,
        MonthlyPlan,
        PublicationWindow,
        SchedulingLog,
        PostStatus,
    )

    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise ValueError(f"Campaign not found: {campaign_id}")

    if plan_start_date is None:
        today = date.today()
        if today.month == 12:
            plan_start_date = date(today.year + 1, 1, 1)
        else:
            plan_start_date = date(today.year, today.month + 1, 1)

    # Collect approved_final posts from the campaign's current plan(s)
    plans = db.query(MonthlyPlan).filter(MonthlyPlan.campaign_id == campaign_id).all()
    posts: list[Post] = []
    for plan in plans:
        for p in plan.posts:
            if p.status == PostStatus.APPROVED_FINAL and not p.scheduled_at:
                posts.append(p)

    if not posts:
        return {
            "campaign_id": campaign_id,
            "assigned_count": 0,
            "schedule_by_week": {1: [], 2: [], 3: [], 4: []},
        }

    # Load publication_windows for this campaign (may be empty -> use defaults)
    db_windows_list = (
        db.query(PublicationWindow)
        .filter(
            PublicationWindow.campaign_id == campaign_id,
            PublicationWindow.is_active == True,
        )
        .all()
    )

    def windows_for_platform(platform_value) -> list[tuple[str, time, time, str | None]]:
        """Return list of (day_of_week, start_time, end_time, window_id)."""
        platform_str = platform_value.value if hasattr(platform_value, "value") else str(platform_value)
        campaign_windows = [
            w
            for w in db_windows_list
            if (w.platform.value == platform_str if hasattr(w.platform, "value") else str(w.platform) == platform_str)
        ]
        if campaign_windows:
            return [
                (
                    w.day_of_week.value if hasattr(w.day_of_week, "value") else str(w.day_of_week),
                    w.start_time,
                    w.end_time,
                    w.id,
                )
                for w in sorted(campaign_windows, key=lambda x: (x.day_of_week.value if hasattr(x.day_of_week, "value") else str(x.day_of_week), x.start_time or time(0))
                )
            ]
        defaults = get_default_windows_for_platform(platform_str)
        return [(w["day_of_week"], w["start_time"], w["end_time"], None) for w in defaults]

    # Group posts by (week_number, platform) to spread across windows
    by_week_platform: dict[tuple[int, str], list[Post]] = {}
    for p in posts:
        platform_str = p.platform.value if p.platform else "linkedin"
        key = (p.week_number, platform_str)
        by_week_platform.setdefault(key, []).append(p)

    tz = timezone.utc
    schedule_by_week: dict[int, list[dict]] = {1: [], 2: [], 3: [], 4: []}
    used_minutes_per_day: dict[tuple[int, date, str], set[int]] = {}  # (week, date, platform) -> set of minute-of-day

    for (week_num, platform_str), group in sorted(by_week_platform.items()):
        windows = windows_for_platform(platform_str)
        if not windows:
            continue
        W = len(windows)
        group_sorted = sorted(group, key=lambda p: p.id)
        N = len(group_sorted)
        for i, post in enumerate(group_sorted):
            # Round-robin across windows so we don't stack all posts on one day
            win_index = i % W
            day_of_week, start_t, end_t, window_id = windows[win_index]
            # How many posts share this window (indices i where i % W == win_index)
            total_in_window = (N - win_index + W - 1) // W
            slot_index = i // W  # 0-based index within this window

            dt = pick_datetime_within_window(
                week_number=week_num,
                day_of_week=day_of_week,
                start_time=start_t,
                end_time=end_t,
                plan_start_date=plan_start_date,
                slot_index=slot_index,
                total_slots=max(1, total_in_window),
                tz=tz,
            )

            # Avoid collision: if this minute was used for same (week, date, platform), nudge
            day_date = dt.date()
            minute_key = (week_num, day_date, platform_str)
            used = used_minutes_per_day.setdefault(minute_key, set())
            minute_of_day = dt.hour * 60 + dt.minute
            while minute_of_day in used and minute_of_day < 24 * 60 - 1:
                minute_of_day += 1
                dt = dt.replace(minute=minute_of_day % 60, hour=minute_of_day // 60)
            used.add(minute_of_day)

            post.scheduled_date = dt.date()
            post.scheduled_time = time(dt.hour, dt.minute, 0)
            post.scheduled_at = dt
            post.scheduling_window_id = window_id
            post.status = PostStatus.SCHEDULED

            schedule_by_week[week_num].append({
                "post_id": post.id,
                "platform": platform_str,
                "scheduled_at": dt.isoformat(),
                "scheduled_date": dt.date().isoformat(),
                "day_of_week": day_of_week,
                "title": getattr(post, "title", None),
                "status": post.status.value if hasattr(post.status, "value") else str(post.status),
            })

            log = SchedulingLog(
                campaign_id=campaign_id,
                post_id=post.id,
                scheduled_at=dt,
                window_id=window_id,
                scheduling_reason="auto_windowed",
            )
            db.add(log)

    # Validation: do not schedule all posts on the same day unless total_posts == 1
    if len(posts) > 1:
        distinct_dates = {p.scheduled_date for p in posts if p.scheduled_date}
        if len(distinct_dates) < 2:
            db.rollback()
            raise ValueError(
                "Scheduling would assign all posts to the same day. "
                "Ensure multiple publication windows across different days."
            )

    db.commit()
    return {
        "campaign_id": campaign_id,
        "assigned_count": len(posts),
        "plan_start_date": plan_start_date.isoformat(),
        "schedule_by_week": schedule_by_week,
    }


def build_schedule_summary_by_week(schedule_by_week: dict) -> list[dict]:
    """
    Helper: format schedule_by_week for display (e.g. API response).
    Returns list of { "week": int, "posts": [ { "post_id", "platform", "scheduled_at" } ] }.
    """
    return [
        {"week": w, "posts": schedule_by_week.get(w, [])}
        for w in sorted(schedule_by_week.keys())
    ]
