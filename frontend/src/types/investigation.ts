export type InvestigationStatus =
  | "CREATED"
  | "QUEUED"
  | "RUNNING"
  | "CORRELATING"
  | "REPORTING"
  | "COMPLETED"
  | "PARTIAL"
  | "FAILED"
  | "CANCELLED"
  | string;

export type ProviderRunStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCESS"
  | "NOT_FOUND"
  | "RATE_LIMITED"
  | "TIMEOUT"
  | "FAILED"
  | "SKIPPED"
  | string;

export interface Target {
  id: string;
  type: string;
  value: string;
  normalized_value: string;
  created_at: string;
}

export interface ProviderObservation {
  type?: string;
  source?: string;
  source_url?: string | null;
  data?: Record<string, unknown> | null;
  confidence?: string | number | null;
}

export interface ProviderResult {
  provider_name?: string;
  status?: ProviderRunStatus;
  observations?: ProviderObservation[];
  raw_data?: Record<string, unknown>;
  error_code?: string | null;
  error_message?: string | null;
}

export interface ProviderRun {
  id: string;
  provider_name: string;
  status: ProviderRunStatus;
  result: ProviderResult | null;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface Investigation {
  id: string;
  name: string;
  status: InvestigationStatus;
  created_at: string;
  targets: Target[];
  provider_runs: ProviderRun[];
}

export interface TargetCreate {
  type: "USERNAME";
  value: string;
}

export interface InvestigationCreate {
  name: string;
  targets: TargetCreate[];
}
