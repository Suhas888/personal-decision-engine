from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

class Operation(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

class TargetType(str, Enum):
    TASK = "TASK"
    EVENT = "EVENT"
    PREFERENCE = "PREFERENCE"

class Scope(str, Enum):
    SINGLE = "SINGLE"
    FILTERED = "FILTERED"
    ALL = "ALL"

class FilterField(str, Enum):
    TITLE = "TITLE"
    CATEGORY = "CATEGORY"
    DAY_OF_WEEK = "DAY_OF_WEEK"
    COMPLETED = "COMPLETED"
    DATE = "DATE"

class FilterOperator(str, Enum):
    EQ = "EQ"
    CONTAINS = "CONTAINS"
    GT = "GT"
    LT = "LT"
    IN = "IN"

from pydantic import BaseModel, Field, model_validator

class CommandFilter(BaseModel):
    field: FilterField
    operator: FilterOperator
    value: str
    
    @model_validator(mode='before')
    @classmethod
    def coerce_value(cls, data: Any) -> Any:
        if isinstance(data, dict) and 'value' in data:
            if isinstance(data['value'], bool):
                data['value'] = str(data['value'])
            elif isinstance(data['value'], int):
                data['value'] = str(data['value'])
        return data

class CommandPayload(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    estimated_minutes: Optional[int] = None
    priority: Optional[int] = None
    deadline: Optional[str] = None
    category: Optional[str] = None
    preferred_days: Optional[str] = None
    energy_requirement: Optional[str] = None
    completed: Optional[bool] = None
    day_of_week: Optional[str] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    
    @model_validator(mode='before')
    @classmethod
    def reject_extra_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            allowed = {'title', 'description', 'estimated_minutes', 'priority', 'deadline', 
                       'category', 'preferred_days', 'energy_requirement', 'completed', 
                       'day_of_week', 'start_time', 'end_time'}
            for k in data.keys():
                if k not in allowed:
                    raise ValueError(f"Field '{k}' is not allowed in CommandPayload")
        return data

class Command(BaseModel):
    operation: Operation
    target_type: TargetType
    scope: Scope
    filters: List[CommandFilter] = []
    payload: Optional[CommandPayload] = None

class ParsedChangeRequest(BaseModel):
    commands: List[Command]
    human_readable_summary: str
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    # Note: requires_confirmation and confirmation_token are determined by the backend Validator, NOT the LLM.
