from uuid import uuid4

import psycopg

from app.config import get_settings
from app.knowledge.chunker import chunk_document, load_documents
from app.knowledge.embeddings import embed_passages
from app.knowledge.validator import validate_knowledge_base


def vector_literal(vector: list[float]) -> str:
    return f"[{','.join(str(value) for value in vector)}]"


def main() -> None:
    settings = get_settings()
    knowledge_root = settings.KNOWLEDGE_BASE_ROOT.resolve(strict=True)
    agent_root = knowledge_root.parent
    validation = validate_knowledge_base(
        kb_root=knowledge_root,
        query_file=agent_root / "tests" / "retrieval" / "knowledge-base-queries.jsonl",
        project_root=agent_root,
        workspace_root=agent_root.parents[1],
    )
    if validation.failures:
        raise RuntimeError("Knowledge-base validation failed:\n" + "\n".join(validation.failures))

    documents = load_documents(knowledge_root)
    chunks = [chunk for document in documents for chunk in chunk_document(document)]
    if not chunks:
        raise RuntimeError("No eligible knowledge chunks were found")
    vectors = embed_passages([chunk.content for chunk in chunks])

    run_id = uuid4()
    lock_key = (
        f"knowledge-ingest:{settings.KNOWLEDGE_CORPUS_ID}:"
        f"{settings.KNOWLEDGE_MODEL_ID}:{settings.KNOWLEDGE_MODEL_REVISION}"
    )
    with psycopg.connect(settings.AI_DATABASE_URL, autocommit=True) as connection:
        locked = connection.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", (lock_key,)
        ).fetchone()
        if locked is None or not locked[0]:
            raise RuntimeError("Another knowledge ingestion is already running")
        try:
            with connection.transaction():
                for chunk, vector in zip(chunks, vectors, strict=True):
                    connection.execute(
                        """
                        INSERT INTO knowledge_chunks (
                          corpus_id, embedding_model, embedding_revision, chunk_id, document_id,
                          heading, citation_label, domain, status, business_authority, audience,
                          content, content_hash, chunk_index, embedding, last_ingest_run_id
                        ) VALUES (
                          %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                          %s::vector, %s
                        )
                        ON CONFLICT (corpus_id, embedding_model, embedding_revision, chunk_id)
                        DO UPDATE SET
                          document_id = EXCLUDED.document_id,
                          heading = EXCLUDED.heading,
                          citation_label = EXCLUDED.citation_label,
                          domain = EXCLUDED.domain,
                          status = EXCLUDED.status,
                          business_authority = EXCLUDED.business_authority,
                          audience = EXCLUDED.audience,
                          content = EXCLUDED.content,
                          content_hash = EXCLUDED.content_hash,
                          chunk_index = EXCLUDED.chunk_index,
                          embedding = EXCLUDED.embedding,
                          last_ingest_run_id = EXCLUDED.last_ingest_run_id,
                          updated_at = now()
                        """,
                        (
                            settings.KNOWLEDGE_CORPUS_ID,
                            settings.KNOWLEDGE_MODEL_ID,
                            settings.KNOWLEDGE_MODEL_REVISION,
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.heading,
                            chunk.citation_label,
                            chunk.domain,
                            chunk.status,
                            chunk.business_authority,
                            chunk.audience,
                            chunk.content,
                            chunk.content_hash,
                            chunk.chunk_index,
                            vector_literal(vector.tolist()),
                            run_id,
                        ),
                    )
                removed = connection.execute(
                    """
                    DELETE FROM knowledge_chunks
                    WHERE corpus_id = %s
                      AND embedding_model = %s
                      AND embedding_revision = %s
                      AND last_ingest_run_id <> %s
                    """,
                    (
                        settings.KNOWLEDGE_CORPUS_ID,
                        settings.KNOWLEDGE_MODEL_ID,
                        settings.KNOWLEDGE_MODEL_REVISION,
                        run_id,
                    ),
                ).rowcount
        finally:
            connection.execute("SELECT pg_advisory_unlock(hashtext(%s))", (lock_key,))
    print(
        f"Knowledge ingestion completed: {len(chunks)} chunks upserted, "
        f"{removed or 0} obsolete chunks removed."
    )


if __name__ == "__main__":
    main()
