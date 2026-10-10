# Đánh giá và tối ưu trải nghiệm mười luồng chính

## Phạm vi và nguyên tắc

Đợt này rà soát **toàn bộ hành trình** từ màn trước đến màn sau trên bản frontend dùng fixture. Giữ hệ màu, typography, bố cục và các quy tắc nghiệp vụ trong `business-rules.md` cùng `Quy chuẩn thiết kế giao diện và năm màn hình lõi.md`. Không thay Prisma, không tạo API hoặc tự tính kết quả tiền thay backend. Dữ liệu chỉnh trong trình duyệt là dữ liệu trình diễn, không phải giao dịch thật.

“Trước → sau” dưới đây là số thao tác hoặc chuyển màn **theo luồng mẫu đã đi thử bằng tay**; không phải số liệu đo hành vi người dùng. Khi trạng thái dữ liệu khác, số thao tác có thể khác.

## Kết quả theo luồng

| Luồng | Vướng mắc tìm thấy | Tối ưu đã làm | Khác biệt trước → sau |
| --- | --- | --- | --- |
| 1. Khám phá → gửi yêu cầu | Đổi trang mất chi nhánh, kỳ thuê, mẫu/size; khách nhập lại, phải bấm riêng để lấy báo giá. Lỗi nhập liệu thiếu vị trí sửa cụ thể. | Lưu bộ lọc và kỳ thuê trong URL; truyền ngữ cảnh từ catalog qua chi tiết và form; vào thẳng bước phù hợp khi mẫu/biến thể hợp lệ; tự lấy báo giá sau bước ngày; lỗi hiển thị cạnh trường. | Từ trang chi tiết đã chọn biến thể: bỏ **2 bước nhập lại** và **1 lần bấm lấy báo giá**. Back giữ bộ lọc. |
| 2. Đơn chờ → xác nhận/gán bộ | Màn xử lý dài, thao tác gán bộ ở dưới; URL đơn không có ở chi nhánh đang xem có thể âm thầm hiện đơn khác. | Liên kết đi nhanh đến phần chọn bộ; URL đơn giữ đúng mã và chi nhánh; nếu không có đơn thì báo rõ và không tự chọn đơn thay. Chỉ hành động trong quyền `rentals.manage.branch`. | Bỏ lần cuộn/tìm mục gán bộ; loại rủi ro thao tác nhầm đơn khi mở link. |
| 3. Giao bộ → thu tiền thuê/cọc | Route giao từ đơn bị chặn bởi điều hướng; quét, kiểm và tiền nằm xa nhau. Chuyển khoản chờ đối soát dễ bị hiểu là đã thu. | Mở đúng route giao theo quyền; thanh bước Quét → Kiểm → Tiền; yêu cầu quét và đối chiếu từng barcode; diễn đạt rõ tiền mặt là bản xem trước, chuyển khoản chưa đối soát không được tính đã thu. | Đi từ đơn đến giao bằng 1 điều hướng hợp lệ; các phần chính có liên kết trực tiếp thay vì cuộn dò. |
| 4. Theo dõi đang thuê | Tra barcode gọi fixture trùng hai lần; tìm không thấy vẫn giữ chi tiết cũ, dễ đọc nhầm khách/đơn. | Ô barcode lấy nét khi mở, một lần tra cho một lần nhập, xóa chi tiết cũ khi lỗi và chỉ hiện kết quả phù hợp. | **2 → 1** lần gọi adapter mỗi lượt tra; lỗi không còn thông tin cũ. |
| 5. Trả một phần/hỏng → quyết toán/hoàn cọc | Bản cũ buộc kiểm đủ mọi bộ mới có thể xem tiếp; chưa rõ bộ nào còn ở khách. Khoản cọc hoàn có thể bị hiểu là đã giao dịch. | Cho quét và kiểm tập con của đơn nhiều bộ; hiển thị số đã quét/tổng và bộ còn ở khách; chỉ xem trước nhận bộ, không tự hoàn cọc. Tách cọc giữ, phí, cấn trừ, đã hoàn, còn dự kiến hoàn. Giữ cảnh báo và lịch sử khi refund lỗi. | Đơn 2 bộ có thể xem trước **1/2** bộ thay vì buộc **2/2**; không tạo bước hoàn cọc giả. |
| 6. Tạo đơn tại quầy | Tìm một khách vẫn phải chọn thêm; tìm không khớp có thể giữ khách đã chọn trước đó. | Tự chọn khi chỉ có một kết quả, báo không có khách khi rỗng, chỉ dùng khách vẫn thuộc tập kết quả; giữ bước báo giá trước tạo đơn. | Với số điện thoại khớp duy nhất: bỏ **1 lần chọn khách**; không chuyển nhầm hồ sơ sau tìm kiếm. |
| 7. Tra kho/block/điều chuyển | Mã bộ sai vẫn giữ chi tiết cũ; nhãn trạng thái kỹ thuật, thiếu tín hiệu sau lưu; nguồn/đích điều chuyển dễ lẫn. | Xóa chi tiết khi tra lỗi; nhãn trạng thái tiếng Việt; thông báo tạo block/phiếu; nhãn chi nhánh xuất/nhận và lịch sử điều chuyển rõ nghĩa; reset ghi chú sau khi tạo. | Sau thao tác thấy kết quả ngay, không cần suy từ dữ liệu cũ; giảm một lần kiểm lại thủ công trong luồng mẫu. |
| 8. Gán role nhân viên | Thêm role cùng chi nhánh có thể thay role cũ; rời hồ sơ làm mất thay đổi đang sửa. | Gán bổ sung đúng cặp role–chi nhánh, chặn trùng, báo chưa lưu, có Bỏ thay đổi và hỏi trước khi chuyển nhân viên. | Một người giữ được **2 role cùng chi nhánh**; không phải nhập lại role trước. |
| 9. Tick quyền vai trò | Khó tìm quyền giữa nhiều nhóm; lưu ở cuối trang, khó nhận ra thay đổi; đổi role mất bản nháp. | Tìm theo tên/mã/mô tả; chọn/bỏ hàng loạt quyền đang hiển thị trong nhóm; xem trước mã thêm/bỏ; thanh lưu luôn thấy khi có thay đổi; hỏi trước khi chuyển role; cảnh báo nếu bỏ quyền quản trị khỏi role Admin. | Nhóm 4 quyền có thể chọn trong **1 lần bấm thay vì tối đa 4 checkbox**; số thêm/bỏ nhìn thấy trước lưu. |
| 10. Xử lý case CRM | Rời khách/case mất nội dung chưa lưu; người chỉ có quyền đọc vẫn nhìn thấy thao tác sửa; lưu nội dung thuần không thêm dòng lịch sử. | Cảnh báo trước khi rời bản nháp, có Bỏ thay đổi; khóa form và hành động nếu thiếu `crm.manage.branch`; ghi lịch sử khi chỉnh nội dung/thuộc tính trong fixture; nhãn trạng thái, mức ưu tiên tiếng Việt. | Giữ được ngữ cảnh sửa; trường hợp chỉ đổi mô tả từ **0 → 1** mục lịch sử. |

