import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from app.knowledge.types import ALLOWED_AUDIENCES, ALLOWED_STATUSES

ALLOWED_SOURCE_TYPES = {
    "business_approved",
    "technical_implementation",
    "internal_draft",
    "derived_knowledge_base",
}
ALLOWED_TEST_TYPES = {"retrieval", "abstention", "safety"}
ALLOWED_FIELDS = {
    "id",
    "title",
    "document_type",
    "domain",
    "status",
    "version",
    "source_type",
    "business_authority",
    "retrieval_enabled",
    "audience",
    "chunk_title_prefix",
    "usage_limit",
    "source",
    "approved_by",
    "approved_at",
    "effective_from",
}
REQUIRED_FIELDS = {
    "id",
    "title",
    "document_type",
    "domain",
    "status",
    "version",
    "source_type",
    "business_authority",
    "retrieval_enabled",
    "audience",
    "chunk_title_prefix",
    "usage_limit",
    "source",
}
FORBIDDEN_BODY_TERMS = re.compile(
    r"\b(api|endpoint|graphql|database|rentalorder|rentalorderitem|costumeunit|expectedversion)\b"
    r"|\b(?:get|post|put|patch|delete)\s+/|https?://|/api/|```(?:json|jsx?|tsx?|typescript|sql)?",
    re.IGNORECASE,
)
SOURCE_PATTERN = re.compile(r"^(workspace|project|kb)://(.+)$")
FRONT_MATTER_PATTERN = re.compile(
    r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$",
    re.DOTALL,
)


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ValueError("front matter keys must be strings")
        if key in mapping:
            raise ValueError(f"duplicate metadata field {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True)
class ValidationResult:
    failures: list[str]
    retrievable_count: int
    query_count: int


def _list_markdown(root: Path) -> list[Path]:
    files: list[Path] = []
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        for name in [*directory_names, *file_names]:
            path = directory_path / name
            if path.is_symlink():
                raise ValueError(f"{path}: symbolic links are not allowed")
        files.extend(
            directory_path / name for name in file_names if Path(name).suffix.lower() == ".md"
        )
    return sorted(files)


def _parse_document(path: Path) -> tuple[dict[str, Any], str]:
    match = FRONT_MATTER_PATTERN.match(path.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"{path}: missing front matter")
    try:
        metadata = yaml.load(match.group(1), Loader=UniqueKeyLoader)
    except (yaml.YAMLError, ValueError) as error:
        raise ValueError(f"{path}: invalid front matter: {error}") from error
    if not isinstance(metadata, dict):
        raise ValueError(f"{path}: front matter must be an object")
    return cast(dict[str, Any], metadata), match.group(2)


def _source_path(root: Path, file: Path) -> str:
    return file.relative_to(root).with_suffix("").as_posix()


def _validate_source(
    source: object,
    roots: dict[str, Path],
    label: str,
    failures: list[str],
    *,
    validate_workspace_source_existence: bool,
) -> None:
    if not isinstance(source, str):
        failures.append(f"{label}: every source entry must be a string")
        return
    match = SOURCE_PATTERN.match(source)
    if match is None:
        failures.append(f"{label}: source must use workspace://, project://, or kb://")
        return
    kind, relative_path = match.groups()
    base = roots[kind].resolve()
    target = (base / relative_path).resolve()
    if target == base or not target.is_relative_to(base):
        failures.append(f"{label}: source escapes its declared root: {source}")
    elif not target.exists() and (kind != "workspace" or validate_workspace_source_existence):
        failures.append(f"{label}: source does not exist: {source}")


def validate_knowledge_base(
    *,
    kb_root: Path,
    query_file: Path,
    project_root: Path,
    workspace_root: Path,
    validate_workspace_source_existence: bool = True,
) -> ValidationResult:
    kb_root = kb_root.resolve()
    roots = {
        "workspace": workspace_root.resolve(),
        "project": project_root.resolve(),
        "kb": kb_root,
    }
    failures: list[str] = []
    all_documents: dict[str, dict[str, Any]] = {}
    retrievable_documents: dict[str, dict[str, Any]] = {}
    seen_document_ids: set[object] = set()

    try:
        files = _list_markdown(kb_root)
    except (OSError, ValueError) as error:
        return ValidationResult([str(error)], 0, 0)

    for file in files:
        label = _source_path(kb_root, file)
        try:
            metadata, body = _parse_document(file)
        except (OSError, ValueError) as error:
            failures.append(str(error))
            continue

        for key in metadata:
            if key not in ALLOWED_FIELDS:
                failures.append(f"{label}: unknown metadata field {key}")
        for field in REQUIRED_FIELDS:
            if field not in metadata or metadata[field] == "":
                failures.append(f"{label}: missing {field}")

        document_id = metadata.get("id")
        if document_id:
            if document_id in seen_document_ids:
                failures.append(f"{label}: duplicate document id {document_id}")
            seen_document_ids.add(document_id)
        if metadata.get("audience") not in ALLOWED_AUDIENCES:
            failures.append(f"{label}: invalid audience")
        if metadata.get("status") not in ALLOWED_STATUSES:
            failures.append(f"{label}: invalid status")
        if metadata.get("source_type") not in ALLOWED_SOURCE_TYPES:
            failures.append(f"{label}: invalid source_type")
        if not isinstance(metadata.get("business_authority"), bool):
            failures.append(f"{label}: business_authority must be a boolean")
        if not isinstance(metadata.get("retrieval_enabled"), bool):
            failures.append(f"{label}: retrieval_enabled must be a boolean")
        if metadata.get("chunk_title_prefix") is not True:
            failures.append(f"{label}: chunk_title_prefix must be true")

        sources = metadata.get("source")
        if not isinstance(sources, list) or not sources:
            failures.append(f"{label}: source must be a non-empty list")
        else:
            for source in sources:
                _validate_source(
                    source,
                    roots,
                    label,
                    failures,
                    validate_workspace_source_existence=validate_workspace_source_existence,
                )

        if metadata.get("status") == "approved":
            if (
                metadata.get("source_type") != "business_approved"
                or metadata.get("business_authority") is not True
            ):
                failures.append(
                    f"{label}: approved documents require business_approved source "
                    "and business_authority true"
                )
            for field in ("approved_by", "approved_at", "effective_from"):
                if not metadata.get(field):
                    failures.append(f"{label}: approved documents require {field}")
        elif metadata.get("business_authority") is True:
            failures.append(f"{label}: business_authority true requires approved status")

        if metadata.get("status") == "verified_from_system" and metadata.get(
            "source_type"
        ) not in {"technical_implementation", "derived_knowledge_base"}:
            failures.append(
                f"{label}: verified_from_system requires technical or derived sources"
            )

        if (
            metadata.get("retrieval_enabled") is True
            and metadata.get("audience") != "internal"
            and FORBIDDEN_BODY_TERMS.search(body)
        ):
            failures.append(f"{label}: technical implementation term found in retrievable body")

        all_documents[label] = metadata
        if (
            metadata.get("retrieval_enabled") is True
            and metadata.get("audience") != "internal"
            and metadata.get("status") != "deprecated"
        ):
            retrievable_documents[label] = metadata

    trusted_derived_statuses = {"approved", "verified_from_system"}
    for label, metadata in all_documents.items():
        if not (
            metadata.get("status") == "verified_from_system"
            and metadata.get("source_type") == "derived_knowledge_base"
        ):
            continue
        sources = metadata.get("source")
        if not isinstance(sources, list):
            continue
        for source in sources:
            if not isinstance(source, str) or not source.startswith("kb://"):
                continue
            dependency = source.removeprefix("kb://")
            if dependency.endswith(".md"):
                dependency = dependency[:-3]
            dependency_metadata = all_documents.get(dependency)
            if dependency_metadata is None:
                continue
            if dependency_metadata.get("status") not in trusted_derived_statuses:
                failures.append(
                    f"{label}: verified derived document depends on unverified source {dependency}"
                )

    try:
        query_lines = [
            line for line in query_file.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
    except OSError as error:
        failures.append(f"{query_file}: {error}")
        query_lines = []

    seen_query_ids: set[object] = set()
    covered_documents: set[str] = set()
    for index, line in enumerate(query_lines, start=1):
        try:
            query = json.loads(line)
        except json.JSONDecodeError:
            failures.append(f"query line {index}: invalid JSON")
            continue
        if not isinstance(query, dict):
            failures.append(f"query line {index}: each case must be a JSON object")
            continue

        query_id = query.get("id")
        test_type = query.get("test_type", "retrieval")
        expected = query.get("expected_documents")
        expected_documents = expected if isinstance(expected, list) else []
        if not query_id or query_id in seen_query_ids:
            failures.append(f"query line {index}: missing or duplicate id")
        if query_id:
            seen_query_ids.add(query_id)
        if (
            not query.get("query")
            or not query.get("expected_behavior")
            or not isinstance(expected, list)
        ):
            failures.append(f"query {query_id or index}: missing required expectation fields")
        if test_type not in ALLOWED_TEST_TYPES:
            failures.append(f"query {query_id}: invalid test_type")
        if query.get("audience") not in {"customer", "staff_internal"}:
            failures.append(f"query {query_id}: invalid audience")
        if test_type == "retrieval" and not expected_documents:
            failures.append(f"query {query_id}: retrieval case requires expected_documents")
        if test_type == "abstention" and expected_documents:
            failures.append(f"query {query_id}: abstention case must not expect documents")

        for expected_path in expected_documents:
            if not isinstance(expected_path, str):
                failures.append(f"query {query_id}: expected document paths must be strings")
                continue
            document = retrievable_documents.get(expected_path)
            if document is None:
                reason = (
                    "document is not retrievable"
                    if expected_path in all_documents
                    else "unknown source path"
                )
                failures.append(f"query {query_id}: {reason} {expected_path}")
            elif document.get("audience") not in {"shared", query.get("audience")}:
                failures.append(
                    f"query {query_id}: {expected_path} is not available to {query.get('audience')}"
                )
            elif test_type == "retrieval":
                covered_documents.add(expected_path)

    for source_path in retrievable_documents:
        if source_path not in covered_documents:
            failures.append(f"{source_path}: no retrieval eval coverage")
    if len(query_lines) < 40:
        failures.append("knowledge-base eval requires at least 40 cases")

    return ValidationResult(failures, len(retrievable_documents), len(query_lines))
