import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncGenerator, Awaitable, Callable

from rich.console import Console

from agents.apply_agent import apply_to_all
from agents.login_agent import login_all
from agents.report_agent import generate_report
from agents.scorer_agent import score_jobs
from agents.search_agent import search_all
from core.browser import get_browser
from core.schemas import HunterState, JobProfile, JobResult

console = Console()


def _progress(agent: str, status: str, detail: str) -> dict:
    return {"type": "progress", "agent": agent, "status": status, "detail": detail}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _job_to_dict(job: JobResult) -> dict:
    if hasattr(job, "model_dump"):
        return job.model_dump()
    return job.dict()


async def run_hunter(profile: JobProfile) -> AsyncGenerator[str, None]:
    browser = await get_browser()
    state = HunterState(profile=profile)

    try:
        console.print("[bold cyan]STEP 1[/bold cyan] [white]Login[/white]")
        yield _sse(_progress("login", "running", "Logging into all platforms..."))
        login_results = await login_all(browser)
        successful_logins = sum(1 for success in login_results.values() if success)
        yield _sse(_progress("login", "done", f"Logged into {successful_logins}/5 platforms"))

        console.print("[bold cyan]STEP 2[/bold cyan] [white]Search[/white]")
        yield _sse(_progress("search", "running", "Searching all platforms..."))
        search_results, = await asyncio.gather(search_all(browser, profile))
        state.raw_jobs = search_results
        yield _sse(_progress("search", "done", f"Found {len(state.raw_jobs)} jobs"))

        console.print("[bold cyan]STEP 3[/bold cyan] [white]Score[/white]")
        yield _sse(_progress("scorer", "running", "Scoring relevance..."))
        state.filtered_jobs = await score_jobs(state.raw_jobs, profile)
        yield _sse(_progress("scorer", "done", f"Top {len(state.filtered_jobs)} jobs selected"))

        console.print("[bold cyan]STEP 4[/bold cyan] [white]Apply[/white]")
        yield _sse(_progress("apply", "running", "Applying to top matches..."))

        # Keep only jobs at or above threshold, sorted by score, capped to top 3 per platform.
        eligible_jobs = [job for job in state.filtered_jobs if job.relevance_score >= 0.6]
        eligible_jobs.sort(key=lambda job: job.relevance_score, reverse=True)

        platform_counts: dict[str, int] = defaultdict(int)
        jobs_to_apply: list[JobResult] = []
        for job in eligible_jobs:
            platform = job.source.lower()
            if platform_counts[platform] >= 3:
                continue
            jobs_to_apply.append(job)
            platform_counts[platform] += 1

        state.filtered_jobs = jobs_to_apply
        console.print(
            f"[cyan]Prepared {len(jobs_to_apply)} jobs for apply (score >= 0.6, top 3 per platform)[/cyan]"
        )
        for job in jobs_to_apply:
            skills = ", ".join(job.matched_skills) if job.matched_skills else "None"
            reason = job.match_reason if job.match_reason else "No reason provided"
            console.print(
                f"[white]Match[/white] score={job.relevance_score:.2f} | "
                f"skills=[{skills}] | reason={reason} | "
                f"{job.source}: {job.company} - {job.title}"
            )

        apply_updates: asyncio.Queue[JobResult | None] = asyncio.Queue()

        async def on_apply_update(job: JobResult) -> None:
            await apply_updates.put(job)

        apply_task = asyncio.create_task(
            apply_to_all(
                browser,
                state.filtered_jobs,
                profile,
                max_per_platform=3,
                on_update=on_apply_update,
            )
        )

        while True:
            if apply_task.done() and apply_updates.empty():
                break

            try:
                job = await asyncio.wait_for(apply_updates.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            if job is None:
                continue

            yield _sse(
                {
                    "type": "apply_update",
                    "job": job.title,
                    "company": job.company,
                    "status": job.apply_status,
                    "platform": job.source,
                }
            )

        state.applied_jobs, state.failed_jobs = await apply_task
        yield _sse(
            _progress(
                "apply",
                "done",
                f"Applied: {len(state.applied_jobs)} | Failed: {len(state.failed_jobs)}",
            )
        )

        console.print("[bold cyan]STEP 5[/bold cyan] [white]Report[/white]")
        yield _sse(_progress("report", "running", "Generating report..."))
        state.report = await generate_report(state)
        yield _sse(_progress("report", "done", "Report ready"))
        yield _sse({"type": "report", "report": state.report})

        console.print("[bold cyan]STEP 6[/bold cyan] [white]Jobs Summary[/white]")
        yield _sse({"type": "jobs", "jobs": [_job_to_dict(job) for job in state.applied_jobs]})
    finally:
        console.print("[bold blue]Closing browser[/bold blue]")
        await browser.close()