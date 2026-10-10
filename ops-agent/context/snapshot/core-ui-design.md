# Quy chuẩn thiết kế giao diện và năm màn hình lõi

**Ngày lập:** 03/10/2026

**Áp dụng cho:** giao diện web Customer, Staff và Admin của Costume Rental Studio.

**Trạng thái:** đặc tả thiết kế để dựng wireframe/prototype. Hướng thẩm mỹ và cách tick quyền đã được chủ dự án xác nhận; mã màu accent cụ thể và ảnh thật còn có thể tinh chỉnh. Tài liệu này cụ thể hóa [kế hoạch UI](Kế%20hoạch%20thiết%20kế%20và%20triển%20khai%20giao%20diện.md), không thay đổi [quy tắc nghiệp vụ hiện hành](business-rules.md) hoặc schema/API.

## 1. Nguyên tắc áp dụng

1. Thiết kế năm màn hình lõi trước: **catalog**, **đặt thuê**, **bảng việc nhân viên**, **không gian xử lý đơn**, **giao/trả trang phục**. Các màn còn lại lắp từ cùng token và component.
2. Tách bạch điều đã có trong schema, dữ liệu tính từ nghiệp vụ và đề xuất UI. Hiện frontend chỉ là khung React/Vite; các mockup chưa phải chức năng thật.
3. Một đơn có nhiều trạng thái đồng thời. UI không ép trạng thái đơn, bộ vật lý và tiền vào một badge duy nhất.
4. Hành động quan trọng phải cho biết **đang xử lý, thành công, thất bại, cách sửa**, và giữ dữ liệu đã nhập khi có lỗi.
5. Mọi ví dụ tên khách, số điện thoại, mã đơn trong wireframe là dữ liệu giả; prototype không dùng dữ liệu cá nhân thật.

## 2. Design tokens phiên bản đề xuất

### 2.1. Chữ và nhịp dọc

Font đề xuất: **Be Vietnam Pro** cho tiêu đề và giao diện, **Noto Sans** làm fallback; sau đó là `system-ui, sans-serif`. Dùng một họ sans xuyên suốt để các bảng số liệu, form và catalog đọc đồng nhất. Font trang trí chỉ cân nhắc cho tiêu đề marketing sau khi có nhận diện thương hiệu và kiểm tra dấu tiếng Việt.

| Vai trò | Cỡ / dòng | Độ đậm | Cách dùng |
|---|---:|---:|---|
| Display | 40 / 48 px | 600 | Hero công khai, tối đa một lần/trang |
| H1 | 32 / 40 px | 600 | Tên trang |
| H2 | 24 / 32 px | 600 | Khu vực lớn |
| H3 | 20 / 28 px | 600 | Card lớn, panel chi tiết |
| Body | 16 / 24 px | 400 | Nội dung chính, form |
| Body nhỏ | 14 / 20 px | 400 | Bảng, bộ lọc, thông tin phụ |
| Label/nút | 14 / 20 px | 600 | Nhãn trường, nút, đầu cột |
| Caption | 13 / 18 px | 500 | Ghi chú ngắn, thời gian; vẫn phải đủ tương phản |

Không dùng chữ hoa toàn bộ cho đoạn dài. Mã đơn/barcode có thể dùng chữ số tabular để thẳng cột. Số tiền có dấu phân cách `vi-VN` và đơn vị `đ`; thời gian hiển thị theo timezone chi nhánh.

### 2.2. Khoảng cách, kích thước, bo góc và bóng

| Token | Giá trị | Quy tắc |
|---|---:|---|
| `space-1/2/3/4/6/8/12` | 4 / 8 / 12 / 16 / 24 / 32 / 48 px | Chỉ dùng các bước này cho gap/padding chuẩn |
| `control-sm/default/lg` | 36 / 44 / 48 px | Nút chính và mục chạm trên mobile tối thiểu 44 px |
| `radius-sm/md/lg` | 6 / 10 / 14 px | Input/nút, card, panel lớn |
| `radius-pill` | 9999 px | Chip ngắn, không dùng cho bảng/panel |
| `border` | 1 px | Phân nhóm nhẹ; không chồng nhiều đường kẻ |
| `shadow-card` | không có | Card thông thường phân cấp bằng nền/viền |
| `shadow-overlay` | `0 8px 24px rgb(23 23 23 / 12%)` | Dropdown, dialog, popover |

