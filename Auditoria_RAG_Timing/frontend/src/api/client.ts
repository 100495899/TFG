
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export type User = {
  id: string;
  email: string;
  role: string;
};

export type Target = {
  id: string;
  name: string;
  endpoint_url: string;
  headers: Record<string, string>;
  payload_template: Record<string, unknown>;
  timeout_seconds: number;
  verify_tls: boolean;
  created_at: string;
  updated_at: string;
};

export type TargetTestResult = {
  ok: boolean;
  status_code: number | null;
  ttfb_ms: number | null;
  full_response_ms: number | null;
  response_size_bytes: number | null;
  error_type: string | null;
  error_message: string | null;
};

export type Dataset = {
  id: string;
  name: string;
  original_filename: string;
  total_queries: number;
  created_at: string;
};

export type DatasetQuery = {
  query: string;
  frequency: "high" | "medium" | "low";
  length: "short" | "medium" | "long";
};

export type DatasetPreview = {
  dataset: Dataset;
  preview: DatasetQuery[];
  distribution: {
    frequency: Record<string, number>;
    length: Record<string, number>;
  };
};

export type AuditSession = {
  id: string;
  target_id: string;
  dataset_id: string;
  status: string;
  progress_current: number;
  progress_total: number;
  random_seed: number;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  calibration_requests: number;
};

export type AuditStatus = Pick<AuditSession, "id" | "status" | "progress_current" | "progress_total" | "error_message"> & {
  error_count: number;
  mean_ttfb_ms: number | null;
  mean_full_response_ms: number | null;
};

export type AuditResult = {
  id: string;
  request_index: number;
  query_text: string;
  frequency_tag: string;
  length_tag: string;
  latency_ms: number | null;
  ttfb_ms: number | null;
  full_response_ms: number | null;
  status_code: number | null;
  response_size_bytes: number | null;
  is_error: boolean;
  error_type: string | null;
  timestamp: string;
};

export type ResultsPage = {
  total: number;
  page: number;
  page_size: number;
  items: AuditResult[];
};

export type Summary = {
  session_id: string;
  metric: string;
  groups: Array<{
    frequency: string;
    count: number;
    mean_ms: number | null;
    median_ms: number | null;
    std_ms: number | null;
    p95_ms: number | null;
    error_rate: number;
  }>;
  comparisons: Array<{
    group_a: string;
    group_b: string;
    mean_difference_ms: number | null;
    median_difference_ms: number | null;
    welch_p_value: number | null;
    mann_whitney_p_value: number | null;
    cohens_d: number | null;
    evidence: string;
  }>;
};

export type ResultFilters = {
  frequency?: string;
  length?: string;
  is_error?: string;
  status_code?: string;
};

type ApiErrorDetail =
  | string
  | Array<{ msg?: string; message?: string }>
  | {
      message?: string;
      errors?: Array<{ msg?: string; message?: string }>;
    };

function apiErrorMessage(detail: ApiErrorDetail | undefined, fallback: string) {
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail[0]?.msg ?? detail[0]?.message ?? fallback;
  }

  if (detail && typeof detail === "object") {
    const validationMessage = detail.errors?.[0]?.msg ?? detail.errors?.[0]?.message;
    return validationMessage ? `${detail.message ?? fallback} ${validationMessage}` : detail.message ?? fallback;
  }

  return fallback;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, credentials: "include" });
  if (response.status === 401) {
    if (window.location.pathname !== "/login") {
      window.location.replace("/login");
    }
  }
  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const errorBody = await response.json() as { detail?: ApiErrorDetail };
      throw new Error(apiErrorMessage(errorBody.detail, response.statusText));
    }
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  return response.text() as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<User>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request<User>("/api/v1/auth/me"),
  logout: () => request<{ ok: boolean }>("/api/v1/auth/logout", { method: "POST" }),
  targets: () => request<Target[]>("/api/v1/targets"),
  createTarget: (payload: unknown) => request<Target>("/api/v1/targets", { method: "POST", body: JSON.stringify(payload) }),
  updateTarget: (id: string, payload: unknown) => request<Target>(`/api/v1/targets/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteTarget: (id: string) => request(`/api/v1/targets/${id}`, { method: "DELETE" }),
  testTarget: (id: string, query: string) => request<TargetTestResult>(`/api/v1/targets/${id}/test`, { method: "POST", body: JSON.stringify({ query }) }),
  datasets: () => request<Dataset[]>("/api/v1/datasets"),
  uploadDataset: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Dataset>("/api/v1/datasets/upload", { method: "POST", body: form });
  },
  datasetPreview: (id: string) => request<DatasetPreview>(`/api/v1/datasets/${id}/preview`),
  deleteDataset: (id: string) => request(`/api/v1/datasets/${id}`, { method: "DELETE" }),
  audits: () => request<AuditSession[]>("/api/v1/audits"),
  startAudit: (payload: unknown) => request<{ session_id: string }>("/api/v1/audits/start", { method: "POST", body: JSON.stringify(payload) }),
  auditStatus: (id: string) => request<AuditStatus>(`/api/v1/audits/${id}/status`),
  auditResults: (id: string, page: number, filters: ResultFilters = {}) => {
    const params = new URLSearchParams({ page: String(page), page_size: "100" });
    if (filters.frequency) params.set("frequency", filters.frequency);
    if (filters.length) params.set("length", filters.length);
    if (filters.is_error) params.set("is_error", filters.is_error);
    if (filters.status_code) params.set("status_code", filters.status_code);
    return request<ResultsPage>(`/api/v1/audits/${id}/results?${params.toString()}`);
  },
  auditSummary: (id: string) => request<Summary>(`/api/v1/audits/${id}/summary`),
  abortAudit: (id: string) => request(`/api/v1/audits/${id}/abort`, { method: "POST" }),
  deleteAudit: (id: string) => request(`/api/v1/audits/${id}`, { method: "DELETE" }),
  exportUrl: (id: string, format: "csv" | "json") => `${API_BASE_URL}/api/v1/audits/${id}/export.${format}`
};
