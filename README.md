# Costume Rental Studio + Ops Agent

Repo này phát triển song song với [Costume Rental Studio](https://github.com/BinCry/Costume-Rental-Studio). Nó bắt đầu từ bản sao frontend/UI/UX và tài liệu hữu ích của Studio, giữ parity với các luồng nền đã xác nhận, rồi bổ sung hệ thống Ops Agent cho công việc vận hành.

Studio gốc vẫn tiếp tục như một web nghiệp vụ bình thường trong repo riêng. Hai nhánh có code và vòng đời riêng; việc đồng bộ UI/domain được thực hiện có chủ đích theo [quy trình parity](docs/ui-parity.md). Frontend hiện có là bản fixture từ snapshot chưa xác minh commit, chưa có backend nghiệp vụ thật và chưa kết nối API Studio.

## Bắt đầu với repo

- [Định hướng sản phẩm](docs/product-direction.md): cách phát triển song song và vai trò bổ sung của Agent.
- [Yêu cầu sản phẩm](docs/product-requirements.md): yêu cầu chức năng, parity, bảo vệ dữ liệu và tiêu chí chấp nhận.
- [Quy trình đồng bộ](docs/ui-parity.md): cách giữ UI/luồng/ngôn ngữ nhất quán qua hai repo.
- [Rà soát nguồn](docs/source-review.md): độ tin cậy và giới hạn của tài liệu/snapshot.
- [Hướng dẫn làm việc của agent](ops-agent/AGENTS.md).

## Tài nguyên đã mang về

- [Frontend nền](apps/web/README.md): React/TypeScript/Vite/Tailwind, các luồng Studio dạng fixture.
- [Manifest nguồn và tài liệu UI/UX](ops-agent/context/studio-reference/README.md).
- [Handoff](ops-agent/context/HANDOFF.md), [phân tích nghiệp vụ](ops-agent/context/PROJECT_BA.md) và [snapshot tài liệu đã chọn](ops-agent/context/snapshot/).

## Chạy frontend

Yêu cầu Node.js phù hợp với Vite hiện hành và pnpm `11.1.2`.

```powershell
pnpm install
pnpm dev
```

Các màn hiện có là demo fixture; chúng không ghi giao dịch lên máy chủ. Ops Agent và mọi nguồn dữ liệu vận hành thật chưa được tích hợp.

## Repo liên quan

- Repo này: <https://github.com/BinCry/Costume-Rental-Ops-Agent>
- Studio gốc: <https://github.com/BinCry/Costume-Rental-Studio>
