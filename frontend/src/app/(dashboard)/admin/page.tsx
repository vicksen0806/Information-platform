"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { adminApi, authApi, type User, type AdminStats, type AuditLog } from "@/lib/api";
import { useT } from "@/lib/i18n";

export default function AdminPage() {
  const t = useT();
  const router = useRouter();

  const [tab, setTab] = useState<"users" | "audit">("users");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState("");
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [accessDenied, setAccessDenied] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);

  const LIMIT = 50;

  // Guard: check admin access
  useEffect(() => {
    authApi.me().then((u) => {
      if (!u.is_admin) {
        setAccessDenied(true);
        router.push("/dashboard");
      }
    }).catch(() => router.push("/login"));
  }, [router]);

  // Load stats
  useEffect(() => {
    adminApi.getStats().then(setStats).catch(() => {});
  }, []);

  // Load initial users
  const loadUsers = useCallback(async (off: number, replace: boolean) => {
    setLoadingMore(true);
    try {
      const page = await adminApi.getUsers(LIMIT, off);
      setUsers((prev) => replace ? page : [...prev, ...page]);
      setHasMore(page.length === LIMIT);
      setOffset(off + page.length);
    } finally {
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    loadUsers(0, true);
  }, [loadUsers]);

  useEffect(() => {
    if (tab === "audit") {
      adminApi.getAuditLogs().then(setAuditLogs).catch(() => {});
    }
  }, [tab]);

  async function handleToggle(user: User) {
    setTogglingId(user.id);
    try {
      const updated = await adminApi.updateUser(user.id, !user.is_active);
      setUsers((prev) => prev.map((u) => u.id === updated.id ? updated : u));
    } finally {
      setTogglingId(null);
    }
  }

  async function handleTriggerAll() {
    setTriggering(true);
    try {
      await adminApi.triggerAll();
      setTriggerMsg(t("admin_triggered"));
      setTimeout(() => setTriggerMsg(""), 3000);
    } finally {
      setTriggering(false);
    }
  }

  if (accessDenied) return null;

  const statCards = stats ? [
    { label: t("admin_stats_users"), value: stats.total_users },
    { label: t("admin_stats_jobs"), value: stats.total_crawl_jobs },
    { label: t("admin_stats_digests"), value: stats.total_digests },
    { label: t("admin_stats_tokens"), value: stats.total_tokens_used.toLocaleString() },
  ] : [];

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("admin_title")}</h1>
        <div className="flex items-center gap-3">
          {triggerMsg && <span className="text-sm text-green-600">{triggerMsg}</span>}
          <button
            onClick={handleTriggerAll}
            disabled={triggering}
            className="px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
          >
            {triggering ? t("admin_triggering") : t("admin_trigger_all")}
          </button>
        </div>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {statCards.map((card) => (
            <div key={card.label} className="bg-card border border-border rounded-lg p-4">
              <p className="text-xs text-muted-foreground mb-1">{card.label}</p>
              <p className="text-2xl font-bold">{card.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {(["users", "audit"] as const).map((t_) => (
          <button
            key={t_}
            onClick={() => setTab(t_)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t_
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t_ === "users" ? t("admin_users_title") : t("admin_col_action") + " Log"}
          </button>
        ))}
      </div>

      {/* Users table */}
      {tab === "users" && <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="font-semibold">{t("admin_users_title")}</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-muted-foreground">{t("admin_col_email")}</th>
                <th className="text-left px-4 py-2 font-medium text-muted-foreground">{t("admin_col_name")}</th>
                <th className="text-left px-4 py-2 font-medium text-muted-foreground">{t("admin_col_role")}</th>
                <th className="text-left px-4 py-2 font-medium text-muted-foreground">{t("admin_col_status")}</th>
                <th className="text-left px-4 py-2 font-medium text-muted-foreground">{t("admin_col_registered")}</th>
                <th className="text-left px-4 py-2 font-medium text-muted-foreground">{t("admin_col_action")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-muted/30">
                  <td className="px-4 py-2">{user.email}</td>
                  <td className="px-4 py-2 text-muted-foreground">{user.display_name || "—"}</td>
                  <td className="px-4 py-2">
                    {user.is_admin
                      ? <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full">{t("admin_role_admin")}</span>
                      : <span className="text-xs text-muted-foreground">{t("admin_role_user")}</span>
                    }
                  </td>
                  <td className="px-4 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${user.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                      {user.is_active ? t("active") : t("disabled_label")}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground text-xs">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2">
                    {!user.is_admin && (
                      <button
                        onClick={() => handleToggle(user)}
                        disabled={togglingId === user.id}
                        className={`text-xs px-2 py-1 rounded border transition-colors disabled:opacity-50 ${
                          user.is_active
                            ? "border-destructive/30 text-destructive hover:bg-destructive/5"
                            : "border-primary/30 text-primary hover:bg-primary/5"
                        }`}
                      >
                        {togglingId === user.id
                          ? "..."
                          : user.is_active ? t("admin_disable_user") : t("admin_enable_user")
                        }
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {hasMore && (
          <div className="px-4 py-3 border-t border-border">
            <button
              onClick={() => loadUsers(offset, false)}
              disabled={loadingMore}
              className="text-sm text-primary hover:underline disabled:opacity-50"
            >
              {loadingMore ? t("loading") : t("admin_load_more")}
            </button>
          </div>
        )}
      </div>}

      {/* Audit log table */}
      {tab === "audit" && (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Time</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Actor</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Action</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Resource</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Detail</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {auditLogs.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-6 text-center text-muted-foreground text-sm">No audit logs yet.</td></tr>
                )}
                {auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-muted/30">
                    <td className="px-4 py-2 text-xs text-muted-foreground whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-xs">{log.actor_email || "—"}</td>
                    <td className="px-4 py-2">
                      <code className="text-xs bg-muted px-1 py-0.5 rounded">{log.action}</code>
                    </td>
                    <td className="px-4 py-2 text-xs text-muted-foreground">
                      {log.resource_type ? `${log.resource_type}:${log.resource_id}` : "—"}
                    </td>
                    <td className="px-4 py-2 text-xs text-muted-foreground max-w-xs truncate">
                      {log.detail ? JSON.stringify(log.detail) : "—"}
                    </td>
                    <td className="px-4 py-2 text-xs text-muted-foreground">{log.ip_address || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
