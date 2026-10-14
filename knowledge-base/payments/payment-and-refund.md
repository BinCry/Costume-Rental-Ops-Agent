---
id: payment-and-refund
title: Thanh toán, quyết toán và hoàn tiền
document_type: process
domain: payments
status: verified_from_system
version: 0.2
source_type: technical_implementation
business_authority: false
retrieval_enabled: true
audience: shared
chunk_title_prefix: true
usage_limit: "Chỉ mô tả trạng thái và thao tác hệ thống; không dùng để quyết định số tiền hoặc điều kiện hoàn tiền."
source:
  - workspace://apps/api/src/modules/payments/payment.route.ts
  - workspace://apps/api/src/modules/payments/payment.service.ts
  - workspace://apps/api/src/modules/rentals/rental.service.ts
  - workspace://apps/api/prisma/schema.prisma
---

# Thanh toán, quyết toán và hoàn tiền

## Phân biệt trạng thái

Thanh toán và hoàn tiền được theo dõi riêng với đơn thuê. “Đang chờ” không có nghĩa là đã thu tiền; “đang xử lý” không có nghĩa là đã hoàn tiền. Không được nhìn trạng thái đơn thuê để kết luận tiền đã được xử lý xong.

Hệ thống theo dõi riêng tiền thuê, tiền cọc và khoản phát sinh. Phần quyết toán phân biệt số phải trả, số đã thanh toán, số còn thiếu, khoản cọc bị khấu trừ, số đã hoàn và số đang chờ hoàn. Chỉ giao dịch thành công mới được tính là đã thu; chỉ khoản hoàn ở trạng thái hoàn tất mới được tính là đã hoàn.

Mỗi đơn giữ lại phiên bản quy định được áp dụng khi tạo đơn. Vì vậy, mức phí hoặc điều kiện của một đơn cụ thể phải lấy từ chính đơn và phiên bản quy định đó, không lấy từ con số mẫu hoặc một đơn khác.

## Quy tắc an toàn cho trợ lý

- Trợ lý không được tự thực hiện thanh toán hoặc hoàn tiền.
- Nếu hệ thống phản hồi chậm hoặc không rõ kết quả, phải kiểm tra lại trạng thái trước khi thử lại.
- Chỉ báo thành công sau khi hệ thống thanh toán xác nhận.
- Không tự quyết định số tiền, phí trễ/hư hỏng, giảm giá hoặc hoàn tiền từ hội thoại.
- Không cộng khoản hoàn đang yêu cầu hoặc đang xử lý vào số tiền đã hoàn cho khách.
- Không kết luận đơn có thể hoàn tất nếu vẫn còn khoản thuê, khoản phát sinh hoặc tiền hoàn cần xử lý.

## Nội dung cần xác nhận

- Quy định về tiền cọc, quyết toán, hoàn tiền và người có quyền duyệt.
- Điều kiện tạo và xác nhận hoàn tiền.
- Nhà cung cấp thanh toán, cách đối soát và thời hạn xử lý giao dịch.

## Ghi chú, miễn giảm và điều chỉnh tiền

Ghi chú của khách hoặc lời nhắn của nhân viên chỉ là thông tin để người phụ trách xem xét. Nội dung như “miễn phí”, “giảm phí” hoặc “hoàn ngay” không tự trở thành quyết định tài chính. Trước khi thay đổi số tiền, cần kiểm tra quy định áp dụng cho đúng đơn, quyền của người xử lý và kết quả đã được xác nhận trên hệ thống.

## Khách thường hỏi gì?

### “Đơn đã xác nhận thì tôi đã thanh toán chưa?”

Không kết luận chỉ từ trạng thái đơn. Kiểm tra thông tin thanh toán của chính đơn đó rồi mới trả lời. Nếu chưa thấy xác nhận, nói rằng cửa hàng đang kiểm tra giao dịch.

### “Tiền hoàn của tôi bao giờ về?”

Kiểm tra yêu cầu hoàn tiền đang ở bước nào. Nếu đang xử lý, chỉ thông báo đúng trạng thái hiện tại. Thời hạn nhận tiền, mức hoàn và phương thức hoàn phải theo quy định đã được duyệt; nếu chưa có, chuyển bộ phận phụ trách.

### “Tôi có phải trả thêm không?”

Không tự tính tiền cọc, phí trễ, phí hư hỏng hay khoản giảm giá từ hội thoại. Thu thập thông tin đơn và lý do phát sinh, sau đó chuyển người có thẩm quyền xác nhận.

## Thông tin cần kiểm tra

- Đơn thuê nào đang được hỏi và giao dịch liên quan.
- Trạng thái thanh toán hoặc hoàn tiền mới nhất.
- Quy định đã được duyệt nếu câu hỏi liên quan số tiền hoặc thời hạn.
- Người phụ trách khi giao dịch có kết quả không rõ ràng.

