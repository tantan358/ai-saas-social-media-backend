import pytest
from app.modules.campaigns.service import CampaignService
from app.modules.campaigns.schemas import CampaignCreate
from app.modules.tenants.service import TenantService
from app.modules.auth.service import AuthService
from app.modules.auth.schemas import UserCreate


def test_create_campaign(db):
    """Test campaign creation"""
    tenant = TenantService.get_or_create_default_tenant(db)
    
    user_data = UserCreate(
        email="test@example.com",
        full_name="Test User",
        password="TestPass123"
    )
    user = AuthService.register_user(db, user_data, tenant.id)
    
    campaign_data = CampaignCreate(
        name="Test Campaign",
        description="Test Description",
        language="es"
    )
    
    campaign = CampaignService.create_campaign(
        db, campaign_data, tenant.id, user.id
    )
    
    assert campaign.name == "Test Campaign"
    assert campaign.description == "Test Description"
    assert campaign.language == "es"
    assert campaign.tenant_id == tenant.id
