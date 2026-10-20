---
title: Readiness confirmation timestamp serialization fix
date: 2026-10-20
status: verified-locally
---

# Readiness Confirmation Timestamp Serialization Fix

## Context

Production Case 1 and Case 2 analysis completed, but confirmation preparation returned HTTP 500 after live context succeeded and before a confirmation row was inserted.

## What happened

- PostgreSQL returned `finding_source_observed_at` as a timezone-aware Python `datetime`.
- Readiness and overdue follow-up runtimes placed that value directly in a frozen action snapshot.
- Canonical `json.dumps` hashing rejected the non-JSON-native value.
- The runtime now converts the timestamp to an ISO string before hashing and rejects missing or invalid values with a controlled domain error.

## Reflection

Mocks had used a string timestamp, hiding the production psycopg data shape. Regression fixtures now use `datetime` and validate the JSON round-trip plus frozen-action hashes.

## Decisions

- Keep canonical hashing strict; do not use a broad `default=str` serializer.
- Normalize only the repository timestamp at the runtime boundary.
- Apply the same normalization to readiness and overdue follow-up confirmation paths.

## Next

- Commit and deploy the AI Agent.
- Re-run the production Case 1–5 E2E matrix and verify database cleanup.
