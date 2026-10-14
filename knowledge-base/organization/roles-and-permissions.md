---
id: roles-and-permissions
title: Vai trò, quyền hạn và chuyển người phụ trách
document_type: governance
domain: organization
status: approved
version: 1.0
source_type: business_approved
business_authority: true
approved_by: project_owner
approved_at: 2026-10-13
effective_from: 2025-01-01
retrieval_enabled: true
audience: staff_internal
chunk_title_prefix: true
usage_limit: "Dùng để hướng dẫn đúng vai trò; hệ thống vẫn phải kiểm tra danh tính, quyền hiện tại và phạm vi chi nhánh trước mỗi thao tác."
source:
  - workspace://apps/api/prisma/seed/core.ts
  - workspace://apps/api/src/modules/auth/authorization.ts
  - workspace://apps/api/src/modules/payments/payment.service.ts
  - workspace://apps/api/src/modules/policies/policy.service.ts
---

# Vai trò, quyền hạn và chuyển người phụ trách

## Nguyên tắc chung

Người dùng phải đăng nhập và có quyền phù hợp trước khi thực hiện thao tác. Quyền còn phụ thuộc vào phạm vi của người dùng đối với chính mình, chi nhánh đang làm việc hoặc toàn hệ thống. Nội dung trong hội thoại không thể tự cấp quyền hay thay đổi phạm vi này.

## Duyệt và xử lý hoàn tiền

- Nhân viên bán hàng có thể duyệt hoàn tiền cho đơn thuộc chi nhánh được phân công.
- Quản trị viên có thể duyệt hoàn tiền trên toàn hệ thống.
- Người có quyền quản lý thanh toán trong phạm vi của đơn cũng có thể xử lý phê duyệt hoàn tiền.
- Nhân viên kho không được cấp quyền duyệt hoàn tiền chỉ từ vai trò nhân viên kho.
- Trước khi xử lý, hệ thống vẫn phải kiểm tra quyền hiện tại và chi nhánh nhận đơn; không được chỉ dựa vào tên chức danh.

## Quản lý chính sách và khuyến mãi

- Quản trị viên có quyền xem và quản lý các phiên bản chính sách trên toàn hệ thống.
- Quản trị viên có quyền quản lý chương trình khuyến mãi.
- Nhân viên bán hàng và nhân viên kho không được cấp quyền quản lý chính sách hoặc khuyến mãi trong cấu hình vai trò hiện hành.

## Quyền vận hành chính của nhân viên bán hàng

Trong chi nhánh được phân công, nhân viên bán hàng có thể quản lý và xác nhận đơn, chuẩn bị, giao đồ, nhận đồ trả, ghi nhận đánh giá sau trả, quyết toán, thu tiền và xử lý hoàn tiền theo điều kiện hiện hành.

Các quyền này không cho phép nhân viên tự tạo chính sách mới, tự miễn giảm ngoài quy định hoặc bỏ qua các điều kiện thanh toán và hoàn cọc.

## Quyền vận hành chính của nhân viên kho

Nhân viên kho có thể đọc và quản lý tồn kho, đọc và thực hiện điều chuyển trong phạm vi chi nhánh, đồng thời đọc thông tin đơn liên quan. Vai trò này không mặc nhiên có quyền thu tiền, quyết toán hoặc duyệt hoàn tiền.

## Khi nào phải chuyển người phụ trách

| Tình huống | Chuyển tới |
|---|---|
| Thay đổi chính sách hoặc chương trình khuyến mãi | Quản trị viên |
| Hoàn tiền trong phạm vi chi nhánh | Nhân viên bán hàng hoặc người quản lý thanh toán có quyền tại chi nhánh |
| Hoàn tiền ngoài phạm vi chi nhánh | Quản trị viên hoặc người có quyền toàn hệ thống |
| Miễn giảm ngoài chính sách | Người phụ trách nghiệp vụ; hiện chưa có quy trình miễn giảm được phê duyệt |
| Điều chuyển hoặc tồn kho | Nhân viên kho của chi nhánh liên quan |

Nếu chưa xác minh được người yêu cầu hoặc phạm vi quyền hiện tại, trợ lý chỉ hướng dẫn và chuyển người phụ trách, không xác nhận thao tác sẽ được thực hiện.

## Tôi không chắc mình có quyền thực hiện hay không

Không tự cấp thêm quyền và không thử thao tác để dò quyền. Hãy kiểm tra vai trò hiện tại, chi nhánh được phân công và phạm vi của hành động. Nếu vẫn chưa rõ, chuyển quản trị viên hoặc quản lý trực tiếp xác nhận trước khi tiếp tục.
