---
id: status-definitions
title: Danh mục trạng thái nghiệp vụ
document_type: reference
domain: shared
status: verified_from_system
version: 0.2
source_type: technical_implementation
business_authority: false
retrieval_enabled: true
audience: shared
chunk_title_prefix: true
usage_limit: "Chỉ giải thích ý nghĩa trạng thái hệ thống; không suy ra quy định hoặc kết quả thanh toán."
source:
  - workspace://apps/api/prisma/schema.prisma
---

# Danh mục trạng thái nghiệp vụ

## Trạng thái đơn thuê

| Cách gọi | Ý nghĩa |
|---|---|
| Đơn nháp | Đơn đang được tạo, chưa gửi xác nhận. |
| Chờ xác nhận | Đơn đang chờ cửa hàng xác nhận. |
| Đã xác nhận | Cửa hàng đã xác nhận đơn. Trạng thái này không khẳng định khách đã thanh toán. |
| Đang chuẩn bị | Cửa hàng đang chuẩn bị trang phục. |
| Sẵn sàng để nhận | Trang phục đã được đánh dấu sẵn sàng giao cho khách. |
| Đang thuê | Khách đã nhận đồ và đơn đang trong thời gian thuê. |
| Đang kiểm tra đồ trả | Cửa hàng đã nhận lại và đang kiểm tra trang phục. |
| Đã hoàn tất | Đơn đã kết thúc trên hệ thống. Trạng thái này không tự xác nhận mọi khoản tiền đã xử lý xong. |
| Từ chối / Đã hủy / Khách không đến | Các trường hợp đơn kết thúc mà không đi hết quy trình thuê. |

## Trạng thái bộ trang phục và việc giữ bộ

| Nhóm | Các tình trạng có thể gặp |
|---|---|
| Tình trạng vận hành của bộ trang phục | Đang nhập kho, sẵn sàng, đang vệ sinh, đang sửa chữa, đang chuyển chi nhánh hoặc đã ngừng sử dụng. |
| Tình trạng thực tế | Chưa kiểm tra, mới, tốt, khá, xuống cấp hoặc hư hỏng. |
| Tình trạng giữ bộ cho đơn | Chưa gắn với đơn, đang giữ chỗ, đã xác nhận, đang cho thuê, đã nhả giữ chỗ hoặc đã hoàn tất. |

## Trạng thái lịch tạm ngưng và điều chuyển

| Nhóm | Các tình trạng có thể gặp |
|---|---|
| Lý do tạm ngưng cho thuê | Vệ sinh, sửa chữa, chỉnh sửa, kiểm tra, sử dụng nội bộ hoặc lý do khác. |
| Tình trạng xử lý | Đã lên lịch, đang thực hiện, đã hoàn tất hoặc đã hủy. |
| Điều chuyển chi nhánh | Đã yêu cầu, đã duyệt, đang vận chuyển, đã nhận, bị từ chối hoặc đã hủy. |

## Trạng thái tiền

| Nhóm | Các tình trạng có thể gặp |
|---|---|
| Thanh toán | Đang chờ, thành công, thất bại hoặc đã hủy. |
| Hoàn tiền | Đã yêu cầu, đang xử lý, đã hoàn tất, bị từ chối hoặc thất bại. |

Không nói với khách rằng tiền đã được thu hoặc hoàn xong khi hệ thống vẫn hiển thị “đang chờ” hoặc “đang xử lý”.

## Trạng thái kiểm tra đồ trả

| Cách gọi | Ý nghĩa |
|---|---|
| Chờ đánh giá | Cửa hàng đã nhận thông tin trả đồ nhưng chưa chốt kết quả kiểm tra. |
| Đạt yêu cầu | Việc kiểm tra chưa ghi nhận vấn đề cần xử lý. |
| Có hư hỏng | Có tình trạng hư hỏng được ghi nhận; chưa tự động có nghĩa khách phải trả một mức phí cụ thể. |
| Có món thất lạc | Có món hoặc phụ kiện chưa được ghi nhận là đã trả đủ; cần đối chiếu trước khi kết luận. |
| Đã kiểm tra xong | Bước kiểm tra đã hoàn thành; vẫn cần xem riêng các khoản thanh toán và hoàn tiền. |

## Cách trả lời theo trạng thái

| Tình huống | Điều nên nói | Điều không nên khẳng định |
|---|---|---|
| Đơn chờ xác nhận | “Cửa hàng đang kiểm tra và sẽ phản hồi sớm.” | Không hứa giờ xác nhận nếu chưa có quy định thời gian xử lý. |
| Đơn đang chuẩn bị | “Cửa hàng đang chuẩn bị trang phục cho đơn của bạn.” | Không nói đã sẵn sàng nhận. |
| Đơn đang kiểm tra đồ trả | “Cửa hàng đã nhận lại đồ và đang kiểm tra tình trạng.” | Không kết luận phí hư hỏng hoặc hoàn tiền. |
| Hoàn tiền đang xử lý | “Yêu cầu hoàn tiền đang được xử lý.” | Không nói tiền đã về tài khoản. |

## Khi cần kiểm tra thêm

Trước khi trả lời về một đơn cụ thể, cần xem thông tin mới nhất của đơn, trang phục liên quan và thanh toán nếu câu hỏi có liên quan đến tiền. Nếu thông tin hiển thị mâu thuẫn hoặc thiếu, hãy thông báo đang kiểm tra lại và chuyển nhân viên phụ trách.

