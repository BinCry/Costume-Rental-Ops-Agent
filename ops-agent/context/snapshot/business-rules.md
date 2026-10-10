# Business Rules — Costume Rental Studio

**Cập nhật:** 01/10/2026  
**Phạm vi:** nghiệp vụ đang được phản ánh trong Prisma schema và initial migration.

## 1. Phạm vi hệ thống

- Studio có nhiều chi nhánh nhưng dùng chung catalog, giá và chính sách.
- Khách đặt online hoặc nhân viên lập đơn tại quầy.
- Khách tự đến đúng chi nhánh để nhận và trả; không có nhân viên giao hàng.
- Một dòng đơn đại diện cho một bộ trang phục vật lý, vì vậy không có `quantity` trên `rental_order_items`.
- Giá thuê, tiền cọc và giá thay thế đặt ở `costume_variants`; đơn đã xác nhận giữ snapshot riêng.
- Tiền lưu bằng `BIGINT` theo đơn vị VND.
- Thời điểm lưu bằng `TIMESTAMPTZ`; ứng dụng hiển thị theo `branches.timezone`, mặc định `Asia/Ho_Chi_Minh`.

## 2. Tác nhân và phân quyền

### Admin

- Quản lý chi nhánh, nhân viên, catalog, giá, policy, promotion và role/permission.
- Tạo trước tài khoản nhân viên ở trạng thái `PENDING`.
- Đăng ký trước unit vật lý và chỉ định chi nhánh nhận.

### Sales Staff

- Tạo và xác nhận đơn tại chi nhánh được phân công.
- Gán unit, chuẩn bị, xử lý khách nhận/trả tại quầy.
- Ghi nhận thanh toán thủ công và xử lý CRM theo quyền.

### Inventory Staff

- Nhận unit được admin chuyển tới chi nhánh.
- Kiểm tra tình trạng, đưa unit từ `INBOUND` sang `READY`, `CLEANING` hoặc `REPAIR`.
- Quản lý block vệ sinh/sửa chữa và điều chuyển kho.

### Customer

- Xem catalog, tạo và quản lý đơn thuộc chính mình.
- Khách tại quầy vẫn có `users` + `customers`; `auth_identities` có thể được liên kết sau.

Quyền được tính từ `user_role_assignments → roles → role_permissions`. Schema hiện tại không có permission override theo từng người.

## 3. Tài khoản nhân viên

```text
Admin nhập email nhân viên
→ tạo users(PENDING)
→ tạo employees
→ tạo user_role_assignments theo chi nhánh
→ nhân viên đăng nhập Google bằng đúng email
→ backend xác minh email_verified và Google sub
→ tạo auth_identities
→ employees.activated_at = now()
→ users.status = ACTIVE
```

Sau lần liên kết đầu, tài khoản được nhận diện bằng `(provider, provider_subject)`, không dùng email làm khóa định danh Google.

## 4. Catalog và unit vật lý

```text
costume_categories
→ costume_models
→ costume_variants
→ costume_units
```

- Model mô tả mẫu trang phục chung.
- Variant là một SKU theo size, màu và edition; chứa giá thuê/ngày, cọc và giá thay thế.
- Unit là một bộ vật lý có barcode riêng và thuộc một chi nhánh tại một thời điểm.
- Ảnh lưu ở object storage; `costume_media` chỉ lưu object key và metadata.
- Phụ kiện chuẩn của model lưu trong `costume_model_accessories`.
- Phụ kiện thực tế giao/trả của dòng đơn lưu snapshot trong `rental_item_accessories`.

Admin đăng ký unit mới với `INBOUND/UNINSPECTED`. Nhân viên kho chi nhánh nhận và kiểm tra; chỉ unit `READY` mới được cho thuê.

## 5. Block và điều chuyển unit

`unit_blocks` hợp nhất lịch không khả dụng và công việc vệ sinh/sửa chữa. Block `PLANNED` hoặc `IN_PROGRESS` làm unit không khả dụng.

Điều chuyển:

```text
REQUESTED → APPROVED → IN_TRANSIT → RECEIVED
          ↘ REJECTED
REQUESTED/APPROVED → CANCELLED
```

