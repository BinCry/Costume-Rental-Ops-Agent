# Đặc tả hành vi — Costume Rental Ops Agent

**Phiên bản:** 0.1
**Trạng thái:** target design, chưa phản ánh runtime hiện có
**Ngày:** 11/10/2026

## 1. Tổng quan

Ops Agent là một orchestrator nhận mục tiêu, chọn skill/tool tại thời điểm chạy, quan sát kết quả và tiếp tục cho tới khi đạt tiêu chí hoàn thành, chạm giới hạn hoặc cần con người. Chat, RAG và một lần gọi tool riêng lẻ không đủ để gọi là agent.

```text
Agent = Goal + Tools + Loop + Termination
Agent đáng tin cậy = Model + Harness
```

Runtime hiện tại là API Python dùng embedding, pgvector và grounded generation; các hành vi ngoài hỏi đáp tài liệu vẫn là yêu cầu mục tiêu.

## 2. Đầu vào và trigger

| Trigger | Ví dụ | Hành vi đầu tiên |
|---|---|---|
| Chat | “Đảm bảo đơn ngày mai sẵn sàng trước 08:00” | Parse goal/constraint, yêu cầu làm rõ nếu thiếu dữ kiện bắt buộc |
| Nút nghiệp vụ | “Phân tích ảnh hưởng” trên đơn | Tạo case gắn với record và actor hiện tại |
| Lịch | Kiểm tra readiness lúc 17:00 | Chạy trong scope/branch cấu hình sẵn |
| Domain event | Đơn gia hạn, bộ hỏng, block trễ | Đánh giá ảnh hưởng trước khi quyết định mở case |

Domain event vận hành là **đề xuất**; chưa có publisher tương ứng trong outbox hiện tại.

## 3. Goal contract

Mỗi case phải lưu goal như dữ liệu có cấu trúc, không chỉ giữ trong lịch sử chat.

```json
{
  "goalType": "ENSURE_ORDER_READINESS",
  "scope": { "branchIds": ["branch-id"], "windowHours": 72 },
  "successCriteria": ["all_in_scope_orders_verified_ready"],
  "constraints": {
    "deadline": "2026-10-12T08:00:00+07:00",
    "maxTransfers": 2,
    "financialWritesAllowed": false
  },
  "requestedBy": "user-id"
}
```

Goal phải có scope, tiêu chí hoàn thành và constraint đo được. Câu lệnh một bước như “tóm tắt đơn này” là tool/RAG task, không cần agent loop.

## 4. Vòng lặp Agent

Mẫu mặc định là **Plan + ReAct**:

1. Dựng context tối thiểu từ goal, state, policy và observation cần thiết.
2. Model đề xuất bước/tool tiếp theo bằng structured output.
3. Harness kiểm tra schema, permission, policy, approval và ngân sách.
4. Workflow engine thực thi tool hoặc chuyển sang `WAITING_APPROVAL`.
5. Chuẩn hóa tool result thành observation có trạng thái rõ.
6. Ghi state, trace và tác dụng phụ đã xảy ra.
7. Chạy verification và termination checks.
8. Nếu môi trường thay đổi đáng kể, cập nhật plan; nếu không thì tiếp tục.

Model chỉ đề xuất. Harness sở hữu việc parse, validate, execute, persist, authorize và terminate.

## 5. Trạng thái case

| Trạng thái | Ý nghĩa |
|---|---|
| `NEW` | Đã nhận trigger nhưng chưa phân tích |
| `ANALYZING` | Đang lấy dữ liệu và xác định phạm vi ảnh hưởng |
| `PLAN_READY` | Có kế hoạch/ước lượng để xem trước |
| `WAITING_APPROVAL` | Đang chờ đúng actor duyệt action cụ thể |
| `EXECUTING` | Đang thực thi action đã cho phép |
| `MONITORING` | Đã thực hiện, đang chờ/kiểm tra trạng thái đích |
| `SUCCEEDED` | Tiêu chí hoàn thành đã được kiểm chứng |
| `FAILED` | Kết thúc bất thường và đã ghi nguyên nhân |
| `CANCELLED` | Actor có quyền đã hủy case |
| `HANDED_OFF` | Đã bàn giao đủ ngữ cảnh cho con người |

State phải nằm trong persistent store của Ops Agent; không dùng context window làm nguồn trạng thái duy nhất.

## 6. Điều kiện dừng

Harness kiểm tra theo thứ tự:

1. **Trước tool:** action có vượt quyền hoặc cần approval không?
2. **Sau observation:** tiêu chí hoàn thành có đúng bằng chứng không?
3. Tool + arguments có lặp vô ích không?
4. Đại lượng tiến triển có đứng yên qua nhiều vòng không?
5. Có vượt giới hạn bước, token, thời gian hoặc chi phí không?

| Kết thúc | Cách phát hiện | Kết quả |
|---|---|---|
| Đạt mục tiêu | Predicate/schema/read-back từ hệ thống nguồn | `SUCCEEDED` |
| Hết ngân sách | Counter của harness | `FAILED` + kết quả dở dang |
| Lặp | Fingerprint tool + arguments/observation | `FAILED` hoặc re-plan một lần |
| Bế tắc | Progress metric không đổi | `HANDED_OFF` |
| Cần người | Permission/policy gate | `WAITING_APPROVAL` |

