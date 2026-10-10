# Báo cáo QA responsive và khả năng truy cập các luồng lõi

Ngày kiểm tra: 03/10/2026. Phạm vi: frontend prototype dùng fixture, chưa có API nghiệp vụ. Vòng này tập trung vào tìm trang phục và đặt thuê; duyệt đơn và gán bộ; giao đồ, đối chiếu tiền thuê và cọc; trả một phần và quyết toán.

## Cách kiểm tra

- Duyệt các luồng bằng trình duyệt tại 375 px; kiểm tra chuyển focus, nội dung hiển thị, trạng thái nút và khả năng phục hồi sau lỗi.
- Kiểm tra chiều ngang ở 360, 768, 1024 và 1440 px trên bốn tuyến `/dat-thue`, `/van-hanh/don-thue`, `/van-hanh/don-thue/RT-1028/giao` và `/van-hanh/don-thue/RT-1035/tra`. Cả 16 tổ hợp không tràn ngang.
- Kiểm tra các fixture `error`, `empty`, `conflict`, `bankPending`, `refundFailed`; kiểm tra hộp thoại xác nhận và phím Escape. Không có lỗi hoặc cảnh báo console trong lượt kiểm tra cuối.
- Chạy ESLint, TypeScript, Vite build và Prettier cho các tệp thay đổi.

## Phát hiện và cách sửa

| Mức | Luồng | Trước | Sau |
| --- | --- | --- | --- |
| P0 | Giao đồ, đổi sang chuyển khoản chờ đối soát | Thông báo thành công “tiền mặt đã đủ” vẫn hiện dù phương thức chuyển khoản chưa đối soát và nút giao bị khóa. | Kết quả xem trước gắn với đơn, phiên bản, kịch bản, mã đã quét, checklist, phương thức, hai khoản tiền và ghi chú. Thay đổi điều kiện sẽ ẩn kết quả cũ; cảnh báo chờ đối soát và trạng thái chưa thu hiển thị nhất quán. |
| P1 | Đặt thuê trên mobile | Qua bước, focus ở nút dưới cùng; tiêu đề bước mới có thể nằm ngoài vùng đang đọc. Khi nhập sai, focus cũng ở nút dưới cùng. | Focus và cuộn tới tiêu đề bước mới; khi có lỗi biểu mẫu, focus tới trường sai đầu tiên hoặc thông báo lỗi. Sau khi gửi thành công, focus tới tiêu đề xác nhận. |
| P1 | Chọn đơn trên mobile | Danh sách biến mất, chi tiết đơn ở dưới màn hình; focus rơi về `body`. | Chọn đơn đưa focus tới nút quay lại và cuộn chi tiết vào màn hình. Quay lại danh sách phục hồi focus đúng dòng đã chọn. |
| P1 | Xung đột gán bộ | Đơn báo bộ vừa hết khả dụng ở đầu trang trong khi nhân viên đang ở cuối trang; focus rơi về `body`. | Thông báo được focus và đưa vào màn hình; nút “Xem bộ còn trống” trở lại phần chọn bộ. Bộ hợp lệ đã chọn vẫn được giữ. |
| P1 | Chuyển khu trên mobile | Menu khách không có lối vào khu vận hành và ngược lại. | Bổ sung liên kết chuyển khu trong menu mobile và khai báo `aria-controls` cho nút mở menu. |
| P2 | Tiến độ đặt thuê | Vùng nhấn của các nút bước cao 42 px tại 360 px. | Tăng tối thiểu lên 44 px. |

Điều hướng nội bộ cũng chuyển focus tới vùng nội dung chính sau khi đổi trang. Các thay đổi này chỉ điều chỉnh giao diện và tương tác, không thay đổi điều kiện xác nhận đơn, ghi nhận thanh toán hay hoàn cọc.

## Kết quả theo tình huống

