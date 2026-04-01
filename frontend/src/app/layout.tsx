import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "信息平台",
  description: "每日定制信息聚合与智能摘要",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-background font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
