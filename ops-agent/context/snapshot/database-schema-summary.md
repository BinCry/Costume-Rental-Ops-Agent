# Database Schema Summary

Schema hiện tại có **32 bảng**, chia thành 7 nhóm. Danh sách field đầy đủ nằm trong `database-schema.dbml` và `schema.prisma`.

## 1. Identity và phân quyền — 9 bảng

| Bảng | Dữ liệu chính | Ràng buộc quan trọng |
|---|---|---|
| `users` | email, phone, display name, avatar, trạng thái | Email/phone unique khi có; phải có ít nhất một phương thức liên hệ |
| `auth_identities` | provider, provider subject, email lúc liên kết | Unique `(provider, provider_subject)` và `(user_id, provider)` |
| `employees` | mã nhân viên, trạng thái làm việc, ngày vào/nghỉ, ngày kích hoạt | Shared PK với `users`; `TERMINATED` cần `terminated_at` |
| `branches` | mã, tên, địa chỉ, điện thoại, timezone | `branch_code` unique; timezone mặc định Việt Nam |
| `roles` | mã role, tên, actor group | `role_code` unique |
| `permissions` | code, module, action, scope | `code` unique |
| `role_permissions` | role và permission | Composite PK |
| `user_role_assignments` | user, role, branch, người gán | Không trùng cả khi `branch_id` null |
| `audit_logs` | actor, action, entity, before/after JSON | Append-only; actor có thể `SET NULL` |

## 2. Catalog, inventory và transfer — 10 bảng

| Bảng | Dữ liệu chính | Ràng buộc quan trọng |
|---|---|---|
| `costume_categories` | cây category | Không tự làm parent; parent `SET NULL` khi xóa |
| `costume_models` | mã mẫu, category, mô tả, chất liệu | `model_code` unique |
| `costume_model_accessories` | phụ kiện chuẩn và giá thay thế | Số lượng dương; tiền không âm |
| `costume_variants` | size, màu, edition, giá thuê/cọc/thay thế | `variant_code` unique; các khoản tiền không âm |
| `costume_media` | model hoặc variant, object key, thứ tự | Chính xác một trong `model_id`, `variant_id` có giá trị |
| `costume_units` | barcode, variant, chi nhánh, tình trạng, trạng thái | `unit_code` unique; chỉ `READY` được thuê |
| `unit_events` | lịch sử vòng đời unit | Append-only; unit là quan hệ sở hữu |
| `unit_blocks` | vệ sinh, sửa, kiểm tra, khóa thủ công | `blocked_from < blocked_until`; state–timestamp hợp lệ |
| `stock_transfers` | phiếu chuyển chi nhánh và workflow actor/time | Nguồn khác đích; optimistic `version` |
| `stock_transfer_items` | unit và tình trạng xuất/nhận | Unique `(transfer_id, unit_id)`; không trùng transfer hoạt động |

## 3. Policy và promotion — 2 bảng

| Bảng | Dữ liệu chính | Ràng buộc quan trọng |
|---|---|---|
| `rental_policy_versions` | thời gian hiệu lực, cách tính ngày, no-show, trễ, hủy, SLA refund | Bất biến; khoảng hiệu lực không chồng nhau |
| `promotions` | mã, loại/mức giảm, thời gian, hạn mức | Mã unique; thời gian và hạn mức hợp lệ |

## 4. Rental operations — 3 bảng

| Bảng | Dữ liệu chính | Ràng buộc quan trọng |
|---|---|---|
| `rental_orders` | khách, chi nhánh, thời gian, policy/promotion snapshot, pickup/return/settlement | Nhận và trả cùng chi nhánh; thời gian hợp lệ; tiền không âm |
| `rental_order_items` | variant, unit, khoảng chiếm dụng, giá/cọc snapshot, tình trạng giao/trả | Một dòng = một unit; GiST chống trùng lịch unit |
| `rental_item_accessories` | phụ kiện thực giao/trả và phí thiếu | Số lượng hợp lệ; snapshot không mất khi master bị xóa |

## 5. Finance — 3 bảng

| Bảng | Dữ liệu chính | Ràng buộc quan trọng |
|---|---|---|
| `payments` | order, mục đích, phương thức, số tiền, trạng thái, provider | Amount dương; idempotency unique; `SUCCEEDED` cần `paid_at` |
| `refunds` | payment nguồn, số tiền, trạng thái, người yêu cầu/duyệt | Tổng completed refund không vượt payment nguồn |
| `provider_webhook_events` | provider event, payload, trạng thái xử lý | Unique `(provider, event_id)`; xử lý idempotent |

## 6. CRM — 4 bảng

| Bảng | Dữ liệu chính | Ràng buộc quan trọng |
|---|---|---|
| `customers` | mã khách, chi nhánh ưu tiên, ngày sinh, số đo, ghi chú | Shared PK với `users`; ngày sinh không ở tương lai |
| `customer_interactions` | khách, chi nhánh/order/case, nhân viên, kênh, tóm tắt | Append-only; ngữ cảnh và actor dùng `SET NULL` |
| `crm_cases` | khách, order, chi nhánh, subject, priority, owner, trạng thái | State–timestamp hợp lệ; order phải thuộc đúng khách |
| `crm_case_history` | lịch sử trạng thái/owner | Append-only; case sở hữu history |

## 7. Platform events — 1 bảng

| Bảng | Dữ liệu chính | Ràng buộc quan trọng |
|---|---|---|
| `outbox_events` | event type, aggregate, payload, trạng thái retry | Ghi cùng transaction nghiệp vụ; consumer idempotent |

## Quan hệ xóa

| Loại quan hệ | Chính sách |
|---|---|
| Actor/ngữ cảnh tùy chọn | `SET NULL` |
| Child hoàn toàn thuộc parent | `CASCADE` |
| Giao dịch cốt lõi | `RESTRICT` |

## Trạng thái migration

- Initial migration: `apps/api/prisma/migrations/20261001120000_init/migration.sql`.
- Migration có raw SQL cho `CHECK`, `UNIQUE NULLS NOT DISTINCT`, partial unique index, `btree_gist` và GiST exclusion.
- Dùng `prisma migrate deploy` để apply vào database test/production.
- Không dùng `prisma db push` thay cho migration đã duyệt.

