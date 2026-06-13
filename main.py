import asyncio
import os
from pathlib import Path

from rich.console import Console

from agents.apply_agent import apply_to_all
from agents.login_agent import login_linkedin
from agents.search_agent import search_linkedin
from agents.scorer_agent import score_jobs
from core.browser import get_browser
from core.env import load_project_env
from core.schemas import JobProfile

console = Console()


def _profile_from_env() -> JobProfile:
	role = os.getenv("JOB_ROLE", "").strip()
	skills_raw = os.getenv("JOB_SKILLS", "").strip()
	location = os.getenv("JOB_LOCATION", "").strip()
	experience_raw = os.getenv("JOB_EXPERIENCE_YEARS", "").strip()
	resume_summary = os.getenv("JOB_RESUME_SUMMARY", "").strip()

	if not role or not skills_raw or not location or not experience_raw or not resume_summary:
		raise ValueError(
			"Missing profile fields. Set JOB_ROLE, JOB_SKILLS, JOB_LOCATION, "
			"JOB_EXPERIENCE_YEARS, and JOB_RESUME_SUMMARY in .env"
		)

	skills = [skill.strip() for skill in skills_raw.split(",") if skill.strip()]
	if not skills:
		raise ValueError("JOB_SKILLS must include at least one skill")

	try:
		experience_years = int(experience_raw)
	except ValueError as exc:
		raise ValueError("JOB_EXPERIENCE_YEARS must be an integer") from exc

	return JobProfile(
		role=role,
		skills=skills,
		location=location,
		experience_years=experience_years,
		resume_summary=resume_summary,
	)


async def run_linkedin_apply_flow() -> None:
	env_source = load_project_env()
	console.print(f"[cyan]Loaded environment from: {env_source or 'system environment'}[/cyan]")

	profile = _profile_from_env()
	console.print(
		f"[cyan]Profile:[/cyan] {profile.role} | {profile.experience_years} yrs | {profile.location}"
	)

	browser = await get_browser()
	try:
		console.print("[bold cyan]STEP 1[/bold cyan] [white]Session / Login[/white]")
		session_file = Path("sessions/linkedin.json")
		if session_file.exists():
			console.print("[green]Using saved LinkedIn session cookies[/green]")
		else:
			console.print("[yellow]No LinkedIn session found; attempting login[/yellow]")
			logged_in = await login_linkedin(browser)
			if not logged_in:
				console.print("[red]LinkedIn login failed; cannot continue apply flow.[/red]")
				return

		console.print("[bold cyan]STEP 2[/bold cyan] [white]Search LinkedIn[/white]")
		raw_jobs = await search_linkedin(browser, profile)
		if not raw_jobs:
			console.print("[yellow]No jobs found from session; retrying after fresh LinkedIn login...[/yellow]")
			logged_in = await login_linkedin(browser)
			if logged_in:
				raw_jobs = await search_linkedin(browser, profile)
		console.print(f"[green]LinkedIn jobs found:[/green] {len(raw_jobs)}")

		console.print("[bold cyan]STEP 3[/bold cyan] [white]Score Matches[/white]")
		scored_jobs = await score_jobs(raw_jobs, profile)
		console.print(f"[green]Matched jobs (>= 0.6):[/green] {len(scored_jobs)}")

		for job in scored_jobs:
			skills = ", ".join(job.matched_skills) if job.matched_skills else "None"
			reason = job.match_reason or "No reason provided"
			console.print(
				f"[white]Match[/white] score={job.relevance_score:.2f} | "
				f"skills=[{skills}] | reason={reason} | "
				f"{job.company} - {job.title}"
			)

		if not scored_jobs:
			console.print("[yellow]No qualifying jobs to apply to.[/yellow]")
			return

		console.print("[bold cyan]STEP 4[/bold cyan] [white]Apply LinkedIn Jobs[/white]")
		applied, failed = await apply_to_all(browser, scored_jobs, profile, max_per_platform=3)

		console.print(f"[bold green]Applied:[/bold green] {len(applied)}")
		console.print(f"[bold red]Failed:[/bold red] {len(failed)}")
	finally:
		await browser.close()


if __name__ == "__main__":
	asyncio.run(run_linkedin_apply_flow())
