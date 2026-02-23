from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.modules.tenants.models import Tenant


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and validate tenant from request"""
    
    async def dispatch(self, request: Request, call_next):
        # Skip tenant check for auth endpoints
        if request.url.path.startswith("/api/auth") or request.url.path.startswith("/docs"):
            response = await call_next(request)
            return response
        
        # For authenticated requests, tenant is set via user dependency
        # This middleware can be extended for subdomain-based tenant resolution
        response = await call_next(request)
        return response
