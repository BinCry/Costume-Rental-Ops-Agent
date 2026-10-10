# Quy trình đồng bộ với Costume Rental Studio

## Mục đích

Repo Ops Agent có bản sao frontend Studio làm baseline và phát triển song song với repo Studio gốc. Tài liệu này giữ cho hai nhánh nhất quán mà không buộc chúng dùng chung checkout, runtime hay database.

## Mốc nguồn hiện tại

- Frontend hiện có trong [`../apps/web/`](../apps/web/) được sao chép từ snapshot tại `D:\HK5\OOAD\Costume-Rental-Studio-ui-2026-10-03\BinCry-Costume-Rental-Studio-2031b82de222ff87962df39a1f13d14f18da7033`.
- Handoff nói snapshot này chưa được đối chiếu với repo chính và chưa được đưa vào repo chính. Snapshot không có metadata Git để xác minh commit; tên thư mục chứa chuỗi `2031b82...` không phải bằng chứng commit.
- Tài liệu UI/UX được lưu nguyên văn tại [`../ops-agent/context/studio-reference/ui-ux/`](../ops-agent/context/studio-reference/ui-ux/); manifest và giới hạn nguồn ở [`../ops-agent/context/studio-reference/README.md`](../ops-agent/context/studio-reference/README.md).
- Vì vậy, baseline này là nguồn để tiếp tục dựng prototype, chưa phải tuyên bố rằng frontend đã đồng bộ với phiên bản mới nhất của repo Studio.

## Những gì phải giữ đồng nhất

1. **Ngôn ngữ nghiệp vụ:** tên actor, đơn, bộ vật lý/unit, chi nhánh và các bước giao/trả.
2. **Chiều trạng thái:** trạng thái rental, unit, payment và refund không gộp thành một trạng thái chung.
3. **Luồng và quyết định đã xác nhận:** thay đổi chính sách, quyền, tiền, khả dụng hoặc xử lý ngoại lệ phải truy về tài liệu nghiệp vụ hiện hành.
4. **UI system:** typography, màu, spacing, kích thước điều khiển, trạng thái phản hồi, responsive và accessibility.
5. **Dữ liệu trình diễn:** fixture phải giữ nhãn DEMO; ví dụ khách/mã/tiền không được xem là giao dịch thật.

## Cách đồng bộ thay đổi

Khi repo Studio thay đổi:

1. Ghi URL, branch, commit SHA và ngày đối chiếu của nguồn.
2. So sánh ảnh hưởng lên UI/UX, route, vocabulary, state, policy, schema/API và fixture.
3. Chọn phần cần mang sang; không sao chép tự động mọi thay đổi hoặc backend chưa được yêu cầu.
4. Cập nhật frontend/tài liệu được chọn trong repo Ops Agent và ghi nội dung đã đồng bộ, nội dung chưa đồng bộ, cùng lý do.
5. Nếu nguồn chưa xác minh hoặc tài liệu mâu thuẫn, giữ nhãn `UNVERIFIED` và không tự biến nó thành quy tắc.

## Vai trò của Ops Agent

Ops Agent là capability bổ sung cho khu vực nhân viên. Nó dùng cùng context và thuật ngữ với giao diện nền, hiển thị nguồn/citation, phạm vi và freshness. Agent không thay luồng thuê hiện có; không được giả vờ một gợi ý là thao tác đã chạy. Tương tác với API Studio chỉ được thêm sau khi hợp đồng, xác thực, scope, PII và lỗi được xác định.

## Checklist cho mỗi thay đổi liên quan parity

- [ ] Nguồn Studio/commit và ngày đối chiếu đã được ghi.
- [ ] Nội dung là quyết định hiện hành, đề xuất, fixture hay chưa xác minh đã được gắn nhãn.
- [ ] Các trạng thái rental/unit/payment/refund còn tách riêng.
- [ ] Desktop, tablet, mobile, keyboard, focus và thông báo lỗi vẫn dùng được.
- [ ] Màn/luồng Studio cũ không bị thay đổi ngầm khi thêm Agent.
- [ ] Tài liệu yêu cầu và manifest resource đã được cập nhật nếu phạm vi/nguồn thay đổi.
