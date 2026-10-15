from .embeddings import embed, embedding_dimension
from .qdrant import ensure_collection, search_points


def search_code(
    query: str,
    limit: int = 5,
    repository: str | None = None,
) -> list[dict]:
    """Return the most relevant indexed chunks with source locations."""

    ensure_collection(embedding_dimension())

    # First, search without a repository filter to diagnose retrieval.
    points = search_points(
        embed(query),
        limit=limit,
        repository=None,
    )

    results = []

    for point in points:
        result = dict(point.payload or {})
        result["score"] = point.score
        results.append(result)

    return results