const API_BASE = "/api/v1";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    if (res.status === 401 && !window.location.pathname.includes("/login")) {
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

// ── Keywords ──────────────────────────────────────────────────────────────────
export const keywordsApi = {
  list: (group?: string) =>
    request<Keyword[]>(`/keywords${group !== undefined ? `?group=${encodeURIComponent(group)}` : ""}`),
  listGroups: () => request<string[]>("/keywords/groups"),
  articleStats: () => request<Record<string, { day: string; count: number }[]>>("/keywords/article-stats"),
  create: (data: { text: string; url?: string; source_type?: string; group_name?: string; crawl_interval_hours?: number; requires_js?: boolean }) =>
    request<Keyword>("/keywords", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: { is_active?: boolean; url?: string; source_type?: string; group_name?: string; crawl_interval_hours?: number; requires_js?: boolean }) =>
    request<Keyword>(`/keywords/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: string) => request(`/keywords/${id}`, { method: "DELETE" }),
  export: () => request<KeywordExportItem[]>("/keywords/export"),
  import: (data: KeywordExportItem[]) =>
    request<{ added: number; skipped: number }>("/keywords/import", { method: "POST", body: JSON.stringify(data) }),
  recommend: () => request<KeywordRecommendation[]>("/keywords/recommend", { method: "POST" }),
};

// ── Crawl Jobs ────────────────────────────────────────────────────────────────
export const crawlJobsApi = {
  list: (limit = 20, offset = 0) => request<CrawlJob[]>(`/crawl-jobs?limit=${limit}&offset=${offset}&_t=${Date.now()}`),
  trigger: () => request<CrawlJob>("/crawl-jobs", { method: "POST" }),
  retry: (id: string) => request<CrawlJob>(`/crawl-jobs/${id}/retry`, { method: "POST" }),
  get: (id: string) => request<CrawlJob>(`/crawl-jobs/${id}`),
  results: (id: string) => request<CrawlResult[]>(`/crawl-jobs/${id}/results`),
};

// ── Digests ───────────────────────────────────────────────────────────────────
export const digestsApi = {
  list: (q?: string, keyword?: string, limit = 20, offset = 0) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (keyword) params.set("keyword", keyword);
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    return request<DigestListItem[]>(`/digests?${params.toString()}`);
  },
  semanticSearch: (q: string, limit = 10) =>
    request<DigestListItem[]>(`/digests/search/semantic?q=${encodeURIComponent(q)}&limit=${limit}`),
  timeline: (keyword: string, days = 90) =>
    request<TimelineDay[]>(`/digests/timeline?keyword=${encodeURIComponent(keyword)}&days=${days}`),
  listKeywords: (q?: string) =>
    request<KeywordHistorySummary[]>(`/digests/keywords${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  keywordHistory: (keyword: string, limit = 30) =>
    request<KeywordHistoryEntry[]>(`/digests/keywords/${encodeURIComponent(keyword)}/history?limit=${limit}`),
  get: (id: string) => request<Digest>(`/digests/${id}`),
  usage: () => request<UsageStats>("/digests/usage"),
  markRead: (id: string, is_read: boolean) =>
    request<Digest>(`/digests/${id}`, { method: "PATCH", body: JSON.stringify({ is_read }) }),
  markAllRead: () => request("/digests/mark-all-read", { method: "POST" }),
  delete: (id: string) => request(`/digests/${id}`, { method: "DELETE" }),
  regenerate: (id: string) => request<Digest>(`/digests/${id}/regenerate`, { method: "POST" }),
  share: (id: string) => request<Digest>(`/digests/${id}/share`, { method: "POST" }),
  unshare: (id: string) => request<Digest>(`/digests/${id}/share`, { method: "DELETE" }),
  setFeedback: (id: string, value: "positive" | "negative") =>
    request<Digest>(`/digests/${id}/feedback`, { method: "PUT", body: JSON.stringify({ value }) }),
  deleteFeedback: (id: string) => request<Digest>(`/digests/${id}/feedback`, { method: "DELETE" }),
  star: (id: string) => request<Digest>(`/digests/${id}/star`, { method: "POST" }),
  unstar: (id: string) => request<Digest>(`/digests/${id}/star`, { method: "DELETE" }),
};

// ── Public (no-auth) ──────────────────────────────────────────────────────────
export const publicApi = {
  getSharedDigest: (token: string) => request<Digest>(`/public/digests/${token}`),
};

// ── Settings ──────────────────────────────────────────────────────────────────
export const settingsApi = {
  getLlm: () => request<LlmConfig>("/settings/llm"),
  upsertLlm: (data: { provider: string; api_key: string; model_name: string; base_url?: string; prompt_template?: string; summary_style?: string; embedding_model?: string }) =>
    request<LlmConfig>("/settings/llm", { method: "PUT", body: JSON.stringify(data) }),
  deleteLlm: () => request("/settings/llm", { method: "DELETE" }),
  testLlm: () => request<{ success: boolean; message: string }>("/settings/llm/test", { method: "POST" }),

  getNotification: () => request<NotificationConfig>("/settings/notification"),
  upsertNotification: (data: { webhook_type: string; webhook_url: string; is_active: boolean }) =>
    request<NotificationConfig>("/settings/notification", { method: "PUT", body: JSON.stringify(data) }),
  deleteNotification: () => request("/settings/notification", { method: "DELETE" }),
  testNotification: () => request<{ success: boolean; message: string }>("/settings/notification/test", { method: "POST" }),
};

// ── Stats ─────────────────────────────────────────────────────────────────────
export const statsApi = {
  get: () => request<Stats>("/stats"),
};

// ── Export ────────────────────────────────────────────────────────────────────
export const digestExportApi = {
  toNotion: (digestId: string) =>
    request<{ url: string }>(`/digests/${digestId}/export/notion`, { method: "POST" }),
  pdfUrl: (digestId: string) => `/api/v1/digests/${digestId}/export/pdf`,
  epubUrl: (digestId: string) => `/api/v1/digests/${digestId}/export/epub`,
};

export const notionSettingsApi = {
  get: () => request<NotionConfig>("/settings/notion"),
  upsert: (data: { notion_token?: string; database_id: string }) =>
    request<NotionConfig>("/settings/notion", { method: "PUT", body: JSON.stringify(data) }),
  delete: () => request("/settings/notion", { method: "DELETE" }),
};

// ── Admin ─────────────────────────────────────────────────────────────────────
export const adminApi = {
  getUsers: (limit = 50, offset = 0) =>
    request<User[]>(`/admin/users?limit=${limit}&offset=${offset}`),
  updateUser: (id: string, is_active: boolean) =>
    request<User>(`/admin/users/${id}?is_active=${is_active}`, { method: "PATCH" }),
  getStats: () => request<AdminStats>("/admin/stats"),
  triggerAll: () => request<{ message: string }>("/admin/crawl/trigger-all", { method: "POST" }),
  getAuditLogs: (limit = 100, offset = 0) =>
    request<AuditLog[]>(`/admin/audit-logs?limit=${limit}&offset=${offset}`),
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

export interface Keyword {
  id: string;
  text: string;
  is_active: boolean;
  url: string | null;
  source_type: string;
  group_name: string | null;
  crawl_interval_hours: number;
  last_crawled_at: string | null;
  requires_js: boolean;
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
  digest_created_at: string | null;
  new_content_found: boolean;
  summary_expected: boolean;
  digest_error: string | null;
}

export interface CrawlResult {
  id: string;
  keyword_text: string | null;
  http_status: number | null;
  content_preview: string | null;
  article_count: number;
  error_message: string | null;
  crawled_at: string;
}

export interface DigestListItem {
  id: string;
  title: string | null;
  keywords_used: string[] | null;
  sources_count: number;
  is_read: boolean;
  created_at: string;
  feedback: "positive" | "negative" | null;
  is_starred: boolean;
  importance_score: number | null;
}

export interface Digest extends DigestListItem {
  crawl_job_id: string;
  summary_md: string | null;
  keywords_used: string[] | null;
  tokens_used: number;
  llm_model: string | null;
  share_token: string | null;
  keyword_cards: DigestKeywordCard[];
}

export interface DigestKeywordCard {
  keyword: string;
  summary_md: string;
  crawl_date: string | null;
}

export interface KeywordHistorySummary {
  keyword: string;
  latest_crawled_at: string | null;
  total_days: number;
}

export interface KeywordHistoryEntry {
  keyword: string;
  crawl_date: string;
  crawled_at: string;
  summary_md: string;
  article_count: number;
  digest_id: string | null;
  title: string | null;
  sources: KeywordHistorySource[];
}

export interface KeywordHistorySource {
  name: string;
  url: string;
}

export interface LlmConfig {
  provider: string;
  api_key_masked: string;
  model_name: string;
  base_url: string | null;
  prompt_template: string | null;
  summary_style: "concise" | "detailed" | "academic";
  embedding_model: string | null;
}

export interface TimelineDay {
  date: string;
  digests: {
    id: string;
    title: string | null;
    created_at: string;
    importance_score: number | null;
    is_read: boolean;
  }[];
}

export interface KeywordRecommendation {
  text: string;
  reason: string;
}

export interface NotificationConfig {
  webhook_type: string;
  webhook_url: string;
  webhook_url_masked: string;
  is_active: boolean;
}

export interface UsageMonthly {
  month: string;
  tokens: number;
  digests: number;
}

export interface UsageStats {
  total_tokens: number;
  total_digests: number;
  this_month_tokens: number;
  this_month_digests: number;
  monthly: UsageMonthly[];
}

export interface Stats {
  this_month_crawls: number;
  this_month_sources: number;
  this_month_tokens: number;
  unread_digests: number;
}

export interface NotionConfig {
  notion_token_masked: string;
  database_id: string;
}

export interface AdminStats {
  total_users: number;
  total_crawl_jobs: number;
  total_digests: number;
  total_tokens_used: number;
}

export interface AuditLog {
  id: string;
  actor_email: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  detail: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface KeywordExportItem {
  text: string;
  url: string | null;
  source_type: string;
  group_name: string | null;
  crawl_interval_hours: number;
  is_active: boolean;
}
