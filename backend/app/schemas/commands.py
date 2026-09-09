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

class CommandFilter(BaseModel):
    field: FilterField
    operator: FilterOperator
    value: Any

class Command(BaseModel):
    operation: Operation
    target_type: TargetType
    scope: Scope
    filters: List[CommandFilter] = []
    payload: Optional[Dict[str, Any]] = None

class ParsedChangeRequest(BaseModel):
    commands: List[Command]
    human_readable_summary: str
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    # Note: requires_confirmation and confirmation_token are determined by the backend Validator, NOT the LLM.
