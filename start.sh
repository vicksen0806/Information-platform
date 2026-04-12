#!/usr/bin/env bash
# Mac 本地开发启动脚本（完全原生，无 Docker）
# 用法: ./start.sh [setup|start|stop|status]
#   首次使用: ./start.sh setup
#   日常启动: ./start.sh  （或 ./start.sh start）
#   停止应用: ./start.sh stop
#   查看状态: ./start.sh status

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"
PIDS_FILE="$SCRIPT_DIR/.dev-pids"
VENV="$SCRIPT_DIR/backend/venv"
PW_DIR="$SCRIPT_DIR/docker/playwright"

# ANSI 颜色
C_GREEN='\033[0;32m'
C_YELLOW='\033[1;33m'
C_BLUE='\033[0;34m'
C_RED='\033[0;31m'
C_BOLD='\033[1m'
C_NC='\033[0m'

log()  { echo -e "${C_BLUE}▶${C_NC} $*"; }
ok()   { echo -e "${C_GREEN}✓${C_NC} $*"; }
warn() { echo -e "${C_YELLOW}⚠${C_NC} $*"; }
fail() { echo -e "${C_RED}✗${C_NC} $*" >&2; exit 1; }

# ── Setup（首次运行）────────────────────────────────────────────
cmd_setup() {
  echo -e "${C_BOLD}首次初始化${C_NC}"
  echo ""

  # 前提条件
  log "检查前提条件..."
  command -v brew >/dev/null 2>&1 || fail "需要安装 Homebrew: https://brew.sh"
  command -v node >/dev/null 2>&1 || fail "需要安装 Node.js（brew install node）"

  # 优先使用 Python 3.11（代码使用 str | None 语法，需要 3.10+）
  PYTHON_BIN=""
  for candidate in python3.11 python3.12 python3.13 python3.10; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
  [ -z "$PYTHON_BIN" ] && fail "需要 Python 3.10+（brew install python@3.11）"
  ok "Python $($PYTHON_BIN --version | cut -d' ' -f2)"
  ok "Node $(node --version)"

  # PostgreSQL
  if ! brew list postgresql@16 >/dev/null 2>&1; then
    log "安装 PostgreSQL 16..."
    brew install postgresql@16
  fi
  brew services start postgresql@16 2>/dev/null || true
  ok "PostgreSQL 16 已启动（开机自动运行）"

  # 等待 postgres 就绪
  log "等待 PostgreSQL 就绪..."
  PG_BIN="$(brew --prefix postgresql@16)/bin"
  for i in $(seq 1 20); do
    if "$PG_BIN/pg_isready" -U "$(whoami)" >/dev/null 2>&1; then
      break
    fi
    [ "$i" -eq 20 ] && fail "PostgreSQL 启动超时"
    sleep 1
  done

  # 创建 postgres 超级用户（Homebrew 默认不创建）
  "$PG_BIN/psql" -d postgres -c \
    "CREATE ROLE postgres WITH SUPERUSER LOGIN PASSWORD 'password';" \
    2>/dev/null && ok "postgres 用户创建完成" || ok "postgres 用户已存在"

  # 创建数据库
  "$PG_BIN/createdb" infoplatform 2>/dev/null \
    && ok "数据库 infoplatform 创建完成" \
    || ok "数据库 infoplatform 已存在"

  # Redis
  if ! brew list redis >/dev/null 2>&1; then
    log "安装 Redis..."
    brew install redis
  fi
  brew services start redis 2>/dev/null || true
  ok "Redis 已启动（开机自动运行）"

  # Python 虚拟环境
  if [ ! -d "$VENV" ]; then
    log "创建 Python 虚拟环境 (backend/venv) 使用 $PYTHON_BIN..."
    "$PYTHON_BIN" -m venv "$VENV"
  fi
  ok "Python 虚拟环境就绪"

  log "安装 Python 依赖（首次较慢，约 1-2 分钟）..."
  "$VENV/bin/pip" install --upgrade pip -q
  "$VENV/bin/pip" install -r "$SCRIPT_DIR/backend/requirements.txt" -q
  # playwright 微服务依赖
  "$VENV/bin/pip" install playwright -q
  ok "Python 依赖安装完成"

  log "安装 Chromium（playwright 渲染引擎，约 150MB）..."
  "$VENV/bin/playwright" install chromium
  ok "Chromium 安装完成"

  log "安装前端依赖（npm install）..."
  cd "$SCRIPT_DIR/frontend"
  npm install --silent
  ok "前端依赖安装完成"

  # 执行数据库迁移
  log "执行数据库迁移..."
  cd "$SCRIPT_DIR/backend"
  "$VENV/bin/alembic" upgrade head 2>&1 | tail -3
  ok "数据库迁移完成"

  mkdir -p "$LOGS_DIR"

  echo ""
  echo -e "${C_BOLD}${C_GREEN}Setup 完成！${C_NC}"
  echo ""
  echo -e "  启动所有服务: ${C_BOLD}./start.sh${C_NC}"
  echo ""
}

