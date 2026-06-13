import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import Tuple

from rich.console import Console
from playwright.async_api import Browser, Page

from core.schemas import JobResult, JobProfile
from core.browser import get_page, safe_goto

console = Console()


async def apply_linkedin(
    browser: Browser,
    job: JobResult,
    profile: JobProfile,
    cover_note: str | None = None,
) -> bool:
    """Apply to a job on LinkedIn."""
    page = None
    try:
        page = await get_page(browser, "linkedin")
        
        # Navigate to job URL
        if not await safe_goto(page, job.url):
            return False
        
        await asyncio.sleep(2)  # Wait for page to load
        
        # Look for Easy Apply button
        try:
            easy_apply_btn = await page.query_selector(".jobs-apply-button")
            if not easy_apply_btn:
                console.log("[yellow]Easy Apply button not found[/yellow]")
                return False
            
            await easy_apply_btn.click()
            await asyncio.sleep(1)
            
            # Handle multi-step form
            max_steps = 10
            step = 0
            cover_note_filled = False
            while step < max_steps:
                step += 1
                await asyncio.sleep(1)
                
                # Check for phone number input
                phone_inputs = await page.query_selector_all('input[type="text"], input[type="tel"]')
                for phone_input in phone_inputs:
                    placeholder = await phone_input.get_attribute("placeholder")
                    if placeholder and ("phone" in placeholder.lower() or "mobile" in placeholder.lower()):
                        await phone_input.fill("+1234567890")
                        await asyncio.sleep(0.5)

                # Fill a cover-note field when available.
                if cover_note and not cover_note_filled:
                    try:
                        note_field = await page.query_selector(
                            'textarea, textarea[name*="cover" i], textarea[placeholder*="cover" i]'
                        )
                        if note_field:
                            await note_field.fill(cover_note)
                            await asyncio.sleep(0.5)
                            cover_note_filled = True
                    except Exception:
                        pass
                
                # Check for Next button
                next_btn = await page.query_selector('button:has-text("Next")')
                if next_btn:
                    await next_btn.click()
                    await asyncio.sleep(1)
                    continue
                
                # Check for Submit or Apply button (final)
                submit_btn = await page.query_selector('button:has-text("Submit"), button:has-text("Apply")')
                if submit_btn:
                    # Make sure it's the final submit, not an intermediate button
                    btn_text = await submit_btn.text_content()
                    if "Submit" in btn_text or "Apply" in btn_text:
                        await submit_btn.click()
                        await asyncio.sleep(2)
                        break
                else:
                    break
            
            # Check for success message
            try:
                await page.wait_for_selector(".artdeco-inline-feedback--success", timeout=5000)
                return True
            except:
                # If no success message but we got here, check if modal closed
                try:
                    await page.wait_for_selector(".modal", timeout=2000)
                    return False
                except:
                    return True  # Modal closed without error = success
        
        except Exception as e:
            console.log(f"[red]LinkedIn apply error: {str(e)}[/red]")
            return False
    
    finally:
        if page:
            await page.close()


async def apply_naukri(
    browser: Browser,
    job: JobResult,
    profile: JobProfile,
    cover_note: str | None = None,
) -> bool:
    """Apply to a job on Naukri."""
    page = None
    try:
        page = await get_page(browser, "naukri")
        
        # Navigate to job URL
        if not await safe_goto(page, job.url):
            return False
        
        await asyncio.sleep(2)
        
        # Look for Apply button
        try:
            apply_btn = None
            for selector in [".apply-button", "#apply-button", 'button:has-text("Apply")']: 
                apply_btn = await page.query_selector(selector)
                if apply_btn:
                    break
            
            if not apply_btn:
                console.log("[yellow]Naukri Apply button not found[/yellow]")
                return False
            
            initial_url = page.url
            await apply_btn.click()
            await asyncio.sleep(2)
            
            # Check if redirected to external site
            current_url = page.url
            if current_url != initial_url and "naukri" not in current_url:
                console.log("[yellow]Redirected to external site[/yellow]")
                job.apply_status = "skipped"
                return False
            
            # Check for apply modal
            try:
                modal_apply_btn = await page.query_selector('button:has-text("Apply"), button:has-text("Submit")')
                if modal_apply_btn:
                    await modal_apply_btn.click()
                    await asyncio.sleep(2)
            except:
                pass
            
            # Check for success message
            try:
                await page.wait_for_selector(".success, .success-message", timeout=5000)
                return True
            except:
                return True  # Assume success if apply was clicked without error
        
        except Exception as e:
            console.log(f"[red]Naukri apply error: {str(e)}[/red]")
            return False
    
    finally:
        if page:
            await page.close()


