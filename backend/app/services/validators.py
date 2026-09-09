from typing import List, Dict, Any
from ..schemas.commands import Command, Operation, TargetType, Scope, FilterField, FilterOperator
from ..schemas.constraints import (
    ConstraintIR, ConstraintType, ConstraintScope, 
    MaxDailyHoursParams, AvoidTimeParams, ForceDayParams, 
    MinGapParams, RequireEnergyParams
)
from pydantic import ValidationError

class ValidationResult:
    def __init__(self, is_valid: bool, errors: List[str], requires_confirmation: bool = False, validated_data: Any = None):
        self.is_valid = is_valid
        self.errors = errors
        self.requires_confirmation = requires_confirmation
        self.validated_data = validated_data # Can hold strictly typed constraints after validation

class CommandValidator:
    def validate(self, commands: List[Command]) -> ValidationResult:
        errors = []
        requires_confirmation = False

        allowed_fields = {
            TargetType.TASK: [FilterField.TITLE, FilterField.CATEGORY, FilterField.DAY_OF_WEEK, FilterField.COMPLETED, FilterField.DATE],
            TargetType.EVENT: [FilterField.TITLE, FilterField.DAY_OF_WEEK, FilterField.DATE],
            TargetType.PREFERENCE: [] # Usually single scope
        }

        for i, cmd in enumerate(commands):
            # 1. Scope/Confirmation Validation
            # Per architecture: DELETE ALL, DELETE FILTERED, and bulk (ALL/FILTERED) UPDATE
            # require explicit user confirmation. SINGLE-scope DELETE does not.
            if cmd.operation in [Operation.DELETE, Operation.UPDATE] and cmd.scope in [Scope.ALL, Scope.FILTERED]:
                requires_confirmation = True

            # 2. Target/Field Validation
            allowed = allowed_fields.get(cmd.target_type, [])
            for f in cmd.filters:
                if f.field not in allowed:
                    errors.append(f"Command {i}: FilterField {f.field} is not allowed for TargetType {cmd.target_type}.")

            # 3. Payload Validation
            if cmd.operation in [Operation.CREATE, Operation.UPDATE]:
                if not cmd.payload:
                    errors.append(f"Command {i}: {cmd.operation} requires a payload.")

            if cmd.operation == Operation.CREATE and cmd.scope != Scope.SINGLE:
                errors.append(f"Command {i}: CREATE must use SINGLE scope.")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, requires_confirmation=requires_confirmation)


class ConstraintValidator:
    def validate(self, constraints: List[ConstraintIR]) -> ValidationResult:
        errors = []
        validated_constraints = []

        param_models = {
            ConstraintType.MAX_DAILY_HOURS: MaxDailyHoursParams,
            ConstraintType.AVOID_TIME: AvoidTimeParams,
            ConstraintType.FORCE_DAY: ForceDayParams,
            ConstraintType.MIN_GAP: MinGapParams,
            ConstraintType.REQUIRE_ENERGY: RequireEnergyParams
        }

        for i, c in enumerate(constraints):
            # 1. Validate Target based on Scope
            if c.scope in [ConstraintScope.CATEGORY, ConstraintScope.TASK]:
                if not c.target_identifier:
                    errors.append(f"Constraint {i} ({c.type}): {c.scope} scope requires a target_identifier.")
            elif c.scope == ConstraintScope.GLOBAL:
                if c.target_identifier:
                    errors.append(f"Constraint {i} ({c.type}): GLOBAL scope should not have a target_identifier.")

            # 2. Strict Parameter Validation
            model_class = param_models.get(c.type)
            if not model_class:
                errors.append(f"Constraint {i}: Unsupported ConstraintType {c.type}.")
                continue

            try:
                # Instantiate the Pydantic model to enforce types and required fields
                validated_params = model_class(**c.parameters)
                
                # Create a new verified IR to return
                verified_c = ConstraintIR(
                    version=c.version,
                    type=c.type,
                    scope=c.scope,
                    target_identifier=c.target_identifier,
                    parameters=validated_params.model_dump(),
                    strength=c.strength
                )
                validated_constraints.append(verified_c)
            except ValidationError as e:
                errors.append(f"Constraint {i} ({c.type}): Parameter validation failed - {str(e)}")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, validated_data=validated_constraints)


class ConstraintConflictDetector:
    def detect(self, constraints: List[ConstraintIR]) -> ValidationResult:
        errors = []
        
        # We need to detect logical conflicts.
        # Example 1: Multiple GLOBAL MAX_DAILY_HOURS for the same day with different limits
        max_daily_global = {}
        
        # Example 2: FORCE_DAY for a task conflicting with AVOID_TIME for that whole day?
        # A bit complex, but let's do multiple FORCE_DAY on the same task.
        task_forced_days = {}

        for c in constraints:
            if c.type == ConstraintType.MAX_DAILY_HOURS and c.scope == ConstraintScope.GLOBAL:
                days = c.parameters.get("days") or ["ALL"]
                limit = c.parameters.get("max_minutes", 0)
                for d in days:
                    if d in max_daily_global and max_daily_global[d] != limit:
                        errors.append(f"Conflict: Multiple GLOBAL MAX_DAILY_HOURS for day {d} with different limits ({max_daily_global[d]} vs {limit}).")
                    max_daily_global[d] = limit

            if c.type == ConstraintType.FORCE_DAY and c.scope == ConstraintScope.TASK:
                t_id = c.target_identifier
                day = c.parameters.get("day")
                if t_id in task_forced_days and task_forced_days[t_id] != day:
                    errors.append(f"Conflict: Task '{t_id}' is forced to multiple different days ({task_forced_days[t_id]} vs {day}).")
                task_forced_days[t_id] = day

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
