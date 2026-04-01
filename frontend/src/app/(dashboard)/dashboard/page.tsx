"use client";
import { useState, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { digestsApi, crawlJobsApi, type DigestListItem, type CrawlJob } from "@/lib/api";

export default function DashboardPage() {
  const [latestDigest, setLatestDigest] = useState<DigestListItem | null>(null);
  const [digestContent, setDigestContent] = useState<string | null>(null);
  const [runningJob, setRunningJob] = useState<CrawlJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [crawling, setCrawling] = useState(false);
  const [error, setError] = useState("");

  const loadLatestDigest = useCallback(async () => {
    try {
      const list = await digestsApi.list();
      if (list.length > 0) {
        setLatestDigest(list[0]);
        const full = await digestsApi.get(list[0].id);
        setDigestContent(full.summary_md);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLatestDigest();
  }, [loadLatestDigest]);

  // Poll running job status
  useEffect(() => {
    if (!runningJob) return;
    const interval = setInterval(async () => {
      try {
        const job = await crawlJobsApi.get(runningJob.id);
        if (job.status === "completed" || job.status === "failed") {
          setRunningJob(null);
          setCrawling(false);
          if (job.status === "completed") {
            await loadLatestDigest();
          }
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [runningJob, loadLatestDigest]);

  async function handleCrawlNow() {
    setCrawling(true);
    setError("");
    try {
      const job = await crawlJobsApi.trigger();
      setRunningJob(job);
    } catch (err: any) {
      setError(err.message);
      setCrawling(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">今日摘要</h1>
          <p className="text-sm text-muted-foreground mt-0.5">基于你配置的信息源和关键词生成</p>
        </div>
        <button
          onClick={handleCrawlNow}
          disabled={crawling}
          className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90 disabled:opacity-50"
        >
          {crawling ? "抓取中..." : "立即抓取"}
        </button>
      </div>

      {error && (
        <div className="mb-4 px-3 py-2 text-sm text-destructive bg-destructive/10 rounded">
          {error}
        </div>
      )}

      {/* Running job indicator */}
      {runningJob && (
        <div className="mb-4 flex items-center gap-3 px-4 py-3 bg-primary/5 border border-primary/20 rounded-lg">
          <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          <span className="text-sm text-primary font-medium">正在抓取信息源，完成后自动更新摘要...</span>
        </div>
      )}

      {/* Digest content */}
      {loading ? (
        <div className="text-center py-20 text-muted-foreground">加载中...</div>
      ) : digestContent ? (
        <div className="bg-background border border-border rounded-lg p-6">
          <div className="text-xs text-muted-foreground mb-4">
            {latestDigest && new Date(latestDigest.created_at).toLocaleString("zh-CN")}
            {latestDigest && ` · ${latestDigest.sources_count} 个来源`}
          </div>
          <div className="prose max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {digestContent}
            </ReactMarkdown>
          </div>
        </div>
      ) : (
        <div className="text-center py-20 text-muted-foreground">
          <p className="text-lg mb-2">暂无摘要</p>
          <p className="text-sm">先配置信息源和关键词，然后点击「立即抓取」</p>
        </div>
      )}
    </div>
  );
}
