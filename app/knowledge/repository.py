import asyncio
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings
from app.models import SearchResult

_pool: ConnectionPool[Any] | None = None


def _vector_literal(vector: list[float]) -> str:
    return f"[{','.join(str(value) for value in vector)}]"


def open_pool() -> None:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool(
            conninfo=settings.AI_DATABASE_URL,
            min_size=1,
            max_size=10,
            open=True,
            kwargs={"row_factory": dict_row},
        )


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def _require_pool() -> ConnectionPool[Any]:
    if _pool is None:
        open_pool()
    if _pool is None:
        raise RuntimeError("Knowledge database pool is unavailable")
    return _pool


def _search(vector: list[float], audiences: tuple[str, ...], top_k: int) -> list[SearchResult]:
    settings = get_settings()
    with _require_pool().connection() as connection:
        rows = connection.execute(
            """
            WITH ranked AS (
              SELECT
                document_id,
                heading,
                citation_label,
                domain,
                status,
                business_authority,
                content,
                (1 - (embedding <=> %s::vector))::double precision AS score,
                row_number() OVER (
                  PARTITION BY document_id ORDER BY embedding <=> %s::vector
                ) AS document_rank
              FROM knowledge_chunks
              WHERE corpus_id = %s
                AND embedding_model = %s
                AND embedding_revision = %s
                AND audience = ANY(%s::text[])
            )
            SELECT document_id, heading, citation_label, domain, status,
                   business_authority, content, score
            FROM ranked
            WHERE document_rank = 1
            ORDER BY score DESC
            LIMIT %s
            """,
            (
                _vector_literal(vector),
                _vector_literal(vector),
                settings.KNOWLEDGE_CORPUS_ID,
                settings.KNOWLEDGE_MODEL_ID,
                settings.KNOWLEDGE_MODEL_REVISION,
                list(audiences),
                top_k,
            ),
        ).fetchall()
    return [
        SearchResult(
            document_id=row["document_id"],
            heading=row["heading"],
            citation=row["citation_label"],
            domain=row["domain"],
            status=row["status"],
            business_authority=row["business_authority"],
            content=row["content"],
            score=row["score"],
        )
        for row in rows
    ]


async def search_chunks(
    vector: list[float], audiences: tuple[str, ...], top_k: int
) -> list[SearchResult]:
    return await asyncio.to_thread(_search, vector, audiences, top_k)


def _ping() -> bool:
    try:
        with _require_pool().connection() as connection:
            connection.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False


async def ping_database() -> bool:
    return await asyncio.to_thread(_ping)
