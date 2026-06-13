import asyncio
from urllib.parse import quote

from playwright.async_api import Browser, Page
from rich.console import Console

from core.browser import get_page, load_session, safe_goto
from core.schemas import JobProfile, JobResult

console = Console()


async def search_linkedin(browser: Browser, profile: JobProfile) -> list[JobResult]:
    """Search for jobs on LinkedIn."""
    page = await get_page(browser, "linkedin")
    jobs = []
    
    try:
        # Load session
        await load_session(page, "linkedin")
        
        # Build URL with role and location
        url = f"https://www.linkedin.com/jobs/search/?keywords={quote(profile.role)}&location={quote(profile.location)}"
        
        # Navigate to primary LinkedIn jobs page; continue with fallbacks if this fails.
        primary_loaded = await safe_goto(page, url, wait_for="domcontentloaded")
        if not primary_loaded:
            console.print("[yellow]Primary LinkedIn jobs page failed; trying guest fallback[/yellow]")
        
        # Wait for a jobs list container to appear.
        list_selectors = [
            ".jobs-search__results-list",
            ".scaffold-layout__list-container",
            "ul.jobs-search__results-list",
            "main:has(a[href*='/jobs/view/'])",
        ]
        list_ready = False
        for selector in list_selectors:
            try:
                await page.wait_for_selector(selector, timeout=5000)
                list_ready = True
                break
            except Exception:
                continue

        if not list_ready:
            console.print("[yellow]No LinkedIn job list container found on primary page; trying guest fallback[/yellow]")
        
        # Extract job links from primary card selectors, then generic anchors fallback.
        job_elements = await page.query_selector_all(
            ".base-card, .job-card-container, li.jobs-search-results__list-item"
        )
        job_urls = []
        
        for idx, element in enumerate(job_elements[:10]):
            try:
                link = await element.query_selector(
                    "a.base-card__full-link, a.job-card-container__link, a[href*='/jobs/view/']"
                )
                if link:
                    job_url = await link.get_attribute("href")
                    if job_url:
                        job_urls.append(job_url.split("?")[0])
            except:
                continue

        if not job_urls:
            anchors = await page.query_selector_all("a[href*='/jobs/view/']")
            for anchor in anchors[:20]:
                try:
                    job_url = await anchor.get_attribute("href")
                    if job_url:
                        job_urls.append(job_url.split("?")[0])
                except Exception:
                    continue

        if not job_urls:
            guest_url = (
                "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                f"?keywords={quote(profile.role)}&location={quote(profile.location)}&start=0"
            )
            if await safe_goto(page, guest_url, wait_for="domcontentloaded"):
                guest_cards = await page.query_selector_all(".base-card, .base-search-card")
                for card in guest_cards[:20]:
                    try:
                        link = await card.query_selector("a.base-card__full-link, a.base-search-card__full-link")
                        if not link:
                            continue
                        job_url = await link.get_attribute("href")
                        if job_url:
                            job_urls.append(job_url.split("?")[0])
                    except Exception:
                        continue

        # Deduplicate while preserving order.
        deduped_urls = []
        seen = set()
        for url_item in job_urls:
            if not url_item or url_item in seen:
                continue
            seen.add(url_item)
            deduped_urls.append(url_item)
        job_urls = deduped_urls[:10]
        
        # Extract job details
        for job_url in job_urls:
            try:
                job_page = await get_page(browser, "linkedin")
                await load_session(job_page, "linkedin")
                
                if not await safe_goto(job_page, job_url):
                    await job_page.close()
                    continue
                
                # Extract job details with selector fallbacks for changing LinkedIn DOM.
                title = "N/A"
                for selector in [
                    ".jobs-details-main-section h1",
                    "h1.top-card-layout__title",
                    "h1.t-24",
                    "h1",
                ]:
                    try:
                        text = await job_page.locator(selector).first.inner_text(timeout=3000)
                        if text and text.strip():
                            title = text.strip()
                            break
                    except Exception:
                        continue

                company = "N/A"
                for selector in [
                    ".jobs-details__main-content .orgName",
                    ".job-details-jobs-unified-top-card__company-name a",
                    ".topcard__org-name-link",
                    "a.topcard__org-name-link",
                ]:
                    try:
                        text = await job_page.locator(selector).first.inner_text(timeout=3000)
                        if text and text.strip():
                            company = text.strip()
                            break
                    except Exception:
                        continue

                location = profile.location
                for selector in [
                    ".jobs-details__main-content .job-details-jobs-unified-top-card__location-without-icon",
                    ".job-details-jobs-unified-top-card__bullet",
                    ".topcard__flavor.topcard__flavor--bullet",
                ]:
                    try:
                        text = await job_page.locator(selector).first.inner_text(timeout=3000)
                        if text and text.strip():
                            location = text.strip()
                            break
                    except Exception:
                        continue

                description = ""
                for selector in [
                    ".jobs-description__content",
                    ".show-more-less-html__markup",
                    "#job-details",
                ]:
                    try:
                        text = await job_page.locator(selector).first.inner_text(timeout=3000)
                        if text and text.strip():
                            description = text.strip()[:1200]
                            break
                    except Exception:
                        continue

                if title == "N/A":
                    try:
                        page_title = (await job_page.title()).strip()
                        if page_title:
                            title = page_title.split("|")[0].strip()
                    except Exception:
                        pass

                if company == "N/A" and " at " in title:
                    parts = title.split(" at ", 1)
                    title = parts[0].strip() or title
                    company = parts[1].strip() or company
                
                job_result = JobResult(
                    title=title,
                    company=company,
                    location=location,
                    url=job_url,
                    description=description,
                    source="linkedin"
                )
                jobs.append(job_result)
                
                await job_page.close()
            except Exception as e:
                console.print(f"[yellow]Error extracting LinkedIn job: {e}[/yellow]")
                continue
        
        console.print(f"[green]LinkedIn: Found {len(jobs)} jobs[/green]")
        
    except Exception as e:
        console.print(f"[red]LinkedIn search error: {e}[/red]")
    finally:
        await page.close()
    
    return jobs


