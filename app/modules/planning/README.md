# Planning module

## Balanced distribution

- **Service**: `app/modules/planning/services/distribution_service.py`
- **Entry point**: `distribute_posts_across_weeks(total_posts, min_per_week=3, max_per_week=5) -> list[int]`

Returns exactly 4 integers (posts per week 1–4) that sum to `total_posts`, with no week 0 for normal totals (12–20), and extras spread evenly (e.g. 14 → [3, 4, 3, 4]).

## How to verify via API

1. **Generate a plan**  
   `POST /api/agencies/{agency_id}/campaigns/{campaign_id}/generate-plan`  
   (with or without body for options).

2. **Inspect the response**  
   - `plan.total_posts`: total number of posts.  
   - `plan.distribution_json`: list of 4 integers, e.g. `[3, 3, 3, 3]` for 12 posts.  
   - `plan.posts`: each post has `week_number` (1–4).  
   - Count posts per week: the counts must match `distribution_json`  
     (e.g. three posts with `week_number: 1` when `distribution_json[0] === 3`).

3. **Or GET plan**  
   `GET /api/agencies/{agency_id}/campaigns/{campaign_id}/plan`  
   The same `total_posts`, `distribution_json`, and `posts[].week_number` are returned.

## Tests

Run:

```bash
pytest tests/test_distribution_service.py -v
```

Covers totals 12, 13, 14, 15, 16; no week empty (12–20); always 4 weeks; sum equals total; and small totals (< 4).
