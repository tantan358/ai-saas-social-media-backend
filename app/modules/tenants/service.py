from sqlalchemy.orm import Session
from app.modules.tenants.models import Tenant
from app.modules.tenants.schemas import TenantCreate
from fastapi import HTTPException, status
import re


class TenantService:
    @staticmethod
    def create_tenant(db: Session, tenant_data: TenantCreate) -> Tenant:
        """Create a new tenant"""
        # Validate slug format
        if not re.match(r'^[a-z0-9-]+$', tenant_data.slug):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Slug must contain only lowercase letters, numbers, and hyphens"
            )
        
        # Check if slug exists
        existing = db.query(Tenant).filter(Tenant.slug == tenant_data.slug).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant slug already exists"
            )
        
        tenant = Tenant(
            name=tenant_data.name,
            slug=tenant_data.slug
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        return tenant
    
    @staticmethod
    def get_or_create_default_tenant(db: Session) -> Tenant:
        """Get or create default tenant (for MVP auto-registration)"""
        default_tenant = db.query(Tenant).filter(Tenant.slug == "default").first()
        if not default_tenant:
            default_tenant = Tenant(
                name="Default Tenant",
                slug="default"
            )
            db.add(default_tenant)
            db.commit()
            db.refresh(default_tenant)
        return default_tenant
    
    @staticmethod
    def get_tenant_by_id(db: Session, tenant_id: str) -> Tenant:
        """Get tenant by ID"""
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        return tenant
