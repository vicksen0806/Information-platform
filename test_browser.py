"""
当前产品形态的端到端冒烟脚本。

覆盖范围：
- 新用户注册 / 登录
- 抓取任务页：新增词条、生成分组、删除分组、删除词条
- 系统设置页加载
- 管理员用户：创建临时抓取词条、触发抓取、等待摘要完成
- 摘要详情：分享 / 撤销分享、收藏 / 取消收藏、反馈
- 词条设置页：按词条查看历史、清空历史、同日重新抓取

运行方式：
  backend/venv/bin/python test_browser.py

可选环境变量：
  E2E_BASE_URL
  E2E_ADMIN_EMAIL
  E2E_ADMIN_PASSWORD
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import quote

from playwright.sync_api import BrowserContext, Page, expect, sync_playwright


BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
API_BASE = f"{BASE_URL}/api/v1"
ADMIN_EMAIL = os.getenv("E2E_ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("E2E_ADMIN_PASSWORD", "changeme123")
SHOTS = Path("test_screenshots")
SHOTS.mkdir(exist_ok=True)

OPENAI_RSS = "https://news.google.com/rss/search?q=OpenAI&hl=en-US&gl=US&ceid=US:en"

step = 0


class SmokeFailure(RuntimeError):
    pass


@dataclass
class CrawlOutcome:
    job_id: str
    digest_id: str | None
    digest_error: str | None


def shot(page: Page, name: str):
    global step
    step += 1
    path = SHOTS / f"{step:02d}_{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  screenshot: {path.name}")


def info(message: str):
    print(f"  info: {message}")


def ok(message: str):
    print(f"  ok: {message}")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def wait_for_http(url: str, timeout_s: int = 90):
    deadline = time.time() + timeout_s
    last_error = ""
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=5) as resp:
                if 200 <= resp.status < 500:
                    return
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    raise SmokeFailure(f"等待服务可用超时: {url} ({last_error})")


def api(page: Page, path: str, method: str = "GET", body: dict | list | None = None, ok_only: bool = True):
    result = page.evaluate(
        """async ({ path, method, body, baseUrl }) => {
          const url = path.startsWith("http://") || path.startsWith("https://")
            ? path
            : new URL(path, baseUrl).toString();
          const res = await fetch(url, {
            method,
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: body === null ? undefined : JSON.stringify(body),
          });
          const text = await res.text();
          let data = null;
          try {
            data = text ? JSON.parse(text) : null;
          } catch {
            data = text || null;
          }
          return { ok: res.ok, status: res.status, data };
        }""",
        {"path": path, "method": method, "body": body, "baseUrl": BASE_URL},
    )
    if ok_only and not result["ok"]:
        raise SmokeFailure(f"API {method} {path} failed: {result['status']} {result['data']}")
    return result


def login(page: Page, email: str, password: str):
    page.goto(BASE_URL, wait_until="domcontentloaded")
    result = api(
        page,
        "/api/v1/auth/login",
        "POST",
        {"email": email, "password": password},
    )
    if not result["ok"]:
        raise SmokeFailure(f"login failed for {email}: {result['status']}")
    ok(f"登录成功: {email}")


def register(page: Page, email: str, password: str, display_name: str):
    page.goto(BASE_URL, wait_until="domcontentloaded")
    result = api(
        page,
        "/api/v1/auth/register",
        "POST",
        {"email": email, "password": password, "display_name": display_name},
    )
    if not result["ok"]:
        raise SmokeFailure(f"register failed for {email}: {result['status']}")
    ok(f"注册成功: {email}")


def logout(page: Page):
    api(page, "/api/v1/auth/logout", "POST")
    ok("已退出登录")


def delete_keyword_if_exists(page: Page, text: str):
    keywords = api(page, "/api/v1/keywords")["data"]
    for item in keywords:
        if item["text"] == text:
            api(page, f"/api/v1/keywords/{item['id']}", "DELETE")


def create_keyword_via_api(page: Page, *, text: str, url: str, source_type: str = "rss"):
    return api(
        page,
        "/api/v1/keywords",
        "POST",
        {"text": text, "url": url, "source_type": source_type, "crawl_interval_hours": 24},
    )["data"]


def list_keyword_history(page: Page, keyword: str):
    return api(page, f"/api/v1/digests/keywords/{quote(keyword)}/history?limit=30")["data"]


def clear_keyword_history_api(page: Page, keyword: str):
    return api(page, f"/api/v1/digests/keywords/{quote(keyword)}/history", "DELETE")["data"]


def trigger_crawl_via_ui(page: Page) -> str:
    existing_jobs = api(page, f"/api/v1/crawl-jobs?limit=20&offset=0&_t={int(time.time() * 1000)}")["data"]
    existing_ids = {job["id"] for job in existing_jobs}
    page.get_by_role("button", name="立即抓取").click()
    deadline = time.time() + 20
    while time.time() < deadline:
        jobs = api(page, f"/api/v1/crawl-jobs?limit=20&offset=0&_t={int(time.time() * 1000)}")["data"]
        for job in jobs:
            if job["id"] not in existing_ids:
                return job["id"]
        time.sleep(1)
    raise SmokeFailure("未观察到新建抓取任务")


def wait_for_job_terminal(page: Page, job_id: str, timeout_s: int = 240) -> CrawlOutcome:
    deadline = time.time() + timeout_s
    last_status = ""
    while time.time() < deadline:
        job = api(page, f"/api/v1/crawl-jobs/{job_id}")["data"]
        last_status = job["status"]
        if job.get("has_digest") and job.get("digest_id"):
            return CrawlOutcome(job_id=job_id, digest_id=job["digest_id"], digest_error=job.get("digest_error"))
        if job["status"] == "failed":
            raise SmokeFailure(f"抓取任务失败: {job.get('error_message')}")
        if job["status"] == "completed" and (job.get("digest_error") or not job.get("summary_expected")):
            return CrawlOutcome(job_id=job_id, digest_id=job.get("digest_id"), digest_error=job.get("digest_error"))
        time.sleep(2)
    raise SmokeFailure(f"等待摘要完成超时，最后状态: {last_status}")


def choose_digest_for_detail(page: Page, preferred_digest_id: str | None) -> str | None:
    if preferred_digest_id:
        return preferred_digest_id

    digests = api(page, "/api/v1/digests?limit=10&offset=0")["data"]
    for item in digests:
        detail = api(page, f"/api/v1/digests/{item['id']}")["data"]
        if not detail.get("share_token"):
            return detail["id"]
    return digests[0]["id"] if digests else None


def restore_digest_state(page: Page, digest: dict):
    digest_id = digest["id"]
    latest = api(page, f"/api/v1/digests/{digest_id}")["data"]

    if bool(latest.get("is_starred")) != bool(digest.get("is_starred")):
        api(page, f"/api/v1/digests/{digest_id}/star", "DELETE" if latest.get("is_starred") else "POST")

    latest = api(page, f"/api/v1/digests/{digest_id}")["data"]
    if latest.get("feedback") != digest.get("feedback"):
        if digest.get("feedback") in {"positive", "negative"}:
            api(page, f"/api/v1/digests/{digest_id}/feedback", "PUT", {"value": digest["feedback"]})
        else:
            api(page, f"/api/v1/digests/{digest_id}/feedback", "DELETE", ok_only=False)

    latest = api(page, f"/api/v1/digests/{digest_id}")["data"]
    if bool(latest.get("share_token")) != bool(digest.get("share_token")):
        api(page, f"/api/v1/digests/{digest_id}/share", "DELETE" if latest.get("share_token") else "POST")


def exercise_digest_detail(page: Page, digest_id: str):
    original = api(page, f"/api/v1/digests/{digest_id}")["data"]
    page.goto(f"{BASE_URL}/digests/{digest_id}", wait_until="networkidle")
    expect(page.get_by_role("button", name=re.compile("收藏"))).to_be_visible()
    shot(page, f"digest_detail_{digest_id[:8]}")

    try:
        if not original.get("share_token"):
            page.get_by_role("button", name="分享").click()
            expect(page.get_by_text("公开链接")).to_be_visible()
            updated = api(page, f"/api/v1/digests/{digest_id}")["data"]
            share_token = updated.get("share_token")
            if not share_token:
                raise SmokeFailure("摘要分享后未拿到 share_token")
            shared_page = page.context.new_page()
            shared_page.goto(f"{BASE_URL}/share/{share_token}", wait_until="networkidle")
            expect(shared_page.get_by_text("信息平台")).to_be_visible()
            shot(shared_page, f"shared_digest_{digest_id[:8]}")
            shared_page.close()
            page.get_by_role("button", name="撤销分享").click()
            page.reload(wait_until="networkidle")
            expect(page.get_by_role("button", name="分享")).to_be_visible()
            ok("摘要可分享并撤销分享")
        else:
            info("跳过分享测试：该摘要原本就已共享")

        current = api(page, f"/api/v1/digests/{digest_id}")["data"]
        if current.get("is_starred"):
            page.get_by_role("button", name=re.compile("取消收藏")).click()
            expect(page.get_by_role("button", name=re.compile("收藏"))).to_be_visible()
            page.get_by_role("button", name=re.compile("收藏")).click()
        else:
            page.get_by_role("button", name=re.compile("收藏")).click()
            expect(page.get_by_role("button", name=re.compile("取消收藏"))).to_be_visible()
            page.get_by_role("button", name=re.compile("取消收藏")).click()
        ok("摘要可收藏和取消收藏")

        page.get_by_title("有用").click()
        expect(page.get_by_title("有用")).to_have_class(re.compile("text-green-600"))
        page.get_by_title("有用").click()
        expect(page.get_by_title("有用")).not_to_have_class(re.compile("text-green-600"))
        page.get_by_title("没用").click()
        expect(page.get_by_title("没用")).to_have_class(re.compile("text-red-500"))
        ok("摘要反馈可设置和取消")
    finally:
        restore_digest_state(page, original)


def run_fresh_user_flow(page: Page):
    print("\n[新用户流程]")
    ts = int(time.time())
    email = f"smoke-{ts}@example.com"
    password = "smoke-pass-123"
    keyword_a = f"smoke-ui-{ts}-a"
    keyword_b = f"smoke-ui-{ts}-b"
    group_name = f"smoke-group-{ts}"

    register(page, email, password, "Smoke Test")
    login(page, email, password)

    page.goto(f"{BASE_URL}/dashboard", wait_until="networkidle")
    expect(page.get_by_text("关键词列表")).to_be_visible()
    expect(page.locator("h1", has_text="抓取任务")).to_be_visible()
    shot(page, "fresh_user_dashboard")

    keyword_input = page.locator("form input[maxlength='200']").first
    add_button = page.get_by_role("button", name="添加")

    keyword_input.fill(keyword_a)
    add_button.click()
    expect(page.get_by_text(keyword_a)).to_be_visible()
    ok("新用户可新增第一个词条")

    keyword_input.fill(keyword_b)
    add_button.click()
    expect(page.get_by_text(keyword_b)).to_be_visible()
    ok("新用户可新增第二个词条")
    shot(page, "fresh_user_keywords_added")

    page.once("dialog", lambda dialog: dialog.accept(group_name))
    page.get_by_role("button", name="生成分组").click()
    expect(page.get_by_role("button", name=group_name, exact=True)).to_be_visible()
    ok("新用户可生成分组")

    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_label(f"删除 {group_name}").click()
    expect(page.get_by_role("button", name=group_name, exact=True)).to_have_count(0)
    ok("新用户可删除分组")

    page.get_by_label(f"删除 {keyword_a}").click()
    expect(page.get_by_text(keyword_a)).to_have_count(0)
    page.get_by_label(f"删除 {keyword_b}").click()
    expect(page.get_by_text(keyword_b)).to_have_count(0)
    ok("新用户可删除词条")

    page.goto(f"{BASE_URL}/settings", wait_until="networkidle")
    expect(page.get_by_text("LLM 配置")).to_be_visible()
    expect(page.get_by_text("推送通知")).to_be_visible()
    expect(page.get_by_text("API 用量")).to_be_visible()
    shot(page, "fresh_user_settings")

    logout(page)


def run_admin_flow(page: Page):
    print("\n[管理员核心链路]")
    ts = int(time.time())
    keyword_text = f"smoke-crawl-{ts}"
    keyword_slug = slug(keyword_text)

    login(page, ADMIN_EMAIL, ADMIN_PASSWORD)

    delete_keyword_if_exists(page, keyword_text)
    clear_keyword_history_api(page, keyword_text)

    try:
        create_keyword_via_api(page, text=keyword_text, url=OPENAI_RSS, source_type="rss")
        ok("已创建临时抓取词条")

        page.goto(f"{BASE_URL}/dashboard", wait_until="networkidle")
        expect(page.get_by_text(keyword_text)).to_be_visible()
        shot(page, f"{keyword_slug}_dashboard_ready")

        job_id = trigger_crawl_via_ui(page)
        info(f"新任务: {job_id}")
        outcome = wait_for_job_terminal(page, job_id)
        if outcome.digest_id:
            ok(f"抓取与摘要完成: {outcome.digest_id}")
        else:
            info(f"当前环境未生成新摘要：{outcome.digest_error or '无摘要输出'}")

        digest_id = choose_digest_for_detail(page, outcome.digest_id)
        if digest_id:
            exercise_digest_detail(page, digest_id)
        else:
            info("跳过摘要详情测试：当前库中没有可用摘要")

        history_before_clear = list_keyword_history(page, keyword_text)
        if not history_before_clear:
            raise SmokeFailure("新抓取后未产生词条历史，无法验证清空和重抓")

        page.goto(f"{BASE_URL}/digests?keyword={quote(keyword_text)}", wait_until="networkidle")
        expect(page.get_by_role("button", name="清空历史")).to_be_visible()
        expect(page.locator("h2", has_text=keyword_text)).to_be_visible()
        shot(page, f"{keyword_slug}_history_before_clear")

        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="清空历史").click()
        expect(page.get_by_text(f"已清空关键词「{keyword_text}」的历史记录。")).to_be_visible()
        history_after_clear = list_keyword_history(page, keyword_text)
        if history_after_clear:
            raise SmokeFailure("清空历史后仍能查到词条历史")
        ok("词条历史可清空")

        page.goto(f"{BASE_URL}/dashboard", wait_until="networkidle")
        expect(page.get_by_text(keyword_text)).to_be_visible()
        recrawl_job_id = trigger_crawl_via_ui(page)
        recrawl_outcome = wait_for_job_terminal(page, recrawl_job_id)
        if recrawl_outcome.digest_id:
            ok(f"同日重抓成功: {recrawl_outcome.digest_id}")
        else:
            info(f"同日重抓已完成，但当前环境未生成新摘要：{recrawl_outcome.digest_error or '无摘要输出'}")

        history_after_recrawl = list_keyword_history(page, keyword_text)
        if not history_after_recrawl:
            raise SmokeFailure("同日重抓后未恢复词条历史")
        ok("清空历史后同一天可重新抓取")
    finally:
        clear_keyword_history_api(page, keyword_text)
        delete_keyword_if_exists(page, keyword_text)
        logout(page)


def main():
    wait_for_http(f"{BASE_URL}/login")
    wait_for_http("http://127.0.0.1:8000/health")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 960})
        context.set_default_timeout(20000)
        page = context.new_page()
        try:
            run_fresh_user_flow(page)
            run_admin_flow(page)
        finally:
            browser.close()

    print("\n测试完成")


if __name__ == "__main__":
    main()
