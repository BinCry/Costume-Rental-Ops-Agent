from pathlib import Path

from app.knowledge.chunker import chunk_document, load_documents


def test_current_knowledge_base_produces_expected_chunks() -> None:
    root = Path(__file__).resolve().parents[1] / "knowledge-base"
    documents = load_documents(root)
    chunks = [chunk for document in documents for chunk in chunk_document(document)]

    assert len(documents) == 15
    assert len(chunks) >= 91
    assert {chunk.audience for chunk in chunks} <= {"customer", "staff_internal", "shared"}
    assert all(len(chunk.content) <= 2_500 for chunk in chunks)
    assert any(chunk.status == "verified_from_system" for chunk in chunks)
    assert any(chunk.status == "approved" and chunk.business_authority for chunk in chunks)


def test_internal_index_is_not_retrievable() -> None:
    root = Path(__file__).resolve().parents[1] / "knowledge-base"
    index = next(
        document for document in load_documents(root) if document.document_id == "kb-index"
    )

    assert chunk_document(index) == []
