from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ...database.core import get_db
from ...models.core import UserProfile, Task, FixedEvent, Plan, ScheduleBlock, User
from ...schemas.plan import PlanRequest, PlanResponse, DBPlan, DBPlanWithBlocks
from ..dependencies import get_current_user
from ...services.optimization_service import generate_weekly_plan
import json

router = APIRouter()

@router.get("/", response_model=List[DBPlan])
def get_plans(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Plan).filter(Plan.user_id == current_user.id).order_by(Plan.created_at.desc()).all()

@router.get("/{plan_id}", response_model=DBPlanWithBlocks)
def get_plan(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_plan = db.query(Plan).filter(Plan.id == plan_id, Plan.user_id == current_user.id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    blocks = db.query(ScheduleBlock).filter(ScheduleBlock.plan_id == plan_id, ScheduleBlock.user_id == current_user.id).all()
    
    # We can dynamically add blocks for the response
    plan_dict = {
        "id": db_plan.id,
        "user_id": db_plan.user_id,
        "week_start": db_plan.week_start,
        "completion_percentage": db_plan.completion_percentage,
        "objective_score": db_plan.objective_score,
        "created_at": db_plan.created_at,
        "warnings": db_plan.warnings,
        "blocks": blocks
    }
    return plan_dict


@router.post("/generate", response_model=PlanResponse)
def generate_plan(request: PlanRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile:
        profile = UserProfile(name=current_user.email.split("@")[0], user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    from ...models.core import TaskDependency
    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    events = db.query(FixedEvent).filter(FixedEvent.user_id == current_user.id).all()
    task_ids = [t.id for t in tasks]
    dependencies = db.query(TaskDependency).filter(TaskDependency.task_id.in_(task_ids)).all()

    # Fetch Dynamic Constraints
    from ...models.core import DynamicConstraint
    dynamic_constraints = db.query(DynamicConstraint).filter(
        DynamicConstraint.user_id == profile.user_id,
        DynamicConstraint.enabled == True
    ).all()

    # Generate Plan
    plan_data = generate_weekly_plan(profile, tasks, events, dependencies, dynamic_constraints)
    plan_data["week_start"] = request.week_start
    
    from ...services.validation_service import validate_schedule
    validate_schedule(plan_data, profile, events, tasks)
    
    # Save the plan to the database
    db_plan = Plan(
        user_id=current_user.id,
        week_start=request.week_start,
        completion_percentage=plan_data.get("completion_percentage", 0.0),
        objective_score=plan_data.get("objective_score", 0),
        warnings=json.dumps(plan_data.get("constraint_warnings", []))
    )
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    
    # Save the scheduled blocks
    for block in plan_data.get("scheduled_blocks", []):
        db_block = ScheduleBlock(
            user_id=current_user.id,
            plan_id=db_plan.id,
            date=block["date"],
            start_time=block["start_time"],
            end_time=block["end_time"],
            task_id=block.get("task_id"),
            block_type="task" if block.get("task_id") else "fixed"
        )
        db.add(db_block)
    db.commit()

    return plan_data
