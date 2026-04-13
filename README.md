# Info Platform

面向多用户的词条抓取与摘要平台。用户维护词条，手动触发抓取，系统按词条抓取内容并生成摘要，结果通过站内查看与 Webhook 推送分发。

## 当前功能

- `抓取任务`
  手动触发抓取，查看每次任务的状态、耗时和摘要入口。
- `词条设置`
  按词条查看历史记录，支持搜索词条，并可清空当前词条或一键清空全部词条历史。
- `系统设置`
  管理账户信息、界面语言、LLM 配置、Webhook 推送配置和 API 用量。
- `摘要详情`
  支持查看、分享、复制 Markdown、下载 `.md / PDF / EPUB`，以及点赞、点踩、收藏。

## 当前规则

- 抓取逻辑以“词条”为单位。
- 同一词条默认一天最多抓取一次。
- 如果当天已抓取，再次触发时会复用当天结果。
- 如果在 `词条设置` 中清空当前词条或一键清空全部词条历史，被清空的词条当天可以重新抓取。
- 删除词条配置时，不会删除该词条的历史记录；历史词条仍可重新加入后继续抓取。
- 任务耗时的统计口径是：`任务下发 -> 摘要生成完成并可查看`。
- 中文界面下，摘要会尽量输出为简体中文；原始抓取数据和来源链接不会被改写。
- 智能推荐返回的是短关键词，而不是长句或新闻标题，中文关键词应尽量控制在 2-5 个字。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 14 App Router + Tailwind CSS |
| 后端 | FastAPI |
| 数据库 | PostgreSQL |
| 队列 | Celery + Redis |
| 抓取 | requests + BeautifulSoup + readability-lxml + feedparser + Google News RSS |
| LLM | OpenAI SDK 兼容接口 |

## 本地开发

当前默认开发方式是 Mac 原生启动。

```bash
./start.sh setup   # 首次安装依赖
./start.sh         # 启动 playwright、backend、worker、frontend
./start.sh stop    # 停止应用进程
./start.sh status  # 查看状态
```

默认访问地址：

- 前端：`http://localhost:3000`
- 后端文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

默认管理员：

- 邮箱：`admin@example.com`
- 密码：`changeme123`

## 可选部署

仓库仍保留 `docker-compose.yml`，可用于容器化部署；日常开发以 `start.sh` 为准。

## 目录结构

```text
.
├── backend/
│   ├── alembic/        # 数据库迁移
│   └── app/
│       ├── models/     # 数据模型
│       ├── routers/    # API 路由
│       ├── schemas/    # Pydantic schema
│       ├── services/   # 抓取、LLM、通知等服务
│       ├── tasks/      # Celery 任务
│       └── main.py     # FastAPI 入口
├── frontend/
│   └── src/app/
│       ├── (auth)/
│       ├── (dashboard)/
│       └── share/[token]/
├── docker/
├── start.sh
├── README.md
└── CLAUDE.md
```

## 主要接口

| Method | Path | 说明 |
|---|---|---|
| GET/POST | `/api/v1/keywords` | 词条列表 / 新增词条 |
| PATCH/DELETE | `/api/v1/keywords/{id}` | 更新 / 删除词条 |
| GET/POST | `/api/v1/crawl-jobs` | 抓取任务列表 / 触发抓取 |
| GET | `/api/v1/digests/keywords` | 获取词条历史概览 |
| GET | `/api/v1/digests/keywords/{keyword}/history` | 获取单个词条历史 |
| DELETE | `/api/v1/digests/keywords/{keyword}/history` | 清空单个词条历史 |
| DELETE | `/api/v1/digests/keywords/history/all` | 一键清空全部词条历史 |
| GET | `/api/v1/digests/{id}` | 摘要详情 |
| GET | `/api/v1/digests/usage` | API 用量统计 |
| GET/PUT | `/api/v1/settings/llm` | LLM 配置 |
| GET/PUT/DELETE | `/api/v1/settings/notification` | Webhook 推送配置 |

## 文档约定

- `README.md` 面向项目使用者，描述稳定的产品形态、运行方式和接口。
- `CLAUDE.md` 面向仓库协作者，记录当前真实页面行为、开发规则和实现约束。
- 如果两者冲突，以 `CLAUDE.md` 中记录的当前实际状态为准。
