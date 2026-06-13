import json
from pathlib import Path

from playwright.async_api import Browser, Page, async_playwright

SESSIONS_DIR = Path(__file__).parent.parent / "sessions"

CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


async def get_browser() -> Browser:
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=False,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    return browser


async def get_page(browser: Browser, platform: str) -> Page:
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=CHROME_USER_AGENT,
    )
    page = await context.new_page()

    cookie_file = SESSIONS_DIR / f"{platform}.json"
    if cookie_file.exists():
        with cookie_file.open("r", encoding="utf-8") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)

    return page


async def save_session(page: Page, platform: str) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    cookies = await page.context.cookies()
    cookie_file = SESSIONS_DIR / f"{platform}.json"
    with cookie_file.open("w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)
    print(f"Session saved for {platform}")


async def load_session(page: Page, platform: str) -> bool:
    cookie_file = SESSIONS_DIR / f"{platform}.json"
    if not cookie_file.exists():
        return False
    with cookie_file.open("r", encoding="utf-8") as f:
        cookies = json.load(f)
    await page.context.add_cookies(cookies)
    return True


async def is_logged_in(page: Page, selector: str) -> bool:
    try:
        await page.wait_for_selector(selector, timeout=5000)
        return True
    except Exception:
        return False


async def safe_goto(page: Page, url: str, wait_for: str = "networkidle") -> bool:
    try:
        await page.goto(url, wait_until=wait_for)
        return True
    except Exception:
        return False
