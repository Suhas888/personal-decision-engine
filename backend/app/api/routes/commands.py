from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import uuid
from datetime import datetime, timezone, timedelta

from ...database.core import get_db
from ...models.core import CommandConfirmation, Task, FixedEvent, UserProfile, Preference, User
from ...schemas.commands import Command, Operation, TargetType, Scope
from ...services.command_executor import CommandExecutor
from ...services.llm_service import parse_commands_from_text
from ...services.validators import CommandValidator

from ..dependencies import get_current_user

router = APIRouter()

class PreviewRequest(BaseModel):
    message: str

class ExecuteRequest(BaseModel):
    confirmation_id: Optional[str] = None
    commands: Optional[List[Command]] = None

def get_affected_count(db: Session, user_id: str, command: Command) -> int:
    """Preview affected count before deletion/update."""
    model_map = {
        TargetType.TASK: Task,
        TargetType.EVENT: FixedEvent,
        TargetType.PREFERENCE: Preference
    }
    
    target_model = model_map.get(command.target_type)
    if not target_model:
        return 0
        
    query = db.query(target_model).filter(target_model.user_id == user_id)
    
    if command.scope == Scope.SINGLE:
        # Simplification: we might not have a reliable way to get count for arbitrary title matches easily without executor logic
        # For destructive logic, this is often handled by ID or specific title.
        return 1
    elif command.scope == Scope.FILTERED and command.filters:
        # We run the actual SQLAlchemy filters the executor would run
        from ...services.command_executor import CommandExecutor
        executor = CommandExecutor(db, user_id)
        for f in command.filters:
            field_obj = executor._get_field(target_model, f.field)
            if field_obj is not None:
                query = executor._apply_filter(query, field_obj, f.operator, f.value)
            
    return query.count()

@router.post("/preview")
def preview_command(request: PreviewRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        commands = parse_commands_from_text(request.message)
    except HTTPException:
        raise  # propagate 429, 503, etc. unchanged
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
        
    validator = CommandValidator()
    validated_commands = []
    
    requires_confirmation = False
    total_affected = 0
    
    for cmd in commands:
        result = validator.validate([cmd])
        if not result.is_valid:
            raise HTTPException(status_code=422, detail=f"Validation failed: {result.errors}")
            
        if result.requires_confirmation:
            requires_confirmation = True
            
        validated_commands.append(cmd.model_dump())
        if cmd.operation in (Operation.DELETE, Operation.UPDATE):
            total_affected += get_affected_count(db, current_user.id, cmd)

    confirmation_id = None
    if requires_confirmation:
        confirmation_id = str(uuid.uuid4())
        conf = CommandConfirmation(
            id=confirmation_id,
            user_id=current_user.id,
            command_payload=validated_commands,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)
        )
        db.add(conf)
        db.commit()

    return {
        "commands": validated_commands,
        "summary": f"Interpreted {len(validated_commands)} command(s).",
        "requires_confirmation": requires_confirmation,
        "confirmation_id": confirmation_id,
        "affected_count": total_affected,
        "expires_at": conf.expires_at.isoformat() if requires_confirmation else None
    }

@router.post("/execute")
def execute_command(request: ExecuteRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    commands_to_execute = []
    
    if request.confirmation_id:
        # Atomic lock/select for update
        conf = db.query(CommandConfirmation).filter(
            CommandConfirmation.id == request.confirmation_id,
            CommandConfirmation.user_id == current_user.id
        ).with_for_update().first()
        
        if not conf:
            raise HTTPException(status_code=404, detail="Confirmation not found.")
            
        if conf.consumed:
            raise HTTPException(status_code=409, detail="Confirmation already consumed.")
            
        if datetime.now(timezone.utc) > conf.expires_at.replace(tzinfo=timezone.utc):
            raise HTTPException(status_code=409, detail="Confirmation expired.")
            
        conf.consumed = True
        db.commit()
        
        raw_commands = conf.command_payload
        commands_to_execute = [Command(**c) for c in raw_commands]
    elif request.commands:
        commands_to_execute = request.commands
        # Validate they don't require confirmation
        validator = CommandValidator()
        res = validator.validate(commands_to_execute)
        if not res.is_valid:
            raise HTTPException(status_code=422, detail=f"Validation failed: {res.errors}")
        if res.requires_confirmation:
            raise HTTPException(status_code=403, detail="Command requires explicit confirmation.")
    else:
        raise HTTPException(status_code=400, detail="Must provide confirmation_id or commands.")
        
    executor = CommandExecutor(db, current_user.id)
    results = []
    
    try:
        results = executor.execute(commands_to_execute)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"results": [r.__dict__ for r in results]}
