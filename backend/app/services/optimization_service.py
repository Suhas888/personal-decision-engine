from ortools.sat.python import cp_model
from typing import List, Dict, Any
import datetime

def generate_weekly_plan(profile, tasks: List, fixed_events: List, dependencies: List = None, dynamic_constraints: List = None) -> Dict[str, Any]:
    if dependencies is None:
        dependencies = []
    if dynamic_constraints is None:
        dynamic_constraints = []
        
    model = cp_model.CpModel()
    
    # 1. Configurable Weights (Multi-Objective)
    WEIGHTS = {
        "priority_base": 1000,
        "priority_step": -100,  # e.g., P1 = 1000, P2 = 900
        "energy_match": 200,
        "context_switch_penalty": -50,
        "balanced_penalty": -5,
        "deadline_boost_per_day": 50, # Boost for being closer to deadline
        "starvation_boost_per_day": 20, # Boost for older tasks
    }
    
    # Output structures
    scheduled_blocks = []
    unscheduled_tasks = []
    task_vars = {}
    objective_terms = []
    
    # Reference Date for calculations based on user timezone
    from ..utils.time_utils import get_current_time, get_relative_day_offset
    user_tz = getattr(profile, "timezone", "UTC")
    today_dt = get_current_time(user_tz)
    today = today_dt.date()
    
    # 2. Hard Constraints: Fixed Events
    fixed_intervals = []
    
    for event in fixed_events:
        # Calculate relative offset instead of rigid monday=0
        day_idx = get_relative_day_offset(today_dt, event.day_of_week)
        day_offset = day_idx * 24 * 60
        start = day_offset + int(event.start_time)
        end = day_offset + int(event.end_time)
        duration = end - start
        
        interval = model.NewFixedSizeIntervalVar(start, duration, f"fixed_{event.id}")
        fixed_intervals.append(interval)
        
    # 3. Available Hours Domain
    valid_work_intervals = []
    for day in range(7):
        day_offset = day * 24 * 60
        valid_start = day_offset + int(profile.preferred_start_hour)
        valid_end = day_offset + int(profile.preferred_end_hour)
        valid_work_intervals.extend([valid_start, valid_end])
        
    global_domain = cp_model.Domain.FromIntervals(
        [[valid_work_intervals[i], valid_work_intervals[i + 1]] for i in range(0, len(valid_work_intervals), 2)]
    )

    # 4. Energy Domains
    def get_energy_domain(energy_type: str) -> cp_model.Domain:
        # High: 420-660 (7am-11am)
        # Medium: 660-1020 (11am-5pm)
        # Low: 1020-1320 (5pm-10pm)
        intervals = []
        for day in range(7):
            day_offset = day * 24 * 60
            if energy_type == "high":
                intervals.extend([day_offset + 420, day_offset + 660])
            elif energy_type == "medium":
                intervals.extend([day_offset + 660, day_offset + 1020])
            elif energy_type == "low":
                intervals.extend([day_offset + 1020, day_offset + 1320])
        if not intervals:
            return global_domain
        return cp_model.Domain.FromIntervals([[intervals[i], intervals[i+1]] for i in range(0, len(intervals), 2)])

    energy_domains = {
        "high": get_energy_domain("high"),
        "medium": get_energy_domain("medium"),
        "low": get_energy_domain("low")
    }

    # 5. Task Variables
    all_task_intervals = []
    
    # Store blocks per day for balancing
    daily_minutes_vars = {day: [] for day in range(7)}
    
    # Store category presence per day for context switching
    # day -> category -> list of bool vars
    category_day_vars = {day: {} for day in range(7)}

    for task in tasks:
        if task.completed:
            continue
            
        # Calculate Base Weight (Priority + Deadline + Starvation)
        base_weight = WEIGHTS["priority_base"] + (task.priority * WEIGHTS["priority_step"])
        
        # Deadline Pressure
        if task.deadline:
            try:
                dt = datetime.datetime.strptime(task.deadline, "%Y-%m-%d").date()
                days_until = (dt - today).days
                if days_until < 7:
                    base_weight += max(0, (7 - days_until) * WEIGHTS["deadline_boost_per_day"])
            except ValueError:
                pass
                
        # Starvation
        if hasattr(task, 'created_at') and task.created_at:
            days_old = (today - task.created_at.date()).days
            if days_old > 0:
                base_weight += min(500, days_old * WEIGHTS["starvation_boost_per_day"])
                
        # Domain based on preferred days
        task_domain = global_domain
        if task.preferred_days:
            allowed_days = [d.strip().lower() for d in task.preferred_days.split(',')]
            t_intervals = []
            for day_name in allowed_days:
                try:
                    day_idx = get_relative_day_offset(today_dt, day_name)
                    day_offset = day_idx * 24 * 60
                    t_intervals.extend([day_offset + int(profile.preferred_start_hour), day_offset + int(profile.preferred_end_hour)])
                except ValueError:
                    pass
            if t_intervals:
                # Sort intervals to ensure Domain.FromIntervals doesn't crash on unsorted intervals
                sorted_intervals = []
                for i in range(0, len(t_intervals), 2):
                    sorted_intervals.append([t_intervals[i], t_intervals[i+1]])
                sorted_intervals.sort(key=lambda x: x[0])
                task_domain = cp_model.Domain.FromIntervals(sorted_intervals)

        # Task Splitting logic
        continuous = getattr(task, 'continuous_only', False)
        if continuous:
            num_blocks = 1
            minutes_per_block = task.estimated_minutes
            remainder = 0
        else:
            num_blocks = (task.estimated_minutes + profile.max_focus_block_minutes - 1) // profile.max_focus_block_minutes
            if num_blocks == 0: num_blocks = 1
            minutes_per_block = task.estimated_minutes // num_blocks
            remainder = task.estimated_minutes % num_blocks
            
        task_blocks = []
        for b in range(num_blocks):
            # Assign remainder to the last block
            current_block_minutes = minutes_per_block + (remainder if b == num_blocks - 1 else 0)
            
            is_scheduled = model.NewBoolVar(f"task_{task.id}_b{b}_sched")
            start_var = model.NewIntVarFromDomain(task_domain, f"task_{task.id}_b{b}_start")
            end_var = model.NewIntVarFromDomain(task_domain, f"task_{task.id}_b{b}_end")
            
            dur_var = model.NewIntVar(0, current_block_minutes, f"task_{task.id}_b{b}_dur")
            model.Add(dur_var == current_block_minutes).OnlyEnforceIf(is_scheduled)
            model.Add(dur_var == 0).OnlyEnforceIf(is_scheduled.Not())
            
            interval_var = model.NewOptionalIntervalVar(start_var, dur_var, end_var, is_scheduled, f"task_{task.id}_b{b}_int")
            
            # Energy Match Objective
            is_energy_matched = model.NewBoolVar(f"task_{task.id}_b{b}_energy_match")
            energy_req = (getattr(task, 'energy_requirement') or 'any').lower()
            if energy_req in energy_domains:
                # If scheduled and in domain -> matched
                model.AddLinearExpressionInDomain(start_var, energy_domains[energy_req]).OnlyEnforceIf(is_energy_matched)
                model.AddLinearExpressionInDomain(start_var, energy_domains[energy_req].complement()).OnlyEnforceIf(is_energy_matched.Not())
                # Add to objective only if actually scheduled
                matched_and_scheduled = model.NewBoolVar(f"task_{task.id}_b{b}_energy_sched_match")
                model.AddBoolAnd([is_scheduled, is_energy_matched]).OnlyEnforceIf(matched_and_scheduled)
                model.AddBoolOr([is_scheduled.Not(), is_energy_matched.Not()]).OnlyEnforceIf(matched_and_scheduled.Not())
                objective_terms.append(WEIGHTS["energy_match"] * matched_and_scheduled)
            else:
                model.Add(is_energy_matched == 0)

            # Daily tracking for balance and context switching
            for day in range(7):
                day_offset = day * 24 * 60
                is_on_day = model.NewBoolVar(f"task_{task.id}_b{b}_on_day_{day}")
                
                # Check if start_var falls in this day's bounds
                model.AddLinearExpressionInDomain(start_var, cp_model.Domain(day_offset, day_offset + 1439)).OnlyEnforceIf(is_on_day)
                model.AddLinearExpressionInDomain(start_var, cp_model.Domain(day_offset, day_offset + 1439).complement()).OnlyEnforceIf(is_on_day.Not())
                
                is_sched_on_day = model.NewBoolVar(f"task_{task.id}_b{b}_sched_on_day_{day}")
                model.AddBoolAnd([is_scheduled, is_on_day]).OnlyEnforceIf(is_sched_on_day)
                model.AddBoolOr([is_scheduled.Not(), is_on_day.Not()]).OnlyEnforceIf(is_sched_on_day.Not())
                
                # Balance contribution
                day_dur = model.NewIntVar(0, minutes_per_block, f"task_{task.id}_b{b}_day_{day}_dur")
                model.Add(day_dur == minutes_per_block).OnlyEnforceIf(is_sched_on_day)
                model.Add(day_dur == 0).OnlyEnforceIf(is_sched_on_day.Not())
                daily_minutes_vars[day].append(day_dur)
                
                # Context switching tracking
                cat = task.category or "none"
                if cat not in category_day_vars[day]:
                    category_day_vars[day][cat] = []
                category_day_vars[day][cat].append(is_sched_on_day)

            objective_terms.append(base_weight * is_scheduled)
            task_blocks.append((is_scheduled, start_var, end_var, interval_var, current_block_minutes, is_energy_matched, base_weight))
            all_task_intervals.append(interval_var)
            
        task_vars[task.id] = task_blocks

    # 6. Task Dependencies (Hard Constraints)
    # dependent_task_id -> depends_on_task_id
    for dep in dependencies:
        dep_id = dep.depends_on_task_id
        task_id = dep.task_id
        if task_id in task_vars and dep_id in task_vars:
            blocks_a = task_vars[task_id] # Dependent
            blocks_b = task_vars[dep_id]  # Prerequisite
            
            # For every block of A and every block of B
            for (a_is_sched, a_start, a_end, _, _, _, _) in blocks_a:
                for (b_is_sched, b_start, b_end, _, _, _, _) in blocks_b:
                    # If both are scheduled, B must end before A starts
                    model.Add(b_end <= a_start).OnlyEnforceIf([a_is_sched, b_is_sched])
                
                # If A is scheduled, ALL blocks of B must be scheduled
                # We enforce this because a prerequisite should be fully complete.
                for (b_is_sched, _, _, _, _, _, _) in blocks_b:
                    model.AddImplication(a_is_sched, b_is_sched)

    # 7. No Overlap
    model.AddNoOverlap(all_task_intervals + fixed_intervals)
    
    # 8. Balanced Distribution Penalty & Daily Limits
    daily_sums = []
    
    limit_weekday = getattr(profile, "daily_task_limit_minutes_weekday", None)
    limit_weekend = getattr(profile, "daily_task_limit_minutes_weekend", None)
    
    for day in range(7):
        # Calculate actual day of week to know if it's weekend
        from datetime import timedelta
        actual_date = today_dt + timedelta(days=day)
        is_weekend = actual_date.weekday() >= 5
        
        limit = limit_weekend if is_weekend else limit_weekday
        
        ds = model.NewIntVar(0, 1440, f"day_{day}_sum")
        if daily_minutes_vars[day]:
            model.Add(ds == sum(daily_minutes_vars[day]))
        else:
            model.Add(ds == 0)
            
        if limit is not None:
            model.Add(ds <= limit)
            
        daily_sums.append(ds)
        
    max_daily = model.NewIntVar(0, 1440, "max_daily_minutes")
    model.AddMaxEquality(max_daily, daily_sums)
    objective_terms.append(WEIGHTS["balanced_penalty"] * max_daily)
    
    # 9. Context Switching Penalty
    for day in range(7):
        cat_present_vars = []
        for cat, bool_vars in category_day_vars[day].items():
            if not bool_vars: continue
            cat_present = model.NewBoolVar(f"day_{day}_cat_{cat}_present")
            model.AddBoolOr(bool_vars).OnlyEnforceIf(cat_present)
            
            # If all are false, cat_present must be false
            # This requires adding implications
            for bv in bool_vars:
                model.AddImplication(bv, cat_present)
            # if cat_present is true, at least one must be true -> this is exactly AddBoolOr
            
            cat_present_vars.append(cat_present)
            
        if cat_present_vars:
            total_cats = model.NewIntVar(0, len(cat_present_vars), f"day_{day}_total_cats")
            model.Add(total_cats == sum(cat_present_vars))
            objective_terms.append(WEIGHTS["context_switch_penalty"] * total_cats)

    # 9.5. Dynamic Constraints
    if dynamic_constraints:
        from .constraint_compiler import ConstraintCompiler
        from ..schemas.constraints import ConstraintIR
        
        irs = []
        for c in dynamic_constraints:
            try:
                ir = ConstraintIR(
                    type=c.type,
                    scope=c.scope,
                    target_identifier=c.target,
                    parameters=c.parameters,
                    strength=c.strength
                )
                irs.append(ir)
            except Exception as e:
                raise ValueError(f"Invalid dynamic constraint {c.id}: {str(e)}")
                
        relative_today_idx = today_dt.weekday()
        compiler = ConstraintCompiler(model, tasks, task_vars, relative_today_idx=relative_today_idx)
        res = compiler.compile(irs)
        
        if res.errors:
            raise ValueError(f"Constraint compilation failed: {res.errors}")
            
        objective_terms.extend(res.objective_terms)

    # 10. Maximize Objective
    model.Maximize(sum(objective_terms))

    # 11. Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0 # Increased for multi-objective
    status = solver.Solve(model)

    # 12. Extract Results & Generate Explanations
    total_scheduled = 0
    total_requested = sum(t.estimated_minutes for t in tasks if not t.completed)
    
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for task in tasks:
            if task.completed:
                continue
                
            task_scheduled = False
            blocks = task_vars.get(task.id, [])
            for b_idx, (is_sched, start_var, end_var, _, duration, is_energy, base_weight) in enumerate(blocks):
                if solver.Value(is_sched):
                    task_scheduled = True
                    start_val = solver.Value(start_var)
                    end_val = solver.Value(end_var)
                    day_idx = start_val // (24 * 60)
                    
                    # Calculate actual date
                    from datetime import timedelta
                    actual_date = today_dt + timedelta(days=day_idx)
                    
                    # Generate Explanations
                    reasons = []
                    if base_weight > WEIGHTS["priority_base"] + 100:
                        reasons.append("High priority/Deadline pressure.")
                    if solver.Value(is_energy):
                        reasons.append(f"Matched {getattr(task, 'energy_requirement', 'any')} energy.")
                        
                    scheduled_blocks.append({
                        "task_id": task.id,
                        "task_title": task.title,
                        "date": actual_date.strftime("%Y-%m-%d"),
                        "day": actual_date.strftime("%A"),
                        "start_time": start_val % (24 * 60),
                        "end_time": end_val % (24 * 60),
                        "duration_minutes": duration,
                        "explanation": " ".join(reasons) or "Scheduled to balance workload."
                    })
                    total_scheduled += duration
                    
            if not task_scheduled:
                unscheduled_tasks.append({"task_id": task.id, "title": task.title})
                
    sorted_blocks = sorted(scheduled_blocks, key=lambda x: x["start_time"])
    
    # 13. Post-Schedule Validation
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) and sorted_blocks:
        _validate_schedule(sorted_blocks, dynamic_constraints, today_dt, user_tz)

    warnings = []
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        warnings.append("Unable to generate schedule.")
        
    return {
        "scheduled_blocks": sorted_blocks,
        "unscheduled_tasks": unscheduled_tasks,
        "total_scheduled_minutes": total_scheduled,
        "total_requested_minutes": total_requested,
        "completion_percentage": (total_scheduled / total_requested * 100.0) if total_requested > 0 else 0.0,
        "objective_score": int(solver.ObjectiveValue()) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0,
        "constraint_warnings": warnings,
    }

