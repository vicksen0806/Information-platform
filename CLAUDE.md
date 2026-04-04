# 项目上下文 — Info Platform

## 项目简介
多用户 SaaS 信息聚合平台。用户配置关键词，系统定时爬取并通过 LLM 生成摘要，支持 Webhook / Email 推送通知。
目标部署在腾讯云，用户通过浏览器访问。

## 技术栈
| 层 | 技术 |
|---|---|
| 前端 | Next.js 14 (App Router) + Tailwind CSS + @tailwindcss/typography |
| 后端 | FastAPI (Python) + slowapi 限速 |
| 数据库 | PostgreSQL + pg_trgm |
| 任务队列 | Celery + Redis |
| 爬虫 | requests + BeautifulSoup + readability-lxml + feedparser |
| LLM | openai SDK（base_url 切换，兼容火山方舟/DeepSeek/Qwen/ZhipuAI/Moonshot/OpenAI） |
| 部署 | 腾讯云 CVM + Docker Compose + Nginx |

## 当前进度（2026-04-04）
**Phase 2 + Phase 2.5 + Phase 3 功能全部完成**，已端对端验证。

**Phase 2 核心功能：**
- 关键词管理（分组/标签、每关键词独立抓取频率）→ 触发抓取（全文提取 + 溯源链接）→ LLM 按关键词分组生成摘要 → 前端实时显示状态 → Webhook 推送通知
- 摘要历史（全文搜索、按关键词趋势筛选）→ 公开分享链接（无需登录访问）
- 设置页：LLM配置 + 调度时间 + 推送通知 + API用量追踪
- 健康检查：`/health` 检测 DB / Redis / Celery worker
- 多语言切换（中文/英文，持久化到 localStorage）

**Phase 2.5 新增功能：**
- 失败任务一键重试（`POST /crawl-jobs/{id}/retry` 创建新任务）
- 抓取结果预览（Dashboard 可展开查看每个关键词的文章数 + 状态）
- 摘要列表无限滚动（IntersectionObserver + offset 分页，每页20条）
- 摘要导出：复制 Markdown / 下载 `.md` 文件
- 自定义 Prompt 模板（设置页 LLM 配置区，存 `user_llm_configs.prompt_template`）
- 关键词文章量趋势图（每个关键词下方显示近30天 sparkline，用 `regexp_count` 统计实际文章数）
- 摘要趋势视图加载全量数据（切换趋势视图时最多加载500条，不依赖分页状态）
- 摘要详情页溯源链接在新标签页打开（`target="_blank"`）

**Phase 3 新增功能：**
- API 限速（slowapi：登录 10次/分钟，注册 5次/分钟）
- Dashboard 统计卡片（本月抓取次数 / 文章数 / Token 用量 / 未读摘要）
- Email SMTP 推送（`user_email_configs` 表，密码 AES-GCM 加密）
- 摘要质量反馈 👍/👎（`digest_feedbacks` 表，PUT/DELETE `/digests/{id}/feedback`）
- 跨关键词 URL 去重（`_filter_seen_articles`，同 job 内相同 Source URL 只处理一次）
- 下次抓取倒计时（`GET /settings/schedule/next-crawl`，设置页实时显示）
- LLM Prompt 分组感知（`has_groups → 【分组：X】` 二级标题，自动适配）
- pg_trgm 中文搜索加速（`gin_trgm_ops` 索引，startup 自动建）
- 关键词活跃度自动调整（连续5次空结果 → 4× crawl_interval_hours，最大168h，不改库存值）
- 摘要全部标为已读（`POST /digests/mark-all-read`，批量 UPDATE）
- 抓取失败告警（连续3次真实错误 → Webhook + Email 告警，`_check_and_alert_failures`）
- Webhook 重试（`_send_with_retry`，30s / 60s exponential backoff，最多3次）
- 摘要收藏 ★（`digest_stars` 表，`POST/DELETE /digests/{id}/star`，列表常驻显示已收藏）
- 分组 Webhook 路由（`notification_routes` 表，设置页 CRUD，生成摘要时按 group_name 分发）
- RSS Feed（`GET /api/v1/public/feed/{token}.rss`，RSS 2.0，HMAC-SHA256 令牌认证，无需登录）
- 关键词 JSON 导入/导出（`GET /keywords/export`、`POST /keywords/import`，跳过重复）
- 登录/注册页 UI 重设计（左侧品牌面板 + 右侧表单分屏布局）

