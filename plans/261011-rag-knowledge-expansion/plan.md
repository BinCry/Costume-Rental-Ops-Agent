---
title: "Mở rộng knowledge base và bộ đánh giá retrieval"
status: completed
created_at: 2026-10-11
---

# Mở rộng knowledge base và bộ đánh giá retrieval

## Mục tiêu

Biến 12 tài liệu nghiệp vụ hiện có thành các chunk tự đủ ngữ cảnh, dễ tìm bằng câu hỏi tự nhiên và không đưa chi tiết phát triển vào câu trả lời khách hàng.

## Phạm vi

1. Mở rộng tài liệu nghiệp vụ bằng tình huống, thông tin cần kiểm tra, cách trả lời, ngoại lệ và trường hợp chuyển người phụ trách.
2. Thêm bộ truy vấn retrieval bằng tiếng Việt, ánh xạ tới tài liệu mong đợi.
3. Cập nhật tài liệu đánh giá để xác định cách chạy và tiêu chí đạt.

## Không thuộc phạm vi

- Xây vector database, embedding, service RAG hoặc giao diện mới.
- Tự đặt mức phí, thời hạn hoặc quyền hạn chưa được phê duyệt.
- Đưa API, endpoint hoặc tên cấu trúc dữ liệu vào knowledge base.

## Tiêu chí hoàn thành

- Mỗi tài liệu nghiệp vụ có ít nhất một phần tình huống/câu hỏi, thông tin cần kiểm tra, cách trả lời an toàn và ngoại lệ hoặc chuyển người phụ trách khi phù hợp.
- Mọi câu trả lời mẫu dùng tiếng Việt dễ hiểu; không khẳng định chính sách chưa được duyệt.
- Bộ đánh giá có tối thiểu 40 truy vấn, bao phủ đơn thuê, kho, giao trả, điều chuyển, thanh toán, quyền hạn và chính sách còn thiếu.
- Mỗi truy vấn chỉ ra tài liệu mong đợi và kỳ vọng xử lý.
- Kiểm tra tĩnh xác nhận không có endpoint hoặc mã phát triển trong phần nội dung knowledge base.

## Các pha

| Pha | Nội dung | Trạng thái |
|---|---|---|
| 1 | Mở rộng knowledge base nghiệp vụ | completed |
| 2 | Thêm evaluation retrieval và kiểm tra | completed |
| 3 | Tách nội dung khách hàng, chuẩn hóa nguồn và siết validator | completed |
| 4 | Rà soát kỹ thuật, siết authority gate và tái lập chỉ mục pgvector | completed |
| 5 | Phê duyệt chính sách lõi từ core seed và runtime đã xác nhận | completed |

## Kết quả pha 4

- 9 tài liệu được xác nhận là kiến thức hệ thống với trạng thái `verified_from_system`.
- 93 chunks đã được upsert và 6 chunks cũ đã được loại khỏi pgvector.
- Retrieval đạt Recall@1 77,3%, Recall@3 93,2% và Recall@5 100% trên 44 truy vấn retrieval.
- Safety gate mặc định từ chối mức phí, thời hạn, thẩm quyền và quyết định chính sách khi không có nguồn `approved` với `business_authority: true`.
- Kiểm tra cuối đạt: 46 tests, Ruff, mypy trên 21 files và validator trên 13 tài liệu/50 trường hợp.

## Kết quả pha 5

- `POLICY-2025`, ma trận quyền trong core seed và điều kiện hoàn cọc đã đối chiếu được ghi thành nguồn nghiệp vụ chính thức theo xác nhận của chủ dự án ngày 2026-10-13.
- Phí trả trễ, khoảng miễn trễ, giới hạn thuê, hạn báo giá, mốc hủy, SLA hoàn tiền và quyền duyệt đã có nguồn `approved`.
- Hư hỏng, thất lạc, miễn giảm ngoại lệ, phí gia hạn, vệ sinh và điều chuyển vẫn không được phép suy đoán.
- Pgvector hiện có 97 chunks; retrieval đạt Recall@1 79,2%, Recall@3 95,8% và Recall@5 100% trên 48 ca retrieval.
- Kiểm tra cuối đạt: 52 tests, Ruff, mypy trên 21 files và validator trên 14 tài liệu/56 trường hợp.
