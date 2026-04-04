"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { digestsApi, type Digest } from "@/lib/api";

export default function DigestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [digest, setDigest] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [copyMsg, setCopyMsg] = useState("");

  useEffect(() => {
    digestsApi.get(id).then(setDigest).finally(() => setLoading(false));
  }, [id]);

  async function handleRegenerate() {
    if (!digest) return;
    setRegenerating(true);
    try {
      await digestsApi.regenerate(digest.id);
      alert("Regeneration triggered — refresh in a moment to see the result");
    } finally {
      setRegenerating(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this digest?")) return;
    await digestsApi.delete(id);
    router.push("/digests");
  }

  async function handleShare() {
    if (!digest) return;
    setSharing(true);
    try {
      const updated = digest.share_token
        ? await digestsApi.unshare(digest.id)
        : await digestsApi.share(digest.id);
      setDigest(updated);
    } finally {
      setSharing(false);
    }
  }

  function handleCopyLink() {
    if (!digest?.share_token) return;
    const url = `${window.location.origin}/share/${digest.share_token}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopyMsg("Copied!");
      setTimeout(() => setCopyMsg(""), 2000);
    });
  }

  if (loading) return <div className="p-6 text-center text-muted-foreground">Loading...</div>;
  if (!digest) return <div className="p-6 text-center text-muted-foreground">Digest not found</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Top bar */}
      <div className="flex items-center justify-between mb-6">
        <Link href="/digests" className="text-sm text-muted-foreground hover:text-foreground">
          ← Back to list
        </Link>
        <div className="flex gap-2 flex-wrap justify-end">
          {digest.share_token ? (
            <>
              <button
                onClick={handleCopyLink}
                className="px-3 py-1.5 text-xs bg-primary/10 text-primary border border-primary/30 rounded hover:bg-primary/20"
              >
                {copyMsg || "Copy link"}
              </button>
              <button
                onClick={handleShare}
                disabled={sharing}
                className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted disabled:opacity-50"
              >
                {sharing ? "..." : "Revoke share"}
              </button>
            </>
          ) : (
            <button
              onClick={handleShare}
              disabled={sharing}
              className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted disabled:opacity-50"
            >
              {sharing ? "..." : "Share"}
            </button>
          )}
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted disabled:opacity-50"
          >
            {regenerating ? "Processing..." : "Regenerate"}
          </button>
          <button
            onClick={handleDelete}
            className="px-3 py-1.5 text-xs text-destructive border border-destructive/30 rounded hover:bg-destructive/10"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Shared indicator */}
      {digest.share_token && (
        <div className="mb-4 px-3 py-2 text-xs text-primary bg-primary/5 border border-primary/20 rounded flex items-center gap-2">
          <span>Public link active —</span>
          <span className="font-mono text-muted-foreground truncate max-w-xs">
            {typeof window !== "undefined" ? `${window.location.origin}/share/${digest.share_token}` : ""}
          </span>
        </div>
      )}

      {/* Meta */}
      <div className="mb-4 text-xs text-muted-foreground flex flex-wrap gap-3">
        <span>{new Date(digest.created_at).toLocaleString("en-US")}</span>
        <span>{digest.sources_count} sources</span>
        {digest.llm_model && <span>Model: {digest.llm_model}</span>}
        {digest.tokens_used > 0 && <span>Tokens: {digest.tokens_used.toLocaleString()}</span>}
      </div>

      {digest.keywords_used && digest.keywords_used.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {digest.keywords_used.map((kw) => (
            <Link
              key={kw}
              href={`/digests?keyword=${encodeURIComponent(kw)}`}
              className="px-2 py-0.5 text-xs bg-primary/10 text-primary rounded-full hover:bg-primary/20 transition-colors"
            >
              {kw}
            </Link>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="bg-background border border-border rounded-lg p-6">
        {digest.summary_md ? (
          <div className="prose prose-slate dark:prose-invert max-w-none prose-h1:text-2xl prose-h2:text-lg prose-h2:border-b prose-h2:border-border prose-h2:pb-1 prose-h3:text-base prose-h3:font-semibold prose-li:my-0.5">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {digest.summary_md}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="text-center py-12 text-muted-foreground">No content</div>
        )}
      </div>
    </div>
  );
}
