
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

export type AuditDashboardItem = AuditStatus & {
  target_id: string;
  target_name: string;
  dataset_id: string;
  dataset_name: string;
  random_seed: number;
  calibration_requests: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
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
  metadata: {
    target_id: string;
    target_name: string;
    dataset_id: string;
    dataset_name: string;
    status: string;
    random_seed: number;
    calibration_requests: number;
    total_requests: number;
    successful_requests: number;
    error_requests: number;
    started_at: string | null;
    completed_at: string | null;
    duration_seconds: number | null;
  };
  overall: SummaryGroup;
  overall_full_response: SummaryGroup;
  groups: SummaryGroup[];
  by_length: SummaryGroup[];
  by_frequency_length: SummaryGroup[];
  comparisons: Array<{
    group_a: string;
    group_b: string;
    mean_difference_ms: number | null;
    median_difference_ms: number | null;
    p_value: number | null;
    evidence: string;
  }>;
  points: Array<{
    request_index: number;
    frequency: string;
    length: string;
    ttfb_ms: number;
    full_response_ms: number | null;
    is_outlier: boolean;
  }>;
};

export type SummaryGroup = {
  frequency: string | null;
  length: string | null;
  count: number;
  raw_count: number;
  error_count: number;
  outlier_count: number;
  mean_ms: number | null;
  median_ms: number | null;
  std_ms: number | null;
  p25_ms: number | null;
  p75_ms: number | null;
  p95_ms: number | null;
  min_ms: number | null;
  max_ms: number | null;
  lower_outlier_threshold_ms: number | null;
  upper_outlier_threshold_ms: number | null;
  error_rate: number;
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

function handleUnauthorized(response: Response) {
  if (response.status === 401 && window.location.pathname !== "/login") {
    window.location.replace("/login");
  }
}

async function responseError(response: Response): Promise<Error> {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const errorBody = await response.json() as { detail?: ApiErrorDetail };
    return new Error(apiErrorMessage(errorBody.detail, response.statusText));
  }
  const text = await response.text();
  return new Error(text || response.statusText);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, credentials: "include" });
  handleUnauthorized(response);
  if (!response.ok) {
    throw await responseError(response);
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  return response.text() as T;
}

async function requestBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`, { credentials: "include" });
  handleUnauthorized(response);
  if (!response.ok) {
    throw await responseError(response);
  }
  return response.blob();
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
  auditDashboard: () => request<AuditDashboardItem[]>("/api/v1/audits/dashboard"),
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
  downloadAuditCsv: (id: string, type: "summary" | "raw") =>
    requestBlob(`/api/v1/audits/${id}/${type === "summary" ? "export-summary.csv" : "export.csv"}`)
};
