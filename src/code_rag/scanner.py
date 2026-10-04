from pathlib import Path

from .config import MAX_FILE_BYTES, MAX_REPOSITORY_FILES


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "target",
}


SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".kts",
    ".scala",
    ".sql",
    ".html",
    ".css",
    ".scss",
    ".md",
    ".json",
    ".yaml",
    ".yml",
}


LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "c_sharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def detect_language(file_path: str | Path) -> str:
    """Return the language inferred from a supported file extension."""
    return LANGUAGE_BY_EXTENSION.get(Path(file_path).suffix.lower(), "text")


def scan_repository(
    repository_path: str,
):

    root = Path(
        repository_path
    )

    if not root.is_dir():
        raise ValueError(f"Repository directory does not exist: {root}")

    files = []

    for path in root.rglob("*"):

        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if any(
            part in IGNORED_DIRECTORIES
            for part in relative.parts
        ):
            continue

        if (
            path.suffix.lower()
            not in SUPPORTED_EXTENSIONS
        ):
            continue

        if path.stat().st_size > MAX_FILE_BYTES:
            continue

        files.append(path)

        if len(files) > MAX_REPOSITORY_FILES:
            raise ValueError(
                f"Repository exceeds the {MAX_REPOSITORY_FILES} supported-file limit"
            )

    return sorted(files)