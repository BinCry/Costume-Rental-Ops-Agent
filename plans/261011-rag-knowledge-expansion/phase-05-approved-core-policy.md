---
phase: 5
title: "Phê duyệt chính sách lõi từ POLICY-2025"
status: completed
priority: P1
effort: "2h"
dependencies: [4]
---

# Phase 5: Phê duyệt chính sách lõi từ POLICY-2025

## Quyết định nguồn

Chủ dự án xác nhận trong hội thoại ngày 2026-10-13 rằng core seed là nguồn nghiệp vụ chính thức
cho các mức và mốc của `POLICY-2025`, ma trận quyền được seed, cùng các điều kiện hoàn cọc đã được
đối chiếu với runtime. Quyết định này bao phủ yêu cầu của chủ dự án về mức phí, thời hạn, điều kiện
hoàn tiền và quyền phê duyệt. Dữ liệu trong `prisma/seed/demo.ts` không phải nguồn chính sách.

## Đầu ra

- Tài liệu policy công bố các giá trị của `POLICY-2025` và phân biệt rõ dữ liệu chung với dữ liệu
  phải đọc từ từng đơn.
- Tài liệu thanh toán/hoàn tiền và quyền hạn phản ánh các điều kiện, RBAC đang được hệ thống thực thi.
- Những nội dung chưa có căn cứ như mức bồi thường hư hỏng, quy trình miễn giảm và SLA vận hành khác
  tiếp tục bị đánh dấu chưa xác nhận.
- Pgvector được tái lập chỉ mục và RAG trả lời được các câu hỏi chính sách đã duyệt.

## Tiêu chí hoàn thành

- [x] Chỉ tài liệu có quyết định nguồn rõ ràng mới mang `approved` và `business_authority: true`.
- [x] Agent trả lời đúng grace period, phí trả trễ, giới hạn thuê, hạn báo giá và SLA hoàn tiền.
- [x] Agent giải thích đúng điều kiện hoàn cọc và quyền duyệt hoàn tiền.
- [x] Agent không coi promotion là miễn giảm và không bịa mức bồi thường hư hỏng.
- [x] Validator, lint, type-check và test đều đạt.
- [x] Ingestion, retrieval evaluation và E2E với pgvector đều đạt.

## Ngoài phạm vi

- Thay đổi API, schema, seed hoặc logic tính tiền hiện tại.
- Tạo quy trình miễn giảm mới.
- Tự động hóa phí hủy hoặc SLA hoàn tiền trong backend.
