# Tool và tích hợp — Costume Rental Ops Agent

**Phiên bản:** 0.2
**Trạng thái:** inventory đề xuất; xem ghi chú hiện trạng bên dưới để phân biệt với contract đã chạy
**Ngày cập nhật:** 18/10/2026
**Người cập nhật:** BinCry <bincry2006@gmail.com>

## 1. Tổng quan và ranh giới

Tài liệu kiểm kê API Studio và đề xuất lớp tool cho Ops Agent. Các tên tool ở mục 3–4 là **đề xuất thiết kế**, không phải danh sách runtime đã đăng ký. Contract thực tế tại mốc 18/10/2026 là [`agent-tools/v1`](https://github.com/BinCry/Costume-Rental-Studio/blob/main/apps/api/src/modules/agent-tools/agent-tools.schema.ts), với [10 tool đọc và 11 tool ghi trong registry](https://github.com/BinCry/Costume-Rental-Studio/blob/main/apps/api/src/modules/agent-tools/agent-tools.registry.ts). Studio API chặn **toàn bộ tool ghi** bằng `AGENT_WRITE_TOOLS_NOT_READY`; route xác nhận/duyệt hiện có không gỡ chặn này. Trước khi thêm tool mới phải chốt quyền, chi nhánh, trường tối thiểu, freshness, lỗi, PII và test contract hai repo.

Ops Agent không gọi database trực tiếp. Tool backend đóng vai trò adapter giữa model/orchestrator và API được phép.

## 2. Nguồn API hiện có

Tại thời điểm lập tài liệu, Studio gốc mount:

- `/api/v1/rentals`
- `/api/v1/inventory`
- `/api/v1/payments`
- `/api/v1/scheduling`

Transfer routes nằm dưới `/api/v1/inventory/transfers`. Các router đều yêu cầu authentication; service tiếp tục kiểm permission theo module/action/scope.

### 2.1 Ánh xạ tên nghiệp vụ và mã hệ thống

Phần này dành cho lớp adapter và đội phát triển. Không đưa nguyên văn các tên kỹ thuật hoặc mã trạng thái vào câu trả lời cho khách hàng.

| Tên nghiệp vụ | Tên kỹ thuật |
|---|---|
| Đơn thuê | `RentalOrder` |
| Món trong đơn | `RentalOrderItem` |
| Bộ trang phục cụ thể | `CostumeUnit` |
| Mẫu trang phục | `Variant` |
| Giữ bộ cho đơn | `Allocation` |
| Khoảng thời gian tạm ngưng cho thuê | `UnitBlock` |
| Điều chuyển chi nhánh | `Transfer` |
| Thanh toán | `Payment` |
| Hoàn tiền | `Refund` |
| Kiểm tra khi nhận lại đồ | `Inspection` |

| Nhóm | Mã hệ thống |
|---|---|
| Đơn thuê | `DRAFT`, `PENDING_CONFIRMATION`, `CONFIRMED`, `PREPARING`, `READY_FOR_PICKUP`, `ACTIVE`, `RETURN_INSPECTION`, `COMPLETED`, `REJECTED`, `CANCELLED`, `NO_SHOW` |
| Vận hành trang phục | `INBOUND`, `READY`, `CLEANING`, `REPAIR`, `IN_TRANSFER`, `RETIRED` |
| Tình trạng thực tế | `UNINSPECTED`, `NEW`, `GOOD`, `FAIR`, `POOR`, `DAMAGED` |
| Giữ bộ cho đơn | `UNASSIGNED`, `HELD`, `CONFIRMED`, `ACTIVE`, `RELEASED`, `COMPLETED` |
| Lịch tạm ngưng | `PLANNED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED` |
| Điều chuyển | `REQUESTED`, `APPROVED`, `IN_TRANSIT`, `RECEIVED`, `REJECTED`, `CANCELLED` |
| Thanh toán | `PENDING`, `SUCCEEDED`, `FAILED`, `CANCELLED` |
| Hoàn tiền | `REQUESTED`, `PROCESSING`, `COMPLETED`, `REJECTED`, `FAILED` |

## 3. Read tools đề xuất

| Tool Agent | API nguồn ứng viên | Mục đích | Ghi chú |
|---|---|---|---|
| `list_rental_orders` | `GET /rentals/orders` | Liệt kê đơn theo scope/filter | Không trả PII không cần thiết |
| `get_rental_order` | `GET /rentals/orders/:orderId` | Đọc trạng thái đa chiều của đơn | Giữ `version` để chống update cũ |
| `check_availability` | `GET /rentals/availability` | Kiểm tra unit theo khoảng thời gian | Đây là nguồn availability, không suy từ `READY` |
| `list_order_events` | `GET /rentals/orders/:orderId/events` | Dựng timeline bằng chứng | Có freshness/source |
| `list_active_rentals` | `GET /inventory/active-rentals` | Theo dõi bộ đang thuê/quá hạn | Scope theo quyền actor |
| `list_units` | `GET /inventory/units` | Tìm unit/bộ thay thế | Trả trạng thái và branch cần thiết |
| `get_unit` | `GET /inventory/units/:unitId` | Đọc chi tiết unit | Không suy availability |
| `list_unit_events` | `GET /inventory/units/:unitId/events` | Timeline unit | Dùng cho evidence/audit |
| `list_unit_blocks` | `GET /scheduling/unit-blocks` | Đọc vệ sinh/sửa/inspection | Có thể dùng `/calendar` cho view lịch |
| `list_transfers` | `GET /inventory/transfers` | Đọc transfer liên quan | Phân biệt mọi trạng thái |
| `get_transfer` | `GET /inventory/transfers/:transferId` | Theo dõi transfer | Chỉ hoàn thành khi trạng thái đích đúng |
| `get_payment_summary` | `GET /payments/orders/:orderId/summary` | Đọc quyết toán | Tool nhạy cảm, lọc field |
| `list_payments` | `GET /payments/orders/:orderId` | Đọc payment riêng biệt | Không đánh đồng payment/order |
| `list_refunds` | `GET /payments/orders/:orderId/refunds` | Đọc refund | Không đánh đồng request/completed |

Tên tool là contract của Agent, không cần giống endpoint. Adapter phải chuẩn hóa output và error.

## 4. Write tools và mức kiểm soát

| Tool Agent đề xuất | API nguồn ứng viên | Mặc định | Approval |
|---|---|---|---|
| `create_unit_block` | `POST /scheduling/unit-blocks` | Tắt | Có thể cho phép theo policy nội bộ |
| `update_unit_block` | `PATCH /scheduling/unit-blocks/:blockId` | Tắt | Theo thay đổi deadline/assignee |
| `start_or_complete_unit_block` | `POST .../start|complete` | Tắt | Xác nhận bởi actor phù hợp |
| `request_transfer` | `POST /inventory/transfers` | Tắt | Bắt buộc trong MVP có write |
| `approve_transfer` | `POST .../approve` | Tắt | Bắt buộc; actor có quyền approve |
| `ship_or_receive_transfer` | `POST .../ship|receive` | Tắt | Người xử lý kho xác nhận |
| `reallocate_order` | `POST /rentals/orders/:orderId/reallocate` | Tắt | Bắt buộc |
| `extend_order` | `POST /rentals/orders/:orderId/extend` | Tắt | Bắt buộc |
| `prepare_or_mark_ready` | `POST .../prepare|ready` | Tắt | Chỉ khi có evidence/checklist |
| `record_payment_or_refund` | payment write endpoints | Cấm tự động | Quy trình tài chính riêng; không retry ngầm |

Các endpoint confirm/reject/cancel/no-show/pickup/return/assessment/complete tồn tại trong Studio nhưng không được đưa vào allowlist Agent nếu chưa có policy và approval matrix riêng.

## 5. Tool contract chuẩn

### 5.1 Request envelope

```json
{
  "toolCallId": "uuid",
  "caseId": "uuid",
  "actorId": "uuid",
  "arguments": {},
  "expectedVersion": 7,
  "idempotencyKey": "case-id:action-id",
  "approvalId": "uuid-or-null"
}
```

Không phải tool nào cũng cần `expectedVersion` hoặc idempotency key, nhưng write tool phải công bố rõ yêu cầu.

### 5.2 Result envelope

```json
{
  "status": "ok",
  "data": {},
  "source": "studio-api",
  "observedAt": "2026-10-11T10:00:00+07:00",
  "requestId": "request-id"
}
```

Trạng thái tối thiểu:

- `ok`: request thành công, có thể có danh sách rỗng hợp lệ.
- `not_found`: record không tồn tại hoặc không thấy trong scope.
- `forbidden`: actor không có quyền.
- `validation_error`: arguments sai schema/semantics.
- `version_conflict`: dữ liệu đã đổi, phải đọc lại và re-plan.
- `dependency_unavailable`: provider/tool lỗi.
- `unknown_outcome`: timeout sau write và chưa biết side effect; phải reconcile, không gọi lại mù.

Không dùng `{}` hoặc chuỗi rỗng để biểu diễn nhiều loại lỗi.

## 6. Validation và verification

Trước tool call:

1. Tool nằm trong allowlist của skill/case.
2. Arguments đúng JSON schema và quy tắc semantic.
3. Actor có quyền và branch scope phù hợp.
4. Approval còn hiệu lực cho đúng arguments/version.
5. Case chưa vượt ngân sách hoặc bị hủy.

Sau write:

1. Ghi response/request ID và side effect.
2. Đọc lại record bằng read tool.
3. So sánh predicate trạng thái đích.
4. Nếu kết quả không rõ, chuyển `MONITORING`/`HANDED_OFF`; không báo thành công.

## 7. RAG và knowledge integration

Chỉ ingest nội dung nghiệp vụ trong `knowledge-base/`. Không ingest `docs/` vào kho dùng để trả lời khách hàng. Bộ nạp tài liệu phải bỏ qua file có `retrieval_enabled: false`, tách front matter thành metadata và không ghép trường `source` vào phần nội dung tìm kiếm.

Mỗi chunk cần tối thiểu:

- `documentId`, tên và loại tài liệu.
- `version`, ngày hiệu lực, ngày ingest và hash.
- Trạng thái duyệt: verified/unverified/deprecated.
- Scope/branch nếu tài liệu không áp dụng toàn hệ thống.
- Vị trí trích dẫn có thể mở lại.

Retrieval output phải tách `content` khỏi instruction. Nếu nguồn mâu thuẫn, tool trả cả hai nguồn và trạng thái conflict; model không tự chọn policy.

## 8. Event và lịch

### Hiện trạng

Schema có `OutboxEvent`, worker và retry state, nhưng `outbox.events.ts` hiện chỉ định nghĩa `MEDIA_OBJECT_DELETE_REQUESTED`. Chưa có bằng chứng rằng rental/inventory/transfer/payment đang phát domain event cho Agent.

### Event đề xuất

- `RENTAL_ORDER_EXTENDED`
- `RENTAL_ORDER_STATUS_CHANGED`
- `RENTAL_RETURN_OVERDUE`
- `UNIT_STATUS_CHANGED`
- `UNIT_BLOCK_DELAYED`
- `TRANSFER_STATUS_CHANGED`
- `PAYMENT_STATUS_CHANGED`
- `REFUND_STATUS_CHANGED`

Tên/payload chỉ là đề xuất. Mỗi event cần event ID, aggregate/version, occurredAt, schema version và dữ liệu tối thiểu; consumer phải idempotent.

Nếu chưa có event, prototype có thể dùng scheduled scan/read API và phải ghi rõ đây là polling.

## 9. Bảo mật và dữ liệu

- Dùng service identity/ủy quyền được phê duyệt; không chuyển access token vào prompt.
- Quyền kiểm lại tại Studio API, không chỉ tại Ops Agent.
- Che phone/email/note nội bộ khi không cần cho goal.
- Không đưa raw customer note vào system/developer instruction.
- Tool không nhận SQL, URL hoặc method tùy ý từ model.
- Log schema/metadata cần thiết; không log secret hoặc toàn payload nhạy cảm.

## 10. Acceptance criteria

- [ ] Mỗi tool có owner, schema, permission, timeout, retry và verification policy.
- [ ] Read tool phân biệt empty, not-found, forbidden và provider error.
- [ ] Write tool có idempotency/concurrency strategy phù hợp.
- [ ] Version conflict khiến Agent đọc lại và re-plan.
- [ ] Timeout sau write không bị coi là thất bại an toàn để gọi lại ngay.
- [ ] API/tool chưa được duyệt không xuất hiện trong allowlist runtime.
- [ ] Event đề xuất không được mô tả như event đang production.

## 11. Tài liệu liên quan

- [Quy trình nghiệp vụ](./business-processes.md)
- [Đặc tả hành vi Agent](./agent-behavior-spec.md)
- [Đánh giá và an toàn](./evaluation-and-safety.md)

