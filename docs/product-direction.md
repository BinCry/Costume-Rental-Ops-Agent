# Định hướng sản phẩm — Costume Rental Studio + Ops Agent

**Phiên bản:** 0.3 — đề xuất theo định hướng phát triển song song  
**Trạng thái:** bản định hướng cần tiếp tục hoàn thiện  
**Ngày:** 08/10/2026

## 1. Tóm tắt

Costume Rental Studio là web nghiệp vụ cho thuê trang phục. Costume Rental Ops Agent là một ứng dụng độc lập, dùng cùng định hướng giao diện và các luồng nền của Studio rồi bổ sung năng lực Ops Agent cho nhân viên vận hành.

Hai dự án phát triển song song. Bản Studio gốc vẫn là một ứng dụng web bình thường; không sửa repo đó để biến nó thành Agent. Bản trong repo này cần giữ cùng ngôn ngữ nghiệp vụ, luồng thuê, giao diện và trạng thái với Studio, đồng thời có thêm Ops Agent. Frontend được mang về hiện là bản demo dùng fixture; backend nghiệp vụ và connector chưa được sao chép hoặc xác nhận.

## 2. Mô hình phát triển

```text
Costume Rental Studio (repo gốc)
  web nghiệp vụ, tiếp tục phát triển riêng
              │
              ├── đồng bộ có chủ đích: domain, UI/UX, luồng và tài liệu đã xác nhận
              ▼
Costume Rental Ops Agent (repo này)
  bản nền Studio được sao chép + capability Ops Agent
```

Repo riêng giúp hai nhánh phát triển và phát hành độc lập. Việc đồng bộ là quy trình có chủ đích, không phải chia sẻ runtime, database hoặc tự động sao chép mọi thay đổi. Cách kết nối dữ liệu live và cách phát hành/chạy chung vẫn cần quyết định riêng; trước quyết định đó, frontend dùng fixture và Agent dùng tài liệu/nguồn demo có nhãn.

## 3. Ngữ cảnh và vấn đề

Nhân viên vận hành phối hợp đơn thuê, từng bộ vật lý, chi nhánh, lịch giao/trả, vệ sinh/sửa chữa và các khoản tiền. Giao diện nền đã có các luồng khách, nhân viên và quản trị, nhưng bản hiện tại là fixture chứ chưa phải nghiệp vụ backend.

Ops Agent bổ sung một cách tương tác để hỏi quy trình có trích dẫn, tìm việc cần chú ý và chuẩn bị bước tiếp theo. Agent phải dùng cùng vocabulary và trạng thái với giao diện Studio. Nó không được suy diễn dữ liệu live, cũng không được làm người dùng hiểu rằng fixture hay gợi ý của model đã cập nhật đơn/tiền.

## 4. Người dùng và công việc dự kiến

| Người dùng | Công việc trong bản có Ops Agent |
|---|---|
| Khách thuê | Tiếp tục các luồng xem mẫu, đặt thuê và theo dõi đơn của web Studio |
| Nhân viên quầy | Xử lý luồng thuê hiện có; hỏi SOP, xem việc cần chú ý và yêu cầu Agent tóm tắt có căn cứ |
| Nhân viên kho | Theo dõi mã bộ, vệ sinh/sửa/điều chuyển; hỏi quy trình theo đúng trạng thái nguồn |
| Quản lý | Xem ngoại lệ trong phạm vi được cấp và yêu cầu tóm tắt có nguồn/thời điểm |
| Người phụ trách Ops Agent | Quản lý knowledge base, đánh giá câu trả lời và cấu hình Agent riêng |

Ma trận quyền, dữ liệu thật và người dùng được phép dùng Agent phải được xác định trước khi mở provider hoặc triển khai production.

## 5. Lời hứa sản phẩm

Ứng dụng giữ các luồng Studio dễ nhận biết và bổ sung Ops Agent như công cụ hỗ trợ công việc. Agent cho biết câu trả lời đến từ tài liệu, dữ liệu DEMO hay provider đã cấu hình; nêu rõ thời điểm/phạm vi khi có dữ liệu vận hành. Agent phân biệt rõ thông tin, đề xuất và thao tác đã được hệ thống xác nhận.

## 6. Nguyên tắc thiết kế

1. **Phát triển song song:** repo Studio gốc và repo Ops Agent có code, build và nhịp phát hành riêng.
2. **Giữ parity:** dùng chung baseline nghiệp vụ, từ vựng, các trạng thái nhiều chiều, luồng lõi, design tokens và tiêu chuẩn responsive/accessibility qua các lần rà soát giữa hai repo.
3. **Ops Agent là phần bổ sung:** không thay hoặc âm thầm đổi hành vi của các luồng thuê đang có; thay đổi nghiệp vụ phải cập nhật tài liệu và được đối chiếu với Studio.
4. **Có nguồn cho câu trả lời:** trích tài liệu hoặc ghi provider, phạm vi và thời điểm truy vấn.
5. **Không biến giả định thành luật:** phân biệt nội dung đã xác nhận, phân tích, đề xuất, DEMO và chưa xác minh.
6. **Không giả lập thành công:** gợi ý/checklist không phải thao tác; không tự xác nhận đơn, giao/trả, thu/hoàn tiền, đổi chính sách hoặc cấp quyền.
7. **Quyền tại backend:** khi có dữ liệu/tài khoản thật, backend kiểm quyền cho từng truy vấn/tool call; UI và prompt không cấp quyền.
8. **Nguồn dữ liệu rõ ràng:** chưa có hợp đồng API được xác nhận. Không đọc trực tiếp database, không giả định endpoint snapshot đang chạy.
9. **Bảo vệ dữ liệu:** không dùng PII thật trong fixture/prototype; retention và dữ liệu gửi provider phải được chốt trước khi triển khai.

