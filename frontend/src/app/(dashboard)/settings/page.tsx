"use client";
import { useState, useEffect } from "react";
import { settingsApi, authApi, type LlmConfig, type User, type ScheduleConfig, type NotificationConfig } from "@/lib/api";

const PROVIDERS = [
  { value: "volcengine", label: "Volcengine (Doubao)", model: "ep-m-20260322064927-gvkkg" },
  { value: "deepseek", label: "DeepSeek", model: "deepseek-chat" },
  { value: "qwen", label: "Qwen", model: "qwen-plus" },
  { value: "zhipu", label: "Zhipu GLM", model: "glm-4-flash" },
  { value: "moonshot", label: "Moonshot Kimi", model: "moonshot-v1-8k" },
  { value: "openai", label: "OpenAI", model: "gpt-4o-mini" },
];

const TIMEZONES = [
  { value: "Asia/Shanghai", label: "China (UTC+8)" },
  { value: "Asia/Tokyo", label: "Japan (UTC+9)" },
  { value: "Asia/Singapore", label: "Singapore (UTC+8)" },
  { value: "Asia/Seoul", label: "Korea (UTC+9)" },
  { value: "Asia/Hong_Kong", label: "Hong Kong (UTC+8)" },
  { value: "America/New_York", label: "New York (UTC-5/-4)" },
  { value: "America/Chicago", label: "Chicago (UTC-6/-5)" },
  { value: "America/Los_Angeles", label: "Los Angeles (UTC-8/-7)" },
  { value: "Europe/London", label: "London (UTC+0/+1)" },
  { value: "Europe/Paris", label: "Paris (UTC+1/+2)" },
  { value: "Europe/Berlin", label: "Berlin (UTC+1/+2)" },
  { value: "UTC", label: "UTC" },
];

const WEBHOOK_TYPES = [
  { value: "feishu", label: "Feishu (飞书)" },
  { value: "wecom", label: "WeCom (企业微信)" },
  { value: "generic", label: "Generic JSON" },
];

