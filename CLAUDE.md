# 项目上下文 — 信息聚合平台

## 项目简介
多用户 SaaS 信息聚合平台。用户配置关键词和信息源，系统每日定时爬取并通过 LLM 生成摘要。
目标部署在腾讯云，用户通过浏览器访问（Web SaaS，支持所有平台）。

## 技术栈
| 层 | 技术 |
|---|---|
| 前端 | Next.js 14 (App Router) + Tailwind CSS |
| 后端 | FastAPI (Python) |
| 数据库 | PostgreSQL |
| 任务队列 | Celery + Redis |
| 爬虫 | requests + BeautifulSoup + feedparser + Google News RSS |
| LLM | openai SDK（base_url 切换，兼容火山方舟/DeepSeek/Qwen/ZhipuAI/Moonshot/OpenAI） |
| 部署 | 腾讯云 CVM + Docker Compose + Nginx |

## 当前进度（2026-04-02）
**Phase 1 MVP 已完全跑通**，完整流程已端对端验证：
注册 → LLM 配置 → 添加信息源（关键词搜索或指定 URL）→ 触发抓取 → LLM 生成摘要 → 前端显示

## 启动命令
```bash
# 启动所有后端服务（需要 Docker Desktop）
docker compose up -d

# 启动前端开发服务器（另开终端）
cd frontend
npm run dev
# 前端运行在 http://localhost:3001（3000 被 Docker frontend 容器占用）

# 后端 API 文档
http://localhost:8000/docs

# 初始管理员账号（见 .env）
# email: admin@example.com
# password: changeme123
```

## LLM 配置（用户使用火山方舟）
- Provider: `volcengine`
- Base URL: `https://ark.cn-beijing.volces.com/api/v3`（系统自动填，留空即可）
- Model: 填在线推理端点 ID，如 `ep-m-20260322064927-gvkkg`
- API Key: UUID 格式（火山方舟控制台 → API Key 管理），不是 sk- 开头

## 信息源类型
- **不限定网址（关键词搜索）**：填搜索词，系统自动用 Google News RSS 抓取
- **限定网址**：填具体网页或 RSS URL

## 关键技术决策（不要改动）
- LLM API Key 用 AES-256-GCM 加密存库，绝不明文返回
- JWT 存 httpOnly cookie，不存 localStorage（防 XSS）
- Celery worker 用同步 `psycopg2`，FastAPI 用异步 `asyncpg`
- `database.py` 会自动将 psycopg2 URL 转为 asyncpg（worker 导入 models 时安全）
- content hash（SHA-256）去重：相同内容不重复调用 LLM
- `source_type="search"` 自动构造 Google News RSS URL 存入 `url` 字段

## 已修复的历史 Bug（勿重蹈）
- bcrypt 固定为 `bcrypt==4.0.1`（passlib 与 5.x 不兼容）
- `entrypoint.sh` 只写 `exec "$@"`，不要覆盖 /etc/resolv.conf（会破坏容器间 DNS）
- `database.py` asyncpg engine 创建前需 `.replace("+psycopg2", "+asyncpg")`
- 火山方舟 API 域名是 `ark.cn-beijing.volces.com`，不是 `ark.volcengineapi.com`

## 数据库变更记录
- `sources` 表手动加了 `search_query TEXT` 列（通过 ALTER TABLE，未走 Alembic）
- 生产环境部署前需补写 Alembic 迁移文件

## 下一步任务（Phase 2）
1. 爬取进度实时轮询（前端每 5s 轮询 job 状态，显示进度条）
2. 用户自定义每日调度时间（Settings 页加时间选择器）
3. 摘要页面优化（Markdown 渲染、已读/未读状态）
4. 生产部署：腾讯云 CVM + Nginx 反向代理 + docker-compose.prod.yml
5. Phase 3：Webhook 通知（企业微信/飞书）、导出 PDF/邮件

## Alembic 迁移（生产环境部署前执行）
```bash
cd backend
alembic revision --autogenerate -m "add search_query to sources"
alembic upgrade head
```
