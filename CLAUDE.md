# 项目上下文 — Info Platform

## 项目简介
多用户 SaaS 信息聚合平台。用户配置关键词，系统定时爬取并通过 LLM 生成摘要，支持 Webhook 推送通知。
目标部署在腾讯云，用户通过浏览器访问。

## 技术栈
| 层 | 技术 |
|---|---|
| 前端 | Next.js 14 (App Router) + Tailwind CSS + @tailwindcss/typography |
| 后端 | FastAPI (Python) |
| 数据库 | PostgreSQL |
| 任务队列 | Celery + Redis |
| 爬虫 | requests + BeautifulSoup + readability-lxml + feedparser |
| LLM | openai SDK（base_url 切换，兼容火山方舟/DeepSeek/Qwen/ZhipuAI/Moonshot/OpenAI） |
| 部署 | 腾讯云 CVM + Docker Compose + Nginx |

## 当前进度（2026-04-04）
**Phase 2 + 功能扩展全部完成**，已端对端验证：
- 关键词管理（分组/标签、每关键词独立抓取频率）→ 触发抓取（全文提取 + 溯源链接）→ LLM 按关键词分组生成摘要 → 前端实时显示状态 → Webhook 推送通知
- 摘要历史（全文搜索、按关键词趋势筛选）→ 公开分享链接（无需登录访问）
- 设置页：LLM配置 + 调度时间 + 推送通知 + API用量追踪
- 健康检查：`/health` 检测 DB / Redis / Celery worker

## 启动命令
```bash
docker compose up -d          # 启动所有后端服务（需要 Docker Desktop）
cd frontend && npm run dev    # 前端开发服务器，运行在 http://localhost:3001
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
- LLM API Key 用 AES-256-GCM 加密存库，绝不明文返回
- Webhook URL 末尾含 token，`webhook_url_masked` 只返回前40字符，前端不回填原值
- JWT 存 httpOnly cookie，不存 localStorage（防 XSS）
- Celery worker 用同步 `psycopg2`，FastAPI 用异步 `asyncpg`
- `database.py` 会自动将 psycopg2 URL 转为 asyncpg
- content hash（SHA-256）去重：同一天内相同内容不重复调用 LLM
- Beat 每 30 分钟触发 `crawl_all_users`，用模运算 `% 1440` 检查每用户本地时间是否命中调度窗口（±15分钟）
- 摘要结构三段式：`## 总结` → `## 详细` → 每个关键词独立 `###` 小节，每条要点末尾附 `([来源](URL))`
- 爬虫：7个真实浏览器 UA 轮换 + Session 级自动重试（backoff 1.5x，最多3次）+ 同域名速率限制 ≥1s + readability 正文提取（失败降级 BeautifulSoup）
- 爬虫每篇文章末尾写入 `Source: {URL}`，LLM prompt 指示模型引用这些链接
- Feishu/WeCom 对无效 token 返回 HTTP 200，需检查响应体的 `code`/`errcode` 字段判断真实成败
- 每关键词 `crawl_interval_hours`（默认24）控制抓取频率，`last_crawled_at` 每次爬取后更新
- 公开分享：`share_token`（`secrets.token_urlsafe(32)`）存 digests 表，`/api/v1/public/digests/{token}` 无需认证

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

-- 新建表（直接 CREATE TABLE）
CREATE TABLE user_schedule_configs (...);
CREATE TABLE user_notification_configs (...);

-- 全文搜索 GIN 索引
CREATE INDEX idx_digests_fts ON digests USING GIN (
    to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(summary_md,''))
);
CREATE INDEX idx_digests_keywords ON digests USING GIN (keywords_used);
```

## 已修复的历史 Bug（勿重蹈）
- bcrypt 固定为 `bcrypt==4.0.1`（passlib 与 5.x 不兼容）
- `entrypoint.sh` 只写 `exec "$@"`，不要覆盖 /etc/resolv.conf
- `database.py` asyncpg engine 创建前需 `.replace("+psycopg2", "+asyncpg")`
- 火山方舟 Coding Plan Base URL 是 `/api/coding/v3`，不是 `/api/v3`
- `crawl_results.source_id` 已改为 nullable
- 调度跨天边界：用 `(current - target) % 1440` 而非 `abs()`
- Feishu/WeCom false success：检查 `body.get("code", 0) or body.get("errcode", 0)`

## 项目文件结构
```
backend/app/
├── models/
│   ├── user.py
│   ├── user_llm_config.py
│   ├── user_schedule_config.py
│   ├── user_notification_config.py
│   ├── keyword.py          # 含 group_name / crawl_interval_hours / last_crawled_at
│   ├── crawl_job.py        # 含 new_content_found / digest_error
│   ├── crawl_result.py     # 含 keyword_text
│   └── digest.py           # 含 share_token
├── routers/
│   ├── auth.py
│   ├── keywords.py         # GET /keywords?group= / GET /keywords/groups
│   ├── crawl_jobs.py       # 响应含 has_digest / digest_id / new_content_found
│   ├── digests.py          # GET ?q= ?keyword= / GET /usage / POST|DELETE /{id}/share
│   ├── public.py           # GET /public/digests/{token}（无需认证）
│   └── settings.py         # /llm + /schedule + /notification
├── services/
│   ├── crawler_service.py  # readability + UA 轮换 + 重试 + 速率限制 + Source URL 注入
│   ├── llm_service.py      # 按关键词分组 prompt，三段式 + 来源链接
│   └── notification_service.py
├── tasks/
│   ├── celery_app.py       # Beat 每30分钟
│   ├── crawl_tasks.py      # 检查 crawl_interval_hours + 更新 last_crawled_at
│   └── digest_tasks.py     # LLM 生成 + 401 处理 + Webhook 推送
└── schemas/
    ├── keyword.py          # 含 group_name / crawl_interval_hours / last_crawled_at
    ├── digest.py           # 含 share_token / UsageResponse / UsageMonthly
    ├── schedule.py
    └── notification.py

frontend/src/app/
├── (dashboard)/
│   ├── dashboard/page.tsx  # 抓取任务列表，完整状态机
│   ├── digests/page.tsx    # 历史列表 + 关键词标签筛选 + debounce 搜索
│   ├── digests/[id]/page.tsx  # 摘要详情 + Share/Revoke + Copy link
│   ├── keywords/page.tsx   # 关键词增删改 + 分组标签 + 抓取频率
│   └── settings/page.tsx   # LLM + 调度 + 推送通知 + API用量
└── share/[token]/page.tsx  # 公开分享页（无需登录）
```

## Claude 工作指引（减少 token 消耗）
- **信任本文件**：CLAUDE.md 里已有的技术决策、文件结构、Bug 记录，不需要再读源文件去确认
- **用 Grep 代替全文读取**：需要找某个函数/变量时，先 Grep 定位行号，再用 Read + offset/limit 只读相关段落
- **按需读取**：只有在要修改某个文件时才读它，不要为了"了解全貌"预先读所有文件
- **避免重复读**：同一个会话里已经读过的文件内容已在上下文中，不要再次 Read 同一路径

## 下一步任务（Phase 3）
1. **Alembic 迁移补写**（生产部署前必做）
2. **生产部署**：腾讯云 CVM + Nginx 反向代理 + docker-compose.prod.yml
3. **中文全文搜索优化**：安装 pg_jieba 插件，替换 `simple` 为中文分词配置
4. **Email 推送**：SMTP 通知渠道
5. **导出功能**：PDF 导出 / 邮件推送
