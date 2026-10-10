# Hướng dẫn trình diễn giao diện toàn hệ thống

## Phạm vi

Frontend hiện có 18 màn hình theo `Kế hoạch thiết kế và triển khai giao diện.md`: 5 màn hình lõi đã duyệt và 13 màn hình mở rộng. Giao diện dùng dữ liệu fixture trong bộ nhớ trình duyệt, không ghi vào PostgreSQL và không gọi API nghiệp vụ. Tải lại trang sẽ đưa dữ liệu mẫu về trạng thái ban đầu.

Chạy từ thư mục gốc:

```bash
pnpm install
pnpm --filter @costume/web dev
pnpm --filter @costume/web typecheck
pnpm --filter @costume/web lint
pnpm --filter @costume/web build
```

## Đường dẫn

| Khu vực | Đường dẫn | Màn hình |
|---|---|---|
| Khách | `/` | Bộ sưu tập |
| Khách | `/trang-phuc/:ma-mau` | Chi tiết trang phục |
| Khách | `/dat-thue` | Gửi yêu cầu thuê |
| Khách | `/don-cua-toi`, `/don-cua-toi/:ma-don` | Đơn và chi tiết đơn của hồ sơ mẫu đang chọn |
| Chung | `/tai-khoan` | Google sign-in entry, hoàn thiện hồ sơ và trạng thái tài khoản ở mức UI |
| Vận hành | `/van-hanh/tong-quan` | Bảng việc |
| Vận hành | `/van-hanh/don-thue`, `/van-hanh/don-thue/:id` | Không gian xử lý đơn |
| Vận hành | `/van-hanh/don-thue/:id/giao`, `/van-hanh/don-thue/:id/tra` | Giao/thu và nhận trả/quyết toán |
| Vận hành | `/van-hanh/tao-don` | Tạo yêu cầu tại quầy |
| Vận hành | `/van-hanh/dang-thue` | Theo dõi từng bộ đang ở khách |
| Kho | `/van-hanh/kho`, `/van-hanh/dieu-chuyen` | Bộ theo barcode và phiếu điều chuyển |
| CRM | `/van-hanh/khach-hang` | Hồ sơ và case |
| Quản trị | `/quan-tri/danh-muc`, `/quan-tri/nhan-vien`, `/quan-tri/vai-tro`, `/quan-tri/chi-nhanh`, `/quan-tri/chinh-sach`, `/quan-tri/bao-cao` | Danh mục/giá, nhân viên, quyền, chi nhánh, chính sách, báo cáo |

## Cách dùng fixture

Khi chạy Vite ở chế độ phát triển, thanh **Kiểm tra UI fixture** cho chọn tình huống, vai trò, chi nhánh và hồ sơ khách. Thanh này không có trong bản build production. Vai trò và mã quyền bám `apps/api/prisma/seed/core.ts`; role của nhân viên chỉ hiệu lực tại chi nhánh có nhân viên `ACTIVE` được phân công. Quản trị có phạm vi toàn chuỗi. Các checkbox ở `/quan-tri/vai-tro` sửa permission trên role, scope hiển thị theo mã quyền và không thể tự đổi.

Các tình huống có sẵn: tải, trống, lỗi mạng, mất quyền, xung đột gán bộ, đơn đổi phiên bản, khách hủy khi duyệt, chuyển khoản chưa đối soát, hoàn cọc lỗi, barcode không thấy/khác chi nhánh, và bộ đang vệ sinh/sửa. Chọn **Bình thường** để thực hiện luồng fixture. Những thao tác tạo/sửa chỉ được hiển thị là hoàn tất sau khi adapter trả thành công.

Luồng demo gợi ý:

