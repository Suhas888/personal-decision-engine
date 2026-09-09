from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from datetime import datetime


class FixedEventBase(BaseModel):
    title: str
    day_of_week: str
    start_time: int
    end_time: int
    recurring: bool = True


class FixedEventCreate(FixedEventBase):
    pass


class FixedEvent(FixedEventBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ScheduleBlock(BaseModel):
    task_id: Optional[int] = None
    task_title: Optional[str] = None
    date: str
    day: str
    start_time: int
    end_time: int
    duration_minutes: int
    explanation: Optional[str] = None


class PlanRequest(BaseModel):
    week_start: str


class PlanResponse(BaseModel):
    week_start: str
    scheduled_blocks: List[ScheduleBlock]
    unscheduled_tasks: List[dict]
    total_scheduled_minutes: int
    total_requested_minutes: int
    completion_percentage: float
    objective_score: int
    constraint_warnings: List[str]


from datetime import datetime

class DBScheduleBlock(BaseModel):
    id: int
    plan_id: int
    date: str
    start_time: int
    end_time: int
    task_id: Optional[int] = None
    block_type: str

    model_config = ConfigDict(from_attributes=True)

class DBPlan(BaseModel):
    id: int
    user_id: str
    week_start: str
    completion_percentage: float
    objective_score: int
    created_at: Any
    warnings: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DBPlanWithBlocks(DBPlan):
    blocks: List[DBScheduleBlock]