## 启动命令
```bash
docker compose up -d          # 启动所有后端服务（需要 Docker Desktop）
cd frontend && npm run dev    # 前端开发服务器，运行在 http://localhost:3000
# 后端 API 文档: http://localhost:8000/docs
# 健康检查: http://localhost:8000/health
# 初始管理员: admin@example.com / changeme123
```

## LLM 配置（火山方舟 Coding Plan）
- Provider: `volcengine`
- Base URL: `https://ark.cn-beijing.volces.com/api/coding/v3`（注意是 /coding/v3，不是 /v3）
- Model: `doubao-seed-2.0-code`
- API Key: UUID 格式

## 信息源类型
- **不限定网址**：Google News RSS 自动抓取，RSS 条目跟进文章链接提取全文
- **限定网址**：具体网页（readability 提取）或 RSS URL（跟进每篇文章全文）

## 关键技术决策（不要改动）
- LLM API Key 用 AES-256-GCM 加密存库，绝不明文返回；SMTP 密码同样加密
- Webhook URL 末尾含 token，`webhook_url_masked` 只返回前40字符，前端不回填原值
- JWT 存 httpOnly cookie，不存 localStorage（防 XSS）
- Celery worker 用同步 `psycopg2`，FastAPI 用异步 `asyncpg`
- `database.py` 会自动将 psycopg2 URL 转为 asyncpg
- content hash（SHA-256）去重：同一天内相同内容不重复调用 LLM
- Beat 每 30 分钟触发 `crawl_all_users`，用模运算 `% 1440` 检查每用户本地时间是否命中调度窗口（±15分钟）
- 摘要结构三段式：`## 总结` → `## 详细` → 每个关键词独立 `###` 小节，每条要点末尾附 `([来源](URL))`
- 分组摘要：当存在 group_name 时，`## 详细` 下先用 `## 分组名` 再用 `### 关键词`
- 爬虫：7个真实浏览器 UA 轮换 + Session 级自动重试（backoff 1.5x，最多3次）+ 同域名速率限制 ≥1s + readability 正文提取（失败降级 BeautifulSoup）
- 爬虫每篇文章末尾写入 `Source: {URL}`，LLM prompt 指示模型引用这些链接
- Feishu/WeCom 对无效 token 返回 HTTP 200，需检查响应体的 `code`/`errcode` 字段判断真实成败
- 每关键词 `crawl_interval_hours`（默认24）控制抓取频率；连续5次空结果自动用 4× 有效间隔（内存计算，不写库）
- 公开分享：`share_token`（`secrets.token_urlsafe(32)`）存 digests 表，`/api/v1/public/digests/{token}` 无需认证
- RSS Feed 令牌：`{user_id.hex}{hmac_sha256(SECRET_KEY, user_id.bytes)[:16]}`（共48字符）；`_verify_feed_token` 在 public.py 中验证
- 自定义 Prompt：`user_llm_configs.prompt_template`（VARCHAR 4000），为空则用内置三段式模板，`llm_service.py` 中判断
- 关键词文章数统计：`/keywords/article-stats` 用 PostgreSQL `regexp_count(raw_content, '## ')` 统计文章数（不是 crawl result 行数）
- 爬虫 URL 解析：`_fetch_article` 返回 `(text, resolved_url)` tuple，`resp.url` 获取重定向后的真实 URL（解决 Google News 短链）
- 跨关键词去重：`_filter_seen_articles` 按 `Source: URL` 在同一 job 内去重，过滤后为空则整条结果标为 "All articles duplicated"
- 分组 Webhook 路由：`notification_routes` 表按 `group_name` 匹配，在 `digest_tasks.py` 的 `generate_digest` 末尾分发；全局 webhook 仍发完整摘要
- Webhook 重试：`_send_with_retry(send_fn, config, keywords, summary, created_at, max_attempts=3)`，第1次重试等30s，第2次等60s
- 失败告警：`_check_and_alert_failures` 在每次 crawl job 结束后调用，过滤掉 "Content unchanged" 和 "All articles duplicated" 的伪错误

