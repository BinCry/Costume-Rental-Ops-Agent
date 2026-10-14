---
date: 2026-10-11
type: technical-journal
scope: costume-rental-ops-agent
tags: [knowledge-base, rag, documentation]
---

# Knowledge base and RAG session

## Context

The knowledge base is intended to support customer-facing and staff-facing operational answers. Initial content was derived from the current implementation, so it needed clear limits: source code can describe system capability but cannot establish business policy.

## What happened

- Reworked knowledge-base language toward plain Vietnamese business terms.
- Removed API endpoints, implementation names, and tool-call details from retrievable operational documents; technical integration material belongs in `docs/tools-and-integrations.md`.
- Added source and usage metadata so code-derived content is identifiable as non-authoritative for fees, deadlines, conditions, and permissions.
- Excluded the index from retrieval and documented ingestion boundaries: ingest `knowledge-base/` only, separate front matter as metadata, and do not index source paths.
- Added a retrieval query dataset and documented the intended retrieval metrics and static knowledge-base validation.
- Added a customer-only return and inspection FAQ so customer questions do not retrieve the staff procedure.
- Standardized provenance URIs with `workspace://`, `project://`, and `kb://`; expanded the evaluation set to 50 retrieval, abstention, and safety cases.

## Decisions

1. **Business knowledge and technical instructions are separate.** RAG content explains what staff or customers need to know; the tool registry and integration document explain how the Agent obtains live data or performs approved actions.
2. **Live facts require tools.** A general document cannot confirm the present state of a rental, payment, refund, or costume.
3. **Code is traceability, not policy authority.** Only approved business sources may support definitive claims about money, timing, eligibility, or decision rights.
4. **Retrieval needs evaluation, not just longer documents.** Each topic should contain common phrasings, checks, exceptions, escalation boundaries, and safe answer guidance; results must be measured with the query set on the real pipeline.

## Validation

- Reviewed the remaining knowledge-base documents for customer-facing language and absence of API/endpoint content.
- Confirmed `00-index.md` is marked `retrieval_enabled: false`.
- Confirmed RAG ingestion and safety guidance is recorded in `docs/tools-and-integrations.md` and `docs/evaluation-and-safety.md`.
- Static validation can verify metadata, audience boundaries, and expected-document mappings. Retrieval quality is not yet validated because no running ingestion, embedding, vector search, or Recall@k measurement exists.
- The hardened validator reports 13 retrievable documents and 50 evaluation cases. Seven regression tests cover approval metadata, disabled documents, duplicate IDs, technical leakage, malformed input, and source-path safety.

## Remaining blocker

Approved business policies are still required before the Agent can state rules about pricing, deposits, refunds, lateness, eligibility, service times, or staff authority. Those policies need an accountable owner, approval date, effective scope, and `source_type: business_approved` / `business_authority: true` before they become authoritative RAG content.

## Next

1. Obtain and ingest approved policy documents.
2. Implement the RAG pipeline and enforce `audience` plus `retrieval_enabled` filters at query time.
3. Run the retrieval dataset against that pipeline to establish Recall@3/Recall@5, citation, prompt-injection, and answer-safety baselines.
