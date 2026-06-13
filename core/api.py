import traceback

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from core.orchestrator import run_hunter
from core.schemas import JobProfile

app = FastAPI(title="JobHunterAgent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "JobHunterAgent"}


@app.post("/hunt")
async def hunt(profile: JobProfile) -> StreamingResponse:
    return StreamingResponse(
        run_hunter(profile),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/login-only")
async def login_only(profile: JobProfile) -> dict[str, object]:
    try:
        from playwright.async_api import async_playwright
        from agents.login_agent import login_all

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            results = await login_all(browser)
            await browser.close()
            return {"status": "ok", "platforms": results}
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"LOGIN ERROR: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/login-test")
async def login_test() -> dict[str, object]:
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto("https://www.google.com")
            title = await page.title()
            await browser.close()
            return {"status": "ok", "browser": "working", "title": title}
    except Exception:
        return {"status": "error", "detail": traceback.format_exc()}