- **Đặt thuê:** báo giá snapshot tách tiền thuê và tiền cọc; lỗi tải có nút thử lại; dữ liệu rỗng có đường về danh mục; lỗi tên hoặc số điện thoại chỉ rõ trường cần sửa. Yêu cầu gửi trong fixture chưa giữ bộ cho đến khi studio xác nhận.
- **Duyệt đơn:** hộp thoại cho xem lại hai barcode trước khi xác nhận; Escape đóng và trả focus về nút gọi. Với `conflict`, BC-001 bị đánh dấu không khả dụng, BC-012 vẫn được chọn; có thể trở lại chọn mã khác.
- **Giao đồ:** chỉ cho xem trước điều kiện giao sau khi quét đủ bộ, đánh dấu tình trạng và phụ kiện, đối chiếu riêng tiền thuê và cọc. `bankPending` hiển thị chưa thu, khóa bước cuối, không còn thông báo tiền mặt cũ.
- **Trả đồ:** quét 1/2 bộ vẫn ghi rõ bộ còn lại ở khách và chưa quyết toán hoặc hoàn cọc. `refundFailed` hiển thị cảnh báo giao dịch hoàn chưa thành công, giữ trạng thái cọc đang giữ và khóa xem trước quyết toán theo fixture.

## Giới hạn và việc cần quyết định khi nối API

- Kiểm tra bằng trình duyệt và cây truy cập; chưa thử với thiết bị thật, bàn phím vật lý hoặc trình đọc màn hình chuyên dụng. Cần chạy lại các luồng này trong môi trường tích hợp.
- Trạng thái còn đồ ở catalog hiện theo mẫu; API cần cung cấp khả dụng theo biến thể, chi nhánh và kỳ thuê để khách hiểu đúng trước khi gửi yêu cầu. Fixture có thể cho gửi một biến thể mà nhân viên không tìm được bộ đủ điều kiện.
- Xác nhận đơn, khóa bộ, đối soát chuyển khoản, ghi nhận thu tiền và hoàn cọc hiện chỉ là xem trước. Backend cần kiểm tra phiên bản đơn, quyền theo vai trò và chi nhánh, tính khả dụng và giao dịch tiền trước khi đổi trạng thái thật.
- Quy tắc tính “một ngày thuê” là chính sách cần cấu hình và trả về trong báo giá. Giao diện không tự tính lại phí hoặc tiền hoàn.

## Bổ sung kiểm tra UI fixture ngày 03/10/2026

- Rà soát 21 tuyến giao diện ở 375 px và 1440 px, gồm khu khách, khu vận hành, quản trị và chi tiết đơn. Không tuyến nào tràn ngang. Chi tiết đơn khách được kiểm bằng đơn RT-1024 thuộc khách mẫu KH-001; đơn không thuộc khách hiển thị lối quay về danh sách.
- Tạo đơn tại quầy: báo giá tách thuê/cọc, chỉ cho chọn barcode READY; sau khi tạo và xác nhận, biểu mẫu bị khóa để tránh sửa nhầm hoặc gửi lặp, có lối xem đơn và tạo đơn khác. Giai đoạn đang gửi cũng khóa các trường đầu vào.
- Trả một phần: quét BC-035 của RT-1035, chọn chờ đánh giá, đối chiếu phụ kiện và nhập mô tả bắt buộc. Bản xem trước nêu rõ 1/2 bộ đã kiểm, BC-036 còn ở khách và cọc tiếp tục được giữ. Checklist tình trạng trùng lặp đã bỏ; kết quả kiểm từng bộ là trường chính.
- CRM: danh sách người phụ trách lấy từ nhân viên có tài khoản và phân công đang hoạt động tại chi nhánh của case. Đổi case sang Thủ Đức khiến người phụ trách Quận 1 hiện cảnh báo; lưu bị chặn cho đến khi chọn người phù hợp hoặc bỏ phân công. Trạng thái lỗi tải có nút thử lại; trạng thái trống có thông báo rõ.
- Tài khoản hiển thị nhãn trạng thái quyền bằng tiếng Việt. Đặt thuê và tạo đơn tại quầy bỏ qua kết quả báo giá cũ nếu lựa chọn đã đổi trong lúc tải; hành động gửi được khóa chống kích hoạt lặp trong cùng phiên.
- Không thấy lỗi console trong lần duyệt các tuyến. TypeScript, ESLint, Prettier và Vite build đều đạt. Trình duyệt trong phiên không cấp ảnh chụp màn hình, nên lượt này xác minh cấu trúc truy cập, trạng thái tương tác và tràn ngang; cần kiểm tra trực quan lại khi có công cụ chụp ảnh hoạt động.

