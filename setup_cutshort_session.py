import asyncio, json, os
from playwright.async_api import async_playwright
from dotenv import load_dotenv
load_dotenv()

async def main():
    os.makedirs("sessions", exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(
            viewport=None,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.goto("https://cutshort.io/login", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        email = os.getenv("CUTSHORT_EMAIL")
        password = os.getenv("CUTSHORT_PASSWORD")

        # Try to auto-fill if fields exist
        try:
            await page.fill("input[type='email']", email)
            await page.fill("input[type='password']", password)
            await page.click("button[type='submit']")
        except Exception as e:
            print(f"Auto-fill failed: {e}")
            print("Please log in manually in the browser window.")

        print("Complete login/CAPTCHA manually if needed.")
        print("Waiting 60 seconds...")
        await asyncio.sleep(60)

        cookies = await context.cookies()
        with open("sessions/cutshort.json", "w") as f:
            json.dump(cookies, f, indent=2)
        print(f"Saved {len(cookies)} cookies")

        # Now go to jobs page and dump structure for debugging
        await page.goto("https://cutshort.io/jobs", wait_until="domcontentloaded")
        await asyncio.sleep(4)

        # Print all elements with 'job' in class name
        elements = await page.query_selector_all("[class*='job' i], [class*='Job']")
        print(f"\nFound {len(elements)} elements with 'job' in class name")
        for i, el in enumerate(elements[:5]):
            cls = await el.get_attribute("class")
            tag = await el.evaluate("e => e.tagName")
            text = (await el.inner_text())[:80]
            print(f"{i}: <{tag} class='{cls}'> {text}")

        input("Press ENTER to close...")
        await browser.close()

asyncio.run(main())
