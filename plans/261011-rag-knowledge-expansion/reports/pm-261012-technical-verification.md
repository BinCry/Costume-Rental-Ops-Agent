---
title: "Báo cáo hoàn tất rà soát knowledge base và pgvector"
date: 2026-10-12
status: completed
phase: 4
---

# Báo cáo hoàn tất pha 4

## Kết quả

- Đối chiếu kiến thức quy trình với hệ thống hiện có và bổ sung trạng thái `verified_from_system`.
- Giữ các mức phí, thời hạn, thẩm quyền và ngoại lệ chưa được nghiệp vụ duyệt ở trạng thái chưa xác nhận.
- Thêm kiểm tra provenance để tài liệu dẫn xuất không thể nâng mức tin cậy từ nguồn chưa duyệt.
- Thêm authority gate mặc định từ chối câu hỏi chính sách khi không có nguồn `approved` và `business_authority: true`.
- Tái lập chỉ mục thành công: 93 chunks được upsert, 6 chunks lỗi thời được xóa.

## Chất lượng

| Hạng mục | Kết quả |
|---|---:|
| Recall@1 | 77,3% (34/44) |
| Recall@3 | 93,2% (41/44) |
| Recall@5 | 100% (44/44) |
| Pytest | 46 passed |
| Ruff | Passed |
| Mypy | Passed, 21 files |
| KB validator | Passed, 13 tài liệu / 50 trường hợp |

## Kiểm tra E2E

- Câu hỏi giải thích trạng thái đơn được trả lời từ nguồn hệ thống đã kiểm chứng, có structured citations và gắn `provisional: true`.
- Câu hỏi ghép giải thích thanh toán với yêu cầu mức phí trả trễ bị từ chối toàn bộ vì chưa có chính sách nghiệp vụ được phê duyệt.
- Phần nguồn do LLM tự sinh được loại bỏ; API chỉ trả nguồn có cấu trúc do hệ thống kiểm soát.

## Việc còn lại phía nghiệp vụ

Người có thẩm quyền cần duyệt các chính sách về mức tiền, thời hạn, điều kiện hoàn tiền, miễn giảm và quyền phê duyệt. Sau khi cập nhật metadata thành `approved` và `business_authority: true`, cần chạy validator, ingestion và retrieval evaluation lại trước khi phát hành.