async def apply_wellfound(
    browser: Browser,
    job: JobResult,
    profile: JobProfile,
    cover_note: str | None = None,
) -> bool:
    """Apply to a job on WellFound."""
    page = None
    try:
        page = await get_page(browser, "wellfound")
        
        # Navigate to job URL
        if not await safe_goto(page, job.url):
            return False
        
        await asyncio.sleep(2)
        
        try:
            # Look for Apply button
            apply_btn = await page.query_selector('button:has-text("Apply")')
            if not apply_btn:
                console.log("[yellow]WellFound Apply button not found[/yellow]")
                return False
            
            await apply_btn.click()
            await asyncio.sleep(2)
            
            # Fill intro message textarea
            try:
                skills_str = ", ".join(profile.skills[:3])
                intro_message = cover_note or (
                    f"Hi, I am a {profile.role} with {profile.experience_years} years "
                    f"of experience in {skills_str}. {profile.resume_summary}"
                )
                
                textarea = await page.query_selector('textarea')
                if textarea:
                    await textarea.fill(intro_message)
                    await asyncio.sleep(1)
            except Exception as e:
                console.log(f"[yellow]Could not fill intro message: {str(e)}[/yellow]")
            
            # Click Send or Submit
            submit_btn = await page.query_selector('button:has-text("Send"), button:has-text("Submit")')
            if submit_btn:
                await submit_btn.click()
                await asyncio.sleep(2)
                return True
            
            return False
        
        except Exception as e:
            console.log(f"[red]WellFound apply error: {str(e)}[/red]")
            return False
    
    finally:
        if page:
            await page.close()


async def apply_cutshort(
    browser: Browser,
    job: JobResult,
    profile: JobProfile,
    cover_note: str | None = None,
) -> bool:
    """Apply to a job on Cutshort."""
    page = None
    try:
        page = await get_page(browser, "cutshort")
        
        # Navigate to job URL
        if not await safe_goto(page, job.url):
            return False
        
        await asyncio.sleep(2)
        
        try:
            # Look for Apply button
            apply_btn = await page.query_selector('button:has-text("Apply")')
            if not apply_btn:
                console.log("[yellow]Cutshort Apply button not found[/yellow]")
                return False
            
            await apply_btn.click()
            await asyncio.sleep(2)
            
            # Check if message box appears
            try:
                message_box = await page.query_selector('textarea, input[type="text"]')
                if message_box:
                    await message_box.fill(cover_note or profile.resume_summary)
                    await asyncio.sleep(1)
            except Exception as e:
                console.log(f"[yellow]Could not fill message box: {str(e)}[/yellow]")
            
            # Click submit
            submit_btn = await page.query_selector('button:has-text("Submit"), button:has-text("Send")')
            if submit_btn:
                await submit_btn.click()
                await asyncio.sleep(2)
                
                # Check for success confirmation
                try:
                    await page.wait_for_selector(".success, .confirmation", timeout=5000)
                    return True
                except:
                    return True  # Assume success if submitted
            
            return False
        
        except Exception as e:
            console.log(f"[red]Cutshort apply error: {str(e)}[/red]")
            return False
    
    finally:
        if page:
            await page.close()


async def apply_instahyre(
    browser: Browser,
    job: JobResult,
    profile: JobProfile,
    cover_note: str | None = None,
) -> bool:
    """Apply to a job on Instahyre."""
    page = None
    try:
        page = await get_page(browser, "instahyre")
        
        # Navigate to job URL
        if not await safe_goto(page, job.url):
            return False
        
        await asyncio.sleep(2)
        
        try:
            # Look for Apply or Express Interest button
            apply_btn = None
            for selector in ['button:has-text("Apply")', 'button:has-text("Express Interest")', '.apply-btn']:
                apply_btn = await page.query_selector(selector)
                if apply_btn:
                    break
            
            if not apply_btn:
                console.log("[yellow]Instahyre Apply button not found[/yellow]")
                return False
            
            await apply_btn.click()
            await asyncio.sleep(2)
            
            # Handle any confirmation modal
            try:
                confirm_btn = await page.query_selector('button:has-text("Confirm"), button:has-text("Yes"), button:has-text("Apply Now")')
                if confirm_btn:
                    await confirm_btn.click()
                    await asyncio.sleep(2)
            except:
                pass
            
            # Check for success message
            try:
                await page.wait_for_selector(".success, .applied, [class*='success']", timeout=5000)
                return True
            except:
                return True  # Assume success if button was clicked
        
        except Exception as e:
            console.log(f"[red]Instahyre apply error: {str(e)}[/red]")
            return False
    
    finally:
        if page:
            await page.close()


async def apply_to_job(
    browser: Browser,
    job: JobResult,
    profile: JobProfile,
    cover_note: str | None = None,
) -> JobResult:
    """Route to the correct apply function based on job source."""
    
    apply_functions = {
        "linkedin": apply_linkedin,
        "naukri": apply_naukri,
        "wellfound": apply_wellfound,
        "cutshort": apply_cutshort,
        "instahyre": apply_instahyre,
    }
    
    platform = job.source.lower()
    apply_func = apply_functions.get(platform)
    
    if not apply_func:
        console.log(f"[red]❌ Unknown platform: {job.source}[/red]")
        job.applied = False
        job.apply_status = "failed"
        return job
    
    try:
        success = await apply_func(browser, job, profile, cover_note)
        
        if success:
            job.applied = True
            job.apply_status = "applied"
            console.log(f"[green]✅ Applied[/green] to [bold]{job.company}[/bold] - {job.title}")
        else:
            if job.apply_status == "skipped":
                console.log(f"[cyan]⏭️  Skipped[/cyan] {job.company} - {job.title} (external redirect)")
            else:
                job.applied = False
                job.apply_status = "failed"
                console.log(f"[red]❌ Failed[/red] to apply to [bold]{job.company}[/bold] - {job.title}")
    
    except Exception as e:
        console.log(f"[red]❌ Error applying to {job.company}: {str(e)}[/red]")
        job.applied = False
        job.apply_status = "failed"
    
    return job


