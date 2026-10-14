---
id: branch-transfer
title: Điều chuyển trang phục giữa chi nhánh
document_type: process
domain: transfers
status: verified_from_system
version: 0.2
source_type: technical_implementation
business_authority: false
retrieval_enabled: true
audience: shared
chunk_title_prefix: true
usage_limit: "Chỉ mô tả luồng hệ thống; thời gian, chi phí và thẩm quyền điều chuyển cần nghiệp vụ xác nhận."
source:
  - workspace://apps/api/src/modules/transfers/transfer.route.ts
  - workspace://apps/api/src/modules/transfers/transfer.service.ts
  - workspace://apps/api/prisma/schema.prisma
---

# Điều chuyển trang phục giữa chi nhánh

## Các bước điều chuyển

Đã yêu cầu → Đã duyệt → Đang vận chuyển → Đã nhận hàng.

Yêu cầu cũng có thể bị từ chối hoặc hủy.

## Quy tắc cho trợ lý

- “Đang vận chuyển” chỉ có nghĩa trang phục đang trên đường, chưa thể xác nhận đã tới chi nhánh nhận.
- Chỉ trạng thái “đã nhận hàng” mới xác nhận chi nhánh nhận đã nhận trang phục trên hệ thống.
- Một chuyến có thể được nhận từng phần. Những bộ chưa được chi nhánh nhận xác nhận vẫn được xem là đang vận chuyển.
- Khi gửi đi, bộ trang phục được đánh dấu đang chuyển; khi nhận, tình trạng thực tế và trạng thái tiếp theo của từng bộ phải được ghi nhận.
- Khi so sánh phương án, trợ lý chỉ được đề xuất điều chuyển, không tự tạo yêu cầu thật.
- Mọi thay đổi phải được kiểm tra quyền và phê duyệt trước khi lưu.

## Nội dung cần xác nhận

- Thời gian điều chuyển và khả năng vận chuyển giữa từng cặp chi nhánh.
- Ai có quyền yêu cầu, phê duyệt, xác nhận gửi và xác nhận nhận.
- Cách xử lý hàng thất lạc hoặc nhận thiếu.

## Tình huống thường gặp

### Khách muốn nhận đồ ở chi nhánh khác

Kiểm tra chi nhánh nhận mong muốn, thời gian cần nhận và khả năng có bộ phù hợp tại đó. Nếu cần điều chuyển, chỉ nói đây là phương án đang được cửa hàng kiểm tra; không xác nhận lịch nhận cho đến khi chi nhánh liên quan xác nhận.

### Đồ đang vận chuyển

Có thể nói trang phục đang trên đường đến chi nhánh nhận. Chỉ thông báo “đã có hàng” khi chi nhánh nhận đã xác nhận nhận hàng trên hệ thống.

### Điều chuyển có nguy cơ trễ

Thông báo cho nhân viên phụ trách về đơn bị ảnh hưởng, thời điểm khách cần nhận và các bộ thay thế nếu có. Không tự hủy đơn hoặc đổi lịch thuê.

## Thông tin cần kiểm tra

- Chi nhánh gửi, chi nhánh nhận và bộ trang phục liên quan.
- Thời điểm khách cần nhận đồ.
- Tình trạng điều chuyển mới nhất.
- Lựa chọn thay thế nếu việc điều chuyển không kịp.

