from pydantic import BaseModel


class JobProfile(BaseModel):
    target_roles: list[str]
    skills: list[str]
    location: str


class JobResult(BaseModel):
    title: str
    company: str
    location: str
    url: str
    tech_stack: list[str] = []
    source: str  # "linkedin"|"naukri"|"wellfound"|"cutshort"
    relevance_score: float = 0.0


class SearchResponse(BaseModel):
    total_found: int
    jobs: list[JobResult]


class HunterState(BaseModel):
    profile: JobProfile
    raw_jobs: list[JobResult] = []
    filtered_jobs: list[JobResult] = []
    applied_jobs: list[JobResult] = []
    failed_jobs: list[JobResult] = []
    report: str = ""