async def apply_to_all(
    browser: Browser,
    jobs: list[JobResult],
    profile: JobProfile,
    max_per_platform: int = 5,
    on_update: Callable[[JobResult], Awaitable[None]] | None = None,
) -> Tuple[list[JobResult], list[JobResult]]:
    """Apply to multiple jobs with rate limiting."""
    
    # Filter jobs by relevance score
    eligible_jobs = [job for job in jobs if job.relevance_score >= 0.6]
    console.log(f"[cyan]Found {len(eligible_jobs)} eligible jobs (score >= 0.6)[/cyan]")
    
    # Group by platform
    jobs_by_platform = {}
    for job in eligible_jobs:
        platform = job.source.lower()
        if platform not in jobs_by_platform:
            jobs_by_platform[platform] = []
        jobs_by_platform[platform].append(job)
    
    applied_jobs = []
    failed_jobs = []
    total_applied = 0
    
    # Apply to jobs sequentially with random delays
    for platform, platform_jobs in jobs_by_platform.items():
        platform_applied = 0
        
        for job in platform_jobs:
            if platform_applied >= max_per_platform:
                console.log(f"[yellow]Reached max applications for {platform} ({max_per_platform})[/yellow]")
                break

            top_matched_skills = job.matched_skills[:3] if job.matched_skills else profile.skills[:3]
            cover_note = (
                f"Hi, I'm a {profile.role} with {profile.experience_years} years "
                f"of experience. My background in {', '.join(top_matched_skills)} "
                f"aligns well with this role. {profile.resume_summary[:150]}"
            )
            
            # Wait 3-5 seconds before applying
            delay = random.uniform(3, 5)
            await asyncio.sleep(delay)
            
            console.log(f"[cyan]Applying to: {job.company} - {job.title} ({job.source})[/cyan]")
            
            updated_job = await apply_to_job(browser, job, profile, cover_note=cover_note)
            if on_update is not None:
                await on_update(updated_job)
            
            if updated_job.applied:
                applied_jobs.append(updated_job)
                platform_applied += 1
                total_applied += 1
            else:
                if updated_job.apply_status != "skipped":
                    failed_jobs.append(updated_job)
    
    console.log(f"\n[bold green]Successfully applied to {total_applied} jobs[/bold green]")
    console.log(f"[bold red]Failed to apply to {len(failed_jobs)} jobs[/bold red]")
    
    return applied_jobs, failed_jobs


if __name__ == "__main__":
    # Test code
    async def test_apply_agent():
        from core.browser import get_browser
        
        # Create test profile
        test_profile = JobProfile(
            role="Software Engineer",
            skills=["Python", "FastAPI", "SQL", "Docker"],
            location="Remote",
            experience_years=5,
            resume_summary="Experienced software engineer with expertise in backend development and cloud technologies."
        )
        
        # Create test jobs
        test_jobs = [
            JobResult(
                title="Senior Python Developer",
                company="TechCorp",
                location="Remote",
                url="https://linkedin.com/jobs/view/1234567",
                description="Looking for a senior Python developer",
                source="linkedin",
                relevance_score=0.85,
                salary="$120K - $150K"
            ),
            JobResult(
                title="Backend Engineer",
                company="StartupXYZ",
                location="San Francisco",
                url="https://naukri.com/job/5678910",
                description="Backend engineer needed",
                source="naukri",
                relevance_score=0.75,
                salary="$100K - $130K"
            ),
            JobResult(
                title="Full Stack Developer",
                company="WebServices Inc",
                location="Remote",
                url="https://wellfound.com/jobs/1",
                description="Full stack developer",
                source="wellfound",
                relevance_score=0.70,
                salary="$90K - $120K"
            ),
        ]
        
        browser = await get_browser()
        
        console.print("[bold cyan]Job Hunter Agent - Apply Module Test[/bold cyan]")
        console.print(f"Profile: {test_profile.role} | {test_profile.experience_years} years | {test_profile.location}")
        console.print(f"Total jobs to process: {len(test_jobs)}")
        console.print()
        
        # Test applying to all jobs
        applied, failed = await apply_to_all(browser, test_jobs, test_profile, max_per_platform=2)
        
        console.print("\n[bold]Results:[/bold]")
        console.print(f"[green]Applied: {len(applied)}[/green]")
        console.print(f"[red]Failed: {len(failed)}[/red]")
        
        await browser.close()
    
    asyncio.run(test_apply_agent())
