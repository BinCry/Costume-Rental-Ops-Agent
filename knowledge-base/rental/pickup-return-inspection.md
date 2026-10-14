---
id: pickup-return-inspection
title: Giao, nhận trả và kiểm tra trang phục
document_type: sop_draft
domain: rental
status: verified_from_system
version: 0.2
source_type: technical_implementation
business_authority: false
retrieval_enabled: true
audience: staff_internal
chunk_title_prefix: true
usage_limit: "Quy trình nháp từ hệ thống; không dùng để tự xác định bằng chứng bắt buộc hoặc mức phí."
source:
  - workspace://apps/api/src/modules/rentals/rental.route.ts
  - workspace://apps/api/src/modules/rentals/rental.service.ts
  - workspace://apps/api/prisma/schema.prisma
---

# Giao, nhận trả và kiểm tra trang phục

## Mục đích

Mô tả các bước khi giao và nhận lại trang phục. Đây là quy trình nháp, chưa phải quy định chính thức về cách kiểm đếm, loại bằng chứng hoặc mức phí.

## Giao trang phục

1. Mở đơn thuê và kiểm tra đơn đang ở bước có thể giao đồ.
2. Đối chiếu từng món và đúng bộ trang phục đã được giữ cho đơn.
3. Người có quyền xác nhận khách đã nhận đồ trên hệ thống.
4. Kiểm tra lại đơn sau khi lưu để chắc chắn thao tác đã thành công.

## Nhận lại và kiểm tra trang phục

1. Xác nhận cửa hàng đã nhận lại đồ.
2. Kiểm tra và ghi nhận tình trạng của từng món.
3. Ghi rõ món bị thiếu, hư hỏng và ghi chú cần thiết; lưu ảnh hoặc bằng chứng theo quy trình.
4. Lên lịch vệ sinh, sửa chữa hoặc kiểm tra thêm theo quy định đã duyệt. Không tự tính phí chỉ từ nội dung ghi chú.

Có thể ghi nhận trả một phần hoặc trả toàn bộ. Mỗi lần nhận lại phải đối chiếu đúng các món đang được khách giữ và số lượng phụ kiện đã giao. Trang phục được đánh giá là hư hỏng phải chuyển sang sửa chữa; món bị ghi nhận thất lạc không được tiếp tục xem là sẵn sàng cho thuê.

Sau khi trả toàn bộ, đơn bước vào giai đoạn kiểm tra. Kết quả kiểm tra có thể đang chờ đánh giá, đạt yêu cầu, có hư hỏng, có món thất lạc hoặc đã hoàn tất. Đây là kết quả kiểm tra riêng, không thay thế trạng thái thanh toán hay hoàn tiền.

## Ngoại lệ

- Thiếu món hoặc hư hỏng: ghi nhận bằng chứng và chuyển cho người có thẩm quyền xác định cách xử lý hoặc mức phí.
- Trả trễ: dùng thời gian thực tế và quy định đã duyệt; nếu chưa có quy định, chỉ cảnh báo và chuyển người phụ trách.
- Nếu không rõ thao tác đã thành công hay chưa, kiểm tra lại đơn trước khi thử lại.

## Nội dung cần xác nhận

- Danh sách cần kiểm tra khi giao, nhận lại và loại bằng chứng bắt buộc.
- Ai có quyền duyệt phí hư hỏng hoặc thiếu món.
- Khi nào đơn được phép chuyển sang “đã hoàn tất” sau khi kiểm tra.

## Cách nói với khách khi giao đồ

Xác nhận ngày nhận, các món khách nhận và hướng dẫn khách kiểm tra trang phục trước khi rời cửa hàng. Nếu có điểm chưa rõ, ghi nhận ngay thay vì tự kết luận sau này.

## Cách nói với khách khi nhận lại đồ

Thông báo rằng cửa hàng đã nhận lại trang phục và sẽ kiểm tra tình trạng theo quy trình. Nếu cần xem xét thêm, nói rõ đây mới là bước kiểm tra; không kết luận ngay về hư hỏng, thiếu món hoặc số tiền phát sinh.

## Khi phát hiện hư hỏng hoặc thiếu món

1. Ghi nhận tình trạng thực tế và bằng chứng theo quy trình cửa hàng.
2. Liên kết đúng với đơn thuê và trang phục liên quan.
3. Chuyển người có thẩm quyền xem xét chính sách và khoản phát sinh.
4. Chỉ thông báo kết quả đã được xác nhận cho khách.

## Câu trả lời mẫu

“Cửa hàng đã ghi nhận tình trạng của trang phục. Mình sẽ chuyển bộ phận phụ trách kiểm tra theo quy định và cập nhật lại cho bạn sau khi có kết quả xác nhận.”

