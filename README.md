# Info Platform

多用户信息聚合 SaaS 平台。用户维护词条列表，系统按词条抓取内容、生成摘要，并通过站内查看、Webhook、Email 等方式分发结果。

## 当前产品形态

- `抓取任务`
  管理词条、生成分组、手动触发抓取、查看每次任务状态。
- `词条设置`
  按词条查看历史记录。每个词条每天最多抓取一次；历史内容按天展示。
- `系统设置`
  当前保留账户、LLM 配置、Webhook 通知、Email、API 用量。

## 当前关键规则

- 抓取逻辑以“词条”为基准，不再以单次批量摘要为主。
- 同一词条一天最多抓取一次。
- 如果当天已抓取，再次触发时直接复用当天内容。
- 历史页中的来源链接跟在每个小标题末尾，而不是集中显示。
- Dashboard 中可将当前词条列表整体生成分组；分组可删除，删除分组不会删除词条本身。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 14 App Router + Tailwind CSS |
| 后端 | FastAPI |
| 数据库 | PostgreSQL |
| 任务队列 | Celery + Redis |
| 抓取 | requests + BeautifulSoup + readability-lxml + feedparser |
| LLM | OpenAI SDK 兼容接口 |
| 部署 | Docker Compose |

## 本地启动

前置条件：
- Docker Desktop 已启动
- Node.js / npm 可用

```bash
# 启动后端服务
docker compose up -d

# 启动前端开发环境
cd frontend
npm install
npm run dev
```

默认访问：
- 前端：`http://localhost:3000`
- 后端文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

默认管理员：
- 邮箱：`admin@example.com`
- 密码：`changeme123`

## 目录结构

```text
.
├── backend/
│   └── app/
│       ├── models/      # 数据模型
│       ├── routers/     # API 路由
│       ├── schemas/     # Pydantic schema
│       ├── services/    # 抓取、LLM、通知等服务
│       ├── tasks/       # Celery 任务
│       └── main.py      # FastAPI 入口
├── frontend/
│   └── src/app/
│       ├── (auth)/      # 登录/注册
│       ├── (dashboard)/
│       │   ├── dashboard/
│       │   ├── digests/
│       │   └── settings/
│       └── share/[token]/
├── docker/
├── docker-compose.yml
├── README.md
└── CLAUDE.md
```

## 常用接口

| Method | Path | 说明 |
|---|---|---|
| GET/POST | `/api/v1/keywords` | 词条列表 / 新增词条 |
| GET | `/api/v1/keywords/groups` | 获取分组列表 |
| PATCH/DELETE | `/api/v1/keywords/{id}` | 更新 / 删除词条 |
| GET/POST | `/api/v1/crawl-jobs` | 抓取任务列表 / 触发抓取 |
| POST | `/api/v1/crawl-jobs/{id}/retry` | 重试失败任务 |
| GET | `/api/v1/digests/keywords` | 获取词条历史摘要列表 |
| GET | `/api/v1/digests/keywords/{keyword}/history` | 获取单个词条按天历史 |
| GET | `/api/v1/digests/{id}` | 摘要详情 |
| GET | `/api/v1/digests/usage` | API 用量统计 |
| GET/PUT | `/api/v1/settings/llm` | LLM 配置 |
| GET/PUT/DELETE | `/api/v1/settings/notification` | Webhook 通知配置 |
| GET/PUT/DELETE | `/api/v1/settings/email` | Email 配置 |

## 开发说明

- 仓库内的 `CLAUDE.md` 作为 AI 协作记忆文件维护，记录当前有效的产品规则和开发约定。
- 如果 `README.md` 与 `CLAUDE.md` 有冲突：
  - `README.md` 以稳定说明为主
  - `CLAUDE.md` 以当前开发中的真实状态为准

## 约束与注意事项

- LLM API Key 与 SMTP 密码使用 AES-256-GCM 加密存储。
- JWT 使用 httpOnly cookie，不放在 localStorage。
- FastAPI 使用异步 `asyncpg`；Celery worker 使用同步 `psycopg2`。
- 当前仍存在未完全沉淀为 Alembic migration 的数据库变更，生产部署前应补齐迁移。
