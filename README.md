# Costume Rental Ops Agent

Ứng dụng này phát triển độc lập dựa trên nền giao diện và các luồng nghiệp vụ của [Costume Rental Studio](https://github.com/BinCry/Costume-Rental-Studio), đồng thời bổ sung Ops Agent cho công việc vận hành. Hai repo có mã nguồn, môi trường chạy và vòng đời riêng; hiện chưa dùng chung backend hoặc dữ liệu live.

## Tài liệu chính

- [Định hướng sản phẩm](docs/product-direction.md)
- [Yêu cầu sản phẩm Ops Agent](docs/product-requirements.md)
- [Tổng quan frontend](apps/web/README.md)
- [Tổng quan Ops Agent](ops-agent/README.md)

## Chạy ứng dụng

Yêu cầu Node.js tương thích với Vite và pnpm `11.1.2`.

```powershell
pnpm install
pnpm dev
```

Frontend hiện dùng fixture; Ops Agent chưa kết nối model, API hoặc nguồn dữ liệu vận hành live. Các thao tác trong prototype không ghi giao dịch lên máy chủ.
