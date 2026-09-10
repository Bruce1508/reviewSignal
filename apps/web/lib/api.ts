// Typed client for the ReviewSignal API.
// Envelope shape is owned by `docs/api-spec.md` §1; error codes by §14.

import { cookies } from "next/headers";

// Must match `core/auth.py`'s `SESSION_COOKIE`. The two are not one source of truth
// because the value never crosses the Python/TypeScript boundary as code.
const SESSION_COOKIE = "rs_session";

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
export type ApiResponse<T> = { data: T; error: null } | { data: null; error: ApiError };

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function apiGet<T>(path: string): Promise<ApiResponse<T>> {
  try {
    // The API and the dashboard are different origins in dev, so the browser's
    // session cookie never reaches this server-side fetch on its own
    // (`docs/api-spec.md` §15). Forward it explicitly from the incoming request.
    const session = (await cookies()).get(SESSION_COOKIE)?.value;
    const response = await fetch(`${BASE_URL}${path}`, {
      cache: "no-store",
      headers: session ? { Cookie: `${SESSION_COOKIE}=${session}` } : undefined,
    });
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

export interface ReviewSummary {
  id: string;
  rating: number;
  review_text: string | null;
  reviewer_name: string | null;
  created_at: string;
  analysis_status: string;
}

export interface ReviewListPayload {
  items: ReviewSummary[];
  page: number;
  page_size: number;
  total: number;
}

export interface ReviewFilters {
  q?: string;
  rating?: number;
  startDate?: string;
  endDate?: string;
}

export const getReviews = (page: number, pageSize: number, filters: ReviewFilters = {}) => {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (filters.q) params.set("q", filters.q);
  if (filters.rating) params.set("rating", String(filters.rating));
  if (filters.startDate) params.set("start_date", filters.startDate);
  if (filters.endDate) params.set("end_date", filters.endDate);
  return apiGet<ReviewListPayload>(`/reviews?${params.toString()}`);
};

export interface ReviewAspectPayload {
  category_id: string;
  category_name: string;
  sentiment: string;
  confidence: number | null;
  evidence_span: string | null;
}

export interface ReviewAnalysisPayload {
  classifier_type: string;
  overall_confidence: number | null;
  taxonomy_version_number: number;
  aspects: ReviewAspectPayload[];
}

export interface ReviewDetail {
  id: string;
  source: string;
  rating: number;
  review_text: string | null;
  reviewer_name: string | null;
  created_at: string;
  updated_at: string;
  owner_reply_text: string | null;
  owner_reply_at: string | null;
  analysis_status: string;
  analysis: ReviewAnalysisPayload | null;
}

export const getReview = (reviewId: string) => apiGet<ReviewDetail>(`/reviews/${reviewId}`);

export interface RatingTrendPoint {
  date: string;
  review_count: number;
  average_rating: number | null;
}

export interface ThemePayload {
  category_name: string;
  sentiment: string;
  mention_count: number;
}

export interface InsightSummary {
  id: string;
  title: string;
  severity: string;
  status: string;
  created_at: string;
}

export interface OverviewPayload {
  start_date: string;
  end_date: string;
  review_count: number;
  average_rating: number | null;
  rating_trend: RatingTrendPoint[];
  positive_themes: ThemePayload[];
  negative_themes: ThemePayload[];
  active_insights: InsightSummary[];
}

export const getOverview = () => apiGet<OverviewPayload>("/overview");

export interface TaxonomyNode {
  id: string;
  name: string;
  description: string;
  slug: string;
  sort_order: number;
  children: TaxonomyNode[];
}

export interface TaxonomyTreePayload {
  version_id: string;
  version_number: number;
  activated_at: string | null;
  nodes: TaxonomyNode[];
}

export const getTaxonomy = () => apiGet<TaxonomyTreePayload | null>("/taxonomy");

export interface RatingHistoryPoint {
  date: string;
  review_count: number;
  average_rating: number | null;
}

export interface RatingHistoryPayload {
  start_date: string;
  end_date: string;
  points: RatingHistoryPoint[];
}

export interface CategoryMovement {
  category_id: string;
  category_name: string;
  sentiment: string;
  current_count: number;
  previous_count: number;
  delta: number;
}

export interface TrendsSummaryPayload {
  current_start: string;
  current_end: string;
  previous_start: string;
  previous_end: string;
  biggest_increases: CategoryMovement[];
  biggest_decreases: CategoryMovement[];
}

export const getRatingTrend = () => apiGet<RatingHistoryPayload>("/trends/ratings");
export const getTrendsSummary = () => apiGet<TrendsSummaryPayload>("/trends/summary");

export interface CategoryTrendPoint {
  category_id: string;
  category_name: string;
  sentiment: string;
  mention_count: number;
}

export interface CategoryTrendsPayload {
  start_date: string;
  end_date: string;
  categories: CategoryTrendPoint[];
}

export const getCategoryTrends = (sentiment?: string) => {
  const params = new URLSearchParams();
  if (sentiment) params.set("sentiment", sentiment);
  const query = params.toString();
  return apiGet<CategoryTrendsPayload>(`/trends/categories${query ? `?${query}` : ""}`);
};

export interface InsightListItem {
  id: string;
  title: string;
  severity: string;
  status: string;
  created_at: string;
}

export interface InsightAction {
  id: string;
  action_text: string;
  action_date: string | null;
  note_text: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface InsightDetail {
  id: string;
  title: string;
  summary: string;
  severity: string;
  evidence_summary: string;
  status: string;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  related_review_ids: string[];
  actions: InsightAction[];
  impact: Record<string, unknown> | null;
}

export const getInsights = () => apiGet<InsightListItem[]>("/insights");
export const getInsight = (insightId: string) => apiGet<InsightDetail>(`/insights/${insightId}`);

export interface SettingsPayload {
  default_date_range_days: number | null;
  daily_sync_time: string | null;
  classification_threshold: number | null;
  active_model: string;
  embedding_model: string;
}

export const getSettings = () => apiGet<SettingsPayload>("/settings");
