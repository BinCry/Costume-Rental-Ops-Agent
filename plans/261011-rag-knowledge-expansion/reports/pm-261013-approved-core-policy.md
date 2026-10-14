---
title: "Báo cáo hoàn tất chính sách lõi đã phê duyệt"
date: 2026-10-13
status: completed
phase: 5
---

# Báo cáo hoàn tất pha 5

## Tóm tắt

Core seed và hành vi hoàn cọc đã đối chiếu được chủ dự án xác nhận làm nguồn nghiệp vụ cho phạm vi mức phí, thời hạn, điều kiện hoàn tiền và quyền phê duyệt. Knowledge base đã tách chính sách chính thức khỏi danh sách nội dung còn thiếu và tái lập chỉ mục pgvector.

## Kết quả

| Hạng mục | Kết quả |
|---|---:|
| Chunks trong pgvector | 97 |
| Recall@1 | 79,2% (38/48) |
| Recall@3 | 95,8% (46/48) |
| Recall@5 | 100% (48/48) |
| Pytest | 52 passed |
| Ruff | Passed |
| Mypy production | Passed, 21 files |
| KB validator | Passed, 14 tài liệu / 56 trường hợp |

## Safety và E2E

- Câu hỏi phí trả trễ trả lời 60 phút miễn trễ và 20% tiền thuê cơ bản mỗi ngày trễ, `provisional: false`.
- Câu hỏi điều kiện hoàn cọc trả lời đúng ba điều kiện và chỉ dùng nguồn đã phê duyệt.
- Câu hỏi quyền duyệt hoàn tiền trả lời theo vai trò và phạm vi chi nhánh.
- Câu hỏi mức bồi thường hư hỏng tiếp tục trả `insufficient_context`.
- Citation do model tự sinh bị loại; nguồn có cấu trúc do API kiểm soát vẫn được giữ.

## Nội dung chưa có quyết định

Mức bồi thường hư hỏng hoặc thất lạc, quy trình miễn giảm ngoại lệ, phí gia hạn, chi phí điều chuyển và SLA vệ sinh hoặc sửa chữa vẫn cần quyết định nghiệp vụ riêng.
