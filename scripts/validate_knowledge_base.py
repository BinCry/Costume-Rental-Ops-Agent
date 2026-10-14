from pathlib import Path

from app.knowledge.validator import validate_knowledge_base


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    result = validate_knowledge_base(
        kb_root=project_root / "knowledge-base",
        query_file=project_root / "tests" / "retrieval" / "knowledge-base-queries.jsonl",
        project_root=project_root,
        workspace_root=project_root.parents[1],
    )
    if result.failures:
        raise SystemExit("\n".join(result.failures))
    print(
        "Static knowledge-base lint passed: "
        f"{result.retrievable_count} retrievable documents, "
        f"{result.query_count} eval cases."
    )


if __name__ == "__main__":
    main()
