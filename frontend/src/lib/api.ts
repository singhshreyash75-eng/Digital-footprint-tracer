import type {
  Investigation,
  InvestigationCreate,
} from "../types/investigation";

import type {
  IdentityCandidate,
  IdentitySearchResponse,
  IdentitySelectResponse,
  SubjectInvestigationResponse,
} from "../types/identity";


const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  "http://localhost:8000/api/v1";


/* =========================================================
 * SUBJECT IDENTITY TYPES
 * ========================================================= */

export type LinkedSubjectIdentity = {
  id: string;
  subject_id: string;
  provider: string;
  provider_user_id: string;

  username?: string | null;
  display_name?: string | null;
  profile_url?: string | null;

  confidence?: number | null;

  identifiers: Record<string, string>;
};


export type ProviderIdentityCandidate = {
  provider: string;
  provider_user_id: string;

  username?: string | null;
  display_name?: string | null;
  profile_url?: string | null;

  confidence: number;
  match_type: string;

  reasons: string[];

  identifiers: Record<string, string>;

  discovery_query?: string | null;

  correlation_score?: number;
  correlation_percent?: number;

  correlation_reasons?: string[];

  auto_link?: boolean;
};


export type ResolveSubjectIdentityResponse = {
  success: boolean;
  resolved: boolean;
  created: boolean;

  subject_id: string;

  provider: string;
  query: string;
  reason: string;

  identity:
    | LinkedSubjectIdentity
    | null;

  candidates:
    ProviderIdentityCandidate[];
};


export type LinkSubjectIdentityResponse = {
  success: boolean;
  resolved: boolean;
  created: boolean;

  identity:
    LinkedSubjectIdentity;
};


export type SubjectIdentitiesResponse = {
  success: boolean;

  subject_id: string;

  count: number;

  identities:
    LinkedSubjectIdentity[];
};


/* =========================================================
 * AUTOMATIC CORRELATION TYPES
 * ========================================================= */

export type CorrelationProviderResult = {
  resolved: boolean;

  auto_link_available: boolean;

  candidate_count: number;

  candidates:
    ProviderIdentityCandidate[];
};


export type AutoLinkedCorrelationIdentity = {
  created: boolean;

  correlation_score: number;

  correlation_percent: number;

  correlation_reasons: string[];

  identity:
    LinkedSubjectIdentity;
};


export type CorrelateSubjectResponse = {
  success: boolean;

  subject_id: string;

  query: string;

  signals: string[];

  discovered_candidate_count: number;

  auto_linked:
    AutoLinkedCorrelationIdentity[];

  providers: Record<
    string,
    CorrelationProviderResult
  >;
};


/* =========================================================
 * ERROR HANDLING
 * ========================================================= */

function formatErrorDetail(
  detail: unknown,
): string {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (
          typeof item === "object" &&
          item !== null
        ) {
          const record =
            item as Record<
              string,
              unknown
            >;

          const message =
            typeof record.msg === "string"
              ? record.msg
              : JSON.stringify(record);

          const location =
            Array.isArray(record.loc)
              ? record.loc.join(" → ")
              : null;

          return location
            ? `${location}: ${message}`
            : message;
        }

        return String(item);
      })
      .join("\n");
  }

  if (
    typeof detail === "object" &&
    detail !== null
  ) {
    try {
      return JSON.stringify(
        detail,
        null,
        2,
      );
    } catch {
      return (
        "The server returned " +
        "an unknown error."
      );
    }
  }

  if (
    detail !== undefined &&
    detail !== null
  ) {
    return String(detail);
  }

  return (
    "The server returned " +
    "an unknown error."
  );
}


async function parseError(
  response: Response,
): Promise<never> {
  let message =
    `Request failed with status ${response.status}`;

  try {
    const body: unknown =
      await response.json();

    if (
      typeof body === "object" &&
      body !== null
    ) {
      const record =
        body as Record<
          string,
          unknown
        >;

      if ("detail" in record) {
        message =
          formatErrorDetail(
            record.detail,
          );
      } else if (
        "message" in record
      ) {
        message =
          formatErrorDetail(
            record.message,
          );
      }
    }
  } catch {
    // Preserve HTTP fallback.
  }

  throw new Error(message);
}


/* =========================================================
 * GENERIC REQUEST
 * ========================================================= */

