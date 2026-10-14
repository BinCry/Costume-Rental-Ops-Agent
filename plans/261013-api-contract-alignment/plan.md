---
title: AI service API contract alignment
status: completed
priority: P1
effort: medium
created: 2026-10-13
tags: [fastapi, api-contract, error-handling, openapi]
---

# AI service API contract alignment

## Goal

Align the FastAPI knowledge service response and error contracts with the public
Express API without changing RAG, authentication, CORS, or health-check behavior.

## Acceptance criteria

- Knowledge success responses retain the `success`, `data`, and `message` envelope.
- Request validation failures use the shared error envelope and `VALIDATION_ERROR`.
- Unknown routes and unsupported methods use the shared error envelope.
- Every handled error includes `statusCode`, `timestamp`, `path`, and `requestId`.
- FastAPI OpenAPI exposes concrete response models for knowledge endpoints.
- Ruff, mypy, and all Python tests pass.

## Scope

- Update `app/models.py`, `app/knowledge/routes.py`, and `app/main.py`.
- Add or update API contract tests.
- Do not change retrieval, prompting, LLM providers, authentication rules, CORS,
  database schema, environment keys, or health endpoint payloads.

## Steps

- [x] Define typed success and error response envelopes.
- [x] Apply typed success responses to knowledge routes.
- [x] Normalize FastAPI validation and HTTP exceptions.
- [x] Add API contract coverage.
- [x] Run lint, type checking, and tests.

