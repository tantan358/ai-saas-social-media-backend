from pydantic import BaseModel
from typing import List, Dict, Any


class AIPlanResponse(BaseModel):
    plan: Dict[str, Any]


class PostGenerationRequest(BaseModel):
    campaign_plan: Dict[str, Any]
    language: str
