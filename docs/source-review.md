# Rà soát nguồn tài liệu Costume Rental Studio

**Ngày rà soát:** 08/10/2026  
**Mục đích:** ghi nguồn domain/UI được dùng làm baseline cho repo Ops Agent. Hai repo phát triển song song; UI/luồng/domain cần nhất quán, còn runtime và API chưa được kết nối.

## Nguồn đã đọc và mức độ tin cậy

| Nguồn | Trạng thái đã thấy | Dùng để làm gì | Giới hạn |
|---|---|---|---|
| [Handoff](../ops-agent/context/HANDOFF.md), ngày 08/10/2026 | Người dùng cung cấp; bản gốc trong checkout dự án môn học đang là tệp chưa commit | Tình trạng bàn giao mới nhất, repo/commit được bàn giao, luồng vận hành và các điểm cần xác nhận | Tình trạng có thể thay đổi sau ngày bàn giao; chỉ là bối cảnh domain cho Ops Agent |
| [Phân tích nghiệp vụ gốc](../ops-agent/context/PROJECT_BA.md), phiên bản 1.0 ngày 25/09/2026 | Nằm trong repo Costume-Rental-Studio tại commit `adfdd11`; repo local ở `main`, có thay đổi README và handoff chưa commit | Mục tiêu, tác nhân, luồng thuê, quy tắc tài chính, quyền, dữ liệu và các đề xuất nghiệp vụ | Tài liệu tự phân biệt nội dung đã chốt với giả định/đề xuất; tài liệu snapshot mới hơn nói đây là phân tích lịch sử |
| [README của snapshot](../ops-agent/context/snapshot/project-readme.md) và [chỉ mục tài liệu snapshot](../ops-agent/context/snapshot/docs-index.md) | Lấy từ thư mục snapshot có tên chứa `2031b82...`; thư mục không có metadata Git để xác nhận HEAD/remotes | Tech stack, các module và cách nhóm snapshot tự phân loại nguồn chuẩn | Không chứng minh repo chính đã có mã/tính năng đó |
| [Frontend nền được sao chép](../apps/web/README.md) và [manifest](../ops-agent/context/studio-reference/README.md) | Đã sao chép từ thư mục snapshot có tên chứa `2031b82...`; app fixture được giữ trong repo Ops Agent | Bắt đầu phát triển parity UI và bổ sung Agent | Snapshot không có `.git`; cần xác minh commit với repo chính. Không có backend nghiệp vụ, không có API live |
| [Business rules snapshot](../ops-agent/context/snapshot/business-rules.md), [schema summary](../ops-agent/context/snapshot/database-schema-summary.md) | Tài liệu trong snapshot, ghi cập nhật nghiệp vụ 01/10/2026 | Mô hình một dòng đơn trên mỗi bộ vật lý, status, payment/refund, quyền, CRM và cấu trúc schema | Chỉ áp dụng nếu đúng schema/migration đã được xác nhận trong repo chính |
| [Đánh giá 10 luồng UX](../ops-agent/context/snapshot/operational-ux-review.md), [đối chiếu 40 tình huống](../ops-agent/context/snapshot/ui-business-flow-review.md), [quy chuẩn 5 màn hình lõi](../ops-agent/context/snapshot/core-ui-design.md) | Tài liệu thiết kế/kiểm toán giao diện của snapshot | Cách nhân viên xử lý đơn, giao/trả, theo dõi bộ, kho, quyền và case; trạng thái lỗi cần được giữ | Giao diện dùng fixture; các dòng “đã đi thử” không xác nhận backend/API nghiệp vụ thật |
| [Bộ tài liệu UI/UX được sao chép](../ops-agent/context/studio-reference/ui-ux/) | Bản sao nguyên văn các đặc tả, hướng dẫn demo, review UI/UX, responsive và accessibility từ snapshot | Làm chuẩn thiết kế và checklist parity trong repo Ops Agent | Cần ghi nhận commit/URL upstream khi đối chiếu repo Studio; tài liệu snapshot có thể cũ |

## Bối cảnh domain được rút ra

