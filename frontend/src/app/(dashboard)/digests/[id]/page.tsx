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

  useEffect(() => {
    digestsApi.get(id).then(setDigest).finally(() => setLoading(false));
  }, [id]);

  async function handleRegenerate() {
    if (!digest) return;
    setRegenerating(true);
    try {
      await digestsApi.regenerate(digest.id);
      alert("重新生成任务已触发，请稍后刷新查看");
    } finally {
      setRegenerating(false);
    }
  }

  async function handleDelete() {
    if (!confirm("确定删除此摘要？")) return;
    await digestsApi.delete(id);
    router.push("/digests");
  }

  if (loading) return <div className="p-6 text-center text-muted-foreground">加载中...</div>;
  if (!digest) return <div className="p-6 text-center text-muted-foreground">摘要不存在</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Top bar */}
      <div className="flex items-center justify-between mb-6">
        <Link href="/digests" className="text-sm text-muted-foreground hover:text-foreground">
          ← 返回列表
        </Link>
        <div className="flex gap-2">
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted disabled:opacity-50"
          >
            {regenerating ? "处理中..." : "重新生成"}
          </button>
          <button
            onClick={handleDelete}
            className="px-3 py-1.5 text-xs text-destructive border border-destructive/30 rounded hover:bg-destructive/10"
          >
            删除
          </button>
        </div>
      </div>

      {/* Meta */}
      <div className="mb-4 text-xs text-muted-foreground flex flex-wrap gap-3">
        <span>{new Date(digest.created_at).toLocaleString("zh-CN")}</span>
        <span>{digest.sources_count} 个来源</span>
        {digest.llm_model && <span>模型：{digest.llm_model}</span>}
        {digest.tokens_used > 0 && <span>Token：{digest.tokens_used}</span>}
      </div>

      {digest.keywords_used && digest.keywords_used.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {digest.keywords_used.map((kw) => (
            <span key={kw} className="px-2 py-0.5 text-xs bg-primary/10 text-primary rounded-full">
              {kw}
            </span>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="bg-background border border-border rounded-lg p-6">
        {digest.summary_md ? (
          <div className="prose max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {digest.summary_md}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="text-center py-12 text-muted-foreground">摘要内容为空</div>
        )}
      </div>
    </div>
  );
}
