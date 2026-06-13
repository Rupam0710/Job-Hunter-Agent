import asyncio
import json
import re

from core.llm_config import fast_llm
from core.schemas import JobProfile, JobResult


async def score_job_match(job: JobResult, profile: JobProfile) -> dict:
    """Score job match and extract matched skills and reason."""
    prompt = (
        "Candidate profile:\n"
        f"Role: {profile.role}\n"
        f"Skills: {', '.join(profile.skills)}\n"
        f"Experience: {profile.experience_years} yrs\n\n"
        "Job posting:\n"
        f"Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Description: {job.description[:400]}\n\n"
        "Tasks:\n"
        "1. Score match 0.0-1.0 based on skill overlap and role fit\n"
        "2. List up to 3 matching skills from candidate's list found in job description\n"
        "3. Write a 1-line reason\n\n"
        'Return ONLY JSON:\n'
        '{"score": 0.0, "matched_skills": [], "reason": ""}\n'
        "No markdown."
    )

    try:
        response = await fast_llm.ainvoke(prompt)
        raw_content = getattr(response, "content", "")
        content = raw_content if isinstance(raw_content, str) else str(raw_content)

        # Extract the first JSON object in case the model adds extra text.
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in model response")

        data = json.loads(match.group(0))
        score = float(data["score"])
        matched_skills = data.get("matched_skills", [])
        reason = data.get("reason", "")

        # Normalize score to 0.0-1.0 range
        score = max(0.0, min(1.0, score))

        # Update job object
        job.relevance_score = score
        job.matched_skills = matched_skills if isinstance(matched_skills, list) else []
        job.match_reason = str(reason)

        return {"score": score, "matched_skills": job.matched_skills, "reason": job.match_reason}
    except Exception:
        # Return default on parse error
        return {"score": 0.5, "matched_skills": [], "reason": "parse error"}


async def score_jobs(jobs: list[JobResult], profile: JobProfile) -> list[JobResult]:
    """Score job relevance with LLM, filter by score >= 0.6, and return top 15 results."""
    for job in jobs:
        await score_job_match(job, profile)

    # Only keep jobs with score >= 0.6
    qualifying_jobs = [job for job in jobs if job.relevance_score >= 0.6]
    
    ranked_jobs = sorted(qualifying_jobs, key=lambda item: item.relevance_score, reverse=True)
    return ranked_jobs[:15]


if __name__ == "__main__":
    sample_profile = JobProfile(
        role="Python Backend Developer",
        skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
        location="Bengaluru",
        experience_years=4,
        resume_summary="Backend engineer focused on APIs and distributed systems.",
    )

    sample_jobs = [
        JobResult(
            title="Backend Engineer",
            company="Acme Tech",
            location="Bengaluru",
            url="https://example.com/job-1",
            description="Build and scale backend APIs in Python and FastAPI with PostgreSQL.",
            source="linkedin",
        ),
        JobResult(
            title="Frontend Developer",
            company="UI Labs",
            location="Remote",
            url="https://example.com/job-2",
            description="Work on React UI with some Node.js backend integration.",
            source="wellfound",
        ),
    ]

    async def _run() -> None:
        scored = await score_jobs(sample_jobs, sample_profile)
        for job in scored:
            print(f"{job.title} @ {job.company}: {job.relevance_score:.2f}")

    asyncio.run(_run())
