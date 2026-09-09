# Personal Decision Engine

An AI system that continuously optimizes a person's
time, goals, constraints and resources.

## Current Goal

Build a weekly planning engine that can:

1. Understand user goals
2. Understand constraints
3. Allocate available time
4. Generate an optimized weekly schedule
5. Re-plan when circumstances change

## Long-term Goal

Build a general Personal Decision Engine that can
optimize decisions involving:

- Time
- Money
- Travel
- Study
- Shopping
- Energy
- Daily life

Future research:
- Classical optimization
- Quantum optimization
- Quantum-inspired algorithms

## Tech Stack (₹0 Prototype)

We are intentionally building a free, scalable foundation before incorporating paid frontier models or complex infrastructure:

- **Backend:** Python (₹0)
- **Optimization:** Google OR-Tools (₹0)
- **LLM Layer:** Gemini 3.5 Flash (₹0) - kept provider-independent to easily swap in GPT-6/Claude later
- **Database (Local):** SQLite (₹0)
- **Frontend (Future):** Next.js (₹0)
- **Development:** VS Code + Git (₹0)

## Architecture Philosophy

We separate natural language understanding from mathematical optimization (Neuro-symbolic approach). The LLM is **not** doing the optimization.

1. **Free LLM** → Understands unstructured user requests ("I have college, GATE prep, and need 8 hrs of sleep").
2. **LLM outputs Structured Data** → Translates text into strict constraints and tasks.
3. **OR-Tools (Optimizer)** → Processes constraints mathematically to find the absolute best schedule.
4. **Free LLM** → Explains the optimal schedule back to the user in a readable format.

This ensures we don't sacrifice core technology, while maintaining a $0 cost footprint until product-market fit is achieved.

## Core Decision Engine (OR-Tools)

The scheduling engine uses **Google OR-Tools CP-SAT (Constraint Programming)** to generate mathematically optimal schedules. It represents time internally as integer minutes (0 to 10079) from the start of the week.

### Hard Constraints
The engine will never violate these rules:
- **No Overlaps**: Tasks can never overlap with each other.
- **Fixed Events**: Tasks can never overlap with user-defined fixed commitments (e.g. College).
- **Sleep Protection**: Tasks will not be scheduled during designated sleep hours.
- **Working Hours**: Tasks are strictly bound to the user's preferred waking/working hours.

### Soft Objectives (Weighted)
When multiple valid schedules exist, the engine maximizes a score based on:
1. **Priority**: High-priority tasks (Priority 1) are given mathematically heavier weights (e.g., 1000) than Priority 2 (900), ensuring they are placed first.
2. **Completion**: Maximizing the total minutes scheduled against the total requested minutes.
3. **Fragmentation**: Large tasks are chunked by the `max_focus_block_minutes` preference, minimizing disjointed contexts.

### API Usage

#### Generate Weekly Plan
```http
POST /api/plan/generate
Content-Type: application/json

{
  "week_start": "2026-09-07"
}
```

**Response**:
```json
{
  "week_start": "2026-09-07",
  "scheduled_blocks": [
    {
      "task_id": 1,
      "task_title": "GATE preparation",
      "date": "2026-09-07",
      "day": "Monday",
      "start_time": 960,
      "end_time": 1080,
      "duration_minutes": 120
    }
  ],
  "unscheduled_tasks": [],
  "total_scheduled_minutes": 1860,
  "total_requested_minutes": 1860,
  "completion_percentage": 100.0,
  "objective_score": 14200,
  "constraint_warnings": []
}
```
