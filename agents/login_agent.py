import asyncio
import os
import re

from rich.console import Console
from rich.table import Table

from core.browser import get_browser, get_page, is_logged_in, save_session
from core.env import load_project_env

os.makedirs("sessions", exist_ok=True)

load_project_env()

console = Console()


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


async def login_linkedin(browser) -> bool:
    page = await get_page(browser, "linkedin")
    try:
        try:
            await page.goto("https://www.linkedin.com/login", timeout=30000)
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception as load_err:
            console.print(f"[yellow]Load timeout, continuing: {load_err}[/yellow]")
        
        await asyncio.sleep(2)
        
        email = os.getenv("LINKEDIN_EMAIL", "")
        password = os.getenv("LINKEDIN_PASSWORD", "")

        print("EMAIL:", repr(os.getenv("LINKEDIN_EMAIL")))
        print("PASSWORD:", repr(os.getenv("LINKEDIN_PASSWORD")))
        
        if not email or not password:
            console.print("[yellow]LinkedIn credentials missing[/yellow]")
            return False

        async def fill_first_visible(selectors: list[str], value: str) -> bool:
            for selector in selectors:
                try:
                    count = await page.locator(selector).count()
                    if count == 0:
                        continue
                    locator = None
                    for i in range(count):
                        candidate = page.locator(selector).nth(i)
                        if await candidate.is_visible():
                            locator = candidate
                            break
                    if locator is None:
                        continue
                    await locator.scroll_into_view_if_needed()
                    await locator.click(timeout=2000)
                    await locator.fill(value, timeout=5000)
                    if (await locator.input_value()).strip():
                        return True
                except Exception:
                    continue
            return False

        # Use visible, interactable inputs because hidden variants are often present on LinkedIn pages.
        email_filled = await fill_first_visible(
            [
                "input[name='session_key']",
                "input[autocomplete='username']",
                "input[autocomplete*='username']",
                "#username",
                "input[type='email']",
            ],
            email,
        )
        
        if not email_filled:
            console.print("[yellow]Could not find email field[/yellow]")
            return False
        
        await asyncio.sleep(1)
        
        pwd_filled = await fill_first_visible(
            [
                "input[name='session_password']",
                "input[autocomplete='current-password']",
                "input[autocomplete*='current-password']",
                "#password",
                "input[type='password']",
            ],
            password,
        )
        
        if not pwd_filled:
            console.print("[yellow]Could not find password field[/yellow]")
            return False
        
        await asyncio.sleep(1)
        
        clicked_submit = False
        submit_selectors = [
            "button[type='submit']",
            "button.sign-in-form__submit-btn",
            "button.sign-in-form__submit-button",
            "button[aria-label='Sign in']",
            "button:has-text('Sign in')",
        ]

        for selector in submit_selectors:
            try:
                count = await page.locator(selector).count()
                if count == 0:
                    continue
                locator = None
                for i in range(count):
                    candidate = page.locator(selector).nth(i)
                    if not (await candidate.is_visible() and await candidate.is_enabled()):
                        continue
                    button_text = (await candidate.inner_text()).strip().lower()
                    if "microsoft" in button_text:
                        continue
                    if selector == "button:has-text('Sign in')" and button_text != "sign in":
                        continue
                    if selector == "button[aria-label='Sign in']" and button_text and button_text != "sign in":
                        continue
                        locator = candidate
                        break
                if locator is None:
                    continue
                await locator.scroll_into_view_if_needed()
                await locator.click(timeout=5000)
                clicked_submit = True
                break
            except Exception:
                continue

        if not clicked_submit:
            try:
                role_btn = page.get_by_role("button", name=re.compile(r"^Sign in$", re.I))
                role_count = await role_btn.count()
                for i in range(role_count):
                    candidate = role_btn.nth(i)
                    if await candidate.is_visible() and await candidate.is_enabled():
                        button_text = (await candidate.inner_text()).strip().lower()
                        if "microsoft" in button_text:
                            continue
                        await candidate.scroll_into_view_if_needed()
                        await candidate.click(timeout=5000)
                        clicked_submit = True
                        break
            except Exception:
                pass

        if not clicked_submit:
            try:
                await page.keyboard.press("Enter")
                clicked_submit = True
            except Exception:
                pass

        if not clicked_submit:
            console.print("[yellow]Could not click submit button[/yellow]")
            return False

        # LinkedIn can route to a checkpoint page that requires confirming sign-in on phone.
        checkpoint_timeout_secs = int(os.getenv("LINKEDIN_CHECKPOINT_TIMEOUT", "120"))
        login_selectors = [
            ".global-nav__me-photo",
            "img.global-nav__me-photo",
            "[data-test-global-nav-me-photo]",
            "nav.global-nav",
            "#global-nav",
        ]

        async def is_any_login_selector_visible() -> bool:
            for selector in login_selectors:
                if await is_logged_in(page, selector):
                    return True
            return False

        logged_in = await is_any_login_selector_visible()
        if not logged_in:
            checkpoint_url_part = "/checkpoint/challenges"
            if checkpoint_url_part in page.url:
                console.print(
                    "[cyan]LinkedIn checkpoint detected. Approve sign-in in your LinkedIn app; waiting for redirect...[/cyan]"
                )
            deadline = asyncio.get_event_loop().time() + checkpoint_timeout_secs
            while asyncio.get_event_loop().time() < deadline:
                if await is_any_login_selector_visible():
                    logged_in = True
                    break
                if checkpoint_url_part not in page.url and "linkedin.com/feed" in page.url:
                    logged_in = True
                    break
                await asyncio.sleep(3)

        if not logged_in:
            console.print(
                f"[yellow]LinkedIn login did not complete within {checkpoint_timeout_secs}s. Current URL: {page.url}[/yellow]"
            )

        if logged_in:
            await save_session(page, "linkedin")
        return logged_in
    except Exception as e:
        console.print(f"[red]LinkedIn login error: {e}[/red]")
        return False
    finally:
        await page.close()


