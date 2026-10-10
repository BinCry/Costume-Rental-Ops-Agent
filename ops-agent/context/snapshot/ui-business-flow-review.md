# Đối chiếu luồng UI/UX theo báo cáo rà soát nghiệp vụ

Ngày rà soát: 03/10/2026. Tài liệu đối chiếu với **Báo cáo rà soát nghiệp vụ toàn diện studio cho thuê trang phục.docx** và frontend React dùng fixture. Báo cáo Word là nguồn đề xuất; quyết định nghiệp vụ đã chốt vẫn theo thứ tự nguồn tại [README](README.md). Mọi thao tác trong giao diện mẫu chỉ thay đổi dữ liệu fixture trong phiên, không xác nhận giao dịch hoặc tồn kho trên máy chủ.

## 1. Hành trình đã nối trên giao diện

| Hành trình | Trạng thái giao diện hiện tại | Giới hạn khi nối API |
| --- | --- | --- |
| Khách tìm mẫu → chọn kỳ thuê → xem báo giá → gửi yêu cầu | Đã có trạng thái tải, trống, lỗi, hết khả dụng và xác nhận chờ duyệt. | Giá, lịch, hiệu lực báo giá và giữ chỗ phải do backend trả. |
| Nhân viên duyệt → gán barcode → chuẩn bị → giao | Có thể tạo và gán ngay tại quầy nếu có quyền, hoặc tạo yêu cầu chờ. Sau xác nhận, nhân viên kiểm từng barcode/phụ kiện để chuyển sang sẵn sàng giao; màn giao kiểm quét và tách tiền thuê/cọc. | Chuyển trạng thái, khóa lịch, thu tiền và đối soát chỉ là fixture/xem trước. |
| Theo dõi bộ đang thuê → yêu cầu gia hạn → trả | Tra theo barcode/khách/đơn; điểm vào nhận trả và bản nháp yêu cầu hạn mới nằm trên chi tiết đơn. | Gia hạn cần kiểm tra lịch từng bộ, báo giá mới và tiền phát sinh từ backend; bản nháp chưa sửa đơn. |
| Trả từng bộ → kiểm tình trạng → chờ đánh giá → quyết toán | Quét được một phần; mỗi bộ chọn Đạt hoặc Cần đánh giá. Trường hợp cần đánh giá yêu cầu mô tả, hiển thị cọc còn giữ; phí/hoàn chỉ đọc snapshot fixture. | Backend phải lập biên bản, lưu bằng chứng, phân công, tính phí/cấn trừ và ghi refund. |
| Kho → điều chuyển → nhận từng bộ | Nhận được 1/n barcode; phiếu còn `IN_TRANSIT` đến khi nhận đủ. Bộ nhận đạt mới `READY`; bộ không đạt bị giữ ở trạng thái chưa khả dụng. | Backend cần transaction cho từng dòng và đối chiếu lịch/địa điểm. |
| Chi nhánh → ngừng hoạt động | Xem số đơn, bộ và phiếu điều chuyển chưa xong; fixture chặn lưu khi còn nghĩa vụ này. | Backend cần kiểm thêm thu/hoàn, case, lịch và dữ liệu lịch sử. |
| Nhân sự, vai trò/quyền, CRM | Màn gán vai trò theo chi nhánh, tick quyền theo vai trò; hồ sơ khách, tương tác và case đã có trong bộ 18 màn hình. | Quyền phải kiểm lại ở API mỗi lần ghi; liên kết tài khoản khách cần xác minh danh tính. |

## 2. Đối chiếu 40 tình huống nghiệm thu của báo cáo

**Ký hiệu:** `UI` = có thể đi thử trong fixture hoặc có cảnh báo rõ; `Bản nháp` = có điểm tiếp nhận/xem điều kiện nhưng chưa ghi nghiệp vụ; `API/quyết định` = thiếu nguồn dữ liệu, luật hoặc giao dịch máy chủ để hoàn tất. Một dòng `UI` không đồng nghĩa đã nghiệm thu backend.

