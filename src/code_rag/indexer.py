from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from typing import Callable

from qdrant_client import models

from .chunker import chunk_file
from .config import UPSERT_BATCH_SIZE
from .embeddings import embed_many, embedding_dimension
from .qdrant import (
    delete_points,
    ensure_collection,
    repository_point_ids,
    upsert_points,
)
from .repository import (
    clone_repository,
    is_repository_url,
    repository_key,
)
from .scanner import scan_repository


def _resolve_source(source: str) -> tuple[Path, str]:
    """Resolve a local repository path or clone a remote Git repository."""

    if is_repository_url(source):
        return (
            Path(clone_repository(source)).resolve(),
            repository_key(source),
        )

    path = Path(source).expanduser().resolve()

    if not path.is_dir():
        raise ValueError(
            f"Local repository directory does not exist: {path}"
        )

    return path, repository_key(str(path))


def _chunk_id(repository: str, chunk: dict) -> str:
    """Generate a deterministic UUID for a code chunk."""

    identity = ":".join(
        (
            repository,
            chunk["file"],
            chunk["symbol"],
            str(chunk["start_line"]),
            str(chunk["end_line"]),
        )
    )

    return str(uuid5(NAMESPACE_URL, identity))


def index_repository(
    source: str,
    progress_callback: Callable[..., None] | None = None,
) -> dict:
    """Index a local working tree or clone a Git URL into Qdrant.

    Args:
        source: Local repository path or remote Git URL.
        progress_callback: Optional callback receiving indexing progress.

    Returns:
        A dictionary containing repository details and indexing results.
    """

    def report_progress(**kwargs) -> None:
        """Report progress when a callback is provided."""

        if progress_callback:
            progress_callback(**kwargs)

    # --------------------------------------------------
    # Step 1: Resolve the repository source
    # --------------------------------------------------

    report_progress(
        status="indexing",
        stage="resolving_repository",
        files_scanned=0,
        files_processed=0,
        percent=0,
    )

    root, repository = _resolve_source(source)

    # --------------------------------------------------
    # Step 2: Scan repository files
    # --------------------------------------------------

    files = scan_repository(str(root))
    total_files = len(files)

    report_progress(
        status="indexing",
        stage="chunking",
        files_scanned=total_files,
        files_processed=0,
        files_chunked=0,
        percent=0,
    )

    # --------------------------------------------------
    # Step 3: Chunk source files
    # --------------------------------------------------

    chunks = []

    for index, path in enumerate(files, start=1):
        relative_path = path.relative_to(root).as_posix()

        file_chunks = chunk_file(
            str(path),
            relative_path=relative_path,
        )

        chunks.extend(file_chunks)

        # Chunking accounts for the first 50% of progress.
        percent = (
            int(index / total_files * 50)
            if total_files > 0
            else 50
        )

        report_progress(
            status="indexing",
            stage="chunking",
            files_scanned=total_files,
            files_processed=0,
            files_chunked=index,
            chunks_total=len(chunks),
            percent=percent,
        )

    # --------------------------------------------------
    # Step 4: Prepare Qdrant collection
    # --------------------------------------------------

    vector_size = embedding_dimension()

    ensure_collection(vector_size)

    previous_ids = repository_point_ids(repository)
    indexed_ids: set[str] = set()

    total_chunks = len(chunks)

    total_batches = (
        (total_chunks + UPSERT_BATCH_SIZE - 1)
        // UPSERT_BATCH_SIZE
    )

    # --------------------------------------------------
    # Step 5: Generate embeddings and upsert into Qdrant
    # --------------------------------------------------

    report_progress(
        status="indexing",
        stage="embedding",
        files_scanned=total_files,
        files_processed=0,
        chunks_total=total_chunks,
        chunks_indexed=0,
        batches_processed=0,
        batches_total=total_batches,
        percent=50,
    )

    chunks_indexed = 0
    processed_files: set[str] = set()

    for offset in range(
        0,
        total_chunks,
        UPSERT_BATCH_SIZE,
    ):
        batch = chunks[
            offset : offset + UPSERT_BATCH_SIZE
        ]

        texts = [
            f"Language: {item['language']}\n"
            f"File: {item['file']}\n"
            f"Symbol: {item['symbol']}\n"
            f"Code:\n{item['code']}"
            for item in batch
        ]

        vectors = embed_many(texts)

        points = []

        for chunk, vector in zip(
            batch,
            vectors,
            strict=True,
        ):
            point_id = _chunk_id(repository, chunk)

            indexed_ids.add(point_id)

            payload = {
                **chunk,
                "repository": repository,
                "repository_name": root.name,
            }

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        # Save the entire batch before updating progress.
        upsert_points(points)

        chunks_indexed += len(batch)

        processed_files.update(
            chunk["file"] for chunk in batch
        )

        # Embedding and upserting account for the next 49%.
        percent = (
            50 + int(chunks_indexed / total_chunks * 49)
            if total_chunks > 0
            else 99
        )

        report_progress(
            status="indexing",
            stage="embedding",
            files_scanned=total_files,
            files_processed=len(processed_files),
            chunks_total=total_chunks,
            chunks_indexed=chunks_indexed,
            batches_processed=(
                offset // UPSERT_BATCH_SIZE
            ) + 1,
            batches_total=total_batches,
            percent=percent,
        )

    # --------------------------------------------------
    # Step 6: Remove stale points
    # --------------------------------------------------

    # Delete old points only after all new batches are stored.
    delete_points(previous_ids - indexed_ids)

    # --------------------------------------------------
    # Step 7: Finalize indexing
    # --------------------------------------------------

    report_progress(
        status="indexing",
        stage="finalizing",
        files_scanned=total_files,
        files_processed=total_files,
        chunks_total=total_chunks,
        chunks_indexed=chunks_indexed,
        percent=99,
    )

    result = {
        "repository": repository,
        "repository_path": str(root),
        "files_scanned": total_files,
        "chunks_indexed": chunks_indexed,
    }

    report_progress(
        status="completed",
        stage="completed",
        files_scanned=total_files,
        files_processed=total_files,
        chunks_total=total_chunks,
        chunks_indexed=chunks_indexed,
        percent=100,
    )

    return result