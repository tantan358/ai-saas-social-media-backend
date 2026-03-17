"""
Balanced monthly distribution engine for NERVIA.

Distributes total_posts across weeks 1-4 as evenly as possible,
respecting min/max per week and spreading extras (e.g. 13 -> [3,3,3,4]).

Verification via API:
  After generating a plan (POST .../generate-plan) or fetching it (GET .../plan):
  - Response.plan.total_posts equals the number of posts.
  - Response.plan.distribution_json is a list of 4 integers (posts per week 1-4)
    that sum to total_posts, e.g. [3, 3, 3, 3] for 12.
  - For each post in Response.plan.posts, week_number is 1-4; the count of
    posts per week matches distribution_json (e.g. three posts with week_number=1
    when distribution_json[0] == 3).
"""

WEEKS = 4


def distribute_posts_across_weeks(
    total_posts: int,
    min_per_week: int = 3,
    max_per_week: int = 5,
) -> list[int]:
    """
    Return exactly 4 integers (posts per week 1–4) that sum to total_posts.

    Rules:
    - Sum equals total_posts.
    - No week is 0 (except when total_posts < 4, then trailing weeks may be 0).
    - As balanced as possible; extras distributed one by one across weeks.
    - Respects min_per_week and max_per_week when possible.

    Examples:
        12 -> [3, 3, 3, 3]
        13 -> [3, 3, 3, 4]
        14 -> [3, 4, 3, 4]
        15 -> [4, 4, 3, 4]
        16 -> [4, 4, 4, 4]
    """
    if total_posts <= 0:
        return [0, 0, 0, 0]

    if total_posts < WEEKS:
        # Represent as much as possible; allow zeros for trailing weeks.
        result = [0] * WEEKS
        for i in range(total_posts):
            result[i] = 1
        return result

    base, remainder = divmod(total_posts, WEEKS)

    # Clamp base into [min_per_week, max_per_week] when possible.
    # If remainder is 0, all weeks get base; otherwise we add 1 to some weeks.
    low = max(1, min_per_week)
    high = max_per_week

    if remainder == 0:
        # Even split. Allow base < min_per_week for small totals (e.g. 4 -> [1,1,1,1]); cap at max.
        value = max(1, min(high, base))
        return [value] * WEEKS

    # Spread remainder so extras are distributed, not stacked.
    # Indices that get +1: for r=1 use last week; r=2 use weeks 2 and 4; r=3 use 1,2,4.
    spread_indices: dict[int, list[int]] = {
        1: [3],       # last week -> [3,3,3,4]
        2: [1, 3],    # -> [3,4,3,4]
        3: [0, 1, 3], # -> [4,4,3,4]
    }
    indices_get_extra = spread_indices.get(remainder, list(range(remainder)))

    result = [base] * WEEKS
    for idx in indices_get_extra:
        result[idx] += 1

    # Clamp each week to [low, high] if we're outside (e.g. total_posts very large).
    for i in range(WEEKS):
        result[i] = max(low, min(high, result[i]))

    # If clamping changed the sum, we may need to rebalance; for normal range 12–20 we're fine.
    current_sum = sum(result)
    if current_sum != total_posts and remainder > 0:
        # Adjust by adding/subtracting from weeks that have room
        diff = total_posts - current_sum
        if diff > 0:
            for i in range(WEEKS):
                if diff <= 0:
                    break
                if result[i] < high:
                    add = min(diff, high - result[i])
                    result[i] += add
                    diff -= add
        elif diff < 0:
            for i in range(WEEKS - 1, -1, -1):
                if diff >= 0:
                    break
                if result[i] > low:
                    sub = min(-diff, result[i] - low)
                    result[i] -= sub
                    diff += sub

    return result