async def login_naukri(browser) -> bool:
    page = await get_page(browser, "naukri")
    try:
        await page.goto("https://www.naukri.com/nlogin/login")
        await page.fill("#usernameField", os.getenv("NAUKRI_EMAIL", ""))
        await page.fill("#passwordField", os.getenv("NAUKRI_PASSWORD", ""))
        await page.click("button[type=submit]")
        await asyncio.sleep(3)
        logged_in = await is_logged_in(page, ".nI-gNb-drawer__icon")
        if logged_in:
            await save_session(page, "naukri")
        return logged_in
    except Exception as e:
        console.print(f"[red]Naukri login error: {e}[/red]")
        return False
    finally:
        await page.close()


async def login_wellfound(browser) -> bool:
    page = await get_page(browser, "wellfound")
    try:
        email = os.getenv("WELLFOUND_EMAIL", "").strip()
        password = os.getenv("WELLFOUND_PASSWORD", "").strip()

        if not email or not password:
            console.print(
                "[yellow]Wellfound credentials missing. Set WELLFOUND_EMAIL and WELLFOUND_PASSWORD in .env[/yellow]"
            )
            return False

        try:
            await page.goto("https://wellfound.com/login", wait_until="domcontentloaded", timeout=30000)
        except Exception as load_err:
            console.print(f"[yellow]Wellfound login page load issue, continuing: {load_err}[/yellow]")

        await asyncio.sleep(3)

        async def fill_first_visible(selectors: list[str], value: str) -> bool:
            for selector in selectors:
                try:
                    count = await page.locator(selector).count()
                    if count == 0:
                        continue
                    for i in range(count):
                        candidate = page.locator(selector).nth(i)
                        if not await candidate.is_visible():
                            continue
                        await candidate.scroll_into_view_if_needed()
                        await candidate.click(timeout=2000)
                        await candidate.fill(value, timeout=5000)
                        if (await candidate.input_value()).strip():
                            return True
                except Exception:
                    continue
            return False

        email_filled = await fill_first_visible(
            [
                "input[name='email']",
                "input[name='emailAddress']",
                "input[type='email']",
                "input[autocomplete='username']",
            ],
            email,
        )
        if not email_filled:
            console.print("[yellow]Could not find Wellfound email field[/yellow]")
            return False

        password_filled = await fill_first_visible(
            [
                "input[name='password']",
                "input[type='password']",
                "input[autocomplete='current-password']",
            ],
            password,
        )
        if not password_filled:
            console.print("[yellow]Could not find Wellfound password field[/yellow]")
            return False

        clicked_submit = False
        submit_selectors = [
            "button[type='submit']",
            "button:has-text('Log in')",
            "button:has-text('Sign in')",
            "input[type='submit']",
        ]
        for selector in submit_selectors:
            try:
                count = await page.locator(selector).count()
                if count == 0:
                    continue
                for i in range(count):
                    candidate = page.locator(selector).nth(i)
                    if await candidate.is_visible() and await candidate.is_enabled():
                        await candidate.scroll_into_view_if_needed()
                        await candidate.click(timeout=5000)
                        clicked_submit = True
                        break
                if clicked_submit:
                    break
            except Exception:
                continue

        if not clicked_submit:
            try:
                await page.keyboard.press("Enter")
                clicked_submit = True
            except Exception:
                pass

        if not clicked_submit:
            console.print("[yellow]Could not click Wellfound submit button[/yellow]")
            return False

        try:
            await page.wait_for_url("**/jobs**", timeout=30000)
        except Exception:
            await asyncio.sleep(5)

        page_title = (await page.title()) or ""
        page_content = (await page.content()) or ""
        if "Just a moment" in page_title or "Cloudflare" in page_title or "Just a moment" in page_content or "Cloudflare" in page_content:
            console.print("[yellow]Wellfound still appears blocked by Cloudflare after login attempt[/yellow]")

        logged_in = await is_logged_in(page, "[data-test='user-menu']") or "/jobs" in page.url
        if logged_in:
            await save_session(page, "wellfound")
        return logged_in
    except Exception as e:
        console.print(f"[red]Wellfound login error: {e}[/red]")
        return False
    finally:
        await page.close()


