# Biên bản bàn giao dự án Costume Rental Studio

## 1. Thông tin chung

| Nội dung | Thông tin |
|---|---|
| Tên dự án | Costume Rental Studio |
| Mục đích | Quản lý chuỗi studio chỉ cho thuê trang phục |
| Phạm vi vận hành | Khách hàng, nhân viên và quản trị viên; nhận và trả tại cùng chi nhánh |
| Ngày bàn giao | 08/10/2026 |
| Phiên bản tài liệu | 1.0 |
| Kho Git chính | `https://github.com/BinCry/Costume-Rental-Studio.git` |
| Nhánh đã kiểm tra | `main` |
| Commit tài liệu hiện có | `adfdd11` – bổ sung phân tích nghiệp vụ và thiết kế hệ thống |

## 2. Mục tiêu bàn giao

Tài liệu này giúp người tiếp nhận biết dự án đang ở đâu, có thể mở phần nào để xem, cách chạy bản mã nguồn hiện có, phần nào mới là giao diện mẫu và phần nào chưa được triển khai.

Hệ thống hướng đến quy trình:

```text
Khách xem trang phục
  → chọn chi nhánh và thời gian thuê
  → gửi yêu cầu
  → nhân viên duyệt và chọn đúng bộ vật lý
  → giao đồ và thu tiền thuê, tiền cọc
  → khách trả đồ
  → nhân viên kiểm tra tình trạng
  → tính phí phát sinh và hoàn phần cọc còn lại
```

## 3. Phạm vi nghiệp vụ đã thống nhất

### Có trong phạm vi

- Danh mục mẫu, size, màu, hình ảnh và mô tả trang phục.
- Quản lý từng bộ vật lý bằng mã riêng hoặc barcode.
- Quản lý nhiều chi nhánh và vị trí hiện tại của từng bộ.
- Khách gửi yêu cầu thuê online hoặc nhân viên tạo đơn tại quầy.
- Nhân viên duyệt yêu cầu online trước khi xác nhận.
- Kiểm tra lịch, chọn bộ cụ thể và ngăn trùng lịch.
- Giao và nhận trả tại cùng chi nhánh.
- Thu tiền thuê và tiền cọc khi giao đồ.
- Ghi nhận tiền mặt hoặc chuyển khoản thủ công.
- Kiểm tra trả đủ, trả trễ, thiếu, hỏng và trả từng phần.
- Quyết toán phần cọc được giữ lại và phần còn phải hoàn.
- Quản lý vệ sinh, sửa chữa, tạm khóa và điều chuyển bộ.
- Quản lý hồ sơ khách, lịch sử thuê, trao đổi và yêu cầu hỗ trợ.
- Ba nhóm người dùng: Customer, Staff và Admin.
- Chọn quyền theo vai trò và chi nhánh bằng checkbox.
- Đăng nhập Google/OIDC theo phương án đã phân tích.

### Chưa nằm trong giai đoạn đầu

- Bán trang phục.
- Giao hàng hoặc trả đồ khác chi nhánh.
- Tự động đối soát chuyển khoản qua SePay.
- Tự động hoàn tiền qua ngân hàng hoặc cổng thanh toán.
- Tích điểm, khuyến mãi tự động và phân nhóm khách nâng cao.
- Tùy chỉnh quyền riêng lẻ cho từng nhân viên ngoài quyền theo vai trò.

## 4. Vai trò người dùng

| Vai trò | Trách nhiệm chính | Phạm vi truy cập |
|---|---|---|
| Customer | Xem mẫu, gửi yêu cầu, theo dõi đơn và thông tin của mình | Hồ sơ và đơn của chính khách |
| Staff | Duyệt đơn, chọn bộ, giao/trả, thu tiền, kiểm kho và hỗ trợ khách | Chi nhánh được phân công và quyền được cấp |
| Admin | Quản lý chi nhánh, người dùng, vai trò, quyền, danh mục, giá và báo cáo | Toàn chuỗi theo quyền |

Quyền của nhân viên phải được kiểm tra ở máy chủ theo cả vai trò và chi nhánh. Không được tin vào quyền do giao diện gửi lên. Mọi thay đổi quyền hoặc dữ liệu tài chính cần được lưu nhật ký thao tác.