# ── Start ──────────────────────────────────────────────────────
cmd_start() {
  [ ! -d "$VENV" ] && fail "请先运行 ./start.sh setup 完成初始化"
  mkdir -p "$LOGS_DIR"

  # 清理上次残留进程
  _stop_app_procs 2>/dev/null || true

  # 检查 postgres
  PG_BIN="$(brew --prefix postgresql@16)/bin"
  if ! "$PG_BIN/pg_isready" -U "$(whoami)" >/dev/null 2>&1; then
    log "启动 PostgreSQL..."
    brew services start postgresql@16
    sleep 2
  fi
  ok "PostgreSQL 就绪"

  # 检查 redis
  if ! redis-cli ping >/dev/null 2>&1; then
    log "启动 Redis..."
    brew services start redis
    sleep 1
  fi
  ok "Redis 就绪"

  # 数据库迁移（每次启动检查，有新迁移自动执行）
  log "检查数据库迁移..."
  cd "$SCRIPT_DIR/backend"
  "$VENV/bin/alembic" upgrade head 2>&1 | tail -2
  ok "数据库已是最新"

  # Playwright 微服务
  log "启动 Playwright 渲染服务..."
  cd "$PW_DIR"
  nohup "$VENV/bin/uvicorn" main:app \
    --host 127.0.0.1 --port 3001 \
    > "$LOGS_DIR/playwright.log" 2>&1 &
  echo $! >> "$PIDS_FILE"
  ok "Playwright 启动 → http://localhost:3001"

  # FastAPI backend
  log "启动 FastAPI backend..."
  cd "$SCRIPT_DIR/backend"
  nohup "$VENV/bin/uvicorn" app.main:app \
    --reload --host 127.0.0.1 --port 8000 \
    > "$LOGS_DIR/backend.log" 2>&1 &
  echo $! >> "$PIDS_FILE"
  ok "Backend 启动 → http://localhost:8000"

  sleep 1

  # Celery worker（本地 concurrency=1 节省内存）
  log "启动 Celery worker..."
  cd "$SCRIPT_DIR/backend"
  nohup "$VENV/bin/celery" -A app.tasks.celery_app worker \
    --loglevel=info --concurrency=1 \
    > "$LOGS_DIR/worker.log" 2>&1 &
  echo $! >> "$PIDS_FILE"
  ok "Worker 启动 (concurrency=1)"

  # Next.js frontend
  log "启动 Next.js frontend..."
  cd "$SCRIPT_DIR/frontend"
  nohup npm run dev > "$LOGS_DIR/frontend.log" 2>&1 &
  echo $! >> "$PIDS_FILE"
  ok "Frontend 启动 → http://localhost:3000"

  echo ""
  echo -e "${C_BOLD}所有服务已启动${C_NC}"
  echo ""
  echo -e "  前端:      ${C_GREEN}http://localhost:3000${C_NC}"
  echo -e "  API 文档:  ${C_GREEN}http://localhost:8000/docs${C_NC}"
  echo ""
  echo -e "  查看日志:  tail -f logs/backend.log"
  echo -e "             tail -f logs/frontend.log"
  echo -e "             tail -f logs/worker.log"
  echo ""
  echo -e "  停止服务:  ${C_YELLOW}./start.sh stop${C_NC}"
  echo -e "  ${C_YELLOW}注意：${C_NC}PostgreSQL 和 Redis 会持续在后台运行（brew services 管理）"
}

# ── Stop ───────────────────────────────────────────────────────
cmd_stop() {
  _stop_app_procs
  echo ""
  echo -e "  ${C_YELLOW}注意：${C_NC}PostgreSQL 和 Redis 保持运行（开机自启）"
  echo -e "  如需完全停止: brew services stop postgresql@16 redis"
}

_stop_app_procs() {
  if [ -f "$PIDS_FILE" ]; then
    log "停止应用进程..."
    while IFS= read -r pid; do
      kill -TERM "$pid" 2>/dev/null || true
    done < "$PIDS_FILE"
    rm -f "$PIDS_FILE"
    sleep 1
    ok "应用进程已停止"
  else
    ok "没有正在运行的应用进程"
  fi
}

# ── Status ─────────────────────────────────────────────────────
cmd_status() {
  echo -e "${C_BOLD}服务状态${C_NC}"
  echo ""

  # 基础设施
  echo -e "${C_BOLD}基础设施（brew services）:${C_NC}"
  PG_BIN="$(brew --prefix postgresql@16)/bin"
  if "$PG_BIN/pg_isready" -U "$(whoami)" >/dev/null 2>&1; then
    echo -e "  ${C_GREEN}●${C_NC} PostgreSQL 16"
  else
    echo -e "  ${C_RED}●${C_NC} PostgreSQL 16  (未运行)"
  fi
  if redis-cli ping >/dev/null 2>&1; then
    echo -e "  ${C_GREEN}●${C_NC} Redis"
  else
    echo -e "  ${C_RED}●${C_NC} Redis  (未运行)"
  fi
  echo ""

  # 应用进程
  echo -e "${C_BOLD}应用进程:${C_NC}"
  if [ -f "$PIDS_FILE" ]; then
    declare -a NAMES=("playwright" "backend (uvicorn)" "worker (celery)" "frontend (next.js)")
    i=0
    while IFS= read -r pid; do
      name="${NAMES[$i]:-process}"
      if kill -0 "$pid" 2>/dev/null; then
        echo -e "  ${C_GREEN}●${C_NC} $name  (PID $pid)"
      else
        echo -e "  ${C_RED}●${C_NC} $name  (已退出)"
      fi
      i=$((i+1))
    done < "$PIDS_FILE"
  else
    echo "  (未运行)"
  fi
  echo ""
}

# ── Main ───────────────────────────────────────────────────────
case "${1:-start}" in
  setup)  cmd_setup  ;;
  start)  cmd_start  ;;
  stop)   cmd_stop   ;;
  status) cmd_status ;;
  *)
    echo "用法: $0 [setup|start|stop|status]"
    echo ""
    echo "  setup   首次初始化（安装 postgres、redis、依赖）"
    echo "  start   启动所有服务（默认）"
    echo "  stop    停止应用进程（postgres/redis 保持运行）"
    echo "  status  查看服务状态"
    exit 1
    ;;
esac
