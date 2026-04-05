"use client";
import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { digestsApi, digestExportApi, type Digest } from "@/lib/api";
import { useT } from "@/lib/i18n";

export default function DigestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const t = useT();
  const [digest, setDigest] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [starring, setStarring] = useState(false);
  const [copyMsg, setCopyMsg] = useState("");
  const [copyMdMsg, setCopyMdMsg] = useState("");
  const [notionMsg, setNotionMsg] = useState("");

  useEffect(() => {
    digestsApi.get(id).then(setDigest).finally(() => setLoading(false));
  }, [id]);

  async function handleRegenerate() {
    if (!digest) return;
    setRegenerating(true);
    try { await digestsApi.regenerate(digest.id); alert(t("digest_regen_alert")); }
    finally { setRegenerating(false); }
  }

  async function handleDelete() {
    if (!confirm(t("digest_delete_confirm"))) return;
    await digestsApi.delete(id);
    router.push("/digests");
  }

  async function handleShare() {
    if (!digest) return;
    setSharing(true);
    try {
      const updated = digest.share_token ? await digestsApi.unshare(digest.id) : await digestsApi.share(digest.id);
      setDigest(updated);
    } finally { setSharing(false); }
  }

  async function handleStar() {
    if (!digest) return;
    setStarring(true);
    try {
      const updated = digest.is_starred
        ? await digestsApi.unstar(digest.id)
        : await digestsApi.star(digest.id);
      setDigest(updated);
    } finally { setStarring(false); }
  }

  async function handleFeedback(value: "positive" | "negative") {
    if (!digest) return;
    try {
      if (digest.feedback === value) {
        const updated = await digestsApi.deleteFeedback(digest.id);
        setDigest(updated);
      } else {
        const updated = await digestsApi.setFeedback(digest.id, value);
        setDigest(updated);
      }
    } catch {}
  }

  function handleCopyLink() {
    if (!digest?.share_token) return;
    const url = `${window.location.origin}/share/${digest.share_token}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopyMsg(t("digest_copied"));
      setTimeout(() => setCopyMsg(""), 2000);
    });
  }

  function handleCopyMarkdown() {
    if (!digest?.summary_md) return;
    navigator.clipboard.writeText(digest.summary_md).then(() => {
      setCopyMdMsg(t("digest_copied_md"));
      setTimeout(() => setCopyMdMsg(""), 2000);
    });
  }

  function handleExportObsidian() {
    if (!digest?.summary_md) return;
    const title = digest.title || `digest-${digest.id.slice(0, 8)}`;
    const date = new Date(digest.created_at).toISOString().slice(0, 10);
    const tags = (digest.keywords_used || []).join(", ");
    const frontmatter = `---\ntags: [${tags}]\ncreated: ${date}\nsource: info-platform\n---\n\n`;
    const content = frontmatter + digest.summary_md;
    const uri = `obsidian://new?name=${encodeURIComponent(title)}&content=${encodeURIComponent(content)}`;
    window.open(uri);
  }

  async function handleExportNotion() {
    if (!digest) return;
    setNotionMsg(t("digest_exporting"));
    try {
      await digestExportApi.toNotion(digest.id);
      setNotionMsg(t("digest_export_ok"));
      setTimeout(() => setNotionMsg(""), 3000);
    } catch (err: any) {
      setNotionMsg(err.message || t("digest_export_err"));
      setTimeout(() => setNotionMsg(""), 4000);
    }
  }

  function handleDownloadMarkdown() {
    if (!digest?.summary_md) return;
    const filename = `digest-${new Date(digest.created_at).toISOString().slice(0, 10)}.md`;
    const blob = new Blob([digest.summary_md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  }

  if (loading) return <div className="p-6 text-center text-muted-foreground">{t("loading")}</div>;
  if (!digest) return <div className="p-6 text-center text-muted-foreground">{t("digest_not_found")}</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Top bar */}
      <div className="flex items-center justify-between mb-6">
        <Link href="/digests" className="text-sm text-muted-foreground hover:text-foreground">
          {t("digest_back")}
        </Link>
        <div className="flex gap-2 flex-wrap justify-end">
          {/* Share controls */}
          {digest.share_token ? (
            <>
              <button onClick={handleCopyLink} className="px-3 py-1.5 text-xs bg-primary/10 text-primary border border-primary/30 rounded hover:bg-primary/20">
                {copyMsg || t("digest_copy_link")}
              </button>
              <button onClick={handleShare} disabled={sharing} className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted disabled:opacity-50">
                {sharing ? "..." : t("digest_revoke")}
              </button>
            </>
          ) : (
            <button onClick={handleShare} disabled={sharing} className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted disabled:opacity-50">
              {sharing ? "..." : t("digest_share")}
            </button>
          )}

          {/* Export controls */}
          {digest.summary_md && (
            <>
              <button onClick={handleCopyMarkdown} className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted">
                {copyMdMsg || t("digest_copy_md")}
              </button>
              <button onClick={handleDownloadMarkdown} className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted">
                {t("digest_download_md")}
              </button>
              <button onClick={handleExportObsidian} className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted" title="Requires Obsidian app installed">
                {t("digest_export_obsidian")}
              </button>
              <button onClick={handleExportNotion} disabled={!!notionMsg} className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted disabled:opacity-60">
                {notionMsg || t("digest_export_notion")}
              </button>
            </>
          )}

          <button onClick={handleStar} disabled={starring}
            className={`px-3 py-1.5 text-xs border rounded disabled:opacity-50 transition-colors ${digest.is_starred ? "border-yellow-400 text-yellow-600 bg-yellow-50 hover:bg-yellow-100" : "border-border hover:bg-muted"}`}>
            {digest.is_starred ? `★ ${t("digest_unstar")}` : `☆ ${t("digest_star")}`}
          </button>
          <button onClick={handleRegenerate} disabled={regenerating} className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted disabled:opacity-50">
            {regenerating ? t("digest_regenerating") : t("digest_regenerate")}
          </button>
          <button onClick={handleDelete} className="px-3 py-1.5 text-xs text-destructive border border-destructive/30 rounded hover:bg-destructive/10">
            {t("digest_delete")}
          </button>
        </div>
      </div>

      {/* Shared indicator */}
      {digest.share_token && (
        <div className="mb-4 px-3 py-2 text-xs text-primary bg-primary/5 border border-primary/20 rounded flex items-center gap-2">
          <span>{t("digest_public_link")}</span>
          <span className="font-mono text-muted-foreground truncate max-w-xs">
            {typeof window !== "undefined" ? `${window.location.origin}/share/${digest.share_token}` : ""}
          </span>
        </div>
      )}

      {/* Meta + Feedback */}
      <div className="mb-4 flex items-center justify-between flex-wrap gap-2">
        <div className="text-xs text-muted-foreground flex flex-wrap gap-3">
          <span>{new Date(digest.created_at).toLocaleString()}</span>
          <span>{t("digests_sources", { n: digest.sources_count })}</span>
          {digest.llm_model && <span>{t("digest_model", { m: digest.llm_model })}</span>}
          {digest.tokens_used > 0 && <span>{t("digest_tokens", { n: digest.tokens_used.toLocaleString() })}</span>}
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => handleFeedback("positive")}
            title={t("digest_feedback_positive")}
            className={`px-2 py-1 text-base rounded transition-colors hover:bg-muted ${digest.feedback === "positive" ? "text-green-600 bg-green-50" : "text-muted-foreground"}`}>
            👍
          </button>
          <button onClick={() => handleFeedback("negative")}
            title={t("digest_feedback_negative")}
            className={`px-2 py-1 text-base rounded transition-colors hover:bg-muted ${digest.feedback === "negative" ? "text-red-500 bg-red-50" : "text-muted-foreground"}`}>
            👎
          </button>
        </div>
      </div>

      {/* Keyword tags */}
      {digest.keywords_used && digest.keywords_used.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {digest.keywords_used.map((kw) => (
            <Link key={kw} href={`/digests?keyword=${encodeURIComponent(kw)}`}
              className="px-2 py-0.5 text-xs bg-primary/10 text-primary rounded-full hover:bg-primary/20 transition-colors">
              {kw}
            </Link>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="bg-background border border-border rounded-lg p-6">
        {digest.summary_md ? (
          <div className="prose prose-slate dark:prose-invert max-w-none prose-h1:text-2xl prose-h2:text-lg prose-h2:border-b prose-h2:border-border prose-h2:pb-1 prose-h3:text-base prose-h3:font-semibold prose-li:my-0.5 prose-a:text-primary prose-a:no-underline hover:prose-a:underline">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
                ),
              }}
            >
              {digest.summary_md}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="text-center py-12 text-muted-foreground">{t("digest_no_content")}</div>
        )}
      </div>
    </div>
  );
}
