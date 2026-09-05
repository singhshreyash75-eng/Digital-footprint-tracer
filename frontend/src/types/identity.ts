export type IdentityCandidate = {
  provider: string;
  provider_user_id: string;

  username?: string | null;
  display_name?: string | null;
  profile_url?: string | null;
  avatar_url?: string | null;

  score: number;
  confidence_percent: number;
  match_type: string;

  reasons: string[];

  public_repos?: number | null;
  followers?: number | null;
  following?: number | null;

  bio?: string | null;
  location?: string | null;
  company?: string | null;
  blog?: string | null;

  identifiers: Record<string, string>;
};

export type IdentitySearchResponse = {
  query: string;
  candidates: IdentityCandidate[];
};

export type IdentitySelectResponse = {
  subject_id: string;

  provider: string;
  provider_user_id: string;

  username?: string | null;
  display_name?: string | null;
  profile_url?: string | null;

  confidence?: number | null;

  identifiers: Record<string, string>;
  capabilities: Record<string, boolean>;

  selected: boolean;
};

export type SubjectObservation = {
  type?: string;
  source?: string;
  source_url?: string;

  data?: Record<string, unknown>;

  confidence?: string;

  [key: string]: unknown;
};

export type SubjectProviderError = {
  code?: string;
  error_code?: string;

  message?: string;
  error_message?: string;

  [key: string]: unknown;
};

export type SubjectInvestigationResult = {
  provider: string;
  status: string;

  supported: boolean;
  executed: boolean;

  requested_capabilities: string[];
  executed_capabilities: string[];

  observations: SubjectObservation[];
  errors: SubjectProviderError[];
};

export type SubjectInvestigationResponse = {
  subject_id: string;

  provider_results: SubjectInvestigationResult[];

  total_providers: number;
  executed_providers: number;
};