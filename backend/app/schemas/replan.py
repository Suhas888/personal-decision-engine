from pydantic import BaseModel
from typing import Optional
from .plan import PlanResponse

class ReplanParseRequest(BaseModel):
    text: str

class ReplanApplyRequest(BaseModel):
    action: str
    target_type: str
    target_name: Optional[str] = None
    new_value: Optional[str] = None
    human_readable_summary: str
    week_start: str = "2026-09-07" # Hardcoded for now based on current logic

class ReplanResponse(BaseModel):
    plan: PlanResponse
    change_reason: str