- Chi nhánh nguồn và đích phải khác nhau.
- Item không được sửa sau khi duyệt.
- Khi xuất: unit chuyển `IN_TRANSFER`, `current_branch_id` vẫn là chi nhánh nguồn.
- Khi nhận: cập nhật `current_branch_id`, tình trạng nhận và trạng thái sau kiểm tra trong cùng transaction.
- Một unit không được nằm trong hai phiếu điều chuyển đang hoạt động.

## 6. Luồng đơn thuê

```text
DRAFT
→ PENDING_CONFIRMATION
→ CONFIRMED
→ PREPARING
→ READY_FOR_PICKUP
→ ACTIVE
→ RETURN_INSPECTION
→ COMPLETED
```

Nhánh kết thúc: `REJECTED`, `CANCELLED`, `NO_SHOW`.

- `PENDING_CONFIRMATION` chưa đảm bảo giữ unit.
- Khi xác nhận, mỗi `rental_order_items` được gán một unit và khoảng chiếm dụng.
- Database ngăn cùng unit có lịch `HELD/CONFIRMED/ACTIVE` chồng nhau.
- Khách nhận tại quầy; `pickup_processed_by` là nhân viên quầy, không phải shipper.
- Khi trả, nhân viên ghi tình trạng, thiếu/hỏng và phí trên order/item.
- Sau nhận trả, unit chuyển sang `READY`, `CLEANING`, `REPAIR` hoặc `RETIRED` theo kết quả kiểm tra.

## 7. No-show, trả trễ và hủy

- Đơn `READY_FOR_PICKUP` quá `planned_start_at + no_show_grace_minutes` có thể chuyển `NO_SHOW` và giải phóng unit.
- Trả sau `planned_due_at + late_grace_minutes` phát sinh phí trễ theo policy snapshot của đơn.
- Đơn chưa xác nhận được hủy miễn phí.
- Đơn đã xác nhận áp dụng `free_cancel_before_hours` và `late_cancel_fee_percent`.
- Đơn đã `ACTIVE` không còn hủy; phải xử lý theo flow trả đồ.
- Hủy đơn không đồng nghĩa hoàn tiền; refund là giao dịch riêng.

## 8. Policy và promotion

- `rental_policy_versions` là policy toàn chuỗi, bất biến sau khi có đơn tham chiếu.
- Các khoảng hiệu lực policy không được chồng nhau.
- Thay policy bằng cách đóng phiên bản hiện tại và thêm phiên bản mới.
- Order lưu `policy_version_id`, nên thay đổi sau này không làm đổi đơn cũ.
- Mỗi đơn có tối đa một promotion; mã và số tiền giảm được snapshot khi xác nhận.

## 9. Thanh toán và refund

- `payments` là tiền thực nhận hoặc đang xử lý, tách theo `RENTAL`, `DEPOSIT`, `EXTRA`.
- `SUCCEEDED` yêu cầu `paid_at`.
- Tiền mặt/chuyển khoản ghi thủ công yêu cầu `recorded_by`.
- Gateway yêu cầu `provider_payment_id`; webhook phải xác minh chữ ký và xử lý idempotent.
- `refunds` luôn tham chiếu payment nguồn đã thành công.
- Tổng refund `COMPLETED` không được vượt số tiền payment nguồn.
- Payment/refund và quan hệ giao dịch cốt lõi dùng `ON DELETE RESTRICT`.

## 10. CRM ban đầu

CRM MVP gồm:

- `customers`: mã khách, chi nhánh ưu tiên, ngày sinh, số đo và ghi chú nội bộ.
- `customer_interactions`: timeline tương tác append-only.
- `crm_cases`: phiếu hỗ trợ/khiếu nại.
- `crm_case_history`: lịch sử trạng thái và người phụ trách.

Campaign, consent, tag và loyalty chưa nằm trong schema hiện tại; chỉ bổ sung khi có yêu cầu nghiệp vụ rõ ràng.

## 11. Chính sách xóa

- Actor vận hành và ngữ cảnh tùy chọn: `SET NULL` để giữ lịch sử.
- Bảng con hoàn toàn phụ thuộc cha: `CASCADE`.
- Order, payment, refund và liên kết nghiệp vụ cốt lõi: `RESTRICT`.
- Trong vận hành bình thường, ưu tiên đổi trạng thái `INACTIVE`, `TERMINATED` hoặc `RETIRED` thay vì xóa vật lý.