## Bổ sung rà soát thao tác và tiền cọc

- Quét các nút và liên kết của 21 tuyến ở 375 px: chỉ cặp hành động chọn/bỏ cả nhóm quyền có vùng nhấn thấp hơn 40 px. Đã tăng lên 44 px và xác minh lại trên màn vai trò, không gây tràn ngang.
- Form hoàn thiện hồ sơ mẫu đưa focus tới ô tên khi mở; khi gửi thiếu dữ liệu, lỗi nằm cạnh từng trường và focus tới trường sai đầu tiên. Sau khi hoàn tất, focus tới thông báo kết quả. Đây vẫn là mô phỏng Google sign-in, không tạo phiên đăng nhập thật.
- Ở màn trả, bảng phí/cọc snapshot chỉ xuất hiện sau khi quét và kiểm đủ barcode trong phiên. Nếu chưa quét, chưa kiểm hoặc mới quét một phần, màn nêu đúng bước còn thiếu và không suy đoán rằng bộ đã ở khách hay đã nhận về chỉ từ trạng thái quét.
- Với RT-1033, fixture có phí hỏng 120.000 đ trong snapshot. Khi người kiểm chọn “Đạt”, màn cảnh báo kết quả kiểm khác snapshot và yêu cầu đối chiếu chứng từ; không tự sửa phí hoặc số hoàn. Đã đi thử các trạng thái trước quét, sau quét và sau kiểm trong trình duyệt.

## Bổ sung kiểm tra trực quan bằng Chrome ngày 03/10/2026

- Chụp và xem trực quan 21 tuyến ở 375 px và 1440 px sau khi dữ liệu fixture tải xong: 42 tổ hợp. Kiểm tra thêm cả 21 tuyến ở 360, 768 và 1024 px: 63 tổ hợp. Kết quả cuối: 105/105 không tràn ngang, không có lỗi JavaScript hoặc tài nguyên trên các lượt chụp. Ảnh và mã chạy Playwright được giữ ngoài repository tại `D:\HK5\OOAD\.visual-qa`; không đưa ảnh kiểm thử hoặc công cụ tạm lên GitHub.
- Thanh chọn tình huống/vai trò/chi nhánh/khách fixture chiếm khoảng 260 px chiều cao trên điện thoại, đẩy nội dung chính xuống dưới màn hình đầu. Thanh nay thu gọn mặc định còn 59 px ở 360–375 px; nút mở rộng có vùng nhấn 44 px, `aria-expanded`, liên kết `aria-controls`, dùng được bằng phím Enter. Ở desktop, các lựa chọn vẫn hiển thị trực tiếp.
- Khi chờ fixture tải xong, màn giao đồ lộ lỗi tràn 526 px trên viewport 375 px do bảng tiền bốn cột ép thẻ rộng ra. Bảng tiền nay trình bày theo từng khoản và ba dòng có nhãn “Cần thu”, “Đã đánh dấu nhận”, “Còn thiếu” trên điện thoại. Nhân viên thấy toàn bộ số tiền mà không cần vuốt ngang. Màn giao và nhận trả ở desktop cũng từng tràn đến 1456 px trên viewport 1440 px vì nhãn trạng thái tiền trong cột 300 px; bố cục tóm tắt tiền đã được điều chỉnh để vừa cột.
- Nút “Về đơn thuê” ở đầu màn giao/trả từng bị bó hẹp thành nhiều dòng trên điện thoại. Nút được đưa xuống dưới tiêu đề và giữ nhãn trên một dòng. Lần chạy đầu có một yêu cầu favicon trả 404; đã thêm favicon SVG cùng màu thương hiệu. Lần chạy cuối không còn lỗi này.
- Giới hạn: đây là QA tự động và kiểm tra ảnh chụp trên Chrome giả lập kích thước màn hình. Chưa kiểm tra trên thiết bị thật hoặc bằng trình đọc màn hình chuyên dụng. Các thao tác giao/trả và số tiền vẫn là bản xem trước từ fixture; không ghi giao dịch thật.
