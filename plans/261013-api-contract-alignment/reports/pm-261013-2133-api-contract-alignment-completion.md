---
title: API contract alignment completion report
status: completed
created: 2026-10-13
---

# API contract alignment completion report

## Outcome

The FastAPI knowledge service now follows the Studio API response, error,
request-tracing, and OpenAPI contracts without changing RAG behavior,
authentication rules, CORS configuration, or health payloads.

## Completed work

- Typed success and error response envelopes with camelCase JSON fields.
- Typed `/search` and `/answer` responses in FastAPI/OpenAPI.
- Normalized validation, invalid JSON, 404, 405, and unhandled errors.
- Preserved `X-Request-Id` for successful and failed responses.
- Preserved protocol headers such as `Allow` on HTTP 405.
- Corrected OpenAPI security and removed default 422 documentation where runtime returns 400.
- Added contract regression tests and README documentation.

## Verification

| Check | Result |
| --- | --- |
| `uv run ruff check app tests` | Pass |
| `uv run ruff format --check` (touched files) | Pass |
| `uv run mypy app` | Pass, 15 files |
| `uv run pytest -q` | Pass, 67 tests |
| `apps/api` knowledge route/service tests | Pass, 9 tests |

## Unrelated follow-up

The full `apps/api` TypeScript typecheck still has existing errors in
`payment.service.ts` concerning a missing `transactionReference`. It was not
introduced by this work and is outside the knowledge API contract scope.
