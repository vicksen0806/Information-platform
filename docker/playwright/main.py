"""
Playwright microservice — renders JS-heavy pages and returns clean HTML.
Exposes a single endpoint: POST /render { url: str } -> { html: str }
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.sync_api import sync_playwright

app = FastAPI(title="Playwright Render Service")


class RenderRequest(BaseModel):
    url: str


class RenderResponse(BaseModel):
    html: str


@app.post("/render", response_model=RenderResponse)
def render(req: RenderRequest):
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                )
            )
            page.goto(req.url, timeout=15000, wait_until="domcontentloaded")
            # Wait a bit for JS to settle
            page.wait_for_timeout(2000)
            html = page.content()
            browser.close()
            return RenderResponse(html=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


@app.get("/health")
def health():
    return {"status": "ok"}
