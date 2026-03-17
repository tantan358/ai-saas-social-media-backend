import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@pytest.mark.skip(reason="Requires seeded database with campaigns and posts")
def test_schedule_auto_uses_defaults_when_no_custom_windows():
    """
    Test case 1:
    campaign has approved_final posts and no custom windows.
    Expected: uses defaults and schedules successfully.
    """
    campaign_id = "REPLACE_WITH_CAMPAIGN_ID_WITH_APPROVED_POSTS_NO_WINDOWS"
    response = client.post(f"/api/campaigns/{campaign_id}/schedule-auto")
    assert response.status_code == 200
    data = response.json()
    assert data["assigned_count"] > 0
    # At least one scheduled_at per post in response
    for week in data["by_week"]:
        for day in week["by_date"]:
            for post in day["posts"]:
                assert post["scheduled_at"] is not None


@pytest.mark.skip(reason="Requires seeded database with campaigns and posts")
def test_schedule_auto_no_approved_posts_returns_422():
    """
    Test case 2:
    campaign has no approved_final posts.
    Expected: 422 clear error.
    """
    campaign_id = "REPLACE_WITH_CAMPAIGN_ID_WITHOUT_APPROVED_POSTS"
    response = client.post(f"/api/campaigns/{campaign_id}/schedule-auto")
    assert response.status_code == 422
    assert "approved_final" in response.json()["detail"]


@pytest.mark.skip(reason="Requires seeded database with campaigns and posts")
def test_schedule_auto_invalid_status_returns_409():
    """
    Test case 3:
    campaign invalid status.
    Expected: 409 clear error.
    """
    campaign_id = "REPLACE_WITH_CAMPAIGN_ID_INVALID_STATUS"
    response = client.post(f"/api/campaigns/{campaign_id}/schedule-auto")
    assert response.status_code == 409
    assert "valid status" in response.json()["detail"]

import pytest
from fastapi.testclient import TestClient

from app.modules.campaigns.models import CampaignStatus, PostStatus, PostPlatform, Campaign, MonthlyPlan, Post
from app.modules.tenants.service import TenantService
from app.modules.auth.service import AuthService
from app.modules.auth.schemas import UserCreate
from app.modules.campaigns.schemas import CampaignCreate


def _create_basic_campaign_with_user(db):
    tenant = TenantService.get_or_create_default_tenant(db)
    user_data = UserCreate(
        email="schedule-test@example.com",
        full_name="Schedule Test User",
        password="TestPass123",
    )
    user = AuthService.register_user(db, user_data, tenant.id)

    # Use the first client for this tenant's default agency to satisfy required client_id
    from app.modules.clients.models import Client

    client = (
        db.query(Client)
        .filter(Client.agency_id == tenant.default_agency_id)
        .first()
    )
    if not client:
        # Create a minimal client for testing if none exists
        from app.modules.clients.models import Client as ClientModel

        client = ClientModel(
            tenant_id=tenant.id,
            agency_id=tenant.default_agency_id,
            name="Test Client",
        )
        db.add(client)
        db.flush()

    campaign_data = CampaignCreate(
        name="Schedule Auto Campaign",
        description="Schedule auto test",
        language="es",
        client_id=client.id,
    )
    from app.modules.campaigns.service import CampaignService

    campaign = CampaignService.create_campaign(db, campaign_data, tenant.id, user.id)
    return tenant, user, campaign


def _add_plan_and_posts(db, campaign, num_posts=2, status=PostStatus.APPROVED_FINAL, platform=PostPlatform.LINKEDIN):
    plan = MonthlyPlan(
        campaign_id=campaign.id,
        total_posts=num_posts,
    )
    db.add(plan)
    db.flush()
    for i in range(num_posts):
        post = Post(
            tenant_id=campaign.tenant_id,
            campaign_id=campaign.id,
            monthly_plan_id=plan.id,
            week_number=1,
            title=f"Post {i+1}",
            content="Test content",
            platform=platform,
            status=status,
        )
        db.add(post)
    db.commit()
    db.refresh(campaign)
    return plan


def test_schedule_auto_uses_default_windows_when_no_custom_windows(db, client: TestClient):
    """
    Test case 1:
    campaign has approved_final posts and no custom windows
    Expected: uses defaults and schedules successfully.
    """
    tenant, user, campaign = _create_basic_campaign_with_user(db)
    # Mark campaign as planning_approved
    campaign.status = CampaignStatus.PLANNING_APPROVED
    db.commit()
    db.refresh(campaign)

    # Add approved_final posts, no custom windows created
    _add_plan_and_posts(db, campaign, num_posts=3, status=PostStatus.APPROVED_FINAL, platform=PostPlatform.LINKEDIN)

    # Call debug endpoint to see diagnostics and ensure default windows are used
    resp = client.get(f"/api/campaigns/{campaign.id}/schedule-auto-debug")
    assert resp.status_code == 200
    data = resp.json()

    assert data["campaign_id"] == campaign.id
    assert data["success"] is True
    assert data["approved_final_posts"] == 3
    # No custom windows; default windows for linkedin should be present/used
    assert data["custom_windows_by_platform"].get("linkedin", 0) == 0
    assert data["default_windows_by_platform"].get("linkedin", 0) > 0
    assert data["assigned_count"] == 3
    assert len(data["scheduled_datetimes"]) == 3


def test_schedule_auto_returns_422_when_no_approved_posts(db, client: TestClient):
    """
    Test case 2:
    campaign has no approved_final posts
    Expected: 422 clear error.
    """
    tenant, user, campaign = _create_basic_campaign_with_user(db)
    campaign.status = CampaignStatus.PLANNING_APPROVED
    db.commit()
    db.refresh(campaign)

    # Add generated posts only, not approved_final
    _add_plan_and_posts(db, campaign, num_posts=2, status=PostStatus.GENERATED, platform=PostPlatform.LINKEDIN)

    resp = client.post(f"/api/campaigns/{campaign.id}/schedule-auto", json={"plan_start_date": None})
    assert resp.status_code == 422
    data = resp.json()
    assert "no approved_final posts" in data["detail"]


def test_schedule_auto_returns_409_for_invalid_campaign_status(db, client: TestClient):
    """
    Test case 3:
    campaign invalid status
    Expected: 409 clear error.
    """
    tenant, user, campaign = _create_basic_campaign_with_user(db)
    # Leave campaign in DRAFT status (invalid for auto scheduling)
    db.refresh(campaign)
    assert campaign.status == CampaignStatus.DRAFT

    resp = client.post(f"/api/campaigns/{campaign.id}/schedule-auto", json={"plan_start_date": None})
    assert resp.status_code == 409
    data = resp.json()
    assert "not in a valid state for auto-scheduling" in data["detail"]

