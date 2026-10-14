from functools import lru_cache
from threading import Lock
from typing import cast

import numpy as np
from numpy.typing import NDArray
from sentence_transformers import SentenceTransformer

from app.config import get_settings

EMBEDDING_DIMENSIONS = 384
_model_lock = Lock()


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    settings = get_settings()
    with _model_lock:
        return cast(
            SentenceTransformer,
            SentenceTransformer(
                settings.KNOWLEDGE_MODEL_ID,
                revision=settings.KNOWLEDGE_MODEL_REVISION,
                cache_folder=str(settings.KNOWLEDGE_MODEL_CACHE_DIR),
                device="cpu",
            ),
        )


def _encode(texts: list[str]) -> NDArray[np.float32]:
    vectors = get_model().encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    result = cast(NDArray[np.float32], vectors)
    if result.ndim != 2 or result.shape[1] != EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSIONS}, got {result.shape}"
        )
    return result


def embed_passages(contents: list[str]) -> NDArray[np.float32]:
    return _encode([f"passage: {content}" for content in contents])


def embed_query(query: str) -> list[float]:
    return cast(list[float], _encode([f"query: {query}"])[0].tolist())


def prewarm() -> None:
    get_model()
