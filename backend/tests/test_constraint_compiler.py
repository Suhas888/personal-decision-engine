import pytest
from ortools.sat.python import cp_model
from app.schemas.constraints import ConstraintIR, ConstraintType, ConstraintScope, ConstraintStrength
from app.services.constraint_compiler import ConstraintCompiler

class MockTask:
    def __init__(self, id, title, category):
        self.id = id
        self.title = title
        self.category = category

@pytest.fixture
def compiler_setup():
    model = cp_model.CpModel()
    
    tasks = [
        MockTask(1, "Deep Work", "coding"),
        MockTask(2, "Emails", "admin"),
        MockTask(3, "Planning", "admin")
    ]
    
    task_vars = {}
    for t in tasks:
        # Create block mock: (is_sched, start_var, end_var, interval_var, dur, is_energy, base_wt)
        is_sched = model.NewBoolVar(f"sched_{t.id}")
        start_var = model.NewIntVar(0, 7 * 24 * 60, f"start_{t.id}")
        end_var = model.NewIntVar(0, 7 * 24 * 60, f"end_{t.id}")
        dur = 60
        model.Add(end_var == start_var + dur)
        task_vars[t.id] = [(is_sched, start_var, end_var, None, dur, None, 100)]
        
    compiler = ConstraintCompiler(model, tasks, task_vars, relative_today_idx=0) # Assume today is Monday
    return model, compiler, is_sched, start_var

def solve(model):
    solver = cp_model.CpSolver()
    return solver, solver.Solve(model)

def test_max_daily_hours_hard(compiler_setup):
    model, compiler, _, _ = compiler_setup
    
    c = ConstraintIR(
        type=ConstraintType.MAX_DAILY_HOURS,
        scope=ConstraintScope.GLOBAL,
        parameters={"max_minutes": 30, "days": ["Monday"]},
        strength=ConstraintStrength.HARD
    )
    
    # We have 3 tasks, 60 minutes each. If all scheduled on Monday, that's 180 minutes.
    # We constrain max_minutes to 30.
    # Therefore, no more than 0 tasks can be scheduled on Monday.
    # Let's force them to be scheduled on Monday and see it fail.
    for t_id, blocks in compiler.task_vars.items():
        model.Add(blocks[0][0] == 1) # Force schedule
        model.Add(blocks[0][1] == 60) # Force Monday (offset 0, minute 60)
        
    compiler.compile([c])
    
    solver, status = solve(model)
    assert status == cp_model.INFEASIBLE

def test_avoid_time_hard(compiler_setup):
    model, compiler, _, _ = compiler_setup
    
    c = ConstraintIR(
        type=ConstraintType.AVOID_TIME,
        scope=ConstraintScope.TASK,
        target_identifier="Deep Work",
        parameters={"start_minute": 600, "end_minute": 720, "days": ["Monday"]},
        strength=ConstraintStrength.HARD
    )
    
    # Deep work is Task 1. Force it into the avoid time.
    blocks = compiler.task_vars[1]
    model.Add(blocks[0][0] == 1)
    model.Add(blocks[0][1] == 660) # Inside [600, 720]
    model.Add(blocks[0][2] == 720) 
    
    compiler.compile([c])
    
    solver, status = solve(model)
    assert status == cp_model.INFEASIBLE

def test_force_day_hard(compiler_setup):
    model, compiler, _, _ = compiler_setup
    
    c = ConstraintIR(
        type=ConstraintType.FORCE_DAY,
        scope=ConstraintScope.CATEGORY,
        target_identifier="admin",
        parameters={"day": "Tuesday", "target": "admin"},
        strength=ConstraintStrength.HARD
    )
    
    # Force admin task to Monday
    blocks = compiler.task_vars[2]
    model.Add(blocks[0][0] == 1)
    model.Add(blocks[0][1] == 100) # Monday
    
    compiler.compile([c])
    
    solver, status = solve(model)
    assert status == cp_model.INFEASIBLE

def test_min_gap_hard(compiler_setup):
    model, compiler, _, _ = compiler_setup
    
    c = ConstraintIR(
        type=ConstraintType.MIN_GAP,
        scope=ConstraintScope.CATEGORY,
        target_identifier="admin",
        parameters={"gap_minutes": 120, "target": "admin"},
        strength=ConstraintStrength.HARD
    )
    
    # Tasks 2 and 3 are admin. Force them to be adjacent (gap = 0).
    b2 = compiler.task_vars[2]
    b3 = compiler.task_vars[3]
    
    model.Add(b2[0][0] == 1)
    model.Add(b3[0][0] == 1)
    model.Add(b2[0][2] == 100)
    model.Add(b3[0][1] == 100) # adjacent
    
    compiler.compile([c])
    
    solver, status = solve(model)
    assert status == cp_model.INFEASIBLE

def test_require_energy_hard(compiler_setup):
    model, compiler, _, _ = compiler_setup
    
    c = ConstraintIR(
        type=ConstraintType.REQUIRE_ENERGY,
        scope=ConstraintScope.TASK,
        target_identifier="Deep Work",
        parameters={"required_energy": "high", "target": "Deep Work"},
        strength=ConstraintStrength.HARD
    )
    
    # High energy is 420-660. Force it to 800 (medium).
    b1 = compiler.task_vars[1]
    model.Add(b1[0][0] == 1)
    model.Add(b1[0][1] == 800)
    
    compiler.compile([c])
    
    solver, status = solve(model)
    assert status == cp_model.INFEASIBLE

def test_soft_constraint_does_not_break_feasibility(compiler_setup):
    model, compiler, _, _ = compiler_setup
    
    c = ConstraintIR(
        type=ConstraintType.AVOID_TIME,
        scope=ConstraintScope.TASK,
        target_identifier="Deep Work",
        parameters={"start_minute": 600, "end_minute": 720, "days": ["Monday"]},
        strength=ConstraintStrength.SOFT
    )
    
    blocks = compiler.task_vars[1]
    model.Add(blocks[0][0] == 1)
    model.Add(blocks[0][1] == 660) # Inside [600, 720]
    model.Add(blocks[0][2] == 720) 
    
    res = compiler.compile([c])
    assert res.compiled_count == 1
    
    # Add objective to maximize
    model.Maximize(sum(res.objective_terms))
    
    solver, status = solve(model)
    # The soft constraint should NOT make it infeasible
    assert status == cp_model.OPTIMAL
    # The objective should be heavily penalized (negative)
    assert solver.ObjectiveValue() < 0

def test_unsupported_energy(compiler_setup):
    model, compiler, _, _ = compiler_setup
    c = ConstraintIR(
        type=ConstraintType.REQUIRE_ENERGY,
        scope=ConstraintScope.TASK,
        target_identifier="Deep Work",
        parameters={"required_energy": "quantum", "target": "Deep Work"}
    )
    res = compiler.compile([c])
    assert res.skipped_count == 1
    assert "Unsupported energy level" in res.errors[0]

def test_unsupported_constraint_type(compiler_setup):
    model, compiler, _, _ = compiler_setup
    c = ConstraintIR(
        type=ConstraintType.MAX_DAILY_HOURS,
        scope=ConstraintScope.GLOBAL,
        parameters={"max_minutes": 300}
    )
    # Bypass enum validation to test compiler fallback
    c.type = "FAKE_TYPE" 
    res = compiler.compile([c])
    assert res.skipped_count == 1
    assert "Unsupported constraint type" in res.errors[0]
