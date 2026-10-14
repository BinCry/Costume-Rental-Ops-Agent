---
date: 2026-10-13
session: fastapi-api-contract-alignment
type: technical-journal
scope: costume-rental-ops-agent
tags: [fastapi, api-contract, error-handling, cors, openapi, gateway]
---

# Journal: 2026-10-13 — FastAPI API contract alignment

## Context

The Python AI service needed to follow the public API conventions already used by `apps/api` without copying Express-specific implementation patterns. The alignment focused on stable response envelopes, predictable errors, request tracing, CORS, and an OpenAPI contract that matches runtime authentication.

## What Happened

- Added typed generic success responses and a shared error response model with camelCase JSON aliases.
- Declared concrete response models for knowledge search and answer routes so FastAPI and OpenAPI expose the actual payload shape.
- Standardized application, validation, malformed JSON, HTTP 404/405, and unexpected exception responses through the common error envelope.
- Preserved and returned `X-Request-Id` across both successful and failed requests; retained HTTP headers such as `Allow` on method errors.
- Kept browser origins configurable and restricted CORS methods and headers to the service's intended surface.
- Added database readiness separately from the lightweight liveness endpoint.
- Corrected OpenAPI knowledge-route security: answer requires the internal service key and permits guest customer access, while search also requires bearer authentication. Removed FastAPI's generated `422` responses because runtime validation is normalized to `400`.
- Review found and fixed three contract gaps: whitespace-only queries previously passed minimum-length validation, malformed JSON was indistinguishable from field validation, and generated OpenAPI security did not reflect the route-level/internal dependency combination.
- Review also verified fail-closed behavior: an invalid supplied credential is rejected and never downgraded to a guest request.

## Verification

- Python test suite: **67 pytest tests passed**.
- Python static checks: **Ruff passed** and **mypy passed**.
- Studio API gateway: **9 knowledge route/service tests passed**, covering guest and authenticated forwarding, internal service authentication, validation, timeouts, upstream failures, malformed responses, and response-size protection.
- The broader `apps/api` typecheck still reports an unrelated pre-existing payment-module type error; it is outside this API-contract change.

## Reflection

Sharing an API contract does not require sharing framework mechanics. Pydantic response models and FastAPI exception handlers now produce the same externally observable conventions as the Express gateway, while each service retains idiomatic internals. Explicit contract tests were especially useful because default FastAPI validation and OpenAPI behavior otherwise diverged silently from runtime expectations.

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Treat `apps/api` as the external contract authority | It is the frontend-facing gateway | Python responses, errors, names, and tracing remain compatible with gateway consumers |
| Use Pydantic generics and typed route responses | Hand-built dictionaries drift and weaken generated documentation | Runtime serialization and OpenAPI now share one schema |
| Normalize validation to HTTP 400 | Matches the gateway contract rather than FastAPI's default 422 | Clients handle validation consistently across services |
| Keep citations and knowledge results inside the shared success envelope | Preserves the existing gateway response shape | No frontend-specific translation is required |
| Make answer auth optional but validate any supplied credential | Guests are supported, but invalid credentials must not weaken authorization | Public customer access remains safe and deterministic |
| Keep CORS narrow and configurable | The gateway is the normal browser entry point | Direct AI-service exposure is limited without hard-coding environments |

## Next Steps

- Add an automated cross-service contract check if the gateway or AI schemas evolve independently.
- Resolve the unrelated payment-module TypeScript error before requiring a clean repository-wide `apps/api` typecheck.
- Keep the AI service private in deployment and route browser traffic through `apps/api`.
