# Inventory & Pharmacy Service

FastAPI service quản lý tồn kho theo lô và cấp thuốc theo FEFO cho DermAI Clinic. Dữ liệu được lưu trong schema PostgreSQL `pharmacy`; service không chứa seed hoặc dữ liệu demo.

## Database schema

- Migration khởi tạo: `db/migration/V1__pharmacy_inventory.sql`.
- File khởi tạo toàn hệ thống: `database/dermai_full_schema.sql` ở thư mục gốc.
- Service vẫn chạy `CREATE SCHEMA IF NOT EXISTS` và SQLAlchemy `create_all()` khi khởi động để tương thích với môi trường hiện có; migration là nguồn chuẩn để tạo database mới và review thay đổi schema.

## Luồng dữ liệu thật

- Danh mục thuốc đang hoạt động trong `prescription.medicines` được đồng bộ idempotent sang `pharmacy.products` khi Dược sĩ mở danh mục hoặc hàng đợi.
- Thuốc mới do Dược sĩ tạo được ghi ngược sang `prescription.medicines`, nên xuất hiện ngay trong danh mục kê đơn của Bác sĩ. Tổng tồn khả dụng được cập nhật sau mỗi lần nhập hoặc xuất lô.
- Hóa đơn có thuốc chuyển sang `PAID` trong `prescription.invoices` được đưa vào hàng đợi `pharmacy.prescriptions` cùng tên bệnh nhân và các dòng thuốc thật.
- Sau khi xuất kho thành công, transaction cập nhật số lượng theo lô, ghi `pharmacy.inventory_logs`, chuyển đơn trong pharmacy sang `DISPENSED`, đồng thời cập nhật hóa đơn nguồn và số lượng đã giao.
- Tồn cũ không được tự chuyển thành lô vì schema cũ không có số lô và hạn sử dụng. Dược sĩ phải nhập đúng lô thực tế qua màn hình Kho & lô thuốc.

## API

- `GET /api/v1/pharmacy/pending-prescriptions`
- `POST /api/v1/pharmacy/dispense`
- `GET /api/v1/inventory/products`
- `POST /api/v1/inventory/products`
- `GET /api/v1/inventory/batches`
- `POST /api/v1/inventory/import-batch`
- `GET /api/v1/inventory/summary`
- `GET /api/v1/inventory/logs`
- `GET /api/v1/inventory/alerts/low-stock`
- `GET /api/v1/inventory/alerts/expiring`

Gateway chuyển `X-User-Id` và `X-User-Role` từ JWT. Tất cả endpoint nghiệp vụ chỉ chấp nhận vai trò `PHARMACIST`.

Khi xuất thuốc, service khóa đơn và toàn bộ lô liên quan bằng `SELECT ... FOR UPDATE` trong cùng transaction. Các lô được khóa theo ID ổn định để giảm nguy cơ deadlock; tồn kho được kiểm tra lại sau khi khóa và trước khi trừ.

## Danh mục thuốc da liễu

`data/dermatology_catalog.json` chứa danh mục khởi tạo được đối chiếu với PDF RAG `SkinDisease/Huong-dan-chan-doan-dieu-tri-Da-lieu.pdf`. Giá là cấu hình vận hành ban đầu và phải được duyệt lại theo báo giá thực tế. File không tạo số lô, hạn dùng hay số lượng tồn.

Có thể kiểm tra hoặc nhập lại danh mục sau khi reset database:

```bash
python services/inventory-service/scripts/import_dermatology_catalog.py --user-id <PHARMACIST_UUID> --dry-run
python services/inventory-service/scripts/import_dermatology_catalog.py --user-id <PHARMACIST_UUID>
```

Importer idempotent theo SKU: sản phẩm đã tồn tại sẽ được bỏ qua.
## Chạy local

```bash
docker compose up -d --build postgres inventory-service gateway frontend
```

- Frontend: `http://localhost:3000`
- OpenAPI: `http://localhost:8010/docs`
- Health check: `http://localhost:8010/health`

Tài khoản Dược sĩ được tạo qua `POST /api/v1/auth/staff` bởi quản trị viên. Không lưu mật khẩu mặc định trong source code.
## Simulated batch dataset

`data/simulated_batch_plan.json` records the explicitly simulated `SIM-*` batches used to exercise FEFO, low-stock alerts, and 30-day expiry alerts. Import them through the API so every quantity change is logged and synchronized to the doctor medicine catalogue:

```bash
python services/inventory-service/scripts/import_simulated_batches.py --user-id <PHARMACIST_UUID> --dry-run
python services/inventory-service/scripts/import_simulated_batches.py --user-id <PHARMACIST_UUID>
```

The importer keeps the saved plan and skips existing batch numbers on subsequent runs. Pass `--regenerate` only when a new simulation plan is intentionally required.
