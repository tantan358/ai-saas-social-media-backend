#!/usr/bin/env python3
"""
Seed/Demo Script for Nervia AI
Creates a demo tenant and owner user for testing
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.modules.auth.service import AuthService
from app.modules.auth.schemas import RegisterOwnerRequest
from app.modules.auth.security import create_access_token, create_refresh_token
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant
from app.modules.tenants.service import TenantService
from app.modules.tenants.schemas import TenantCreate
from app.modules.agencies.models import Agency
from app.modules.campaigns.service import CampaignService
from app.modules.campaigns.schemas import CampaignCreate
from app.modules.clients.models import Client
from app.modules.clients.service import ClientService
from app.modules.clients.schemas import ClientCreate
from app.modules.auth.security import get_password_hash


def seed_demo():
    """Create demo tenant and owner"""
    db: Session = SessionLocal()
    
    try:
        print("=" * 50)
        print("Nervia AI - Demo Seed Script")
        print("=" * 50)
        print()
        
        # Create demo tenant and owner
        owner_data = RegisterOwnerRequest(
            email="demo@nervia.ai",
            full_name="Demo Owner",
            password="DemoPass123",
            tenant_name="Demo Company",
            tenant_slug="demo-company"
        )
        
        print("Checking for existing demo tenant and owner...")
        
        # Check if tenant exists
        tenant = db.query(Tenant).filter(Tenant.slug == owner_data.tenant_slug).first()
        if tenant:
            print(f"⚠️  Tenant '{tenant.name}' already exists, using existing tenant...")
        else:
            print("Creating demo tenant...")
            tenant_data = TenantCreate(
                name=owner_data.tenant_name,
                slug=owner_data.tenant_slug
            )
            tenant = TenantService.create_tenant(db, tenant_data)
            print(f"✅ Tenant created: {tenant.name} (ID: {tenant.id})")
        
        # Get or create agency for this tenant
        agency = db.query(Agency).filter(
            Agency.tenant_id == tenant.id,
            Agency.slug == tenant.slug,
        ).first()
        if not agency:
            agency = Agency(
                tenant_id=tenant.id,
                name=tenant.name,
                slug=tenant.slug,
                is_active=True,
            )
            db.add(agency)
            db.commit()
            db.refresh(agency)
            print(f"✅ Agency created: {agency.name} (ID: {agency.id})")
        else:
            print(f"⚠️  Agency '{agency.name}' already exists, using existing agency...")
        
        # Check if user exists
        user = db.query(User).filter(User.email == owner_data.email).first()
        if user:
            print(f"⚠️  User '{user.email}' already exists, updating password...")
            # Update password
            user.hashed_password = get_password_hash(owner_data.password)
            user.full_name = owner_data.full_name
            if user.agency_id is None:
                user.agency_id = agency.id
            db.commit()
            db.refresh(user)
            print(f"✅ User updated: {user.email} (ID: {user.id})")
        else:
            print("Creating demo owner user...")
            from app.modules.auth.models import UserRole
            hashed_password = get_password_hash(owner_data.password)
            user = User(
                email=owner_data.email,
                hashed_password=hashed_password,
                full_name=owner_data.full_name,
                role=UserRole.ADMIN,
                tenant_id=tenant.id,
                agency_id=agency.id,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"✅ Owner created: {user.email} (ID: {user.id})")
        
        print(f"✅ Tenant created: {tenant.name} (ID: {tenant.id})")
        print(f"✅ Owner created: {user.email} (ID: {user.id})")
        print()
        
        # Create tokens
        access_token = create_access_token(data={"sub": user.id, "tenant_id": user.tenant_id})
        refresh_token = create_refresh_token(data={"sub": user.id})
        
        print("=" * 50)
        print("Demo Credentials")
        print("=" * 50)
        print(f"Email: {user.email}")
        print(f"Password: {owner_data.password}")
        print(f"Tenant: {tenant.name} ({tenant.slug})")
        print()
        print("Access Token:")
        print(access_token)
        print()
        print("Refresh Token:")
        print(refresh_token)
        print()
        
        # Get or create demo client for the agency
        client = db.query(Client).filter(Client.agency_id == agency.id).first()
        if not client:
            client = ClientService.create(db, agency.id, ClientCreate(name="Demo Client"))
            print(f"✅ Client created: {client.name} (ID: {client.id})")
        else:
            print(f"⚠️  Client '{client.name}' already exists, using existing client...")
        
        # Create a demo campaign
        print("Creating demo campaign...")
        campaign_data = CampaignCreate(
            name="Welcome Campaign",
            description="Demo campaign to get started",
            language="es",
            client_id=client.id,
        )
        campaign = CampaignService.create_campaign(
            db, campaign_data, agency.id, user.id
        )
        print(f"✅ Campaign created: {campaign.name} (ID: {campaign.id})")
        print()
        
        print("=" * 50)
        print("✅ Seed completed successfully!")
        print("=" * 50)
        print()
        print("You can now login with:")
        print(f"  Email: {user.email}")
        print(f"  Password: {owner_data.password}")
        print()
        print("Example curl commands:")
        print(f'  curl -X POST "http://localhost:8000/api/auth/login" \\')
        print(f'    -H "Content-Type: application/json" \\')
        print(f'    -d \'{{"email":"{user.email}","password":"{owner_data.password}"}}\'')
        print()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 1
    
    finally:
        db.close()
    
    return 0


if __name__ == "__main__":
    exit(seed_demo())
