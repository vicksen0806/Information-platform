"use client";
import { useState, useEffect } from "react";
import { keywordsApi, type Keyword } from "@/lib/api";

export default function KeywordsPage() {
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [newText, setNewText] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [newSourceType, setNewSourceType] = useState("webpage");
  const [hasUrl, setHasUrl] = useState(false);
  const [saving, setSaving] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editUrl, setEditUrl] = useState("");
  const [editSourceType, setEditSourceType] = useState("webpage");
  const [editHasUrl, setEditHasUrl] = useState(false);

  useEffect(() => {
    keywordsApi.list().then(setKeywords).finally(() => setLoading(false));
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const text = newText.trim();
    if (!text) return;
    setError("");
    setSaving(true);
    try {
      const kw = await keywordsApi.create({
        text,
        url: hasUrl && newUrl.trim() ? newUrl.trim() : undefined,
        source_type: hasUrl && newUrl.trim() ? newSourceType : "search",
      });
      setKeywords((prev) => [...prev, kw]);
      setNewText("");
      setNewUrl("");
      setHasUrl(false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(kw: Keyword) {
    const updated = await keywordsApi.update(kw.id, { is_active: !kw.is_active });
    setKeywords((prev) => prev.map((k) => (k.id === kw.id ? updated : k)));
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this keyword?")) return;
    await keywordsApi.delete(id);
    setKeywords((prev) => prev.filter((k) => k.id !== id));
  }

  function startEdit(kw: Keyword) {
    setEditingId(kw.id);
    setEditHasUrl(!!kw.url);
    setEditUrl(kw.url || "");
    setEditSourceType(kw.source_type === "search" ? "webpage" : kw.source_type);
  }

  async function handleSaveEdit(kw: Keyword) {
    const url = editHasUrl && editUrl.trim() ? editUrl.trim() : null;
    const updated = await keywordsApi.update(kw.id, {
      url: url || undefined,
      source_type: url ? editSourceType : "search",
    });
    setKeywords((prev) => prev.map((k) => (k.id === kw.id ? updated : k)));
    setEditingId(null);
  }

  const activeCount = keywords.filter((k) => k.is_active).length;

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Keywords</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Each keyword is a crawl source. Leave URL blank to search Google News automatically · {activeCount} / {keywords.length} active
        </p>
      </div>

      {/* Add form */}
      <form onSubmit={handleAdd} className="mb-6 bg-background border border-border rounded-lg p-4 space-y-3">
        <div className="flex gap-2">
          <input
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            className="flex-1 px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            placeholder="e.g. AI, Trump, tplink"
            maxLength={200}
          />
          <button
            type="submit"
            disabled={saving || !newText.trim()}
            className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90 disabled:opacity-50"
          >
            {saving ? "Adding..." : "Add"}
          </button>
        </div>

        <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
          <input
            type="checkbox"
            checked={hasUrl}
            onChange={(e) => setHasUrl(e.target.checked)}
            className="rounded"
          />
          <span className="text-muted-foreground">Pin to a specific URL (optional)</span>
        </label>

        {hasUrl && (
          <div className="flex gap-2 pl-6">
            <select
              value={newSourceType}
              onChange={(e) => setNewSourceType(e.target.value)}
              className="px-2 py-1.5 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="webpage">Webpage</option>
              <option value="rss">RSS</option>
            </select>
            <input
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
              className="flex-1 px-3 py-1.5 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="https://..."
            />
          </div>
        )}
      </form>

      {error && (
        <div className="mb-4 px-3 py-2 text-sm text-destructive bg-destructive/10 rounded">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-20 text-muted-foreground">Loading...</div>
      ) : keywords.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          No keywords yet — add topics you want to follow
        </div>
      ) : (
        <div className="space-y-2">
          {keywords.map((kw) => (
            <div
              key={kw.id}
              className={`bg-background border rounded-lg px-4 py-3 transition-colors ${
                kw.is_active ? "border-border" : "border-border opacity-50"
              }`}
            >
              {editingId === kw.id ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{kw.text}</span>
                    <span className="text-xs text-muted-foreground">Edit source</span>
                  </div>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editHasUrl}
                      onChange={(e) => setEditHasUrl(e.target.checked)}
                    />
                    <span className="text-muted-foreground">Pin to a specific URL</span>
                  </label>
                  {editHasUrl && (
                    <div className="flex gap-2 pl-6">
                      <select
                        value={editSourceType}
                        onChange={(e) => setEditSourceType(e.target.value)}
                        className="px-2 py-1.5 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      >
                        <option value="webpage">Webpage</option>
                        <option value="rss">RSS</option>
                      </select>
                      <input
                        value={editUrl}
                        onChange={(e) => setEditUrl(e.target.value)}
                        className="flex-1 px-3 py-1.5 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        placeholder="https://..."
                      />
                    </div>
                  )}
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleSaveEdit(kw)}
                      className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="px-3 py-1 text-xs border border-border rounded hover:bg-muted"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div className="min-w-0">
                    <span className="font-medium text-sm">{kw.text}</span>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {kw.url ? (
                        <span className="truncate block max-w-sm">
                          {kw.source_type === "rss" ? "RSS · " : "Webpage · "}{kw.url}
                        </span>
                      ) : (
                        <span>Google News auto-search</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-4">
                    <button
                      onClick={() => startEdit(kw)}
                      className="px-2.5 py-1 text-xs border border-border rounded hover:bg-muted"
                    >
                      Configure
                    </button>
                    <button
                      onClick={() => handleToggle(kw)}
                      className="px-2.5 py-1 text-xs border border-border rounded hover:bg-muted"
                    >
                      {kw.is_active ? "Disable" : "Enable"}
                    </button>
                    <button
                      onClick={() => handleDelete(kw.id)}
                      className="px-2.5 py-1 text-xs text-destructive border border-destructive/30 rounded hover:bg-destructive/10"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
