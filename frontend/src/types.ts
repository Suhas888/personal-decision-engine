export interface ScheduleBlock {
  task_id?: number;
  task_title: string;
  date: string;
  day: string;
  start_time: number;
  end_time: number;
  duration_minutes: number;
  explanation?: string;
}

export interface PlanResponse {
  week_start: string;
  scheduled_blocks: ScheduleBlock[];
  unscheduled_tasks: unknown[];
  total_scheduled_minutes: number;
  total_requested_minutes: number;
  completion_percentage: number;
  objective_score: number;
  constraint_warnings: string[];
}

// Stage 7B: exported here for convenience but the canonical definitions live in api/commandsApi.ts
export type CommandMode =
  | "idle"
  | "loading"
  | "preview"
  | "clarification"
  | "unsupported"
  | "confirming"
  | "success"
  | "error";
