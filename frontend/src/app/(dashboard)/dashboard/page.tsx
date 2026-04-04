"use client";
import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { crawlJobsApi, type CrawlJob } from "@/lib/api";

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

const STATUS_LABEL = (job: CrawlJob): string => {
  if (job.status === "pending") return "Queued";
  if (job.status === "running") return "Crawling";
  if (job.status === "failed") return "Failed";
  if (isGeneratingDigest(job)) return "Generating digest";
  if (job.status === "completed" && !job.has_digest) return "No new content";
  return "Completed";
};

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

export default function DashboardPage() {
  const [jobs, setJobs] = useState<CrawlJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [crawling, setCrawling] = useState(false);
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

  useEffect(() => { loadJobs(); }, [loadJobs]);

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

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Crawl Jobs</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Progress and status of each crawl</p>
        </div>
        <button
          onClick={handleCrawlNow}
          disabled={crawling}
          className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90 disabled:opacity-50"
        >
          {crawling ? "Submitting..." : "Crawl now"}
        </button>
      </div>

      {digestError && (
        <div className="mb-4 flex items-start gap-3 px-4 py-3 bg-destructive/10 border border-destructive/30 rounded-lg">
          <span className="text-destructive text-lg leading-none mt-0.5">⚠</span>
          <div>
            <p className="text-sm font-medium text-destructive">API Key is inactive — digest generation paused</p>
            <p className="text-xs text-destructive/80 mt-0.5">
              Update your API Key to resume.
              <a href="/settings" className="underline ml-1">Go to Settings</a>
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-4 px-3 py-2 text-sm text-destructive bg-destructive/10 rounded">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-20 text-muted-foreground">Loading...</div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <p className="text-lg mb-2">No crawl jobs yet</p>
          <p className="text-sm">Add keywords then click "Crawl now" to start</p>
        </div>
      ) : (
        <div className="space-y-2">
          {jobs.map((job) => {
            const active = isActive(job);
            const durationStr = active
              ? `Elapsed ${formatDuration(job.started_at || job.created_at, null, true)}`
              : formatDuration(job.started_at, job.completed_at || job.created_at);

            return (
              <div
                key={job.id}
                className="flex items-center gap-4 px-4 py-3 bg-background border border-border rounded-lg"
              >
                {/* Status badge */}
                <span className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLOR(job)}`}>
                  {active && (
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-current mr-1 animate-pulse align-middle" />
                  )}
                  {STATUS_LABEL(job)}
                </span>

                {/* View digest button */}
                {job.has_digest && job.digest_id && (
                  <Link
                    href={`/digests/${job.digest_id}`}
                    className="shrink-0 px-2.5 py-1 text-xs font-medium border border-border rounded hover:bg-muted transition-colors"
                  >
                    View digest
                  </Link>
                )}

                {/* Error */}
                {job.status === "failed" && job.error_message && (
                  <span className="shrink-0 text-xs text-destructive max-w-[160px] truncate" title={job.error_message}>
                    {job.error_message}
                  </span>
                )}

                {/* spacer */}
                <div className="flex-1" />

                {/* Time + duration — always at the end */}
                <div className="shrink-0 text-right">
                  <p className="text-sm text-foreground">
                    {new Date(job.created_at).toLocaleString("en-US")}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">{durationStr}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
