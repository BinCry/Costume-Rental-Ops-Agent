---
date: 2026-10-15
session: hybrid-goal-resolver
---

# Journal: 2026-10-15 — Hybrid Goal Resolver

## Context

Goal inference trước đây phụ thuộc nhiều vào từ khóa cố định, nên dễ bỏ sót cách diễn đạt tự nhiên và chưa tận dụng tốt message bổ sung khi case đang `WAITING_INPUT`. Mục tiêu của phiên này là tăng độ linh hoạt mà không giao quyền chọn tool hay policy cho model.

## What Happened

- Bổ sung hybrid resolver: rule xử lý fast path rõ ràng, structured model output xử lý câu tự nhiên chưa khớp rule, và fallback an toàn khi model lỗi hoặc confidence thấp.
- Thêm `GoalDraft`, `GoalEntities` và metadata trên goal để lưu input đã trích xuất, nguồn phân giải và confidence.
- Giữ trusted policy boundary: model chỉ đề xuất goal type, entity, confidence và write intent; tool allowlist, permission, confirmation/approval và success criteria vẫn lấy từ code/skill catalog.
- Message bổ sung cho case `WAITING_INPUT` được merge theo field còn thiếu, tránh ghi đè nhầm ID đã có hoặc phân loại lại toàn bộ case.
- Token dùng cho goal classification được cộng vào budget toàn case và budget của write-planning.
- Bổ sung test cho diễn đạt tự nhiên, giới hạn tool theo trusted skill và continuation merge.

## Reflection

Thiết kế hybrid cân bằng tốt hơn giữa tính linh hoạt và khả năng kiểm soát. Điểm quan trọng không phải để model tự quyết định workflow, mà là dùng model như bộ phân tích dữ liệu không tin cậy rồi tái dựng goal bằng contract nội bộ. Continuation merge theo field còn thiếu cũng phù hợp hơn với hội thoại nhiều lượt so với việc infer lại từ đầu.

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Ưu tiên deterministic rule trước model | Giảm latency, token và độ bất định cho intent rõ ràng | Các lệnh phổ biến giữ hành vi ổn định |
| Structured output chỉ là untrusted draft | Ngăn model tự mở rộng tool hoặc quyền thực thi | Policy boundary vẫn nằm hoàn toàn trong backend |
| Confidence thấp phải hỏi lại | Tránh thực thi dựa trên intent mơ hồ | Case chuyển sang thu thập thêm input an toàn |
| Merge continuation theo goal hiện tại | Bảo toàn ngữ cảnh và identifier đã thu thập | `WAITING_INPUT` trở thành flow hội thoại thực sự |
| Tính classification token vào case budget | Budget phải phản ánh toàn bộ chi phí model | Guard token nhất quán giữa resolve, ReAct và write planning |

## Next Steps

- Theo dõi confidence và tỷ lệ fallback trên dữ liệu production để hiệu chỉnh threshold/rule.
- Bổ sung evaluation set cho paraphrase tiếng Việt và continuation nhiều lượt.
- Chạy E2E với model, database và Studio API production trước khi bật write feature flags.
