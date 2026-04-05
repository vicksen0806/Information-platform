"use client";
import { useState, useEffect, useRef } from "react";
import { keywordsApi, type Keyword, type KeywordExportItem } from "@/lib/api";
import { useT } from "@/lib/i18n";

function MiniTrend({ data }: { data: { day: string; count: number }[] }) {
  const t = useT();

  // Build a full 30-day frame so missing days show as empty bars
  const days = Array.from({ length: 30 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (29 - i));
    return d.toISOString().slice(0, 10);
  });
  const countMap: Record<string, number> = {};
  for (const { day, count } of (data || [])) countMap[day] = count;
  const filled = days.map((day) => ({ day, count: countMap[day] || 0 }));
  const total = filled.reduce((s, d) => s + d.count, 0);
  const max = Math.max(...filled.map((d) => d.count), 1);

  if (total === 0) return (
    <div className="flex items-center gap-1.5">
      <div className="flex items-end gap-px h-4">
        {filled.map((d) => (
          <div key={d.day} className="w-0.5 rounded-sm bg-muted" style={{ height: "4px" }} />
        ))}
      </div>
      <span className="text-xs text-muted-foreground/40">{t("kw_no_data")}</span>
    </div>
  );

  return (
    <div className="flex items-center gap-1.5" title={`${t("kw_article_trend")}: ${total}`}>
      <div className="flex items-end gap-px h-4">
        {filled.map((d) => (
          <div
            key={d.day}
            className={`w-0.5 rounded-sm transition-colors ${d.count > 0 ? "bg-primary/70" : "bg-muted"}`}
            style={{ height: d.count > 0 ? `${Math.max((d.count / max) * 100, 25)}%` : "4px" }}
            title={`${d.day}: ${d.count}`}
          />
        ))}
      </div>
      <span className="text-xs text-muted-foreground">{total} {t("kw_article_trend")}</span>
    </div>
  );
}

function useIntervalOptions() {
  const t = useT();
  return [
    { value: 1,   label: t("kw_interval_1") },
    { value: 6,   label: t("kw_interval_6") },
    { value: 12,  label: t("kw_interval_12") },
    { value: 24,  label: t("kw_interval_24") },
    { value: 72,  label: t("kw_interval_72") },
    { value: 168, label: t("kw_interval_168") },
  ];
}

