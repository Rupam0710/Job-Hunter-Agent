import ast
import asyncio
import json
import re

from core.llm_config import fast_llm


async def extract_tech_stack(description: str, candidate_skills: list[str]) -> list[str]:
    prompt = (
        "From this job description, list up to 6 technologies/skills \n"
        "mentioned that are relevant. Prioritize any that match: \n"
        f"{candidate_skills}\n\n"
        f"Description: {description[:400]}\n\n"
        "Return ONLY a JSON list of strings, e.g. ['React', 'C#', 'Azure']\n"
        "No markdown."
    )

    try:
        response = await fast_llm.ainvoke(prompt)
        raw_content = getattr(response, "content", "")
        content = raw_content if isinstance(raw_content, str) else str(raw_content)

        match = re.search(r"\[[\s\S]*?\]", content)
        if not match:
            return []

        payload = match.group(0).strip()

        try:
            data = json.loads(payload)
        except Exception:
            data = ast.literal_eval(payload)

        if not isinstance(data, list):
            return []

        tech_stack = [str(item).strip() for item in data if str(item).strip()]
        return tech_stack[:6]
    except Exception:
        return []


if __name__ == "__main__":

    async def _run() -> None:
        description = (
            "We are looking for a Backend Engineer with strong experience in C#, ASP.NET Core, "
            "Azure, SQL Server, Docker, and REST APIs. Familiarity with Python and LLM integration "
            "is a plus."
        )
        candidate_skills = ["Python", "C#", "Azure", "React", "Docker"]
        result = await extract_tech_stack(description, candidate_skills)
        print(result)

    asyncio.run(_run())