"""
Playwright microservice — renders JS-heavy pages and returns clean HTML or PDF.
Endpoints:
  POST /render { url: str }        -> { html: str }
  POST /pdf    { html: str }       -> application/pdf bytes
"""
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from playwright.sync_api import sync_playwright

app = FastAPI(title="Playwright Render Service")


class RenderRequest(BaseModel):
    url: str


class RenderResponse(BaseModel):
    html: str


class PdfRequest(BaseModel):
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
            page.wait_for_timeout(2000)
            html = page.content()
            browser.close()
            return RenderResponse(html=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


@app.post("/pdf")
def render_pdf(req: PdfRequest):
    """Render HTML to PDF and return raw bytes."""
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.new_page()
            page.set_content(req.html, wait_until="load")
            pdf_bytes = page.pdf(
                format="A4",
                margin={"top": "20mm", "right": "20mm", "bottom": "20mm", "left": "20mm"},
                print_background=True,
            )
            browser.close()
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


@app.get("/health")
def health():
    return {"status": "ok"}
