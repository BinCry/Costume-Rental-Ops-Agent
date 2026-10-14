import json
from collections.abc import Callable
from pathlib import Path

from app.knowledge.validator import ValidationResult, validate_knowledge_base

VALID_DOCUMENT = """---
id: sample-doc
title: Tài liệu mẫu
document_type: guide
domain: rental
status: draft_from_code
version: 0.1
source_type: technical_implementation
business_authority: false
retrieval_enabled: true
audience: shared
chunk_title_prefix: true
usage_limit: "Chỉ dùng để kiểm thử."
source:
  - project://source.md
---

# Tài liệu mẫu

Nội dung dễ hiểu dành cho người dùng.
"""


def fixture(
    tmp_path: Path,
    *,
    document: str = VALID_DOCUMENT,
    disabled_document: str | None = None,
    query_transform: Callable[[list[dict[str, object]]], list[object]] | None = None,
    validate_workspace_source_existence: bool = True,
) -> ValidationResult:
    project_root = tmp_path / "project"
    kb_root = project_root / "knowledge-base"
    kb_root.mkdir(parents=True)
    (project_root / "source.md").write_text("# Nguồn", encoding="utf-8")
    (kb_root / "sample.md").write_text(document, encoding="utf-8")
    if disabled_document is not None:
        (kb_root / "disabled.md").write_text(disabled_document, encoding="utf-8")

    queries: list[dict[str, object]] = [
        {
            "id": f"Q{index + 1}",
            "query": f"Câu hỏi {index + 1}",
            "audience": "customer",
            "test_type": "retrieval",
            "expected_documents": ["sample"],
            "expected_behavior": "Trả lời từ tài liệu mẫu.",
        }
        for index in range(40)
    ]
    output = query_transform(queries) if query_transform else list(queries)
    query_file = project_root / "queries.jsonl"
    query_file.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in output) + "\n",
        encoding="utf-8",
    )
    return validate_knowledge_base(
        kb_root=kb_root,
        query_file=query_file,
        project_root=project_root,
        workspace_root=tmp_path,
        validate_workspace_source_existence=validate_workspace_source_existence,
    )


def test_validator_accepts_valid_fixture(tmp_path: Path) -> None:
    result = fixture(tmp_path)

    assert result.failures == []
    assert result.retrievable_count == 1


def test_validator_accepts_system_verified_technical_document(tmp_path: Path) -> None:
    document = VALID_DOCUMENT.replace("status: draft_from_code", "status: verified_from_system")

    assert fixture(tmp_path, document=document).failures == []


def test_validator_rejects_system_verified_internal_draft(tmp_path: Path) -> None:
    document = VALID_DOCUMENT.replace("status: draft_from_code", "status: verified_from_system")
    document = document.replace(
        "source_type: technical_implementation", "source_type: internal_draft"
    )
    failures = "\n".join(fixture(tmp_path, document=document).failures)

    assert "verified_from_system requires technical or derived sources" in failures


def test_validator_rejects_verified_derived_document_with_unverified_source(
    tmp_path: Path,
) -> None:
    document = VALID_DOCUMENT.replace("status: draft_from_code", "status: verified_from_system")
    document = document.replace(
        "source_type: technical_implementation", "source_type: derived_knowledge_base"
    )
    document = document.replace("project://source.md", "kb://disabled.md")
    dependency = VALID_DOCUMENT.replace("id: sample-doc", "id: unverified-doc")
    dependency = dependency.replace(
        "status: draft_from_code", "status: needs_business_confirmation"
    )
    dependency = dependency.replace(
        "source_type: technical_implementation", "source_type: internal_draft"
    )
    dependency = dependency.replace("retrieval_enabled: true", "retrieval_enabled: false")
    dependency = dependency.replace("audience: shared", "audience: internal")

    failures = "\n".join(
        fixture(tmp_path, document=document, disabled_document=dependency).failures
    )

    assert "verified derived document depends on unverified source disabled" in failures


def test_validator_rejects_chunk_prefix_and_technical_leakage(tmp_path: Path) -> None:
    document = VALID_DOCUMENT.replace("chunk_title_prefix: true", "chunk_title_prefix: false")
    document = document.replace(
        "Nội dung dễ hiểu dành cho người dùng.",
        "Gọi api endpoint để xử lý.",
    )
    failures = "\n".join(fixture(tmp_path, document=document).failures)

    assert "chunk_title_prefix must be true" in failures
    assert "technical implementation term" in failures


def test_validator_requires_approval_provenance(tmp_path: Path) -> None:
    document = VALID_DOCUMENT.replace("status: draft_from_code", "status: approved")
    document = document.replace(
        "source_type: technical_implementation",
        "source_type: business_approved",
    )
    document = document.replace("business_authority: false", "business_authority: true")
    failures = "\n".join(fixture(tmp_path, document=document).failures)

    assert "approved documents require approved_by" in failures
    assert "approved documents require approved_at" in failures
    assert "approved documents require effective_from" in failures


def test_validator_rejects_duplicate_document_ids(tmp_path: Path) -> None:
    disabled = VALID_DOCUMENT.replace("retrieval_enabled: true", "retrieval_enabled: false")
    disabled = disabled.replace("audience: shared", "audience: internal")
    failures = "\n".join(fixture(tmp_path, disabled_document=disabled).failures)

    assert "duplicate document id sample-doc" in failures


def test_validator_rejects_eval_targeting_disabled_document(tmp_path: Path) -> None:
    disabled = VALID_DOCUMENT.replace("id: sample-doc", "id: disabled-doc")
    disabled = disabled.replace("retrieval_enabled: true", "retrieval_enabled: false")
    disabled = disabled.replace("audience: shared", "audience: internal")

    def transform(queries: list[dict[str, object]]) -> list[object]:
        queries[0] = {**queries[0], "expected_documents": ["disabled"]}
        return list(queries)

    failures = "\n".join(
        fixture(tmp_path, disabled_document=disabled, query_transform=transform).failures
    )

    assert "document is not retrievable disabled" in failures


def test_validator_rejects_escaping_source(tmp_path: Path) -> None:
    document = VALID_DOCUMENT.replace("project://source.md", "project://../outside.md")
    failures = "\n".join(fixture(tmp_path, document=document).failures)

    assert "source escapes its declared root" in failures


def test_validator_can_skip_missing_workspace_sources_in_standalone_checkout(
    tmp_path: Path,
) -> None:
    document = VALID_DOCUMENT.replace(
        "project://source.md",
        "workspace://apps/api/prisma/schema.prisma",
    )

    result = fixture(
        tmp_path,
        document=document,
        validate_workspace_source_existence=False,
    )

    assert result.failures == []


def test_validator_handles_invalid_source_and_query_values(tmp_path: Path) -> None:
    document = VALID_DOCUMENT.replace("project://source.md", "true")

    def transform(queries: list[dict[str, object]]) -> list[object]:
        return [None, *queries[1:]]

    failures = "\n".join(fixture(tmp_path, document=document, query_transform=transform).failures)

    assert "every source entry must be a string" in failures
    assert "each case must be a JSON object" in failures
