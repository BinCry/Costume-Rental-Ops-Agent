---
phase: 4
title: "Rà soát kỹ thuật và tái lập chỉ mục knowledge base"
status: completed
priority: P1
effort: "2h"
dependencies: [1, 2, 3]
---

# Phase 4: Rà soát kỹ thuật và tái lập chỉ mục knowledge base

## Overview

Đối chiếu nội dung knowledge base với hành vi hiện có của Studio, phân biệt kiến thức đã
kiểm chứng từ hệ thống với chính sách đã được nghiệp vụ phê duyệt, rồi chunk và embed lại.

## Requirements

- Dùng ngôn ngữ nghiệp vụ dễ hiểu trong nội dung được retrieval.
- Không tự đặt mức phí, thời hạn, thẩm quyền hoặc ngoại lệ chưa được phê duyệt.
- Cho phép Agent giải thích quy trình đã kiểm chứng từ hệ thống mà không trình bày đó là
  chính sách kinh doanh chính thức.
- Giữ nguyên API request/response và cơ chế lọc audience hiện tại.

## Related Files

- Modify: `knowledge-base/**/*.md`
- Modify: `app/knowledge/types.py`
- Modify: `app/knowledge/chunker.py`
- Modify: `app/knowledge/validator.py`
- Modify: `app/knowledge/service.py`
- Modify: `tests/**/*.py`
- Modify: `tests/retrieval/knowledge-base-queries.jsonl` khi cần tăng chất lượng retrieval.

## Implementation Steps

1. Thêm trạng thái `verified_from_system` cho kiến thức đã đối chiếu với code/schema.
2. Rà nội dung quy trình, trạng thái, availability, giao trả, thanh toán và điều chuyển.
3. Giữ chính sách tiền/phí/SLA chưa được duyệt ở `needs_business_confirmation`.
4. Làm rõ prompt để trả lời kiến thức hệ thống đã kiểm chứng và từ chối con số/chính sách thiếu nguồn.
5. Chạy lint, type-check, test, validator, ingestion, retrieval evaluation và RAG smoke test.

## Acceptance Criteria

- [x] Không có tài liệu kỹ thuật đã kiểm chứng còn mang nhãn bản nháp mơ hồ.
- [x] Không có chính sách tiền/phí/SLA chưa duyệt bị gắn `business_authority: true`.
- [x] Agent trả lời được câu hỏi quy trình chung từ nguồn đã kiểm chứng.
- [x] Agent từ chối câu hỏi yêu cầu mức phí hoặc thời hạn chưa có căn cứ.
- [x] Toàn bộ kiểm tra tĩnh và test tự động đạt.
- [x] Pgvector được cập nhật và retrieval đạt Recall@5 từ 95% trở lên.

## Risks

- Tài liệu suy từ code có thể mô tả hành vi hệ thống nhưng không đại diện cho quyết định kinh doanh.
- Thay metadata làm thay đổi chunk hash và yêu cầu ingest lại toàn bộ phần liên quan.