- Sản phẩm đích quản lý studio cho thuê trang phục theo nhiều chi nhánh; có Customer, Staff và Admin.
- Nghiệp vụ quan trọng nhất chạy theo vòng đời: tìm lịch/giá → yêu cầu → nhân viên duyệt và gán bộ vật lý → giao/thu thuê+cọc → nhận trả/kiểm tra → thu phụ phí, cấn trừ và hoàn phần cọc đủ điều kiện.
- Khả dụng phải được xét theo mã từng bộ, chi nhánh, lịch và block vệ sinh/sửa; một trạng thái `READY` riêng lẻ không đủ để khẳng định bộ trống ở một kỳ.
- Trạng thái đơn, trạng thái bộ, payment và refund là các chiều riêng. `CANCELLED` không có nghĩa tiền đã hoàn; giao diện fixture không phải giao dịch.
- Nhân viên bị giới hạn theo quyền và chi nhánh. Handoff yêu cầu server kiểm tra quyền; ẩn nút trên UI không phải kiểm soát bảo mật.
- Dữ liệu giao dịch tiền, quyền, giá và chuyển trạng thái cần truy vết. VND là số nguyên; cọc chưa quyết toán không phải doanh thu.
- Chỉ thu tiền thuê/cọc khi giao theo phương án hiện hành; chuyển khoản chờ đối soát không phải đã thu; hoàn cọc sau khi kiểm tra đồ trả.

## Khác biệt cần giữ rõ

1. **Nguồn chuẩn website chưa đồng nhất:** handoff nói repo chính chưa chứa toàn bộ snapshot; README snapshot chỉ định migration/schema/rules của snapshot làm nguồn chuẩn. Vì snapshot không có `.git`, các định nghĩa đó chưa được xác thực là trạng thái website. Snapshot frontend trong repo Ops Agent là baseline tạm để làm tiếp, cần đối chiếu với repo Studio.
2. **Số lượng so với từng bộ:** phân tích ngày 25/09 mô tả số lượng trên dòng đơn; business rules/schema snapshot ngày 01/10 mô tả mỗi dòng gắn với một bộ vật lý. Đây là khác biệt domain cần giữ nhãn và xác minh trước khi đồng bộ.
3. **Quyền:** phân tích gốc có đề xuất ngoại lệ ALLOW/DENY riêng cho nhân viên; snapshot ghi schema hiện không có permission override và quyền được gán qua role theo chi nhánh.
4. **CRM:** phân tích gốc đề xuất consent marketing, campaign, tag và loyalty; schema snapshot chỉ có khách, interactions và cases, các chức năng mở rộng chưa nằm trong schema.
5. **Giá/chính sách:** tài liệu gốc đề xuất nhiều phiên bản giá theo thời gian/chi nhánh; snapshot mô tả giá hiện lưu trên variant toàn chuỗi, còn policy có phiên bản. Không được giả định có giá khác chi nhánh hoặc giá đặt lịch nếu API/schema không xác nhận.
6. **API:** handoff chỉ xác nhận `GET /health`; snapshot mô tả nhiều UI fixture và API kế hoạch. Repo Ops Agent chưa tích hợp API. Nếu chọn API Studio làm nguồn live, cần contract, authentication/scope, freshness và audit được duyệt; không đọc database trực tiếp.
7. **Quyết định nghiệp vụ còn mở:** cách tính ngày, SLA duyệt, giữ bộ, phí trả trễ/hư hỏng, hoàn cọc/SePay, vệ sinh, đổi/gia hạn, gộp hồ sơ và giờ/ngày nghỉ cần được chốt trước khi agent đưa ra chỉ dẫn mang tính quy tắc.

## Quy tắc sử dụng nguồn trong Ops Agent

Mỗi dữ kiện hoặc chỉ dẫn cần thuộc một nhãn:

- **Đã xác nhận:** có trong quyết định/hợp đồng hiện hành được xác minh.
- **Tài liệu phân tích:** mô hình hoặc yêu cầu trong BA, chưa chứng minh đã triển khai.
- **Đề xuất:** phương án được tài liệu đưa ra nhưng cần người nghiệp vụ xác nhận.
- **Fixture/demo:** ví dụ trong dữ liệu trình diễn; không phản ánh trạng thái thật.
- **Chưa xác minh:** có trong snapshot hoặc nguồn cũ nhưng chưa đối chiếu repo/API hiện hành.

Khi hai nguồn khác nhau, agent phải báo rõ mâu thuẫn và nêu nguồn/ngày; không tự chọn phương án thuận tiện. Hiện Ops Agent chưa lấy trạng thái live từ Studio. Nếu sau này được cấu hình provider/API đã duyệt, câu trả lời về đơn/bộ/tiền phải nêu provider, phạm vi và thời điểm truy vấn. Nếu chưa có provider, Agent chỉ trả lời theo tài liệu hoặc dữ liệu DEMO và phải ghi rõ loại nguồn. Quy trình giữ parity giữa hai repo nằm ở [ui-parity.md](ui-parity.md).
