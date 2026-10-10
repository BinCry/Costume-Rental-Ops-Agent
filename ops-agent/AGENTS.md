# Hướng dẫn làm việc trong repo Ops Agent

Repo này phát triển song song với Costume Rental Studio. `apps/web` là baseline frontend đã được mang về; hãy giữ các luồng Studio nhất quán với tài liệu/phiên bản đã đối chiếu và bổ sung Ops Agent cho nhân viên. Không sửa repo Studio gốc khi đang làm việc ở đây.

## Trước khi thay đổi

1. Đọc `../docs/product-direction.md`, `../docs/product-requirements.md`, `../docs/ui-parity.md` và `../docs/source-review.md`.
2. Dùng `context/HANDOFF.md` và `context/PROJECT_BA.md` để hiểu domain và tình trạng bàn giao.
3. `context/snapshot/` và `context/studio-reference/ui-ux/` là bản tài liệu tham khảo từ snapshot. Handoff ghi snapshot chưa xác nhận là commit chính thức; không mô tả nó như trạng thái hiện hành nếu chưa đối chiếu repo Studio.
4. Frontend trong `apps/web` dùng fixture. Không coi fixture, mockup, báo cáo UX hoặc test/demo route là nghiệp vụ/backend thật.

## Nguyên tắc sản phẩm

- Bổ sung Agent vào bản web nền; không thay luồng thuê, ngôn ngữ nghiệp vụ, quyền hay trạng thái hiện có một cách âm thầm.
- Giữ parity có chủ đích về vocabulary, rental/unit/payment/refund states, quy trình, design tokens, responsive và accessibility. Ghi nhận drift theo `../docs/ui-parity.md`.
- Dùng nguồn đã xác nhận cho nghiệp vụ. Gắn nhãn đã chốt, phân tích, đề xuất, DEMO hoặc chưa xác minh; nêu mâu thuẫn thay vì tự chọn chính sách.
- Không dùng dữ liệu demo để khẳng định giao dịch/tồn kho thật. Agent phải trích dẫn nguồn hoặc ghi provider, phạm vi và thời điểm nếu có dữ liệu live.
- Chưa kết nối API Studio, SSO hoặc database. Nếu cần dữ liệu live, chọn contract API/provider và quyền rõ ràng trước; không truy cập trực tiếp database.
- Kiểm quyền ở backend/tool. Không dùng prompt hoặc role do client gửi làm lớp phân quyền.
- Không để model tự quyết định khả dụng, phí, cấn trừ, số tiền hoàn, trạng thái đơn/bộ/tiền. Không tự xác nhận đơn, ghi nhận tiền, đổi chính sách hoặc cấp quyền.
- Trước thao tác ghi ở giai đoạn tương lai, hiển thị đúng record, phạm vi và ảnh hưởng; cần xác nhận rõ ràng, chống trùng và xác thực kết quả từ hệ thống đích.
- Giảm thiểu PII; không đưa dữ liệu khách thật, secret, token, mật khẩu hoặc connection string vào repo/prompt/log ngoài chính sách được duyệt.

## Nguồn và cập nhật

Thứ tự cùng cách giải quyết khác biệt được mô tả trong `../docs/source-review.md`. Không sửa bản sao tài liệu gốc; thêm nhận định vào docs Ops Agent và cập nhật manifest khi mang thêm resource hoặc đồng bộ nguồn.