## 数据库变更记录（未走 Alembic，生产部署前需补写迁移）
```sql
-- crawl_results 表
ALTER TABLE crawl_results ALTER COLUMN source_id DROP NOT NULL;
ALTER TABLE crawl_results ADD COLUMN keyword_text TEXT;

-- crawl_jobs 表
ALTER TABLE crawl_jobs ADD COLUMN new_content_found BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE crawl_jobs ADD COLUMN digest_error TEXT;

-- keywords 表
ALTER TABLE keywords ADD COLUMN group_name TEXT;
ALTER TABLE keywords ADD COLUMN crawl_interval_hours INTEGER NOT NULL DEFAULT 24;
ALTER TABLE keywords ADD COLUMN last_crawled_at TIMESTAMPTZ;

-- digests 表
ALTER TABLE digests ADD COLUMN share_token TEXT UNIQUE;
CREATE INDEX idx_digests_share_token ON digests(share_token) WHERE share_token IS NOT NULL;

-- user_llm_configs 表（Phase 2.5 新增）
ALTER TABLE user_llm_configs ADD COLUMN prompt_template TEXT;

-- 新建表（Phase 2.5，直接 CREATE TABLE）
CREATE TABLE user_schedule_configs (...);
CREATE TABLE user_notification_configs (...);

-- 全文搜索 GIN 索引
CREATE INDEX idx_digests_fts ON digests USING GIN (
    to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(summary_md,''))
);
CREATE INDEX idx_digests_keywords ON digests USING GIN (keywords_used);

-- Phase 3 新增表（dev 环境由 create_all 自动建，生产需补 Alembic）
CREATE TABLE user_email_configs (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    smtp_host VARCHAR(255) NOT NULL,
    smtp_port INTEGER NOT NULL DEFAULT 465,
    smtp_user VARCHAR(255) NOT NULL,
    smtp_password_enc TEXT NOT NULL,
    smtp_from VARCHAR(255) NOT NULL,
    smtp_to TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE digest_feedbacks (
    id UUID PRIMARY KEY,
    digest_id UUID NOT NULL REFERENCES digests(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    value VARCHAR(20) NOT NULL,  -- 'positive' | 'negative'
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(digest_id, user_id)
);

CREATE TABLE digest_stars (
    id UUID PRIMARY KEY,
    digest_id UUID NOT NULL REFERENCES digests(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_digest_star UNIQUE(user_id, digest_id)
);

CREATE TABLE notification_routes (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_name VARCHAR(100),         -- NULL = 未分组关键词
    webhook_url TEXT NOT NULL,
    webhook_type VARCHAR(30) NOT NULL DEFAULT 'generic',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_notification_routes_user ON notification_routes(user_id);

-- Phase 3 pg_trgm 索引（startup 自动建）
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_digests_title_trgm ON digests USING GIN (title gin_trgm_ops);
CREATE INDEX idx_digests_summary_trgm ON digests USING GIN (summary_md gin_trgm_ops);
```

## 已修复的历史 Bug（勿重蹈）
- bcrypt 固定为 `bcrypt==4.0.1`（passlib 与 5.x 不兼容）
- `entrypoint.sh` 只写 `exec "$@"`，不要覆盖 /etc/resolv.conf
- `database.py` asyncpg engine 创建前需 `.replace("+psycopg2", "+asyncpg")`
- 火山方舟 Coding Plan Base URL 是 `/api/coding/v3`，不是 `/api/v3`
- `crawl_results.source_id` 已改为 nullable
- 调度跨天边界：用 `(current - target) % 1440` 而非 `abs()`
- Feishu/WeCom false success：检查 `body.get("code", 0) or body.get("errcode", 0)`
- SQLAlchemy mapper 初始化失败：`models/__init__.py` 必须显式 import 所有新模型（UserScheduleConfig、UserNotificationConfig、UserEmailConfig、DigestFeedback、DigestStar、NotificationRoute），否则 Celery worker 启动时 mapper 报错
- `crawl-jobs/{id}/results` 不能 JOIN Source 表（source_id nullable），需直接查 CrawlResult
- `.next` 缓存污染：修改 webpack 相关配置后需 `rm -rf .next` 再重启
- 关键词文章数统计不能用 `COUNT(id)`（只统计抓取次数），要用 `regexp_count(raw_content, '## ')` 统计实际文章头数
- `POST /digests/mark-all-read` 必须定义在 `GET /{digest_id}` 之前，否则 FastAPI 路由冲突（同理 `/export`、`/import` 在 `/{id}` 之前）

