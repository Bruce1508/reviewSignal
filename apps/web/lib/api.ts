// Typed client for the ReviewSignal API.
// Envelope shape is owned by `docs/api-spec.md` §1; error codes by §14.

export type ErrorCode =
  | "VALIDATION_ERROR"
  | "UNAUTHORIZED"
  | "RESOURCE_NOT_FOUND"
  | "CONFLICT"
  | "GOOGLE_NOT_CONNECTED"
  | "GOOGLE_API_ERROR"
  | "JOB_NOT_RETRYABLE"
  | "TAXONOMY_VERSION_CONFLICT"
  | "MODEL_UNAVAILABLE"
  | "INTERNAL_ERROR";

export interface ApiError {
  code: ErrorCode;
  message: string;
}

/**
 * A discriminated union, so callers cannot read `data` without ruling out `error` first.
 */
export type ApiResponse<T> =
  | { data: T; error: null }
  | { data: null; error: ApiError };

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function apiGet<T>(path: string): Promise<ApiResponse<T>> {
  try {
    const response = await fetch(`${BASE_URL}${path}`, { cache: "no-store" });
    return (await response.json()) as ApiResponse<T>;
  } catch {
    return { data: null, error: { code: "INTERNAL_ERROR", message: "The API is unreachable." } };
  }
}

export interface HealthPayload {
  status: string;
  components: { api: string; database: string; redis: string };
}

export interface SystemStatusPayload {
  last_sync: {
    status: string;
    started_at: string;
    finished_at: string | null;
    reviews_created: number;
    reviews_updated: number;
  } | null;
  queue_depth: number;
  failed_jobs: number;
  active_taxonomy: { version_number: number; activated_at: string | null } | null;
  active_model: string;
  last_insight_at: string | null;
}

export const getHealth = () => apiGet<HealthPayload>("/health");
export const getSystemStatus = () => apiGet<SystemStatusPayload>("/system/status");
