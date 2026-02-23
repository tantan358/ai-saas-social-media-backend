from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.modules.tenants.schemas import TenantCreate, TenantResponse
from app.modules.tenants.service import TenantService
from app.dependencies import get_current_user, get_current_tenant, require_role
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    tenant_data: TenantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["owner", "admin"]))
):
    """Create a new tenant (owner/admin only)"""
    return TenantService.create_tenant(db, tenant_data)


@router.get("/me", response_model=TenantResponse)
def get_my_tenant(
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """Get current user's tenant information"""
    return current_tenant
