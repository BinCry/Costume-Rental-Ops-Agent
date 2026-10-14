from pathlib import Path

from app.knowledge.validator import validate_knowledge_base


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = project_root.parents[1]
    validate_workspace_sources = (workspace_root / "apps" / "api").is_dir()
    result = validate_knowledge_base(
        kb_root=project_root / "knowledge-base",
        query_file=project_root / "tests" / "retrieval" / "knowledge-base-queries.jsonl",
        project_root=project_root,
        workspace_root=workspace_root,
        validate_workspace_source_existence=validate_workspace_sources,
    )
    if result.failures:
        raise SystemExit("\n".join(result.failures))
    print(
        "Static knowledge-base lint passed: "
        f"{result.retrievable_count} retrievable documents, "
        f"{result.query_count} eval cases."
    )
    if not validate_workspace_sources:
        print(
            "Workspace source existence checks skipped: "
            "Studio API is not present in this standalone checkout."
        )


if __name__ == "__main__":
    main()
