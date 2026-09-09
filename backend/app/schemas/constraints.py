from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

class ConstraintScope(str, Enum):
    GLOBAL = "GLOBAL"
    CATEGORY = "CATEGORY"
    TASK = "TASK"

class ConstraintType(str, Enum):
    MAX_DAILY_HOURS = "MAX_DAILY_HOURS"
    AVOID_TIME = "AVOID_TIME"
    FORCE_DAY = "FORCE_DAY"
    MIN_GAP = "MIN_GAP"
    REQUIRE_ENERGY = "REQUIRE_ENERGY"
    
class ConstraintStrength(str, Enum):
    HARD = "HARD"
    SOFT = "SOFT"

class ConstraintSource(str, Enum):
    USER = "USER"
    AI = "AI"
    SYSTEM = "SYSTEM"

class MaxDailyHoursParams(BaseModel):
    max_minutes: int
    days: Optional[List[str]] = None

class AvoidTimeParams(BaseModel):
    start_minute: int
    end_minute: int
    days: Optional[List[str]] = None
    target: Optional[str] = None

class ForceDayParams(BaseModel):
    day: str
    target: str

class MinGapParams(BaseModel):
    gap_minutes: int
    target: str

class RequireEnergyParams(BaseModel):
    required_energy: str
    target: str

class ConstraintIR(BaseModel):
    version: str = "1.0"
    type: ConstraintType
    scope: ConstraintScope
    target_identifier: Optional[str] = None
    # Use a generic dict here for the top-level schema to catch all from Gemini, 
    # but we will validate it into the specific Param models in the Validator layer.
    parameters: Dict[str, Any] 
    strength: ConstraintStrength = ConstraintStrength.SOFT
