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
 * ERROR HANDLING
 * ========================================================= */

function formatErrorDetail(detail: unknown): string {
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
          const record = item as Record<string, unknown>;

          const message =
            typeof record.msg === "string"
              ? record.msg
              : JSON.stringify(record);

          const location = Array.isArray(record.loc)
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
      return JSON.stringify(detail, null, 2);
    } catch {
      return "The server returned an unknown error.";
    }
  }

  if (detail !== undefined && detail !== null) {
    return String(detail);
  }

  return "The server returned an unknown error.";
}

async function parseError(
  response: Response,
): Promise<never> {
  let message =
    `Request failed with status ${response.status}`;

  try {
    const body: unknown = await response.json();

    if (
      typeof body === "object" &&
      body !== null
    ) {
      const record = body as Record<string, unknown>;

      if ("detail" in record) {
        message = formatErrorDetail(record.detail);
      } else if ("message" in record) {
        message = formatErrorDetail(record.message);
      }
    }
  } catch {
    // Keep the HTTP status fallback.
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
    response = await fetch(input, init);
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
    return (await response.json()) as T;
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
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    },
  );
}

export async function getInvestigation(
  investigationId: string,
): Promise<Investigation> {
  return requestJson<Investigation>(
    `${API_BASE_URL}/investigations/${encodeURIComponent(
      investigationId,
    )}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
    },
  );
}

/* =========================================================
 * IDENTITY DISCOVERY
 *
 * Name
 *  ↓
 * candidates[]
 * ========================================================= */

export async function searchIdentities(
  query: string,
): Promise<IdentitySearchResponse> {
  const cleanQuery = query.trim();

  if (!cleanQuery) {
    throw new Error(
      "Identity search query cannot be empty.",
    );
  }

  return requestJson<IdentitySearchResponse>(
    `${API_BASE_URL}/identity/search`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        query: cleanQuery,
      }),
    },
  );
}

/* =========================================================
 * CANDIDATE SELECTION
 *
 * candidate
 *   ↓
 * subject_id
 * ========================================================= */

export async function selectIdentity(
  candidate: IdentityCandidate,
): Promise<IdentitySelectResponse> {
  return requestJson<IdentitySelectResponse>(
    `${API_BASE_URL}/identity/select`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },

      body: JSON.stringify({
        provider: candidate.provider,

        provider_user_id:
          candidate.provider_user_id,

        username:
          candidate.username ??
          candidate.display_name ??
          candidate.provider_user_id,

        display_name:
          candidate.display_name ?? null,

        profile_url:
          candidate.profile_url ?? null,

        confidence:
          candidate.score,

        identifiers:
          candidate.identifiers ?? {},
      }),
    },
  );
}

/* =========================================================
 * MULTI-PROVIDER SUBJECT INVESTIGATION
 *
 * ONE selected subject
 *       ↓
 * GitHub
 * Steam
 * Twitch
 * StackExchange
 *       ↓
 * provider_results[]
 * ========================================================= */

export async function investigateSubject(
  subjectId: string,
): Promise<SubjectInvestigationResponse> {
  const cleanSubjectId = subjectId.trim();

  if (!cleanSubjectId) {
    throw new Error(
      "Cannot investigate an empty subject ID.",
    );
  }

  return requestJson<SubjectInvestigationResponse>(
    `${API_BASE_URL}/subjects/${encodeURIComponent(
      cleanSubjectId,
    )}/investigate`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
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