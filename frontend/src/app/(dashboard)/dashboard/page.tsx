"use client";
import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  crawlJobsApi,
  digestsApi,
  keywordsApi,
  type CrawlJob,
  type Keyword,
  type KeywordHistorySummary,
  type KeywordRecommendation,
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

export default function DashboardPage() {
  const t = useT();

  const [jobs, setJobs] = useState<CrawlJob[]>([]);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [historicalKeywords, setHistoricalKeywords] = useState<KeywordHistorySummary[]>([]);
  const [groups, setGroups] = useState<string[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<string>("all");

  const [loadingJobs, setLoadingJobs] = useState(true);
  const [loadingKeywords, setLoadingKeywords] = useState(true);
  const [error, setError] = useState("");

  const [crawling, setCrawling] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [, setTick] = useState(0);

  const [newText, setNewText] = useState("");
  const [savingKeyword, setSavingKeyword] = useState(false);

  const [recommendations, setRecommendations] = useState<KeywordRecommendation[]>([]);
  const [recommendLoading, setRecommendLoading] = useState(false);
  const [showRecommend, setShowRecommend] = useState(false);
  const [addingRec, setAddingRec] = useState<string | null>(null);
  const [creatingGroup, setCreatingGroup] = useState(false);
  const [deletingGroup, setDeletingGroup] = useState<string | null>(null);

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
      const [kws, history, groupNames] = await Promise.all([
        keywordsApi.list(),
        digestsApi.listKeywords(),
        keywordsApi.listGroups(),
      ]);
      setKeywords(kws);
      setHistoricalKeywords(history);
      setGroups(groupNames);
    } catch (err: any) {
      setError(err.message || "Failed to load keywords");
    } finally {
      setLoadingKeywords(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
    loadKeywords();
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
        source_type: "search",
        group_name: selectedGroup !== "all" ? selectedGroup : undefined,
      });
      setKeywords((prev) => [...prev, kw]);
      if (kw.group_name) {
        setGroups((prev) => Array.from(new Set([...prev, kw.group_name!])).sort());
      }
      setNewText("");
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
      const kw = await keywordsApi.create({
        text,
        source_type: "search",
        group_name: selectedGroup !== "all" ? selectedGroup : undefined,
      });
      setKeywords((prev) => [...prev, kw]);
      if (kw.group_name) {
        setGroups((prev) => Array.from(new Set([...prev, kw.group_name!])).sort());
      }
      setRecommendations((prev) => prev.filter((r) => r.text !== text));
    } finally {
      setAddingRec(null);
    }
  }

  async function handleDeleteKeyword(id: string) {
    await keywordsApi.delete(id);
    setKeywords((prev) => prev.filter((item) => item.id !== id));
  }

  async function handleAddHistoricalKeyword(text: string) {
    setAddingRec(text);
    try {
      const kw = await keywordsApi.create({
        text,
        source_type: "search",
        group_name: selectedGroup !== "all" ? selectedGroup : undefined,
      });
      setKeywords((prev) => [...prev, kw]);
      if (kw.group_name) {
        setGroups((prev) => Array.from(new Set([...prev, kw.group_name!])).sort());
      }
    } finally {
      setAddingRec(null);
    }
  }

  async function handleCreateGroup() {
    if (selectedGroup !== "all" || displayedKeywords.length === 0) return;
    const value = window.prompt(t("kw_group_prompt"))?.trim();
    if (!value) return;
    setCreatingGroup(true);
    setError("");
    try {
      const updatedKeywords = await Promise.all(
        displayedKeywords.map((item) => keywordsApi.update(item.id, { group_name: value }))
      );
      const updatedMap = new Map(updatedKeywords.map((item) => [item.id, item]));
      setKeywords((prev) => prev.map((item) => updatedMap.get(item.id) ?? item));
      setGroups((prev) => Array.from(new Set([...prev, value])).sort());
      setSelectedGroup(value);
    } catch (err: any) {
      setError(err.message || "创建分组失败");
    } finally {
      setCreatingGroup(false);
    }
  }

  async function handleDeleteGroup(groupName: string) {
    if (!window.confirm(t("kw_group_delete_confirm", { group: groupName }))) return;
    setDeletingGroup(groupName);
    setError("");
    try {
      const keywordsInGroup = keywords.filter((item) => item.group_name === groupName);
      const updatedKeywords = await Promise.all(
        keywordsInGroup.map((item) => keywordsApi.update(item.id, { group_name: "" }))
      );
      const updatedMap = new Map(updatedKeywords.map((item) => [item.id, item]));
      setKeywords((prev) => prev.map((item) => updatedMap.get(item.id) ?? item));
      setGroups((prev) => prev.filter((item) => item !== groupName));
      if (selectedGroup === groupName) {
        setSelectedGroup("all");
      }
    } catch (err: any) {
      setError(err.message || "删除分组失败");
    } finally {
      setDeletingGroup(null);
    }
  }

  const jobsLoadingState = loadingJobs;
  const keywordsLoadingState = loadingKeywords;
  const currentKeywordSet = new Set(keywords.map((item) => item.text.toLowerCase()));
  const recentHistoricalHints = historicalKeywords.filter((item) => {
    if (!item.latest_crawled_at) return false;
    const daysAgo = (Date.now() - new Date(item.latest_crawled_at).getTime()) / (1000 * 60 * 60 * 24);
    return daysAgo <= 30 && !currentKeywordSet.has(item.keyword.toLowerCase());
  }).slice(0, 12);
  const availableGroups = useMemo(() => Array.from(new Set(groups)).sort(), [groups]);
  const displayedKeywords = useMemo(() => {
    if (selectedGroup === "all") return keywords;
    return keywords.filter((item) => item.group_name === selectedGroup);
  }, [keywords, selectedGroup]);

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
          <button
            onClick={handleRecommend}
            disabled={recommendLoading}
            className="rounded border border-primary/40 px-3 py-1.5 text-xs text-primary transition-colors hover:bg-primary/5 disabled:opacity-50"
          >
            {recommendLoading ? t("kw_recommending") : t("kw_recommend")}
          </button>
          <button
            onClick={handleCrawlNow}
            disabled={crawling || activeKeywords === 0}
            className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {crawling ? t("dash_submitting") : t("dash_crawl_now")}
          </button>
        </div>
      </div>

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

      <section className="mb-6 grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-background p-4">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">{t("kw_list_title")}</h2>
            <span className="text-xs text-muted-foreground">{keywords.length}</span>
          </div>

          <div className="mb-4 flex flex-wrap items-center gap-2">
            <button
              onClick={() => setSelectedGroup("all")}
              className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                selectedGroup === "all" ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-muted"
              }`}
            >
              {t("kw_group_all")}
            </button>
            {availableGroups.map((group) => (
              <div key={group} className="relative inline-flex">
                <button
                  onClick={() => setSelectedGroup(group)}
                  className={`rounded-full border px-3 py-1 pr-7 text-xs transition-colors ${
                    selectedGroup === group ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-muted"
                  }`}
                >
                  {group}
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteGroup(group);
                  }}
                  disabled={deletingGroup === group}
                  aria-label={`${t("delete")} ${group}`}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
                >
                  ×
                </button>
              </div>
            ))}
            {selectedGroup === "all" && (
              <button
                onClick={handleCreateGroup}
                disabled={creatingGroup || displayedKeywords.length === 0}
                className="rounded-full border border-primary/40 px-3 py-1 text-xs text-primary transition-colors hover:bg-primary/5"
              >
                {creatingGroup ? t("saving") : t("kw_group_generate")}
              </button>
            )}
          </div>

          {recentHistoricalHints.length > 0 && (
            <div className="mb-4">
              <p className="mb-2 text-xs text-muted-foreground">{t("kw_history_hint_title")}</p>
              <div className="flex flex-wrap gap-2">
                {recentHistoricalHints.map((item) => (
                  <button
                    key={item.keyword}
                    onClick={() => handleAddHistoricalKeyword(item.keyword)}
                    disabled={addingRec === item.keyword}
                    className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-primary disabled:opacity-50"
                  >
                    {addingRec === item.keyword ? t("kw_adding") : item.keyword}
                  </button>
                ))}
              </div>
            </div>
          )}

          {keywordsLoadingState ? (
            <div className="py-12 text-center text-muted-foreground">{t("loading")}</div>
          ) : keywords.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">{t("kw_empty")}</div>
          ) : displayedKeywords.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">{t("kw_group_empty")}</div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {displayedKeywords.map((kw) => (
                <div
                  key={kw.id}
                  className="relative min-w-[160px] max-w-full flex-none rounded-lg border border-border px-3 py-4 pr-8"
                >
                  <span className="block min-w-0 truncate text-sm font-medium">{kw.text}</span>
                  <button
                    onClick={(e) => {
                      handleDeleteKeyword(kw.id);
                    }}
                    aria-label={`${t("delete")} ${kw.text}`}
                    className="absolute right-2 top-2 text-xs text-muted-foreground transition-colors hover:text-foreground"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border bg-background p-4">
          <div className="mb-4">
            <h2 className="text-lg font-semibold">{t("kw_title")}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {selectedGroup === "all" ? t("kw_subtitle_simple") : t("kw_subtitle_group", { group: selectedGroup })}
            </p>
          </div>

          <form onSubmit={handleAddKeyword} className="rounded-lg border border-border bg-muted/20 p-4">
            <div className="flex flex-col gap-3">
              <input
                value={newText}
                onChange={(e) => setNewText(e.target.value)}
                className="w-full rounded-md border border-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder={t("kw_placeholder")}
                maxLength={200}
              />
              <button
                type="submit"
                disabled={savingKeyword || !newText.trim()}
                className="self-end rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {savingKeyword ? t("kw_adding") : t("kw_add")}
              </button>
            </div>
          </form>
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

                      <div className="shrink-0 text-right">
                        <p className="text-sm text-foreground">{new Date(job.created_at).toLocaleString()}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">{durationStr}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
      </section>
    </div>
  );
}