Không tin câu “đã xong” do model tự tuyên bố nếu không có verification độc lập.

## 7. Context, retrieval và memory

### Context mỗi vòng

- Goal và constraints bất biến.
- State/plan hiện tại đã nén.
- Observation mới nhất và bằng chứng liên quan.
- Tool schema đúng với actor/scope hiện tại.
- Policy/SOP được retrieval theo nhu cầu, có source/version/freshness.

Không nạp toàn bộ hội thoại, CRM hoặc tất cả tài liệu nếu không cần.

### Memory

- **Session memory:** thông tin phục vụ hội thoại hiện tại.
- **Case state:** tiến độ, action, approval, deadline, retry và side effect.
- **Knowledge:** tài liệu đã ingest, version/hash và trạng thái duyệt.
- **Không lưu mặc định:** secret, token, toàn bộ PII, nội dung không có retention policy.

## 8. Skill catalog mục tiêu

| Skill | Goal điển hình | Tool chính | Verification |
|---|---|---|---|
| `answer-sop-with-citations` | Trả lời SOP có căn cứ | retrieval | Mọi claim chính có source |
| `daily-operations-planning` | Lập kế hoạch theo ngày/72 giờ | order, availability, block | Kế hoạch bao phủ toàn bộ scope |
| `rental-conflict-resolution` | Giải quyết overlap/gia hạn/đổi bộ | order, availability, reallocate | Order/version và allocation đọc lại hợp lệ |
| `late-return-recovery` | Giảm ảnh hưởng trả trễ | active rental, order, block | Các đơn bị ảnh hưởng có disposition |
| `costume-turnaround-management` | Đảm bảo vệ sinh/sửa kịp | unit, block | Block và unit state phù hợp |
| `cross-branch-transfer` | Điều chuyển bộ có kiểm soát | transfer tools | Transfer đạt trạng thái được yêu cầu |
| `payment-exception-review` | Tổng hợp ngoại lệ tiền | payment/refund read | Không suy trạng thái; không tự ghi tiền |

Mỗi skill cần trigger rõ, workflow 5–8 bước, references, schema đầu ra, tool tối thiểu và bước verification cuối.

## 9. Planning và đề xuất

Mỗi phương án phải có:

- Mô tả hành động.
- Record và nguồn dữ liệu liên quan.
- Preconditions và dependencies.
- Tác động dự kiến theo metric đã định nghĩa.
- Độ tin cậy/giới hạn dữ liệu.
- Action cần approval.
- Verification sau thực thi.

Không dùng LLM để tự tính availability, tiền hoặc tối ưu số học khi có thể dùng code/rule/optimizer. LLM dùng để hiểu mục tiêu, chọn skill/tool, giải thích và xử lý ngoại lệ mở.

## 10. Approval và handoff

Approval request tối thiểu gồm actor, action, arguments, record/version, ảnh hưởng, khả năng hoàn tác và thời hạn duyệt. Approval hết hiệu lực khi arguments hoặc version nguồn thay đổi.

Handoff phải cho biết:

- Goal và constraint gốc.
- Đã làm tới đâu.
- Tác dụng phụ đã xảy ra.
- Những phương án đã thử và lý do thất bại.
- Câu hỏi/quyết định cụ thể cần con người trả lời.
- Deadline và rủi ro nếu không xử lý.

## 11. Constraint bắt buộc

- Tool allowlist và schema validation ở backend.
- Quyền kiểm tại từng tool call, không dựa vào prompt/UI.
- Mặc định read-only; write tool mở theo action cụ thể.
- Giới hạn bước/token/thời gian/chi phí cho mỗi case.
- Không tự retry action tài chính hoặc action không idempotent.
- Tool output và user content luôn là dữ liệu không tin cậy.
- Không đọc database trực tiếp hoặc gọi URL tùy ý.
- Không dùng dữ liệu DEMO để thực hiện write lên Studio.

## 12. Acceptance criteria

- [ ] Agent giữ goal/constraints qua toàn bộ case và kiểm lại trước action cuối.
- [ ] Mỗi tool call có actor, permission decision, request/action ID và result.
- [ ] Case resume được sau khi process/browser dừng.
- [ ] Lặp và bế tắc được phát hiện trước khi chỉ còn lỗi “hết ngân sách”.
- [ ] Action cần approval không chạy trước quyết định hợp lệ.
- [ ] `SUCCEEDED` chỉ xuất hiện sau read-back/predicate kiểm chứng được.
- [ ] Handoff đủ thông tin để người nhận quyết định mà không đọc toàn bộ chat.
- [ ] Trace cho phép xác định vòng sai đầu tiên khi eval thất bại.

## 13. Tài liệu liên quan

- [Quy trình nghiệp vụ](./business-processes.md)
- [Tool và tích hợp](./tools-and-integrations.md)
- [Đánh giá và an toàn](./evaluation-and-safety.md)
- [Yêu cầu sản phẩm](./product-requirements.md)

