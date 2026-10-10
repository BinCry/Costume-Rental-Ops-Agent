# Tài nguyên tham khảo được đưa vào repo Ops Agent

## Frontend

`apps/web/` là bản sao có chọn lọc của `apps/web` từ snapshot:

`D:\HK5\OOAD\Costume-Rental-Studio-ui-2026-10-03\BinCry-Costume-Rental-Studio-2031b82de222ff87962df39a1f13d14f18da7033`

Đã sao chép source, cấu hình, public assets và package frontend; không mang `node_modules` hoặc `dist`. Tên workspace đã đổi thành `@costume/ops-web`; title/description được đổi để thể hiện bản có Ops Agent. Các màn Studio vẫn là bản demo fixture, chưa có backend nghiệp vụ thật. Mã nguồn snapshot chưa xác minh commit chính thức; xem [handoff](../HANDOFF.md) và [source review](../../../docs/source-review.md).

## Tài liệu UI/UX được sao chép nguyên văn

Các tài liệu dưới đây nằm trong `ui-ux/` và được dùng làm baseline thiết kế/luồng. Chúng vẫn thuộc snapshot, không tự động phản ánh thay đổi sau thời điểm sao chép.

- Kế hoạch thiết kế và triển khai giao diện.
- Quy chuẩn thiết kế giao diện và năm màn hình lõi.
- Hướng dẫn trình diễn giao diện toàn hệ thống.
- Đánh giá và tối ưu trải nghiệm mười luồng chính.
- Báo cáo kiểm toán hoàn chỉnh giai đoạn UI UX.
- Báo cáo QA responsive và khả năng truy cập các luồng lõi.
- Đối chiếu luồng UI UX theo báo cáo rà soát nghiệp vụ.

Các bản đã chọn/đổi tên trước đó vẫn có trong `../snapshot/` để phục vụ tóm tắt domain. Mọi lần đồng bộ sau này cần ghi source URL, branch, commit và ngày trong [quy trình parity](../../../docs/ui-parity.md).
