---
title: Agent production release
date: 2026-10-15
status: completed
---

# Agent Production Release

## Context

Hoàn thiện single-agent synchronous runtime, apply database migrations và phát hành qua CI/CD.

## What happened

- Áp dụng thành công migrations `002–005`; lần chạy lại xác nhận checksum và idempotency.
- Thêm goal, business skill allowlist, bounded ReAct reads, guarded write workflow,
  confirmation/approval, read-back và structured handoff.
- Push Ops Agent và Studio API lên hai repository riêng.
- Pipeline Ops Agent phát hiện test helpers chưa đạt strict mypy vì local gate trước đó chỉ
  typecheck `app`; bổ sung annotations và chạy lại đúng lệnh CI trên `app scripts tests`.

## Decisions

- Write flags tiếp tục mặc định `false`; bật theo nhóm trong production environment sau smoke test.
- Transfer approval chỉ resume qua approval endpoint, không cho message planner gọi trực tiếp.
- CI verification local phải khớp hoàn toàn command trong workflow trước khi push.

## Next

- Xác nhận GitHub Actions publish và Coolify deploy thành công.
- Chạy production health/read-only smoke test trước khi bật từng write flag.
