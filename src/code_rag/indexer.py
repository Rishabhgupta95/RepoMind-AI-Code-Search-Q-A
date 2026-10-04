from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

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
from .repository import clone_repository, is_repository_url, repository_key
from .scanner import scan_repository


def _resolve_source(source: str) -> tuple[Path, str]:
    if is_repository_url(source):
        return Path(clone_repository(source)).resolve(), repository_key(source)
    path = Path(source).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"Local repository directory does not exist: {path}")
    return path, repository_key(str(path))


def _chunk_id(repository: str, chunk: dict) -> str:
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


def index_repository(source: str) -> dict:
    """Index a local working tree or clone a Git URL into Qdrant."""
    root, repository = _resolve_source(source)
    files = scan_repository(str(root))
    chunks = []
    for path in files:
        relative_path = path.relative_to(root).as_posix()
        chunks.extend(chunk_file(str(path), relative_path=relative_path))

    vector_size = embedding_dimension()
    ensure_collection(vector_size)
    previous_ids = repository_point_ids(repository)
    indexed_ids: set[str] = set()

    for offset in range(0, len(chunks), UPSERT_BATCH_SIZE):
        batch = chunks[offset : offset + UPSERT_BATCH_SIZE]
        texts = [
            f"Language: {item['language']}\n"
            f"File: {item['file']}\n"
            f"Symbol: {item['symbol']}\n"
            f"Code:\n{item['code']}"
            for item in batch
        ]
        vectors = embed_many(texts)
        points = []
        for chunk, vector in zip(batch, vectors, strict=True):
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
        upsert_points(points)

    # Prune deleted/changed chunks only after every new batch has been stored.
    delete_points(previous_ids - indexed_ids)
    return {
        "repository": repository,
        "repository_path": str(root),
        "files_scanned": len(files),
        "chunks_indexed": len(chunks),
    }