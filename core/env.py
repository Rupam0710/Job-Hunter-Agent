from pathlib import Path

from dotenv import load_dotenv


def load_project_env() -> str | None:
    """Load .env first, then fall back to .env.example for local development."""
    root = Path(__file__).resolve().parent.parent
    env_file = root / ".env"
    example_file = root / ".env.example"

    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=True)
        return str(env_file)

    if example_file.exists():
        load_dotenv(dotenv_path=example_file, override=True)
        return str(example_file)

    load_dotenv(override=True)
    return None