# Báo cáo kiểm toán hoàn chỉnh giai đoạn UI/UX

Ngày kiểm toán: 04/10/2026. Phạm vi là frontend React dùng adapter fixture của Costume Rental Studio. Đợt này nối tiếp [đánh giá mười luồng chính](Đánh%20giá%20và%20tối%20ưu%20trải%20nghiệm%20mười%20luồng%20chính.md) và [QA responsive trước đó](Báo%20cáo%20QA%20responsive%20và%20khả%20năng%20truy%20cập%20các%20luồng%20lõi.md). Không thay nhận diện đã duyệt, schema Prisma, API hay chính sách nghiệp vụ.

## Kết luận trong phạm vi fixture

**Đạt nghiệm thu UI/UX để chuyển sang bước chuẩn bị tích hợp API.** Mười hành trình đầu cuối và năm kịch bản phục hồi/xung đột được chạy qua trong trình duyệt. Trạng thái rỗng và lỗi được rà trên 21 route; trạng thái tải được kiểm qua skeleton ở các màn dùng tài nguyên. Không thấy lỗi JavaScript hoặc tràn ngang trong lượt kiểm cuối. Đây là nghiệm thu giao diện và tương tác mô phỏng, không xác nhận giao dịch, phân quyền, bảo mật hoặc đối soát tiền thật.

## Hành trình đầu cuối

| Luồng | Điểm kiểm tra | Kết quả UI |
| --- | --- | --- |
| 1. Khám phá → yêu cầu thuê | Chọn kỳ mẫu, xem nhanh, sang form, báo giá, nhập khách, gửi | Đạt; giữ kỳ thuê trong URL, báo giá tự tải, xác nhận yêu cầu một lần. |
| 2. Đơn chờ → xác nhận/gán bộ | RT-1024, chọn BC-001 và BC-012, xem lại trước xác nhận | Đạt; mã bộ và phiên bản có trong bước xem lại. |
| 3. Giao bộ → thu tiền/cọc | RT-1028, quét BC-028, kiểm tình trạng/phụ kiện, xem tiền mặt và chuyển khoản chờ | Đạt; khoản thu tách biệt, chuyển khoản chưa đối soát khóa bước giao. |
| 4. Theo dõi bộ đang thuê | Tra BC-031, sau đó tra BC-001 không thuộc ACTIVE | Đạt; lượt tra sau xóa chi tiết khách cũ, tránh đọc nhầm người đang giữ. |
| 5. Trả một phần và hư hỏng | RT-1035, quét BC-035, chọn chờ đánh giá, xem trước 1/2 bộ | Đạt; BC-036 còn ở khách và cọc tiếp tục giữ được nêu rõ. |
| 6. Tạo đơn tại quầy | Tìm một khách theo số điện thoại, lấy báo giá, gán BC-001, tạo/xác nhận | Đạt; khách khớp duy nhất được chọn, form khóa sau khi tạo mẫu. |
| 7. Kho/block/điều chuyển | Tra BC-014, tạo block; duyệt DC-001, xuất, nhận BC-012 | Đạt; phiếu thể hiện 1/2 bộ đã nhận, bộ còn lại đang vận chuyển. |
| 8. Nhân viên và chi nhánh | Gán thêm role kho cho NV-001 tại Quận 1 | Đạt; role bán hàng vẫn còn, không tạo cặp role/chi nhánh trùng. |
| 9. Phân quyền checkbox | Tìm mã quyền, đổi tick, xem chênh lệch và lưu | Đạt; thấy số quyền thêm/bỏ và hành động lưu khi có nháp. |
| 10. CRM case | Sửa mô tả CS-001, thử rời case, quay lại và lưu | Đạt; nháp còn sau khi hủy chuyển, lịch sử có dòng cập nhật. |

## Ma sát tìm thấy và thay đổi trong lượt kiểm cuối

| Vấn đề | Trước | Sau | Ảnh hưởng |
| --- | --- | --- | --- |
| Menu mobile của nhân viên chỉ có bốn mục đầu | Các mục Kho, CRM và quản trị phải tìm trong thanh cuộn ngang; route sâu có thể mở với tab hiện hành nằm ngoài khung | Menu mở đủ 13 điểm đến theo quyền và một lối đổi khu; tab hiện hành tự nằm trong vùng nhìn thấy; Escape đóng menu và trả focus | Từ menu cần một lần mở và một lần chọn cho mọi điểm đến; không cần dò thanh ngang. |
| Chọn dòng ở layout hai cột trên điện thoại không đưa người dùng tới chi tiết | Chi tiết của Kho, Nhân viên, Vai trò và CRM nằm dưới viewport khoảng 900–1.144 px; xem nhanh catalog mở phía trên vị trí hiện tại | Vùng chi tiết được đưa vào viewport và nhận focus; đóng xem nhanh trả focus về thẻ đã mở | Bỏ lượt cuộn tìm chi tiết sau khi chọn; có ngữ cảnh rõ cho bàn phím và trình đọc màn hình. |
| Tra bộ đang thuê không khớp giữ thông tin khách cũ | Sau mã BC-001 không thuộc ACTIVE, thẻ “Người đang giữ” của lượt BC-031 vẫn hiện | Chi tiết cũ được xóa khi tra lỗi | Giảm nguy cơ nhân viên đối chiếu nhầm khách. |
| Một số link mobile thấp 33–40 px | Brand, link điều hướng phụ và link trong bảng hơi khó chạm | Chiều cao tối thiểu 44 px; checkbox vẫn có label bao quanh để chạm toàn dòng | Mục tiêu chạm của link rõ hơn, không đổi bố cục desktop. |
| Mô tả quyền dùng tên bảng kỹ thuật | Người quản trị thấy `role_permissions` trong phần giải thích | Dùng câu “Quyền được chọn áp dụng cho vai trò này” | Giải thích theo công việc thay vì cấu trúc lưu trữ. |