async function requestJson<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(
      input,
      init,
    );
  } catch (error) {
    const reason =
      error instanceof Error
        ? error.message
        : "Unknown network error";

    throw new Error(
      `Unable to connect to backend: ${reason}`,
    );
  }

  if (!response.ok) {
    return parseError(response);
  }

  try {
    return (
      await response.json()
    ) as T;
  } catch {
    throw new Error(
      "Backend returned an invalid JSON response.",
    );
  }
}


/* =========================================================
 * ORIGINAL INVESTIGATION API
 * ========================================================= */

export async function createInvestigation(
  payload: InvestigationCreate,
): Promise<Investigation> {
  return requestJson<Investigation>(
    `${API_BASE_URL}/investigations`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",

        Accept:
          "application/json",
      },

      body:
        JSON.stringify(payload),
    },
  );
}


export async function getInvestigation(
  investigationId: string,
): Promise<Investigation> {
  const cleanId =
    investigationId.trim();

  if (!cleanId) {
    throw new Error(
      "Investigation ID cannot be empty.",
    );
  }

  return requestJson<Investigation>(
    `${API_BASE_URL}/investigations/${encodeURIComponent(
      cleanId,
    )}`,
    {
      method: "GET",

      headers: {
        Accept:
          "application/json",
      },

      cache: "no-store",
    },
  );
}


/* =========================================================
 * IDENTITY DISCOVERY
 * ========================================================= */

export async function searchIdentities(
  query: string,
): Promise<IdentitySearchResponse> {
  const cleanQuery =
    query.trim();

  if (!cleanQuery) {
    throw new Error(
      "Identity search query cannot be empty.",
    );
  }

  return requestJson<
    IdentitySearchResponse
  >(
    `${API_BASE_URL}/identity/search`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",

        Accept:
          "application/json",
      },

      body: JSON.stringify({
        query: cleanQuery,
      }),
    },
  );
}


/* =========================================================
 * ANCHOR SELECTION
 * ========================================================= */

export async function selectIdentity(
  candidate: IdentityCandidate,
  query: string,
): Promise<IdentitySelectResponse> {
  const cleanQuery =
    query.trim();

  if (!cleanQuery) {
    throw new Error(
      "Selection query cannot be empty.",
    );
  }

  const provider =
    candidate.provider
      .trim()
      .toLowerCase();

  const providerUserId =
    candidate.provider_user_id
      .trim();

  if (
    !provider ||
    !providerUserId
  ) {
    throw new Error(
      "Selected identity is missing provider information.",
    );
  }

  return requestJson<
    IdentitySelectResponse
  >(
    `${API_BASE_URL}/identity/select`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",

        Accept:
          "application/json",
      },

      body: JSON.stringify({
        query:
          cleanQuery,

        provider,

        provider_user_id:
          providerUserId,
      }),
    },
  );
}


/* =========================================================
 * AUTOMATIC CROSS-PROVIDER CORRELATION
 *
 * Selected Subject
 *       ↓
 * public signal expansion
 *       ↓
 * GitHub / Steam / Twitch / StackExchange discovery
 *       ↓
 * correlation scoring
 * ========================================================= */

export async function correlateSubject(
  subjectId: string,
  query: string,
): Promise<CorrelateSubjectResponse> {
  const cleanSubjectId =
    subjectId.trim();

  const cleanQuery =
    query.trim();

  if (!cleanSubjectId) {
    throw new Error(
      "Subject ID cannot be empty.",
    );
  }

  if (!cleanQuery) {
    throw new Error(
      "Correlation query cannot be empty.",
    );
  }

  return requestJson<
    CorrelateSubjectResponse
  >(
    `${API_BASE_URL}/subjects/${encodeURIComponent(
      cleanSubjectId,
    )}/correlate`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",

        Accept:
          "application/json",
      },

      body: JSON.stringify({
        query: cleanQuery,
      }),
    },
  );
}


/* =========================================================
 * MANUAL PROVIDER FALLBACK
 * ========================================================= */

export async function resolveSubjectIdentity(
  subjectId: string,
  provider: string,
  query: string,
): Promise<ResolveSubjectIdentityResponse> {
  const cleanSubjectId =
    subjectId.trim();

  const cleanProvider =
    provider
      .trim()
      .toLowerCase();

  const cleanQuery =
    query.trim();

  if (!cleanSubjectId) {
    throw new Error(
      "Subject ID cannot be empty.",
    );
  }

  if (!cleanProvider) {
    throw new Error(
      "Provider cannot be empty.",
    );
  }

  if (!cleanQuery) {
    throw new Error(
      "Provider identity query cannot be empty.",
    );
  }

  return requestJson<
    ResolveSubjectIdentityResponse
  >(
    `${API_BASE_URL}/subjects/${encodeURIComponent(
      cleanSubjectId,
    )}/identities/resolve`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",

        Accept:
          "application/json",
      },

      body: JSON.stringify({
        provider:
          cleanProvider,

        query:
          cleanQuery,
      }),
    },
  );
}


