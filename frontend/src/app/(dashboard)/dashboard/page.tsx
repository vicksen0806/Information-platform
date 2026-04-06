"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import {
  crawlJobsApi,
  keywordsApi,
  statsApi,
  type CrawlJob,
  type CrawlResult,
  type Keyword,
  type KeywordExportItem,
  type KeywordRecommendation,
  type Stats,
} from "@/lib/api";
import { useT } from "@/lib/i18n";

const DIGEST_TIMEOUT_MS = 90 * 1000;

function isGeneratingDigest(job: CrawlJob) {
  if (job.status !== "completed" || job.has_digest) return false;
  if (!job.new_content_found) return false;
  const completedAt = job.completed_at ? new Date(job.completed_at).getTime() : null;
  if (!completedAt) return false;
  return Date.now() - completedAt < DIGEST_TIMEOUT_MS;
}

function isActive(job: CrawlJob) {
  return job.status === "pending" || job.status === "running" || isGeneratingDigest(job);
}

function MiniTrend({ data }: { data: { day: string; count: number }[] }) {
  const t = useT();
  const days = Array.from({ length: 30 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (29 - i));
    return d.toISOString().slice(0, 10);
  });
  const countMap: Record<string, number> = {};
  for (const { day, count } of (data || [])) countMap[day] = count;
  const filled = days.map((day) => ({ day, count: countMap[day] || 0 }));
  const total = filled.reduce((s, d) => s + d.count, 0);
  const max = Math.max(...filled.map((d) => d.count), 1);

  if (total === 0) {
    return (
      <div className="flex items-center gap-1.5">
        <div className="flex h-4 items-end gap-px">
          {filled.map((d) => (
            <div key={d.day} className="w-0.5 rounded-sm bg-muted" style={{ height: "4px" }} />
          ))}
        </div>
        <span className="text-xs text-muted-foreground/40">{t("kw_no_data")}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5" title={`${t("kw_article_trend")}: ${total}`}>
      <div className="flex h-4 items-end gap-px">
        {filled.map((d) => (
          <div
            key={d.day}
            className={`w-0.5 rounded-sm ${d.count > 0 ? "bg-primary/70" : "bg-muted"}`}
            style={{ height: d.count > 0 ? `${Math.max((d.count / max) * 100, 25)}%` : "4px" }}
            title={`${d.day}: ${d.count}`}
          />
        ))}
      </div>
      <span className="text-xs text-muted-foreground">{total} {t("kw_article_trend")}</span>
    </div>
  );
}

function useIntervalOptions() {
  const t = useT();
  return [
    { value: 1, label: t("kw_interval_1") },
    { value: 6, label: t("kw_interval_6") },
    { value: 12, label: t("kw_interval_12") },
    { value: 24, label: t("kw_interval_24") },
    { value: 72, label: t("kw_interval_72") },
    { value: 168, label: t("kw_interval_168") },
  ];
}

