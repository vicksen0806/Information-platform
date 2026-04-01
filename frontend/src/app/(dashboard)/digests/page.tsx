"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { digestsApi, type DigestListItem } from "@/lib/api";

export default function DigestsPage() {
  const [digests, setDigests] = useState<DigestListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    digestsApi.list().then(setDigests).finally(() => setLoading(false));
  }, []);

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.preventDefault();
    if (!confirm("确定删除？")) return;
    await digestsApi.delete(id);
    setDigests((prev) => prev.filter((d) => d.id !== id));
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">摘要历史</h1>
        <p className="text-sm text-muted-foreground mt-0.5">所有历史摘要，点击查看详情</p>
      </div>

      {loading ? (
        <div className="text-center py-20 text-muted-foreground">加载中...</div>
      ) : digests.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">暂无摘要历史</div>
      ) : (
        <div className="space-y-2">
          {digests.map((digest) => (
            <Link
              key={digest.id}
              href={`/digests/${digest.id}`}
              className="group flex items-center justify-between bg-background border border-border rounded-lg px-4 py-3 hover:border-primary/50 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                {!digest.is_read && (
                  <div className="w-2 h-2 rounded-full bg-primary shrink-0" />
                )}
                <div className="min-w-0">
                  <p className={`text-sm font-medium truncate ${!digest.is_read ? "" : "text-muted-foreground"}`}>
                    {digest.title || "无标题摘要"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {new Date(digest.created_at).toLocaleString("zh-CN")} · {digest.sources_count} 个来源
                  </p>
                </div>
              </div>
              <button
                onClick={(e) => handleDelete(digest.id, e)}
                className="shrink-0 ml-4 px-2 py-1 text-xs text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100"
              >
                删除
              </button>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
