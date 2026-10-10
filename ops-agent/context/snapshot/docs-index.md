# Tài liệu hệ thống Costume Rental Studio

## Nguồn chuẩn

Khi có khác biệt giữa các tài liệu, dùng thứ tự ưu tiên sau:

1. `apps/api/prisma/migrations/*/migration.sql`: cấu trúc PostgreSQL thực thi.
2. `apps/api/prisma/schema.prisma`: mô hình Prisma và quan hệ ứng dụng.
3. `docs/database-schema.dbml`: ERD dùng để trao đổi và hiển thị.
4. `docs/database-constraints.md`: constraint PostgreSQL và rule liên bảng.
5. `docs/business-rules.md`: nghiệp vụ đã chốt.

## Danh sách tài liệu hiện hành

| Tài liệu | Mục đích |
|---|---|
| `database-schema.dbml` | ERD đầy đủ gồm 32 bảng |
| `database-schema-summary.md` | Tóm tắt các nhóm bảng và trách nhiệm |
| `database-constraints.md` | `CHECK`, FK, `ON DELETE`, unique và exclusion constraint |
| `database-review-guide.md` | Checklist review schema, migration và dữ liệu |
| `business-rules.md` | Actor, flow thuê, kho, thanh toán và CRM đã chốt |
| `Kế hoạch thiết kế và triển khai giao diện.md` | Hiện trạng code, các điểm cần chốt, sơ đồ màn hình, luồng UX và thứ tự làm UI |
| `Quy chuẩn thiết kế giao diện và năm màn hình lõi.md` | Token hình ảnh, trạng thái nhiều chiều, đặc tả 5 màn hình đầu, trạng thái lỗi/xung đột và tiêu chí nghiệm thu |
| `Hướng dẫn trình diễn giao diện toàn hệ thống.md` | Các route, cách chạy, kịch bản fixture và phụ thuộc API của 18 màn hình |
| `Đánh giá và tối ưu trải nghiệm mười luồng chính.md` | Ma sát, thay đổi trước/sau, kiểm tra UX và phụ thuộc API của 10 hành trình |
| `Báo cáo kiểm toán hoàn chỉnh giai đoạn UI UX.md` | Kết quả nghiệm thu UI/UX cuối giai đoạn fixture: 10 hành trình, trạng thái phục hồi, responsive, accessibility và việc còn chờ API |
| `Đối chiếu luồng UI UX theo báo cáo rà soát nghiệp vụ.md` | Mức bao phủ UI/fixture của 40 tình huống, các hành trình mới và phần chờ API/quyết định |
| `Báo cáo rà soát nghiệp vụ toàn diện studio cho thuê trang phục.docx` | Đánh giá nghiệp vụ đa chi nhánh, ngoại lệ vận hành và 40 kịch bản nghiệm thu; các thay đổi trong báo cáo là đề xuất cần chốt trước khi triển khai |
| `ci-cd.md` | CI, publish Docker image, deploy Coolify và migration production |

File `Phân tích nghiệp vụ và thiết kế hệ thống studio cho thuê trang phục.md` là tài liệu phân tích lịch sử. Một số phương án trong đó đã được rút gọn và không còn phản ánh schema cuối cùng; không dùng file đó làm nguồn để viết migration hoặc API.

Báo cáo rà soát nghiệp vụ là tài liệu đối chiếu, không tự thay thế nguồn chuẩn ở trên. Với SePay và hoàn cọc, giao diện hiện chỉ hiển thị trạng thái và điểm cần chốt theo lựa chọn của nhóm ngày 03/10/2026; phương thức hoàn, đối soát và phạm vi MVP vẫn cần quyết định trước khi sửa quy tắc thanh toán.
