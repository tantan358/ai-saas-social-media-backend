from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.modules.auth.schemas import UserCreate, UserLogin, Token, UserResponse, RegisterOwnerRequest
from app.modules.auth.service import AuthService
from app.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.tenants.schemas import TenantResponse
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RegisterOwnerResponse(BaseModel):
    user: UserResponse
    tenant: TenantResponse
    tokens: Token


@router.post("/register-owner", response_model=RegisterOwnerResponse, status_code=status.HTTP_201_CREATED)
def register_owner(
    owner_data: RegisterOwnerRequest,
    db: Session = Depends(get_db)
):
    """Register owner - creates tenant and owner user, returns tokens"""
    user, tenant = AuthService.register_owner(db, owner_data)
    
    # Create tokens
    from app.modules.auth.security import create_access_token, create_refresh_token
    access_token = create_access_token(data={"sub": user.id, "tenant_id": user.tenant_id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    tokens = Token(access_token=access_token, refresh_token=refresh_token)
    
    return RegisterOwnerResponse(
        user=UserResponse.model_validate(user),
        tenant=TenantResponse.model_validate(tenant),
        tokens=tokens
    )


@router.post("/login", response_model=Token)
def login(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """Login and get access/refresh tokens"""
    return AuthService.authenticate_user(db, login_data)


@router.post("/refresh", response_model=Token)
def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Refresh access token"""
    return AuthService.refresh_access_token(db, request.refresh_token)


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return current_user
