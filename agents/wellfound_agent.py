import asyncio
import json
import os
from urllib.parse import quote, urljoin

from agents.login_agent import login_wellfound
from playwright.async_api import Browser, ElementHandle
from rich.console import Console

from core.browser import get_page
from core.env import load_project_env
from core.schemas import JobResult

load_project_env()

DEBUG = True

console = Console()

JOB_CARD_SELECTORS = [
    "[data-test='JobSearchResultCard']",
    ".styles_component__",
    "div[id^='job-listing']",
    "[data-test='JobSearchCard']",
    "[data-test='job-search-card']",
    "[data-test='JobCard']",
    "[class*='JobCard']",
    "[class*='job-card']",
    "article",
]

TITLE_SELECTORS = [
    "h2",
    "h3",
    "[data-test='job-title']",
    "[class*='title']",
    "a[href*='/jobs/']",
]

COMPANY_SELECTORS = [
    "[data-test='company-name']",
    "[class*='company']",
    "[class*='startup']",
    "p",
    "span",
]

LOCATION_SELECTORS = [
    "[data-test='location']",
    "[class*='location']",
    "[class*='city']",
    "span",
    "p",
]

LINK_SELECTORS = [
    "a[href*='/jobs/']",
    "a[href]",
]


async def _first_text(element: ElementHandle, selectors: list[str]) -> str | None:
    for selector in selectors:
        try:
            candidate = await element.query_selector(selector)
            if not candidate:
                continue

            text = await candidate.text_content()
            if text:
                text = text.strip()
            if text:
                return text
        except Exception:
            continue
    return None


async def _first_link(element: ElementHandle) -> str:
    for selector in LINK_SELECTORS:
        try:
            candidate = await element.query_selector(selector)
            if not candidate:
                continue

            href = await candidate.get_attribute("href")
            if href:
                return href
        except Exception:
            continue
    return ""


async def search_wellfound(browser: Browser, role: str, location: str) -> list[JobResult]:
    jobs: list[JobResult] = []
    playwright_instance = None
    context = None

    try:
        # Launch persistent Chrome context with real browser (Cloudflare-friendly)
        from playwright.async_api import async_playwright
        
        playwright_instance = await async_playwright().start()
        context = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir="./chrome_profile_wellfound",
            headless=False,
            channel="chrome",
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        url = f"https://wellfound.com/jobs?q={quote(role)}"
        retried_after_login = False

        async def load_and_scan(current_page) -> tuple[list, str, str]:
            await current_page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(5)

            page_title = (await current_page.title()) or ""
            page_content = (await current_page.content()) or ""
            if DEBUG:
                print("\n[DEBUG] Wellfound page content preview:")
                print(page_content[:2000])

            job_cards_local = []
            for selector in JOB_CARD_SELECTORS:
                try:
                    job_cards_local = await current_page.query_selector_all(selector)
                except Exception:
                    job_cards_local = []
                if job_cards_local:
                    console.print(
                        f"[cyan]Wellfound selector matched '{selector}' with {len(job_cards_local)} cards[/cyan]"
                    )
                    break

            if DEBUG:
                console.print(f"[cyan]Wellfound selectors matched {len(job_cards_local)} job cards[/cyan]")

            return job_cards_local, page_title, page_content

        # Use persistent context page (already logged in via profile)
        job_cards, page_title, page_content = await load_and_scan(page)

        blocked = (
            "Just a moment" in page_title
            or "Cloudflare" in page_title
            or "Just a moment" in page_content
            or "Cloudflare" in page_content
        )

        if blocked or not job_cards:
            if blocked:
                console.print(
                    "[yellow]Wellfound blocked; please manually log in with the browser window that just opened.[/yellow]"
                    "[yellow]Profile persists in ./chrome_profile_wellfound for future runs.[/yellow]"
                )
            else:
                console.print(
                    "[yellow]No Wellfound job cards found; please try again or check if you're logged in.[/yellow]"
                )

        for idx, card in enumerate(job_cards, 1):
            try:
                title = await _first_text(card, TITLE_SELECTORS) or "N/A"
                company = await _first_text(card, COMPANY_SELECTORS) or "N/A"
                job_location = await _first_text(card, LOCATION_SELECTORS) or location or "N/A"

                job_url = await _first_link(card)
                if job_url and not job_url.startswith("http"):
                    job_url = urljoin("https://wellfound.com", job_url)

                if not any([title, company, job_location, job_url]):
                    continue

                jobs.append(
                    JobResult(
                        title=title,
                        company=company,
                        location=job_location,
                        url=job_url,
                        tech_stack=[],
                        source="wellfound",
                    )
                )

                if DEBUG:
                    console.print(
                        f"[green]✓ Job {idx}:[/green] {title} | {company} | {job_location}"
                    )
            except Exception as e:
                if DEBUG:
                    console.print(f"[yellow]Error extracting Wellfound job card {idx}: {e}[/yellow]")
                continue

        return jobs

    except Exception as e:
        console.print(f"[red]Wellfound search error: {e}[/red]")
        return []
    finally:
        if context:
            await context.close()
        if playwright_instance:
            await playwright_instance.stop()


if __name__ == "__main__":
    async def test() -> None:
        console.print("[cyan]Testing Wellfound job search with persistent Chrome profile...[/cyan]")
        console.print("[yellow]A browser window will open. Please log in to Wellfound if not already logged in.[/yellow]")
        
        try:
            results = await search_wellfound(None, role="Software Engineer", location="Bangalore")

            console.print(f"\n[bold cyan]Found {len(results)} jobs:[/bold cyan]")
            for i, job in enumerate(results, 1):
                console.print(f"\n[yellow]{i}. {job.title}[/yellow]")
                console.print(f"   Company: {job.company}")
                console.print(f"   Location: {job.location}")
                console.print(f"   URL: {job.url}")
                console.print(f"   Source: {job.source}")
        except Exception as e:
            console.print(f"[red]Test failed: {e}[/red]")

    asyncio.run(test())