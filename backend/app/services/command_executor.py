from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from ..schemas.commands import Command, Operation, TargetType, Scope, FilterField, FilterOperator
from ..models.core import Task, FixedEvent, Preference
from .validators import CommandValidator

class ExecutionResult:
    def __init__(self, operation: Operation, target_type: TargetType, scope: Scope, affected_count: int, success: bool, error: Optional[str] = None):
        self.operation = operation
        self.target_type = target_type
        self.scope = scope
        self.affected_count = affected_count
        self.success = success
        self.error = error

class CommandExecutor:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.validator = CommandValidator()

    def _get_model(self, target_type: TargetType):
        if target_type == TargetType.TASK:
            return Task
        elif target_type == TargetType.EVENT:
            return FixedEvent
        elif target_type == TargetType.PREFERENCE:
            return Preference
        raise ValueError(f"Unsupported target type: {target_type}")

    def _get_field(self, model, field: FilterField):
        if model == Task:
            mapping = {
                FilterField.TITLE: Task.title,
                FilterField.CATEGORY: Task.category,
                FilterField.DAY_OF_WEEK: Task.preferred_days,
                FilterField.COMPLETED: Task.completed,
                FilterField.DATE: Task.deadline,
            }
            return mapping.get(field)
        elif model == FixedEvent:
            mapping = {
                FilterField.TITLE: FixedEvent.title,
                FilterField.DAY_OF_WEEK: FixedEvent.day_of_week,
                # DATE not strictly on FixedEvent in the same way, but let's map it safely or ignore
            }
            return mapping.get(field)
        return None

    def _apply_filter(self, query, field_obj, operator: FilterOperator, value: Any):
        if field_obj is Task.completed and isinstance(value, str):
            value = value.lower() in ("true", "1", "t", "y", "yes")
            
        if operator == FilterOperator.EQ:
            return query.filter(field_obj == value)
        elif operator == FilterOperator.CONTAINS:
            return query.filter(field_obj.ilike(f"%{value}%"))
        elif operator == FilterOperator.GT:
            return query.filter(field_obj > value)
        elif operator == FilterOperator.LT:
            return query.filter(field_obj < value)
        elif operator == FilterOperator.IN:
            return query.filter(field_obj.in_(value))
        return query

    def _validate_payload(self, target_type: TargetType, payload: Dict[str, Any]):
        allowed_keys = set()
        if target_type == TargetType.TASK:
            allowed_keys = {"title", "description", "estimated_minutes", "priority", "deadline", "category", "preferred_days", "completed", "energy_requirement", "continuous_only"}
        elif target_type == TargetType.EVENT:
            allowed_keys = {"title", "day_of_week", "start_time", "end_time", "recurring"}
        elif target_type == TargetType.PREFERENCE:
            allowed_keys = {"key", "value"}
        
        for k in payload.keys():
            if k not in allowed_keys:
                raise ValueError(f"Field '{k}' is not allowed for {target_type}")

    def execute(self, commands: List[Command]) -> List[ExecutionResult]:
        # 1. Validate commands structurally
        validation = self.validator.validate(commands)
        if not validation.is_valid:
            raise ValueError(f"Command validation failed: {validation.errors}")

        results = []
        try:
            for cmd in commands:
                model = self._get_model(cmd.target_type)
                
                # Enforce user isolation
                query = self.db.query(model).filter(model.user_id == self.user_id)
                
                # Apply explicit filters safely
                if cmd.scope in [Scope.SINGLE, Scope.FILTERED]:
                    for f in cmd.filters:
                        field_obj = self._get_field(model, f.field)
                        if field_obj is None:
                            raise ValueError(f"Field mapping not found for {f.field} on {cmd.target_type}")
                        query = self._apply_filter(query, field_obj, f.operator, f.value)

                affected = 0
                if cmd.operation == Operation.DELETE:
                    affected = query.delete()
                elif cmd.operation == Operation.UPDATE:
                    if not cmd.payload:
                        raise ValueError("Payload required for UPDATE")
                    payload_dict = cmd.payload.model_dump(exclude_unset=True)
                    self._validate_payload(cmd.target_type, payload_dict)
                    affected = query.update(payload_dict)
                elif cmd.operation == Operation.READ:
                    affected = query.count()
                elif cmd.operation == Operation.CREATE:
                    if not cmd.payload:
                        raise ValueError("Payload required for CREATE")
                    payload_dict = cmd.payload.model_dump(exclude_unset=True)
                    self._validate_payload(cmd.target_type, payload_dict)
                    new_obj = model(user_id=self.user_id, **payload_dict)
                    self.db.add(new_obj)
                    self.db.flush()
                    affected = 1
                
                results.append(ExecutionResult(
                    operation=cmd.operation,
                    target_type=cmd.target_type,
                    scope=cmd.scope,
                    affected_count=affected,
                    success=True
                ))
            
            # 3. Commit Transaction
            self.db.commit()
            return results

        except Exception as e:
            self.db.rollback()
            # If a single command fails, the whole transaction rolls back, return the failure
            return [ExecutionResult(
                operation=Operation.READ, # dummy
                target_type=TargetType.TASK, # dummy
                scope=Scope.SINGLE, # dummy
                affected_count=0,
                success=False,
                error=str(e)
            )]
