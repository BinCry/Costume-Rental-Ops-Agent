---
title: Actor context authentication boundary
created: 2026-10-13
tags: [authentication, authorization, rag, service-to-service]
---

# Actor context authentication boundary

## Context

The initial knowledge flow forwarded the browser JWT to the AI service, which
then called Studio API `/auth/me`. That duplicated authentication and coupled
the AI service to the main API's user-session contract.

## What happened

Studio API became the single authentication boundary. After optional JWT
authentication, it derives a minimal actor context and sends the actor ID and
allowed knowledge audiences with the internal service key. The AI service now
validates those trusted headers and never receives the browser JWT.

Security review also identified that checking only the permission code could
allow a branch-bound `ALL` assignment to be treated as global. Actor derivation
now uses the canonical authorization helper, and a regression test covers this
case.

## Decisions

- Authenticate browser credentials only in Studio API.
- Protect the private hop with `X-AI-Service-Key`.
- Treat actor headers as trusted only after the service key succeeds.
- Permit exactly `customer,shared` or `staff_internal,shared` audience sets.
- Keep guest support in Studio API by forwarding an explicit guest context.
- Reject guest actors from the internal search endpoint.

## Impact

The flow has fewer network calls, one source of truth for JWT/RBAC behavior,
and an explicit authorization boundary for RAG retrieval. Public request and
response bodies remain unchanged.

## Next

Rotate the shared internal key through deployment secrets as normal and keep
the AI service private to the application network wherever possible.
