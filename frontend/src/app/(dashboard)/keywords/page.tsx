"use client";
import { useState, useEffect } from "react";
import { keywordsApi, type Keyword } from "@/lib/api";

export default function KeywordsPage() {
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    keywordsApi.list().then(setKeywords).finally(() => setLoading(false));
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setError("");
    try {
      const kw = await keywordsApi.create(text);
      setKeywords((prev) => [...prev, kw]);
      setInput("");
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleToggle(kw: Keyword) {
    const updated = await keywordsApi.toggle(kw.id, !kw.is_active);
    setKeywords((prev) => prev.map((k) => (k.id === kw.id ? updated : k)));
  }

  async function handleDelete(id: string) {
    await keywordsApi.delete(id);
    setKeywords((prev) => prev.filter((k) => k.id !== id));
  }

  const activeCount = keywords.filter((k) => k.is_active).length;

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">关键词</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          LLM 会重点提炼与这些关键词相关的内容 · 已激活 {activeCount} / {keywords.length}
        </p>
      </div>

      {/* Add keyword */}
      <form onSubmit={handleAdd} className="flex gap-2 mb-6">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-1 px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          placeholder="输入关键词，按回车添加"
          maxLength={200}
        />
        <button
          type="submit"
          className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90"
        >
          添加
        </button>
      </form>

      {error && (
        <div className="mb-4 px-3 py-2 text-sm text-destructive bg-destructive/10 rounded">
          {error}
        </div>
      )}

      {/* Keyword tags */}
      {loading ? (
        <div className="text-center py-20 text-muted-foreground">加载中...</div>
      ) : keywords.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          还没有关键词，在上方输入框添加你感兴趣的话题
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {keywords.map((kw) => (
            <div
              key={kw.id}
              className={`inline-flex items-center gap-1.5 pl-3 pr-1.5 py-1.5 rounded-full text-sm border transition-colors ${
                kw.is_active
                  ? "bg-primary/10 text-primary border-primary/30"
                  : "bg-muted text-muted-foreground border-border"
              }`}
            >
              <button onClick={() => handleToggle(kw)} className="font-medium">
                {kw.text}
              </button>
              <button
                onClick={() => handleDelete(kw.id)}
                className="w-4 h-4 flex items-center justify-center rounded-full hover:bg-black/10 text-xs leading-none"
                title="删除"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {keywords.length > 0 && (
        <p className="mt-4 text-xs text-muted-foreground">
          点击关键词可切换启用/禁用状态，点击 × 删除
        </p>
      )}
    </div>
  );
}