Các con số “trước → sau” của mười luồng nghiệp vụ (như số lần nhập lại, tra adapter, bước báo giá và nhận 1/2 bộ) nằm trong tài liệu đánh giá mười luồng chính. Chúng là phép đếm trên hành trình mẫu, không phải số liệu người dùng thực tế.

## Trạng thái và phục hồi

| Tình huống | Kết quả kiểm tra |
| --- | --- |
| Đang tải, dữ liệu rỗng, lỗi tải | Rà 21 route × hai trạng thái lỗi/rỗng: màn dùng tài nguyên fixture có thông báo rỗng hoặc lỗi và nút Thử lại; không có runtime error. Trang Tài khoản là màn mô phỏng xác thực, không dùng tài nguyên tải nên tình huống lỗi mạng không áp dụng. Trạng thái tải có skeleton/status trong các màn dùng `StateGate`. |
| Đơn bị đổi phiên bản | RT-1024 báo lỗi và giữ hai bộ đã chọn để nhân viên kiểm lại, không âm thầm xác nhận. |
| Bộ vừa mất khả dụng | BC-001 bị bỏ chọn khỏi đơn; có lối tải lại danh sách bộ. |
| Mất quyền | Thông báo rõ và nút xác nhận bị khóa. |
| Barcode khác chi nhánh | Nêu chi nhánh đang giữ bộ, không hiển thị chi tiết bộ cũ như kết quả hợp lệ. |
| Hoàn cọc thất bại | Sau khi kiểm bộ của RT-1033, cảnh báo còn mã RF-DEMO-01 và nhắc kiểm trước khi thử lại. Không có thao tác hoàn tiền giả. |
| Chuyển khoản chờ đối soát | Không đánh dấu tiền đã thu; không mở bước giao bộ. |
| Nháp nhân viên/role/CRM | Có chỉ báo chưa lưu và hộp thoại khi đổi đối tượng; hủy chuyển giữ nháp. |

## Kiểm tra responsive, hình ảnh và khả năng truy cập

- **Bố cục:** 21 route ở 360, 768 và 1024 px = 63 tổ hợp, không tràn ngang hay lỗi console. Bộ chụp kiểm cuối 21 route ở 375 và 1440 px = 42 ảnh, cũng không tràn hoặc lỗi runtime. Đã xem trực quan trang khách, CRM và phân quyền trên mobile cùng hero desktop; nhận diện thời trang sáng và bố cục thẻ được giữ.
- **Tự động accessibility:** axe-core quét 42 trạng thái route/viewport ở 375 và 1440 px theo WCAG 2 A/AA, 2.1 A/AA và 2.2 AA: **0 violation**. Kết quả này chỉ bao phủ quy tắc tự động; chưa xác nhận bằng thiết bị hỗ trợ thật.
- **Bàn phím và focus:** menu mobile mở/đóng bằng bàn phím, Escape trả focus; xem nhanh catalog và các vùng chi tiết mới nhận focus, có tên vùng; hộp thoại nháp có đường quay lại. Tab hiện hành trên thanh điều hướng nằm trong vùng nhìn thấy khi mở route sâu.
- **Chạm:** link chính trên mobile đạt tối thiểu 44 px. Checkbox nội tại 20–21 px nhưng nằm trong label cho phép chạm cả hàng; số đo riêng ô checkbox không phản ánh toàn vùng chạm.
- **Bảng tiền:** nhãn khoản thu hiển thị trong từng hàng ở 375 px, bảng không tràn; desktop giữ tiêu đề cột. Thanh điều khiển fixture gọn trên mobile và thao tác được bằng bàn phím.

## Việc còn lại khi có backend hoặc quyết định nghiệp vụ

1. **Chính sách ngày thuê và giữ chỗ:** chốt cách tính một ngày và thời hạn giữ bộ khi yêu cầu online chờ nhân viên duyệt; UI chỉ dùng kết quả báo giá/khả dụng từ adapter.
2. **Tiền và hoàn cọc:** API phải cung cấp chứng từ, kết quả đối soát chuyển khoản, phí/cấn trừ, số đã hoàn và idempotency. Phương thức hoàn qua SePay vẫn để mở; giao diện chỉ báo trạng thái và điểm cần chốt.
3. **Trả một phần:** backend cần lưu trạng thái từng bộ và chỉ quyết toán khi đủ điều kiện; bản UI hiện chỉ xem trước, không ghi nhận nhận trả hoặc hoàn tiền thật.
4. **Phân quyền:** backend phải tính quyền hiệu lực từ các role theo chi nhánh, kiểm mỗi thao tác và bảo vệ quản trị viên cuối cùng. Checkbox hiện chỉ đổi dữ liệu fixture.
5. **Google Login, CRM và media:** xác thực token, lịch sử bất biến có người/thời gian, tải ảnh bằng chứng và quyền xem ảnh cần dịch vụ thật.
6. **Kiểm tra sau tích hợp:** chạy lại mười hành trình với API, dữ liệu cạnh tranh, mạng chậm, bàn phím và trình đọc màn hình thật. Số liệu hiệu quả thao tác hiện mới là đo trên kịch bản mẫu.

## Ranh giới nghiệm thu

Giai đoạn UI/UX hoàn thành trong phạm vi frontend fixture. Đợt kiểm này không xác nhận tính đúng của dữ liệu sản xuất, Google OAuth, giao dịch tiền, tính toán báo giá hoặc enforcement phân quyền. Những phần đó thuộc giai đoạn tích hợp và kiểm thử sau tích hợp.