async def login_cutshort(browser) -> bool:
    page = await get_page(browser, "cutshort")
    try:
        await page.goto("https://cutshort.io/login")
        await page.fill("input[type=email]", os.getenv("CUTSHORT_EMAIL", ""))
        await page.fill("input[type=password]", os.getenv("CUTSHORT_PASSWORD", ""))
        await page.click("button[type=submit]")
        await asyncio.sleep(3)
        logged_in = await is_logged_in(page, ".user-avatar")
        if logged_in:
            await save_session(page, "cutshort")
        return logged_in
    except Exception as e:
        console.print(f"[red]Cutshort login error: {e}[/red]")
        return False
    finally:
        await page.close()


async def login_instahyre(browser) -> bool:
    page = await get_page(browser, "instahyre")
    try:
        await page.goto("https://www.instahyre.com/login/")

        # Reuse saved session when available.
        if await is_logged_in(page, ".profile-pic"):
            await save_session(page, "instahyre")
            return True

        use_linkedin_sso = _is_truthy(os.getenv("INSTAHYRE_USE_LINKEDIN"))

        if use_linkedin_sso:
            linkedin_selectors = [
                "button:has-text('Continue with LinkedIn')",
                "a:has-text('Continue with LinkedIn')",
                "button:has-text('Sign in with LinkedIn')",
                "a:has-text('Sign in with LinkedIn')",
                "button:has-text('LinkedIn')",
                "a:has-text('LinkedIn')",
            ]

            clicked = False
            for selector in linkedin_selectors:
                if await page.locator(selector).count() > 0:
                    await page.click(selector)
                    clicked = True
                    break

            if not clicked:
                console.print("[yellow]Instahyre LinkedIn button not found.[/yellow]")
                return False

            await asyncio.sleep(5)
        else:
            email = os.getenv("INSTAHYRE_EMAIL", "")
            password = os.getenv("INSTAHYRE_PASSWORD", "")
            if not email or not password:
                console.print(
                    "[yellow]Instahyre credentials missing. Set INSTAHYRE_EMAIL and INSTAHYRE_PASSWORD or enable INSTAHYRE_USE_LINKEDIN.[/yellow]"
                )
                return False

            await page.fill("input[name=email]", email)
            await page.fill("input[name=password]", password)
            await page.click("button[type=submit]")
            await asyncio.sleep(3)

        logged_in = await is_logged_in(page, ".profile-pic")
        if logged_in:
            await save_session(page, "instahyre")
        return logged_in
    except Exception as e:
        console.print(f"[red]Instahyre login error: {e}[/red]")
        return False
    finally:
        await page.close()


async def login_all(browser) -> dict:
    results = {}

    platforms = [
        ("linkedin", login_linkedin),
        ("naukri", login_naukri),
        ("wellfound", login_wellfound),
        ("cutshort", login_cutshort),
        ("instahyre", login_instahyre),
    ]

    for platform, login_fn in platforms:
        console.print(f"[cyan]Logging in to {platform.capitalize()}...[/cyan]")
        try:
            success = await login_fn(browser)
        except Exception as e:
            console.print(f"[red]{platform.capitalize()} login crashed: {e}[/red]")
            success = False
        results[platform] = success
        status = "[green]SUCCESS[/green]" if success else "[red]FAILED[/red]"
        console.print(f"  {platform.capitalize()}: {status}")
        await asyncio.sleep(2)

    return results


if __name__ == "__main__":
    async def main():
        browser = await get_browser()
        try:
            results = await login_all(browser)

            table = Table(title="Login Results", show_header=True, header_style="bold magenta")
            table.add_column("Platform", style="cyan", width=15)
            table.add_column("Status", width=10)

            for platform, success in results.items():
                status = "[green]✓ Logged In[/green]" if success else "[red]✗ Failed[/red]"
                table.add_row(platform.capitalize(), status)

            console.print(table)
        finally:
            await browser.close()

    asyncio.run(main())
