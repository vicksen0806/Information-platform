"use client";
import { useState, useEffect, useCallback, useRef, Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { digestsApi, keywordsApi, type DigestListItem } from "@/lib/api";
import { useT } from "@/lib/i18n";

const PAGE_SIZE = 20;

// ── Trend helpers ───────────────────────────────────────────────────────────

function getWeekLabel(date: Date): string {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
  const year = d.getUTCFullYear();
  const startOfYear = new Date(Date.UTC(year, 0, 1));
  const weekNo = Math.ceil((((d.getTime() - startOfYear.getTime()) / 86400000) + 1) / 7);
  return `${year}-W${String(weekNo).padStart(2, "0")}`;
}

interface TrendRow { keyword: string; counts: Record<string, number>; total: number; }

function buildTrend(digests: DigestListItem[]): { rows: TrendRow[]; weeks: string[] } {
  const kwMap: Record<string, Record<string, number>> = {};
  for (const d of digests) {
    const week = getWeekLabel(new Date(d.created_at));
    const kws = d.keywords_used?.length ? d.keywords_used : ["(other)"];
    for (const kw of kws) {
      if (!kwMap[kw]) kwMap[kw] = {};
      kwMap[kw][week] = (kwMap[kw][week] || 0) + 1;
    }
  }
  const allWeeks = Array.from(new Set(Object.values(kwMap).flatMap((w) => Object.keys(w)))).sort();
  const rows = Object.entries(kwMap)
    .map(([keyword, counts]) => ({ keyword, counts, total: Object.values(counts).reduce((a, b) => a + b, 0) }))
    .sort((a, b) => b.total - a.total);
  return { rows, weeks: allWeeks };
}

// ── Main ────────────────────────────────────────────────────────────────────

function DigestsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const t = useT();

  const [digests, setDigests] = useState<DigestListItem[]>([]);
  const [allDigests, setAllDigests] = useState<DigestListItem[] | null>(null);
  const [loadingAll, setLoadingAll] = useState(false);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [view, setView] = useState<"list" | "trend">("list");
  const sentinelRef = useRef<HTMLDivElement>(null);
  const offsetRef = useRef(0);

  const keywordFilter = searchParams.get("keyword") || "";

  useEffect(() => {
    keywordsApi.list().then((kws) => setKeywords(kws.map((k) => k.text)));
  }, []);

  // Initial / filter change: reset and reload
  const reload = useCallback(async (q: string, kw: string) => {
    setLoading(true);
    setHasMore(true);
    offsetRef.current = 0;
    try {
      const list = await digestsApi.list(q || undefined, kw || undefined, PAGE_SIZE, 0);
      setDigests(list);
      setHasMore(list.length === PAGE_SIZE);
      offsetRef.current = list.length;
    } finally {
      setLoading(false);
      setSearching(false);
    }
  }, []);

  useEffect(() => { reload(query, keywordFilter); }, [keywordFilter]); // eslint-disable-line

  // Debounced search
  useEffect(() => {
    setSearching(!!query);
    const timer = setTimeout(() => reload(query, keywordFilter), 300);
    return () => clearTimeout(timer);
  }, [query]); // eslint-disable-line

  // Infinite scroll
  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const list = await digestsApi.list(query || undefined, keywordFilter || undefined, PAGE_SIZE, offsetRef.current);
      setDigests((prev) => [...prev, ...list]);
      setHasMore(list.length === PAGE_SIZE);
      offsetRef.current += list.length;
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore, hasMore, query, keywordFilter]);

  useEffect(() => {
    if (!sentinelRef.current) return;
    const observer = new IntersectionObserver(([entry]) => { if (entry.isIntersecting) loadMore(); }, { threshold: 0.1 });
    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [loadMore]);

  function setKeywordFilter(kw: string) {
    const params = new URLSearchParams();
    if (kw) params.set("keyword", kw);
    router.push(`/digests${params.toString() ? `?${params}` : ""}`);
  }

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.preventDefault();
    if (!confirm(t("delete") + "?")) return;
    await digestsApi.delete(id);
    setDigests((prev) => prev.filter((d) => d.id !== id));
  }

  async function handleFeedback(id: string, value: "positive" | "negative", current: string | null, e: React.MouseEvent) {
    e.preventDefault();
    try {
      if (current === value) {
        await digestsApi.deleteFeedback(id);
        setDigests((prev) => prev.map((d) => d.id === id ? { ...d, feedback: null } : d));
      } else {
        await digestsApi.setFeedback(id, value);
        setDigests((prev) => prev.map((d) => d.id === id ? { ...d, feedback: value } : d));
      }
    } catch {}
  }

  async function handleStar(id: string, isStarred: boolean, e: React.MouseEvent) {
    e.preventDefault();
    try {
      if (isStarred) {
        await digestsApi.unstar(id);
        setDigests((prev) => prev.map((d) => d.id === id ? { ...d, is_starred: false } : d));
      } else {
        await digestsApi.star(id);
        setDigests((prev) => prev.map((d) => d.id === id ? { ...d, is_starred: true } : d));
      }
    } catch {}
  }

  async function handleMarkAllRead() {
    if (!confirm(t("digests_mark_all_read_confirm"))) return;
    await digestsApi.markAllRead();
    setDigests((prev) => prev.map((d) => ({ ...d, is_read: true })));
  }

  function handleRead(id: string) {
    setDigests((prev) => prev.map((d) => (d.id === id ? { ...d, is_read: true } : d)));
  }

  // When switching to trend view, load all digests (no pagination limit)
  useEffect(() => {
    if (view !== "trend" || allDigests !== null || loadingAll) return;
    setLoadingAll(true);
    digestsApi.list(undefined, keywordFilter || undefined, 500, 0)
      .then(setAllDigests)
      .finally(() => setLoadingAll(false));
  }, [view, allDigests, loadingAll, keywordFilter]);

  // Reset allDigests when keyword filter changes so trend reloads
  useEffect(() => { setAllDigests(null); }, [keywordFilter]);

  const trend = buildTrend(allDigests ?? digests);
  const subtitle = keywordFilter ? t("digests_subtitle_kw", { kw: keywordFilter }) : t("digests_subtitle_all");

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{t("digests_title")}</h1>
          <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {view === "list" && digests.some((d) => !d.is_read) && (
            <button onClick={handleMarkAllRead} className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted transition-colors">
              {t("digests_mark_all_read")}
            </button>
          )}
          <div className="flex rounded-md border border-border overflow-hidden text-xs">
            <button onClick={() => setView("list")} className={`px-3 py-1.5 transition-colors ${view === "list" ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}>
              {t("digests_view_list")}
            </button>
            <button onClick={() => setView("trend")} className={`px-3 py-1.5 border-l border-border transition-colors ${view === "trend" ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}>
              {t("digests_view_trend")}
            </button>
          </div>
        </div>
      </div>

      {view === "trend" ? (
        <TrendView trend={trend} loading={loading || loadingAll} totalDigests={(allDigests ?? digests).length} />
      ) : (
        <>
          {/* Keyword filter tabs */}
          {keywords.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-4">
              <button onClick={() => setKeywordFilter("")} className={`px-3 py-1 text-xs rounded-full border transition-colors ${!keywordFilter ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-muted"}`}>
                {t("all")}
              </button>
              {keywords.map((kw) => (
                <button key={kw} onClick={() => setKeywordFilter(keywordFilter === kw ? "" : kw)}
                  className={`px-3 py-1 text-xs rounded-full border transition-colors ${keywordFilter === kw ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-muted"}`}>
                  {kw}
                </button>
              ))}
            </div>
          )}

          {/* Search */}
          <div className="relative mb-4">
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("digests_search_placeholder")}
              className="w-full pl-9 pr-4 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            {searching && <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">{t("digests_searching")}</span>}
            {query && !searching && <button onClick={() => setQuery("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">✕</button>}
          </div>

          {loading ? (
            <div className="text-center py-20 text-muted-foreground">{t("loading")}</div>
          ) : digests.length === 0 ? (
            <div className="text-center py-20 text-muted-foreground">
              {query ? t("digests_empty_search", { q: query }) : keywordFilter ? t("digests_empty_kw", { kw: keywordFilter }) : t("digests_empty")}
            </div>
          ) : (
            <>
              <div className="space-y-2">
                {digests.map((digest) => (
                  <Link key={digest.id} href={`/digests/${digest.id}`} onClick={() => handleRead(digest.id)}
                    className="group flex items-center justify-between bg-background border border-border rounded-lg px-4 py-3 hover:border-primary/50 transition-colors">
                    <div className="flex items-center gap-3 min-w-0">
                      {!digest.is_read && <div className="w-2 h-2 rounded-full bg-primary shrink-0" />}
                      <div className="min-w-0">
                        <p className={`text-sm font-medium truncate ${!digest.is_read ? "" : "text-muted-foreground"}`}>
                          {digest.keywords_used?.length ? digest.keywords_used.join(", ") : digest.title || "Untitled digest"}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {new Date(digest.created_at).toLocaleString()} · {t("digests_sources", { n: digest.sources_count })}
                          {digest.importance_score != null && (
                            <span className={`ml-2 px-1.5 py-0.5 rounded text-xs font-medium ${
                              digest.importance_score >= 0.7 ? "bg-red-100 text-red-600" :
                              digest.importance_score >= 0.4 ? "bg-yellow-100 text-yellow-700" :
                              "bg-muted text-muted-foreground"
                            }`}>
                              {digest.importance_score >= 0.7 ? "🔥" : digest.importance_score >= 0.4 ? "⚡" : "○"} {Math.round(digest.importance_score * 100)}
                            </span>
                          )}
                        </p>
                      </div>
                    </div>
                    <div className="shrink-0 ml-4 flex items-center gap-1">
                      {/* Star — always visible when starred */}
                      <button
                        onClick={(e) => handleStar(digest.id, digest.is_starred, e)}
                        title={digest.is_starred ? t("digest_unstar") : t("digest_star")}
                        className={`px-1.5 py-1 text-sm rounded hover:bg-muted transition-colors ${digest.is_starred ? "text-yellow-500" : "text-muted-foreground opacity-0 group-hover:opacity-100"}`}>
                        {digest.is_starred ? "★" : "☆"}
                      </button>
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={(e) => handleFeedback(digest.id, "positive", digest.feedback ?? null, e)}
                          title={t("digest_feedback_positive")}
                          className={`px-1.5 py-1 text-sm rounded hover:bg-muted transition-colors ${digest.feedback === "positive" ? "text-green-600" : "text-muted-foreground"}`}>
                          👍
                        </button>
                        <button onClick={(e) => handleFeedback(digest.id, "negative", digest.feedback ?? null, e)}
                          title={t("digest_feedback_negative")}
                          className={`px-1.5 py-1 text-sm rounded hover:bg-muted transition-colors ${digest.feedback === "negative" ? "text-red-500" : "text-muted-foreground"}`}>
                          👎
                        </button>
                        <button onClick={(e) => handleDelete(digest.id, e)}
                          className="px-2 py-1 text-xs text-muted-foreground hover:text-destructive">
                          {t("delete")}
                        </button>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>

              {/* Infinite scroll sentinel */}
              <div ref={sentinelRef} className="py-4 text-center text-xs text-muted-foreground">
                {loadingMore ? t("loading") : !hasMore ? t("digests_no_more") : ""}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

// ── Trend View ──────────────────────────────────────────────────────────────

function TrendView({ trend, loading, totalDigests }: { trend: { rows: TrendRow[]; weeks: string[] }; loading: boolean; totalDigests: number }) {
  const t = useT();
  if (loading) return <div className="text-center py-20 text-muted-foreground">{t("loading")}</div>;
  if (totalDigests === 0) return <div className="text-center py-20 text-muted-foreground">{t("trend_empty")}</div>;

  const { rows, weeks } = trend;
  const maxCount = Math.max(...rows.flatMap((r) => Object.values(r.counts)), 1);
  const displayWeeks = weeks.slice(-8);

  return (
    <div className="space-y-6">
      <div className="text-xs text-muted-foreground">{t("trend_subtitle", { n: displayWeeks.length })}</div>

      {displayWeeks.length > 1 && (
        <div className="bg-background border border-border rounded-lg overflow-hidden">
          <div className="grid border-b border-border bg-muted/50 text-xs text-muted-foreground" style={{ gridTemplateColumns: `180px repeat(${displayWeeks.length}, 1fr) 60px` }}>
            <div className="px-4 py-2 font-medium">{t("trend_keyword")}</div>
            {displayWeeks.map((w) => <div key={w} className="px-1 py-2 text-center truncate">{w.slice(5)}</div>)}
            <div className="px-2 py-2 text-center">{t("trend_total")}</div>
          </div>
          {rows.map((row) => (
            <div key={row.keyword} className="grid border-b border-border last:border-0 hover:bg-muted/30 transition-colors" style={{ gridTemplateColumns: `180px repeat(${displayWeeks.length}, 1fr) 60px` }}>
              <div className="px-4 py-3 text-sm font-medium truncate">{row.keyword}</div>
              {displayWeeks.map((w) => {
                const count = row.counts[w] || 0;
                const pct = (count / maxCount) * 100;
                return (
                  <div key={w} className="px-1 py-3 flex items-center justify-center">
                    {count > 0 ? (
                      <div className="relative w-full flex items-center justify-center">
                        <div className="absolute inset-x-1 bottom-0 bg-primary/20 rounded-sm" style={{ height: `${Math.max(pct, 20)}%`, minHeight: "4px" }} />
                        <span className="relative text-xs font-medium text-primary z-10">{count}</span>
                      </div>
                    ) : <span className="text-xs text-muted-foreground/40">—</span>}
                  </div>
                );
              })}
              <div className="px-2 py-3 text-center text-sm font-semibold text-muted-foreground">{row.total}</div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {rows.slice(0, 6).map((row) => {
          const pct = totalDigests > 0 ? Math.round((row.total / totalDigests) * 100) : 0;
          return (
            <div key={row.keyword} className="bg-background border border-border rounded-lg p-3">
              <p className="text-xs text-muted-foreground truncate">{row.keyword}</p>
              <p className="text-2xl font-bold mt-1">{row.total}</p>
              <div className="mt-2 h-1 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full" style={{ width: `${pct}%` }} />
              </div>
              <p className="text-xs text-muted-foreground mt-1">{t("trend_pct", { pct })}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function DigestsPage() {
  return (
    <Suspense fallback={<div className="p-6 text-center text-muted-foreground">Loading...</div>}>
      <DigestsContent />
    </Suspense>
  );
}
