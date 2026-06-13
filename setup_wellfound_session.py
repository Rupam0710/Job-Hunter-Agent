import asyncio
import json
import os

from dotenv import load_dotenv
from playwright.async_api import async_playwright


load_dotenv()


async def main() -> None:
    os.makedirs("sessions", exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(
            viewport=None,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.goto("https://wellfound.com/login", wait_until="domcontentloaded")

        print("If a Cloudflare challenge appears, solve it manually.")
        print("Then log in with your email/password.")
        print("Waiting up to 180 seconds for login to complete...")

        try:
            await page.wait_for_url("**/jobs**", timeout=180000)
        except Exception:
            print("Timeout - checking current state anyway...")

        cookies = await context.cookies()
        with open("sessions/wellfound.json", "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)

        print(f"Saved {len(cookies)} cookies to sessions/wellfound.json")

        await browser.close()


asyncio.run(main())