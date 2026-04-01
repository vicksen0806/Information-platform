# 项目上下文 — 信息聚合平台

## 项目简介
多用户 SaaS 信息聚合平台。用户配置关键词和信息源 URL，系统每日定时爬取并通过 LLM 生成摘要。
目标部署在腾讯云，用户通过浏览器访问（Web SaaS，支持所有平台）。

## 技术栈
| 层 | 技术 |
|---|---|
| 前端 | Next.js 14 (App Router) + Tailwind CSS |
| 后端 | FastAPI (Python) |
| 数据库 | PostgreSQL |
| 任务队列 | Celery + Redis |
| 爬虫 | requests + BeautifulSoup（Phase 1），OpenClaw（Phase 3） |
| LLM | openai SDK（base_url 切换，兼容 DeepSeek/Qwen/ZhipuAI/Moonshot/OpenAI） |
| 部署 | 腾讯云 CVM + Docker Compose + Nginx |

## 当前进度
**Phase 1 MVP 已全部完成**，代码已写入项目目录，尚未实际运行验证。

已完成的文件：
- `backend/` — FastAPI 完整后端（模型、路由、服务、Celery 任务）
- `frontend/` — Next.js 前端（登录/注册、Dashboard、信息源、关键词、设置、摘要历史）
- `docker-compose.yml` — 本地开发完整环境
- `.env` / `.env.example` — 环境变量配置

## 下一步任务（Phase 2）
1. 实际启动验证：`docker compose up -d`，然后 `cd frontend && npm install && npm run dev`
2. 测试完整流程：注册 → Settings 填 LLM API Key → 添加信息源/关键词 → 手动抓取 → 查看摘要
3. 修复运行时 bug（Celery worker 需要 psycopg2-binary，worker 用同步 DB URL）
4. Phase 2 功能：爬取进度轮询优化、用户自定义调度时间、内容去重优化

## 关键技术决策（不要改动）
- LLM API Key 用 AES-256-GCM 加密存库，绝不明文返回
- JWT 存 httpOnly cookie，不存 localStorage（防 XSS）
- Celery worker 用同步 `psycopg2`，FastAPI 用异步 `asyncpg`（两套 DB URL）
- content hash（SHA-256）去重：相同内容不重复调用 LLM

## 启动命令
```bash
# 启动所有后端服务（需要 Docker）
docker compose up -d

# 启动前端开发服务器
cd frontend && npm install && npm run dev

# 后端 API 文档
http://localhost:8000/docs

# 前端
http://localhost:3000

# 初始管理员账号（见 .env）
# email: admin@example.com
# password: changeme123
```

## Alembic 迁移（生产环境）
```bash
cd backend
alembic revision --autogenerate -m "init"
alembic upgrade head
```
