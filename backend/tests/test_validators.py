import pytest
from app.schemas.commands import Command, Operation, TargetType, Scope, FilterField, FilterOperator, CommandFilter
from app.schemas.constraints import ConstraintIR, ConstraintType, ConstraintScope, ConstraintStrength
from app.services.validators import CommandValidator, ConstraintValidator, ConstraintConflictDetector

def test_command_validator_requires_confirmation():
    validator = CommandValidator()
    # DELETE ALL
    cmd1 = Command(operation=Operation.DELETE, target_type=TargetType.TASK, scope=Scope.ALL)
    # DELETE FILTERED
    cmd2 = Command(operation=Operation.DELETE, target_type=TargetType.TASK, scope=Scope.FILTERED, filters=[
        CommandFilter(field=FilterField.COMPLETED, operator=FilterOperator.EQ, value=True)
    ])
    # DELETE SINGLE (no confirmation required for single task usually, based on current rules, wait actually our rule said "DELETE ALL, DELETE FILTERED, and large/bulk UPDATE operations MUST require explicit user confirmation.")
    cmd3 = Command(operation=Operation.DELETE, target_type=TargetType.TASK, scope=Scope.SINGLE, filters=[
        CommandFilter(field=FilterField.TITLE, operator=FilterOperator.EQ, value="Homework")
    ])

    res = validator.validate([cmd1])
    assert res.is_valid
    assert res.requires_confirmation is True

    res2 = validator.validate([cmd2])
    assert res2.is_valid
    assert res2.requires_confirmation is True
    
    res3 = validator.validate([cmd3])
    assert res3.is_valid
    assert res3.requires_confirmation is False

def test_command_validator_invalid_field():
    validator = CommandValidator()
    cmd = Command(operation=Operation.READ, target_type=TargetType.PREFERENCE, scope=Scope.ALL, filters=[
        CommandFilter(field=FilterField.COMPLETED, operator=FilterOperator.EQ, value=True)
    ])
    res = validator.validate([cmd])
    assert not res.is_valid
    assert "FilterField FilterField.COMPLETED is not allowed for TargetType TargetType.PREFERENCE." in res.errors[0]

def test_constraint_validator_valid():
    validator = ConstraintValidator()
    c = ConstraintIR(
        type=ConstraintType.MAX_DAILY_HOURS,
        scope=ConstraintScope.GLOBAL,
        parameters={"max_minutes": 300, "days": ["Monday"]}
    )
    res = validator.validate([c])
    assert res.is_valid
    assert len(res.validated_data) == 1

def test_constraint_validator_invalid_params():
    validator = ConstraintValidator()
    # Missing max_minutes
    c = ConstraintIR(
        type=ConstraintType.MAX_DAILY_HOURS,
        scope=ConstraintScope.GLOBAL,
        parameters={"days": ["Monday"]}
    )
    res = validator.validate([c])
    assert not res.is_valid
    assert "Parameter validation failed" in res.errors[0]
    
def test_constraint_validator_scope_mismatch():
    validator = ConstraintValidator()
    c = ConstraintIR(
        type=ConstraintType.MAX_DAILY_HOURS,
        scope=ConstraintScope.TASK,
        parameters={"max_minutes": 300}
        # missing target_identifier
    )
    res = validator.validate([c])
    assert not res.is_valid
    assert "TASK scope requires a target_identifier" in res.errors[0]

def test_constraint_conflict_detector():
    detector = ConstraintConflictDetector()
    c1 = ConstraintIR(
        type=ConstraintType.MAX_DAILY_HOURS,
        scope=ConstraintScope.GLOBAL,
        parameters={"max_minutes": 300, "days": ["Monday"]}
    )
    c2 = ConstraintIR(
        type=ConstraintType.MAX_DAILY_HOURS,
        scope=ConstraintScope.GLOBAL,
        parameters={"max_minutes": 400, "days": ["Monday"]}
    )
    res = detector.detect([c1, c2])
    assert not res.is_valid
    assert "Multiple GLOBAL MAX_DAILY_HOURS for day Monday with different limits" in res.errors[0]
