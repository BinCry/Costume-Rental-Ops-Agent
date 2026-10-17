# Costume Rental Ops Agent

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangChain-1C3334?style=flat-square&logo=chainlink&logoColor=white" alt="LangChain">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/pgvector-336791?style=flat-square&logo=postgresql&logoColor=white" alt="pgvector">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Coolify-6A0DAD?style=flat-square&logo=coolify&logoColor=white" alt="Coolify">
  <img src="https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white" alt="GitHub Actions">
</p>

Service Python độc lập bổ sung Ops Agent và RAG cho [Costume Rental Studio](https://github.com/BinCry/Costume-Rental-Studio). Repo này chứa API AI, knowledge base, ingestion và evaluation; giao diện người dùng tiếp tục thuộc ứng dụng Studio chính.

## Tài liệu chính

- [Yêu cầu sản phẩm Ops Agent](docs/product-requirements.md)
- [Quy trình nghiệp vụ](docs/business-processes.md)
- [Đặc tả hành vi Agent](docs/agent-behavior-spec.md)
- [Tools và tích hợp](docs/tools-and-integrations.md)
- [Đánh giá và an toàn](docs/evaluation-and-safety.md)
- [Chỉ mục kho tri thức RAG](knowledge-base/00-index.md)

## Chạy API

Yêu cầu Python 3.11 hoặc 3.12 và `uv`.

```powershell
Copy-Item .env.example .env
uv sync
uv run python scripts/validate_knowledge_base.py
uv run python scripts/migrate_knowledge.py
uv run python scripts/ingest_knowledge.py
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

`migrate_knowledge.py` now applies both the pgvector schema and the agent-case
schema. It is safe to re-run: each migration is checksum tracked.

## Kho tri thức RAG

`knowledge-base/` chỉ chứa nội dung nghiệp vụ bằng ngôn ngữ dễ hiểu để đưa vào RAG. API, ánh xạ tool và hướng dẫn phát triển nằm trong `docs/` và không được ingest vào kho trả lời khách hàng. Khi ingest, front matter phải được tách thành metadata; trường `source` chỉ dùng để truy vết và không được ghép vào nội dung trả lời.

File có `retrieval_enabled: false` phải bị loại khỏi tập tìm kiếm. Tài liệu đã được đối chiếu với hành vi hiện có của Studio mang nhãn `verified_from_system`; tài liệu đang soạn mang nhãn `draft_from_code`. Hai loại này có thể giải thích quy trình hệ thống nhưng không thay thế chính sách kinh doanh. Quy định chưa có bằng chứng được gắn `needs_business_confirmation` và không được dùng làm quy định chính thức cho câu trả lời hoặc thao tác.

Các quy định lõi của `POLICY-2025` và ma trận quyền hoàn tiền đã được chủ dự án xác nhận làm nguồn nghiệp vụ chính thức. Các tài liệu tương ứng mang `status: approved` và `business_authority: true`, nên RAG có thể dùng để trả lời về giới hạn thuê, hiệu lực báo giá, trả trễ, hủy đơn, thời hạn xử lý hoàn tiền, điều kiện hoàn cọc và quyền phê duyệt trong đúng phạm vi được công bố. Thời điểm phải trả và số tiền cụ thể của một đơn vẫn phải lấy từ dữ liệu live của đơn; knowledge base không thay thế việc tra cứu đó. Mức bồi thường hư hỏng hoặc thất lạc, phí gia hạn, chi phí điều chuyển và quy trình miễn giảm ngoại lệ vẫn chưa được phê duyệt, vì vậy Agent phải từ chối suy đoán hoặc chuyển người phụ trách.

## Python RAG API

RAG chạy trực tiếp từ thư mục gốc bằng Python/FastAPI. Service này kết nối trực tiếp với database PGVector riêng, nhưng kiểm tra quyền bằng cách gọi API của Costume Rental Studio; không đọc database nghiệp vụ của Studio.

```powershell
Copy-Item .env.example .env
uv sync
uv run python scripts/migrate_knowledge.py
uv run python scripts/ingest_knowledge.py
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

`AI_DATABASE_URL` phải là một PostgreSQL URL duy nhất. Mật khẩu có ký tự đặc biệt như `@` phải URL-encode thành `%40`; không dùng tham số Prisma `schema=public`, và không lặp lại tên biến trong giá trị (ví dụ `AI_DATABASE_URL=AI_DATABASE_URL=...`).

Các endpoint Python là `POST /api/v1/knowledge/search` và `POST /api/v1/knowledge/answer`. Cả hai đều là API service-to-service và bắt buộc có header `X-AI-Service-Key` khớp `AI_INTERNAL_API_KEY`:

- Studio API xác thực Bearer token trước khi gọi Python service, sau đó gửi actor context qua `X-Actor-Id` và `X-Knowledge-Audiences`.
- `search` yêu cầu actor đã đăng nhập và chỉ phục vụ luồng nội bộ.
- `answer` cho phép actor `guest`. Guest và customer chỉ truy xuất tài liệu `customer/shared`, còn staff có quyền `knowledge.read.all` truy xuất `staff_internal/shared`.

### API contract

Các endpoint knowledge dùng cùng response envelope với Studio API và serialize tên trường JSON theo `camelCase`:

```json
{
  "success": true,
  "data": { "result": {} },
  "message": "Knowledge answer completed"
}
```

Mọi lỗi đã xử lý, bao gồm body không hợp lệ, route không tồn tại và HTTP method không được hỗ trợ, đều trả envelope chung:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid knowledge answer request"
  },
  "statusCode": 400,
  "timestamp": "2026-10-13T12:00:00+00:00",
  "path": "/api/v1/knowledge/answer",
  "requestId": "..."
}
```

Service giữ `X-Request-Id` do caller gửi hoặc tự tạo nếu thiếu, rồi trả lại cùng giá trị trong response header và error body để trace xuyên hai service. Body JSON sai cú pháp dùng code `INVALID_JSON`; body không đúng schema dùng `VALIDATION_ERROR`, đều với HTTP 400. Schema request, success response, error response và yêu cầu xác thực có tại `/docs` hoặc `/openapi.json`; OpenAPI không quảng bá response 422 mặc định vì validation đã được chuẩn hóa thành 400.

Frontend và client bên ngoài không gọi trực tiếp Python service và không được nhận `AI_INTERNAL_API_KEY`. Chúng chỉ gọi `POST /api/v1/knowledge/answer` trên Studio API. Studio API áp dụng rate limit, xác thực Bearer token nếu có, tự tạo actor context đáng tin cậy, rồi chuyển tiếp request cùng service key. Python service không nhận JWT và không gọi ngược `/auth/me`. `/api/v1/knowledge/search` không được proxy ra Studio API.

### Cấu hình hai service

Hai service phải ở cùng private network và dùng cùng một secret ngẫu nhiên dài ít nhất 32 ký tự. URL phải là origin nội bộ, không chứa credential, path, query hoặc fragment.

| Service | Biến | Giá trị |
| --- | --- | --- |
| Studio API | `AI_SERVICE_URL` | Origin nội bộ của Python service, ví dụ `http://costume-rental-ops-agent:8001` |
| Studio API | `AI_SERVICE_TIMEOUT_MS` | Timeout proxy; mặc định `30000` ms |
| Studio API | `AI_INTERNAL_API_KEY` | Cùng secret với Python service |
| Studio API | `TRUST_PROXY_HOPS` | Số reverse-proxy hop chính xác; để trống khi chạy local, Coolify thường là `1` |
| Python service | `AI_INTERNAL_API_KEY` | Cùng secret với Studio API |

