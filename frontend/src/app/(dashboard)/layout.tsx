"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { authApi, type User } from "@/lib/api";
import { useT } from "@/lib/i18n";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const t = useT();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    authApi.me().then(setUser).catch(() => {});
  }, []);

  const NAV_ITEMS = [
    { href: "/dashboard", label: t("nav_crawl_jobs") },
    { href: "/digests",   label: t("nav_digests") },
    { href: "/keywords",  label: t("nav_keywords") },
    { href: "/settings",  label: t("nav_settings") },
    ...(user?.is_admin ? [{ href: "/admin", label: t("nav_admin") }] : []),
  ];

  async function handleLogout() {
    await authApi.logout();
    router.push("/login");
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 border-r border-border bg-background flex flex-col h-full">
        <div className="px-5 py-5 border-b border-border flex items-center justify-between">
          <span className="font-bold text-lg text-primary">Info Platform</span>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-border space-y-1">
          <button
            onClick={handleLogout}
            className="w-full px-3 py-2 text-sm text-muted-foreground hover:text-destructive hover:bg-muted rounded-md text-left"
          >
            {t("nav_signout")}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-muted/20">
        {children}
      </main>
    </div>
  );
}
