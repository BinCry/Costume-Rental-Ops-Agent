---
id: unit-availability
title: Kiểm tra trang phục còn trống
document_type: rule_reference
domain: inventory
status: verified_from_system
version: 0.2
source_type: technical_implementation
business_authority: false
retrieval_enabled: true
audience: shared
chunk_title_prefix: true
usage_limit: "Chỉ mô tả cách hệ thống kiểm tra lịch; không thay thế dữ liệu hiện tại hoặc quy định của cửa hàng."
source:
  - workspace://apps/api/src/modules/rentals/rental.route.ts
  - workspace://apps/api/src/modules/rentals/rental.service.ts
  - workspace://apps/api/src/modules/inventory/inventory.route.ts
  - workspace://apps/api/prisma/schema.prisma
---

# Kiểm tra trang phục còn trống

## Quy tắc cốt lõi

Không được kết luận một bộ trang phục còn trống chỉ vì nó đang ở trạng thái “sẵn sàng”. Cần kiểm tra đúng khoảng thời gian khách muốn thuê, các đơn đã giữ bộ, lịch vệ sinh hoặc sửa chữa, yêu cầu điều chuyển đang hoạt động và chi nhánh đang giữ đồ.

## Dữ liệu cần xem

| Dữ liệu | Nguồn ứng viên | Vì sao cần |
|---|---|---|
| Khoảng thời gian cần thuê | Đơn thuê | Biết chính xác ngày giờ cần kiểm tra. |
| Các đơn đã giữ bộ | Lịch đặt thuê | Bộ đồ có thể đã được giữ hoặc đang cho thuê. |
| Lịch tạm ngưng cho thuê | Lịch vận hành | Việc vệ sinh, sửa chữa hoặc kiểm tra có thể trùng thời gian thuê. |
| Tình trạng hiện tại | Kho trang phục | Bộ đồ có thể đang vệ sinh, sửa chữa, chuyển chi nhánh hoặc đã ngừng sử dụng. |
| Chi nhánh hiện tại | Kho trang phục | Phải phù hợp với nơi khách nhận đồ hoặc có phương án điều chuyển. |
| Điều chuyển đang hoạt động | Lịch điều chuyển | Bộ đang chờ chuyển, đã duyệt chuyển hoặc đang vận chuyển chưa thể đồng thời giữ cho đơn mới. |

Hai khoảng thời gian được xem là trùng nhau khi một khoảng bắt đầu trước lúc khoảng kia kết thúc và kết thúc sau lúc khoảng kia bắt đầu. Vì vậy, chỉ cần một phần thời gian thuê chồng lên đơn hoặc lịch xử lý khác thì bộ đó chưa thể được xác nhận là còn trống.

## Kết luận an toàn

| Bằng chứng | Cách diễn đạt |
|---|---|
| Hệ thống tìm thấy bộ phù hợp | “Hiện tại có trang phục phù hợp trong thời gian bạn yêu cầu.” |
| Chỉ biết bộ đang “sẵn sàng” | “Mình cần kiểm tra thêm lịch đặt trong thời gian bạn muốn thuê.” |
| Thiếu dữ liệu cần thiết | “Hiện mình chưa thể xác nhận bộ này còn trống. Nhân viên cửa hàng sẽ kiểm tra lại giúp bạn.” |

## Tình huống thường gặp

### Khách hỏi một bộ có còn trống vào ngày cụ thể không?

Xác định ngày giờ nhận và trả đồ, chi nhánh khách muốn nhận, cùng mẫu hoặc kích cỡ khách cần. Chỉ trả lời “còn” khi lịch của bộ phù hợp không bị trùng đơn thuê, vệ sinh, sửa chữa hoặc điều chuyển.

### Khách hỏi vì sao bộ đang sẵn sàng nhưng chưa đặt được

Giải thích rằng trạng thái sẵn sàng cho biết tình trạng hiện tại của bộ đồ, còn việc cho thuê phụ thuộc vào lịch trong đúng thời gian khách chọn. Đề nghị kiểm tra thời gian khác hoặc bộ tương tự.

## Khi cần chuyển nhân viên

Chuyển cho nhân viên khi không có đủ lịch đặt, lịch xử lý trang phục hoặc thông tin chi nhánh; khi khách yêu cầu giữ bộ ngoài quy trình; hoặc khi cần quyết định điều chuyển.

