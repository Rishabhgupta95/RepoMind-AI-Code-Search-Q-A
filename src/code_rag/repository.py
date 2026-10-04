from pathlib import Path
import re
from urllib.parse import urlparse

from git import Repo

from .config import REPOSITORY_DIRECTORY


def repository_name(
    url: str,
) -> str:
    candidate = url.rsplit(":", 1)[-1] if url.startswith("git@") else urlparse(url).path
    name = Path(candidate.rstrip("/")).name
    if name.endswith(".git"):
        name = name[:-4]
    if not name or name in {".", ".."}:
        raise ValueError(f"Cannot determine repository name from {url!r}")
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def is_repository_url(source: str) -> bool:
    return source.startswith("git@") or urlparse(source).scheme.lower() in {
        "http",
        "https",
        "ssh",
        "git",
    }


def repository_key(source: str) -> str:
    """Create a stable Qdrant filter key for a URL or local repository path."""
    if not is_repository_url(source):
        return str(Path(source).expanduser().resolve())
    if source.startswith("git@"):
        host_and_path = source[4:]
        host, _, path = host_and_path.partition(":")
        normalized = f"{host.lower()}/{path}"
    else:
        parsed = urlparse(source)
        normalized = f"{parsed.hostname or ''}{parsed.path}"
    normalized = normalized.rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized.lower()


def clone_repository(
    url: str,
) -> str:

    name = repository_name(url)

    destination = (
        Path(REPOSITORY_DIRECTORY)
        / name
    )

    if destination.exists():
        if (destination / ".git").exists():
            return str(destination)
        raise FileExistsError(
            f"Clone destination exists but is not a Git repository: {destination}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)

    Repo.clone_from(
        url,
        destination,
    )

    return str(destination)