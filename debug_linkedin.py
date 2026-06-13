import asyncio
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
load_dotenv()

async def test_linkedin():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        try:
            await page.goto("https://www.linkedin.com/login", timeout=30000)
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception as e:
            print(f"Load timeout: {e}, continuing anyway...")
        await asyncio.sleep(2)

        # Capture what's actually on screen before touching any selectors
        await page.screenshot(path="debug_screenshot.png", full_page=True)
        print(f"\nPage title : {await page.title()}")
        print(f"Page URL   : {page.url}")
        print("Screenshot saved → debug_screenshot.png\n")

        email = os.getenv("LINKEDIN_EMAIL")
        password = os.getenv("LINKEDIN_PASSWORD")
        print(f"EMAIL   : {repr(email)}")
        print(f"PASSWORD: {repr(password)}\n")

        print("\n--- EMAIL SELECTORS ---")
        email_selectors = [
            "input[name='session_key']",
            "input[autocomplete='username']",
            "input[autocomplete*='username']",
            "input[id='username']",
            "#username",
            "input[type='email']",
            "input[type='text']",
        ]
        email_filled = False
        for sel in email_selectors:
            try:
                els = await page.query_selector_all(sel)
                if not els:
                    print(f"NOT FOUND: {sel}")
                    continue
                visible_el = None
                for el in els:
                    if await el.is_visible():
                        visible_el = el
                        break
                if not visible_el:
                    print(f"FOUND x{len(els)} but all HIDDEN: {sel}")
                    continue
                print(f"FOUND + VISIBLE: {sel}")
                await visible_el.scroll_into_view_if_needed()
                await visible_el.fill(email)
                email_filled = True
                break
            except Exception as e:
                print(f"ERROR {sel}: {e}")

        print("\n--- PASSWORD SELECTORS ---")
        pwd_selectors = [
            "input[name='session_password']",
            "input[autocomplete='current-password']",
            "input[autocomplete*='current-password']",
            "input[id='password']",
            "#password",
            "input[type='password']",
        ]
        pwd_filled = False
        for sel in pwd_selectors:
            try:
                els = await page.query_selector_all(sel)
                if not els:
                    print(f"NOT FOUND: {sel}")
                    continue
                visible_el = None
                for el in els:
                    if await el.is_visible():
                        visible_el = el
                        break
                if not visible_el:
                    print(f"FOUND x{len(els)} but all HIDDEN: {sel}")
                    continue
                print(f"FOUND + VISIBLE: {sel}")
                await visible_el.scroll_into_view_if_needed()
                await visible_el.fill(password)
                pwd_filled = True
                break
            except Exception as e:
                print(f"ERROR {sel}: {e}")

        print("\n--- BUTTON SELECTORS ---")
        btn_selectors = [
            "button[type='submit']",
            "button[data-litms-control-urn]",
            ".btn__primary--large",
            "button.sign-in-form__submit-button",
            ".sign-in-form__submit-button",
            "button:has-text('Sign in')",
        ]
        btn_clicked = False
        for sel in btn_selectors:
            try:
                els = await page.query_selector_all(sel)
                if not els:
                    print(f"NOT FOUND: {sel}")
                    continue
                visible_el = None
                for el in els:
                    if not (await el.is_visible() and await el.is_enabled()):
                        continue
                    text = (await el.inner_text()).strip().lower()
                    if "microsoft" in text:
                        continue
                    if sel == "button:has-text('Sign in')" and text != "sign in":
                        continue
                    visible_el = el
                    break
                if not visible_el:
                    print(f"FOUND x{len(els)} but none visible+enabled: {sel}")
                    continue
                print(f"FOUND + VISIBLE: {sel}")
                if email_filled and pwd_filled:
                    await visible_el.scroll_into_view_if_needed()
                    await visible_el.click()
                    btn_clicked = True
                break
            except Exception as e:
                print(f"ERROR {sel}: {e}")

        if email_filled and pwd_filled and not btn_clicked:
            try:
                await page.keyboard.press("Enter")
                btn_clicked = True
                print("USED FALLBACK: Enter key")
            except Exception as e:
                print(f"ERROR Enter fallback: {e}")

        if btn_clicked:
            timeout_secs = int(os.getenv("LINKEDIN_CHECKPOINT_TIMEOUT", "120"))
            print(f"\nWaiting up to {timeout_secs}s for checkpoint approval redirect...")
            deadline = asyncio.get_event_loop().time() + timeout_secs
            while asyncio.get_event_loop().time() < deadline:
                current_url = page.url
                if "linkedin.com/feed" in current_url or "linkedin.com/in/" in current_url:
                    print(f"Login redirect detected: {current_url}")
                    break
                await asyncio.sleep(3)
            else:
                print(f"Checkpoint wait timed out. Still at: {page.url}")

        print(f"\nEmail filled: {email_filled}")
        print(f"Password filled: {pwd_filled}")
        print(f"Sign in clicked: {btn_clicked}")
        input("\nPress ENTER to close...")
        await browser.close()

asyncio.run(test_linkedin())