## 项目文件结构
```
backend/app/
├── models/
│   ├── user.py                      # 含 email_config / notification_routes relationship
│   ├── user_llm_config.py           # 含 prompt_template
│   ├── user_schedule_config.py
│   ├── user_notification_config.py
│   ├── user_email_config.py         # SMTP 配置（Phase 3）
│   ├── keyword.py                   # 含 group_name / crawl_interval_hours / last_crawled_at
│   ├── crawl_job.py                 # 含 new_content_found / digest_error
│   ├── crawl_result.py              # 含 keyword_text（source_id nullable）
│   ├── digest.py                    # 含 share_token
│   ├── digest_feedback.py           # 👍/👎（Phase 3）
│   ├── digest_star.py               # 收藏（Phase 3）
│   └── notification_route.py        # 分组路由（Phase 3）
├── routers/
│   ├── auth.py                      # 含 slowapi 限速（登录10/min，注册5/min）
│   ├── keywords.py                  # GET /export / POST /import / GET /groups / GET /article-stats
│   ├── crawl_jobs.py                # 含 POST /{id}/retry / GET /{id}/results
│   ├── digests.py                   # POST /mark-all-read / GET /usage / POST|DELETE /{id}/star|share|feedback
│   ├── public.py                    # GET /public/digests/{token} / GET /public/feed/{token}.rss
│   ├── settings.py                  # /llm / /schedule / /notification / /email / /feed-token / /notification-routes
│   └── stats.py                     # GET /stats（Dashboard 统计卡片）
├── services/
│   ├── crawler_service.py           # readability + UA 轮换 + 重试 + 速率限制 + Source URL 注入 + resolved_url
│   ├── llm_service.py               # 分组感知 prompt（has_groups）+ 来源链接 + 自定义 prompt_template
│   └── notification_service.py      # Feishu / WeCom / Generic + SMTP email
├── tasks/
│   ├── celery_app.py                # Beat 每30分钟
│   ├── crawl_tasks.py               # crawl_interval_hours + 活跃度自动调整 + _check_and_alert_failures
│   └── digest_tasks.py              # LLM 生成 + 401 处理 + _send_with_retry + 分组路由分发
└── schemas/
    ├── keyword.py                   # 含 group_name / crawl_interval_hours / last_crawled_at
    ├── digest.py                    # 含 share_token / is_starred / UsageResponse
    ├── llm_config.py                # 含 prompt_template
    ├── schedule.py
    ├── notification.py              # 含 NotificationRouteCreate / NotificationRouteResponse
    └── email_config.py

frontend/src/app/
├── (auth)/
│   ├── login/page.tsx               # 分屏布局（左侧品牌 + 右侧表单）
│   └── register/page.tsx            # 分屏布局
├── (dashboard)/
│   ├── dashboard/page.tsx           # 统计卡片 + 任务列表 + 状态机 + 重试 + 结果预览
│   ├── digests/page.tsx             # 列表（收藏★ + 反馈👍👎）+ 全部已读 + 搜索 + 趋势视图
│   ├── digests/[id]/page.tsx        # 摘要详情 + 收藏 + Share + 导出 + 反馈
│   ├── keywords/page.tsx            # 增删改 + 分组 + 抓取频率 + sparkline + 导入/导出JSON
│   └── settings/page.tsx            # 账户 + LLM + 调度 + 推送 + Email + RSS订阅 + 分组路由 + 用量
└── share/[token]/page.tsx           # 公开分享页（无需登录）

frontend/src/lib/
├── api.ts       # 所有 API 调用 + 类型定义（含 FeedTokenInfo / NotificationRoute / KeywordExportItem）
└── i18n.tsx     # 中英双语，React Context + localStorage 持久化
```

## Claude 工作指引（减少 token 消耗）
- **信任本文件**：CLAUDE.md 里已有的技术决策、文件结构、Bug 记录，不需要再读源文件去确认
- **用 Grep 代替全文读取**：需要找某个函数/变量时，先 Grep 定位行号，再用 Read + offset/limit 只读相关段落
- **按需读取**：只有在要修改某个文件时才读它，不要为了"了解全貌"预先读所有文件
- **避免重复读**：同一个会话里已经读过的文件内容已在上下文中，不要再次 Read 同一路径

## 下一步任务（剩余）

### 生产就绪（优先）
1. **Alembic 迁移补写**（生产部署前必做——Phase 3 新增了4张表，全部需要迁移文件）
2. **生产部署**：腾讯云 CVM + Nginx 反向代理 + docker-compose.prod.yml

### 功能扩展
3. **管理员用户管理页**：`/admin` 页面，查看所有用户、禁用账户（`is_admin` 字段已有）
4. **中文全文搜索优化**：安装 pg_jieba 插件，替换 `simple` 分词配置