1. Chọn Áo dài Lina, xem chi tiết và gửi yêu cầu thuê với kỳ mẫu 10/10/2026 09:00–12/10/2026 09:00 tại Quận 1. Yêu cầu mới xuất hiện ở **Đơn của tôi** cho hồ sơ khách vừa nhập, đồng thời ở hàng đợi nhân viên; trạng thái vẫn chờ xác nhận và chưa giữ bộ.
2. Trong `/van-hanh/don-thue/:id`, chọn đủ barcode READY và xác nhận. Có thể chuyển sang tình huống **Xung đột bộ** trước khi xác nhận để thấy lựa chọn được giữ lại và bộ xung đột bị loại.
3. Tại quầy, tìm khách hoặc tạo hồ sơ mẫu, chọn mẫu/biến thể/kỳ mẫu, lấy báo giá và tạo yêu cầu. Mở mã đơn vừa tạo để duyệt theo quyền.
4. Tra `BC-031` ở **Đang thuê** để xem khách giữ, đơn, hạn trả và mở luồng nhận trả. Tại **Kho**, xem trạng thái vận hành riêng với khả dụng theo kỳ; thử `BC-018` cho tình huống bộ bị block.
5. Ở **Điều chuyển**, mở `DC-001`, duyệt, xuất `BC-012`, chọn tình trạng nhận và xác nhận nhận từng bộ. Chi nhánh hiện tại của bộ chỉ đổi sau bước nhận.
6. Tại **Vai trò**, chọn một role, tick/bỏ mã quyền và lưu. Chuyển vai trò/chi nhánh trên thanh fixture để xem menu hiệu lực thay đổi. Chọn nhân viên kho ở Quận 1 sẽ thấy trạng thái chưa được phân công; chuyển sang Thủ Đức để xem quyền kho.

## Kiến trúc và giới hạn

- `apps/web/src/app/routes.ts` khai báo đường dẫn; `app/StudioApp.tsx` quản lý điều hướng và context fixture. Component dùng chung ở `components/ui.tsx`, `components/studio.tsx`; token nằm ở `index.css`.
- `fixtures/adapter.ts` giữ dữ liệu năm màn hình lõi; `fixtures/studio.ts` cung cấp contract và dữ liệu mở rộng, thao tác trong bộ nhớ. Component trực quan không tự tính ngày thuê, phí trễ, cấn trừ hay doanh thu; dùng snapshot do adapter trả.
- Thuê, cọc, phụ phí và hoàn cọc hiển thị riêng. Chuyển khoản `PENDING` không được coi là đã thu; cọc đang giữ không cộng doanh thu. Các luồng tài chính giao/nhận hiện chỉ trình bày và xem trước theo fixture, chưa ghi giao dịch thật.
- Media mới, biên nhận điện tử, ảnh bằng chứng, OAuth Google, phiên đăng nhập và quyền server, báo giá/khả dụng thực thời, khóa phân bổ chống trùng, kiểm soát phiên bản, thu tiền và đối soát ngân hàng, quyết toán/refund, báo cáo và audit cần API tương ứng. Không có endpoint nào được giả định là đã tồn tại.
- Seed hiện chỉ có `rentals.manage.branch` cho xử lý đơn; chưa có mã quyền độc lập cho duyệt, giao và trả. Màn hình quyền hiển thị phụ thuộc này, không tạo mã quyền giả. Chính sách có bảng phiên bản trong schema nhưng chưa có permission chuyên biệt/API quản lý; bản tạo trong fixture chỉ minh họa UI.
- Giá hiện hành lưu theo biến thể toàn chuỗi. Sửa giá fixture không sửa snapshot đơn đã có. Không có giá theo chi nhánh hoặc lịch giá. CRM chỉ dùng khách, tương tác và case theo schema; không có loyalty, tag, campaign hay consent center.

Khi nối backend, ưu tiên thay từng hàm adapter bằng API trả cùng shape và giữ các trạng thái lỗi/xung đột. Backend phải kiểm quyền theo người dùng, role và chi nhánh trên mỗi yêu cầu; kiểm tra UI không thay thế phân quyền server.
