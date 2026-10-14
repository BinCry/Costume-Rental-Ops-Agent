import hashlib
import os
import re
from pathlib import Path
from typing import Any, cast

import yaml

from app.knowledge.types import (
    ALLOWED_AUDIENCES,
    ALLOWED_STATUSES,
    DocumentAudience,
    DocumentStatus,
    KnowledgeChunk,
    KnowledgeDocument,
)

MAX_CHUNK_CHARACTERS = 1_800
CHUNK_OVERLAP_CHARACTERS = 260


def _front_matter(raw: str, label: str) -> tuple[dict[str, Any], str]:
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", raw, flags=re.DOTALL)
    if match is None:
        raise ValueError(f"{label}: missing front matter")
    loaded = yaml.safe_load(match.group(1))
    if not isinstance(loaded, dict):
        raise ValueError(f"{label}: front matter must be an object")
    return cast(dict[str, Any], loaded), match.group(2)


def _required_string(metadata: dict[str, Any], key: str, label: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label}: missing {key}")
    return value


def _required_bool(metadata: dict[str, Any], key: str, label: str) -> bool:
    value = metadata.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{label}: {key} must be boolean")
    return value


def parse_document(raw: str, source_path: str) -> KnowledgeDocument:
    metadata, body = _front_matter(raw, source_path)
    audience = _required_string(metadata, "audience", source_path)
    status = _required_string(metadata, "status", source_path)
    if audience not in ALLOWED_AUDIENCES:
        raise ValueError(f"{source_path}: unsupported audience")
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"{source_path}: unsupported status")
    retrieval_enabled = _required_bool(metadata, "retrieval_enabled", source_path)
    if audience == "internal" and retrieval_enabled:
        raise ValueError(f"{source_path}: internal documents must have retrieval_enabled: false")

    return KnowledgeDocument(
        document_id=_required_string(metadata, "id", source_path),
        title=_required_string(metadata, "title", source_path),
        domain=_required_string(metadata, "domain", source_path),
        status=cast(DocumentStatus, status),
        business_authority=_required_bool(metadata, "business_authority", source_path),
        audience=cast(DocumentAudience, audience),
        retrieval_enabled=retrieval_enabled,
        source_path=source_path,
        body=body.strip(),
    )


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _split_long_text(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARACTERS:
        return [text]
    paragraphs = [part for part in re.split(r"\n{2,}", text) if part]
    chunks: list[str] = []
    current = ""
    step = MAX_CHUNK_CHARACTERS - CHUNK_OVERLAP_CHARACTERS
    for paragraph in paragraphs:
        if len(paragraph) > MAX_CHUNK_CHARACTERS:
            if current:
                chunks.append(current)
            current = ""
            chunks.extend(
                paragraph[cursor : cursor + MAX_CHUNK_CHARACTERS]
                for cursor in range(0, len(paragraph), step)
            )
            continue
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= MAX_CHUNK_CHARACTERS:
            current = candidate
            continue
        chunks.append(current)
        current = paragraph
    if current:
        chunks.append(current)
    return chunks


def _sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    for line in _normalize(body).split("\n"):
        heading = re.match(r"^#{2,3}\s+(.+)$", line)
        if heading is not None:
            if current is not None:
                sections.append(current)
            current = (heading.group(1).strip(), [])
        elif current is not None:
            current[1].append(line)
    if current is not None:
        sections.append(current)
    return [
        (heading, normalized)
        for heading, lines in sections
        if (normalized := _normalize("\n".join(lines)))
    ]


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def chunk_document(document: KnowledgeDocument) -> list[KnowledgeChunk]:
    if (
        not document.retrieval_enabled
        or document.status == "deprecated"
        or document.audience == "internal"
    ):
        return []
    chunks: list[KnowledgeChunk] = []
    for heading, section_text in _sections(document.body):
        for text in _split_long_text(section_text):
            chunk_index = len(chunks)
            content = f"{document.title} — {heading}\n\n{text}"
            chunks.append(
                KnowledgeChunk(
                    chunk_id=_sha256(f"{document.document_id}\0{heading}\0{chunk_index}"),
                    document_id=document.document_id,
                    title=document.title,
                    heading=heading,
                    citation_label=f"{document.title} — {heading}",
                    domain=document.domain,
                    status=document.status,
                    business_authority=document.business_authority,
                    audience=document.audience,
                    content=content,
                    content_hash=_sha256(content),
                    chunk_index=chunk_index,
                )
            )
    return chunks


def load_documents(root: Path) -> list[KnowledgeDocument]:
    resolved_root = root.resolve(strict=True)
    documents: list[KnowledgeDocument] = []
    for directory, directory_names, file_names in os.walk(resolved_root, followlinks=False):
        directory_path = Path(directory)
        for name in [*directory_names, *file_names]:
            if (directory_path / name).is_symlink():
                raise ValueError(f"Knowledge base rejects symbolic link: {directory_path / name}")
        for name in sorted(file_names):
            path = directory_path / name
            if path.suffix.lower() != ".md":
                continue
            source_path = path.relative_to(resolved_root).with_suffix("").as_posix()
            documents.append(parse_document(path.read_text(encoding="utf-8"), source_path))
    return documents
