---
id: kb-index
title: Chỉ mục kho tri thức vận hành
document_type: index
domain: operations
status: draft_from_code
version: 0.1
source_type: technical_implementation
business_authority: false
retrieval_enabled: false
audience: internal
chunk_title_prefix: true
usage_limit: "Chỉ dùng để mô tả khả năng của hệ thống; không dùng để kết luận quy định kinh doanh."
source:
  - workspace://apps/api/prisma/schema.prisma
  - workspace://apps/api/src/modules
---

# Chỉ mục kho tri thức vận hành

## Mục đích

Đây là kho kiến thức để trợ lý trả lời khách hàng và hỗ trợ nhân viên vận hành. Nội dung phải ưu tiên tiếng Việt tự nhiên, dễ hiểu và đúng với cách cửa hàng làm việc. Tên kỹ thuật chỉ dùng để đối chiếu với hệ thống, không dùng nguyên văn khi trả lời khách hàng.

Nội dung ban đầu được tổng hợp từ mã nguồn nên chỉ mô tả những gì hệ thống đang lưu hoặc hỗ trợ. Nội dung này không tự đặt ra phí, thời hạn hay quy định kinh doanh chưa được người phụ trách xác nhận.

## Cách dùng ngôn ngữ

- Khi trả lời khách hàng, dùng các từ như “đơn thuê”, “bộ trang phục”, “đang vận chuyển”, “đã nhận hàng”, “thanh toán” và “hoàn tiền”.
- Không dùng tên bảng dữ liệu, tên API, mã trường hoặc từ chuyên môn phát triển phần mềm nếu khách không hỏi.
- Nếu cần nhắc trạng thái hệ thống, giải thích bằng tiếng Việt trước; mã trạng thái chỉ đặt trong ngoặc để nhân viên đối chiếu.
- Hướng dẫn kỹ thuật dành cho đội phát triển phải đặt trong `docs/`, không đưa vào tập tài liệu RAG dùng để trả lời khách hàng.

## Quy tắc sử dụng cho RAG

| Trạng thái tài liệu | Cách dùng |
|---|---|
| `approved` | Có thể dùng làm hướng dẫn nghiệp vụ chính thức. |
| `verified_from_system` | Đã đối chiếu với hành vi hiện có của hệ thống; dùng để giải thích quy trình và trạng thái, không dùng để công bố chính sách kinh doanh. |
| `draft_from_code` | Có thể giải thích thông tin hệ thống bằng ngôn ngữ dễ hiểu, nhưng không dùng để xác nhận quy định. |
| `needs_business_confirmation` | Không dùng để kết luận quy định, phí, thời hạn xử lý hoặc quyền hạn; chỉ nêu phần cần người phụ trách xác nhận. |
| `deprecated` | Không dùng để trả lời mặc định. |

Khi câu hỏi liên quan đến một trường hợp cụ thể, trợ lý phải đọc dữ liệu mới nhất từ hệ thống. Không dùng tài liệu chung để khẳng định trạng thái hiện tại của một đơn thuê, khoản thanh toán hoặc bộ trang phục cụ thể.

## Phân loại nguồn

| `source_type` | Ý nghĩa | Có thể dùng để xác nhận quy định không? |
|---|---|---|
| `business_approved` | Quy định hoặc quy trình đã được người có thẩm quyền phê duyệt. | Có. |
| `technical_implementation` | Mã nguồn, cấu trúc dữ liệu hoặc API hiện có. | Không. Chỉ dùng để mô tả khả năng và trạng thái hệ thống. |
| `internal_draft` | Tài liệu nội bộ đang soạn hoặc chưa được phê duyệt. | Không. Phải nói rõ nội dung đang chờ xác nhận. |
| `derived_knowledge_base` | Nội dung được viết lại từ các tài liệu khác trong kho kiến thức. | Phụ thuộc vào trạng thái của tài liệu nguồn. |

Chỉ tài liệu có `source_type: business_approved`, `business_authority: true` và thông tin phê duyệt hợp lệ mới được dùng để khẳng định phí, thời hạn, điều kiện hoặc quyền xử lý.

## Đối tượng sử dụng

| `audience` | Cách dùng khi retrieval |
|---|---|
| `customer` | Chỉ dùng cho câu hỏi và câu trả lời hướng khách hàng. |
| `staff_internal` | Chỉ dùng cho nhân viên đã đăng nhập đúng phạm vi. |
| `shared` | Dùng được cho cả khách hàng và nhân viên. |
| `internal` | Không đưa vào kết quả retrieval. |

Khi chia đoạn, bộ nạp phải thêm tiêu đề tài liệu vào đầu mỗi đoạn, ví dụ: “Thanh toán và hoàn tiền — Khách thường hỏi gì?”. Điều này giúp từng đoạn đủ ngữ cảnh dù được tìm riêng lẻ.

## Cây tài liệu

```text
knowledge-base/
├── glossary/       thuật ngữ và trạng thái
├── rental/         vòng đời đơn, giao/trả và ngoại lệ
├── inventory/      trang phục, tình trạng sẵn sàng, vệ sinh/sửa chữa
├── transfers/      điều chuyển chi nhánh
├── payments/       thanh toán và hoàn tiền
├── organization/   quyền hạn và chuyển người phụ trách
├── policies/       các quy định còn thiếu cần chốt
└── faq/            câu hỏi nhân viên
```

Tài liệu API, ánh xạ tool và hướng dẫn tích hợp nằm tại `docs/tools-and-integrations.md`, ngoài kho kiến thức nghiệp vụ này.

## Metadata và chunking

Mỗi file có front matter gồm `id`, `title`, `document_type`, `domain`, `status`, `version`, `source_type`, `business_authority`, `retrieval_enabled`, `audience`, `chunk_title_prefix`, `usage_limit` và `source`. Trường `source` chỉ phục vụ truy vết, không được đưa vào nội dung câu trả lời. Khi ingest, một heading `##` hoặc `###` là đơn vị chunk ưu tiên; không tách giữa bảng trạng thái, điều kiện và kết quả của cùng một bước.

Đường dẫn nguồn phải có tiền tố rõ ràng: `workspace://` tính từ workspace Studio, `project://` tính từ thư mục dự án Ops Agent và `kb://` tính từ thư mục `knowledge-base`.

Tài liệu có `status: approved` phải đồng thời có `source_type: business_approved`, `business_authority: true`, `approved_by`, `approved_at` và `effective_from`. Thiếu một trong các trường này thì tài liệu chưa được xem là chính sách đã phê duyệt.

Metadata hiện được lưu cùng từng chunk gồm mã tài liệu, tiêu đề phần, nhãn trích dẫn, miền nghiệp vụ, trạng thái kiểm chứng, quyền làm căn cứ nghiệp vụ, nhóm người đọc và vị trí đoạn. Phiên bản, loại nguồn, giới hạn sử dụng và đường dẫn nguồn được kiểm tra ở cấp tài liệu trước khi ingest nhưng không được ghép vào nội dung trả lời. Chunk có `business_authority: false` không được dùng làm căn cứ khẳng định quy định. Chunk từ `needs_business_confirmation` chỉ được dùng để nhận biết phần còn thiếu, không được trình bày như quy định đang có hiệu lực.

