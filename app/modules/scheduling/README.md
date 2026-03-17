# Scheduling module

Publication window scheduling assigns real `scheduled_date`, `scheduled_time`, `scheduled_at`, and `scheduling_window_id` to posts using campaign publication windows (or platform defaults).

## Services

- **`app/modules/scheduling/services/window_scheduler.py`**
  - `get_default_windows_for_platform(platform)` – default windows for LinkedIn / Instagram
  - `pick_datetime_within_window(week_number, day_of_week, start_time, end_time, plan_start_date, ...)` – one datetime inside a window
  - `assign_dates_and_times_for_campaign(db, campaign_id, plan_start_date=None)` – assign all approved posts and return summary
  - `build_schedule_summary_by_week(schedule_by_week)` – format for display

## Rules

- Each post is scheduled only once.
- Posts are spread across available week days (round-robin across windows).
- One datetime per post inside one chosen window; evenly spaced minutes when multiple posts share a window to avoid collisions.

## Default windows

| Platform  | Day      | Time      |
|----------|----------|-----------|
| LinkedIn | Tuesday  | 10:00–12:00 |
| LinkedIn | Thursday | 14:00–16:00 |
| LinkedIn | Friday   | 09:00–11:00 |
| Instagram| Monday   | 11:00–13:00 |
| Instagram| Wednesday| 15:00–17:00 |
| Instagram| Saturday | 18:00–20:00 |

## API integration

- **After approval (auto):** If the monthly plan has `scheduling_mode = auto_windowed`, `POST .../approve-plan` runs assignment and sets campaign status to `scheduled`.
- **Manual:** `POST .../campaigns/{campaign_id}/schedule` with optional body `{ "plan_start_date": "2026-04-01" }` to assign dates and set status to `scheduled`.

## Example assigned schedule output (grouped by week)

```json
{
  "campaign_id": "abc-123",
  "assigned_count": 12,
  "plan_start_date": "2026-04-01",
  "schedule_by_week": {
    "1": [
      { "post_id": "...", "platform": "linkedin", "scheduled_at": "2026-04-01T10:15:00+00:00", "day_of_week": "tuesday" },
      { "post_id": "...", "platform": "instagram", "scheduled_at": "2026-04-01T11:30:00+00:00", "day_of_week": "monday" }
    ],
    "2": [
      { "post_id": "...", "platform": "linkedin", "scheduled_at": "2026-04-09T14:00:00+00:00", "day_of_week": "thursday" }
    ],
    "3": [ ... ],
    "4": [ ... ]
  }
}
```

Posts in the same week are spread across different days (and windows); multiple posts in the same window get evenly spaced minutes within the window.