Khung desktop tối đa 1440 px; nội dung nội bộ có sidebar khoảng 240 px và khoảng cách 24 px. Ở 375–767 px dùng lề 16 px, card một cột; 768–1023 px ưu tiên layout hai cột; từ 1024 px cho phép sidebar và bảng rộng. Đây là breakpoint kiểm tra thiết kế, không ràng buộc cứng vào một thư viện CSS.

### 2.3. Bề mặt và nhận diện đã chọn

Hướng thẩm mỹ đã chốt: **trẻ trung, hiện đại, tối giản có điểm nhấn**, nền sáng nhiều khoảng trắng, ảnh trang phục lớn, bo góc vừa phải. Khu khách hàng tạo cảm giác fashion/lifestyle và trải nghiệm chọn đồ; khu nội bộ vẫn sáng, gọn, dễ xử lý việc. Tránh serif cổ điển/luxury nặng, kính mờ và bảng điều khiển khô cứng. Accent **hồng berry** dưới đây là mã màu đề xuất để bắt đầu prototype, có thể điều chỉnh khi có logo/ảnh thật.

| Token | Mã màu | Cách dùng |
|---|---|---|
| `canvas` | `#FAFAFA` | Nền ứng dụng sáng |
| `surface` | `#FFFFFF` | Card, panel, form |
| `surface-muted` | `#F7F7F8` | Bộ lọc, hàng xen kẽ nhẹ, skeleton |
| `surface-hover` | `#F4F4F5` | Hover ở dòng/card có thể bấm |
| `surface-selected` | `#FDF2F8` | Dòng đang chọn, luôn có viền/đánh dấu phụ |
| `input-bg` | `#FFFFFF` | Nền trường nhập |
| `input-border` | `#71717A` | Viền input thường đủ nhận biết trên nền trắng; lỗi dùng tone danger |
| `text-primary` | `#171717` | Nội dung chính |
| `text-secondary` | `#52525B` | Nội dung phụ trên nền sáng |
| `border` | `#E4E4E7` | Viền input/card |
| `brand-primary` | `#C0265B` | CTA chính, đường dẫn nổi bật, trạng thái được chọn |
| `brand-primary-hover` | `#9D174D` | Hover/pressed của CTA chính |
| `brand-tint` | `#FDF2F8` | Nền điểm nhấn rất nhẹ |
| `focus-ring` | `#1D4ED8` | Vòng focus tách khỏi màu thương hiệu |

Chữ trắng trên `brand-primary` đạt khoảng **5,72:1**. Giữ tỷ lệ ảnh trang phục lớn và khoảng trắng thoáng ở catalog; ở khu nội bộ dùng cùng chữ, màu và component nhưng giảm diện tích ảnh để ưu tiên hàng đợi và form. Không dùng ảnh giả lập như ảnh sản phẩm thật trong bản phát hành.

### 2.4. Màu ngữ nghĩa và trạng thái

| Tone | Nền | Chữ/viền đậm | Dùng cho |
|---|---|---|---|
| `success` | `#F0FDF4` | `#166534` | Đã xác nhận, đã thu, đã hoàn, sẵn sàng |
| `warning` | `#FFFBEB` | `#92400E` | Chờ duyệt, sắp đến hạn, chờ đối soát |
| `danger` | `#FEF2F2` | `#B91C1C` | Quá hạn, thất bại, hư hỏng cần xử lý |
| `info` | `#EFF6FF` | `#1D4ED8` | Đang xử lý, đang giao, đang kiểm tra |
| `neutral` | `#F1F5F9` | `#475569` | Bản nháp, đã hủy, ngừng hoạt động |

Đã tính tỷ lệ tương phản cho chữ trên nền tương ứng: success 6,81:1; warning 6,84:1; danger 5,91:1; info 6,16:1; neutral 6,92:1. Badge luôn có **tên trạng thái bằng chữ**; màu chỉ hỗ trợ nhận biết. Màu biểu thị mức khẩn cấp, không biểu thị role hay chi nhánh.

