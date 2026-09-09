/** Typed client for the Stage 7B command pipeline. */

import { authenticatedFetch } from "./apiClient";
import { API_BASE_URL } from "./config";

// ---------- Types matching the backend contract ----------

export interface CommandFilter {
  field: string;
  operator: string;
  value: unknown;
}

export interface ParsedCommand {
  operation: string;   // CREATE | READ | UPDATE | DELETE
  target_type: string; // TASK | EVENT | PREFERENCE
  scope: string;       // SINGLE | FILTERED | ALL
  filters: CommandFilter[];
  payload: Record<string, unknown> | null;
}

export interface CommandPreviewResponse {
  commands: ParsedCommand[];
  summary: string;
  requires_confirmation: boolean;
  confirmation_id: string | null;
  affected_count: number;
  expires_at: string | null;
}

export interface CommandExecutionResult {
  operation: string;
  target_type: string;
  scope: string;
  affected_count: number;
  success: boolean;
  error?: string;
}

export interface CommandExecuteResponse {
  results: CommandExecutionResult[];
}

// ---------- API Errors ----------

export class CommandApiError extends Error {
  constructor(
    public statusCode: number,
    message: string,
  ) {
    super(message);
    this.name = "CommandApiError";
  }
}

// ---------- Preview ----------

export async function previewCommands(
  message: string,
): Promise<CommandPreviewResponse> {
  const res = await authenticatedFetch(`${API_BASE_URL}/api/commands/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Network error" }));
    throw new CommandApiError(
      res.status,
      body.detail ?? `Preview failed (${res.status})`,
    );
  }

  return res.json() as Promise<CommandPreviewResponse>;
}

// ---------- Execute (safe, non-destructive path via commands list) ----------

export async function executeCommands(
  commands: ParsedCommand[],
): Promise<CommandExecuteResponse> {
  const res = await authenticatedFetch(`${API_BASE_URL}/api/commands/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ commands }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Network error" }));
    throw new CommandApiError(
      res.status,
      body.detail ?? `Execute failed (${res.status})`,
    );
  }

  return res.json() as Promise<CommandExecuteResponse>;
}

// ---------- Execute (destructive path via server-stored confirmation_id) ----------

export async function executeWithConfirmation(
  confirmationId: string,
): Promise<CommandExecuteResponse> {
  const res = await authenticatedFetch(`${API_BASE_URL}/api/commands/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmation_id: confirmationId }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Network error" }));
    throw new CommandApiError(
      res.status,
      body.detail ?? `Execute failed (${res.status})`,
    );
  }

  return res.json() as Promise<CommandExecuteResponse>;
}

// ---------- Helpers ----------

export function friendlyOperation(op: string): string {
  const map: Record<string, string> = {
    DELETE: "Delete",
    UPDATE: "Update",
    CREATE: "Create",
    READ: "Read",
  };
  return map[op] ?? op;
}

export function friendlyTarget(t: string): string {
  const map: Record<string, string> = {
    TASK: "task(s)",
    EVENT: "event(s)",
    PREFERENCE: "preference(s)",
  };
  return map[t] ?? t.toLowerCase();
}

export function friendlyScope(s: string): string {
  const map: Record<string, string> = {
    ALL: "all",
    FILTERED: "matching",
    SINGLE: "one",
  };
  return map[s] ?? s.toLowerCase();
}

export function isDestructive(cmd: ParsedCommand): boolean {
  return cmd.operation === "DELETE" || (cmd.operation === "UPDATE" && cmd.scope !== "SINGLE");
}