async def search_naukri(browser: Browser, profile: JobProfile) -> list[JobResult]:
    """Search for jobs on Naukri."""
    page = await get_page(browser, "naukri")
    jobs = []
    
    try:
        # Load session
        await load_session(page, "naukri")
        
        # Build URL with role and location (lowercase, spaces to hyphens)
        role_slug = profile.role.lower().replace(" ", "-")
        location_slug = profile.location.lower().replace(" ", "-")
        url = f"https://www.naukri.com/{role_slug}-jobs-in-{location_slug}"
        
        # Navigate and wait for job cards
        if not await safe_goto(page, url):
            console.print("[yellow]Failed to navigate to Naukri jobs[/yellow]")
            return jobs
        
        # Wait for job cards
        try:
            await page.wait_for_selector(".jobTuple, .cust-job-tuple", timeout=10000)
        except:
            console.print("[yellow]No job cards found on Naukri[/yellow]")
            return jobs
        
        # Extract job cards
        job_cards = await page.query_selector_all(".jobTuple")
        
        for job_card in job_cards[:10]:
            try:
                # Extract title
                title_elem = await job_card.query_selector(".jobTitle")
                title = await title_elem.inner_text() if title_elem else "N/A"
                title = title.strip()
                
                # Extract company
                company_elem = await job_card.query_selector(".companyName")
                company = await company_elem.inner_text() if company_elem else "N/A"
                company = company.strip()
                
                # Extract location
                location_elem = await job_card.query_selector(".jobLocation")
                location = await location_elem.inner_text() if location_elem else profile.location
                location = location.strip()
                
                # Extract URL
                link_elem = await job_card.query_selector("a.titleUrl")
                url = await link_elem.get_attribute("href") if link_elem else ""
                
                # Extract salary
                salary_elem = await job_card.query_selector(".sal")
                salary = await salary_elem.inner_text() if salary_elem else None
                salary = salary.strip() if salary else None
                
                job_result = JobResult(
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    description="",
                    source="naukri",
                    salary=salary
                )
                jobs.append(job_result)
                
            except Exception as e:
                console.print(f"[yellow]Error extracting Naukri job: {e}[/yellow]")
                continue
        
        console.print(f"[green]Naukri: Found {len(jobs)} jobs[/green]")
        
    except Exception as e:
        console.print(f"[red]Naukri search error: {e}[/red]")
    finally:
        await page.close()
    
    return jobs