export default function KeywordsPage() {
  const t = useT();
  const intervalOptions = useIntervalOptions();

  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [groups, setGroups] = useState<string[]>([]);
  const [articleStats, setArticleStats] = useState<Record<string, { day: string; count: number }[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterGroup, setFilterGroup] = useState<string | null>(null);

  const [newText, setNewText] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [newSourceType, setNewSourceType] = useState("webpage");
  const [hasUrl, setHasUrl] = useState(false);
  const [newGroup, setNewGroup] = useState("");
  const [newInterval, setNewInterval] = useState(24);
  const [saving, setSaving] = useState(false);

  const [importMsg, setImportMsg] = useState("");
  const importInputRef = useRef<HTMLInputElement>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editUrl, setEditUrl] = useState("");
  const [editSourceType, setEditSourceType] = useState("webpage");
  const [editHasUrl, setEditHasUrl] = useState(false);
  const [editGroup, setEditGroup] = useState("");
  const [editInterval, setEditInterval] = useState(24);
  const [editRequiresJs, setEditRequiresJs] = useState(false);

  useEffect(() => {
    Promise.all([keywordsApi.list(), keywordsApi.listGroups()])
      .then(([kws, grps]) => { setKeywords(kws); setGroups(grps); })
      .finally(() => setLoading(false));
    keywordsApi.articleStats().then(setArticleStats).catch(() => {});
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const text = newText.trim();
    if (!text) return;
    setError(""); setSaving(true);
    try {
      const kw = await keywordsApi.create({
        text,
        url: hasUrl && newUrl.trim() ? newUrl.trim() : undefined,
        source_type: hasUrl && newUrl.trim() ? newSourceType : "search",
        group_name: newGroup.trim() || undefined,
        crawl_interval_hours: newInterval,
      });
      setKeywords((prev) => [...prev, kw]);
      if (newGroup.trim() && !groups.includes(newGroup.trim())) {
        setGroups((prev) => [...prev, newGroup.trim()].sort());
      }
      setNewText(""); setNewUrl(""); setHasUrl(false); setNewGroup(""); setNewInterval(24);
    } catch (err: any) { setError(err.message); }
    finally { setSaving(false); }
  }

  async function handleExport() {
    const data = await keywordsApi.export();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "keywords.json"; a.click();
    URL.revokeObjectURL(url);
  }

  async function handleImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text) as KeywordExportItem[];
      const result = await keywordsApi.import(data);
      setImportMsg(t("kw_import_success", { added: result.added, skipped: result.skipped }));
      const [kws, grps] = await Promise.all([keywordsApi.list(), keywordsApi.listGroups()]);
      setKeywords(kws); setGroups(grps);
      setTimeout(() => setImportMsg(""), 4000);
    } catch {
      setImportMsg(t("kw_import_error"));
      setTimeout(() => setImportMsg(""), 3000);
    } finally {
      if (importInputRef.current) importInputRef.current.value = "";
    }
  }

  async function handleToggle(kw: Keyword) {
    const updated = await keywordsApi.update(kw.id, { is_active: !kw.is_active });
    setKeywords((prev) => prev.map((k) => (k.id === kw.id ? updated : k)));
  }

  async function handleDelete(id: string) {
    if (!confirm(t("kw_delete_confirm"))) return;
    await keywordsApi.delete(id);
    setKeywords((prev) => prev.filter((k) => k.id !== id));
  }

  function startEdit(kw: Keyword) {
    setEditingId(kw.id);
    setEditHasUrl(!!kw.url);
    setEditUrl(kw.url || "");
    setEditSourceType(kw.source_type === "search" ? "webpage" : kw.source_type);
    setEditGroup(kw.group_name || "");
    setEditInterval(kw.crawl_interval_hours);
    setEditRequiresJs(kw.requires_js || false);
  }

  async function handleSaveEdit(kw: Keyword) {
    const url = editHasUrl && editUrl.trim() ? editUrl.trim() : null;
    const updated = await keywordsApi.update(kw.id, {
      url: url || undefined,
      source_type: url ? editSourceType : "search",
      group_name: editGroup.trim() || undefined,
      crawl_interval_hours: editInterval,
      requires_js: editRequiresJs,
    });
    setKeywords((prev) => prev.map((k) => (k.id === kw.id ? updated : k)));
    const grps = await keywordsApi.listGroups();
    setGroups(grps);
    setEditingId(null);
  }

  const activeCount = keywords.filter((k) => k.is_active).length;

  const filteredKeywords = filterGroup !== null
    ? keywords.filter((k) => (filterGroup === "" ? !k.group_name : k.group_name === filterGroup))
    : keywords;

  const grouped: Record<string, Keyword[]> = {};
  for (const kw of filteredKeywords) {
    const g = kw.group_name || "";
    if (!grouped[g]) grouped[g] = [];
    grouped[g].push(kw);
  }
  const groupKeys = Object.keys(grouped).sort((a, b) => {
    if (a === "") return 1;
    if (b === "") return -1;
    return a.localeCompare(b);
  });

  function intervalLabel(hours: number) {
    return intervalOptions.find((o) => o.value === hours)?.label ?? `${hours}h`;
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{t("kw_title")}</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {t("kw_subtitle", { a: activeCount, t: keywords.length })}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {importMsg && <span className="text-xs text-muted-foreground">{importMsg}</span>}
          <button onClick={handleExport} className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted transition-colors">
            {t("kw_export")}
          </button>
          <button onClick={() => importInputRef.current?.click()} className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted transition-colors">
            {t("kw_import")}
          </button>
          <input ref={importInputRef} type="file" accept=".json" className="hidden" onChange={handleImportFile} />
        </div>
      </div>

      {groups.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          <button
            onClick={() => setFilterGroup(null)}
            className={`px-3 py-1 text-xs rounded-full border transition-colors ${filterGroup === null ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-muted"}`}
          >
            {t("all")}
          </button>
          {groups.map((g) => (
            <button
              key={g}
              onClick={() => setFilterGroup(filterGroup === g ? null : g)}
              className={`px-3 py-1 text-xs rounded-full border transition-colors ${filterGroup === g ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-muted"}`}
            >
              {g}
            </button>
          ))}
          <button
            onClick={() => setFilterGroup("")}
            className={`px-3 py-1 text-xs rounded-full border transition-colors ${filterGroup === "" ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-muted"}`}
          >
            {t("digests_ungrouped")}
          </button>
        </div>
      )}

      <form onSubmit={handleAdd} className="mb-6 bg-background border border-border rounded-lg p-4 space-y-3">
        <div className="flex gap-2">
          <input
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            className="flex-1 px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            placeholder={t("kw_placeholder")}
            maxLength={200}
          />
          <button
            type="submit"
            disabled={saving || !newText.trim()}
            className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90 disabled:opacity-50"
          >
            {saving ? t("kw_adding") : t("kw_add")}
          </button>
        </div>

        <div className="flex gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted-foreground whitespace-nowrap">{t("kw_group_label")}</label>
            <input
              value={newGroup}
              onChange={(e) => setNewGroup(e.target.value)}
              list="group-suggestions"
              className="px-2 py-1 border border-input rounded-md text-xs focus:outline-none focus:ring-2 focus:ring-ring w-28"
              placeholder={t("kw_group_placeholder")}
            />
            <datalist id="group-suggestions">
              {groups.map((g) => <option key={g} value={g} />)}
            </datalist>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted-foreground">{t("kw_frequency")}</label>
            <select
              value={newInterval}
              onChange={(e) => setNewInterval(Number(e.target.value))}
              className="px-2 py-1 border border-input rounded-md text-xs focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {intervalOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
          <input type="checkbox" checked={hasUrl} onChange={(e) => setHasUrl(e.target.checked)} className="rounded" />
          <span className="text-muted-foreground">{t("kw_pin_url")}</span>
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
        <div className="mb-4 px-3 py-2 text-sm text-destructive bg-destructive/10 rounded">{error}</div>
      )}

      {loading ? (
        <div className="text-center py-20 text-muted-foreground">{t("loading")}</div>
      ) : keywords.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">{t("kw_empty")}</div>
      ) : (
        <div className="space-y-4">
          {groupKeys.map((groupKey) => (
            <div key={groupKey}>
              {groupKey && (
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{groupKey}</span>
                  <div className="flex-1 h-px bg-border" />
                </div>
              )}
              <div className="space-y-2">
                {grouped[groupKey].map((kw) => (
                  <div
                    key={kw.id}
                    className={`bg-background border rounded-lg px-4 py-3 transition-colors ${kw.is_active ? "border-border" : "border-border opacity-50"}`}
                  >
                    {editingId === kw.id ? (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">{kw.text}</span>
                          <span className="text-xs text-muted-foreground">{t("edit")}</span>
                        </div>
                        <div className="flex gap-3 flex-wrap">
                          <div className="flex items-center gap-2">
                            <label className="text-xs text-muted-foreground">{t("kw_group_label")}</label>
                            <input
                              value={editGroup}
                              onChange={(e) => setEditGroup(e.target.value)}
                              list="group-suggestions"
                              className="px-2 py-1 border border-input rounded-md text-xs focus:outline-none focus:ring-2 focus:ring-ring w-28"
                              placeholder={t("kw_group_placeholder")}
                            />
                          </div>
                          <div className="flex items-center gap-2">
                            <label className="text-xs text-muted-foreground">{t("kw_frequency")}</label>
                            <select
                              value={editInterval}
                              onChange={(e) => setEditInterval(Number(e.target.value))}
                              className="px-2 py-1 border border-input rounded-md text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                            >
                              {intervalOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                            </select>
                          </div>
                        </div>
                        <label className="flex items-center gap-2 text-sm cursor-pointer">
                          <input type="checkbox" checked={editHasUrl} onChange={(e) => setEditHasUrl(e.target.checked)} />
                          <span className="text-muted-foreground">{t("kw_pin_url")}</span>
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
                        <label className="flex items-center gap-2 text-xs cursor-pointer text-muted-foreground">
                          <input type="checkbox" checked={editRequiresJs} onChange={(e) => setEditRequiresJs(e.target.checked)} />
                          {t("kw_requires_js")}
                          <span className="text-xs opacity-60">({t("kw_requires_js_hint")})</span>
                        </label>
                        <div className="flex gap-2">
                          <button onClick={() => handleSaveEdit(kw)} className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90">{t("save")}</button>
                          <button onClick={() => setEditingId(null)} className="px-3 py-1 text-xs border border-border rounded hover:bg-muted">{t("cancel")}</button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm">{kw.text}</span>
                            {kw.crawl_interval_hours !== 24 && (
                              <span className="text-xs px-1.5 py-0.5 bg-muted rounded text-muted-foreground">
                                {intervalLabel(kw.crawl_interval_hours)}
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {kw.url ? (
                              <span className="truncate block max-w-sm">
                                {kw.source_type === "rss" ? "RSS · " : "Webpage · "}{kw.url}
                              </span>
                            ) : (
                              <span>{t("kw_google_news")}</span>
                            )}
                            {kw.last_crawled_at && (
                              <span className="ml-2 text-muted-foreground/70">
                                {t("kw_last_crawled", { t: new Date(kw.last_crawled_at).toLocaleString() })}
                              </span>
                            )}
                          </div>
                          <div className="mt-1.5">
                            <MiniTrend data={articleStats[kw.text] || []} />
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0 ml-4">
                          <button onClick={() => startEdit(kw)} className="px-2.5 py-1 text-xs border border-border rounded hover:bg-muted">{t("kw_configure")}</button>
                          <button onClick={() => handleToggle(kw)} className="px-2.5 py-1 text-xs border border-border rounded hover:bg-muted">
                            {kw.is_active ? t("disable") : t("enable")}
                          </button>
                          <button onClick={() => handleDelete(kw.id)} className="px-2.5 py-1 text-xs text-destructive border border-destructive/30 rounded hover:bg-destructive/10">
                            {t("delete")}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
