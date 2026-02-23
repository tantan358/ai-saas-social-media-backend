import pytest
from app.modules.auth.service import AuthService
from app.modules.auth.schemas import UserCreate, UserLogin
from app.modules.tenants.service import TenantService


def test_register_user(db):
    """Test user registration"""
    # Create tenant first
    tenant = TenantService.get_or_create_default_tenant(db)
    
    user_data = UserCreate(
        email="test@example.com",
        full_name="Test User",
        password="TestPass123"
    )
    
    user = AuthService.register_user(db, user_data, tenant.id)
    
    assert user.email == "test@example.com"
    assert user.full_name == "Test User"
    assert user.tenant_id == tenant.id
    assert user.hashed_password != "TestPass123"  # Should be hashed


def test_authenticate_user(db):
    """Test user authentication"""
    tenant = TenantService.get_or_create_default_tenant(db)
    
    user_data = UserCreate(
        email="test@example.com",
        full_name="Test User",
        password="TestPass123"
    )
    
    # Register user
    user = AuthService.register_user(db, user_data, tenant.id)
    
    # Authenticate
    login_data = UserLogin(email="test@example.com", password="TestPass123")
    token = AuthService.authenticate_user(db, login_data)
    
    assert token.access_token is not None
    assert token.refresh_token is not None
    assert token.token_type == "bearer"


def test_authenticate_user_wrong_password(db):
    """Test authentication with wrong password"""
    tenant = TenantService.get_or_create_default_tenant(db)
    
    user_data = UserCreate(
        email="test@example.com",
        full_name="Test User",
        password="TestPass123"
    )
    
    AuthService.register_user(db, user_data, tenant.id)
    
    login_data = UserLogin(email="test@example.com", password="WrongPassword")
    
    with pytest.raises(Exception):  # Should raise HTTPException
        AuthService.authenticate_user(db, login_data)
