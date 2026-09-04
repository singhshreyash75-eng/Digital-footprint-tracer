export type InvestigationStatus =
  | "CREATED"
  | "QUEUED"
  | "RUNNING"
  | "CORRELATING"
  | "REPORTING"
  | "COMPLETED"
  | "PARTIAL"
  | "FAILED"
  | "CANCELLED";

export type ProviderRunStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCESS"
  | "NOT_FOUND"
  | "RATE_LIMITED"
  | "TIMEOUT"
  | "FAILED"
  | "SKIPPED";

export interface Investigation {
  id: string;
  name: string;
  status: InvestigationStatus;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ProviderRun {
  id: string;
  provider_name: string;
  status: ProviderRunStatus;
  result?: Record<string, unknown> | null;
}