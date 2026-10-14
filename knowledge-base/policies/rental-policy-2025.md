---
id: rental-policy-2025
title: Chính sách thuê và hoàn cọc hiện hành
document_type: policy
domain: policies
status: approved
version: 1.0
source_type: business_approved
business_authority: true
approved_by: project_owner
approved_at: 2026-10-13
effective_from: 2025-01-01
retrieval_enabled: true
audience: shared
chunk_title_prefix: true
usage_limit: "Áp dụng cho chính sách chung; thông tin thời hạn, số tiền và trạng thái của một đơn cụ thể phải lấy từ chính đơn đó."
source:
  - workspace://apps/api/prisma/seed/core.ts
  - workspace://apps/api/prisma/schema.prisma
  - workspace://apps/api/src/modules/rentals/rental.service.ts
  - workspace://apps/api/src/modules/payments/payment.service.ts
---

# Chính sách thuê và hoàn cọc hiện hành

## Thời gian thuê và hiệu lực báo giá

- Thời gian thuê tối thiểu là 1 ngày và tối đa là 14 ngày.
- Một báo giá có hiệu lực trong 24 giờ kể từ khi được lập.
- Ngày giờ phải trả của khách được ghi trên từng đơn thuê. Trợ lý phải tra đúng đơn thay vì tự suy ra ngày trả từ chính sách chung.
- Khi gia hạn hoặc đổi lịch, cửa hàng vẫn phải kiểm tra lịch trống và thời hạn tối đa trước khi xác nhận.

## Trả trễ

- Khách có 60 phút kể từ thời điểm phải trả ghi trên đơn trước khi bắt đầu tính trễ.
- Sau khoảng miễn trễ, phí trả trễ bằng 20% tiền thuê cơ bản cho mỗi ngày trễ.
- Số ngày trễ được làm tròn lên theo từng ngày. Ví dụ, quá thời gian miễn trễ nhưng chưa đủ một ngày vẫn được tính là một ngày trễ.
- Số tiền cuối cùng phải lấy từ kết quả quyết toán của đúng đơn vì giá thuê, thời điểm trả và phiên bản chính sách có thể khác nhau giữa các đơn.

## Không đến nhận đồ và hủy đơn

- Khách được chờ 120 phút sau thời điểm dự kiến nhận đồ trước khi đơn có thể được xử lý là không đến nhận.
- Mốc hủy miễn phí là trước thời điểm nhận đồ 48 giờ.
- Tỷ lệ phí hủy trễ là 30%. Khi báo số tiền cụ thể, nhân viên phải dùng kết quả tính cho đúng đơn; không tự chọn căn cứ tính từ hội thoại.
- Hiện hệ thống lưu các mốc và tỷ lệ trên nhưng việc xác nhận khoản hủy cụ thể vẫn phải do nhân viên kiểm tra trước khi thông báo cho khách.

## Điều kiện hoàn cọc

Một yêu cầu hoàn cọc chỉ được tạo khi đồng thời đáp ứng các điều kiện sau:

1. Khoản tiền nguồn là tiền cọc đã thanh toán thành công.
2. Đơn đang ở bước kiểm tra đồ trả, đã hủy hoặc khách không đến nhận đồ.
3. Số tiền yêu cầu hoàn không vượt quá số tiền còn có thể hoàn của khoản cọc và của đơn.

Yêu cầu đang chờ hoặc đang xử lý chưa có nghĩa tiền đã về cho khách. Chỉ yêu cầu hoàn tất mới được xem là đã hoàn.

## Thời hạn xử lý hoàn tiền

Thời hạn xử lý theo chính sách là 5 ngày làm việc. Đây là thời hạn xử lý nghiệp vụ, không phải cam kết về thời điểm ngân hàng ghi có. Khi khách hỏi một giao dịch cụ thể, cần kiểm tra trạng thái yêu cầu hoàn mới nhất trước khi trả lời.

## Khoản chưa được chính sách này quy định

Chính sách này chưa quy định mức bồi thường hư hỏng hoặc thất lạc, mức phí gia hạn, chi phí điều chuyển, thời gian vệ sinh hoặc sửa chữa và quy trình miễn giảm ngoại lệ. Các nội dung đó phải được người phụ trách xác nhận; không dùng tỷ lệ phí trả trễ hoặc phí hủy để suy ra.

Mã khuyến mãi là chương trình giảm giá có điều kiện riêng, không phải quyết định miễn hoặc giảm một khoản phí phát sinh cho từng trường hợp.
