# Milestone 3 – Scheduling API

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/campaigns/{id}/schedule-auto` | Auto-schedule approved posts using publication windows; response grouped by week and date |
| PUT | `/api/posts/{id}/schedule` | Manual override: set scheduled_date and scheduled_time for one post |
| GET | `/api/campaigns/{id}/calendar` | Calendar view: posts grouped by week and by date (platform, title, status, client, campaign) |
| POST | `/api/campaigns/{id}/publication-windows` | Save custom publication windows for the campaign |
| GET | `/api/campaigns/{id}/publication-windows` | List publication windows for the campaign |

All campaign endpoints require the campaign to belong to the current agency (via `agency_id` from auth). Post schedule requires the post to belong to a campaign of the current agency.

---

## 1. POST /api/campaigns/{id}/schedule-auto

**Behavior:** Only for campaigns whose planning is approved. Only posts with status `approved_final` are scheduled. Uses balanced distribution and publication windows; creates `scheduling_logs`; returns schedule grouped by week and by date.

**Request (optional body):**
```json
{
  "plan_start_date": "2026-04-01"
}
```
Omit body to use first day of next month.

**Response (200):**
```json
{
  "campaign_id": "abc-123",
  "assigned_count": 12,
  "plan_start_date": "2026-04-01",
  "by_week": [
    {
      "week": 1,
      "by_date": [
        {
          "date": "2026-04-01",
          "posts": [
            {
              "post_id": "p1",
              "platform": "linkedin",
              "title": "Post title",
              "status": "scheduled",
              "scheduled_at": "2026-04-01T10:15:00+00:00",
              "scheduled_date": "2026-04-01",
              "day_of_week": "tuesday"
            }
          ]
        }
      ]
    }
  ],
  "by_date": [
    {
      "date": "2026-04-01",
      "posts": [...]
    }
  ]
}
```

---

## 2. PUT /api/posts/{id}/schedule

**Behavior:** Manual override for one post. Only allowed if post status is `approved_final` or `scheduled`. Cannot edit if post is `canceled`. Creates a scheduling_log entry (e.g. `manual_override` or custom note).

**Request:**
```json
{
  "scheduled_date": "2026-04-15",
  "scheduled_time": "14:30:00",
  "scheduling_note": "Moved to match client request"
}
```

**Response (200):** Full `PostResponse` including updated `scheduled_date`, `scheduled_time`, `scheduled_at`, `status` (scheduled).

**Validation errors (400):**
- "Only approved_final or already scheduled posts can be (re)scheduled."
- "Cannot schedule a canceled post."

---

## 3. GET /api/campaigns/{id}/calendar

**Response (200):**
```json
{
  "campaign_id": "abc-123",
  "campaign_name": "Q2 Campaign",
  "client_name": "Acme Inc",
  "by_week": [
    {
      "week": 1,
      "by_date": [
        {
          "date": "2026-04-01",
          "posts": [
            {
              "post_id": "p1",
              "platform": "linkedin",
              "title": "Title",
              "status": "scheduled",
              "week_number": 1,
              "scheduled_at": "2026-04-01T10:15:00+00:00",
              "scheduled_date": "2026-04-01",
              "client_name": "Acme Inc",
              "campaign_name": "Q2 Campaign"
            }
          ]
        }
      ]
    }
  ],
  "by_date": [
    {
      "date": "2026-04-01",
      "posts": [...]
    }
  ]
}
```

---

## 4. POST /api/campaigns/{id}/publication-windows

**Request:**
```json
{
  "windows": [
    {
      "platform": "linkedin",
      "day_of_week": "tuesday",
      "start_time": "10:00:00",
      "end_time": "12:00:00",
      "priority": 1,
      "is_active": true
    },
    {
      "platform": "instagram",
      "day_of_week": "monday",
      "start_time": "11:00:00",
      "end_time": "13:00:00",
      "priority": 1,
      "is_active": true
    }
  ]
}
```

**Response (201):** List of `PublicationWindowResponse` with `id`, `campaign_id`, `platform`, `day_of_week`, `start_time`, `end_time`, `priority`, `is_active`, `created_at`.

---

## 5. GET /api/campaigns/{id}/publication-windows

**Response (200):** List of `PublicationWindowResponse` (same shape as above).

---

## Validation rules (backend)

- Do not schedule all posts on the same day unless `total_posts = 1` (enforced in window scheduler).
- Each post is assigned at most one scheduled datetime per run; manual override can reschedule and creates a new log.
- Auto-schedule uses only configured publication windows (campaign-specific or platform defaults).
- Manual override is allowed even if the post was previously auto-scheduled.
- No week is left empty when posts exist for that week (handled by balanced distribution and window assignment).