export default function SettingsPage() {
  const [user, setUser] = useState<User | null>(null);

  // LLM state
  const [llmConfig, setLlmConfig] = useState<LlmConfig | null>(null);
  const [llmForm, setLlmForm] = useState({ provider: "volcengine", api_key: "", model_name: "ep-m-20260322064927-gvkkg", base_url: "" });
  const [llmError, setLlmError] = useState("");
  const [llmSuccess, setLlmSuccess] = useState("");
  const [savingLlm, setSavingLlm] = useState(false);
  const [testingLlm, setTestingLlm] = useState(false);
  const [llmTestResult, setLlmTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // Schedule state
  const [scheduleForm, setScheduleForm] = useState<ScheduleConfig>({ schedule_hour: 8, schedule_minute: 0, timezone: "Asia/Shanghai", is_active: true });
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [scheduleSuccess, setScheduleSuccess] = useState("");

  // Notification state
  const [notifConfig, setNotifConfig] = useState<NotificationConfig | null>(null);
  const [notifForm, setNotifForm] = useState({ webhook_type: "feishu", webhook_url: "", is_active: true });
  const [savingNotif, setSavingNotif] = useState(false);
  const [testingNotif, setTestingNotif] = useState(false);
  const [notifSuccess, setNotifSuccess] = useState("");
  const [notifError, setNotifError] = useState("");
  const [notifTestResult, setNotifTestResult] = useState<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    authApi.me().then(setUser);
    settingsApi.getLlm().then((config) => {
      setLlmConfig(config);
      setLlmForm((prev) => ({ ...prev, provider: config.provider, model_name: config.model_name, base_url: config.base_url || "" }));
    }).catch(() => {});
    settingsApi.getSchedule().then(setScheduleForm).catch(() => {});
    settingsApi.getNotification().then((c) => {
      setNotifConfig(c);
      setNotifForm({ webhook_type: c.webhook_type, webhook_url: c.webhook_url, is_active: c.is_active });
    }).catch(() => {});
  }, []);

  function handleProviderChange(provider: string) {
    const found = PROVIDERS.find((p) => p.value === provider);
    setLlmForm((prev) => ({ ...prev, provider, model_name: found?.model || prev.model_name, base_url: "" }));
  }

  async function handleSaveLlm(e: React.FormEvent) {
    e.preventDefault();
    setLlmError(""); setLlmSuccess(""); setSavingLlm(true);
    try {
      const config = await settingsApi.upsertLlm({ provider: llmForm.provider, api_key: llmForm.api_key, model_name: llmForm.model_name, base_url: llmForm.base_url || undefined });
      setLlmConfig(config); setLlmSuccess("Saved");
    } catch (err: any) { setLlmError(err.message); } finally { setSavingLlm(false); }
  }

  async function handleTestLlm() {
    setTestingLlm(true); setLlmTestResult(null);
    try { setLlmTestResult(await settingsApi.testLlm()); }
    catch (err: any) { setLlmTestResult({ success: false, message: err.message }); }
    finally { setTestingLlm(false); }
  }

  async function handleSaveSchedule(e: React.FormEvent) {
    e.preventDefault();
    setScheduleSuccess(""); setSavingSchedule(true);
    try { await settingsApi.upsertSchedule(scheduleForm); setScheduleSuccess("Saved"); }
    catch (err: any) { setScheduleSuccess(""); }
    finally { setSavingSchedule(false); }
  }

  async function handleSaveNotif(e: React.FormEvent) {
    e.preventDefault();
    setNotifError(""); setNotifSuccess(""); setSavingNotif(true);
    try {
      const config = await settingsApi.upsertNotification(notifForm);
      setNotifConfig(config); setNotifSuccess("Saved");
    } catch (err: any) { setNotifError(err.message); } finally { setSavingNotif(false); }
  }

  async function handleTestNotif() {
    setTestingNotif(true); setNotifTestResult(null);
    try { setNotifTestResult(await settingsApi.testNotification()); }
    catch (err: any) { setNotifTestResult({ success: false, message: err.message }); }
    finally { setTestingNotif(false); }
  }

  async function handleDeleteNotif() {
    if (!confirm("Remove notification config?")) return;
    await settingsApi.deleteNotification();
    setNotifConfig(null);
    setNotifForm({ webhook_type: "feishu", webhook_url: "", is_active: true });
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold">Settings</h1>

      {/* ── LLM ── */}
      <section className="bg-background border border-border rounded-lg p-5">
        <h2 className="font-semibold mb-1">LLM Configuration</h2>
        <p className="text-sm text-muted-foreground mb-4">Configure the AI model used to generate digests</p>
        {llmConfig && (
          <div className="mb-4 p-3 bg-muted rounded text-sm">
            Current: <strong>{llmConfig.provider}</strong> · {llmConfig.model_name} · Key: {llmConfig.api_key_masked}
          </div>
        )}
        {llmError && <div className="mb-3 px-3 py-2 text-sm text-destructive bg-destructive/10 rounded">{llmError}</div>}
        {llmSuccess && <div className="mb-3 px-3 py-2 text-sm text-green-700 bg-green-50 rounded">{llmSuccess}</div>}
        <form onSubmit={handleSaveLlm} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Provider</label>
              <select value={llmForm.provider} onChange={(e) => handleProviderChange(e.target.value)} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring">
                {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Model name</label>
              <input required value={llmForm.model_name} onChange={(e) => setLlmForm({ ...llmForm, model_name: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">API Key</label>
            {llmConfig && <div className="mb-1 px-3 py-1.5 bg-muted rounded text-xs text-muted-foreground font-mono">Current key: {llmConfig.api_key_masked}</div>}
            <input type="password" value={llmForm.api_key} onChange={(e) => setLlmForm({ ...llmForm, api_key: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring" placeholder={llmConfig ? "Leave blank to keep existing key" : "Paste API Key"} />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Custom Base URL (optional)</label>
            <input value={llmForm.base_url} onChange={(e) => setLlmForm({ ...llmForm, base_url: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring" placeholder="https://api.example.com/v1" />
          </div>
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={savingLlm} className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90 disabled:opacity-50">{savingLlm ? "Saving..." : "Save"}</button>
            {llmConfig && <button type="button" onClick={handleTestLlm} disabled={testingLlm} className="px-4 py-2 border border-border text-sm font-medium rounded-md hover:bg-muted disabled:opacity-50">{testingLlm ? "Testing..." : "Test connection"}</button>}
          </div>
        </form>
        {llmTestResult && (
          <div className={`mt-3 p-3 text-sm rounded ${llmTestResult.success ? "bg-green-50 text-green-800" : "bg-destructive/10 text-destructive"}`}>
            {llmTestResult.success ? "✓ " : "✗ "}{llmTestResult.message}
          </div>
        )}
      </section>

      {/* ── Schedule ── */}
      <section className="bg-background border border-border rounded-lg p-5">
        <h2 className="font-semibold mb-1">Daily Schedule</h2>
        <p className="text-sm text-muted-foreground mb-4">Set the time for automatic daily crawl</p>
        {scheduleSuccess && <div className="mb-3 px-3 py-2 text-sm text-green-700 bg-green-50 rounded">{scheduleSuccess}</div>}
        <form onSubmit={handleSaveSchedule} className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Hour</label>
              <select
                value={scheduleForm.schedule_hour}
                onChange={(e) => setScheduleForm({ ...scheduleForm, schedule_hour: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {Array.from({ length: 24 }, (_, i) => (
                  <option key={i} value={i}>{String(i).padStart(2, "0")}:00</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Minute</label>
              <select
                value={scheduleForm.schedule_minute}
                onChange={(e) => setScheduleForm({ ...scheduleForm, schedule_minute: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value={0}>:00</option>
                <option value={30}>:30</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Timezone</label>
              <select
                value={scheduleForm.timezone}
                onChange={(e) => setScheduleForm({ ...scheduleForm, timezone: e.target.value })}
                className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {TIMEZONES.map((tz) => <option key={tz.value} value={tz.value}>{tz.label}</option>)}
              </select>
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={scheduleForm.is_active} onChange={(e) => setScheduleForm({ ...scheduleForm, is_active: e.target.checked })} className="rounded" />
            <span>Enable automatic daily crawl</span>
          </label>
          <button type="submit" disabled={savingSchedule} className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90 disabled:opacity-50">
            {savingSchedule ? "Saving..." : "Save schedule"}
          </button>
        </form>
      </section>

      {/* ── Notification ── */}
      <section className="bg-background border border-border rounded-lg p-5">
        <h2 className="font-semibold mb-1">Push Notifications</h2>
        <p className="text-sm text-muted-foreground mb-4">Send a webhook message when a new digest is ready</p>
        {notifError && <div className="mb-3 px-3 py-2 text-sm text-destructive bg-destructive/10 rounded">{notifError}</div>}
        {notifSuccess && <div className="mb-3 px-3 py-2 text-sm text-green-700 bg-green-50 rounded">{notifSuccess}</div>}
        <form onSubmit={handleSaveNotif} className="space-y-3">
          <div>
            <label className="block text-sm font-medium mb-1">Platform</label>
            <select value={notifForm.webhook_type} onChange={(e) => setNotifForm({ ...notifForm, webhook_type: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring">
              {WEBHOOK_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Webhook URL</label>
            <input
              value={notifForm.webhook_url}
              onChange={(e) => setNotifForm({ ...notifForm, webhook_url: e.target.value })}
              className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
            />
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={notifForm.is_active} onChange={(e) => setNotifForm({ ...notifForm, is_active: e.target.checked })} className="rounded" />
            <span>Enable notifications</span>
          </label>
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={savingNotif} className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90 disabled:opacity-50">
              {savingNotif ? "Saving..." : "Save"}
            </button>
            {notifConfig && (
              <button type="button" onClick={handleTestNotif} disabled={testingNotif} className="px-4 py-2 border border-border text-sm font-medium rounded-md hover:bg-muted disabled:opacity-50">
                {testingNotif ? "Sending..." : "Send test"}
              </button>
            )}
            {notifConfig && (
              <button type="button" onClick={handleDeleteNotif} className="px-4 py-2 text-sm text-destructive border border-destructive/30 rounded-md hover:bg-destructive/10">
                Remove
              </button>
            )}
          </div>
        </form>
        {notifTestResult && (
          <div className={`mt-3 p-3 text-sm rounded ${notifTestResult.success ? "bg-green-50 text-green-800" : "bg-destructive/10 text-destructive"}`}>
            {notifTestResult.success ? "✓ " : "✗ "}{notifTestResult.message}
          </div>
        )}
      </section>

      {/* ── Account ── */}
      <section className="bg-background border border-border rounded-lg p-5">
        <h2 className="font-semibold mb-1">Account</h2>
        {user && (
          <div className="text-sm space-y-1 text-muted-foreground">
            <p>Email: <span className="text-foreground">{user.email}</span></p>
            <p>Display name: <span className="text-foreground">{user.display_name || "Not set"}</span></p>
            <p>Registered: <span className="text-foreground">{new Date(user.created_at).toLocaleString("en-US")}</span></p>
            {user.is_admin && <p className="text-primary font-medium">Admin account</p>}
          </div>
        )}
      </section>
    </div>
  );
}
