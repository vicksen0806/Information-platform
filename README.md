# Info Platform

A multi-user SaaS information aggregation platform. Users configure keywords and sources; the system crawls them daily and generates AI-powered digests.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router) + Tailwind CSS |
| Backend | FastAPI (Python) |
| Database | PostgreSQL |
| Task Queue | Celery + Redis |
| Crawler | requests + BeautifulSoup + readability-lxml + feedparser |
| LLM | openai SDK (compatible with Volcengine / DeepSeek / Qwen / Zhipu / Moonshot / OpenAI) |

## Quick Start (Mac)

**Prerequisites:** Docker Desktop installed and running.

```bash
# 1. Clone and start backend services
cd Information-platform
docker compose up -d

# 2. Start frontend (separate terminal)
cd frontend
npm install
npm run dev
# Runs at http://localhost:3001 (3000 is occupied by Docker frontend container)
```

**Access:**
- Frontend: http://localhost:3001
- Backend API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

**Default admin account** (configured in `.env`):
- Email: `admin@example.com`
- Password: `changeme123`

## Features

### Core
- **Keywords** — Add topics to track (e.g. "AI", "Trump", "tplink"). Supports grouping by tag and per-keyword crawl frequency (1h / 6h / 12h / daily / 3-day / weekly).
- **Crawl Jobs** — Trigger manual crawls or let the scheduler run automatically. Full-text extraction via Mozilla Readability algorithm.
- **AI Digests** — LLM generates structured summaries per keyword with three sections: overall summary, per-keyword details (with source links), and bullet-point highlights.
- **Digest History** — Browse all past digests with full-text search and per-keyword trend filtering.
- **Public Share Links** — Generate a public read-only link for any digest; revokable at any time.

### Settings
- **LLM Configuration** — Connect any OpenAI-compatible provider (Volcengine Doubao, DeepSeek, Qwen, etc.)
- **Daily Schedule** — Choose the time and timezone for automatic daily crawls (granularity: 30 min)
- **Push Notifications** — Webhook push to Feishu, WeCom, or any generic JSON endpoint when a digest is ready
- **API Usage** — Token consumption statistics by month with breakdown chart

### Monitoring
- `GET /health` — Detailed health check: DB, Redis, and Celery worker status

## LLM Setup (Volcengine example)

| Field | Value |
|---|---|
| Provider | `volcengine` |
| Base URL | `https://ark.cn-beijing.volces.com/api/coding/v3` |
| Model | `doubao-seed-2.0-code` (or your endpoint ID) |
| API Key | UUID format from Volcengine console |

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── routers/         # FastAPI route handlers
│   │   │   └── public.py    # Unauthenticated share-link endpoint
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/        # Business logic (crawler, LLM, notifications)
│   │   ├── tasks/           # Celery tasks (crawl, digest)
│   │   ├── core/            # Auth, security, dependencies
│   │   ├── config.py        # Settings (loaded from .env)
│   │   ├── database.py      # SQLAlchemy async engine
│   │   └── main.py          # FastAPI app + lifespan + health check
│   └── requirements.txt
├── frontend/
│   └── src/app/
│       ├── (auth)/          # Login, register pages
│       ├── (dashboard)/     # Main app pages
│       │   ├── dashboard/   # Crawl job status
│       │   ├── digests/     # Digest history + detail (share button)
│       │   ├── keywords/    # Keyword management (groups + intervals)
│       │   └── settings/    # LLM, schedule, notification, usage
│       └── share/[token]/   # Public share page (no login required)
├── docker/
│   ├── Dockerfile.backend
│   └── Dockerfile.worker
├── docker-compose.yml
└── .env
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/register` | Register |
| GET/POST | `/api/v1/keywords` | List (supports `?group=`) / create keywords |
| GET | `/api/v1/keywords/groups` | List distinct group names |
| PATCH/DELETE | `/api/v1/keywords/{id}` | Update / delete keyword |
| GET/POST | `/api/v1/crawl-jobs` | List jobs / trigger crawl |
| GET | `/api/v1/crawl-jobs/{id}` | Get job status |
| GET | `/api/v1/digests` | List digests (supports `?q=` search, `?keyword=` filter) |
| GET | `/api/v1/digests/usage` | Token usage stats |
| GET | `/api/v1/digests/{id}` | Get digest detail |
| POST/DELETE | `/api/v1/digests/{id}/share` | Generate / revoke public share token |
| GET | `/api/v1/public/digests/{token}` | Public digest access (no auth) |
| GET/PUT | `/api/v1/settings/llm` | LLM config |
| POST | `/api/v1/settings/llm/test` | Test LLM connection |
| GET/PUT | `/api/v1/settings/schedule` | Daily schedule config |
| GET/PUT/DELETE | `/api/v1/settings/notification` | Webhook notification config |
| POST | `/api/v1/settings/notification/test` | Send test notification |
| GET | `/health` | Health check (DB + Redis + Celery) |

## Database Schema Notes

The following columns were added via `ALTER TABLE` (not through Alembic migrations):

```sql
-- crawl_results table
ALTER TABLE crawl_results ALTER COLUMN source_id DROP NOT NULL;
ALTER TABLE crawl_results ADD COLUMN keyword_text TEXT;

-- crawl_jobs table
ALTER TABLE crawl_jobs ADD COLUMN new_content_found BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE crawl_jobs ADD COLUMN digest_error TEXT;

-- keywords table
ALTER TABLE keywords ADD COLUMN group_name TEXT;
ALTER TABLE keywords ADD COLUMN crawl_interval_hours INTEGER NOT NULL DEFAULT 24;
ALTER TABLE keywords ADD COLUMN last_crawled_at TIMESTAMPTZ;

-- digests table
ALTER TABLE digests ADD COLUMN share_token TEXT UNIQUE;
CREATE INDEX idx_digests_share_token ON digests(share_token) WHERE share_token IS NOT NULL;
```

New tables created directly:
- `user_schedule_configs`
- `user_notification_configs`

GIN indexes for full-text search:
```sql
CREATE INDEX idx_digests_fts ON digests USING GIN (
    to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(summary_md,''))
);
CREATE INDEX idx_digests_keywords ON digests USING GIN (keywords_used);
```

**Before production deployment:** write Alembic migration files to capture all the above.

## Known Constraints

- `bcrypt==4.0.1` pinned — passlib is incompatible with 5.x
- Celery workers use synchronous `psycopg2`; FastAPI uses async `asyncpg`
- `database.py` auto-converts psycopg2 URL to asyncpg on import
- LLM API keys are AES-256-GCM encrypted at rest, never returned in plaintext
- JWT stored in httpOnly cookies (XSS-safe)
- Google News RSS is the default source when no URL is specified for a keyword
- Volcengine Coding Plan base URL: `https://ark.cn-beijing.volces.com/api/coding/v3` (not `/api/v3`)
- Feishu/WeCom return HTTP 200 even for invalid tokens — response body `code`/`errcode` must be checked
- Per-keyword `crawl_interval_hours` is checked at crawl time; `last_crawled_at` is updated after each attempt
