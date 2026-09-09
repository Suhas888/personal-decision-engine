from typing import List, Dict, Any, Tuple
from ortools.sat.python import cp_model
from ..schemas.constraints import (
    ConstraintIR, ConstraintType, ConstraintScope, ConstraintStrength,
    MaxDailyHoursParams, AvoidTimeParams, ForceDayParams, MinGapParams, RequireEnergyParams
)

class CompilerResult:
    def __init__(self):
        self.compiled_count = 0
        self.skipped_count = 0
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.objective_terms = []

class ConstraintCompiler:
    def __init__(self, model: cp_model.CpModel, tasks: List[Any], task_vars: Dict[int, List[Tuple]], relative_today_idx: int = 0):
        self.model = model
        self.tasks = {t.id: t for t in tasks}
        self.task_vars = task_vars # Dict[task_id, List[(is_sched, start_var, end_var, interval_var, current_block_minutes, is_energy_matched, base_weight)]]
        self.relative_today_idx = relative_today_idx # to map "Monday" to a day index 0-6 relative to today
        
        self.handlers = {
            ConstraintType.MAX_DAILY_HOURS: self._compile_max_daily_hours,
            ConstraintType.AVOID_TIME: self._compile_avoid_time,
            ConstraintType.FORCE_DAY: self._compile_force_day,
            ConstraintType.MIN_GAP: self._compile_min_gap,
            ConstraintType.REQUIRE_ENERGY: self._compile_require_energy
        }

    def _get_day_offsets(self, days: List[str]) -> List[int]:
        # Simple mapping: 0 to 6. If days provided, we find the offsets.
        # For a robust system, we would use time_utils.get_relative_day_offset
        # Here we mock it by mapping name to 0-6. For simplicity, assume days are provided as integers 0-6 as strings,
        # or we rely on external util. Let's just use 0-6 directly or string matching.
        day_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
        if not days:
            return list(range(7))
        
        offsets = []
        for d in days:
            d_lower = d.lower()
            if d_lower in day_map:
                # Need actual date logic to find relative offset from today. 
                # For compiler isolation, let's just use the absolute day of week and adjust by relative_today_idx
                # Simplification: we map it directly.
                target_idx = day_map[d_lower]
                offset = (target_idx - self.relative_today_idx) % 7
                offsets.append(offset)
        return offsets

    def _get_target_tasks(self, scope: ConstraintScope, target: str) -> List[int]:
        matched = []
        for t_id, task in self.tasks.items():
            if scope == ConstraintScope.GLOBAL:
                matched.append(t_id)
            elif scope == ConstraintScope.CATEGORY and task.category and task.category.lower() == target.lower():
                matched.append(t_id)
            elif scope == ConstraintScope.TASK and task.title.lower() == target.lower():
                matched.append(t_id)
        return matched

    def compile(self, constraints: List[ConstraintIR]) -> CompilerResult:
        res = CompilerResult()
        for c in constraints:
            handler = self.handlers.get(c.type)
            if not handler:
                res.errors.append(f"Unsupported constraint type: {c.type}")
                res.skipped_count += 1
                continue
            
            try:
                handler(c, res)
                res.compiled_count += 1
            except Exception as e:
                res.errors.append(f"Error compiling {c.type}: {str(e)}")
                res.skipped_count += 1
                
        return res

    def _compile_max_daily_hours(self, c: ConstraintIR, res: CompilerResult):
        params = MaxDailyHoursParams(**c.parameters)
        target_task_ids = self._get_target_tasks(c.scope, c.target_identifier)
        if not target_task_ids:
            res.warnings.append(f"No tasks matched for MAX_DAILY_HOURS scope {c.scope}")
            return

        days = self._get_day_offsets(params.days)
        max_minutes = params.max_minutes

        for day in days:
            day_offset = day * 24 * 60
            day_start = day_offset
            day_end = day_offset + 1439
            
            day_durations = []
            for t_id in target_task_ids:
                if t_id not in self.task_vars: continue
                blocks = self.task_vars[t_id]
                for b_idx, b in enumerate(blocks):
                    is_sched, start_var, end_var, _, dur, _, _ = b
                    
                    # Create a boolean variable that is true if the task starts on this day
                    is_on_day = self.model.NewBoolVar(f"max_daily_c{id(c)}_{t_id}_{b_idx}_day{day}")
                    # A block starts on this day if start_var is in [day_start, day_end]
                    self.model.AddLinearExpressionInDomain(start_var, cp_model.Domain(day_start, day_end)).OnlyEnforceIf(is_on_day)
                    self.model.AddLinearExpressionInDomain(start_var, cp_model.Domain(day_start, day_end).complement()).OnlyEnforceIf(is_on_day.Not())
                    
                    is_sched_on_day = self.model.NewBoolVar(f"max_daily_c{id(c)}_{t_id}_{b_idx}_sched_day{day}")
                    self.model.AddBoolAnd([is_sched, is_on_day]).OnlyEnforceIf(is_sched_on_day)
                    self.model.AddBoolOr([is_sched.Not(), is_on_day.Not()]).OnlyEnforceIf(is_sched_on_day.Not())
                    
                    day_dur = self.model.NewIntVar(0, 1440, f"max_daily_dur_c{id(c)}_{t_id}_{b_idx}_day{day}")
                    self.model.Add(day_dur == dur).OnlyEnforceIf(is_sched_on_day)
                    self.model.Add(day_dur == 0).OnlyEnforceIf(is_sched_on_day.Not())
                    day_durations.append(day_dur)

            if day_durations:
                total_dur = sum(day_durations)
                if c.strength == ConstraintStrength.HARD:
                    self.model.Add(total_dur <= max_minutes)
                else:
                    # SOFT: Add penalty if total_dur > max_minutes
                    excess = self.model.NewIntVar(0, 1440, f"max_daily_excess_c{id(c)}_day{day}")
                    # excess >= total_dur - max_minutes
                    # excess >= 0
                    self.model.AddMaxEquality(excess, [0, total_dur - max_minutes])
                    res.objective_terms.append(-10 * excess) # Heavy penalty per minute

    def _compile_avoid_time(self, c: ConstraintIR, res: CompilerResult):
        params = AvoidTimeParams(**c.parameters)
        target_task_ids = self._get_target_tasks(c.scope, c.target_identifier)
        if not target_task_ids: return

        days = self._get_day_offsets(params.days)
        start_min = params.start_minute
        end_min = params.end_minute

        for t_id in target_task_ids:
            if t_id not in self.task_vars: continue
            for b_idx, b in enumerate(self.task_vars[t_id]):
                is_sched, start_var, end_var, _, _, _, _ = b
                
                for day in days:
                    day_offset = day * 24 * 60
                    a_start = day_offset + start_min
                    a_end = day_offset + end_min
                    
                    if c.strength == ConstraintStrength.HARD:
                        # If scheduled, start_var cannot be inside [a_start - duration + 1, a_end - 1]
                        # Actually simpler: no overlap means either end_var <= a_start OR start_var >= a_end
                        before = self.model.NewBoolVar(f"avoid_before_{id(c)}_{t_id}_{b_idx}_d{day}")
                        after = self.model.NewBoolVar(f"avoid_after_{id(c)}_{t_id}_{b_idx}_d{day}")
                        self.model.Add(end_var <= a_start).OnlyEnforceIf(before)
                        self.model.Add(start_var >= a_end).OnlyEnforceIf(after)
                        # We only care if it's scheduled
                        self.model.AddBoolOr([before, after, is_sched.Not()])
                    else:
                        # Soft: Penalty if overlapping
                        overlap = self.model.NewBoolVar(f"avoid_overlap_{id(c)}_{t_id}_{b_idx}_d{day}")
                        # Not before and not after -> overlap
                        before = self.model.NewBoolVar(f"soft_avoid_before_{id(c)}_{t_id}_{b_idx}_d{day}")
                        after = self.model.NewBoolVar(f"soft_avoid_after_{id(c)}_{t_id}_{b_idx}_d{day}")
                        self.model.Add(end_var <= a_start).OnlyEnforceIf(before)
                        self.model.Add(end_var > a_start).OnlyEnforceIf(before.Not())
                        self.model.Add(start_var >= a_end).OnlyEnforceIf(after)
                        self.model.Add(start_var < a_end).OnlyEnforceIf(after.Not())
                        
                        self.model.AddBoolOr([before, after]).OnlyEnforceIf(overlap.Not())
                        self.model.AddBoolAnd([before.Not(), after.Not()]).OnlyEnforceIf(overlap)
                        
                        actual_overlap = self.model.NewBoolVar(f"actual_overlap_{id(c)}_{t_id}_{b_idx}_d{day}")
                        self.model.AddBoolAnd([overlap, is_sched]).OnlyEnforceIf(actual_overlap)
                        self.model.AddBoolOr([overlap.Not(), is_sched.Not()]).OnlyEnforceIf(actual_overlap.Not())
                        
                        res.objective_terms.append(-500 * actual_overlap)

    def _compile_force_day(self, c: ConstraintIR, res: CompilerResult):
        params = ForceDayParams(**c.parameters)
        target_task_ids = self._get_target_tasks(c.scope, c.target_identifier)
        if not target_task_ids: return

        days = self._get_day_offsets([params.day])
        if not days: return
        day = days[0]
        day_offset = day * 24 * 60
        day_start = day_offset
        day_end = day_offset + 1439

        for t_id in target_task_ids:
            if t_id not in self.task_vars: continue
            for b_idx, b in enumerate(self.task_vars[t_id]):
                is_sched, start_var, _, _, _, _, _ = b
                
                is_on_day = self.model.NewBoolVar(f"force_day_c{id(c)}_{t_id}_{b_idx}")
                self.model.AddLinearExpressionInDomain(start_var, cp_model.Domain(day_start, day_end)).OnlyEnforceIf(is_on_day)
                self.model.AddLinearExpressionInDomain(start_var, cp_model.Domain(day_start, day_end).complement()).OnlyEnforceIf(is_on_day.Not())

                if c.strength == ConstraintStrength.HARD:
                    self.model.AddImplication(is_sched, is_on_day)
                else:
                    # Soft: Reward if on day, penalty if not
                    matched = self.model.NewBoolVar(f"force_day_matched_c{id(c)}_{t_id}_{b_idx}")
                    self.model.AddBoolAnd([is_sched, is_on_day]).OnlyEnforceIf(matched)
                    self.model.AddBoolOr([is_sched.Not(), is_on_day.Not()]).OnlyEnforceIf(matched.Not())
                    
                    missed = self.model.NewBoolVar(f"force_day_missed_c{id(c)}_{t_id}_{b_idx}")
                    self.model.AddBoolAnd([is_sched, is_on_day.Not()]).OnlyEnforceIf(missed)
                    self.model.AddBoolOr([is_sched.Not(), is_on_day]).OnlyEnforceIf(missed.Not())
                    
                    res.objective_terms.append(500 * matched)
                    res.objective_terms.append(-500 * missed)

    def _compile_min_gap(self, c: ConstraintIR, res: CompilerResult):
        # Implementation for MIN_GAP
        # (A bit tricky: ensures gap between any two tasks within the scope)
        params = MinGapParams(**c.parameters)
        target_task_ids = self._get_target_tasks(c.scope, c.target_identifier)
        if len(target_task_ids) < 2: return # Need at least 2 tasks to enforce a gap

        gap = params.gap_minutes
        
        # O(N^2) constraints between all block pairs
        for i in range(len(target_task_ids)):
            t1_id = target_task_ids[i]
            if t1_id not in self.task_vars: continue
            for b1_idx, b1 in enumerate(self.task_vars[t1_id]):
                is_sched1, start1, end1, _, _, _, _ = b1
                
                for j in range(i + 1, len(target_task_ids)):
                    t2_id = target_task_ids[j]
                    if t2_id not in self.task_vars: continue
                    for b2_idx, b2 in enumerate(self.task_vars[t2_id]):
                        is_sched2, start2, end2, _, _, _, _ = b2
                        
                        both_sched = self.model.NewBoolVar(f"mingap_both_{id(c)}_{t1_id}_{b1_idx}_{t2_id}_{b2_idx}")
                        self.model.AddBoolAnd([is_sched1, is_sched2]).OnlyEnforceIf(both_sched)
                        self.model.AddBoolOr([is_sched1.Not(), is_sched2.Not()]).OnlyEnforceIf(both_sched.Not())
                        
                        t1_before = self.model.NewBoolVar(f"mingap_1before_{id(c)}_{t1_id}_{b1_idx}_{t2_id}_{b2_idx}")
                        t2_before = self.model.NewBoolVar(f"mingap_2before_{id(c)}_{t1_id}_{b1_idx}_{t2_id}_{b2_idx}")
                        
                        if c.strength == ConstraintStrength.HARD:
                            self.model.Add(end1 + gap <= start2).OnlyEnforceIf(t1_before)
                            self.model.Add(end2 + gap <= start1).OnlyEnforceIf(t2_before)
                            self.model.AddBoolOr([t1_before, t2_before]).OnlyEnforceIf(both_sched)
                        else:
                            # Soft logic is complex: distance between intervals.
                            # Skip full penalty logic for soft MIN_GAP for brevity, add a basic penalty if overlap/no gap
                            self.model.Add(end1 + gap <= start2).OnlyEnforceIf(t1_before)
                            self.model.Add(end1 + gap > start2).OnlyEnforceIf(t1_before.Not())
                            
                            self.model.Add(end2 + gap <= start1).OnlyEnforceIf(t2_before)
                            self.model.Add(end2 + gap > start1).OnlyEnforceIf(t2_before.Not())
                            
                            valid_gap = self.model.NewBoolVar(f"valid_gap_{id(c)}_{t1_id}_{b1_idx}_{t2_id}_{b2_idx}")
                            self.model.AddBoolOr([t1_before, t2_before]).OnlyEnforceIf(valid_gap)
                            self.model.AddBoolAnd([t1_before.Not(), t2_before.Not()]).OnlyEnforceIf(valid_gap.Not())
                            
                            penalty_applied = self.model.NewBoolVar(f"gap_penalty_{id(c)}_{t1_id}_{b1_idx}_{t2_id}_{b2_idx}")
                            self.model.AddBoolAnd([both_sched, valid_gap.Not()]).OnlyEnforceIf(penalty_applied)
                            self.model.AddBoolOr([both_sched.Not(), valid_gap]).OnlyEnforceIf(penalty_applied.Not())
                            
                            res.objective_terms.append(-200 * penalty_applied)

    def _compile_require_energy(self, c: ConstraintIR, res: CompilerResult):
        # Implementation for REQUIRE_ENERGY
        params = RequireEnergyParams(**c.parameters)
        target_task_ids = self._get_target_tasks(c.scope, c.target_identifier)
        if not target_task_ids: return

        energy = params.required_energy.lower()
        if energy not in ["high", "medium", "low", "any"]:
            res.errors.append(f"Unsupported energy level: {energy}")
            res.skipped_count += 1
            return
            
        def get_energy_intervals(energy_type: str) -> List[int]:
            intervals = []
            for day in range(7):
                day_offset = day * 24 * 60
                if energy_type == "high":
                    intervals.extend([day_offset + 420, day_offset + 660])
                elif energy_type == "medium":
                    intervals.extend([day_offset + 660, day_offset + 1020])
                elif energy_type == "low":
                    intervals.extend([day_offset + 1020, day_offset + 1320])
            return intervals

        intervals = get_energy_intervals(energy)
        if not intervals:
            domain = cp_model.Domain.FromIntervals([[0, 7 * 24 * 60]])
        else:
            domain = cp_model.Domain.FromIntervals([[intervals[i], intervals[i+1]] for i in range(0, len(intervals), 2)])

        for t_id in target_task_ids:
            if t_id not in self.task_vars: continue
            for b_idx, b in enumerate(self.task_vars[t_id]):
                is_sched, start_var, _, _, _, _, _ = b
                
                is_matched = self.model.NewBoolVar(f"req_energy_c{id(c)}_{t_id}_{b_idx}")
                self.model.AddLinearExpressionInDomain(start_var, domain).OnlyEnforceIf(is_matched)
                self.model.AddLinearExpressionInDomain(start_var, domain.complement()).OnlyEnforceIf(is_matched.Not())
                
                if c.strength == ConstraintStrength.HARD:
                    self.model.AddImplication(is_sched, is_matched)
                else:
                    matched_and_sched = self.model.NewBoolVar(f"soft_energy_c{id(c)}_{t_id}_{b_idx}")
                    self.model.AddBoolAnd([is_sched, is_matched]).OnlyEnforceIf(matched_and_sched)
                    self.model.AddBoolOr([is_sched.Not(), is_matched.Not()]).OnlyEnforceIf(matched_and_sched.Not())
                    
                    missed = self.model.NewBoolVar(f"soft_energy_miss_c{id(c)}_{t_id}_{b_idx}")
                    self.model.AddBoolAnd([is_sched, is_matched.Not()]).OnlyEnforceIf(missed)
                    self.model.AddBoolOr([is_sched.Not(), is_matched]).OnlyEnforceIf(missed.Not())
                    
                    res.objective_terms.append(300 * matched_and_sched)
                    res.objective_terms.append(-300 * missed)