async def search_wellfound(browser: Browser, profile: JobProfile) -> list[JobResult]:
    """Search for jobs on Wellfound."""
    page = await get_page(browser, "wellfound")
    jobs = []
    
    try:
        # Load session
        await load_session(page, "wellfound")
        
        # Build URL
        url = f"https://wellfound.com/jobs?q={quote(profile.role)}&l={quote(profile.location)}"
        
        # Navigate
        if not await safe_goto(page, url):
            console.print("[yellow]Failed to navigate to Wellfound jobs[/yellow]")
            return jobs
        
        # Wait for job cards
        try:
            await page.wait_for_selector("[class*='JobCard'], [class*='job-card']", timeout=10000)
        except:
            console.print("[yellow]No job cards found on Wellfound[/yellow]")
            return jobs
        
        # Extract job cards
        job_cards = await page.query_selector_all("[class*='JobCard']")
        
        for job_card in job_cards[:10]:
            try:
                # Extract title
                title_elem = await job_card.query_selector("h3, .title, [class*='title']")
                title = await title_elem.inner_text() if title_elem else "N/A"
                title = title.strip()
                
                # Extract company
                company_elem = await job_card.query_selector(".company, [class*='company']")
                company = await company_elem.inner_text() if company_elem else "N/A"
                company = company.strip()
                
                # Extract location
                location_elem = await job_card.query_selector(".location, [class*='location']")
                location = await location_elem.inner_text() if location_elem else profile.location
                location = location.strip()
                
                # Extract URL
                link_elem = await job_card.query_selector("a")
                job_url = await link_elem.get_attribute("href") if link_elem else ""
                if job_url and not job_url.startswith("http"):
                    job_url = f"https://wellfound.com{job_url}"
                
                job_result = JobResult(
                    title=title,
                    company=company,
                    location=location,
                    url=job_url,
                    description="",
                    source="wellfound"
                )
                jobs.append(job_result)
                
            except Exception as e:
                console.print(f"[yellow]Error extracting Wellfound job: {e}[/yellow]")
                continue
        
        console.print(f"[green]Wellfound: Found {len(jobs)} jobs[/green]")
        
    except Exception as e:
        console.print(f"[red]Wellfound search error: {e}[/red]")
    finally:
        await page.close()
    
    return jobs


async def search_cutshort(browser: Browser, profile: JobProfile) -> list[JobResult]:
    """Search for jobs on Cutshort."""
    page = await get_page(browser, "cutshort")
    jobs = []
    
    try:
        # Load session
        await load_session(page, "cutshort")
        
        # Build URL
        url = f"https://cutshort.io/jobs?q={quote(profile.role)}&locations={quote(profile.location)}"
        
        # Navigate
        if not await safe_goto(page, url):
            console.print("[yellow]Failed to navigate to Cutshort jobs[/yellow]")
            return jobs
        
        # Wait for job cards
        try:
            await page.wait_for_selector(".job-card, [class*='JobCard']", timeout=10000)
        except:
            console.print("[yellow]No job cards found on Cutshort[/yellow]")
            return jobs
        
        # Extract job cards
        job_cards = await page.query_selector_all(".job-card")
        if not job_cards:
            job_cards = await page.query_selector_all("[class*='JobCard']")
        
        for job_card in job_cards[:10]:
            try:
                # Extract title
                title_elem = await job_card.query_selector("h2, h3, .title, [class*='title']")
                title = await title_elem.inner_text() if title_elem else "N/A"
                title = title.strip()
                
                # Extract company
                company_elem = await job_card.query_selector(".company, [class*='company']")
                company = await company_elem.inner_text() if company_elem else "N/A"
                company = company.strip()
                
                # Extract location
                location_elem = await job_card.query_selector(".location, [class*='location']")
                location = await location_elem.inner_text() if location_elem else profile.location
                location = location.strip()
                
                # Extract URL
                link_elem = await job_card.query_selector("a")
                job_url = await link_elem.get_attribute("href") if link_elem else ""
                if job_url and not job_url.startswith("http"):
                    job_url = f"https://cutshort.io{job_url}"
                
                job_result = JobResult(
                    title=title,
                    company=company,
                    location=location,
                    url=job_url,
                    description="",
                    source="cutshort"
                )
                jobs.append(job_result)
                
            except Exception as e:
                console.print(f"[yellow]Error extracting Cutshort job: {e}[/yellow]")
                continue
        
        console.print(f"[green]Cutshort: Found {len(jobs)} jobs[/green]")
        
    except Exception as e:
        console.print(f"[red]Cutshort search error: {e}[/red]")
    finally:
        await page.close()
    
    return jobs