Trong Coolify, dùng hostname/nội bộ URL thật được cấp cho từng resource; không dùng `localhost` để kết nối giữa hai container. Chỉ Studio API cần public access. Sau khi deploy, kiểm tra `GET /health/ready` của Python service trước khi gửi câu hỏi qua Studio API.

Endpoint `answer` dùng Groq làm primary và Gemini làm fallback; cấu hình bằng `GROQ_API_KEY` và `GEMINI_API_KEY`. Fallback chỉ xảy ra khi timeout, HTTP 429 hoặc HTTP 5xx, không xảy ra khi knowledge base thiếu dữ liệu. Cả hai endpoint đều trả citation và từ chối trả lời khi không có ngữ cảnh đủ tin cậy.

## Agent runtime

Agent chạy đồng bộ, không cần worker/job queue riêng. Nhánh đọc dùng LangChain
`create_agent` làm ReAct loop và LangGraph checkpoint theo `case_id`. Nhánh ghi
dùng một outer `StateGraph`: graph dừng bằng `interrupt()` tại confirmation và
approval, sau đó endpoint quyết định resume đúng checkpoint bằng
`Command(resume=...)`.

Mỗi message trước tiên được ánh xạ vào một goal có cấu trúc gồm `goalType`,
`skillName`, inputs đã trích xuất, constraints, plan và success criteria. Goal
resolver dùng rule làm fast-path cho yêu cầu rõ ràng; câu diễn đạt tự nhiên chưa
khớp rule được Groq phân loại bằng structured output và dùng Gemini làm fallback.
Model chỉ đề xuất loại goal, entity, confidence và write intent. Tool, permission,
confirmation/approval và success criteria luôn lấy từ policy/skill tin cậy trong
code. Nếu case đang `WAITING_INPUT`, message mới bổ sung vào goal hiện có thay vì
phân loại lại từ đầu; goal mơ hồ hoặc write intent chưa rõ sẽ tiếp tục hỏi người
dùng. Token dùng để phân loại goal được tính vào budget toàn case.

