from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient, models

from .config import COLLECTION_NAME, QDRANT_API_KEY, QDRANT_URL


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def ensure_collection(vector_size: int) -> None:
    client = get_client()
    collection_names = {
        item.name for item in client.get_collections().collections
    }
    if COLLECTION_NAME not in collection_names:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )
        return

    collection = client.get_collection(COLLECTION_NAME)
    configured_vectors = collection.config.params.vectors
    if isinstance(configured_vectors, dict):
        raise ValueError(
            f"Qdrant collection {COLLECTION_NAME!r} uses named vectors, which this "
            "service does not support. Use a new collection name or migrate the collection."
        )
    existing_size = getattr(configured_vectors, "size", None)
    if existing_size is not None and existing_size != vector_size:
        raise ValueError(
            f"Qdrant collection {COLLECTION_NAME!r} uses {existing_size}-dimensional "
            f"vectors, but the selected model produces {vector_size}. Use a new "
            "collection name or recreate the existing collection."
        )


def upsert_points(points: list[models.PointStruct]) -> None:
    if points:
        get_client().upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True,
        )


def search_points(
    vector: list[float],
    limit: int,
    repository: str | None = None,
) -> list[Any]:
    query_filter = None
    if repository:
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="repository",
                    match=models.MatchValue(value=repository),
                )
            ]
        )
    result = get_client().query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )
    return result.points


def repository_point_ids(repository: str) -> set[str]:
    selector = models.FilterSelector(
        filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="repository",
                    match=models.MatchValue(value=repository),
                )
            ]
        )
    )
    point_ids: set[str] = set()
    offset = None
    while True:
        points, offset = get_client().scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=selector.filter,
            offset=offset,
            limit=256,
            with_payload=False,
            with_vectors=False,
        )
        point_ids.update(str(point.id) for point in points)
        if offset is None:
            return point_ids


def delete_points(point_ids: set[str]) -> None:
    if point_ids:
        get_client().delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.PointIdsList(points=list(point_ids)),
            wait=True,
        )