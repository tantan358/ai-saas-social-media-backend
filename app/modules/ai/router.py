from fastapi import APIRouter
from app.modules.ai.schemas import AIPlanResponse

router = APIRouter(prefix="/ai", tags=["ai"])

# AI endpoints are primarily used internally by campaigns module
# Public endpoints can be added here if needed
