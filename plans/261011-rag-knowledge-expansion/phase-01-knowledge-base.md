---
phase: 1
title: "Mở rộng knowledge base nghiệp vụ"
status: completed
priority: P1
effort: "3h"
dependencies: []
---

# Phase 1: Mở rộng knowledge base nghiệp vụ

## Overview

Mở rộng 12 tài liệu có thể retrieval thành nguồn trả lời tự đủ ngữ cảnh cho khách hàng và nhân viên.

## Requirements

- Mỗi phần dùng ngôn ngữ nghiệp vụ, không có endpoint hoặc tên model.
- Nội dung chính xác với tài liệu hiện có và nêu rõ phần chưa được duyệt.

## Related Code Files

- Modify: `knowledge-base/**/*.md`

## Implementation Steps

1. Bổ sung tình huống, dữ liệu cần kiểm tra, câu trả lời mẫu, ngoại lệ và chuyển người phụ trách.
2. Giữ front matter và giới hạn nguồn hiện có.
3. Rà tĩnh các đoạn nội dung để loại mã phát triển.

## Success Criteria

- [x] Mỗi tài liệu retrieval có ngữ cảnh đủ để trả lời một nhóm câu hỏi.
- [x] Không có chính sách được tự suy diễn.
