import asyncio
from urllib.parse import quote

from playwright.async_api import Browser
from rich.console import Console

from core.browser import get_page, load_session, safe_goto
from core.schemas import JobResult

console = Console()


async def search_linkedin(browser: Browser, role: str, location: str) -> list[JobResult]:
    """Search for jobs on LinkedIn using list view.
    
    Args:
        browser: Playwright browser instance
        role: Job role to search for
        location: Job location to search for
        
    Returns:
        list[JobResult]: List of job results from LinkedIn
    """
    page = await get_page(browser, "linkedin")
    jobs = []
    
    try:
        # Load session cookies
        session_loaded = await load_session(page, "linkedin")
        if not session_loaded:
            console.print("[yellow]No LinkedIn session found - will use guest access[/yellow]")
        
        # Build URL with role and location
        url = f"https://www.linkedin.com/jobs/search/?keywords={quote(role)}&location={quote(location)}"
        
        # Navigate to LinkedIn job search page
        await safe_goto(page, url, wait_for="domcontentloaded")
        await asyncio.sleep(3)
        
        # Query job cards with multiple selector fallbacks
        job_cards = await page.query_selector_all(
            ".base-card, .job-card-container, li.jobs-search-results__list-item"
        )
        job_cards = job_cards[:10]  # Limit to 10
        
        console.print(f"[cyan]Found {len(job_cards)} job cards on LinkedIn[/cyan]")
        
        # If no cards found, try guest API endpoint
        if not job_cards:
            console.print("[yellow]No cards found on main page, trying guest API endpoint...[/yellow]")
            guest_url = (
                "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                f"?keywords={quote(role)}&location={quote(location)}&start=0"
            )
            await safe_goto(page, guest_url, wait_for="domcontentloaded")
            await asyncio.sleep(2)
            job_cards = await page.query_selector_all(".base-card, .base-search-card")
            job_cards = job_cards[:10]
        
        # Extract data from each card
        for idx, card in enumerate(job_cards, 1):
            try:
                # Extract title - try multiple selectors
                title_elem = await card.query_selector(
                    ".base-search-card__title, .job-card-container__title, .job-card__title, a[data-tracking-click*='job_title']"
                )
                title = await title_elem.text_content() if title_elem else None
                title = title.strip() if title else None
                
                # If title not found, try getting it from the link text
                if not title:
                    link_elem = await card.query_selector("a")
                    if link_elem:
                        title = await link_elem.text_content()
                        title = title.strip() if title else None
                
                # For guest API, try to extract company and location from span elements
                company = None
                location = None
                
                spans = await card.query_selector_all("span")
                span_texts = []
                for span in spans[:15]:
                    text = await span.text_content()
                    text = text.strip() if text else ""
                    if text and text != title and len(text) > 2:
                        span_texts.append(text)
                
                # First non-title span is usually company, second is location
                if len(span_texts) > 0:
                    company = span_texts[0]
                if len(span_texts) > 1:
                    location = span_texts[1]
                
                # Extract URL from closest anchor tag
                url_elem = await card.query_selector(
                    "a.base-card__full-link, a.job-card-container__link, a[href*='/jobs/view/']"
                )
                if not url_elem:
                    url_elem = await card.query_selector("a")
                    
                job_url = await url_elem.get_attribute("href") if url_elem else ""
                if job_url:
                    job_url = job_url.split("?")[0]  # Remove query parameters
                
                # Skip if we have no useful data
                if not any([title, company, location, job_url]):
                    continue
                    
                # Create JobResult
                job_result = JobResult(
                    title=title or "N/A",
                    company=company or "N/A",
                    location=location or "N/A",
                    url=job_url or "",
                    tech_stack=[],
                    source="linkedin"
                )
                jobs.append(job_result)
                console.print(f"[green]✓ Job {idx}:[/green] {title or 'N/A'} | {company or 'N/A'} | {location or 'N/A'}")
                
            except Exception as e:
                console.print(f"[yellow]Error extracting job card {idx}: {e}[/yellow]")
                continue
        
        console.print(f"[green]Successfully extracted {len(jobs)} jobs from LinkedIn[/green]")
        
    except Exception as e:
        console.print(f"[red]Error searching LinkedIn: {e}[/red]")
        return []
    finally:
        await page.close()
    
    return jobs


if __name__ == "__main__":
    async def test():
        from core.browser import get_browser
        
        browser = await get_browser()
        try:
            console.print("[cyan]Testing LinkedIn job search...[/cyan]")
            results = await search_linkedin(
                browser,
                role="Software Engineer",
                location="Bangalore"
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