### 2.5. Component contract

| Component | Biến thể bắt buộc | Hành vi bắt buộc |
|---|---|---|
| Button | primary accent, secondary viền, quiet, destructive; default 44 px | Có focus, disabled, loading; không gửi lặp khi đang xử lý |
| Input/select/date | default, focused, error, readonly | Label hiển thị; lỗi gắn với trường; giữ giá trị sau lỗi server |
| StatusLabel | tone + text + optional icon | Dùng đúng chiều trạng thái (đơn/bộ/tiền); không chỉ một chấm màu |
| MoneyBreakdown | thuê, cọc, phụ phí, đã thu, còn thu/hoàn | Tổng và phép tính do backend trả; tránh số tiền “ước tính” trông như đã thu |
| DataTable | tìm, lọc, sắp xếp, phân trang, chọn dòng | Header rõ; trên mobile chuyển card hoặc cuộn có kiểm soát; giữ bộ lọc trong URL khi phù hợp |
| WorkQueueItem | hạn xử lý, mã đơn, khách, việc, mức ưu tiên | Bấm mở đúng panel; có trạng thái đã xử lý/mất quyền/xung đột |
| Modal xác nhận | lý do, tác động, hành động tiếp | Chỉ dùng cho thao tác ảnh hưởng trạng thái/tiền; không biến luồng xử lý đơn thành chuỗi modal |
| Feedback | inline error, summary, toast/status, empty state | Nêu việc vừa xảy ra và cách tiếp tục; screen reader nhận được status không cần chuyển focus vô cớ |

## 3. Hệ thống trạng thái nhiều chiều

### 3.1. Trạng thái đơn có trong schema

Không tạo enum `RETURNED`: schema dùng `RETURN_INSPECTION` rồi `COMPLETED`. Tên hiển thị và hành động chính:

| Enum | Nhãn UI | Tone | Hành động tiếp theo thường gặp |
|---|---|---|---|
| `DRAFT` | Bản nháp | neutral | Tiếp tục/chỉnh yêu cầu |
| `PENDING_CONFIRMATION` | Chờ studio xác nhận | warning | Nhân viên kiểm tra lịch và gán bộ |
| `CONFIRMED` | Đã xác nhận | success | Chuẩn bị trang phục |
| `PREPARING` | Đang chuẩn bị | info | Kiểm tra bộ/phụ kiện |
| `READY_FOR_PICKUP` | Sẵn sàng nhận | info | Giao và thu tiền |
| `ACTIVE` | Đang thuê | info | Theo dõi hạn trả / bắt đầu nhận trả |
| `RETURN_INSPECTION` | Đang kiểm tra đồ trả | warning | Ghi phí/cấn cọc/hoàn |
| `COMPLETED` | Hoàn tất | success | Xem biên nhận/lịch sử |
| `REJECTED` | Studio từ chối | danger | Xem lý do/chọn kỳ khác |
| `CANCELLED` | Đã hủy | neutral | Xem xử lý tiền nếu có |
| `NO_SHOW` | Không đến nhận | warning | Xem phí/chính sách và giải phóng bộ |

`COMPLETED` chỉ được hiển thị khi nghiệp vụ và tài chính đã chốt theo backend. UI không tự đổi trạng thái dựa vào việc khách đã trả đồ.

### 3.2. Trạng thái bộ và khả dụng

`costume_units.operational_status` có `INBOUND`, `READY`, `CLEANING`, `REPAIR`, `IN_TRANSFER`, `RETIRED`. Giao diện còn cần **nhãn tổng hợp** suy từ đơn đang thuê và `unit_blocks`:

| Tình huống | Nhãn hiển thị | Nguồn |
|---|---|---|
| Có order item đang phân bổ `ACTIVE` | Đang ở khách | Dòng đơn + mã khách/đơn |
| Có block hiệu lực | Tạm không khả dụng: vệ sinh/sửa/kiểm tra… | `unit_blocks` |
| Đang điều chuyển | Đang điều chuyển | `operational_status` và phiếu chuyển |
| `INBOUND` | Chờ kiểm tra nhập | `operational_status` |
| `CLEANING` | Đang vệ sinh | `operational_status` |
| `REPAIR` | Đang sửa chữa | `operational_status` |
| `READY` và không vướng lịch/block | Sẵn sàng | Trạng thái + truy vấn khả dụng theo kỳ |
| `RETIRED` | Ngừng khai thác | `operational_status` |

Khi tra theo một khoảng thuê, “sẵn sàng” phải xét **chi nhánh + kỳ thuê + block + lịch gán**, không suy chỉ từ enum `READY`. API trả một kết quả khả dụng chuẩn; UI không tự giải quyết xung đột lịch. Nếu cùng một bộ xuất hiện “đang ở khách” và “đang sửa/điều chuyển” cùng lúc, hiển thị cảnh báo dữ liệu bất nhất cho nhân viên thay vì âm thầm chọn một nhãn.

### 3.3. Trạng thái tiền theo từng khoản

Mỗi đơn hiển thị ba hàng riêng: **tiền thuê**, **tiền cọc**, **phụ phí/hoàn**. Các nhãn dưới đây là **trạng thái tổng hợp cho UI**, không phải enum mới trong DB:

| Khoản | Nhãn có thể hiển thị | Dữ liệu gốc |
|---|---|---|
| Tiền thuê | Chưa thu / Chờ đối soát / Thu thiếu / Đã thu | Tổng tiền thuê snapshot và `payments` mục đích `RENTAL` |
| Cọc | Chưa thu / Chờ đối soát / Đang giữ / Đang hoàn / Đã hoàn một phần / Đã hoàn | `payments` mục đích `DEPOSIT`, cấn trừ và `refunds` |
| Phụ phí | Chưa phát sinh / Cần thu / Đã thu / Chờ xử lý | Phí trên order/item và `payments` mục đích `EXTRA` |
| Hoàn tiền | Chưa yêu cầu / Đang xử lý / Hoàn thất bại / Đã hoàn | `refunds.status`; chỉ tính tiền thực hoàn khi `COMPLETED` |

Ví dụ chi tiết đơn: **Đơn: Đang thuê** · **Tiền thuê: Đã thu** · **Cọc: Đang giữ** · **Đồ trả: Chưa trả**. Không gộp bốn dữ kiện thành “Đang thuê (màu xanh)”. Số còn phải thu/hoàn do backend tính; UI cho xem phép tính và payment/refund liên quan.

## 4. Đặc tả năm màn hình lõi

### 4.1. Catalog khách hàng — UI-01

**Mục tiêu:** chọn được mẫu và biến thể phù hợp với chi nhánh/kỳ thuê mà không nhầm giá tham khảo với bộ đã giữ.

- **Đầu vào:** chi nhánh, thời điểm nhận/trả, loại trang phục, size/màu, từ khóa. Có thể xem mẫu trước khi chọn ngày; khi có kỳ thuê thì kết quả khả dụng được cập nhật từ API.
- **Desktop:** vùng lọc trái gọn; thanh chọn chi nhánh/kỳ thuê ở trên; lưới card ảnh 4:5. **Mobile:** bộ lọc mở thành panel, chip đang áp dụng luôn nhìn thấy, một hoặc hai card mỗi hàng tùy rộng.
- **Card:** ảnh có alt, tên mẫu, size/màu khả dụng, giá **từ …đ/ngày**, cọc **từ …đ**, nhãn còn/không còn **theo kỳ đã chọn**; CTA “Xem chi tiết”. Giá “từ” là giá biến thể thấp nhất khả dụng, không phải báo giá cuối.
- **Empty:** “Không có trang phục phù hợp tại chi nhánh và thời gian này” với nút đổi ngày/xóa lọc/chọn chi nhánh khác. Nếu chưa chọn kỳ, không nói “hết đồ”.
- **Chờ/lỗi:** skeleton giữ tỷ lệ ảnh và số card; lỗi tải dữ liệu có nút thử lại, giữ bộ lọc.
- **Nghiệm thu:** bộ đang vệ sinh/sửa hoặc vướng lịch không xuất hiện là khả dụng cho kỳ trùng; ảnh thiếu có placeholder đúng kích thước.