## 5. Trạng thái dự án tại thời điểm bàn giao

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Tài liệu nghiệp vụ | Hoàn thành bản phân tích | Đã có trong thư mục `Tài liệu` của repo chính |
| Phạm vi và luồng UI/UX | Đã thiết kế và kiểm toán | Có fixture cho luồng khách, nhân viên và quản trị |
| Frontend | Có bản trình diễn fixture | Chưa nối API nghiệp vụ thật |
| Express foundation | Đã có trong snapshot mã nguồn | Có health check, middleware bảo mật, log và error contract |
| API nghiệp vụ | Chưa hoàn thành | Endpoint hiện tại cần xem là nền tảng; `/health` là endpoint đã xác nhận |
| Google Login | Chưa tích hợp production | Cần thiết kế callback, session, kiểm tra tài khoản và branch scope |
| Database | Có Prisma schema và migration thiết kế | Cần apply, seed và kiểm thử trên PostgreSQL thật |
| Thanh toán | Ghi nhận thủ công | Chưa tích hợp SePay hoặc hoàn tiền tự động |
| Kiểm thử tích hợp | Chưa hoàn tất | Cần kiểm thử cạnh tranh lịch, quyền, tiền và retry |
| Triển khai production | Chưa bàn giao | Chưa nhận secret, domain hoặc máy chủ production |

## 6. Công nghệ sử dụng

### Frontend

- React 19.
- TypeScript 6.
- Vite 8.
- Tailwind CSS 4.
- React DOM.
- Dữ liệu giao diện hiện dùng fixture adapter; chưa coi fixture là dữ liệu thật.

### Backend nền tảng

- Node.js 22, yêu cầu từ `22.12.0`.
- TypeScript 6.
- Express 5.
- Zod để kiểm tra dữ liệu đầu vào.
- Pino và pino-http để ghi log có cấu trúc.
- Helmet, CORS và express-rate-limit cho lớp bảo vệ HTTP.
- tsup để build API.

### Dữ liệu và kiểm thử

- PostgreSQL 16.
- Prisma 7 và `@prisma/adapter-pg`.
- Vitest và Supertest.
- pnpm 11.1.2.
- ESLint, Prettier, Husky và lint-staged.

## 7. Vị trí mã nguồn và tài liệu

### Repo Git chính

Repo hiện đã kiểm tra tại `D:\HK5\OOAD\Costume-Rental-Studio`. Ở commit `adfdd11`, repo chính hiện chứa README và tài liệu phân tích trong thư mục `Tài liệu`.

### Snapshot mã nguồn cần đối chiếu

Trong workspace hiện có bản snapshot mã nguồn đầy đủ ở:

`D:\HK5\OOAD\Costume-Rental-Studio-ui-2026-10-03\BinCry-Costume-Rental-Studio-2031b82de222ff87962df39a1f13d14f18da7033`

Snapshot này có `apps/api`, `apps/web`, Prisma, migration, seed và cấu hình pnpm workspace. Tên thư mục chứa mã commit snapshot `2031b82...`; người tiếp nhận cần kiểm tra lại nhánh/commit trên GitHub trước khi tiếp tục phát triển. Không coi thư mục snapshot ngoài repo chính là nguồn bàn giao chính thức cho đến khi được đưa vào Git và chốt commit.

### Tài liệu quan trọng

- `README.md`: giới thiệu dự án, tech stack, cách chạy và trạng thái.
- `Tài liệu/Phân tích nghiệp vụ và thiết kế hệ thống studio cho thuê trang phục.md`: phạm vi, quy tắc, database, API dự kiến và kịch bản nghiệm thu.
- `apps/api/prisma/schema.prisma`: mô hình dữ liệu, khi sử dụng snapshot mã nguồn.
- `apps/api/prisma/migrations`: migration database, khi sử dụng snapshot mã nguồn.
- `apps/api/.env.example`: danh sách biến môi trường backend.
- `apps/web`: mã nguồn giao diện React.

## 8. Cách chạy bản mã nguồn hiện có

Thực hiện trong thư mục gốc của snapshot mã nguồn hoặc workspace đã được đưa vào repo chính.

### Điều kiện

- Node.js `>=22.12.0`.
- pnpm `11.1.2`.
- PostgreSQL nếu cần chạy migration, seed hoặc nghiệp vụ database.
- PowerShell hoặc terminal tương thích.

### Cài đặt

```powershell
pnpm install
Copy-Item apps/api/.env.example apps/api/.env
```

Thiết lập tối thiểu trong `apps/api/.env`:

```dotenv
NODE_ENV=development
PORT=4000
WEB_URL=http://localhost:5173
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<database>
```

Nếu frontend cần gọi API, có thể tạo `apps/web/.env`:

```dotenv
VITE_API_URL=http://localhost:4000
```

Không commit `.env`, mật khẩu, client secret Google, khóa SePay, token hoặc connection string thật.

### Chạy giao diện và API