function ResultsPreview({ jobId }: { jobId: string }) {
  const t = useT();
  const [results, setResults] = useState<CrawlResult[] | null>(null);

  useEffect(() => {
    crawlJobsApi.results(jobId).then(setResults).catch(() => setResults([]));
  }, [jobId]);

  if (!results) return <p className="px-1 py-2 text-xs text-muted-foreground">{t("dash_preview_loading")}</p>;

  return (
    <div className="mt-2 space-y-1.5 border-t border-border pt-2">
      {results.map((r) => (
        <div key={r.id} className="flex items-start gap-2 text-xs">
          <span
            className={`mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full ${
              r.error_message && r.error_message !== "Content unchanged since last crawl"
                ? "bg-red-400"
                : r.error_message
                  ? "bg-yellow-400"
                  : "bg-green-400"
            }`}
          />
          <div className="min-w-0">
            <span className="font-medium">{r.keyword_text || "—"}</span>
            {r.error_message ? (
              <span className="ml-1 text-muted-foreground">
                {r.error_message === "Content unchanged since last crawl" ? t("dash_preview_dup") : t("dash_preview_error")}
              </span>
            ) : (
              <span className="ml-1 text-muted-foreground">{t("dash_preview_articles", { n: r.article_count })}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const t = useT();
  const intervalOptions = useIntervalOptions();

  const [jobs, setJobs] = useState<CrawlJob[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [groups, setGroups] = useState<string[]>([]);
  const [articleStats, setArticleStats] = useState<Record<string, { day: string; count: number }[]>>({});

  const [loadingJobs, setLoadingJobs] = useState(true);
  const [loadingKeywords, setLoadingKeywords] = useState(true);
  const [error, setError] = useState("");

  const [crawling, setCrawling] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [, setTick] = useState(0);

  const [newText, setNewText] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [newSourceType, setNewSourceType] = useState("webpage");
  const [hasUrl, setHasUrl] = useState(false);
  const [newGroup, setNewGroup] = useState("");
  const [newInterval, setNewInterval] = useState(24);
  const [savingKeyword, setSavingKeyword] = useState(false);

  const [filterGroup, setFilterGroup] = useState<string | null>(null);
  const [importMsg, setImportMsg] = useState("");
  const importInputRef = useRef<HTMLInputElement>(null);

  const [recommendations, setRecommendations] = useState<KeywordRecommendation[]>([]);
  const [recommendLoading, setRecommendLoading] = useState(false);
  const [showRecommend, setShowRecommend] = useState(false);
  const [addingRec, setAddingRec] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editUrl, setEditUrl] = useState("");
  const [editSourceType, setEditSourceType] = useState("webpage");
  const [editHasUrl, setEditHasUrl] = useState(false);
  const [editGroup, setEditGroup] = useState("");
  const [editInterval, setEditInterval] = useState(24);
  const [editRequiresJs, setEditRequiresJs] = useState(false);

  const hasActive = jobs.some(isActive);
  const digestError = jobs.find((j) => j.digest_error)?.digest_error ?? null;
  const activeKeywords = keywords.filter((k) => k.is_active).length;

  const loadJobs = useCallback(async () => {
    try {
      const list = await crawlJobsApi.list();
      setJobs(list);
    } catch (err: any) {
      setError(err.message || "Failed to load jobs");
    } finally {
      setLoadingJobs(false);
    }
  }, []);

  const loadKeywords = useCallback(async () => {
    try {
      const [kws, grps, statsMap] = await Promise.all([
        keywordsApi.list(),
        keywordsApi.listGroups(),
        keywordsApi.articleStats(),
      ]);
      setKeywords(kws);
      setGroups(grps);
      setArticleStats(statsMap);
    } catch (err: any) {
      setError(err.message || "Failed to load keywords");
    } finally {
      setLoadingKeywords(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
    loadKeywords();
    statsApi.get().then(setStats).catch(() => {});
  }, [loadJobs, loadKeywords]);

  useEffect(() => {
    if (!hasActive) return;
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, [hasActive, loadJobs]);

  useEffect(() => {
    if (!hasActive) return;
    const timer = setInterval(() => setTick((v) => v + 1), 1000);
    return () => clearInterval(timer);
  }, [hasActive]);

  function statusLabel(job: CrawlJob): string {
    if (job.status === "pending") return t("dash_status_queued");
    if (job.status === "running") return t("dash_status_crawling");
    if (job.status === "failed") return t("dash_status_failed");
    if (isGeneratingDigest(job)) return t("dash_status_generating");
    if (job.status === "completed") {
      if (!job.new_content_found) return t("dash_status_completed_no_new");
      return t("dash_status_completed");
    }
    return t("dash_status_completed");
  }

  function statusColor(job: CrawlJob): string {
    if (job.status === "pending") return "bg-yellow-100 text-yellow-700";
    if (job.status === "running") return "bg-blue-100 text-blue-700";
    if (job.status === "failed") return "bg-red-100 text-red-700";
    if (isGeneratingDigest(job)) return "bg-blue-100 text-blue-700";
    if (job.status === "completed" && !job.new_content_found) return "bg-green-100 text-green-700";
    return "bg-green-100 text-green-700";
  }

  function formatDuration(start: string | null, end: string | null, live = false): string {
    if (!start) return "";
    const s = new Date(start).getTime();
    const e = live ? Date.now() : (end ? new Date(end).getTime() : new Date(start).getTime());
    const sec = Math.floor((e - s) / 1000);
    if (sec < 60) return `${sec}s`;
    return `${Math.floor(sec / 60)}m ${sec % 60}s`;
  }

  function intervalLabel(hours: number) {
    return intervalOptions.find((o) => o.value === hours)?.label ?? `${hours}h`;
  }

  async function handleCrawlNow() {
    setCrawling(true);
    setError("");
    try {
      const job = await crawlJobsApi.trigger();
      setJobs((prev) => [job, ...prev]);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setCrawling(false);
    }
  }

  async function handleRetry(jobId: string) {
    setRetryingId(jobId);
    try {
      const job = await crawlJobsApi.retry(jobId);
      setJobs((prev) => [job, ...prev.filter((j) => j.id !== jobId)]);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setRetryingId(null);
    }
  }

  async function handleAddKeyword(e: React.FormEvent) {
    e.preventDefault();
    const text = newText.trim();
    if (!text) return;
    setSavingKeyword(true);
    setError("");
    try {
      const kw = await keywordsApi.create({
        text,
        url: hasUrl && newUrl.trim() ? newUrl.trim() : undefined,
        source_type: hasUrl && newUrl.trim() ? newSourceType : "search",
        group_name: newGroup.trim() || undefined,
        crawl_interval_hours: 24,
      });
      setKeywords((prev) => [...prev, kw]);
      if (newGroup.trim() && !groups.includes(newGroup.trim())) {
        setGroups((prev) => [...prev, newGroup.trim()].sort());
      }
      setNewText("");
      setNewUrl("");
      setHasUrl(false);
      setNewGroup("");
      setNewInterval(24);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSavingKeyword(false);
    }
  }

  async function handleRecommend() {
    setRecommendLoading(true);
    setShowRecommend(true);
    try {
      const recs = await keywordsApi.recommend();
      setRecommendations(recs);
      setError("");
    } catch (err: any) {
      setRecommendations([]);
      setError(err.message || "智能推荐失败");
    } finally {
      setRecommendLoading(false);
    }
  }

  async function handleAddRecommendation(text: string) {
    setAddingRec(text);
    try {
      const kw = await keywordsApi.create({ text, source_type: "search" });
      setKeywords((prev) => [...prev, kw]);
      setRecommendations((prev) => prev.filter((r) => r.text !== text));
    } finally {
      setAddingRec(null);
    }
  }

  async function handleExportKeywords() {
    const data = await keywordsApi.export();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "keywords.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text) as KeywordExportItem[];
      const result = await keywordsApi.import(data);
      setImportMsg(t("kw_import_success", { added: result.added, skipped: result.skipped }));
      await loadKeywords();
      setTimeout(() => setImportMsg(""), 4000);
    } catch {
      setImportMsg(t("kw_import_error"));
      setTimeout(() => setImportMsg(""), 3000);
    } finally {
      if (importInputRef.current) importInputRef.current.value = "";
    }
  }

  async function handleToggleKeyword(kw: Keyword) {
    const updated = await keywordsApi.update(kw.id, { is_active: !kw.is_active });
    setKeywords((prev) => prev.map((item) => (item.id === kw.id ? updated : item)));
  }

  async function handleDeleteKeyword(id: string) {
    if (!confirm(t("kw_delete_confirm"))) return;
    await keywordsApi.delete(id);
    setKeywords((prev) => prev.filter((item) => item.id !== id));
  }

  function startEditKeyword(kw: Keyword) {
    setEditingId(kw.id);
    setEditHasUrl(!!kw.url);
    setEditUrl(kw.url || "");
    setEditSourceType(kw.source_type === "search" ? "webpage" : kw.source_type);
    setEditGroup(kw.group_name || "");
    setEditInterval(24);
    setEditRequiresJs(kw.requires_js || false);
  }

  async function handleSaveEdit(kw: Keyword) {
    const url = editHasUrl && editUrl.trim() ? editUrl.trim() : null;
    const updated = await keywordsApi.update(kw.id, {
      url: url || undefined,
      source_type: url ? editSourceType : "search",
      group_name: editGroup.trim() || undefined,
      crawl_interval_hours: 24,
      requires_js: editRequiresJs,
    });
    setKeywords((prev) => prev.map((item) => (item.id === kw.id ? updated : item)));
    setGroups(await keywordsApi.listGroups());
    setEditingId(null);
  }

  const filteredKeywords = filterGroup !== null
    ? keywords.filter((k) => (filterGroup === "" ? !k.group_name : k.group_name === filterGroup))
    : keywords;

  const groupedKeywords: Record<string, Keyword[]> = {};
  for (const kw of filteredKeywords) {
    const groupKey = kw.group_name || "";
    if (!groupedKeywords[groupKey]) groupedKeywords[groupKey] = [];
    groupedKeywords[groupKey].push(kw);
  }

  const groupKeys = Object.keys(groupedKeywords).sort((a, b) => {
    if (a === "") return 1;
    if (b === "") return -1;
    return a.localeCompare(b);
  });

  const jobsLoadingState = loadingJobs;
  const keywordsLoadingState = loadingKeywords;

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t("dash_title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            统一管理关键词、触发抓取，并查看每次任务的进度与结果。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {importMsg && <span className="text-xs text-muted-foreground">{importMsg}</span>}
          <button
            onClick={handleRecommend}
            disabled={recommendLoading}
            className="rounded border border-primary/40 px-3 py-1.5 text-xs text-primary transition-colors hover:bg-primary/5 disabled:opacity-50"
          >
            {recommendLoading ? t("kw_recommending") : t("kw_recommend")}
          </button>
          <button
            onClick={handleExportKeywords}
            className="rounded border border-border px-3 py-1.5 text-xs transition-colors hover:bg-muted"
          >
            {t("kw_export")}
          </button>
          <button
            onClick={() => importInputRef.current?.click()}
            className="rounded border border-border px-3 py-1.5 text-xs transition-colors hover:bg-muted"
          >
            {t("kw_import")}
          </button>
          <input ref={importInputRef} type="file" accept=".json" className="hidden" onChange={handleImportFile} />
          <button
            onClick={handleCrawlNow}
            disabled={crawling || activeKeywords === 0}
            className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {crawling ? t("dash_submitting") : t("dash_crawl_now")}
          </button>
        </div>
      </div>

      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
          {[
            { label: t("kw_title"), value: `${activeKeywords}/${keywords.length}` },
            { label: t("dash_stat_crawls"), value: stats.this_month_crawls },
            { label: t("dash_stat_sources"), value: stats.this_month_sources },
            { label: t("dash_stat_tokens"), value: stats.this_month_tokens },
            { label: t("dash_stat_unread"), value: stats.unread_digests },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-lg border border-border bg-background px-4 py-3 text-center">
              <p className="mb-1 text-xs text-muted-foreground">{label}</p>
              <p className="text-xl font-bold tabular-nums">{value}</p>
            </div>
          ))}
        </div>
      )}

      {digestError && (
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3">
          <span className="mt-0.5 text-lg leading-none text-destructive">⚠</span>
          <div>
            <p className="text-sm font-medium text-destructive">{t("dash_api_inactive")}</p>
            <p className="mt-0.5 text-xs text-destructive/80">
              {t("dash_api_inactive_sub")}
              <a href="/settings" className="ml-1 underline">{t("dash_go_settings")}</a>
            </p>
          </div>
        </div>
      )}

      {showRecommend && (
        <div className="mb-6 rounded-lg border border-primary/20 bg-primary/5 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold">{t("kw_recommend_title")}</h3>
            <button onClick={() => setShowRecommend(false)} className="text-xs text-muted-foreground hover:text-foreground">
              {t("kw_recommend_close")}
            </button>
          </div>
          {recommendLoading ? (
            <div className="text-sm text-muted-foreground">{t("loading")}</div>
          ) : recommendations.length === 0 ? (
            <div className="text-sm text-muted-foreground">{t("kw_recommend_empty")}</div>
          ) : (
            <div className="space-y-2">
              {recommendations.map((rec) => (
                <div key={rec.text} className="flex items-center justify-between gap-3 rounded-md border border-border bg-background px-3 py-2">
                  <div className="min-w-0">
                    <span className="text-sm font-medium">{rec.text}</span>
                    <span className="ml-2 text-xs text-muted-foreground">{rec.reason}</span>
                  </div>
                  <button
                    onClick={() => handleAddRecommendation(rec.text)}
                    disabled={addingRec === rec.text}
                    className="shrink-0 rounded bg-primary px-2.5 py-1 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                  >
                    {addingRec === rec.text ? t("kw_recommend_adding") : t("kw_recommend_add")}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {error && <div className="mb-4 rounded bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>}

      <section className="mb-6 space-y-4">
        <div className="rounded-xl border border-border bg-background p-4">
          <div className="mb-4">
            <h2 className="text-lg font-semibold">{t("kw_title")}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {t("kw_subtitle", { a: activeKeywords, t: keywords.length })}
            </p>
          </div>

          {groups.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-1.5">
              <button
                onClick={() => setFilterGroup(null)}
                className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                  filterGroup === null ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-muted"
                }`}
              >
                {t("all")}
              </button>
              {groups.map((group) => (
                <button
                  key={group}
                  onClick={() => setFilterGroup(filterGroup === group ? null : group)}
                  className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                    filterGroup === group ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-muted"
                  }`}
                >
                  {group}
                </button>
              ))}
              <button
                onClick={() => setFilterGroup("")}
                className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                  filterGroup === "" ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-muted"
                }`}
              >
                {t("digests_ungrouped")}
              </button>
            </div>
          )}

          <form onSubmit={handleAddKeyword} className="space-y-3 rounded-lg border border-border bg-muted/20 p-4">
            <div className="flex gap-2">
              <input
                value={newText}
                onChange={(e) => setNewText(e.target.value)}
                className="flex-1 rounded-md border border-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder={t("kw_placeholder")}
                maxLength={200}
              />
              <button
                type="submit"
                disabled={savingKeyword || !newText.trim()}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {savingKeyword ? t("kw_adding") : t("kw_add")}
              </button>
            </div>

            <div className="flex flex-wrap gap-3">
              <div className="flex items-center gap-2">
                <label className="whitespace-nowrap text-xs text-muted-foreground">{t("kw_group_label")}</label>
                <input
                  value={newGroup}
                  onChange={(e) => setNewGroup(e.target.value)}
                  list="group-suggestions"
                  className="w-28 rounded-md border border-input px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder={t("kw_group_placeholder")}
                />
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>{t("kw_frequency")}</span>
                <span>{t("kw_daily_once")}</span>
              </div>
            </div>

            <datalist id="group-suggestions">
              {groups.map((group) => <option key={group} value={group} />)}
            </datalist>

            <label className="flex cursor-pointer items-center gap-2 text-sm select-none">
              <input type="checkbox" checked={hasUrl} onChange={(e) => setHasUrl(e.target.checked)} className="rounded" />
              <span className="text-muted-foreground">{t("kw_pin_url")}</span>
            </label>

            {hasUrl && (
              <div className="flex gap-2 pl-6">
                <select
                  value={newSourceType}
                  onChange={(e) => setNewSourceType(e.target.value)}
                  className="rounded-md border border-input px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="webpage">Webpage</option>
                  <option value="rss">RSS</option>
                </select>
                <input
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  className="flex-1 rounded-md border border-input px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="https://..."
                />
              </div>
            )}
          </form>
        </div>

        <div className="rounded-xl border border-border bg-background p-4">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">关键词列表</h2>
            <span className="text-xs text-muted-foreground">{activeKeywords}/{keywords.length} 已启用</span>
          </div>

          {keywordsLoadingState ? (
            <div className="py-12 text-center text-muted-foreground">{t("loading")}</div>
          ) : keywords.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">{t("kw_empty")}</div>
          ) : (
            <div className="space-y-4">
              {groupKeys.map((groupKey) => (
                <div key={groupKey}>
                  {groupKey && (
                    <div className="mb-2 flex items-center gap-2">
                      <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{groupKey}</span>
                      <div className="h-px flex-1 bg-border" />
                    </div>
                  )}
                  <div className="space-y-2">
                    {groupedKeywords[groupKey].map((kw) => (
                      <div
                        key={kw.id}
                        className={`rounded-lg border px-4 py-3 ${kw.is_active ? "border-border" : "border-border opacity-50"}`}
                      >
                        {editingId === kw.id ? (
                          <div className="space-y-2">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{kw.text}</span>
                              <span className="text-xs text-muted-foreground">{t("edit")}</span>
                            </div>
                            <div className="flex flex-wrap gap-3">
                              <div className="flex items-center gap-2">
                                <label className="text-xs text-muted-foreground">{t("kw_group_label")}</label>
                                <input
                                  value={editGroup}
                                  onChange={(e) => setEditGroup(e.target.value)}
                                  list="group-suggestions"
                                  className="w-28 rounded-md border border-input px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                                />
                              </div>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <span>{t("kw_frequency")}</span>
                                <span>{t("kw_daily_once")}</span>
                              </div>
                            </div>
                            <label className="flex cursor-pointer items-center gap-2 text-sm">
                              <input type="checkbox" checked={editHasUrl} onChange={(e) => setEditHasUrl(e.target.checked)} />
                              <span className="text-muted-foreground">{t("kw_pin_url")}</span>
                            </label>
                            {editHasUrl && (
                              <div className="flex gap-2 pl-6">
                                <select
                                  value={editSourceType}
                                  onChange={(e) => setEditSourceType(e.target.value)}
                                  className="rounded-md border border-input px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                >
                                  <option value="webpage">Webpage</option>
                                  <option value="rss">RSS</option>
                                </select>
                                <input
                                  value={editUrl}
                                  onChange={(e) => setEditUrl(e.target.value)}
                                  className="flex-1 rounded-md border border-input px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                  placeholder="https://..."
                                />
                              </div>
                            )}
                            <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
                              <input type="checkbox" checked={editRequiresJs} onChange={(e) => setEditRequiresJs(e.target.checked)} />
                              {t("kw_requires_js")}
                              <span className="opacity-60">({t("kw_requires_js_hint")})</span>
                            </label>
                            <div className="flex gap-2">
                              <button onClick={() => handleSaveEdit(kw)} className="rounded bg-primary px-3 py-1 text-xs text-primary-foreground hover:opacity-90">
                                {t("save")}
                              </button>
                              <button onClick={() => setEditingId(null)} className="rounded border border-border px-3 py-1 text-xs hover:bg-muted">
                                {t("cancel")}
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-start justify-between gap-4">
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="text-sm font-medium">{kw.text}</span>
                                {!kw.is_active && (
                                  <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">{t("disabled_label")}</span>
                                )}
                              </div>
                              <div className="mt-0.5 text-xs text-muted-foreground">
                                {kw.url ? (
                                  <span className="block max-w-lg truncate">
                                    {kw.source_type === "rss" ? "RSS · " : "Webpage · "}{kw.url}
                                  </span>
                                ) : (
                                  <span>{t("kw_google_news")}</span>
                                )}
                                {kw.last_crawled_at && (
                                  <span className="ml-2 text-muted-foreground/70">
                                    {t("kw_last_crawled", { t: new Date(kw.last_crawled_at).toLocaleString() })}
                                  </span>
                                )}
                              </div>
                              <div className="mt-1.5">
                                <MiniTrend data={articleStats[kw.text] || []} />
                              </div>
                            </div>
                            <div className="ml-4 flex shrink-0 items-center gap-2">
                              <button onClick={() => startEditKeyword(kw)} className="rounded border border-border px-2.5 py-1 text-xs hover:bg-muted">
                                {t("kw_configure")}
                              </button>
                              <button onClick={() => handleToggleKeyword(kw)} className="rounded border border-border px-2.5 py-1 text-xs hover:bg-muted">
                                {kw.is_active ? t("disable") : t("enable")}
                              </button>
                              <button onClick={() => handleDeleteKeyword(kw.id)} className="rounded border border-destructive/30 px-2.5 py-1 text-xs text-destructive hover:bg-destructive/10">
                                {t("delete")}
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-background p-4">
          <div className="mb-4">
            <h2 className="text-lg font-semibold">{t("dash_title")}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{t("dash_subtitle")}</p>
          </div>

          {jobsLoadingState ? (
            <div className="py-20 text-center text-muted-foreground">{t("loading")}</div>
          ) : jobs.length === 0 ? (
            <div className="py-20 text-center text-muted-foreground">
              <p className="mb-2 text-lg">{t("dash_empty_title")}</p>
              <p className="text-sm">{t("dash_empty_sub")}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {jobs.map((job) => {
                const active = isActive(job);
                const dur = formatDuration(job.started_at || job.created_at, null, true);
                const durationStr = active
                  ? `${t("dash_elapsed")} ${dur}`
                  : formatDuration(job.started_at, job.completed_at || job.created_at);
                const isExpanded = expandedId === job.id;
                const canPreview = job.status === "completed" || job.status === "failed";

                return (
                  <div key={job.id} className="rounded-lg border border-border px-4 py-3">
                    <div className="flex items-center gap-3">
                      <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(job)}`}>
                        {active && <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current align-middle" />}
                        {statusLabel(job)}
                      </span>

                      {job.has_digest && job.digest_id && (
                        <Link href={`/digests/${job.digest_id}`} className="shrink-0 rounded border border-border px-2.5 py-1 text-xs font-medium hover:bg-muted">
                          {t("dash_view_digest")}
                        </Link>
                      )}

                      {job.status === "failed" && (
                        <button
                          onClick={() => handleRetry(job.id)}
                          disabled={retryingId === job.id}
                          className="shrink-0 rounded border border-border px-2.5 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
                        >
                          {retryingId === job.id ? t("dash_retrying") : t("dash_retry")}
                        </button>
                      )}

                      {job.status === "failed" && job.error_message && (
                        <span className="max-w-[120px] shrink-0 truncate text-xs text-destructive" title={job.error_message}>
                          {job.error_message}
                        </span>
                      )}

                      <div className="flex-1" />

                      {canPreview && (
                        <button
                          onClick={() => setExpandedId(isExpanded ? null : job.id)}
                          className="shrink-0 text-xs text-muted-foreground transition-colors hover:text-foreground"
                        >
                          {isExpanded ? t("dash_hide_preview") : t("dash_preview")}
                        </button>
                      )}

                      <div className="shrink-0 text-right">
                        <p className="text-sm text-foreground">{new Date(job.created_at).toLocaleString()}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">{durationStr}</p>
                      </div>
                    </div>

                    {isExpanded && <ResultsPreview jobId={job.id} />}
                  </div>
                );
              })}
            </div>
          )}
      </section>
    </div>
  );
}
