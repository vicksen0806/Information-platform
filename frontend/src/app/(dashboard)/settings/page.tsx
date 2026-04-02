"use client";
import { useState, useEffect } from "react";
import { settingsApi, authApi, type LlmConfig, type User } from "@/lib/api";

const PROVIDERS = [
  { value: "volcengine", label: "火山方舟 (Doubao)", model: "ep-m-20260322064927-gvkkg" },
  { value: "deepseek", label: "DeepSeek", model: "deepseek-chat" },
  { value: "qwen", label: "通义千问 (Qwen)", model: "qwen-plus" },
  { value: "zhipu", label: "智谱 GLM", model: "glm-4-flash" },
  { value: "moonshot", label: "Moonshot Kimi", model: "moonshot-v1-8k" },
  { value: "openai", label: "OpenAI", model: "gpt-4o-mini" },
];

export default function SettingsPage() {
  const [user, setUser] = useState<User | null>(null);
  const [llmConfig, setLlmConfig] = useState<LlmConfig | null>(null);
  const [llmForm, setLlmForm] = useState({
    provider: "volcengine",
    api_key: "",
    model_name: "ep-m-20260322064927-gvkkg",
    base_url: "",
  });
  const [llmError, setLlmError] = useState("");
  const [llmSuccess, setLlmSuccess] = useState("");
  const [savingLlm, setSavingLlm] = useState(false);
  const [testingLlm, setTestingLlm] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    authApi.me().then(setUser);
    settingsApi.getLlm().then(setLlmConfig).catch(() => {});
  }, []);

  function handleProviderChange(provider: string) {
    const found = PROVIDERS.find((p) => p.value === provider);
    setLlmForm((prev) => ({
      ...prev,
      provider,
      model_name: found?.model || prev.model_name,
      base_url: "",
    }));
  }

  async function handleSaveLlm(e: React.FormEvent) {
    e.preventDefault();
    setLlmError("");
    setLlmSuccess("");
    setSavingLlm(true);
    try {
      const config = await settingsApi.upsertLlm({
        provider: llmForm.provider,
        api_key: llmForm.api_key,
        model_name: llmForm.model_name,
        base_url: llmForm.base_url || undefined,
      });
      setLlmConfig(config);
      setLlmForm((prev) => ({ ...prev, api_key: "" }));
      setLlmSuccess("保存成功");
    } catch (err: any) {
      setLlmError(err.message);
    } finally {
      setSavingLlm(false);
    }
  }

  async function handleTestLlm() {
    setTestingLlm(true);
    setTestResult(null);
    try {
      const result = await settingsApi.testLlm();
      setTestResult(result);
    } catch (err: any) {
      setTestResult({ success: false, message: err.message });
    } finally {
      setTestingLlm(false);
    }
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold">设置</h1>

      {/* LLM Config */}
      <section className="bg-background border border-border rounded-lg p-5">
        <h2 className="font-semibold mb-1">大模型配置</h2>
        <p className="text-sm text-muted-foreground mb-4">
          配置用于生成摘要的 AI 大模型 API
        </p>

        {llmConfig && (
          <div className="mb-4 p-3 bg-muted rounded text-sm">
            当前：<strong>{llmConfig.provider}</strong> · {llmConfig.model_name} ·
            密钥：{llmConfig.api_key_masked}
          </div>
        )}

        {llmError && (
          <div className="mb-3 px-3 py-2 text-sm text-destructive bg-destructive/10 rounded">{llmError}</div>
        )}
        {llmSuccess && (
          <div className="mb-3 px-3 py-2 text-sm text-green-700 bg-green-50 rounded">{llmSuccess}</div>
        )}

        <form onSubmit={handleSaveLlm} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">提供商</label>
              <select
                value={llmForm.provider}
                onChange={(e) => handleProviderChange(e.target.value)}
                className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">模型名称</label>
              <input
                required
                value={llmForm.model_name}
                onChange={(e) => setLlmForm({ ...llmForm, model_name: e.target.value })}
                className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">API Key</label>
            <input
              type="password"
              required
              value={llmForm.api_key}
              onChange={(e) => setLlmForm({ ...llmForm, api_key: e.target.value })}
              className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder={llmConfig ? "输入新密钥以更新" : "粘贴 API Key"}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              自定义 Base URL（可选，留空使用默认）
            </label>
            <input
              value={llmForm.base_url}
              onChange={(e) => setLlmForm({ ...llmForm, base_url: e.target.value })}
              className="w-full px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="https://api.example.com/v1"
            />
          </div>
          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={savingLlm}
              className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:opacity-90 disabled:opacity-50"
            >
              {savingLlm ? "保存中..." : "保存"}
            </button>
            {llmConfig && (
              <button
                type="button"
                onClick={handleTestLlm}
                disabled={testingLlm}
                className="px-4 py-2 border border-border text-sm font-medium rounded-md hover:bg-muted disabled:opacity-50"
              >
                {testingLlm ? "测试中..." : "测试连接"}
              </button>
            )}
          </div>
        </form>

        {testResult && (
          <div className={`mt-3 p-3 text-sm rounded ${testResult.success ? "bg-green-50 text-green-800" : "bg-destructive/10 text-destructive"}`}>
            {testResult.success ? "✓ " : "✗ "}{testResult.message}
          </div>
        )}
      </section>

      {/* Account */}
      <section className="bg-background border border-border rounded-lg p-5">
        <h2 className="font-semibold mb-1">账户信息</h2>
        {user && (
          <div className="text-sm space-y-1 text-muted-foreground">
            <p>邮箱：<span className="text-foreground">{user.email}</span></p>
            <p>昵称：<span className="text-foreground">{user.display_name || "未设置"}</span></p>
            <p>注册时间：<span className="text-foreground">{new Date(user.created_at).toLocaleString("zh-CN")}</span></p>
            {user.is_admin && <p className="text-primary font-medium">管理员账户</p>}
          </div>
        )}
      </section>
    </div>
  );
}
