const API_BASE = "/api/v1";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    if (res.status === 401) {
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const message = Array.isArray(detail)
      ? detail.map((e: any) => e.msg || JSON.stringify(e)).join("; ")
      : (typeof detail === "string" ? detail : "Request failed");
    throw new Error(message);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  register: (data: { email: string; password: string; display_name?: string }) =>
    request("/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: { email: string; password: string }) =>
    request<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  logout: () => request("/auth/logout", { method: "POST" }),

  me: () => request<User>("/auth/me"),

  updateMe: (data: { display_name?: string; password?: string }) =>
    request<User>("/auth/me", { method: "PATCH", body: JSON.stringify(data) }),
};

// ── Sources ───────────────────────────────────────────────────────────────────
export const sourcesApi = {
  list: () => request<Source[]>("/sources"),
  create: (data: { name: string; url?: string; search_query?: string; source_type: string }) =>
    request<Source>("/sources", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Source>) =>
    request<Source>(`/sources/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: string) => request(`/sources/${id}`, { method: "DELETE" }),
  test: (id: string) => request<SourceTestResult>(`/sources/${id}/test`, { method: "POST" }),
};

// ── Keywords ──────────────────────────────────────────────────────────────────
export const keywordsApi = {
  list: () => request<Keyword[]>("/keywords"),
  create: (data: { text: string; url?: string; source_type?: string }) =>
    request<Keyword>("/keywords", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: { is_active?: boolean; url?: string; source_type?: string }) =>
    request<Keyword>(`/keywords/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: string) => request(`/keywords/${id}`, { method: "DELETE" }),
};

// ── Crawl Jobs ────────────────────────────────────────────────────────────────
export const crawlJobsApi = {
  list: () => request<CrawlJob[]>("/crawl-jobs"),
  trigger: () => request<CrawlJob>("/crawl-jobs", { method: "POST" }),
  get: (id: string) => request<CrawlJob>(`/crawl-jobs/${id}`),
};

// ── Digests ───────────────────────────────────────────────────────────────────
export const digestsApi = {
  list: (q?: string) => request<DigestListItem[]>(`/digests${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  get: (id: string) => request<Digest>(`/digests/${id}`),
  markRead: (id: string, is_read: boolean) =>
    request<Digest>(`/digests/${id}`, { method: "PATCH", body: JSON.stringify({ is_read }) }),
  delete: (id: string) => request(`/digests/${id}`, { method: "DELETE" }),
  regenerate: (id: string) => request<Digest>(`/digests/${id}/regenerate`, { method: "POST" }),
};

// ── Settings ──────────────────────────────────────────────────────────────────
export const settingsApi = {
  getLlm: () => request<LlmConfig>("/settings/llm"),
  upsertLlm: (data: { provider: string; api_key: string; model_name: string; base_url?: string }) =>
    request<LlmConfig>("/settings/llm", { method: "PUT", body: JSON.stringify(data) }),
  deleteLlm: () => request("/settings/llm", { method: "DELETE" }),
  testLlm: () => request<{ success: boolean; message: string }>("/settings/llm/test", { method: "POST" }),

  getSchedule: () => request<ScheduleConfig>("/settings/schedule"),
  upsertSchedule: (data: ScheduleConfig) =>
    request<ScheduleConfig>("/settings/schedule", { method: "PUT", body: JSON.stringify(data) }),

  getNotification: () => request<NotificationConfig>("/settings/notification"),
  upsertNotification: (data: { webhook_type: string; webhook_url: string; is_active: boolean }) =>
    request<NotificationConfig>("/settings/notification", { method: "PUT", body: JSON.stringify(data) }),
  deleteNotification: () => request("/settings/notification", { method: "DELETE" }),
  testNotification: () => request<{ success: boolean; message: string }>("/settings/notification/test", { method: "POST" }),
};

// ── Types ─────────────────────────────────────────────────────────────────────
export interface User {
  id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface Source {
  id: string;
  name: string;
  url: string;
  search_query: string | null;
  source_type: string;
  is_active: boolean;
  crawl_interval_hours: number;
  last_crawled_at: string | null;
  created_at: string;
}

export interface SourceTestResult {
  success: boolean;
  http_status: number | null;
  content_preview: string | null;
  error: string | null;
}

export interface Keyword {
  id: string;
  text: string;
  is_active: boolean;
  url: string | null;
  source_type: string;
  created_at: string;
}

export interface CrawlJob {
  id: string;
  status: string;
  triggered_by: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
  has_digest: boolean;
  digest_id: string | null;
  new_content_found: boolean;
  digest_error: string | null;
}

export interface DigestListItem {
  id: string;
  title: string | null;
  keywords_used: string[] | null;
  sources_count: number;
  is_read: boolean;
  created_at: string;
}

export interface Digest extends DigestListItem {
  crawl_job_id: string;
  summary_md: string | null;
  keywords_used: string[] | null;
  tokens_used: number;
  llm_model: string | null;
}

export interface LlmConfig {
  provider: string;
  api_key_masked: string;
  model_name: string;
  base_url: string | null;
}

export interface ScheduleConfig {
  schedule_hour: number;
  schedule_minute: number;
  timezone: string;
  is_active: boolean;
}

export interface NotificationConfig {
  webhook_type: string;
  webhook_url: string;
  is_active: boolean;
}
