"use client";
import { useState, useEffect } from "react";
import { settingsApi, digestsApi, authApi, type LlmConfig, type User, type NotificationConfig, type UsageStats, type EmailConfig } from "@/lib/api";
import { useLang, useT } from "@/lib/i18n";

const PROVIDERS = [
  { value: "volcengine", label: "Volcengine (Doubao)", model: "ep-m-20260322064927-gvkkg" },
  { value: "deepseek",   label: "DeepSeek",            model: "deepseek-chat" },
  { value: "qwen",       label: "Qwen",                model: "qwen-plus" },
  { value: "zhipu",      label: "Zhipu GLM",           model: "glm-4-flash" },
  { value: "moonshot",   label: "Moonshot Kimi",        model: "moonshot-v1-8k" },
  { value: "openai",     label: "OpenAI",              model: "gpt-4o-mini" },
];

const WEBHOOK_TYPES = [
  { value: "feishu",   label: "Feishu (飞书)" },
  { value: "wecom",    label: "WeCom (企业微信)" },
  { value: "discord",  label: "Discord" },
  { value: "telegram", label: "Telegram" },
  { value: "generic",  label: "Generic JSON" },
];

export default function SettingsPage() {
  const t = useT();
  const { lang, toggle } = useLang();
  const [user, setUser] = useState<User | null>(null);
  const [usage, setUsage] = useState<UsageStats | null>(null);

  const [llmConfig, setLlmConfig] = useState<LlmConfig | null>(null);
  const [llmForm, setLlmForm] = useState({ provider: "volcengine", api_key: "", model_name: "ep-m-20260322064927-gvkkg", base_url: "" });
  const [summaryStyle, setSummaryStyle] = useState<"concise" | "detailed" | "academic">("concise");
  const [llmError, setLlmError] = useState("");
  const [llmSuccess, setLlmSuccess] = useState("");
  const [savingLlm, setSavingLlm] = useState(false);
  const [testingLlm, setTestingLlm] = useState(false);
  const [llmTestResult, setLlmTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const [notifConfig, setNotifConfig] = useState<NotificationConfig | null>(null);
  const [notifForm, setNotifForm] = useState({ webhook_type: "feishu", webhook_url: "", is_active: true });
  const [savingNotif, setSavingNotif] = useState(false);
  const [testingNotif, setTestingNotif] = useState(false);
  const [notifSuccess, setNotifSuccess] = useState("");
  const [notifError, setNotifError] = useState("");
  const [notifTestResult, setNotifTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const [emailConfig, setEmailConfig] = useState<EmailConfig | null>(null);
  const [emailForm, setEmailForm] = useState({ smtp_host: "", smtp_port: 465, smtp_user: "", smtp_password: "", smtp_from: "", smtp_to: "", is_active: true });
  const [savingEmail, setSavingEmail] = useState(false);
  const [testingEmail, setTestingEmail] = useState(false);
  const [emailSuccess, setEmailSuccess] = useState("");
  const [emailError, setEmailError] = useState("");
  const [emailTestResult, setEmailTestResult] = useState<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    authApi.me().then(setUser);
    digestsApi.usage().then(setUsage).catch(() => {});
    settingsApi.getLlm().then((config) => {
      setLlmConfig(config);
      setLlmForm((prev) => ({ ...prev, provider: config.provider, model_name: config.model_name, base_url: config.base_url || "" }));
      setSummaryStyle((config.summary_style as "concise" | "detailed" | "academic") || "concise");
    }).catch(() => {});
    settingsApi.getNotification().then((c) => {
      setNotifConfig(c);
      setNotifForm({ webhook_type: c.webhook_type, webhook_url: "", is_active: c.is_active });
    }).catch(() => {});
    settingsApi.getEmail().then((c) => {
      setEmailConfig(c);
      setEmailForm((prev) => ({ ...prev, smtp_host: c.smtp_host, smtp_port: c.smtp_port, smtp_user: c.smtp_user, smtp_from: c.smtp_from, smtp_to: c.smtp_to, is_active: c.is_active }));
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
      const config = await settingsApi.upsertLlm({ provider: llmForm.provider, api_key: llmForm.api_key, model_name: llmForm.model_name, base_url: llmForm.base_url || undefined, summary_style: summaryStyle });
      setLlmConfig(config);
      setSummaryStyle((config.summary_style as "concise" | "detailed" | "academic") || "concise");
      setLlmSuccess(t("settings_saved"));
    } catch (err: any) { setLlmError(err.message); }
    finally { setSavingLlm(false); }
  }

  async function handleTestLlm() {
    setTestingLlm(true); setLlmTestResult(null);
    try { setLlmTestResult(await settingsApi.testLlm()); }
    catch (err: any) { setLlmTestResult({ success: false, message: err.message }); }
    finally { setTestingLlm(false); }
  }

  async function handleSaveNotif(e: React.FormEvent) {
    e.preventDefault();
    setNotifError(""); setNotifSuccess(""); setSavingNotif(true);
    try {
      const config = await settingsApi.upsertNotification(notifForm);
      setNotifConfig(config); setNotifSuccess(t("settings_saved"));
    } catch (err: any) { setNotifError(err.message); }
    finally { setSavingNotif(false); }
  }

  async function handleTestNotif() {
    setTestingNotif(true); setNotifTestResult(null);
    try { setNotifTestResult(await settingsApi.testNotification()); }
    catch (err: any) { setNotifTestResult({ success: false, message: err.message }); }
    finally { setTestingNotif(false); }
  }

  async function handleDeleteNotif() {
    if (!confirm(t("settings_remove_notif_confirm"))) return;
    await settingsApi.deleteNotification();
    setNotifConfig(null);
    setNotifForm({ webhook_type: "feishu", webhook_url: "", is_active: true });
  }

  async function handleSaveEmail(e: React.FormEvent) {
    e.preventDefault();
    setEmailError(""); setEmailSuccess(""); setSavingEmail(true);
    try {
      const config = await settingsApi.upsertEmail({
        smtp_host: emailForm.smtp_host,
        smtp_port: emailForm.smtp_port,
        smtp_user: emailForm.smtp_user,
        smtp_password: emailForm.smtp_password || undefined,
        smtp_from: emailForm.smtp_from,
        smtp_to: emailForm.smtp_to,
        is_active: emailForm.is_active,
      });
      setEmailConfig(config);
      setEmailForm((prev) => ({ ...prev, smtp_password: "" }));
      setEmailSuccess(t("settings_saved"));
    } catch (err: any) { setEmailError(err.message); }
    finally { setSavingEmail(false); }
  }

  async function handleTestEmail() {
    setTestingEmail(true); setEmailTestResult(null);
    try { setEmailTestResult(await settingsApi.testEmail()); }
    catch (err: any) { setEmailTestResult({ success: false, message: err.message }); }
    finally { setTestingEmail(false); }
  }

  async function handleDeleteEmail() {
    if (!confirm(t("settings_remove_email_confirm"))) return;
    await settingsApi.deleteEmail();
    setEmailConfig(null);
    setEmailForm({ smtp_host: "", smtp_port: 465, smtp_user: "", smtp_password: "", smtp_from: "", smtp_to: "", is_active: true });
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold">{t("settings_title")}</h1>

      {/* ── Account ── */}
      <section className="bg-background border border-border rounded-lg p-5">
        <h2 className="font-semibold mb-1">{t("settings_account_title")}</h2>
        {user && (
          <div className="text-sm space-y-1 text-muted-foreground mb-4">
            <p>{t("settings_email")}<span className="text-foreground">{user.email}</span></p>
            <p>{t("settings_display_name")}<span className="text-foreground">{user.display_name || t("settings_name_unset")}</span></p>
            <p>{t("settings_registered")}<span className="text-foreground">{new Date(user.created_at).toLocaleString()}</span></p>
            {user.is_admin && <p className="text-primary font-medium">{t("settings_admin")}</p>}
          </div>
        )}
        <div className="flex items-center justify-between pt-3 border-t border-border">
          <span className="text-sm text-muted-foreground">
            {lang === "zh" ? "界面语言" : "Interface language"}
          </span>
          <button
            onClick={toggle}
            className="flex items-center gap-2 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-muted transition-colors"
          >
            <span>{lang === "zh" ? "中文" : "English"}</span>
            <span className="text-xs text-muted-foreground">→</span>
            <span className="text-muted-foreground">{lang === "zh" ? "English" : "中文"}</span>
          </button>
        </div>
      </section>

      {/* ── LLM ── */}
      <section className="bg-background border border-border rounded-lg p-5">
        <h2 className="font-semibold mb-1">{t("settings_llm_title")}</h2>
        <p className="text-sm text-muted-foreground mb-4">{t("settings_llm_sub")}</p>
        {llmConfig && (
          <div className="mb-4 p-3 bg-muted rounded text-sm">
            {t("settings_llm_current", { p: llmConfig.provider, m: llmConfig.model_name, k: llmConfig.api_key_masked })}
          </div>
        )}
        {llmError && <div className="mb-3 px-3 py-2 text-sm text-destructive bg-destructive/10 rounded">{llmError}</div>}
        {llmSuccess && <div className="mb-3 px-3 py-2 text-sm text-green-700 bg-green-50 rounded">{llmSuccess}</div>}
        <form onSubmit={handleSaveLlm} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">{t("settings_provider")}</label>
              <select value={llmForm.provider} onChange={(e) => handleProviderChange(e.target.value)} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring">
                {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">{t("settings_model")}</label>
              <input required value={llmForm.model_name} onChange={(e) => setLlmForm({ ...llmForm, model_name: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">{t("settings_api_key")}</label>
            {llmConfig && (
              <div className="mb-1 px-3 py-1.5 bg-muted rounded text-xs text-muted-foreground font-mono">
                {t("settings_current_key")}{llmConfig.api_key_masked}
              </div>
            )}
            <input
              type="password"
              value={llmForm.api_key}
              onChange={(e) => setLlmForm({ ...llmForm, api_key: e.target.value })}
              className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder={llmConfig ? t("settings_api_key_keep") : t("settings_api_key_paste")}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">{t("settings_base_url")}</label>
            <input value={llmForm.base_url} onChange={(e) => setLlmForm({ ...llmForm, base_url: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring" placeholder="https://api.example.com/v1" />
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">{t("settings_style_title")}</label>
            <p className="text-xs text-muted-foreground mb-2">{t("settings_style_sub")}</p>
            <div className="flex flex-col gap-1.5">
              {(["concise", "detailed", "academic"] as const).map((style) => (
                <label key={style} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="summaryStyle"
                    value={style}
                    checked={summaryStyle === style}
                    onChange={() => setSummaryStyle(style)}
                    className="accent-primary"
                  />
                  <span className="text-sm">{t(`settings_style_${style}` as any)}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={savingLlm} className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90 disabled:opacity-50">
              {savingLlm ? t("saving") : t("save")}
            </button>
            {llmConfig && (
              <button type="button" onClick={handleTestLlm} disabled={testingLlm} className="px-4 py-2 border border-border text-sm font-medium rounded-md hover:bg-muted disabled:opacity-50">
                {testingLlm ? t("settings_testing") : t("settings_test_conn")}
              </button>
            )}
          </div>
        </form>
        {llmTestResult && (
          <div className={`mt-3 p-3 text-sm rounded ${llmTestResult.success ? "bg-green-50 text-green-800" : "bg-destructive/10 text-destructive"}`}>
            {llmTestResult.success ? "✓ " : "✗ "}{llmTestResult.message}
          </div>
        )}
      </section>

      {/* ── Notification ── */}
      <section className="bg-background border border-border rounded-lg p-5">
        <h2 className="font-semibold mb-1">{t("settings_notif_title")}</h2>
        <p className="text-sm text-muted-foreground mb-4">{t("settings_notif_sub")}</p>
        {notifError && <div className="mb-3 px-3 py-2 text-sm text-destructive bg-destructive/10 rounded">{notifError}</div>}
        {notifSuccess && <div className="mb-3 px-3 py-2 text-sm text-green-700 bg-green-50 rounded">{notifSuccess}</div>}
        {notifConfig && (
          <div className="mb-4 p-3 bg-muted rounded text-sm">
            {t("active")}：<strong>{notifConfig.webhook_type}</strong> · {notifConfig.webhook_url_masked}
            · {notifConfig.is_active ? t("active") : t("disabled_label")}
          </div>
        )}
        <form onSubmit={handleSaveNotif} className="space-y-3">
          <div>
            <label className="block text-sm font-medium mb-1">{t("settings_platform")}</label>
            <select value={notifForm.webhook_type} onChange={(e) => setNotifForm({ ...notifForm, webhook_type: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring">
              {WEBHOOK_TYPES.map((tp) => <option key={tp.value} value={tp.value}>{tp.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">{t("settings_webhook_url")}</label>
            <input
              value={notifForm.webhook_url}
              onChange={(e) => setNotifForm({ ...notifForm, webhook_url: e.target.value })}
              className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder={notifConfig ? t("settings_webhook_placeholder_update") : "https://open.feishu.cn/open-apis/bot/v2/hook/..."}
            />
            {notifForm.webhook_type === "telegram" && (
              <p className="text-xs text-muted-foreground mt-1">{t("settings_telegram_hint")}</p>
            )}
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={notifForm.is_active} onChange={(e) => setNotifForm({ ...notifForm, is_active: e.target.checked })} className="rounded" />
            <span>{t("settings_enable_notif")}</span>
          </label>
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={savingNotif} className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90 disabled:opacity-50">
              {savingNotif ? t("saving") : t("save")}
            </button>
            {notifConfig && (
              <button type="button" onClick={handleTestNotif} disabled={testingNotif} className="px-4 py-2 border border-border text-sm font-medium rounded-md hover:bg-muted disabled:opacity-50">
                {testingNotif ? t("settings_sending") : t("settings_send_test")}
              </button>
            )}
            {notifConfig && (
              <button type="button" onClick={handleDeleteNotif} className="px-4 py-2 text-sm text-destructive border border-destructive/30 rounded-md hover:bg-destructive/10">
                {t("settings_remove")}
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

      {/* ── Email ── */}
      <section className="bg-background border border-border rounded-lg p-5">
        <h2 className="font-semibold mb-1">{t("settings_email_title")}</h2>
        <p className="text-sm text-muted-foreground mb-4">{t("settings_email_sub")}</p>
        {emailError && <div className="mb-3 px-3 py-2 text-sm text-destructive bg-destructive/10 rounded">{emailError}</div>}
        {emailSuccess && <div className="mb-3 px-3 py-2 text-sm text-green-700 bg-green-50 rounded">{emailSuccess}</div>}
        {emailConfig && (
          <div className="mb-4 p-3 bg-muted rounded text-sm">
            {t("settings_email_current", { host: emailConfig.smtp_host, port: String(emailConfig.smtp_port), to: emailConfig.smtp_to })}
            {" · "}{emailConfig.is_active ? t("active") : t("disabled_label")}
          </div>
        )}
        <form onSubmit={handleSaveEmail} className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block text-sm font-medium mb-1">{t("settings_smtp_host")}</label>
              <input required value={emailForm.smtp_host} onChange={(e) => setEmailForm({ ...emailForm, smtp_host: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring" placeholder="smtp.example.com" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">{t("settings_smtp_port")}</label>
              <input required type="number" value={emailForm.smtp_port} onChange={(e) => setEmailForm({ ...emailForm, smtp_port: Number(e.target.value) })} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">{t("settings_smtp_user")}</label>
              <input required value={emailForm.smtp_user} onChange={(e) => setEmailForm({ ...emailForm, smtp_user: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">{t("settings_smtp_password")}</label>
              <input type="password" value={emailForm.smtp_password} onChange={(e) => setEmailForm({ ...emailForm, smtp_password: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring" placeholder={emailConfig ? t("settings_smtp_password_keep") : ""} />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">{t("settings_smtp_from")}</label>
            <input required value={emailForm.smtp_from} onChange={(e) => setEmailForm({ ...emailForm, smtp_from: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring" placeholder="noreply@example.com" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">{t("settings_smtp_to")}</label>
            <input required value={emailForm.smtp_to} onChange={(e) => setEmailForm({ ...emailForm, smtp_to: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring" placeholder="you@example.com" />
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={emailForm.is_active} onChange={(e) => setEmailForm({ ...emailForm, is_active: e.target.checked })} className="rounded" />
            <span>{t("settings_email_active")}</span>
          </label>
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={savingEmail} className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90 disabled:opacity-50">
              {savingEmail ? t("saving") : t("save")}
            </button>
            {emailConfig && (
              <button type="button" onClick={handleTestEmail} disabled={testingEmail} className="px-4 py-2 border border-border text-sm font-medium rounded-md hover:bg-muted disabled:opacity-50">
                {testingEmail ? t("settings_sending") : t("settings_send_test")}
              </button>
            )}
            {emailConfig && (
              <button type="button" onClick={handleDeleteEmail} className="px-4 py-2 text-sm text-destructive border border-destructive/30 rounded-md hover:bg-destructive/10">
                {t("settings_remove")}
              </button>
            )}
          </div>
        </form>
        {emailTestResult && (
          <div className={`mt-3 p-3 text-sm rounded ${emailTestResult.success ? "bg-green-50 text-green-800" : "bg-destructive/10 text-destructive"}`}>
            {emailTestResult.success ? "✓ " : "✗ "}{emailTestResult.message}
          </div>
        )}
      </section>

      {/* ── Usage ── */}
      <section className="bg-background border border-border rounded-lg p-5">
        <h2 className="font-semibold mb-1">{t("settings_usage_title")}</h2>
        <p className="text-sm text-muted-foreground mb-4">{t("settings_usage_sub")}</p>
        {usage ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 bg-muted rounded">
                <p className="text-xs text-muted-foreground">{t("settings_usage_this_month")}</p>
                <p className="text-xl font-bold mt-1">{usage.this_month_tokens.toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">{t("settings_usage_digests", { n: usage.this_month_digests })}</p>
              </div>
              <div className="p-3 bg-muted rounded">
                <p className="text-xs text-muted-foreground">{t("settings_usage_all_time")}</p>
                <p className="text-xl font-bold mt-1">{usage.total_tokens.toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">{t("settings_usage_digests", { n: usage.total_digests })}</p>
              </div>
            </div>
            {usage.monthly.length > 1 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-2">{t("settings_usage_monthly")}</p>
                <div className="space-y-1.5">
                  {[...usage.monthly].reverse().map((m) => {
                    const pct = usage.total_tokens > 0 ? Math.round((m.tokens / usage.total_tokens) * 100) : 0;
                    return (
                      <div key={m.month} className="flex items-center gap-3 text-xs">
                        <span className="w-16 text-muted-foreground shrink-0">{m.month}</span>
                        <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                          <div className="h-full bg-primary rounded-full" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="w-24 text-right text-muted-foreground">{m.tokens.toLocaleString()} tokens</span>
                        <span className="w-16 text-right text-muted-foreground">{t("settings_usage_digests", { n: m.digests })}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{t("settings_usage_empty")}</p>
        )}
      </section>

    </div>
  );
}
