export type Role = "owner" | "editor" | "viewer";
export type StepType = "http_fetch" | "llm" | "transform" | "conditional" | "output";
export type RunStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
}
export interface Org {
  id: string;
  name: string;
  slug: string;
  role: Role | null;
}
export interface Step {
  id?: string;
  position?: number;
  type: StepType;
  name: string;
  config: Record<string, any>;
}
export interface WorkflowSummary {
  id: string;
  org_id: string;
  name: string;
  description: string | null;
  is_sample: boolean;
  created_at: string;
  updated_at: string;
}
export interface Workflow extends WorkflowSummary {
  steps: Step[];
}
export interface LogEntry {
  level: string;
  message: string;
}
export interface StepRun {
  id: string;
  position: number;
  type: string;
  name: string;
  status: string;
  input: any;
  output: any;
  error: string | null;
  logs: LogEntry[];
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
}
export interface RunSummary {
  id: string;
  workflow_id: string;
  status: RunStatus;
  trigger: string;
  attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}
export interface Run extends RunSummary {
  input: any;
  output: any;
  step_runs: StepRun[];
}
export interface ProviderKey {
  id: string;
  name: string;
  provider: string;
  last4: string;
  created_at: string;
}
