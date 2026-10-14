---
phase: 2
title: "Bộ đánh giá retrieval"
status: completed
priority: P1
effort: "1h"
dependencies: [1]
---

# Phase 2: Bộ đánh giá retrieval

## Overview

Tạo tập truy vấn có kỳ vọng rõ ràng để đánh giá retrieval trước khi đưa RAG vào sử dụng.

## Requirements

- Tối thiểu 40 truy vấn tiếng Việt theo cách khách và nhân viên thường hỏi.
- Mỗi truy vấn ánh xạ tới tài liệu mong đợi và nhãn hành vi an toàn.

## Related Code Files

- Create: `tests/retrieval/knowledge-base-queries.jsonl`
- Modify: `docs/evaluation-and-safety.md`

## Implementation Steps

1. Tạo dữ liệu JSONL theo một schema đơn giản.
2. Bổ sung hướng dẫn cách đo recall@k và kiểm tra câu trả lời.
3. Kiểm tra tính hợp lệ từng dòng JSON và độ phủ chủ đề.

## Success Criteria

- [x] Có ít nhất 40 truy vấn hợp lệ.
- [x] Không có truy vấn yêu cầu trợ lý bịa quy định.
