"use client";
import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

export type Lang = "zh" | "en";

// ── Translations ─────────────────────────────────────────────────────────────

export const translations = {
  // Shared
  loading: { zh: "加载中…", en: "Loading..." },
  saving: { zh: "保存中…", en: "Saving..." },
  delete: { zh: "删除", en: "Delete" },
  cancel: { zh: "取消", en: "Cancel" },
  save: { zh: "保存", en: "Save" },
  all: { zh: "全部", en: "All" },
  enable: { zh: "启用", en: "Enable" },
  disable: { zh: "禁用", en: "Disable" },
  edit: { zh: "编辑", en: "Edit" },
  test: { zh: "测试", en: "Test" },
  active: { zh: "已启用", en: "Active" },
  disabled_label: { zh: "已禁用", en: "Disabled" },

  // Nav
  nav_crawl_jobs: { zh: "抓取任务", en: "Crawl Jobs" },
  nav_digests: { zh: "摘要历史", en: "Digest History" },
  nav_keywords: { zh: "关键词", en: "Keywords" },
  nav_settings: { zh: "设置", en: "Settings" },
  nav_signout: { zh: "退出登录", en: "Sign out" },
  nav_admin: { zh: "管理后台", en: "Admin" },

  // Admin page
  admin_title: { zh: "管理后台", en: "Admin Panel" },
  admin_stats_users: { zh: "总用户数", en: "Total users" },
  admin_stats_jobs: { zh: "总抓取次数", en: "Total crawl jobs" },
  admin_stats_digests: { zh: "总摘要数", en: "Total digests" },
  admin_stats_tokens: { zh: "总 Token 用量", en: "Total tokens" },
  admin_users_title: { zh: "用户管理", en: "User Management" },
  admin_trigger_all: { zh: "触发全局抓取", en: "Trigger all crawls" },
  admin_triggering: { zh: "触发中…", en: "Triggering..." },
  admin_triggered: { zh: "已触发！", en: "Triggered!" },
  admin_col_email: { zh: "邮箱", en: "Email" },
  admin_col_name: { zh: "昵称", en: "Name" },
  admin_col_role: { zh: "角色", en: "Role" },
  admin_col_status: { zh: "状态", en: "Status" },
  admin_col_registered: { zh: "注册时间", en: "Registered" },
  admin_col_action: { zh: "操作", en: "Action" },
  admin_role_admin: { zh: "管理员", en: "Admin" },
  admin_role_user: { zh: "普通用户", en: "User" },
  admin_enable_user: { zh: "启用", en: "Enable" },
  admin_disable_user: { zh: "禁用", en: "Disable" },
  admin_load_more: { zh: "加载更多", en: "Load more" },
  admin_no_access: { zh: "无访问权限", en: "Access denied" },

  // Dashboard page
  dash_title: { zh: "抓取任务", en: "Crawl Jobs" },
  dash_subtitle: { zh: "每次抓取的进度与状态", en: "Progress and status of each crawl" },
  dash_crawl_now: { zh: "立即抓取", en: "Crawl now" },
  dash_submitting: { zh: "提交中…", en: "Submitting..." },
  dash_status_queued: { zh: "排队中", en: "Queued" },
  dash_status_crawling: { zh: "抓取中", en: "Crawling" },
  dash_status_failed: { zh: "失败", en: "Failed" },
  dash_status_generating: { zh: "生成摘要中", en: "Generating digest" },
  dash_status_completed: { zh: "已完成", en: "Completed" },
  dash_status_completed_no_new: { zh: "已完成（无新内容）", en: "Completed (no new content)" },
  dash_status_content_found: { zh: "发现新内容", en: "Content found" },
  dash_status_no_new: { zh: "无新内容", en: "No new content" },
  dash_view_digest: { zh: "查看摘要", en: "View digest" },
  dash_api_inactive: { zh: "API Key 已失效 — 摘要生成已暂停", en: "API Key is inactive — digest generation paused" },
  dash_api_inactive_sub: { zh: "请在设置页面更新 API Key 以恢复。", en: "Update your API Key to resume." },
  dash_go_settings: { zh: "前往设置", en: "Go to Settings" },
  dash_empty_title: { zh: "暂无抓取任务", en: "No crawl jobs yet" },
  dash_empty_sub: { zh: "添加关键词后点击「立即抓取」开始", en: 'Add keywords then click "Crawl now" to start' },
  dash_elapsed: { zh: "已用时", en: "Elapsed" },

  // Digests page
  digests_title: { zh: "摘要历史", en: "Digest History" },
  digests_subtitle_all: { zh: "按词条查看历史抓取内容", en: "Browse crawl history by keyword" },
  digests_subtitle_kw: { zh: "关键词「{kw}」的历史抓取内容", en: 'History for "{kw}"' },
  digests_view_list: { zh: "列表", en: "List" },
  digests_view_trend: { zh: "趋势", en: "Trend" },
  digests_search_placeholder: { zh: "搜索词条…", en: "Search keywords..." },
  digests_searching: { zh: "搜索中…", en: "Searching..." },
  digests_empty: { zh: "暂无词条历史", en: "No keyword history yet" },
  digests_empty_kw: { zh: "关键词「{kw}」暂无历史内容", en: 'No history for "{kw}" yet' },
  digests_empty_search: { zh: "「{q}」无搜索结果", en: 'No results for "{q}"' },
  digests_sources: { zh: "{n} 个来源", en: "{n} sources" },
  digests_ungrouped: { zh: "未分组", en: "Ungrouped" },
  digests_keyword_list_title: { zh: "全部词条", en: "All keywords" },
  digests_keyword_history_title: { zh: "历史记录", en: "History" },
  digests_keyword_total: { zh: "已抓取 {n} 个词条", en: "{n} keyword(s) crawled" },
  digests_keyword_days: { zh: "{n} 天记录", en: "{n} day(s)" },
  digests_history_count: { zh: "过去 {n} 次抓取", en: "Past {n} crawls" },
  digests_history_articles: { zh: "{n} 篇文章", en: "{n} articles" },
  digests_history_open: { zh: "打开原摘要", en: "Open digest" },
  trend_subtitle: { zh: "各关键词每周摘要频率 · 最近 {n} 周", en: "Digest frequency per keyword · last {n} week(s)" },
  trend_empty: { zh: "暂无摘要，生成摘要后即可查看趋势", en: "No digests yet — generate digests to see trends" },
  trend_keyword: { zh: "关键词", en: "Keyword" },
  trend_total: { zh: "合计", en: "Total" },
  trend_pct: { zh: "{pct}% 的全部摘要", en: "{pct}% of all digests" },

  // Digest detail page
  digest_back: { zh: "← 返回列表", en: "← Back to list" },
  digest_copy_link: { zh: "复制链接", en: "Copy link" },
  digest_copied: { zh: "已复制！", en: "Copied!" },
  digest_share: { zh: "分享", en: "Share" },
  digest_revoke: { zh: "撤销分享", en: "Revoke share" },
  digest_regenerate: { zh: "重新生成", en: "Regenerate" },
  digest_regenerating: { zh: "处理中…", en: "Processing..." },
  digest_delete: { zh: "删除", en: "Delete" },
  digest_regen_alert: { zh: "重新生成已触发 — 稍后刷新查看结果", en: "Regeneration triggered — refresh in a moment to see the result" },
  digest_delete_confirm: { zh: "删除这条摘要？", en: "Delete this digest?" },
  digest_public_link: { zh: "公开链接已启用 —", en: "Public link active —" },
  digest_not_found: { zh: "摘要不存在", en: "Digest not found" },
  digest_no_content: { zh: "暂无内容", en: "No content" },
  digest_model: { zh: "模型：{m}", en: "Model: {m}" },
  digest_tokens: { zh: "Token 用量：{n}", en: "Tokens: {n}" },

  // Keywords page
  kw_title: { zh: "关键词", en: "Keywords" },
  kw_subtitle: { zh: "每个关键词是一个抓取来源。留空 URL 则自动搜索 Google News · {a}/{t} 已启用", en: "Each keyword is a crawl source. Leave URL blank to search Google News automatically · {a}/{t} active" },
  kw_add: { zh: "添加", en: "Add" },
  kw_adding: { zh: "添加中…", en: "Adding..." },
  kw_placeholder: { zh: "如 AI、特朗普、tplink", en: "e.g. AI, Trump, tplink" },
  kw_group_label: { zh: "分组（可选）", en: "Group (optional)" },
  kw_group_placeholder: { zh: "如 科技", en: "e.g. Tech" },
  kw_frequency: { zh: "抓取频率", en: "Crawl frequency" },
  kw_daily_once: { zh: "同一词条每天最多抓取一次", en: "Each keyword is crawled at most once per day" },
  kw_pin_url: { zh: "指定 URL（可选）", en: "Pin to a specific URL (optional)" },
  kw_configure: { zh: "配置", en: "Configure" },
  kw_google_news: { zh: "Google News 自动搜索", en: "Google News auto-search" },
  kw_last_crawled: { zh: "· 最近抓取于 {t}", en: "· Last crawled {t}" },
  kw_empty: { zh: "暂无关键词 — 添加你想关注的话题", en: "No keywords yet — add topics you want to follow" },
  kw_delete_confirm: { zh: "删除这个关键词？", en: "Delete this keyword?" },
  kw_requires_js: { zh: "启用 JS 渲染（Playwright）", en: "Enable JS rendering (Playwright)" },
  kw_requires_js_hint: { zh: "对单页应用或登录墙页面使用，会更慢", en: "For SPAs or paywalled pages — slower" },
  kw_interval_1: { zh: "每小时", en: "Every hour" },
  kw_interval_6: { zh: "每 6 小时", en: "Every 6 hours" },
  kw_interval_12: { zh: "每 12 小时", en: "Every 12 hours" },
  kw_interval_24: { zh: "每天", en: "Daily" },
  kw_interval_72: { zh: "每 3 天", en: "Every 3 days" },
  kw_interval_168: { zh: "每周", en: "Weekly" },

  // Settings page
  settings_title: { zh: "设置", en: "Settings" },
  settings_llm_title: { zh: "LLM 配置", en: "LLM Configuration" },
  settings_llm_sub: { zh: "配置用于生成摘要的 AI 模型", en: "Configure the AI model used to generate digests" },
  settings_llm_current: { zh: "当前：{p} · {m} · Key: {k}", en: "Current: {p} · {m} · Key: {k}" },
  settings_provider: { zh: "供应商", en: "Provider" },
  settings_model: { zh: "模型名称", en: "Model name" },
  settings_api_key: { zh: "API Key", en: "API Key" },
  settings_api_key_keep: { zh: "留空则保持现有 Key", en: "Leave blank to keep existing key" },
  settings_api_key_paste: { zh: "粘贴 API Key", en: "Paste API Key" },
  settings_base_url: { zh: "自定义 Base URL（可选）", en: "Custom Base URL (optional)" },
  settings_test_conn: { zh: "测试连接", en: "Test connection" },
  settings_testing: { zh: "测试中…", en: "Testing..." },
  settings_schedule_title: { zh: "定时调度", en: "Daily Schedule" },
  settings_schedule_sub: { zh: "设置每日自动抓取时间", en: "Set the time for automatic daily crawl" },
  settings_hour: { zh: "时", en: "Hour" },
  settings_minute: { zh: "分", en: "Minute" },
  settings_timezone: { zh: "时区", en: "Timezone" },
  settings_enable_schedule: { zh: "启用每日自动抓取", en: "Enable automatic daily crawl" },
  settings_save_schedule: { zh: "保存调度", en: "Save schedule" },
  settings_notif_title: { zh: "推送通知", en: "Push Notifications" },
  settings_notif_sub: { zh: "新摘要生成后通过 Webhook 发送通知", en: "Send a webhook message when a new digest is ready" },
  settings_platform: { zh: "平台", en: "Platform" },
  settings_webhook_url: { zh: "Webhook URL", en: "Webhook URL" },
  settings_webhook_placeholder_update: { zh: "输入新 URL 以更新", en: "Enter new URL to update" },
  settings_enable_notif: { zh: "启用通知", en: "Enable notifications" },
  settings_send_test: { zh: "发送测试", en: "Send test" },
  settings_sending: { zh: "发送中…", en: "Sending..." },
  settings_remove: { zh: "移除", en: "Remove" },
  settings_remove_notif_confirm: { zh: "移除通知配置？", en: "Remove notification config?" },
  settings_usage_title: { zh: "API 用量", en: "API Usage" },
  settings_usage_sub: { zh: "所有摘要的 LLM Token 消耗统计", en: "LLM token consumption across all digests" },
  settings_usage_this_month: { zh: "本月", en: "This month" },
  settings_usage_all_time: { zh: "累计", en: "All time" },
  settings_usage_digests: { zh: "{n} 条摘要", en: "{n} digests" },
  settings_usage_monthly: { zh: "按月明细", en: "Monthly breakdown" },
  settings_usage_empty: { zh: "暂未生成摘要。", en: "No digests generated yet." },
  settings_account_title: { zh: "账户", en: "Account" },
  settings_email: { zh: "邮箱：", en: "Email: " },
  settings_display_name: { zh: "昵称：", en: "Display name: " },
  settings_name_unset: { zh: "未设置", en: "Not set" },
  settings_registered: { zh: "注册时间：", en: "Registered: " },
  settings_admin: { zh: "管理员账户", en: "Admin account" },
  settings_saved: { zh: "已保存", en: "Saved" },
  settings_current_key: { zh: "当前 Key：", en: "Current key: " },

  // Share page
  share_platform: { zh: "信息平台 · 公开摘要", en: "Info Platform · Shared digest" },
  share_not_found_title: { zh: "链接不存在", en: "Link not found" },
  share_not_found_sub: { zh: "该分享链接可能已被撤销或从未存在。", en: "This share link may have been revoked or never existed." },
  share_sources: { zh: "{n} 个来源", en: "{n} sources" },
  share_model: { zh: "模型：{m}", en: "Model: {m}" },
  share_footer: { zh: "由信息平台生成", en: "Generated by Info Platform" },
  share_no_content: { zh: "暂无内容", en: "No content" },

  // Dashboard – retry & preview
  dash_retry: { zh: "重试", en: "Retry" },
  dash_retrying: { zh: "重试中…", en: "Retrying..." },
  dash_preview: { zh: "预览结果", en: "Preview results" },
  dash_hide_preview: { zh: "收起", en: "Hide" },
  dash_preview_articles: { zh: "{n} 篇文章", en: "{n} articles" },
  dash_preview_error: { zh: "抓取失败", en: "Fetch failed" },
  dash_preview_dup: { zh: "内容未变", en: "Unchanged" },
  dash_preview_loading: { zh: "加载中…", en: "Loading..." },

  // Digest detail – export
  digest_copy_md: { zh: "复制 Markdown", en: "Copy Markdown" },
  digest_copied_md: { zh: "已复制！", en: "Copied!" },
  digest_download_md: { zh: "下载 .md", en: "Download .md" },

  // Digests – infinite scroll
  digests_load_more: { zh: "加载更多", en: "Load more" },
  digests_no_more: { zh: "已全部加载", en: "All loaded" },

  // Keywords – article trend
  kw_article_trend: { zh: "近30天文章数", en: "Articles (30d)" },
  kw_no_data: { zh: "暂无数据", en: "No data" },

  // Settings – summary style
  settings_style_title: { zh: "摘要风格", en: "Summary Style" },
  settings_style_sub: { zh: "选择 LLM 生成摘要的表达方式（自定义 Prompt 时此设置不生效）", en: "Style for AI-generated summaries (ignored when custom prompt is set)" },
  settings_style_concise: { zh: "简洁 — 每点一句话", en: "Concise — one sentence per point" },
  settings_style_detailed: { zh: "详细 — 含背景与影响分析", en: "Detailed — includes context and impact" },
  settings_style_academic: { zh: "学术 — 正式语气，引用数据", en: "Academic — formal tone with data citations" },

  // Settings – prompt template
  settings_prompt_title: { zh: "自定义 Prompt", en: "Custom Prompt" },
  settings_prompt_sub: { zh: "替换默认系统提示词，留空则使用内置模板", en: "Override the default system prompt. Leave blank to use the built-in template." },
  settings_prompt_placeholder: { zh: "你是一个……（留空使用默认）", en: "You are a... (leave blank for default)" },
  settings_prompt_saved: { zh: "已保存", en: "Saved" },

  // Dashboard stats cards
  dash_stat_crawls: { zh: "本月抓取", en: "Crawls this month" },
  dash_stat_sources: { zh: "本月来源", en: "Sources this month" },
  dash_stat_tokens: { zh: "本月 Token", en: "Tokens this month" },
  dash_stat_unread: { zh: "未读摘要", en: "Unread digests" },

  // Digest feedback
  digest_feedback_positive: { zh: "有用", en: "Helpful" },
  digest_feedback_negative: { zh: "没用", en: "Not helpful" },

  // Settings – Email
  settings_email_title: { zh: "Email 通知", en: "Email Notifications" },
  settings_email_sub: { zh: "新摘要生成后发送邮件通知", en: "Send email when a new digest is ready" },
  settings_smtp_host: { zh: "SMTP 服务器", en: "SMTP Host" },
  settings_smtp_port: { zh: "端口", en: "Port" },
  settings_smtp_user: { zh: "登录账号", en: "Username" },
  settings_smtp_password: { zh: "密码", en: "Password" },
  settings_smtp_password_keep: { zh: "留空保持现有密码", en: "Leave blank to keep existing password" },
  settings_smtp_from: { zh: "发件人地址", en: "From address" },
  settings_smtp_to: { zh: "收件人地址（多个用逗号分隔）", en: "Recipient(s) — comma-separated" },
  settings_email_active: { zh: "启用邮件通知", en: "Enable email notifications" },
  settings_email_current: { zh: "当前：{host}:{port} → {to}", en: "Current: {host}:{port} → {to}" },
  settings_remove_email_confirm: { zh: "移除邮件通知配置？", en: "Remove email notification config?" },

  // Settings – next crawl
  settings_next_crawl: { zh: "下次抓取", en: "Next crawl" },
  settings_next_crawl_at: { zh: "将于 {time} 执行", en: "Scheduled for {time}" },
  settings_next_crawl_in: { zh: "（{h}h {m}m 后）", en: "（in {h}h {m}m）" },
  settings_schedule_disabled: { zh: "自动调度已禁用", en: "Auto-schedule disabled" },

  // Digest starring & mark-all-read
  digest_star: { zh: "收藏", en: "Star" },
  digest_unstar: { zh: "取消收藏", en: "Unstar" },
  digests_mark_all_read: { zh: "全部标为已读", en: "Mark all read" },
  digests_mark_all_read_confirm: { zh: "将所有摘要标为已读？", en: "Mark all digests as read?" },

  // Keywords import/export
  kw_export: { zh: "导出 JSON", en: "Export JSON" },
  kw_import: { zh: "导入 JSON", en: "Import JSON" },
  kw_import_success: { zh: "导入完成：新增 {added}，跳过 {skipped}", en: "Import done: {added} added, {skipped} skipped" },
  kw_import_error: { zh: "导入失败", en: "Import failed" },

  // Settings – RSS feed
  settings_rss_title: { zh: "RSS 订阅", en: "RSS Feed" },
  settings_rss_sub: { zh: "使用任意 RSS 阅读器订阅你的每日摘要", en: "Subscribe to your digests in any RSS reader" },
  settings_rss_copy: { zh: "复制 URL", en: "Copy URL" },
  settings_rss_copied: { zh: "已复制！", en: "Copied!" },
  settings_rss_loading: { zh: "生成中…", en: "Generating..." },

  // Settings – notification routes
  settings_routes_title: { zh: "分组路由", en: "Group Routing" },
  settings_routes_sub: { zh: "将特定分组的内容推送到独立 Webhook", en: "Route specific keyword groups to separate webhooks" },
  settings_routes_add: { zh: "添加路由", en: "Add route" },
  settings_routes_group: { zh: "分组名（留空=未分组）", en: "Group name (blank = ungrouped)" },
  settings_routes_empty: { zh: "暂无路由配置", en: "No routes configured" },
  settings_routes_delete_confirm: { zh: "删除这条路由？", en: "Delete this route?" },

  // Web Push
  settings_push_title: { zh: "移动端推送（Web Push）", en: "Web Push Notifications" },
  settings_push_sub: { zh: "在此设备上接收浏览器推送通知（需要 HTTPS）", en: "Receive push notifications on this device (requires HTTPS)" },
  settings_push_enable: { zh: "启用推送通知", en: "Enable push notifications" },
  settings_push_disable: { zh: "关闭推送通知", en: "Disable push notifications" },
  settings_push_enabling: { zh: "启用中…", en: "Enabling..." },
  settings_push_enabled: { zh: "推送已启用", en: "Push enabled" },
  settings_push_denied: { zh: "通知权限被拒绝，请在浏览器设置中允许", en: "Permission denied — allow notifications in browser settings" },
  settings_push_unsupported: { zh: "此浏览器不支持推送通知", en: "Push notifications not supported in this browser" },
  settings_push_not_configured: { zh: "服务器未配置 VAPID 密钥，暂不支持 Web Push", en: "Server VAPID keys not configured — Web Push unavailable" },

  // Export
  digest_export_obsidian: { zh: "导出到 Obsidian", en: "Open in Obsidian" },
  digest_export_notion: { zh: "导出到 Notion", en: "Export to Notion" },
  digest_exporting: { zh: "导出中…", en: "Exporting..." },
  digest_export_ok: { zh: "已导出！", en: "Exported!" },
  digest_export_err: { zh: "导出失败", en: "Export failed" },

  // Settings – Notion
  settings_notion_title: { zh: "Notion 集成", en: "Notion Integration" },
  settings_notion_sub: { zh: "将摘要导出到 Notion 数据库", en: "Export digests to a Notion database" },
  settings_notion_token: { zh: "Integration Token", en: "Integration Token" },
  settings_notion_token_keep: { zh: "留空保持现有 Token", en: "Leave blank to keep existing token" },
  settings_notion_db: { zh: "Database ID", en: "Database ID" },
  settings_notion_save: { zh: "保存 Notion 配置", en: "Save Notion config" },
  settings_notion_remove: { zh: "移除", en: "Remove" },
  settings_notion_remove_confirm: { zh: "移除 Notion 配置？", en: "Remove Notion config?" },
  settings_notion_current: { zh: "当前数据库：{db}", en: "Current database: {db}" },

  // Auth pages
  auth_login_title: { zh: "登录", en: "Sign in" },
  auth_register_title: { zh: "注册", en: "Register" },
  auth_email: { zh: "邮箱", en: "Email" },
  auth_password: { zh: "密码", en: "Password" },
  auth_display_name: { zh: "昵称（可选）", en: "Display name (optional)" },
  auth_login_btn: { zh: "登录", en: "Sign in" },
  auth_register_btn: { zh: "注册", en: "Register" },
  auth_to_register: { zh: "没有账号？注册", en: "No account? Register" },
  auth_to_login: { zh: "已有账号？登录", en: "Already have an account? Sign in" },
  auth_logging_in: { zh: "登录中…", en: "Signing in..." },
  auth_registering: { zh: "注册中…", en: "Registering..." },

  // Semantic search
  digests_semantic: { zh: "语义搜索", en: "Semantic search" },
  digests_semantic_hint: { zh: "用自然语言描述你想找的内容", en: "Describe what you're looking for in natural language" },
  digests_search_mode_text: { zh: "关键词", en: "Keyword" },
  digests_search_mode_semantic: { zh: "语义", en: "Semantic" },

  // Timeline
  digests_view_timeline: { zh: "时间线", en: "Timeline" },
  digests_timeline_empty: { zh: "该关键词近 {n} 天无摘要", en: "No digests for this keyword in the last {n} days" },
  digests_timeline_day: { zh: "{n} 条", en: "{n} digest(s)" },

  // Keyword recommendations
  kw_recommend: { zh: "智能推荐", en: "Get Recommendations" },
  kw_recommending: { zh: "推荐中…", en: "Fetching..." },
  kw_recommend_title: { zh: "推荐关键词", en: "Recommended Keywords" },
  kw_recommend_add: { zh: "添加", en: "Add" },
  kw_recommend_adding: { zh: "添加中…", en: "Adding..." },
  kw_recommend_empty: { zh: "暂无推荐", en: "No recommendations" },
  kw_recommend_close: { zh: "关闭", en: "Close" },

  // EPUB/PDF export
  digest_export_pdf: { zh: "下载 PDF", en: "Download PDF" },
  digest_export_epub: { zh: "下载 EPUB", en: "Download EPUB" },

  // Settings – embedding model
  settings_embedding_title: { zh: "向量搜索（语义搜索）", en: "Vector Search (Semantic)" },
  settings_embedding_sub: { zh: "设置 Embedding 模型后可用自然语言搜索摘要（需兼容 OpenAI Embeddings API，输出 1536 维）", en: "Set an embedding model to enable natural language digest search (requires OpenAI-compatible Embeddings API, 1536 dims)" },
  settings_embedding_model: { zh: "Embedding 模型名称（留空则禁用）", en: "Embedding model name (leave blank to disable)" },
  settings_embedding_placeholder: { zh: "如 text-embedding-3-small", en: "e.g. text-embedding-3-small" },

  // Settings – webhook type Telegram/Discord hint
  settings_telegram_hint: { zh: "URL 格式：https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}", en: "URL format: https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}" },
} satisfies Record<string, { zh: string; en: string }>;

export type TKey = keyof typeof translations;

// ── Context ──────────────────────────────────────────────────────────────────

const LangContext = createContext<{
  lang: Lang;
  toggle: () => void;
}>({ lang: "zh", toggle: () => {} });

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("zh");

  useEffect(() => {
    const saved = localStorage.getItem("lang") as Lang | null;
    if (saved === "en" || saved === "zh") setLang(saved);
  }, []);

  function toggle() {
    setLang((prev) => {
      const next = prev === "zh" ? "en" : "zh";
      localStorage.setItem("lang", next);
      return next;
    });
  }

  return <LangContext.Provider value={{ lang, toggle }}>{children}</LangContext.Provider>;
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useLang() {
  return useContext(LangContext);
}

/** Translate a key. Optionally replace {placeholder} tokens. */
export function useT() {
  const { lang } = useLang();
  return function t(key: TKey, vars?: Record<string, string | number>): string {
    let str = translations[key][lang];
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        str = str.replace(`{${k}}`, String(v));
      }
    }
    return str;
  };
}
