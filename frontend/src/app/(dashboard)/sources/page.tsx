"use client";
import { useState, useEffect } from "react";
import { sourcesApi, type Source } from "@/lib/api";

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [mode, setMode] = useState<"url" | "search">("search");
  const [form, setForm] = useState({
    name: "",
    url: "",
    search_query: "",
    source_type: "webpage",
  });
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<{ id: string; result: string } | null>(null);

  useEffect(() => {
    sourcesApi.list().then(setSources).finally(() => setLoading(false));
  }, []);

  function handleModeChange(newMode: "url" | "search") {
    setMode(newMode);
    setFormError("");
    setForm({ name: "", url: "", search_query: "", source_type: "webpage" });
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    setSaving(true);
    try {
      const payload =
        mode === "search"
          ? { name: form.name, search_query: form.search_query, source_type: "search" as const }
          : { name: form.name, url: form.url, source_type: form.source_type as "webpage" | "rss" };
      const source = await sourcesApi.create(payload);
      setSources((prev) => [source, ...prev]);
      setShowForm(false);
      setForm({ name: "", url: "", search_query: "", source_type: "webpage" });
    } catch (err: any) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(source: Source) {
    const updated = await sourcesApi.update(source.id, { is_active: !source.is_active });
    setSources((prev) => prev.map((s) => (s.id === source.id ? updated : s)));
  }

  async function handleDelete(id: string) {
    if (!confirm("确定删除此信息源？")) return;
    await sourcesApi.delete(id);
    setSources((prev) => prev.filter((s) => s.id !== id));
  }

  async function handleTest(source: Source) {
    setTestResult({ id: source.id, result: "测试中..." });
    try {
      const result = await sourcesApi.test(source.id);
      setTestResult({
        id: source.id,
        result: result.success
          ? `成功 (HTTP ${result.http_status})\n\n${result.content_preview || ""}`
          : `失败: ${result.error}`,
      });
    } catch (err: any) {
      setTestResult({ id: source.id, result: `错误: ${err.message}` });
    }
  }

  const sourceTypeLabel = (s: Source) => {
    if (s.source_type === "search") return "搜索";
    if (s.source_type === "rss") return "RSS";
    return "网页";
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">信息源</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            添加关键词搜索（不限定网址）或指定具体网址
          </p>
        </div>
        <button
          onClick={() => { setShowForm(!showForm); setFormError(""); }}
          className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90"
        >
          {showForm ? "取消" : "+ 添加信息源"}
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="mb-6 bg-background border border-border rounded-lg p-5">
          <h2 className="font-semibold mb-4">添加信息源</h2>

          {/* Mode toggle */}
          <div className="flex gap-1 mb-5 p-1 bg-muted rounded-lg w-fit">
            <button
              type="button"
              onClick={() => handleModeChange("search")}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
                mode === "search"
                  ? "bg-background shadow text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              不限定网址（关键词搜索）
            </button>
            <button
              type="button"
              onClick={() => handleModeChange("url")}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
                mode === "url"
                  ? "bg-background shadow text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              限定网址
            </button>
          </div>

          {formError && (
            <div className="mb-3 px-3 py-2 text-sm text-destructive bg-destructive/10 rounded">
              {formError}
            </div>
          )}

          <form onSubmit={handleAdd} className="space-y-3">
            <div>
              <label className="block text-sm font-medium mb-1">名称</label>
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder={mode === "search" ? "例：美国新闻" : "例：HackerNews"}
              />
            </div>

            {mode === "search" ? (
              <div>
                <label className="block text-sm font-medium mb-1">搜索关键词</label>
                <input
                  required
                  value={form.search_query}
                  onChange={(e) => setForm({ ...form, search_query: e.target.value })}
                  className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="例：美国新闻、AI technology、特朗普"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  系统将自动从 Google News 搜索该关键词的最新资讯
                </p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">类型</label>
                    <select
                      value={form.source_type}
                      onChange={(e) => setForm({ ...form, source_type: e.target.value })}
                      className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      <option value="webpage">网页</option>
                      <option value="rss">RSS/Atom</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">URL</label>
                  <input
                    required
                    type="url"
                    value={form.url}
                    onChange={(e) => setForm({ ...form, url: e.target.value })}
                    className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="https://..."
                  />
                </div>
              </>
            )}

            <div className="flex gap-2 pt-1">
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90 disabled:opacity-50"
              >
                {saving ? "保存中..." : "保存"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Sources list */}
      {loading ? (
        <div className="text-center py-20 text-muted-foreground">加载中...</div>
      ) : sources.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <p>还没有信息源，点击「添加信息源」开始</p>
        </div>
      ) : (
        <div className="space-y-2">
          {sources.map((source) => (
            <div key={source.id}>
              <div className="bg-background border border-border rounded-lg px-4 py-3 flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{source.name}</span>
                    <span className="px-1.5 py-0.5 text-xs bg-muted rounded">
                      {sourceTypeLabel(source)}
                    </span>
                    {!source.is_active && (
                      <span className="px-1.5 py-0.5 text-xs bg-muted text-muted-foreground rounded">
                        已禁用
                      </span>
                    )}
                  </div>
                  {source.source_type === "search" ? (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      搜索词：{source.search_query}
                    </p>
                  ) : (
                    <p className="text-xs text-muted-foreground truncate mt-0.5">{source.url}</p>
                  )}
                  {source.last_crawled_at && (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      上次抓取：{new Date(source.last_crawled_at).toLocaleString("zh-CN")}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleTest(source)}
                    className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted"
                  >
                    测试
                  </button>
                  <button
                    onClick={() => handleToggle(source)}
                    className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted"
                  >
                    {source.is_active ? "禁用" : "启用"}
                  </button>
                  <button
                    onClick={() => handleDelete(source.id)}
                    className="px-3 py-1.5 text-xs text-destructive border border-destructive/30 rounded hover:bg-destructive/10"
                  >
                    删除
                  </button>
                </div>
              </div>
              {testResult?.id === source.id && (
                <div className="mx-px mt-1 p-3 bg-muted rounded-b text-xs font-mono whitespace-pre-wrap">
                  {testResult.result}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