### 4.2. Đặt thuê — UI-03

**Mục tiêu:** khách gửi yêu cầu ít ma sát trên điện thoại, biết rõ đơn còn chờ nhân viên.

| Bước mobile | Nội dung | Điều kiện chuyển bước |
|---|---|---|
| 1. Trang phục | Mẫu đã chọn hoặc quay về catalog | Có ít nhất một mẫu/biến thể |
| 2. Lựa chọn | Size, màu, edition, số bộ | Số bộ hợp lệ; nếu >1, backend sẽ tạo một dòng cho mỗi bộ |
| 3. Nhận và trả | Chi nhánh, ngày/giờ nhận, ngày/giờ trả cùng chi nhánh | Khoảng hợp lệ theo policy; tra lại khả dụng |
| 4. Báo giá | Số ngày tính tiền, giá/ngày từng biến thể, tiền thuê, cọc, giảm giá nếu có, hạn báo giá | Dữ liệu báo giá từ backend còn hiệu lực |
| 5. Người thuê | Đăng nhập Google nếu cần, tên/điện thoại, ghi chú | Liên hệ đầy đủ; không mất các bước trước khi đăng nhập |
| 6. Xác nhận | Tóm tắt toàn bộ, điều kiện hủy, CTA “Gửi yêu cầu thuê” | Hiển thị ngay cạnh CTA: “Yêu cầu chưa giữ trang phục cho đến khi studio xác nhận.” |

Desktop có thể gom thành 3 nhóm nhìn thấy cùng lúc; vẫn giữ thứ tự và tóm tắt giá cố định ở cạnh. Mobile có thanh tiến độ, nút Quay lại/Đi tiếp và tóm tắt thu gọn; không xóa lựa chọn khi quay lại. Màn thành công lặp lại câu “chưa giữ trang phục”, mã đơn và nơi theo dõi; không ghi “Đặt thành công/đã giữ đồ”. Nếu báo giá hết hạn hoặc bộ vừa hết, giữ form và yêu cầu cập nhật giá/lịch trước khi gửi lại.

### 4.3. Bảng việc nhân viên — UI-06

**Mục tiêu:** cho nhân viên biết việc nào phải làm tiếp, không biến trang đầu thành năm KPI card lớn.

- **Header:** chi nhánh đang làm việc, ngày/giờ hiện tại theo timezone chi nhánh, tìm nhanh mã đơn/barcode/số điện thoại.
- **Dải tóm tắt gọn:** đơn chờ xác nhận, giao trong ngày, trả trong ngày, quá hạn, giao dịch cần xử lý. Mỗi số mở danh sách đã lọc; không coi số đếm là báo cáo tài chính.
- **Danh sách “Ưu tiên xử lý”:** giờ hạn, mã đơn hoặc barcode, khách, việc cần làm, thời gian còn/quá, người phụ trách (nếu có), CTA. Chia nhóm Quá hạn → Trong 2 giờ tới → Hôm nay → Chờ xác nhận lâu; ngưỡng 2 giờ là quy tắc UI đề xuất, cần cấu hình nếu studio muốn dùng làm SLA.
- **Bộ lọc:** chi nhánh (nếu có quyền nhiều chi nhánh), loại việc, trạng thái, khoảng ngày. Dữ liệu mặc định là chi nhánh đang chọn, không gộp toàn chuỗi cho nhân viên.
- **Empty:** “Chưa có việc cần xử lý ở chi nhánh này”; vẫn có đường tới danh sách đơn/kho.
- **Nghiệm thu:** một dòng mở đúng đơn/panel và thao tác; mục vừa được người khác xử lý biến khỏi hàng đợi sau làm mới mà không làm mất ngữ cảnh lọc.

### 4.4. Không gian xử lý đơn — UI-07