## 7. Phạm vi theo giai đoạn

### Giai đoạn 0 — Thiết lập nền độc lập

- Duy trì frontend nền và các luồng web trong repo Ops Agent độc lập với runtime của Studio.
- Giữ nhất quán UI/domain với phiên bản Studio được đối chiếu trong quá trình phát triển.
- Chốt hành vi MVP, persona, bề mặt giao diện Agent và nguồn dữ liệu.

### Giai đoạn 1 — Ops Agent có kiểm soát

- Bổ sung khu vực/panel Ops Agent cho nhân viên, hòa vào layout và design system hiện có.
- Hỏi đáp tài liệu có trích dẫn, hiển thị trạng thái nguồn và xử lý mâu thuẫn.
- Dùng dữ liệu tổng hợp có nhãn DEMO cho các tình huống vận hành; Agent chỉ đề xuất/checklist.
- Giữ ứng dụng chạy được bằng dữ liệu demo khi không cấu hình nguồn nghiệp vụ.

### Giai đoạn 2 — Provider nghiệp vụ (chưa chọn)

Chọn một hợp đồng dữ liệu cụ thể trước khi truy vấn vận hành live. Có thể là API được Studio công bố hoặc nguồn khác, nhưng phải xác định chủ sở hữu, authentication/scope, fields tối thiểu, freshness, lỗi, audit và quyền riêng tư. Không kết nối trực tiếp database. Connector phải có thể tắt mà không làm hỏng hỏi đáp tài liệu.

### Giai đoạn 3 — Thao tác có giám sát (chưa cam kết)

Chỉ xem xét khi có hệ thống đích và quyền được phê duyệt. Cho người dùng xem record, phạm vi và thay đổi; yêu cầu xác nhận cho đúng thao tác; chống trùng, audit và báo thành công dựa trên xác nhận từ đích. Tài chính, quyền và chính sách cần quy trình duyệt riêng.

## 8. Ranh giới sản phẩm

### Trong bản Ops Agent

- Bản nền frontend/UI/UX của Studio được duy trì parity trong repo này.
- Hỏi đáp SOP và nghiệp vụ có trích nguồn.
- Tóm tắt/hỗ trợ điều hướng công việc vận hành từ nguồn demo hoặc provider đã được duyệt.
- Capability Ops Agent bổ sung trên các luồng web, không thay thế web nghiệp vụ.

### Chưa mặc định

- API, database, SSO, session, deployment hoặc mã backend dùng chung với repo Studio.
- Truy vấn live từ Studio trước khi API contract, authentication và scope được xác nhận.
- Để model thực hiện giao dịch, quyết định phí, giá, chính sách, tiền, quyền hoặc trạng thái.
- Dùng fixture, snapshot code hoặc báo cáo UX làm bằng chứng rằng nghiệp vụ/backend đã chạy thật.

## 9. Đo lường thành công

- Các luồng Studio được sao chép không lệch từ vựng, trạng thái, nội dung nghiệp vụ hoặc design tokens so với baseline đã đối chiếu.
- Người dùng nhận ra các dữ liệu DEMO và đề xuất của Agent.
- Câu trả lời từ knowledge base dẫn được tới nguồn hỗ trợ; mâu thuẫn được hiển thị.
- Không có hành động nào được báo thành công nếu không có xác nhận từ hệ thống thực thi.
- Khi provider lỗi/tắt, luồng web demo và hỏi đáp tài liệu vẫn hoạt động.

## 10. Quyết định còn mở

- Prototype hiện chọn route nhân viên `/van-hanh/ops-agent`; có bổ sung panel theo ngữ cảnh trong dashboard hay không vẫn cần quyết định.
- Những màn/luồng nào phải luôn parity trước; nhịp rà soát đồng bộ với repo Studio là gì?
- Snapshot frontend hiện có cần cập nhật từ repo Studio chính ở commit nào?
- Agent chỉ đọc tài liệu/DEMO trong MVP hay cần API nghiệp vụ; nếu cần, API nào và ai cấp quyền?
- Ops Agent dùng xác thực riêng hay tích hợp danh tính qua hợp đồng được chọn?
- Model/provider, ngân sách, deployment, logging, retention và PII?
- Ai duyệt SOP và quy tắc nghiệp vụ còn mở?
