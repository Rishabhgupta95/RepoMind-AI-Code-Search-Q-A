from functools import lru_cache

from sentence_transformers import SentenceTransformer

from .config import EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    """Load the embedding model once, on first use rather than API startup."""
    return SentenceTransformer(EMBEDDING_MODEL, device="cpu")


def embedding_dimension() -> int:
    dimension = get_model().get_embedding_dimension()
    if dimension is None:
        raise RuntimeError(f"Could not determine dimensions for {EMBEDDING_MODEL!r}")
    return dimension


def embed(text: str) -> list[float]:
    return embed_many([text])[0]


def embed_many(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = get_model().encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vectors.tolist()