| Mã | Tình huống | Mức hiện tại | Bước còn thiếu |
| --- | --- | --- | --- |
| AT-01 | Hai nhân viên gán cùng barcode | UI | Khóa lịch/transaction chống chồng ở API. |
| AT-02 | Khách tại quầy nhận quyền sở hữu tài khoản online | API/quyết định | Xác minh số điện thoại/danh tính rồi mới liên kết. |
| AT-03 | Trùng tên, khác số không gộp hồ sơ | Bản nháp | Quy tắc matching và xác minh tài khoản; tại quầy chặn tạo trùng số đã có. |
| AT-04 | Không xóa chi nhánh có lịch sử | UI | Hiện dùng ngừng hoạt động, không có thao tác xóa; API bảo vệ lịch sử. |
| AT-05 | Không đóng chi nhánh còn nghĩa vụ | UI | Backend tính đủ nghĩa vụ tài chính, case và lịch. |
| AT-06 | Không nhận đặt vào ngày/giờ đóng cửa | API/quyết định | Cấu hình giờ, ngày nghỉ và API lịch. |
| AT-07 | Tạo khách/đơn/xác nhận nhanh tại quầy | UI | Giao dịch nguyên tử, phân quyền và xác minh khách. |
| AT-08 | Nhấn gửi hai lần chỉ tạo một đơn | UI | Khóa thao tác trong màn; idempotency ở API cho mọi nguồn. |
| AT-09 | Mất kết nối rồi gửi lại | API/quyết định | Mã idempotency và tra kết quả lần gửi trước. |
| AT-10 | Bộ chuyển sang vệ sinh khi xác nhận | UI | Kiểm lại lịch/trạng thái trong transaction. |
| AT-11 | Khách hủy lúc nhân viên đang duyệt | UI | Phiên bản và sự kiện hủy từ API. |
| AT-12 | Chuyển khoản chờ đối soát không được giao | UI | Xác nhận payment thành công từ nguồn đối soát. |
| AT-13 | Sửa giao dịch tiền mặt ghi nhầm | API/quyết định | Chứng từ điều chỉnh/void và quyền duyệt. |
| AT-14 | Khách nhận trễ, ghi giờ giao thực tế | Bản nháp | API giao nhận lưu thời điểm thực tế, không tự đổi hạn trả. |
| AT-15 | Gia hạn khi bộ còn trống | Bản nháp | Kiểm lịch, báo giá mới, thu phát sinh và lưu phiên bản. |
| AT-16 | Gia hạn xung đột lịch | Bản nháp | Kết quả xung đột từng barcode, phương án khác. |
| AT-17 | Đổi size trước khi nhận | Bản nháp | Kiểm bộ thay, chênh lệch giá/cọc, giải phóng gán cũ. |
| AT-18 | Trả 1/2 bộ, bộ kia vẫn ở khách | UI | Return record và allocation theo từng dòng. |
| AT-19 | Quét trùng một bộ khi trả | UI | UI khử trùng mã quét; API chống ghi trùng biên bản. |
| AT-20 | Hư hỏng cần đánh giá, giữ cọc | UI | Biên bản, bằng chứng, người xử lý và hạn xử lý. |
| AT-21 | Phí hỏng lớn hơn cọc | API/quyết định | Backend tính khoản còn phải thu và chứng từ riêng. |
| AT-22 | Hoàn tiền lỗi, không hoàn trùng | UI | API quản lý mã refund và retry idempotent. |
| AT-23 | Trả bình thường tự chuyển sang vệ sinh | API/quyết định | Sự kiện tồn kho và thời gian vệ sinh từ chính sách. |
| AT-24 | Vệ sinh xong sớm | Bản nháp | Kiểm xung đột rồi giải phóng lịch. |
| AT-25 | Điều chuyển bộ có booking tương lai | UI | API kiểm allocation và phương án gán lại. |
| AT-26 | Chỉ nhận một phần phiếu điều chuyển | UI | Transaction từng barcode, xử lý thiếu/hỏng. |
| AT-27 | Thu hồi quyền khi nhân viên đang mở màn | UI | API xác thực quyền tại lúc ghi. |
| AT-28 | Đổi giá chỉ áp dụng đơn mới | UI | Snapshot giá trong đơn và API phiên bản giá. |
| AT-29 | Hai ưu đãi tranh suất cuối | API/quyết định | Khóa ngân sách/giới hạn ưu đãi ở backend. |
| AT-30 | Báo cáo lịch sử của chi nhánh ngừng hoạt động | Bản nháp | API báo cáo từ dữ liệu lịch sử. |
| AT-31 | Trả sớm không tự hoàn tiền thuê | UI | Quy tắc hoàn thuê nếu có phải quyết định riêng. |
| AT-32 | Job no-show chạy lặp | API/quyết định | Idempotency của job và trạng thái đơn. |
| AT-33 | Khách tới sau khi đơn no-show giải phóng bộ | API/quyết định | Kiểm lại tồn/lịch, tạo quyết định mới. |
| AT-34 | Mất tem barcode, in lại | API/quyết định | Quy trình in tem giữ nguyên mã bộ và audit. |
| AT-35 | Chủ case nghỉ việc, gán lại | Bản nháp | Lịch sử người phụ trách và quyền chuyển case. |
| AT-36 | Khiếu nại hư hỏng gắn đơn/bằng chứng | Bản nháp | Case gắn đơn có sẵn; kho bằng chứng và audit cần API. |
| AT-37 | Cọc không tính doanh thu; refund lỗi không tính đã hoàn | UI | Báo cáo dựa payment/refund thành công. |
| AT-38 | Đổi địa chỉ chi nhánh không sửa chứng từ cũ | API/quyết định | Snapshot địa chỉ trên đơn/chứng từ. |
| AT-39 | Ngừng mẫu/biến thể, đơn cũ vẫn xem được | Bản nháp | Trạng thái mẫu/biến thể và truy vấn lịch sử. |
| AT-40 | Bộ nghỉ sử dụng, lịch sử thuê vẫn còn | Bản nháp | Vòng đời unit và API chỉ đọc lịch sử. |

