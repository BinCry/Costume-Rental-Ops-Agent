---
date: 2026-10-13
session: approved-core-policy
type: technical-journal
scope: costume-rental-ops-agent
tags: [knowledge-base, policy, authority, rag, pgvector, safety]
---

# Journal: 2026-10-13 — Approved core policy

## Context

Phase 5 turned the explicitly accepted `POLICY-2025` core seed and runtime-enforced refund rules into authoritative RAG knowledge. The goal was to answer supported fee, timing, refund, and approval questions while preserving abstention for business decisions that still have no approved source.

## What Happened

- Set a narrow approval boundary: the core seed is authoritative for `POLICY-2025`, seeded RBAC is authoritative for the documented roles, and runtime checks are authoritative for deposit-refund eligibility. Demo seed data is excluded.
- Published `rental-policy-2025.md` and `roles-and-permissions.md` as `approved` with `business_authority: true` and updated payment/refund, FAQ, gap, glossary, and index documents to reference the approved scope accurately.
- Kept order-specific deadlines dynamic: the Agent must use the order's `plannedDueAt`, not invent one universal due date from the maximum rental duration.
- Preserved the deterministic authority filter. Policy or commitment answers require retrieved approved business-authority chunks; verified technical documents alone cannot authorize them.
- Hardened answer sanitization so model-generated citation appendices, including Vietnamese variants such as “Nguồn tham khảo,” are removed. Structured API sources remain the only citations returned to clients.
- Re-ingested the reviewed knowledge base into pgvector with 97 active chunks.
- Retrieval evaluation reached Recall@1 79.2%, Recall@3 95.8%, and Recall@5 100% across 48 queries.
- Validation and review passed: 52 pytest cases, Ruff, mypy across 21 production files, and the knowledge validator across 14 documents and 56 cases.
- Live RAG checks returned non-provisional answers for approved late-return fees, deposit-refund conditions, and refund approval roles, while unsupported damage-compensation amounts still returned `insufficient_context`.

## Reflection

Seed data can become a valid business source only through an explicit ownership decision and a bounded scope. Treating the whole seed or all implemented behavior as automatically approved would blur policy, configuration, and technical enforcement. The combination of metadata validation, deterministic authority filtering, retrieval tests, and answer sanitization keeps that boundary observable and testable.

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Approve only the confirmed core seed and matched runtime rules | Seed values are not inherently policy; approval must identify the exact source and scope | Supported policy questions can now be answered with `provisional: false` |
| Keep `approved` separate from `verified_from_system` | Technical truth does not grant business authority | Workflow explanations remain useful without authorizing unsupported commitments |
| Require approved business-authority evidence at answer time | Retrieval may contain nearby but non-authoritative chunks | Policy answers fail closed when authoritative evidence is absent |
| Sanitize generated citation sections | The LLM must not fabricate or duplicate references | Consumers receive only API-controlled structured sources |
| Re-index after material metadata or content changes | Authority metadata affects filtering and answer eligibility | Pgvector now reflects the reviewed Phase 5 corpus |

## Next Steps

- Obtain separate business decisions for damage or loss compensation, exceptional waivers, extension fees, transfer costs, and cleaning or repair service levels.
- Read active policy and order-specific values through tools or APIs when they can change at runtime; use RAG for definitions, rules, and provenance.
- Re-run validation, ingestion, retrieval evaluation, and live safety checks after every approved policy change.
- Monitor production paraphrases and add regression cases before broadening the authority filter.
