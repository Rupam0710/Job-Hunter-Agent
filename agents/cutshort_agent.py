import asyncio
from urllib.parse import quote, urljoin

from playwright.async_api import Browser, ElementHandle
from rich.console import Console

from core.browser import get_page
from core.schemas import JobResult

DEBUG = True

console = Console()

JOB_CARD_SELECTORS = [
    "[class*='JobCard']",
    "[class*='job-card']",
    "[class*='jobCard']",
    ".job-card",
    "article",
]

TITLE_SELECTORS = [
    "h2",
    "h3",
    "[class*='title']",
    "a[href*='/jobs/']",
]

COMPANY_SELECTORS = [
    "[class*='company']",
    "[class*='org']",
    "[class*='startup']",
    "span",
    "p",
]

LOCATION_SELECTORS = [
    "[class*='location']",
    "[class*='city']",
    "[class*='loc']",
    "span",
    "p",
]

LINK_SELECTORS = [
    "a[href*='/jobs/']",
    "a[href*='cutshort.io/job']",
    "a[href]",
]


async def _first_text(element: ElementHandle, selectors: list[str]) -> str | None:
    for selector in selectors:
        try:
            candidate = await element.query_selector(selector)
            if not candidate:
                continue

            text = await candidate.text_content()
            text = text.strip() if text else ""
            if text:
                return text
        except Exception:
            continue
    return None


async def _first_link(element: ElementHandle, selectors: list[str]) -> str:
    for selector in selectors:
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


async def search_cutshort(browser: Browser, role: str, location: str) -> list[JobResult]:
    page = await get_page(browser, "cutshort")
    jobs: list[JobResult] = []

    try:
        url = f"https://cutshort.io/jobs?q={quote(role)}"
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        page_content = (await page.content()) or ""
        if DEBUG:
            print("\n[DEBUG] Cutshort page content preview:")
            print(page_content[:2000])

        job_cards = []
        matched_selector = ""
        for selector in JOB_CARD_SELECTORS:
            try:
                job_cards = await page.query_selector_all(selector)
            except Exception:
                job_cards = []

            if DEBUG:
                console.print(
                    f"[cyan]Cutshort selector '{selector}' matched {len(job_cards)} cards[/cyan]"
                )

            if job_cards:
                matched_selector = selector
                break

        if DEBUG:
            if matched_selector:
                console.print(
                    f"[cyan]Using Cutshort selector '{matched_selector}' with {len(job_cards)} cards[/cyan]"
                )
            else:
                console.print("[yellow]No Cutshort job card selectors matched[/yellow]")

        for idx, card in enumerate(job_cards, 1):
            try:
                title = await _first_text(card, TITLE_SELECTORS)
                company = await _first_text(card, COMPANY_SELECTORS)
                job_location = await _first_text(card, LOCATION_SELECTORS)

                job_url = await _first_link(card, LINK_SELECTORS)
                if job_url and not job_url.startswith("http"):
                    job_url = urljoin("https://cutshort.io", job_url)

                if not any([title, company, job_location, job_url]):
                    continue

                jobs.append(
                    JobResult(
                        title=title or "N/A",
                        company=company or "N/A",
                        location=job_location or location or "N/A",
                        url=job_url,
                        tech_stack=[],
                        source="cutshort",
                    )
                )

                if DEBUG:
                    console.print(
                        f"[green]✓ Job {idx}:[/green] {title or 'N/A'} | "
                        f"{company or 'N/A'} | {job_location or location or 'N/A'}"
                    )
            except Exception as extract_err:
                if DEBUG:
                    console.print(f"[yellow]Error extracting Cutshort job card {idx}: {extract_err}[/yellow]")
                continue

        return jobs

    except Exception as search_err:
        console.print(f"[red]Cutshort search error: {search_err}[/red]")
        return []
    finally:
        await page.close()


if __name__ == "__main__":
    async def test() -> None:
        from core.browser import get_browser

        browser = await get_browser()
        try:
            console.print("[cyan]Testing Cutshort job search...[/cyan]")
            results = await search_cutshort(
                browser,
                role="Software Engineer",
                location="Bangalore",
            )

            console.print(f"\n[bold cyan]Found {len(results)} jobs:[/bold cyan]")
            for i, job in enumerate(results, 1):
                console.print(f"\n[yellow]{i}. {job.title}[/yellow]")
                console.print(f"   Company: {job.company}")
                console.print(f"   Location: {job.location}")
                console.print(f"   URL: {job.url}")
                console.print(f"   Source: {job.source}")
        finally:
            await browser.close()

    asyncio.run(test())