/* =========================================================
 * CONFIRM CORRELATED IDENTITY
 * ========================================================= */

export async function confirmCorrelatedIdentity(
  subjectId: string,
  candidate: ProviderIdentityCandidate,
): Promise<LinkSubjectIdentityResponse> {
  const cleanSubjectId = subjectId.trim();
  const cleanProvider = candidate.provider.trim().toLowerCase();
  const cleanProviderUserId = candidate.provider_user_id.trim();
  const discoveryQuery = (candidate.discovery_query ?? "").trim();

  if (!cleanSubjectId) {
    throw new Error("Subject ID cannot be empty.");
  }

  if (!cleanProvider || !cleanProviderUserId) {
    throw new Error("Correlated candidate is missing provider identity data.");
  }

  if (!discoveryQuery) {
    throw new Error(
      "Correlated candidate is missing its verified discovery query.",
    );
  }

  return requestJson<LinkSubjectIdentityResponse>(
    `${API_BASE_URL}/subjects/${encodeURIComponent(
      cleanSubjectId,
    )}/identities/confirm-correlated`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        provider: cleanProvider,
        provider_user_id: cleanProviderUserId,
        discovery_query: discoveryQuery,
      }),
    },
  );
}


/* =========================================================
 * CONFIRM DISCOVERED IDENTITY
 * ========================================================= */

export async function linkSubjectIdentity(
  subjectId: string,
  provider: string,
  providerUserId: string,
  query: string,
): Promise<LinkSubjectIdentityResponse> {
  const cleanSubjectId =
    subjectId.trim();

  const cleanProvider =
    provider
      .trim()
      .toLowerCase();

  const cleanProviderUserId =
    providerUserId.trim();

  const cleanQuery =
    query.trim();

  if (!cleanSubjectId) {
    throw new Error(
      "Subject ID cannot be empty.",
    );
  }

  if (!cleanProvider) {
    throw new Error(
      "Provider cannot be empty.",
    );
  }

  if (!cleanProviderUserId) {
    throw new Error(
      "Provider user ID cannot be empty.",
    );
  }

  if (!cleanQuery) {
    throw new Error(
      "Provider discovery query cannot be empty.",
    );
  }

  return requestJson<
    LinkSubjectIdentityResponse
  >(
    `${API_BASE_URL}/subjects/${encodeURIComponent(
      cleanSubjectId,
    )}/identities`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",

        Accept:
          "application/json",
      },

      body: JSON.stringify({
        provider:
          cleanProvider,

        provider_user_id:
          cleanProviderUserId,

        query:
          cleanQuery,
      }),
    },
  );
}


/* =========================================================
 * LIST LINKED IDENTITIES
 * ========================================================= */

export async function getSubjectIdentities(
  subjectId: string,
): Promise<SubjectIdentitiesResponse> {
  const cleanSubjectId =
    subjectId.trim();

  if (!cleanSubjectId) {
    throw new Error(
      "Subject ID cannot be empty.",
    );
  }

  return requestJson<
    SubjectIdentitiesResponse
  >(
    `${API_BASE_URL}/subjects/${encodeURIComponent(
      cleanSubjectId,
    )}/identities`,
    {
      method: "GET",

      headers: {
        Accept:
          "application/json",
      },

      cache: "no-store",
    },
  );
}


/* =========================================================
 * SUBJECT INVESTIGATION
 * ========================================================= */

export async function investigateSubject(
  subjectId: string,
): Promise<SubjectInvestigationResponse> {
  const cleanSubjectId =
    subjectId.trim();

  if (!cleanSubjectId) {
    throw new Error(
      "Cannot investigate an empty subject ID.",
    );
  }

  return requestJson<
    SubjectInvestigationResponse
  >(
    `${API_BASE_URL}/subjects/${encodeURIComponent(
      cleanSubjectId,
    )}/investigate`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",

        Accept:
          "application/json",
      },

      body: JSON.stringify({
        providers: [
          "github",
          "steam",
          "twitch",
          "stackexchange",
        ],

        capability_overrides: {},
      }),
    },
  );
}