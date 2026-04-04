"use client";
import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { crawlJobsApi, statsApi, type CrawlJob, type CrawlResult, type Stats } from "@/lib/api";
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

const STATUS_COLOR = (job: CrawlJob): string => {
  if (job.status === "pending") return "bg-yellow-100 text-yellow-700";
  if (job.status === "running") return "bg-blue-100 text-blue-700";
  if (job.status === "failed") return "bg-red-100 text-red-700";
  if (isGeneratingDigest(job)) return "bg-blue-100 text-blue-700";
  if (job.status === "completed" && !job.has_digest) return "bg-muted text-muted-foreground";
  return "bg-green-100 text-green-700";
};

function formatDuration(start: string | null, end: string | null, live = false): string {
  if (!start) return "";
  const s = new Date(start).getTime();
  const e = live ? Date.now() : (end ? new Date(end).getTime() : new Date(start).getTime());
  const sec = Math.floor((e - s) / 1000);
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
}

// ── Result preview panel ──────────────────────────────────────────────────────
function ResultsPreview({ jobId }: { jobId: string }) {
  const t = useT();
  const [results, setResults] = useState<CrawlResult[] | null>(null);

  useEffect(() => {
    crawlJobsApi.results(jobId).then(setResults).catch(() => setResults([]));
  }, [jobId]);

  if (!results) return <p className="text-xs text-muted-foreground py-2 px-1">{t("dash_preview_loading")}</p>;

  return (
    <div className="mt-2 border-t border-border pt-2 space-y-1.5">
      {results.map((r) => (
        <div key={r.id} className="flex items-start gap-2 text-xs">
          <span className={`shrink-0 mt-0.5 w-1.5 h-1.5 rounded-full ${r.error_message && r.error_message !== "Content unchanged since last crawl" ? "bg-red-400" : r.error_message ? "bg-yellow-400" : "bg-green-400"}`} />
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
  const [jobs, setJobs] = useState<CrawlJob[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [crawling, setCrawling] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [, setTick] = useState(0);

  const hasActive = jobs.some(isActive);
  const digestError = jobs.find((j) => j.digest_error)?.digest_error ?? null;

  const loadJobs = useCallback(async () => {
    try {
      const list = await crawlJobsApi.list();
      setJobs(list);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
    statsApi.get().then(setStats).catch(() => {});
  }, [loadJobs]);

  useEffect(() => {
    if (!hasActive) return;
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, [hasActive, loadJobs]);

  useEffect(() => {
    if (!hasActive) return;
    const timer = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(timer);
  }, [hasActive]);

  async function handleCrawlNow() {
    setCrawling(true); setError("");
    try {
      const job = await crawlJobsApi.trigger();
      setJobs((prev) => [job, ...prev]);
    } catch (err: any) { setError(err.message); }
    finally { setCrawling(false); }
  }

  async function handleRetry(jobId: string) {
    setRetryingId(jobId);
    try {
      const job = await crawlJobsApi.retry(jobId);
      setJobs((prev) => [job, ...prev]);
    } catch (err: any) { setError(err.message); }
    finally { setRetryingId(null); }
  }

  function statusLabel(job: CrawlJob): string {
    if (job.status === "pending") return t("dash_status_queued");
    if (job.status === "running") return t("dash_status_crawling");
    if (job.status === "failed") return t("dash_status_failed");
    if (isGeneratingDigest(job)) return t("dash_status_generating");
    if (job.status === "completed" && job.has_digest) return t("dash_status_completed");
    if (job.status === "completed" && job.new_content_found) return t("dash_status_content_found");
    if (job.status === "completed") return t("dash_status_no_new");
    return t("dash_status_completed");
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{t("dash_title")}</h1>
          <p className="text-sm text-muted-foreground mt-0.5">{t("dash_subtitle")}</p>
        </div>
        <button
          onClick={handleCrawlNow}
          disabled={crawling}
          className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90 disabled:opacity-50"
        >
          {crawling ? t("dash_submitting") : t("dash_crawl_now")}
        </button>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-4 gap-3 mb-6">
          {[
            { label: t("dash_stat_crawls"), value: stats.this_month_crawls },
            { label: t("dash_stat_sources"), value: stats.this_month_sources },
            { label: t("dash_stat_tokens"), value: stats.this_month_tokens.toLocaleString() },
            { label: t("dash_stat_unread"), value: stats.unread_digests },
          ].map(({ label, value }) => (
            <div key={label} className="bg-background border border-border rounded-lg px-4 py-3 text-center">
              <p className="text-xs text-muted-foreground mb-1">{label}</p>
              <p className="text-xl font-bold tabular-nums">{value}</p>
            </div>
          ))}
        </div>
      )}

      {digestError && (
        <div className="mb-4 flex items-start gap-3 px-4 py-3 bg-destructive/10 border border-destructive/30 rounded-lg">
          <span className="text-destructive text-lg leading-none mt-0.5">⚠</span>
          <div>
            <p className="text-sm font-medium text-destructive">{t("dash_api_inactive")}</p>
            <p className="text-xs text-destructive/80 mt-0.5">
              {t("dash_api_inactive_sub")}
              <a href="/settings" className="underline ml-1">{t("dash_go_settings")}</a>
            </p>
          </div>
        </div>
      )}

      {error && <div className="mb-4 px-3 py-2 text-sm text-destructive bg-destructive/10 rounded">{error}</div>}

      {loading ? (
        <div className="text-center py-20 text-muted-foreground">{t("loading")}</div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <p className="text-lg mb-2">{t("dash_empty_title")}</p>
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
              <div
                key={job.id}
                className="px-4 py-3 bg-background border border-border rounded-lg"
              >
                <div className="flex items-center gap-3">
                  {/* Status badge */}
                  <span className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLOR(job)}`}>
                    {active && <span className="inline-block w-1.5 h-1.5 rounded-full bg-current mr-1 animate-pulse align-middle" />}
                    {statusLabel(job)}
                  </span>

                  {/* View digest */}
                  {job.has_digest && job.digest_id && (
                    <Link href={`/digests/${job.digest_id}`} className="shrink-0 px-2.5 py-1 text-xs font-medium border border-border rounded hover:bg-muted transition-colors">
                      {t("dash_view_digest")}
                    </Link>
                  )}

                  {/* Retry button for failed jobs */}
                  {job.status === "failed" && (
                    <button
                      onClick={() => handleRetry(job.id)}
                      disabled={retryingId === job.id}
                      className="shrink-0 px-2.5 py-1 text-xs font-medium border border-border rounded hover:bg-muted transition-colors disabled:opacity-50"
                    >
                      {retryingId === job.id ? t("dash_retrying") : t("dash_retry")}
                    </button>
                  )}

                  {/* Error message */}
                  {job.status === "failed" && job.error_message && (
                    <span className="shrink-0 text-xs text-destructive max-w-[120px] truncate" title={job.error_message}>
                      {job.error_message}
                    </span>
                  )}

                  <div className="flex-1" />

                  {/* Preview toggle */}
                  {canPreview && (
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : job.id)}
                      className="shrink-0 text-xs text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {isExpanded ? t("dash_hide_preview") : t("dash_preview")}
                    </button>
                  )}

                  {/* Time */}
                  <div className="shrink-0 text-right">
                    <p className="text-sm text-foreground">{new Date(job.created_at).toLocaleString()}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{durationStr}</p>
                  </div>
                </div>

                {/* Expandable results */}
                {isExpanded && <ResultsPreview jobId={job.id} />}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
