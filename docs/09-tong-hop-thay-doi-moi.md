# Tổng hợp những phần đã thêm vào DermAI Clinic

> Cập nhật: 04/10/2026. Phạm vi: các commit gần đây từ `f160c058` đến `dafc63fc` và những thay đổi đang có trong working tree. Tài liệu ghi lại chức năng và vị trí mã nguồn; trạng thái kiểm thử được nêu ở cuối.

## 1. Đặt lịch, đặt cọc và hoàn tiền

- Thêm `payment-service` để tạo giao dịch đặt cọc qua PayOS, nhận webhook, đối soát khi quay về trang và xử lý giao dịch hết hạn. Có cấu hình `PAYOS_FAKE_MODE` cho môi trường demo/kiểm thử.
- Luồng đặt lịch có các trạng thái chờ thanh toán và chờ lễ tân xác nhận sau khi cọc thành công. Giao diện bệnh nhân hiển thị trạng thái slot, thông báo thanh toán và chính sách hủy/đổi.
- Bệnh nhân có thể gửi yêu cầu hoàn cọc cho lịch đã hủy. Hệ thống tính mức hoàn theo thời điểm yêu cầu; lễ tân xử lý hàng đợi hoàn tiền và lưu phương thức, mã tham chiếu, người nhận, chứng từ. Admin có màn hình theo dõi.
- Lễ tân có thông báo liên quan đến thanh toán và màn hình đặt lịch hotline được cập nhật theo quy trình mới.

**Mã liên quan:** `services/payment-service/`, `services/appointment-service/`, `frontend/src/features/patient/PatientAppointmentsView.tsx`, `frontend/src/features/reception/ReceptionRefundQueue.tsx`, `frontend/src/features/reception/ReceptionNotifications.tsx`, `frontend/e2e/payment.spec.ts`.

## 2. Khám bệnh, dịch vụ và hóa đơn

- Admin có màn hình quản lý danh mục dịch vụ: mã, tên, chuyên khoa, bác sĩ được phép sử dụng, giá, thời lượng, thứ tự hiển thị và trạng thái hoạt động.
- Trong luồng khám, bác sĩ lập hồ sơ, kê đơn từ danh mục thuốc và xác nhận các dịch vụ thực tế đã làm trước khi hoàn tất ca. Danh sách dịch vụ cùng đơn giá được ghi lại cho ca khám.
- Lễ tân có quầy hóa đơn sau khám: chọn ca đủ điều kiện, lập hóa đơn gồm phí khám, dịch vụ, thuốc và khoản cọc được khấu trừ; thu tiền mặt hoặc mở thanh toán online. Bệnh nhân có trang xem hóa đơn và thanh toán online.
- Admin có bảng đối soát 30 ngày, doanh thu tổng, các khoản theo nguồn thu, dòng tiền và chức năng xuất CSV; backend có API điều chỉnh hóa đơn kèm lý do.

**Mã liên quan:** `services/prescription-service/`, `services/appointment-service/`, `frontend/src/features/admin/AdminServices.tsx`, `frontend/src/features/admin/AdminBilling.tsx`, `frontend/src/features/cashier/CashierWorkspace.tsx`, `frontend/src/features/doctor/DoctorView.tsx`, `frontend/src/features/patient/PatientInvoices.tsx`.

## 3. Kho thuốc và vai trò dược sĩ

- Thêm `inventory-service` độc lập cùng migration cơ sở dữ liệu, danh mục thuốc da liễu mẫu và script nhập dữ liệu/lô mô phỏng.
- Thêm vai trò `PHARMACIST`, route và menu riêng. Dược sĩ có tổng quan quầy thuốc, đơn chờ xuất, kho và lô thuốc, nhập lô, lịch sử nhập/xuất, cảnh báo tồn dưới ngưỡng và lô sắp hết hạn.
- Màn hình xuất thuốc dùng thông tin đơn đã thanh toán và gợi ý lô theo FEFO. Admin có màn hình xem kho.

**Mã liên quan:** `services/inventory-service/`, `frontend/src/features/pharmacy/`, `frontend/src/routes/PharmacyRoute.tsx`, `frontend/src/features/admin/AdminInventory.tsx`.

## 4. Quyền riêng tư cho kết quả AI

- Luồng phân tích ảnh đi qua Patient Service: nhận ảnh và consent, gọi AI nội bộ rồi lưu kết quả. Trình duyệt không tự khai nhãn hoặc confidence để ghi vào lịch sử.
- Thêm ghi nhận consent, nhật ký truy cập AI, mã hóa ảnh gốc AES-256-GCM, thời hạn lưu ảnh mặc định 180 ngày và tác vụ xóa ảnh hết hạn. Xóa assessment sẽ tắt chia sẻ và xóa dữ liệu ảnh.
- Bác sĩ chỉ được đọc kết quả/ảnh khi bệnh nhân đã chia sẻ cho đúng lịch khám mình phụ trách. Tài liệu kiến trúc, API và schema tổng hợp được cập nhật theo luồng này.

**Mã liên quan:** `services/patient-service/`, `database/dermai_full_schema.sql`, `docs/02-architecture.md`, `docs/03-api.md`.

## 5. Chat hỗ trợ và giao diện theo vai trò

- Chat hỗ trợ thêm gửi và hiển thị ảnh JPG/PNG/WebP, tối đa 5 MB; nội dung và ảnh được xử lý trong cùng cuộc trò chuyện. Lễ tân cần nhận phụ trách trước khi trả lời; admin xem ở chế độ giám sát.
- Thanh điều hướng được mở rộng cho bệnh nhân, lễ tân, admin và dược sĩ. Nhiều màn hình lịch khám, dashboard, hồ sơ y khoa, hotline và trang chủ được điều chỉnh để thể hiện các luồng mới.
- Docker/Nginx được cập nhật cho đường trả về thanh toán và cấu hình đóng cửa hằng tuần của phòng khám.

**Mã liên quan:** `frontend/src/features/support/`, `frontend/src/core/appNavigation.ts`, `frontend/src/main.tsx`, `frontend/nginx.conf`, `docker-compose.yml`.

## Trạng thái tại thời điểm ghi

- **Đã commit:** backend thanh toán/hoàn tiền, hóa đơn và dịch vụ thực hiện, inventory service/schema, tăng cường riêng tư AI (các commit `f160c058`, `fd2da1e7`, `94d53cd1`, `ab18a2fe`, `1694abb2`, `dafc63fc`).
- **Chưa commit:** phần lớn màn hình frontend, cập nhật tài liệu/schema tổng hợp, cấu hình và E2E nêu trên đang ở working tree. Vì vậy đây là tổng hợp mã hiện có, chưa phải xác nhận đã phát hành.
- **Kiểm thử:** dự án có unit test và E2E cho nhiều luồng mới, nhưng chưa chạy lại toàn bộ test khi lập tài liệu này.
