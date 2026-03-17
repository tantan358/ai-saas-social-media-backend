"""Tests for the balanced monthly distribution engine."""

import pytest
from app.modules.planning.services.distribution_service import distribute_posts_across_weeks


def test_distribution_12():
    """12 -> [3, 3, 3, 3]"""
    result = distribute_posts_across_weeks(12)
    assert result == [3, 3, 3, 3]
    assert sum(result) == 12
    assert len(result) == 4


def test_distribution_13():
    """13 -> [3, 3, 3, 4]"""
    result = distribute_posts_across_weeks(13)
    assert result == [3, 3, 3, 4]
    assert sum(result) == 13
    assert len(result) == 4


def test_distribution_14():
    """14 -> [3, 4, 3, 4]"""
    result = distribute_posts_across_weeks(14)
    assert result == [3, 4, 3, 4]
    assert sum(result) == 14
    assert len(result) == 4


def test_distribution_15():
    """15 -> [4, 4, 3, 4]"""
    result = distribute_posts_across_weeks(15)
    assert result == [4, 4, 3, 4]
    assert sum(result) == 15
    assert len(result) == 4


def test_distribution_16():
    """16 -> [4, 4, 4, 4]"""
    result = distribute_posts_across_weeks(16)
    assert result == [4, 4, 4, 4]
    assert sum(result) == 16
    assert len(result) == 4


def test_no_week_is_empty_for_normal_range():
    """For total_posts in 12..20 (and nearby), no week has 0 posts."""
    for total in range(12, 21):
        result = distribute_posts_across_weeks(total)
        assert len(result) == 4
        assert sum(result) == total
        assert all(n >= 1 for n in result), f"total_posts={total} produced {result} with a zero week"


def test_always_four_weeks():
    """Always return exactly 4 numbers."""
    for total in [1, 4, 12, 13, 14, 15, 16, 20]:
        result = distribute_posts_across_weeks(total)
        assert len(result) == 4


def test_sum_equals_total():
    """Sum of distribution equals total_posts."""
    for total in [1, 3, 4, 12, 13, 14, 15, 16, 18, 20]:
        result = distribute_posts_across_weeks(total)
        assert sum(result) == total


def test_below_four_posts():
    """When total_posts < 4, represent as much as possible; trailing weeks may be 0."""
    result = distribute_posts_across_weeks(3)
    assert len(result) == 4
    assert sum(result) == 3
    assert result.count(1) == 3
    assert result.count(0) == 1
