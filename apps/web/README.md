# Web foundation — Costume Rental Studio + Ops Agent

Đây là bản frontend nền được sao chép từ snapshot UI của Costume Rental Studio để hai sản phẩm phát triển song song trên cùng nền giao diện và luồng nghiệp vụ. Ops Agent sẽ được bổ sung như một capability dành cho vận hành; bản sao này chưa có chức năng agent hoặc backend nghiệp vụ thật.

## Trạng thái hiện tại

- React, TypeScript, Vite và Tailwind CSS.
- Giao diện Studio hiện có dùng fixture; banner demo và dữ liệu mẫu phải được giữ rõ cho tới khi thay bằng API/provider thật.
- Khu vực Ops Agent nằm tại `/van-hanh/ops-agent`; câu trả lời hiện là kịch bản mẫu có trích dẫn tài liệu snapshot, chưa gọi mô hình hay nguồn nghiệp vụ.
- Nguồn sao chép và giới hạn xác minh được ghi trong [source review](../../docs/source-review.md) và [studio reference manifest](../../ops-agent/context/studio-reference/README.md).
- Yêu cầu thêm Ops Agent nằm trong [product requirements](../../docs/product-requirements.md).

## Chạy frontend

Tại repo root, cài dependencies bằng `pnpm install`, sau đó chạy `pnpm dev`.
