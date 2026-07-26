# Software Requirements Specification

## 1. Phạm vi và nguyên tắc

DermAI Clinic quản lý hành trình từ đăng ký, đặt lịch, khám, hồ sơ, đơn thuốc
đến tái khám. Computer Vision và chatbot RAG là công cụ hỗ trợ; giao diện luôn
hiển thị cảnh báo “không thay thế bác sĩ”. AI không tạo chẩn đoán cuối cùng,
không kê thuốc và không tự động thay đổi hồ sơ.

## 2. Actor và use case

| Actor | Use case chính |
|---|---|
| Patient | Quản lý hồ sơ cá nhân; khai tiền sử/dị ứng; tải ảnh; đặt/hủy/đổi lịch; xem lịch sử, kết luận và đơn đã ký |
| Receptionist | Tìm bệnh nhân; tạo lịch; nhận gợi ý slot/bác sĩ; xác nhận, đổi hoặc hủy lịch; check-in |
| Doctor | Quản lý lịch làm/nghỉ; xem hàng đợi; xem AI dưới dạng tham khảo; ghi khám; chẩn đoán cuối; ký đơn; yêu cầu tái khám |
| Admin | Quản lý tài khoản/RBAC, bác sĩ, danh mục, cấu hình, audit và dashboard |

## 3. Yêu cầu chức năng

- FR-AUTH-01: đăng ký, đăng nhập, refresh token rotation, đăng xuất và OTP email.
- FR-AUTH-02: RBAC bốn vai trò; khóa tài khoản và audit sự kiện nhạy cảm.
- FR-PAT-01: quản lý hồ sơ, tiền sử, dị ứng và ảnh có consent.
- FR-DOC-01: chuyên môn, chứng chỉ, ca làm và nghỉ phép.
- FR-APT-01: đặt, hủy, đổi, tái khám; chống trùng lịch bằng transaction.
- FR-APT-02: gợi ý tối đa 5 slot, cân bằng tải và giải thích điểm số.
- FR-MED-01: chỉ Doctor được hoàn tất hồ sơ và ký đơn thuốc.
- FR-AI-01: top-3, confidence, Grad-CAM; lưu model version và thời điểm.
- FR-RAG-01: trả lời từ knowledge base, kèm trích dẫn; từ chối kê thuốc.
- FR-NOT-01: email theo event, retry và idempotency.
- FR-DASH-01: KPI theo khoảng ngày và quyền truy cập.

## 4. Trạng thái lịch khám

`PENDING -> ASSIGNED -> CONFIRMED -> IN_PROGRESS -> COMPLETED`

`COMPLETED -> FOLLOW_UP_REQUIRED -> PENDING` tạo lịch mới liên kết lịch gốc.
`PENDING|ASSIGNED|CONFIRMED -> CANCELLED`. Không cho hủy sau `IN_PROGRESS`.
Mọi chuyển trạng thái sai trả HTTP 409 và được ghi audit.

## 5. Phi chức năng

- Bảo mật: TLS, Argon2/BCrypt, JWT 15 phút, refresh token rotation, RBAC,
  malware scan ảnh, giới hạn 10 MB, audit bất biến và không ghi PII vào log.
- Hiệu năng: API CRUD p95 < 400 ms; gợi ý lịch p95 < 1 giây; inference GPU
  p95 < 3 giây; dashboard có cache 60 giây.
- Tin cậy: availability mục tiêu 99,5%; backup hằng ngày; RPO 24 giờ, RTO 4 giờ.
- Khả năng tiếp cận: responsive, keyboard navigation, WCAG 2.1 AA cơ bản.
- Riêng tư: consent rõ ràng, retention cấu hình được, xóa/ẩn danh theo chính sách.
- Quan sát: correlation ID, structured log, health check, metrics và alert.

## 6. Acceptance criteria quan trọng

1. Hai yêu cầu đồng thời không thể giữ cùng bác sĩ/cùng slot.
2. Bác sĩ nghỉ phép không xuất hiện trong gợi ý.
3. Patient không đọc hồ sơ của người khác; receptionist không kê đơn.
4. AI chưa nạp model phải fail-closed với 503.
5. Chatbot không có nguồn phù hợp phải nói không đủ dữ liệu, không bịa.
6. Mọi kết luận cuối và đơn thuốc có bác sĩ, timestamp và audit trail.