**Mục tiêu:** xem hàng đợi, đọc chi tiết và xử lý xác nhận/gán bộ nhanh trong một workspace.

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Chi nhánh Q1  ·  Tìm mã đơn/khách/barcode  ·  Bộ lọc trạng thái/ngày       │
├──────────────────┬──────────────────────┬──────────────────────────────────┤
│ Nhóm trạng thái  │ Danh sách đơn         │ Chi tiết đơn đang chọn            │
│ Chờ xác nhận 12  │ RT-1024 · 09:30       │ Khách · kỳ thuê · chính sách       │
│ Sắp giao 8       │ RT-1028 · 10:00       │ Trang phục A · size M · 2 bộ       │
│ Đang thuê 14     │ ...                  │ Bộ phù hợp: BC-001, BC-012       │
│ Cần kiểm tra 5   │                      │ Giá thuê | Cọc | Ghi chú           │
│                 │                      │ [Xác nhận và gán bộ]              │
└──────────────────┴──────────────────────┴──────────────────────────────────┘
```

- **Từ 1280 px:** ba vùng như sơ đồ; dưới 1280 px gộp nhóm trạng thái vào tab/filter và giữ danh sách + chi tiết; mobile đi từ danh sách sang trang chi tiết, có nút Quay lại rõ.
- **Panel chi tiết:** mã/trạng thái đơn, khách và liên hệ, kỳ thuê, chi nhánh, chính sách ngày, từng dòng biến thể, barcode được gán, lịch sử, tiền thuê/cọc riêng, việc có thể làm theo quyền.
- **Xác nhận:** chọn **đủ số bộ vật lý khác nhau**, thấy trạng thái `READY` và lịch khả dụng của từng bộ; nút ghi “Xác nhận và gán X bộ”. Trước khi lưu, hiển thị số bộ/giá/hạn; khi lưu, khóa nút và dùng version để phát hiện đơn bị sửa đồng thời.
- **Xung đột:** nếu bộ vừa được gán bởi nhân viên khác, không tự gán thay; hiển thị “BC-001 không còn khả dụng”, giữ lựa chọn khác và tải lại danh sách bộ. Nếu đơn đã đổi trạng thái/hủy, panel làm mới và chỉ ra thay đổi.
- **Từ chối/hủy:** yêu cầu lý do, hiển thị tác động đến bộ và tiền; không dùng modal cho các bước đọc/xem thông thường.
- **Nghiệm thu:** xử lý hết hàng đợi chờ mà không phải rời trang nhiều lần; keyboard có thể chuyển danh sách/chi tiết và dùng action chính.

### 4.5. Giao và trả trang phục — UI-09/UI-11

Hai tác vụ dùng cùng **OrderDetailShell** nhưng có biểu mẫu và điều kiện khác nhau. Không tạo nút “Hoàn tất” chung.

| Giao đồ | Nhận trả |
|---|---|
| Quét/nhập barcode từng bộ đã gán; đối chiếu khách/đơn/chi nhánh | Quét/nhập barcode đang ở khách; mở đúng đơn và bộ |
| Ghi tình trạng xuất, phụ kiện thực giao, ảnh bằng chứng nếu lưu ảnh đã có | Ghi tình trạng trả, phụ kiện thiếu/hỏng, ảnh và lý do phí |
| Hiển thị tiền thuê và cọc riêng; xác nhận tiền mặt/chuyển khoản theo hai khoản | Hiển thị phí trễ/hỏng/thiếu, cọc có thể cấn trừ, phần còn hoàn |
| Chỉ chuyển `ACTIVE` khi backend xác nhận điều kiện giao/thu | Chuyển `RETURN_INSPECTION` trước; `COMPLETED` sau quyết toán theo backend |

**Giao diện tiền:** bảng `Cần thu / Đã thu / Còn thiếu` cho tiền thuê và cọc; lúc trả là `Cọc đã giữ / Cấn trừ / Đã hoàn / Còn hoàn`. Chuyển khoản chưa đối soát vẫn là chờ xử lý, không hiển thị “Đã thu”. Refund thất bại giữ nguyên chứng từ và cho phép thử lại qua quy trình có quyền, tránh hoàn hai lần.

**Barcode:** khi nhập/quét, mở panel bộ với tên, size/màu, đơn, khách, hạn trả. Barcode không tồn tại hoặc thuộc chi nhánh khác phải có thông báo khác nhau. Fallback nhập tay luôn có sẵn; quét chỉ tra cứu, không tự xác nhận giao/trả.

**Nghiệm thu:** một đơn nhiều bộ có thể kiểm từng bộ; khách trả thiếu một bộ thì phần còn lại vẫn hiện trong “Đang thuê”; cọc không hoàn trước khi kiểm tra/đối soát; giao/trả không vượt phạm vi chi nhánh và quyền.

## 5. Màn “Đang thuê” và bộ quyền dùng lại

### 5.1. Tra cứu tài sản đang ở khách — UI-10

Đây là màn **truy vết bộ**, không phải bản sao danh sách đơn. Bảng: `Barcode | Trang phục/size | Khách | Đơn | Nhận lúc | Hạn trả | Quá hạn | Chi nhánh`. Tìm barcode được ưu tiên và focus sẵn tại quầy; gõ/scan mã khớp duy nhất mở panel ngay. Panel cho biết khách nào đang giữ, đơn nào, giờ phải trả, phụ kiện và CTA nhận trả. Dữ liệu “đang thuê” lấy từ order item `ACTIVE` và đơn liên quan, không thêm trạng thái `RENTED` vào `costume_units`.

### 5.2. Ma trận quyền theo vai trò — UI-15

Thay bảng 30–50 hàng × nhiều cột bằng **một vai trò tại một thời điểm**. Cột trái liệt kê role, phần phải nhóm quyền theo Đơn thuê, Giao nhận, Thanh toán, Kho, CRM, Quản trị. Mỗi dòng có tên dễ hiểu, mô tả thao tác và checkbox; header cho biết phạm vi chi nhánh/toàn chuỗi của role được gán. Có tìm kiếm quyền, chọn/bỏ theo nhóm với xem trước thay đổi, và cảnh báo mất quyền quản trị cuối cùng.

`Permission.scope` hiện là thuộc tính cố định của **mã quyền**. UI không cho chọn radio `OWN/BRANCH/ALL` tùy ý nếu backend không có các mã quyền tương ứng. Khi một hành động có nhiều scope thật, UI có thể trình bày chúng như các lựa chọn loại trừ nhau và ánh xạ đến mã quyền. **Đã chốt:** checkbox sửa quyền của role; màn nhân viên riêng gán role theo chi nhánh. Không có checkbox ngoại lệ riêng trên hồ sơ từng nhân viên trong MVP.

## 6. Empty, error và conflict state phải thiết kế trước

| Tình huống | Nội dung chính cần nói | Hành động khôi phục | Giữ dữ liệu |
|---|---|---|---|
| Không còn biến thể phù hợp kỳ thuê | “Không còn bộ phù hợp ở chi nhánh này trong thời gian đã chọn” | Đổi ngày, chi nhánh, size hoặc xóa lọc | Bộ lọc khác |
| Bộ vừa được người khác gán | “Mã BC-… vừa hết khả dụng” | Tải lại bộ còn trống và chọn mã khác | Đơn, các bộ khác |
| Đơn bị người khác sửa | “Đơn đã thay đổi từ lúc bạn mở” và nêu trường/trạng thái mới | Làm mới, kiểm tra rồi thao tác lại | Ghi chú chưa gửi nếu còn hợp lệ |
| Khách hủy khi staff đang duyệt | “Đơn đã hủy, không thể xác nhận” | Mở lịch sử, về hàng đợi | Bộ lọc hàng đợi |
| Mất quyền giữa phiên | “Bạn không còn quyền xử lý đơn tại chi nhánh này” | Chuyển chi nhánh nếu có quyền hoặc về tổng quan | Không gửi thao tác cũ |
| Chuyển khoản chưa đối soát | “Chưa xác nhận tiền đã nhận” | Kiểm tra giao dịch, ghi nhận sau đối soát | Đơn và số tiền dự kiến |
| Hoàn cọc thất bại | “Hoàn cọc chưa thành công” kèm mã giao dịch/đường hỗ trợ | Xem lý do, thử lại theo quyền | Lịch sử refund, không tạo hoàn trùng |
| Barcode không tồn tại | “Không tìm thấy mã bộ này” | Kiểm tra/nhập lại; tìm theo tên | Đơn đang mở |
| Barcode thuộc chi nhánh khác | Nêu chi nhánh sở hữu hiện tại | Mở bộ nếu có quyền hoặc báo quản lý | Đơn đang mở |
| Bộ đang vệ sinh/sửa | Nêu loại block và thời điểm dự kiến sẵn sàng | Chọn bộ khác hoặc kỳ khác | Các lựa chọn khác |
| Lỗi mạng/server | “Chưa lưu được thay đổi” và trạng thái dữ liệu đã/sẽ gửi | Thử lại an toàn, mã yêu cầu hỗ trợ | Toàn bộ form |

Thông báo lỗi không chỉ là toast biến mất. Lỗi form có tóm tắt focus được và mô tả cạnh trường; xung đột nghiệp vụ giữ panel mở để người dùng giải quyết. Với thao tác ghi tiền, không cho “thử lại” mù khi chưa xác minh yêu cầu trước đã được xử lý hay chưa.

## 7. Accessibility và tiêu chí kiểm tra thiết kế

- Chữ thường đạt tương phản tối thiểu **4,5:1**; chữ lớn tối thiểu **3:1**, theo [WCAG 2.2 về tương phản](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html). Các cặp màu trạng thái ở mục 2.4 đã được tính, nhưng vẫn kiểm tra lại trong UI thật và trên ảnh nền.
- Mục chạm chính của sản phẩm đặt mục tiêu **44×44 px**; đây là chuẩn thiết kế nội bộ cao hơn mức tối thiểu 24×24 px hoặc ngoại lệ khoảng cách của [WCAG 2.2 Target Size Minimum](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum).
- Form phải có label, thông báo lỗi cạnh trường và tóm tắt sau submit; các cập nhật thành công/chờ/lỗi không đổi focus cần được công bố cho công nghệ hỗ trợ theo [W3C WAI về status messages](https://www.w3.org/WAI/WCAG21/Understanding/status-messages) và [form notifications](https://www.w3.org/WAI/tutorials/forms/notifications/).
- Kiểm tra keyboard từ catalog đến gửi yêu cầu, từ hàng đợi đến gán bộ, từ quét tay đến hoàn tất giao/trả; focus luôn nhìn thấy, không bị header cố định che.
- Kiểm tra 375, 768, 1024 và 1440 px; zoom 200%; nội dung lỗi dài và tên trang phục dài; không có cuộn ngang toàn trang.
- Trạng thái phải đọc được khi bỏ màu: badge có chữ, bảng có tiêu đề, icon quan trọng có tên truy cập được. Chuyển động tôn trọng `prefers-reduced-motion`.

## 8. Bàn giao trước khi code 18 màn hình

1. Dùng hướng fashion/lifestyle hiện đại đã chốt; kiểm tra accent đề xuất với logo và ảnh trang phục thật khi có.
2. Tạo wireframe ở 375 và 1440 px cho năm màn mục 4, gồm trạng thái bình thường, loading, empty và ít nhất một xung đột cho mỗi luồng.
3. Dựng thư viện component nền: button, form field, card trang phục, status label nhiều chiều, work queue, table/card list, money breakdown, checklist.
4. Chạy review nghiệp vụ với staff/admin: cùng một đơn từ yêu cầu đến hoàn cọc; review đồng thời hai nhân viên xác nhận cùng bộ.
5. Chỉ sau khi năm màn và component được thống nhất mới nhân rộng sang 13 màn còn lại. API nghiệp vụ vẫn là điều kiện để prototype thành chức năng thật.

**Câu hỏi còn mở:** giá có theo chi nhánh/ngày hiệu lực không; mã màu accent cuối cùng và ảnh thật sẽ là gì. Phân quyền theo role + chi nhánh đã được xác nhận; giá theo biến thể toàn chuỗi vẫn là phương án theo schema hiện tại cho đến khi có yêu cầu khác.
