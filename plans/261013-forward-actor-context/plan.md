---
title: Forward trusted actor context to AI service
status: completed
priority: P1
effort: medium
branch: main
created: 2026-10-13
tags: [authentication, authorization, service-to-service, rag]
---

# Forward trusted actor context to AI service

## Goal

Authenticate users once in `apps/api`, then forward a minimal trusted actor
context to the private AI service instead of forwarding the JWT and calling
back to `/api/v1/auth/me`.

## Acceptance criteria

- Guest, customer, and authorized staff retain their existing knowledge audiences.
- Invalid JWTs are rejected by `apps/api` before the AI service is called.
- The AI proxy sends actor headers and never forwards the browser JWT.
- The AI service validates actor headers and no longer calls Studio auth.
- Public knowledge request and response payloads remain unchanged.
- Tests, lint, and source type checks pass in both touched services.

## Out of scope

- JWT issuance or algorithms.
- RBAC schema and permissions.
- Retrieval, embeddings, prompting, and LLM behavior.
- Database changes and new environment variables.

## Steps

- [x] Derive knowledge actor context in the Studio API.
- [x] Forward actor headers through the internal proxy.
- [x] Replace AI auth callback with trusted-header validation.
- [x] Update OpenAPI and regression tests.
- [x] Run review and verification gates.

## Completion

Completed on 2026-10-13. Studio API is now the only component that authenticates
the browser JWT. It forwards a minimal trusted actor context over the protected
service-to-service channel, and the AI service validates that context before
selecting retrieval audiences.
