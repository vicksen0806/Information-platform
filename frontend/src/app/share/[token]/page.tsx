"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { publicApi, type Digest } from "@/lib/api";
import { useT } from "@/lib/i18n";

export default function SharedDigestPage() {
  const { token } = useParams<{ token: string }>();
  const t = useT();
  const [digest, setDigest] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    publicApi.getSharedDigest(token)
      .then(setDigest)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        {t("loading")}
      </div>
    );
  }

  if (notFound || !digest) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-center px-4">
        <p className="text-2xl font-bold">{t("share_not_found_title")}</p>
        <p className="text-muted-foreground text-sm">{t("share_not_found_sub")}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-3xl mx-auto px-4 py-10">
        <div className="mb-6 border-b border-border pb-4">
          <p className="text-xs text-muted-foreground mb-1">{t("share_platform")}</p>
          <h1 className="text-xl font-bold">
            {digest.keywords_used && digest.keywords_used.length > 0
              ? digest.keywords_used.join(", ")
              : digest.title || "Digest"}
          </h1>
          <div className="mt-2 text-xs text-muted-foreground flex flex-wrap gap-3">
            <span>{new Date(digest.created_at).toLocaleString()}</span>
            <span>{t("share_sources", { n: digest.sources_count })}</span>
            {digest.llm_model && <span>{t("share_model", { m: digest.llm_model })}</span>}
          </div>
        </div>

        {digest.keywords_used && digest.keywords_used.length > 0 && (
          <div className="mb-4 flex flex-wrap gap-1.5">
            {digest.keywords_used.map((kw) => (
              <span key={kw} className="px-2 py-0.5 text-xs bg-primary/10 text-primary rounded-full">{kw}</span>
            ))}
          </div>
        )}

        <div className="bg-background border border-border rounded-lg p-6">
          {digest.summary_md ? (
            <div className="prose prose-slate dark:prose-invert max-w-none prose-h1:text-2xl prose-h2:text-lg prose-h2:border-b prose-h2:border-border prose-h2:pb-1 prose-h3:text-base prose-h3:font-semibold prose-li:my-0.5">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{digest.summary_md}</ReactMarkdown>
            </div>
          ) : (
            <div className="text-center py-12 text-muted-foreground">{t("share_no_content")}</div>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">{t("share_footer")}</p>
      </div>
    </div>
  );
}
