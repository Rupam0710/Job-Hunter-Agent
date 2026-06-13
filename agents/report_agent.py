import asyncio
from pathlib import Path

from core.llm_config import powerful_llm
from core.schemas import HunterState, JobProfile, JobResult


def _format_applied_jobs(applied: list[JobResult]) -> str:
    if not applied:
        return "None"

    lines = []
    for job in applied:
        lines.append(f"- {job.title} | {job.company} | {job.source} | {job.url}")
    return "\n".join(lines)


def _format_failed_jobs(failed: list[JobResult]) -> str:
    if not failed:
        return "None"

    lines = []
    for job in failed:
        reason = getattr(job, "failure_reason", "") or job.apply_status or "unknown"
        lines.append(f"- {job.title} | {job.company} | {reason}")
    return "\n".join(lines)


async def generate_report(state: HunterState) -> str:
    profile = state.profile
    applied = state.applied_jobs
    failed = state.failed_jobs

    prompt = (
        "You are a career advisor. Generate a job hunt report in markdown.\n\n"
        f"Candidate: {profile.role}, {profile.experience_years} yrs\n"
        f"Skills: {profile.skills}\n"
        f"Location: {profile.location}\n\n"
        f"Applied Jobs ({len(applied)}):\n"
        f"{_format_applied_jobs(applied)}\n\n"
        f"Failed/Skipped ({len(failed)}):\n"
        f"{_format_failed_jobs(failed)}\n\n"
        "Write these sections:\n"
        "## 🎯 Hunt Summary\n"
        "- Total jobs found, applied, failed, skipped\n"
        "- Platforms searched\n"
        "- Success rate\n\n"
        "## ✅ Successfully Applied\n"
        "- For each applied job: title, company, platform, link, why it matches\n\n"
        "## 📊 Market Insights\n"
        "- Most active hiring platforms\n"
        "- Salary trends observed\n"
        "- Top skills in demand from listings\n\n"
        "## 🔥 Recommended Next Steps\n"
        "- 3 specific actions to improve chances"
    )

    response = await powerful_llm.ainvoke(prompt)
    raw_content = getattr(response, "content", "")
    report_markdown = raw_content if isinstance(raw_content, str) else str(raw_content)

    project_root = Path(__file__).resolve().parents[1]
    output_path = project_root / "output" / "report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_markdown, encoding="utf-8")

    return report_markdown


if __name__ == "__main__":
    sample_state = HunterState(
        profile=JobProfile(
            role="Python Backend Developer",
            skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
            location="Bengaluru",
            experience_years=4,
            resume_summary="Backend engineer focused on APIs and scalable systems.",
        ),
        raw_jobs=[],
        filtered_jobs=[],
        applied_jobs=[
            JobResult(
                title="Backend Engineer",
                company="Acme Tech",
                location="Bengaluru",
                url="https://example.com/jobs/1",
                description="Build Python APIs with FastAPI.",
                source="linkedin",
                salary="20-30 LPA",
                applied=True,
                apply_status="applied",
            ),
            JobResult(
                title="Senior Python Developer",
                company="DataCloud",
                location="Remote",
                url="https://example.com/jobs/2",
                description="Develop backend services and data pipelines.",
                source="naukri",
                salary="25-35 LPA",
                applied=True,
                apply_status="applied",
            ),
        ],
        failed_jobs=[
            JobResult(
                title="Platform Engineer",
                company="Infra Labs",
                location="Bengaluru",
                url="https://example.com/jobs/3",
                description="Maintain platform infrastructure.",
                source="wellfound",
                applied=False,
                apply_status="failed",
            ),
            JobResult(
                title="API Developer",
                company="FinServe",
                location="Bengaluru",
                url="https://example.com/jobs/4",
                description="Build financial APIs.",
                source="cutshort",
                applied=False,
                apply_status="skipped",
            ),
        ],
    )

    async def _run() -> None:
        report = await generate_report(sample_state)
        print(report)

    asyncio.run(_run())