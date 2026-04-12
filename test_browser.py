"""
自动化浏览器测试脚本
用法: python test_browser.py
截图保存至 test_screenshots/
"""
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

BASE_URL = "http://localhost:3000"
SHOTS = Path("test_screenshots")
SHOTS.mkdir(exist_ok=True)

EMAIL = "admin@example.com"
PASSWORD = "changeme123"

step = 0
issues = []

def shot(page: Page, name: str):
    global step
    step += 1
    p = SHOTS / f"{step:02d}_{name}.png"
    page.screenshot(path=str(p), full_page=True)
    print(f"  📸 {p.name}")

def ok(msg):   print(f"  ✅ {msg}")
def warn(msg): print(f"  ⚠️  {msg}"); issues.append(msg)
def info(msg): print(f"  ℹ️  {msg}")

def login(page: Page):
    """在浏览器内直接 fetch 登录，确保 cookie 被正确设置"""
    page.goto(BASE_URL, wait_until="domcontentloaded")
    result = page.evaluate(f"""async () => {{
        const res = await fetch('/api/v1/auth/login', {{
            method: 'POST',
            credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{email: '{EMAIL}', password: '{PASSWORD}'}})
        }});
        return {{ status: res.status, ok: res.ok }};
    }}""")
    return result

def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.set_default_timeout(12000)

        # ── 1. 登录 ───────────────────────────────────────────────
        print("\n[1] 登录")
        result = login(page)
        if result["ok"]:
            ok(f"登录 API: {result['status']}")
        else:
            warn(f"登录失败: {result['status']}")
            return

        page.goto(f"{BASE_URL}/keywords", wait_until="networkidle")
        shot(page, "dashboard_after_login")
        ok(f"当前页: {page.url}")

        # ── 2. 抓取任务页 ─────────────────────────────────────────
        print("\n[2] 抓取任务页结构")
        has_kw_list  = page.query_selector('text=关键词列表') is not None
        has_kw_input = page.query_selector('text=关键词') is not None
        has_crawl    = page.query_selector('text=抓取任务') is not None
        ok(f"关键词列表: {'✓' if has_kw_list else '✗'}")
        ok(f"关键词模块: {'✓' if has_kw_input else '✗'}")
        ok(f"抓取任务模块: {'✓' if has_crawl else '✗'}")

        # ── 3. 添加关键词 ─────────────────────────────────────────
        print("\n[3] 添加关键词")
        kw_input = page.query_selector('input[placeholder*="AI"], input[placeholder*="特斯拉"]')
        if kw_input:
            kw_input.click()
            kw_input.type("人工智能")
            page.wait_for_timeout(300)
            shot(page, "keyword_typed")

            add_btn = page.query_selector('button:has-text("添加")')
            if add_btn:
                add_btn.click()
                page.wait_for_timeout(1500)
                shot(page, "keyword_added")
                if page.query_selector('text=人工智能'):
                    ok("「人工智能」已添加并显示在列表")
                else:
                    warn("添加后列表未显示「人工智能」")
            else:
                warn("未找到「添加」按钮")
        else:
            warn("未找到关键词输入框")
            shot(page, "no_kw_input")

        # 再添加一个
        print("\n[4] 添加第二个关键词「特斯拉」")
        kw_input = page.query_selector('input[placeholder*="AI"], input[placeholder*="特斯拉"]')
        if kw_input:
            kw_input.click()
            kw_input.type("特斯拉")
            add_btn = page.query_selector('button:has-text("添加")')
            if add_btn:
                add_btn.click()
                page.wait_for_timeout(1500)
                shot(page, "two_keywords")
                ok("「特斯拉」已添加")

        # ── 5. 生成分组 ───────────────────────────────────────────
        print("\n[5] 生成分组")
        group_btn = page.query_selector('button:has-text("生成分组")')
        if group_btn and group_btn.is_enabled():
            group_btn.click()
            page.wait_for_timeout(1500)
            shot(page, "group_created")
            ok("生成分组已点击")
        else:
            info("「生成分组」未启用（正常，需先有关键词）")
            shot(page, "keywords_final")

        # ── 6. 立即抓取按钮状态 ───────────────────────────────────
        print("\n[6] 检查「立即抓取」按钮")
        crawl_btn = page.query_selector('button:has-text("立即抓取")')
        if crawl_btn:
            enabled = crawl_btn.is_enabled()
            ok(f"「立即抓取」: {'可用 ✓' if enabled else '禁用（无关键词或未配置 LLM）'}")
        else:
            warn("未找到「立即抓取」按钮")

        # ── 7. 删除关键词（× 按钮）───────────────────────────────
        print("\n[7] 删除关键词")
        shot(page, "before_delete")
        close_btns = page.query_selector_all('button:has-text("×")')
        info(f"找到 × 按钮: {len(close_btns)} 个")
        if close_btns:
            close_btns[0].click()
            page.wait_for_timeout(1000)
            shot(page, "after_delete")
            ok("已点击第一个 × 删除关键词")
        else:
            all_btns = page.query_selector_all('button')
            info(f"页面所有按钮: {[b.inner_text().strip() for b in all_btns]}")

        # ── 8. 词条设置页 ─────────────────────────────────────────
        print("\n[8] 词条设置页")
        page.goto(f"{BASE_URL}/digests", wait_until="networkidle")
        shot(page, "digests_page")
        ok(f"URL: {page.url}")

        # ── 9. 系统设置页 ─────────────────────────────────────────
        print("\n[9] 系统设置页")
        page.goto(f"{BASE_URL}/settings", wait_until="networkidle")
        shot(page, "settings_page")
        ok(f"URL: {page.url}")

        for mod in ["账户", "LLM", "Webhook", "Email"]:
            found = page.query_selector(f'text={mod}') is not None
            ok(f"模块「{mod}」: {'✓' if found else '✗'}")

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(500)
        shot(page, "settings_scrolled")

        # ── 10. 管理后台 ──────────────────────────────────────────
        print("\n[10] 管理后台")
        page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
        shot(page, "admin_page")
        ok(f"URL: {page.url}")

        browser.close()

    print(f"\n{'='*55}")
    print(f"✅ 测试完成，{step} 张截图 → test_screenshots/")
    if issues:
        print(f"\n⚠️  发现 {len(issues)} 个问题:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("🎉 未发现明显问题")

if __name__ == "__main__":
    run()