async def search_instahyre(browser: Browser, profile: JobProfile) -> list[JobResult]:
    """Search for jobs on Instahyre."""
    page = await get_page(browser, "instahyre")
    jobs = []
    
    try:
        # Load session
        await load_session(page, "instahyre")
        
        # Build URL
        url = f"https://www.instahyre.com/search-jobs/?q={quote(profile.role)}&l={quote(profile.location)}"
        
        # Navigate
        if not await safe_goto(page, url):
            console.print("[yellow]Failed to navigate to Instahyre jobs[/yellow]")
            return jobs
        
        # Wait for job cards
        try:
            await page.wait_for_selector(".job-card, .opportunity-card", timeout=10000)
        except:
            console.print("[yellow]No job cards found on Instahyre[/yellow]")
            return jobs
        
        # Extract job cards
        job_cards = await page.query_selector_all(".job-card")
        if not job_cards:
            job_cards = await page.query_selector_all(".opportunity-card")
        
        for job_card in job_cards[:10]:
            try:
                # Extract title
                title_elem = await job_card.query_selector("h2, h3, .title, [class*='title']")
                title = await title_elem.inner_text() if title_elem else "N/A"
                title = title.strip()
                
                # Extract company
                company_elem = await job_card.query_selector(".company, [class*='company']")
                company = await company_elem.inner_text() if company_elem else "N/A"
                company = company.strip()
                
                # Extract location
                location_elem = await job_card.query_selector(".location, [class*='location']")
                location = await location_elem.inner_text() if location_elem else profile.location
                location = location.strip()
                
                # Extract URL
                link_elem = await job_card.query_selector("a")
                job_url = await link_elem.get_attribute("href") if link_elem else ""
                if job_url and not job_url.startswith("http"):
                    job_url = f"https://www.instahyre.com{job_url}"
                
                job_result = JobResult(
                    title=title,
                    company=company,
                    location=location,
                    url=job_url,
                    description="",
                    source="instahyre"
                )
                jobs.append(job_result)
                
            except Exception as e:
                console.print(f"[yellow]Error extracting Instahyre job: {e}[/yellow]")
                continue
        
        console.print(f"[green]Instahyre: Found {len(jobs)} jobs[/green]")
        
    except Exception as e:
        console.print(f"[red]Instahyre search error: {e}[/red]")
    finally:
        await page.close()
    
    return jobs


async def search_all(browser: Browser, profile: JobProfile) -> list[JobResult]:
    """Search all 5 platforms concurrently and merge results."""
    console.print("[cyan]Starting job search across all platforms...[/cyan]")
    
    # Run all searches concurrently using asyncio.gather
    results = await asyncio.gather(
        search_linkedin(browser, profile),
        search_naukri(browser, profile),
        search_wellfound(browser, profile),
        search_cutshort(browser, profile),
        search_instahyre(browser, profile),
        return_exceptions=True
    )
    
    # Merge results and handle exceptions
    all_jobs = []
    platform_counts = {
        "linkedin": 0,
        "naukri": 0,
        "wellfound": 0,
        "cutshort": 0,
        "instahyre": 0
    }
    
    for result in results:
        if isinstance(result, Exception):
            console.print(f"[red]Search error: {result}[/red]")
        elif isinstance(result, list):
            all_jobs.extend(result)
            for job in result:
                platform_counts[job.source] += 1
    
    # Print summary
    console.print("[cyan]╔════════════════════════════════════╗[/cyan]")
    console.print("[cyan]║     Job Search Results Summary      ║[/cyan]")
    console.print("[cyan]╠════════════════════════════════════╣[/cyan]")
    for platform, count in platform_counts.items():
        console.print(f"[cyan]║ {platform:.<28} {count:>3} ║[/cyan]")
    console.print("[cyan]╠════════════════════════════════════╣[/cyan]")
    console.print(f"[cyan]║ {'Total':.<28} {len(all_jobs):>3} ║[/cyan]")
    console.print("[cyan]╚════════════════════════════════════╝[/cyan]")
    
    return all_jobs


if __name__ == "__main__":
    from core.browser import get_browser
    
    async def main():
        # Test profile
        test_profile = JobProfile(
            role="Python Developer",
            skills=["Python", "Django", "PostgreSQL"],
            location="Bangalore",
            experience_years=3,
            resume_summary="Experienced Python developer with 3 years in web development"
        )
        
        browser = await get_browser()
        try:
            jobs = await search_all(browser, test_profile)
            console.print(f"\n[green]Total jobs found: {len(jobs)}[/green]")
            
            # Display sample results
            if jobs:
                console.print("\n[yellow]Sample Results:[/yellow]")
                for job in jobs[:5]:
                    console.print(f"\n[bold]{job.title}[/bold]")
                    console.print(f"  Company: {job.company}")
                    console.print(f"  Location: {job.location}")
                    console.print(f"  Source: {job.source}")
                    if job.salary:
                        console.print(f"  Salary: {job.salary}")
        finally:
            await browser.close()
    
    asyncio.run(main())
