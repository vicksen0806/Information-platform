"use client";
import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { digestsApi, keywordsApi, type DigestListItem } from "@/lib/api";

export default function DigestsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [digests, setDigests] = useState<DigestListItem[]>([]);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);

  const keywordFilter = searchParams.get("keyword") || "";

  // Load keyword list for filter tabs
  useEffect(() => {
    keywordsApi.list().then((kws) => setKeywords(kws.map((k) => k.text)));
  }, []);

  const fetchDigests = useCallback(async (q: string, kw: string) => {
    if (q) setSearching(true); else setLoading(true);
    try {
      const list = await digestsApi.list(q || undefined, kw || undefined);
      setDigests(list);
    } finally {
      setLoading(false);
      setSearching(false);
    }
  }, []);

  // Initial load + keyword filter change
  useEffect(() => {
    fetchDigests(query, keywordFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keywordFilter]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => fetchDigests(query, keywordFilter), 300);
    return () => clearTimeout(timer);
  }, [query, keywordFilter, fetchDigests]);

  function setKeywordFilter(kw: string) {
    const params = new URLSearchParams();
    if (kw) params.set("keyword", kw);
    router.push(`/digests${params.toString() ? `?${params}` : ""}`);
  }

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.preventDefault();
    if (!confirm("Delete this digest?")) return;
    await digestsApi.delete(id);
    setDigests((prev) => prev.filter((d) => d.id !== id));
  }

  function handleRead(id: string) {
    setDigests((prev) => prev.map((d) => (d.id === id ? { ...d, is_read: true } : d)));
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Digest History</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          {keywordFilter ? `Showing digests for "${keywordFilter}"` : "All past digests — click to view"}
        </p>
      </div>

      {/* Keyword filter tabs */}
      {keywords.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          <button
            onClick={() => setKeywordFilter("")}
            className={`px-3 py-1 text-xs rounded-full border transition-colors ${!keywordFilter ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-muted"}`}
          >
            All
          </button>
          {keywords.map((kw) => (
            <button
              key={kw}
              onClick={() => setKeywordFilter(keywordFilter === kw ? "" : kw)}
              className={`px-3 py-1 text-xs rounded-full border transition-colors ${keywordFilter === kw ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-muted"}`}
            >
              {kw}
            </button>
          ))}
        </div>
      )}

      {/* Search */}
      <div className="relative mb-4">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search digests..."
          className="w-full pl-9 pr-4 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        {searching && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">Searching...</span>
        )}
        {query && !searching && (
          <button
            onClick={() => setQuery("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            ✕
          </button>
        )}
      </div>

      {loading ? (
        <div className="text-center py-20 text-muted-foreground">Loading...</div>
      ) : digests.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          {query ? `No results for "${query}"` : keywordFilter ? `No digests for "${keywordFilter}" yet` : "No digests yet"}
        </div>
      ) : (
        <div className="space-y-2">
          {digests.map((digest) => (
            <Link
              key={digest.id}
              href={`/digests/${digest.id}`}
              onClick={() => handleRead(digest.id)}
              className="group flex items-center justify-between bg-background border border-border rounded-lg px-4 py-3 hover:border-primary/50 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                {!digest.is_read && <div className="w-2 h-2 rounded-full bg-primary shrink-0" />}
                <div className="min-w-0">
                  <p className={`text-sm font-medium truncate ${!digest.is_read ? "" : "text-muted-foreground"}`}>
                    {digest.keywords_used && digest.keywords_used.length > 0
                      ? digest.keywords_used.join(", ")
                      : digest.title || "Untitled digest"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {new Date(digest.created_at).toLocaleString("en-US")} · {digest.sources_count} sources
                  </p>
                </div>
              </div>
              <button
                onClick={(e) => handleDelete(digest.id, e)}
                className="shrink-0 ml-4 px-2 py-1 text-xs text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100"
              >
                Delete
              </button>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
