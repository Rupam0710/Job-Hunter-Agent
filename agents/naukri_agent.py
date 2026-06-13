import asyncio

from playwright.async_api import Browser
from rich.console import Console

from core.browser import get_page, safe_goto
from core.schemas import JobResult

console = Console()


async def search_naukri(browser: Browser, role: str, location: str) -> list[JobResult]:
    """Search for jobs on Naukri using list view.
    
    Args:
        browser: Playwright browser instance
        role: Job role to search for
        location: Job location to search for
        
    Returns:
        list[JobResult]: List of job results from Naukri
    """
    page = await get_page(browser, "naukri")
    jobs = []
    
    try:
        # Build URL with role and location (lowercase, hyphenated)
        role_slug = role.lower().replace(" ", "-")
        location_slug = location.lower().replace(" ", "-")
        url = f"https://www.naukri.com/{role_slug}-jobs-in-{location_slug}"
        
        console.print(f"[cyan]Searching Naukri: {url}[/cyan]")
        
        # Navigate to Naukri job search page
        await safe_goto(page, url, wait_for="domcontentloaded")
        await asyncio.sleep(3)
        
        # Query job cards with selector fallbacks
        job_cards = await page.query_selector_all(
            ".cust-job-tuple, .srp-jobtuple-wrapper"
        )
        job_cards = job_cards[:10]  # Limit to 10
        
        console.print(f"[cyan]Found {len(job_cards)} job cards on Naukri[/cyan]")
        
        # Extract data from each card
        for idx, card in enumerate(job_cards, 1):
            try:
                # Extract title
                title_elem = await card.query_selector(".title")
                title = await title_elem.text_content() if title_elem else None
                title = title.strip() if title else None
                
                # Extract company
                company_elem = await card.query_selector(".comp-name")
                company = await company_elem.text_content() if company_elem else None
                company = company.strip() if company else None
                
                # Extract location
                location_elem = await card.query_selector(".locWdth")
                job_location = await location_elem.text_content() if location_elem else None
                job_location = job_location.strip() if job_location else None
                
                # Extract URL from title link
                url_elem = await card.query_selector("a.title")
                job_url = await url_elem.get_attribute("href") if url_elem else ""
                
                # Handle relative URLs
                if job_url and not job_url.startswith("http"):
                    job_url = f"https://www.naukri.com{job_url}"
                
                # Skip if we have no useful data
                if not any([title, company, job_location, job_url]):
                    continue
                
                # Create JobResult
                job_result = JobResult(
                    title=title or "N/A",
                    company=company or "N/A",
                    location=job_location or "N/A",
                    url=job_url or "",
                    tech_stack=[],
                    source="naukri"
                )
                jobs.append(job_result)
                console.print(f"[green]✓ Job {idx}:[/green] {title or 'N/A'} | {company or 'N/A'} | {job_location or 'N/A'}")
                
            except Exception as e:
                console.print(f"[yellow]Error extracting job card {idx}: {e}[/yellow]")
                continue
        
        console.print(f"[green]Successfully extracted {len(jobs)} jobs from Naukri[/green]")
        
    except Exception as e:
        console.print(f"[red]Error searching Naukri: {e}[/red]")
        return []
    finally:
        await page.close()
    
    return jobs


if __name__ == "__main__":
    async def test():
        from core.browser import get_browser
        
        browser = await get_browser()
        try:
            console.print("[cyan]Testing Naukri job search...[/cyan]")
            results = await search_naukri(
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
