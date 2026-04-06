"use client";
import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  digestsApi,
  type KeywordHistoryEntry,
  type KeywordHistorySummary,
} from "@/lib/api";
import { useT } from "@/lib/i18n";

function normalizeMarkdownLinks(markdown: string): string {
  return markdown.replace(/(?<!\]\()(?<!\]\()https?:\/\/[^\s)]+/g, (url) => {
    return `[来源](${url})`;
  });
}

function HistoryCard({ entry }: { entry: KeywordHistoryEntry }) {
  const t = useT();
  const normalizedMarkdown = normalizeMarkdownLinks(entry.summary_md);

  return (
    <section className="rounded-2xl border border-border bg-background p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-3 border-b border-border pb-3">
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            {new Date(entry.crawled_at).toLocaleDateString()}
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {new Date(entry.crawled_at).toLocaleString()} · {t("digests_history_articles", { n: entry.article_count })}
          </p>
        </div>
        {entry.digest_id && (
          <Link
            href={`/digests/${entry.digest_id}`}
            className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/20"
          >
            {t("digests_history_open")}
          </Link>
        )}
      </div>

      <div className="prose prose-slate dark:prose-invert max-w-none break-words prose-p:my-3 prose-ul:my-3 prose-li:my-1 prose-strong:text-foreground prose-a:text-primary prose-a:no-underline hover:prose-a:underline [&_a]:break-all">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ href, children }) => (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            ),
          }}
        >
          {normalizedMarkdown}
        </ReactMarkdown>
      </div>
    </section>
  );
}

function DigestsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const t = useT();
  const selectedKeyword = searchParams.get("keyword") || "";

  const [keywords, setKeywords] = useState<KeywordHistorySummary[]>([]);
  const [historyEntries, setHistoryEntries] = useState<KeywordHistoryEntry[]>([]);
  const [loadingKeywords, setLoadingKeywords] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    setLoadingKeywords(true);
    digestsApi.listKeywords()
      .then(setKeywords)
      .finally(() => setLoadingKeywords(false));
  }, []);

  const filteredKeywords = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return keywords;
    return keywords.filter((item) => item.keyword.toLowerCase().includes(term));
  }, [keywords, query]);

  useEffect(() => {
    if (selectedKeyword || filteredKeywords.length === 0) return;
    router.replace(`/digests?keyword=${encodeURIComponent(filteredKeywords[0].keyword)}`);
  }, [selectedKeyword, filteredKeywords, router]);

  useEffect(() => {
    if (!selectedKeyword) {
      setHistoryEntries([]);
      return;
    }
    setLoadingHistory(true);
    digestsApi.keywordHistory(selectedKeyword, 60)
      .then(setHistoryEntries)
      .finally(() => setLoadingHistory(false));
  }, [selectedKeyword]);

  const selectedSummary = keywords.find((item) => item.keyword === selectedKeyword) || null;

  function pickKeyword(keyword: string) {
    router.push(`/digests?keyword=${encodeURIComponent(keyword)}`);
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{t("digests_title")}</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          {selectedKeyword ? t("digests_subtitle_kw", { kw: selectedKeyword }) : t("digests_subtitle_all")}
        </p>
      </div>

      <div className="mb-6 rounded-2xl border border-border bg-background p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">{t("digests_keyword_list_title")}</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              {loadingKeywords ? t("loading") : t("digests_keyword_total", { n: keywords.length })}
            </p>
          </div>
        </div>

        <div className="relative mb-4">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("digests_search_placeholder")}
            className="w-full rounded-md border border-input py-2 pl-9 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>

        {loadingKeywords ? (
          <div className="py-8 text-center text-sm text-muted-foreground">{t("loading")}</div>
        ) : filteredKeywords.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            {query ? t("digests_empty_search", { q: query }) : t("digests_empty")}
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {filteredKeywords.map((item) => {
              const active = item.keyword === selectedKeyword;
              return (
                <button
                  key={item.keyword}
                  onClick={() => pickKeyword(item.keyword)}
                  className={`rounded-xl border p-4 text-left transition-colors ${
                    active ? "border-primary bg-primary/5" : "border-border hover:border-primary/40 hover:bg-muted/30"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-base font-semibold">{item.keyword}</span>
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {t("digests_keyword_days", { n: item.total_days })}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {item.latest_crawled_at ? new Date(item.latest_crawled_at).toLocaleString() : "—"}
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="space-y-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">
              {selectedKeyword || t("digests_keyword_history_title")}
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              {selectedSummary ? t("digests_keyword_days", { n: selectedSummary.total_days }) : t("digests_subtitle_all")}
            </p>
          </div>
        </div>

        {!selectedKeyword ? (
          <div className="rounded-2xl border border-dashed border-border bg-background px-4 py-12 text-center text-sm text-muted-foreground">
            {t("digests_empty")}
          </div>
        ) : loadingHistory ? (
          <div className="rounded-2xl border border-border bg-background px-4 py-12 text-center text-sm text-muted-foreground">
            {t("loading")}
          </div>
        ) : historyEntries.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-background px-4 py-12 text-center text-sm text-muted-foreground">
            {t("digests_empty_kw", { kw: selectedKeyword })}
          </div>
        ) : (
          historyEntries.map((entry) => <HistoryCard key={`${entry.keyword}-${entry.crawl_date}`} entry={entry} />)
        )}
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
