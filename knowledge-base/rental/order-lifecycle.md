---
id: rental-order-lifecycle
title: Vòng đời đơn thuê
document_type: process
domain: rental
status: verified_from_system
version: 0.2
source_type: technical_implementation
business_authority: false
retrieval_enabled: true
audience: shared
chunk_title_prefix: true
usage_limit: "Chỉ mô tả các bước hệ thống hỗ trợ; điều kiện chuyển bước cần nghiệp vụ phê duyệt."
source:
  - workspace://apps/api/src/modules/rentals/rental.route.ts
  - workspace://apps/api/src/modules/rentals/rental.service.ts
  - workspace://apps/api/prisma/schema.prisma
---

# Vòng đời đơn thuê

## Phạm vi

Tài liệu mô tả các bước chính của một đơn thuê. Điều kiện chi tiết, thời hạn cho phép thay đổi và thời gian xử lý cần được cửa hàng xác nhận trước khi dùng như quy trình chính thức.

## Các bước chính

Đơn nháp → Chờ xác nhận → Đã xác nhận → Đang chuẩn bị → Sẵn sàng để nhận → Đang thuê → Đang kiểm tra đồ trả → Đã hoàn tất.

Đơn cũng có thể kết thúc do bị từ chối, bị hủy hoặc khách không đến nhận đồ.

Khách trả một phần đồ thì đơn vẫn có thể tiếp tục ở bước đang thuê. Khi toàn bộ món đang thuê được nhận lại, đơn chuyển sang bước kiểm tra đồ trả. Việc đã nhận lại đồ không đồng nghĩa đơn được hoàn tất ngay; cửa hàng còn phải xử lý kiểm tra và các khoản liên quan.

## Thao tác hệ thống hiện có

| Giai đoạn | Thao tác | Lưu ý cho trợ lý |
|---|---|---|
| Kiểm tra còn trống | Tra cứu theo thời gian thuê | Không chỉ dựa vào trạng thái “sẵn sàng”. |
| Tạo hoặc cập nhật đơn | Ghi thông tin đơn thuê | Cần đúng quyền và quy định của cửa hàng. |
| Xác nhận hoặc từ chối | Cập nhật quyết định của cửa hàng | Phải dùng dữ liệu mới nhất của đơn. |
| Đổi bộ hoặc gia hạn | Kiểm tra lịch rồi cập nhật | Phải kiểm tra lại các đơn bị ảnh hưởng trước khi lưu. |
| Chuẩn bị và báo sẵn sàng | Cập nhật tiến độ chuẩn bị | Chỉ đánh dấu sẵn sàng khi nhân viên đã xác nhận thực tế. |
| Giao, nhận lại và đánh giá | Ghi nhận việc giao trả và tình trạng đồ | Cần bằng chứng và người có thẩm quyền khi có hư hỏng hoặc thiếu món. |
| Hoàn tất | Kết thúc đơn trên hệ thống | Không dùng trạng thái đơn để kết luận thanh toán đã hoàn tất. |

## Cách trợ lý trả lời

Khi khách hỏi về một đơn cụ thể, trợ lý phải kiểm tra dữ liệu mới nhất của đơn, lịch trang phục và thanh toán trong phạm vi được cấp quyền. Tài liệu này chỉ giải thích quy trình chung, không thay thế dữ liệu thực tế.

## Nội dung cần xác nhận

- Điều kiện để xác nhận đơn, báo sẵn sàng, giao đồ và hoàn tất đơn.
- Thời gian chuẩn bị và quy tắc ưu tiên đơn.
- Quy định hủy đơn, khách không đến nhận và gia hạn.

## Khách thường hỏi gì?

### “Đơn của tôi đang ở đâu?”

Tra cứu đơn mới nhất, sau đó diễn đạt bằng bước dễ hiểu: đang chờ xác nhận, đang chuẩn bị, sẵn sàng để nhận, đang thuê, đang kiểm tra đồ trả hoặc đã hoàn tất. Không suy đoán trạng thái nếu chưa có dữ liệu đơn.

### “Khi nào tôi nhận được đồ?”

Chỉ xác nhận thời điểm nhận khi đơn đã có thông tin được cửa hàng xác nhận. Nếu đơn còn đang chuẩn bị hoặc chờ xác nhận, nói rõ bước hiện tại và chuyển nhân viên khi khách cần cam kết thời gian cụ thể.

### “Tôi muốn đổi lịch hoặc gia hạn”

Hỏi thời gian mới khách mong muốn và kiểm tra trang phục còn trống. Nếu có đơn hoặc lịch xử lý khác bị ảnh hưởng, đề xuất phương án thay thế rồi chuyển người có quyền phê duyệt thay đổi.

## Thông tin cần có trước khi trả lời

- Thông tin nhận diện đơn và khách.
- Ngày giờ nhận, ngày giờ trả và chi nhánh liên quan.
- Tình trạng đơn và trang phục mới nhất.
- Trạng thái thanh toán khi câu hỏi liên quan tiền.

## Khi cần chuyển nhân viên

Chuyển người phụ trách khi khách muốn hủy, đổi lịch, gia hạn, đổi bộ, yêu cầu cam kết thời gian hoặc có tranh chấp về tình trạng đơn.

