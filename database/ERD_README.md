# ERD DermAI Clinic

Mở [dbdiagram.io](https://dbdiagram.io), tạo diagram mới rồi dán nội dung một trong hai file:

- `dermai_erd.dbml`: 48 bảng, 9 schema, 417 cột và 33 khóa ngoại **có thật** trong PostgreSQL. Dùng file này để trình bày ERD vật lý.
- `dermai_erd_with_logical_refs.dbml`: cùng cấu trúc trên, thêm 41 liên kết UUID do ứng dụng quản lý. Các dòng cuối có chú thích `// LOGICAL`; chúng **không phải** khóa ngoại trong PostgreSQL. Dùng file này để trình bày quan hệ nghiệp vụ xuyên service.

DBML chỉ dùng để vẽ sơ đồ, không phải SQL để khởi tạo database. Để sơ đồ dễ đọc, các file không hiển thị giá trị mặc định, `CHECK`, chỉ mục thường và chỉ mục `UNIQUE` có điều kiện. Ba bảng chi tiết của schema `prescription` hiện không có khóa chính riêng; sơ đồ giữ đúng cấu trúc đó.

Nguồn sinh: `docs/database-schema-reference.md` và `docs/database-erd-guide.md`. Khi tài liệu schema đổi, chạy:

```powershell
python scripts/generate_erd_dbml.py
```
