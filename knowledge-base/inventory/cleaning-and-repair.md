---
id: cleaning-and-repair
title: Vệ sinh, sửa chữa và thời gian tạm ngưng cho thuê
document_type: process
domain: inventory
status: verified_from_system
version: 0.2
source_type: technical_implementation
business_authority: false
retrieval_enabled: true
audience: shared
chunk_title_prefix: true
usage_limit: "Chỉ mô tả dữ liệu và thao tác hệ thống; thời gian và quyền xử lý cần nghiệp vụ xác nhận."
source:
  - workspace://apps/api/src/modules/scheduling/scheduling.route.ts
  - workspace://apps/api/src/modules/inventory/inventory.route.ts
  - workspace://apps/api/src/modules/rentals/rental.service.ts
  - workspace://apps/api/prisma/schema.prisma
---

# Vệ sinh, sửa chữa và thời gian tạm ngưng cho thuê

## Mục đích

Mỗi bộ trang phục có thể được tạm ngưng cho thuê trong một khoảng thời gian để vệ sinh, sửa chữa, chỉnh sửa hoặc kiểm tra. Khoảng thời gian này phải được tính đến khi xác nhận trang phục có sẵn sàng cho đơn tiếp theo hay không.

## Trạng thái và loại công việc

- Loại công việc: vệ sinh, sửa chữa, chỉnh sửa, kiểm tra, sử dụng nội bộ hoặc lý do khác.
- Tình trạng công việc: đã lên lịch, đang thực hiện, đã hoàn tất hoặc đã hủy.
- Không được chỉ nhìn trạng thái của bộ trang phục để kết luận công việc đã hoàn tất; cần kiểm tra lịch công việc tương ứng.

## Cách trợ lý hỗ trợ

Trợ lý có thể phát hiện lịch vệ sinh hoặc sửa chữa trùng với thời gian thuê, chỉ ra các đơn bị ảnh hưởng và đề xuất thứ tự xử lý. Chỉ người có quyền mới được tạo, sửa hoặc đánh dấu công việc hoàn tất.

Khi cửa hàng ghi nhận trả đồ, hệ thống tạo khoảng tạm ngưng tương ứng cho bộ trang phục. Đồ hư hỏng phải chuyển sang sửa chữa; đồ không hư hỏng vẫn có thể cần thời gian vệ sinh trước khi quay lại trạng thái sẵn sàng. Thời điểm kết thúc phải lấy từ dữ liệu của chính bộ đồ, không dùng một con số chung để hứa với khách.

## Nội dung cần xác nhận

- Thời lượng vệ sinh/sửa tiêu chuẩn theo loại trang phục.
- Ai được giao việc, đổi hạn hoàn thành hoặc xác nhận công việc đã xong.
- Điều kiện để một bộ trang phục được đánh dấu sẵn sàng sau khi vệ sinh hoặc sửa chữa.

## Tình huống thường gặp

### Bộ đồ vừa được trả nhưng khách khác sắp nhận

Kiểm tra tình trạng thực tế, công việc cần làm và thời điểm đơn tiếp theo cần nhận đồ. Nếu chưa chắc kịp, hãy coi đây là rủi ro cần xử lý; đề xuất ưu tiên xử lý hoặc bộ thay thế, không cam kết rằng bộ đồ sẽ sẵn sàng.

### Khách hỏi vì sao chưa thể thuê bộ đó

Có thể giải thích ngắn gọn: “Bộ này đang được cửa hàng kiểm tra hoặc chăm sóc để đảm bảo tình trạng trước khi cho thuê lại.” Không nêu chi tiết nội bộ hoặc hứa hẹn thời gian hoàn tất khi chưa được xác nhận.

## Thông tin cần ghi nhận

- Bộ trang phục nào đang được xử lý và lý do.
- Thời điểm dự kiến hoàn thành nếu cửa hàng đã xác nhận.
- Đơn thuê nào có thể bị ảnh hưởng.
- Phương án thay thế và người chịu trách nhiệm quyết định.