`skills.py` chứa các business playbook cho policy, tra cứu đơn,
availability/schedule, gia hạn, reallocation, hủy đơn, unit block, transfer,
checkout và refund. Skill là một tool allowlist cứng: ReAct chỉ nhìn thấy read
tools của skill hiện tại, còn write planner chỉ được đề xuất write tool nằm trong
đúng skill đó.

Mọi write action được đóng băng bằng payload hash, có idempotency key xác định,
được Studio API kiểm tra lại quyền/branch/version và chỉ thành công sau read-back.
Timeout write không được retry mù. Các feature flag write trong `.env.example`
mặc định vẫn là `false`; chỉ bật từng nhóm sau khi chạy migration
`python scripts/migrate_knowledge.py` và hoàn tất E2E trên đúng môi trường.

Luồng write chuẩn:

```text
message -> proposal -> fresh read -> frozen action -> confirmation interrupt
        -> execute/read-back hoặc approval interrupt -> execute/read-back
        -> SUCCEEDED / CANCELLED / HANDED_OFF
```

Mỗi case bị giới hạn 6 vòng/tool calls một turn, 24 bước và 30.000 model token
cho toàn case. Token của write planner cũng được tính vào budget. Với nhánh đọc,
`goalVerified` chỉ là `true` khi verification đạt và `terminationReason` là
`GOAL_ACHIEVED`; kết quả thành công không tạo `handoff`. Khi loop, stall, hết
budget, vi phạm policy hoặc verification thất bại, API trả termination reason
tương ứng và `handoff` có reason, tool/evidence đã quan sát, bước tiếp theo cùng
trạng thái side effect. Write timeout không được tự động retry.

## Docker và CI/CD

Build production image từ chính thư mục Ops Agent để `.dockerignore` cục bộ
được áp dụng:

```powershell
docker build -t costume-rental-ops-agent:local .
docker run --rm -p 8001:8001 --env-file .env costume-rental-ops-agent:local
```

Image dùng Python 3.12, dependency production được khóa bởi `uv.lock`, chạy bằng
user không có quyền root và kiểm tra sức khỏe qua `/health`. Secret runtime
không được copy vào image.

Hai GitHub Actions workflow ở thư mục `.github/workflows`:

- `ci.yml`: chạy Ruff, mypy, kiểm tra knowledge base, pytest và build
  Python package khi pull request hoặc branch khác `main` thay đổi AI service.
- `publish.yml`: chạy lại toàn bộ kiểm tra trên `main`, publish image
  `kietphan24/costume-rental-ops-agent:staging` cùng một tag chứa short SHA, sau
  đó gọi webhook deploy resource Ops Agent trên Coolify.

Trước khi bật publish, tạo các GitHub repository secret:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
- `OPS_AGENT_COOLIFY_DEPLOY_WEBHOOK`
- `COOLIFY_API_TOKEN` (không bắt buộc nếu URL webhook đã tự xác thực)

Trong Coolify, cấu hình resource pull image
`kietphan24/costume-rental-ops-agent:staging`, expose port `8001` và inject các
biến trong `.env.example`. Đặt pre-deploy command là
`python scripts/migrate_knowledge.py`. Chỉ chủ động chạy
`python scripts/ingest_knowledge.py` khi tài liệu được duyệt có thay đổi. Không
đưa database URL hoặc provider API key production vào workflow GitHub.