## 3. Điểm cần quyết định và hợp đồng dữ liệu tiếp theo

1. **SePay và hoàn cọc:** Theo lựa chọn ngày 03/10/2026, UI để mở cách hoàn. Chỉ hiển thị trạng thái đối soát/hoàn tiền thực tế và điểm cần chốt; không giả định hoàn tự động hay thủ công. Cần quyết định nguồn xác nhận tiền thuê/cọc, phương thức hoàn, người duyệt, SLA và xử lý refund lỗi.
2. **Lịch:** Chốt giờ hoạt động, ngày nghỉ, cách đếm ngày thuê, khoảng chuẩn bị/vệ sinh và quy tắc đổi lịch/gia hạn. UI không thể tự xác nhận khả dụng ngoài snapshot fixture.
3. **Danh tính:** Khách tại quầy phải xác minh trước khi liên kết với tài khoản Google. Không dùng số điện thoại hoặc tên trùng làm bằng chứng sở hữu tài khoản.
4. **API theo hành trình:** Cần dữ liệu báo giá/khả dụng; xác nhận gán bộ có phiên bản; chuẩn bị/giao; payment và đối soát; return record từng bộ; assessment, phí và refund; chuyển kho từng bộ; nghĩa vụ chi nhánh; quyền theo vai trò/chi nhánh; CRM case và audit. Đây là nhóm năng lực cần tích hợp, không phải danh sách endpoint đã tồn tại.

## 4. Phạm vi kiểm tra giao diện của lượt này

- TypeScript, ESLint và Vite build chạy thành công.
- Đi thử trình duyệt: tại quầy tạo và gán barcode → kiểm bộ/phụ kiện → `READY_FOR_PICKUP`; trả 1/2 bộ với `PENDING_ASSESSMENT` và cọc đang giữ; điều chuyển nhận 1/2 bộ rồi giữ phiếu `IN_TRANSIT`; đóng chi nhánh có nghĩa vụ bị chặn.
- Không thay Prisma schema, không thêm endpoint, không ghi giao dịch thanh toán thực.
