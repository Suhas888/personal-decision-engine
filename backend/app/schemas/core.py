from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional


class UserProfileBase(BaseModel):
    name: str
    timezone: str = "UTC"
    preferred_start_hour: int = 540
    preferred_end_hour: int = 1020
    sleep_start: int = 1380
    sleep_end: int = 420
    max_focus_block_minutes: int = 120


class UserProfileCreate(UserProfileBase):
    pass


class UserProfile(UserProfileBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    estimated_minutes: int
    priority: int
    deadline: Optional[str] = None
    category: Optional[str] = None
    preferred_days: Optional[str] = None
    completed: bool = False
    energy_requirement: str = "any"
    continuous_only: bool = False
    dependencies: Optional[list[int]] = None
    
    @field_validator('estimated_minutes')
    def validate_estimated_minutes(cls, v):
        if v <= 0:
            raise ValueError("estimated_minutes must be greater than 0")
        return v
        
    @field_validator('priority')
    def validate_priority(cls, v):
        if v < 1 or v > 5:
            raise ValueError("priority must be between 1 and 5")
        return v


class TaskCreate(TaskBase):
    pass


class Task(TaskBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class PreferenceBase(BaseModel):
    key: str
    value: str


class PreferenceCreate(PreferenceBase):
    pass


class Preference(PreferenceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