## Kiểm tra trạng thái và khả năng phục hồi

- **Đang tải, trống, lỗi mạng:** các route tiếp tục dùng `StateGate` và hành động thử lại; không để nội dung cũ giả làm dữ liệu mới.
- **Xung đột bộ/đơn, barcode sai chi nhánh, bộ bị block, mất quyền:** không tự chuyển sang đơn/bộ khác; thông báo lỗi giữ ngữ cảnh hiện tại để người dùng sửa hoặc thử lại.
- **Chuyển khoản chờ đối soát:** số dự kiến tách khỏi số đã thu; nút chốt giao không hợp lệ bị vô hiệu hóa với lý do.
- **Hoàn cọc thất bại:** giữ mã giao dịch và cảnh báo kiểm tra trước khi thử lại; giao diện không tạo một khoản hoàn thứ hai.
- **Bản nháp nhân viên, role, CRM:** có cảnh báo trước khi chuyển đối tượng, nút bỏ thay đổi và chỉ báo chưa lưu.

## Kiểm tra giao diện và kỹ thuật

Đã đi thử bằng trình duyệt các kịch bản: catalog → chi tiết → báo giá; xác nhận đơn chờ với hai barcode; giao bộ và tiền mặt/chuyển khoản chờ; tra đơn đang thuê; trả 1/2 bộ; trả có phí hỏng và refund thất bại; tạo đơn tại quầy; tạo block và nhận điều chuyển; gán hai role cùng chi nhánh; sửa quyền và xem trước; lưu case và kiểm lịch sử. Các hành động dùng adapter fixture.

Đã kiểm tra 22 route tại **375, 768, 1024 và 1440 px** (88 tổ hợp). Một lỗi tràn ngang ở thanh chọn tình huống demo tại 768 px được sửa; lần kiểm tra sau không còn route tràn ngang hoặc thiếu tiêu đề. Kiểm tra này xác nhận bố cục cơ bản; chưa thay thế thử nghiệm bàn phím, trình đọc màn hình và thử với dữ liệu thật.

## Phụ thuộc khi nối API và quyết định còn mở

1. **Trả một phần:** frontend hiện chỉ xem trước theo barcode đã kiểm. API cần xác nhận trạng thái từng `rental_item`/bộ, giữ các bộ còn ở khách và chỉ quyết toán/hoàn cọc khi đủ điều kiện. Không coi nút xem trước là đã nhận bộ thật.
2. **Tiền và cọc:** tổng, phí hỏng/trễ/thiếu, cấn trừ, số hoàn và kết quả đối soát phải do backend trả theo chứng từ. Cần khóa chống gửi trùng giao dịch và thử lại refund bằng mã giao dịch hiện có.
3. **Cạnh tranh dữ liệu:** kiểm version, khả dụng bộ trong kỳ, chi nhánh, quyền hiệu lực và trạng thái đơn ở API khi xác nhận/giao/trả; UI fixture chỉ mô phỏng lỗi xung đột.
4. **Phân quyền:** API tính quyền từ các role được gán theo chi nhánh và kiểm ở từng thao tác. Cần bảo vệ trường hợp quản trị viên cuối cùng mất `rbac.manage.all`. Seed chưa có mã quyền giao/trả riêng nên UI dùng `rentals.manage.branch` như đặc tả hiện hành.
5. **CRM:** lịch sử case từ backend phải ghi sự kiện bất biến kèm người và thời gian thật, không dựa vào lịch sử trong bộ nhớ trình duyệt.
6. **Chính sách ngày thuê:** vẫn là cấu hình chưa chốt; giữ báo giá từ adapter/API, không tự gán quy tắc 24 giờ hay ngày lịch trong giao diện.

