---
title: Forward actor context completion report
status: completed
created: 2026-10-13
---

# Forward actor context completion report

## Summary

The Studio API now authenticates the user once and forwards only trusted actor
identity and retrieval audiences to the private AI service. The browser JWT is
not forwarded and the AI service no longer calls back to `/auth/me`.

## Results

| Area | Result |
|---|---|
| Guest access | `customer` and `shared` audiences |
| Customer access | `customer` and `shared` audiences |
| Authorized staff access | `staff_internal` and `shared` audiences |
| Invalid JWT | Rejected by Studio API before proxying |
| Internal trust | `X-AI-Service-Key` plus validated actor headers |
| Branch-bound `ALL` permission | Does not grant global knowledge access |
| Public payload contract | Unchanged |

## Verification

- Studio API focused tests: 23 passed.
- Studio API full tests: 236 passed, 14 skipped.
- AI-service auth and route tests: 22 passed.
- AI-service full tests: 71 passed.
- Python Ruff and mypy: passed.
- Targeted Studio API ESLint: passed.
- Independent security and contract review: passed.

The full Studio API typecheck still reports pre-existing errors in
`payment.service.ts` for a missing `transactionReference` field. Those errors
are unrelated to this change.

## Unresolved questions

None for this scope.
