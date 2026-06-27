"""Project-path helpers for scripts and relocated notebooks."""

from pathlib import Path


def find_repo_root(start: str | Path | None = None) -> Path:
    """Find the nearest parent containing the project and Git markers."""
    candidate = Path.cwd() if start is None else Path(start)
    candidate = candidate.expanduser().resolve()
    if candidate.is_file():
        candidate = candidate.parent

    for directory in (candidate, *candidate.parents):
        if (directory / "pyproject.toml").is_file() and (directory / ".git").exists():
            return directory

    raise FileNotFoundError(
        f"Could not find a repository containing pyproject.toml and .git from {candidate}"
    )