```powershell
pnpm dev
```

Hoặc chạy riêng:

```powershell
pnpm dev:api
pnpm --filter @costume/web dev
```

Địa chỉ mặc định:

- Frontend: `http://localhost:5173`
- API: `http://localhost:4000`
- Health check: `http://localhost:4000/health`

### Cơ sở dữ liệu phát triển

Sau khi tạo database và đặt `DATABASE_URL`:

```powershell
pnpm --filter @costume/api db:migrate
pnpm db:seed
pnpm --filter @costume/api db:studio
```

Không chạy seed profile demo trên database production thật. Với production, phải xác nhận profile seed và quyền truy cập trước khi chạy.

## 9. Lệnh kiểm tra trước khi nhận việc

```powershell
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

Nếu database được cấu hình:

```powershell
pnpm --filter @costume/api db:validate
pnpm --filter @costume/api db:migrate:deploy
```

Kết quả kiểm tra phải ghi lại commit, môi trường, thời điểm và lỗi còn tồn tại. Không đánh đồng `build` thành kiểm thử nghiệp vụ thành công.

## 10. API hiện có và API cần phát triển

Endpoint đã xác nhận trong nền tảng hiện tại:

| Method | Đường dẫn | Mục đích | Trạng thái |
|---|---|---|---|
| GET | `/health` | Kiểm tra tiến trình API | Đã có |

Nhóm API dự kiến, chưa được coi là hợp đồng đã triển khai:

- `/api/v1/auth`: Google Login, session và tài khoản.
- `/api/v1/costumes`: danh mục, biến thể và tìm kiếm.
- `/api/v1/availability`: lịch trống và báo giá dự kiến.
- `/api/v1/rentals`: tạo, duyệt, xác nhận, giao và nhận trả.
- `/api/v1/payments`: khoản thu, cọc, cấn trừ và hoàn tiền.
- `/api/v1/customers`: hồ sơ và lịch sử thuê.
- `/api/v1/admin`: chi nhánh, nhân viên, vai trò, quyền và báo cáo.

API cần thống nhất response envelope, mã lỗi, request ID, phân trang, idempotency key cho thao tác tiền và quy tắc xử lý lỗi xung đột lịch trước khi frontend chuyển từ fixture sang API.

## 11. Thiết kế dữ liệu cần bảo toàn

Mô hình đã phân tích gồm các nhóm: tài khoản/quyền, chi nhánh, danh mục, mẫu và biến thể, từng bộ vật lý, kho và điều chuyển, đơn thuê, khoản thu/hoàn, hồ sơ khách, CRM và audit log.

Các nguyên tắc không được bỏ qua:

- Một đơn phải gắn với từng bộ vật lý cụ thể, không chỉ lưu số lượng.
- Giá thuê, tiền cọc và chính sách phải được snapshot tại thời điểm xác nhận đơn.
- Không cho xác nhận hai đơn chồng lấn trên cùng một bộ.
- Bộ đang thuê, vệ sinh, sửa chữa hoặc bị khóa không được giao cho khách.
- Tiền thuê, tiền cọc, phí phát sinh và tiền hoàn là các khoản riêng.
- Tổng tiền hoàn không vượt số tiền đã thu thành công.
- Tiền lưu bằng số nguyên đồng Việt Nam, không dùng số thực gần đúng.
- Lịch sử giao dịch và thay đổi trạng thái cốt lõi không xóa cứng.
- Thời gian phải lưu rõ múi giờ và hiển thị theo giờ chi nhánh.

## 12. Luồng nghiệm thu ưu tiên

1. Khách tìm trang phục → chọn chi nhánh, ngày nhận/trả → gửi yêu cầu.
2. Nhân viên xem đơn chờ → kiểm tra lịch → chọn bộ → xác nhận hoặc từ chối.
3. Nhân viên giao đồ → kiểm tra tình trạng trước giao → thu tiền thuê và cọc.
4. Nhân viên theo dõi bộ đang thuê và người đang giữ.
5. Khách trả đủ, trả trễ, thiếu, hỏng hoặc trả một phần → kiểm tra → quyết toán/refund.
6. Nhân viên tạo đơn nhanh tại quầy.
7. Nhân viên tra cứu kho, khóa bộ hoặc điều chuyển giữa chi nhánh.
8. Admin gán vai trò và chi nhánh cho nhân viên.
9. Admin tick quyền theo vai trò và kiểm tra quyền hiệu lực.
10. Nhân viên mở hồ sơ khách, xem lịch sử và xử lý case CRM.

Mỗi luồng phải kiểm tra cả loading, empty, error và conflict; đặc biệt là xung đột bộ vừa được nhân viên khác xác nhận và lỗi thử lại thao tác thanh toán.

## 13. Các quyết định nghiệp vụ còn mở

| Vấn đề | Trạng thái cần chốt |
|---|---|
| Cách tính một ngày thuê | Ngày lịch hoặc 24 giờ; cần cấu hình theo policy phiên bản |
| Đơn online chờ duyệt | Đề xuất chưa giữ bộ; cần chốt SLA duyệt và cách cảnh báo |
| Phí trả trễ | Cần mức phí, thời điểm bắt đầu tính và người được duyệt |
| Hư hỏng chưa định giá | Đề xuất chờ đánh giá, không tự trừ cọc |
| Hoàn cọc | Tiền mặt, chuyển khoản thủ công hay tích hợp cổng thanh toán |
| SePay | Có dùng đối soát tự động không; nếu có cần hợp đồng webhook và retry |
| Vệ sinh sau trả | Thời lượng khóa bộ và trường hợp ngoại lệ |
| Đổi/gia hạn đơn | Có cho phép không; cách kiểm tra lại lịch và giá |
| Gộp hồ sơ khách | Điều kiện xác minh trước khi gộp hai hồ sơ |
| Giờ hoạt động | Giờ riêng theo chi nhánh và cách kiểm tra ngày lễ |

Không tự triển khai các nội dung trên như quy tắc đã chốt nếu chưa có người phụ trách nghiệp vụ xác nhận.

## 14. Rủi ro và lưu ý bàn giao

- Repo Git chính hiện chưa chứa toàn bộ mã nguồn ứng dụng; phải chốt cách đưa snapshot mã nguồn vào repo trước khi phát triển tiếp.
- Giao diện fixture có thể tạo cảm giác giao dịch đã thành công nhưng chưa có API lưu dữ liệu thật.
- Schema và migration cần chạy thử trên PostgreSQL để xác nhận index, constraint và dữ liệu seed.
- Google Login cần cấu hình redirect URI, kiểm tra issuer/audience/email verified, session và thu hồi phiên.
- Quyền theo chi nhánh phải được kiểm tra ở mọi truy vấn và lệnh ghi, không chỉ ẩn nút trên frontend.
- Thanh toán và hoàn cọc cần idempotency, audit và đối soát; không xem trạng thái “đang chờ” là đã hoàn tiền.
- Chưa có dữ liệu production, secret production hoặc tài khoản vận hành trong bàn giao này.

## 15. Checklist xác nhận bàn giao

- [ ] Người nhận đã truy cập được repo Git và được cấp quyền phù hợp.
- [ ] Đã chốt commit nguồn chính thức; không dùng snapshot ngoài repo làm nguồn duy nhất.
- [ ] Đã đọc README và tài liệu phân tích nghiệp vụ.
- [ ] Chạy được frontend và API ở môi trường local.
- [ ] `GET /health` trả kết quả thành công.
- [ ] Đã tạo `.env` từ `.env.example`, không commit secret.
- [ ] Đã xác định database development và cách reset dữ liệu mẫu.
- [ ] Đã chạy typecheck, lint, test và build; lưu kết quả.
- [ ] Đã chốt các quyết định ngày thuê, pending hold, phí trễ và hoàn cọc.
- [ ] Đã xác định người duyệt nghiệp vụ cho quyền, tài chính và CRM.
- [ ] Đã lập backlog API theo mười luồng nghiệm thu ưu tiên.
- [ ] Đã thống nhất cách phát hành, backup database, log và xử lý sự cố.

## 16. Việc đề xuất sau bàn giao

1. Đưa snapshot mã nguồn đầy đủ vào repo chính và tạo commit/tag chính thức.
2. Chốt các quyết định nghiệp vụ còn mở bằng decision log.
3. Hoàn thiện auth, session và branch-scoped authorization.
4. Triển khai API catalog, availability và rental trước; giữ UI contract ổn định.
5. Apply/test Prisma migration trên PostgreSQL development.
6. Nối frontend với API theo từng luồng, thay fixture adapter có kiểm soát.
7. Hoàn thiện payment/refund với idempotency và audit.
8. Chạy kiểm thử tích hợp, E2E, accessibility và UAT với nhân viên studio.
9. Chuẩn bị môi trường staging, dữ liệu seed riêng và quy trình rollback.

## 17. Xác nhận bàn giao

| Bên bàn giao | Bên tiếp nhận | Ngày | Chữ ký/xác nhận |
|---|---|---|---|
| __________________ | __________________ | ____/____/2026 | __________________ |

