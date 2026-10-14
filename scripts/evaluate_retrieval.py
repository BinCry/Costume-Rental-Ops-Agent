import json
from typing import Any

import psycopg

from app.config import get_settings
from app.knowledge.chunker import load_documents
from app.knowledge.embeddings import embed_query


def vector_literal(vector: list[float]) -> str:
    return f"[{','.join(str(value) for value in vector)}]"


def main() -> None:
    settings = get_settings()
    knowledge_root = settings.KNOWLEDGE_BASE_ROOT.resolve(strict=True)
    document_ids = {
        document.source_path: document.document_id for document in load_documents(knowledge_root)
    }
    query_path = knowledge_root.parent / "tests" / "retrieval" / "knowledge-base-queries.jsonl"
    cases: list[dict[str, Any]] = [
        json.loads(line) for line in query_path.read_text(encoding="utf-8").splitlines() if line
    ]
    retrieval_cases = [case for case in cases if case.get("test_type", "retrieval") == "retrieval"]
    hits = {1: 0, 3: 0, 5: 0}
    misses: dict[int, list[str]] = {1: [], 3: [], 5: []}
    miss_details: list[str] = []

    with psycopg.connect(settings.AI_DATABASE_URL) as connection:
        for case in retrieval_cases:
            expected = {document_ids[path] for path in case["expected_documents"]}
            audiences = (
                ["customer", "shared"]
                if case["audience"] == "customer"
                else ["staff_internal", "shared"]
            )
            vector = vector_literal(embed_query(case["query"]))
            rows = connection.execute(
                """
                WITH ranked AS (
                  SELECT
                    document_id,
                    (embedding <=> %s::vector) AS distance,
                    row_number() OVER (
                      PARTITION BY document_id ORDER BY embedding <=> %s::vector
                    ) AS document_rank
                  FROM knowledge_chunks
                  WHERE corpus_id = %s
                    AND embedding_model = %s
                    AND embedding_revision = %s
                    AND audience = ANY(%s::text[])
                )
                SELECT document_id
                FROM ranked
                WHERE document_rank = 1
                ORDER BY distance
                LIMIT 5
                """,
                (
                    vector,
                    vector,
                    settings.KNOWLEDGE_CORPUS_ID,
                    settings.KNOWLEDGE_MODEL_ID,
                    settings.KNOWLEDGE_MODEL_REVISION,
                    audiences,
                ),
            ).fetchall()
            returned = [row[0] for row in rows]
            for top_k in hits:
                if expected.intersection(returned[:top_k]):
                    hits[top_k] += 1
                else:
                    misses[top_k].append(case["id"])
                    if top_k == 5:
                        miss_details.append(f"{case['id']} -> {', '.join(returned)}")

    for top_k, hit_count in hits.items():
        percentage = hit_count / len(retrieval_cases) * 100
        print(f"Recall@{top_k}: {percentage:.1f}% ({hit_count}/{len(retrieval_cases)})")
        print(f"Misses@{top_k}: {', '.join(misses[top_k]) or 'none'}")
    if miss_details:
        print("Miss details@5:")
        for detail in miss_details:
            print(f"  {detail}")
    print(
        f"Abstention and safety cases: {len(cases) - len(retrieval_cases)} "
        "(generation is evaluated separately)."
    )


if __name__ == "__main__":
    main()