def _validate_schedule(blocks, dynamic_constraints, today_dt, user_tz):
    """Post-schedule validation to ensure mathematical constraints were honored."""
    # Validate no overlaps
    for i in range(len(blocks) - 1):
        b1 = blocks[i]
        b2 = blocks[i+1]
        if b1["date"] == b2["date"] and b1["end_time"] > b2["start_time"]:
            raise ValueError(f"Overlap detected between {b1['task_title']} and {b2['task_title']}")
            
    # Validate HARD dynamic constraints (basic checks)
    if not dynamic_constraints: return
    
    from ..schemas.constraints import ConstraintStrength
    from ..utils.time_utils import get_relative_day_offset
    
    for c in dynamic_constraints:
        if c.strength != ConstraintStrength.HARD.value:
            continue
            
        if c.type == "MAX_DAILY_HOURS":
            max_minutes = c.parameters.get("max_minutes", 1440)
            days = [d.lower() for d in c.parameters.get("days", [])]
            
            daily_sums = {}
            for b in blocks:
                # Target match simplified for validation
                if c.scope == "GLOBAL" or (c.scope == "TASK" and b["task_title"].lower() == (c.target or "").lower()):
                    day_name = b["day"].lower()
                    if not days or day_name in days:
                        key = (b["date"], day_name)
                        daily_sums[key] = daily_sums.get(key, 0) + b["duration_minutes"]
                        
            for key, total in daily_sums.items():
                if total > max_minutes:
                    raise ValueError(f"MAX_DAILY_HOURS violation on {key}: {total} > {max_minutes}")
                    
        elif c.type == "AVOID_TIME":
            start_min = c.parameters.get("start_minute", 0)
            end_min = c.parameters.get("end_minute", 0)
            days = [d.lower() for d in c.parameters.get("days", [])]
            for b in blocks:
                if c.scope == "TASK" and b["task_title"].lower() == (c.target or "").lower():
                    day_name = b["day"].lower()
                    if not days or day_name in days:
                        if b["start_time"] < end_min and b["end_time"] > start_min:
                            raise ValueError(f"AVOID_TIME violation on {day_name} for {b['task_title']}")
