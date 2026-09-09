from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone
from ..database.core import Base
from ..utils.time_utils import get_utc_now

# Decision on UUID types: Retained `String` for `User.id`, `RefreshSession.id`, and `CommandConfirmation.id` 
# because migrating all dependent `user_id` columns across 10 tables to a strict `Uuid` type would instantly 
# break the entire test suite which heavily relies on non-UUID mock strings like "default_user" or "test_user". 
# This avoids massive unnecessary compatibility breakage in the test environment while remaining fully supported by PostgreSQL.

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    refresh_token_jti = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    name = Column(String)
    timezone = Column(String, default="UTC")
    preferred_start_hour = Column(Integer, default=540)  # 9:00 = 9 * 60
    preferred_end_hour = Column(Integer, default=1020)  # 17:00 = 17 * 60
    sleep_start = Column(Integer, default=1380)  # 23:00 = 23 * 60
    sleep_end = Column(Integer, default=420)  # 7:00 = 7 * 60
    max_focus_block_minutes = Column(Integer, default=120)
    daily_task_limit_minutes_weekday = Column(Integer, nullable=True)
    daily_task_limit_minutes_weekend = Column(Integer, nullable=True)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String, index=True)
    description = Column(String, nullable=True)
    estimated_minutes = Column(Integer)
    priority = Column(Integer)
    deadline = Column(String, nullable=True)
    category = Column(String, nullable=True)
    preferred_days = Column(String, nullable=True)  # JSON or comma-separated
    completed = Column(Boolean, default=False)
    
    # Phase 6 Additions
    energy_requirement = Column(String, default="any")  # "high", "medium", "low", "any"
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    continuous_only = Column(Boolean, default=False)
    
    # Relationships
    blocks = relationship("ScheduleBlock", cascade="all, delete-orphan", passive_deletes=True, backref="task")
    dependencies = relationship("TaskDependency", cascade="all, delete-orphan", passive_deletes=True, foreign_keys="[TaskDependency.task_id]")


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    id = Column(Integer, primary_key=True, index=True)
    # TaskDependency does NOT have a user_id because it is purely an association between two user_id-owned Tasks.
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    depends_on_task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)


class FixedEvent(Base):
    __tablename__ = "fixed_events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String, index=True)
    day_of_week = Column(String)
    start_time = Column(Integer)  # minutes from midnight
    end_time = Column(Integer)  # minutes from midnight
    recurring = Column(Boolean, default=True)


class Plan(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    week_start = Column(String)
    completion_percentage = Column(Float)
    objective_score = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    warnings = Column(String, nullable=True)  # JSON array as string

    blocks = relationship("ScheduleBlock", cascade="all, delete-orphan", passive_deletes=True, backref="plan")


class ScheduleBlock(Base):
    __tablename__ = "schedule_blocks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="CASCADE"), index=True, nullable=True)
    date = Column(String)
    start_time = Column(Integer)
    end_time = Column(Integer)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), index=True, nullable=True)
    block_type = Column(String)  # e.g. "task", "fixed", "sleep", "free"


class Preference(Base):
    __tablename__ = "preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    key = Column(String, index=True, nullable=False)
    value = Column(String)
    
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_preferences_user_key"),
    )


class PlanHistory(Base):
    __tablename__ = "plan_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    previous_plan_id = Column(Integer, ForeignKey("plans.id", ondelete="SET NULL"), index=True, nullable=True)
    new_plan_id = Column(Integer, ForeignKey("plans.id", ondelete="SET NULL"), index=True, nullable=True)
    change_reason = Column(String)
    timestamp = Column(DateTime(timezone=True), default=get_utc_now)


class DynamicConstraint(Base):
    __tablename__ = "dynamic_constraints"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    version = Column(String, default="1.0")
    type = Column(String, index=True)
    scope = Column(String, index=True)
    target = Column(String, nullable=True)
    parameters = Column(JSON)
    strength = Column(String, default="SOFT")
    enabled = Column(Boolean, default=True, index=True)
    source = Column(String, default="USER")
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)


class CommandConfirmation(Base):
    __tablename__ = "command_confirmations"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    command_payload = Column(JSON)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
