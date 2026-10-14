---
date: 2026-10-12
session: technical-knowledge-verification
type: technical-journal
scope: costume-rental-ops-agent
tags: [knowledge-base, provenance, rag, pgvector, safety]
---

# Journal: 2026-10-12 — Technical knowledge verification

## Context

The RAG service could retrieve code-derived documents, but treating every non-approved document as equally uncertain made useful system explanations abstain. The review needed a trust level for behavior verified against the implementation without promoting it to approved business policy.

## What Happened

- Added `verified_from_system` for operational facts confirmed against the current system and restricted it to technical or derived knowledge sources.
- Marked nine applicable documents as system-verified; kept fees, deadlines, permissions, exceptions, and other policy decisions unapproved.
- Prevented derived documents from inheriting trust from unapproved `kb://` dependencies.
- Added a deterministic, default-deny authority gate before LLM generation. Questions about money decisions, commitments, permissions, or policy still require an approved source with `business_authority: true`.
- Hardened Vietnamese query normalization and blocked paraphrased or composite requests that combine a safe explanation with an unsupported policy question.
- Removed model-generated reference appendices so the API remains the single source of structured citations.
- Re-ingested the knowledge base into pgvector: 93 chunks were upserted and 6 obsolete chunks removed.
- Retrieval evaluation reached Recall@1 77.3%, Recall@3 93.2%, and Recall@5 100% across 44 retrieval cases, with six separate abstention and safety cases.
- Static validation, lint, type checking, automated tests, and live RAG smoke checks passed. A system-status question produced a grounded provisional answer; a combined explanation-plus-late-fee question abstained.

## Reflection

The useful distinction is not “draft versus approved” alone. System behavior can be reliable enough for explanatory answers while still being insufficient authority for a business commitment. Enforcing that boundary in deterministic code is safer than relying on prompt wording, especially for paraphrases and mixed-intent questions.

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Introduce `verified_from_system` | Preserve verified technical knowledge without calling it approved policy | The Agent can explain current workflow and statuses provisionally |
| Keep `business_authority` independent from technical verification | Code does not establish fees, deadlines, eligibility, or decision rights | Unsupported business claims continue to abstain |
| Validate transitive knowledge provenance | A derived FAQ must not launder an unapproved dependency into a trusted answer | Trust remains traceable to direct approved or verified inputs |
| Apply a deterministic authority gate before the LLM | Prompt instructions alone were bypassable by paraphrased and composite questions | Safety behavior is testable and independent of model compliance |
| Replace pgvector rows through normal ingestion | Metadata and content changes alter chunk identity | The live index now matches the reviewed documents and removes stale chunks |

## Next Steps

- Obtain accountable business approval for fee, timing, refund, exception, and permission policies.
- Publish approved documents with owner, effective scope, approval date, and `business_authority: true`.
- Re-run validation, ingestion, retrieval evaluation, and answer-level safety tests after every policy approval or material knowledge change.
- Monitor production queries for new Vietnamese paraphrases and add them as regression cases before relaxing any authority gate.
