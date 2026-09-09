from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ...database.core import get_db
from ...models.core import UserProfile, Task, FixedEvent, Plan, ScheduleBlock, PlanHistory, User
from ...schemas.replan import ReplanParseRequest, ReplanApplyRequest, ReplanResponse
from ..dependencies import get_current_user
from ...services.llm_service import parse_schedule_change, ParsedChangeRequest
from ...services.optimization_service import generate_weekly_plan
import json

router = APIRouter()

@router.post("/parse", response_model=ParsedChangeRequest)
def parse_change(request: ReplanParseRequest):
    return parse_schedule_change(request.text)

@router.post("/apply", response_model=ReplanResponse)
def apply_replan(request: ReplanApplyRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 1. Load current user state
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile:
        profile = UserProfile(name=current_user.email.split("@")[0], user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        
    # 2. Apply the requested change transactionally using CommandExecutor
    from ...schemas.commands import Command, Operation, TargetType, Scope, CommandFilter, FilterField, FilterOperator
    from ...services.command_executor import CommandExecutor
    
    if request.target_name:
        target_type = TargetType.EVENT if request.target_type == "event" else TargetType.TASK
        target_name_lower = request.target_name.lower()
        
        if target_name_lower == "all":
            scope = Scope.ALL
            filters = []
        else:
            scope = Scope.FILTERED
            filters = [CommandFilter(field=FilterField.TITLE, operator=FilterOperator.CONTAINS, value=request.target_name)]
            
        cmd = None
        if request.action in ["cancel_event", "cancel_task", "delete_task"]:
            cmd = Command(operation=Operation.DELETE, target_type=target_type, scope=scope, filters=filters)
        elif request.action == "complete_task":
            cmd = Command(operation=Operation.UPDATE, target_type=target_type, scope=scope, filters=filters, payload={"completed": True})
        elif request.action == "change_duration" and request.new_value:
            try:
                cmd = Command(operation=Operation.UPDATE, target_type=target_type, scope=scope, filters=filters, payload={"estimated_minutes": int(request.new_value)})
            except ValueError:
                pass
                
        if cmd:
            executor = CommandExecutor(db, profile.user_id)
            executor.execute([cmd])
            # The executor commits the transaction on success

    # 3. Preserve the previous plan id
    previous_plan = db.query(Plan).filter(Plan.user_id == current_user.id).order_by(Plan.created_at.desc()).first()
    previous_plan_id = previous_plan.id if previous_plan else None

    # 4. Invoke the existing OR-Tools optimizer
    from ...models.core import TaskDependency, DynamicConstraint
    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    events = db.query(FixedEvent).filter(FixedEvent.user_id == current_user.id).all()
    task_ids = [t.id for t in tasks]
    dependencies = db.query(TaskDependency).filter(TaskDependency.task_id.in_(task_ids)).all()
    
    # Fetch Dynamic Constraints
    dynamic_constraints = db.query(DynamicConstraint).filter(
        DynamicConstraint.user_id == profile.user_id,
        DynamicConstraint.enabled == True
    ).all()

    # Phase 2: Run Optimizer
    plan_data = generate_weekly_plan(profile, tasks, events, dependencies, dynamic_constraints)
    plan_data["week_start"] = request.week_start
    
    from ...services.validation_service import validate_schedule
    validate_schedule(plan_data, profile, events, tasks)
    
    # 5. Save the new plan
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

    # 6. Create a PlanRevision record
    if previous_plan_id:
        history = PlanHistory(
            user_id=current_user.id,
            previous_plan_id=previous_plan_id,
            new_plan_id=db_plan.id,
            change_reason=request.human_readable_summary
        )
        db.add(history)
        db.commit()

    # 7. Return both the new plan and explanation
    return ReplanResponse(
        plan=plan_data,
        change_reason=request.human_readable_summary
    )
