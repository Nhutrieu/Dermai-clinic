# Đặc tả yêu cầu phần mềm — DermAI Clinic

## 1. Mục tiêu và phạm vi

**Tên đề tài:** Hệ thống đặt lịch khám và hỗ trợ chẩn đoán y tế bằng trí tuệ
nhân tạo cho phòng khám da liễu.

DermAI Clinic lấy quy trình đặt lịch làm nghiệp vụ trung tâm. Computer Vision
hỗ trợ bác sĩ phân tích ảnh da liễu; hồ sơ y khoa, đơn thuốc, thông báo, chat và
dashboard tạo thành quy trình khám liên tục. AI chỉ cung cấp thông tin tham
khảo, không tự tạo chẩn đoán cuối cùng, không kê thuốc và không thay bác sĩ.

Phạm vi hiện tại gồm ứng dụng web bốn vai trò, các dịch vụ Spring Boot, dịch vụ
AI FastAPI và hạ tầng Docker Compose. Thanh toán, bảo hiểm, SMS thương mại, kết
nối bệnh viện và chẩn đoán tự động thay bác sĩ nằm ngoài phạm vi.

### 1.1. Trạng thái phạm vi AI

- Backend AI đã có API nhận ảnh, Top-3, confidence, ngưỡng không chắc chắn và
  Grad-CAM.
- Repository chưa có checkpoint `best_model.pth` hoặc bộ dữ liệu huấn luyện;
  chưa được công bố metric.
- Frontend hiện dùng Gemini cho tư vấn công khai. RAG trích xuất có citation đã
  có mã nền nhưng chưa được nối vào giao diện chính.
- Luồng tải ảnh và xem kết quả chẩn đoán AI trên frontend là phần cần hoàn tất
  để đạt đầy đủ mục tiêu đề tài.

## 2. Tác nhân và quyền chính

| Tác nhân | Chức năng |
|---|---|
| Bệnh nhân | Đăng ký; cập nhật hồ sơ; chọn bác sĩ/ngày/slot; giữ và xác nhận lịch; đổi/hủy trong thời hạn; xem lịch, hồ sơ, đơn thuốc; nhận thông báo; chat lễ tân; đánh giá lịch đã hoàn thành |
| Bác sĩ | Cập nhật hồ sơ nghề nghiệp, avatar, mô tả; quản lý ca làm/nghỉ phép; xem lịch được xác nhận; bắt đầu khám; xem AI tham khảo; ghi hồ sơ; ký đơn; yêu cầu tái khám |
| Lễ tân | Tra cứu bệnh nhân; đặt hộ qua hotline/chat; tiếp nhận, phân công, xác nhận, đổi/hủy lịch; nhắc lịch; ghi nhận không đến khám |
| Quản trị viên | Tạo tài khoản nhân sự; xem bác sĩ/bệnh nhân; khóa/mở tài khoản bệnh nhân; khai báo ngày nghỉ chung; duyệt đánh giá; xem dashboard |

Phân quyền sử dụng RBAC với bốn role: `PATIENT`, `DOCTOR`, `RECEPTIONIST` và
`ADMIN`. Gateway xác thực JWT và truyền danh tính/role cho dịch vụ phía sau.

## 3. Yêu cầu chức năng

### 3.1. Xác thực và hồ sơ

- **FR-AUTH-01:** đăng ký bệnh nhân, đăng nhập, refresh token rotation, đăng
  xuất, quên mật khẩu và đặt lại mật khẩu bằng OTP email.
- **FR-AUTH-02:** Admin tạo tài khoản Doctor/Receptionist/Admin và khóa hoặc mở
  khóa tài khoản Patient.
- **FR-PAT-01:** Patient tạo/cập nhật họ tên, ngày sinh, điện thoại, tiền sử và
  dị ứng. Điện thoại được chuẩn hóa về dạng bắt đầu bằng `0` và là duy nhất.
- **FR-PAT-02:** Lễ tân/Admin tạo hồ sơ khách hotline. Khi bệnh nhân đăng ký bằng
  đúng số điện thoại, hệ thống liên kết hồ sơ, lịch, chat và thông báo cũ với
  tài khoản mới mà không đổi patient ID.
- **FR-DOC-01:** Doctor quản lý họ tên, chuyên môn, số năm kinh nghiệm, chứng
  chỉ, avatar và mô tả công khai.
- **FR-DOC-02:** Doctor cấu hình lịch làm việc định kỳ và nghỉ phép; hệ thống
  kiểm tra ca làm khi sinh slot.

### 3.2. Đặt lịch và điều phối

- **FR-APT-01:** hiển thị slot theo bác sĩ và ngày trong cửa sổ tối đa 60 ngày,
  múi giờ `Asia/Ho_Chi_Minh`.
- **FR-APT-02:** loại bỏ slot ngoài ca, nghỉ trưa 12:00–13:00, nghỉ phép, ngày
  phòng khám đóng cửa, slot đã đặt và slot đang được giữ.
- **FR-APT-03:** Patient giữ slot trong 5 phút, xác nhận hoặc nhấn lại để nhả;
  slot hết hạn được tự giải phóng.
- **FR-APT-04:** chống trùng lịch bác sĩ và bệnh nhân bằng kiểm tra ứng dụng kết
  hợp PostgreSQL exclusion constraint cho mọi trạng thái đang chiếm chỗ.
- **FR-APT-05:** `Idempotency-Key` ngăn tạo lặp khi client retry thao tác đặt,
  đổi hoặc tái khám.
- **FR-APT-06:** Patient chỉ tự hủy trong 30 phút kể từ lúc đặt; sau thời hạn
  phải chat/gọi lễ tân. Lịch hủy giải phóng slot ngay và có thể được Patient ẩn.
- **FR-APT-07:** Lễ tân có thể tạo đề nghị lịch giữ 10 phút để Patient đồng ý
  hoặc từ chối.
- **FR-APT-08:** Scheduling Engine đề xuất tối đa số lượng được yêu cầu, mặc
  định 5, kèm điểm và lý do.
- **FR-APT-09:** WebSocket phát sự kiện khi slot, lịch, chat hoặc thông báo thay
  đổi; client tự reconnect và tải lại dữ liệu chuẩn từ REST API.
- **FR-APT-10:** nhắc lịch tự động trước khoảng 24 giờ và 2 giờ; lễ tân có thể
  lưu trạng thái đã gọi, gửi lại hoặc không liên hệ được.
- **FR-APT-11:** sau khi ngày khám kết thúc, lịch chờ mà bác sĩ chưa bắt đầu được
  tự động chuyển `CANCELLED`.
- **FR-APT-12:** sau giờ khám 30 phút, lễ tân/Admin có thể ghi nhận `NO_SHOW`.

### 3.3. Khám, hồ sơ và đơn thuốc

- **FR-MED-01:** chỉ Doctor phụ trách lịch được bắt đầu/hoàn thành buổi khám và
  tạo hồ sơ y khoa cho lịch đó.
- **FR-MED-02:** hồ sơ gồm chẩn đoán cuối, ghi chú lâm sàng, kế hoạch điều trị,
  mức độ và thời điểm tái khám nếu có.
- **FR-RX-01:** chỉ Doctor tạo và ký đơn thuốc gắn với hồ sơ; Patient chỉ đọc
  đơn của chính mình.
- **FR-FUP-01:** Doctor đánh dấu cần tái khám và ngày sớm nhất; Patient/lễ tân
  chọn lịch mới liên kết lịch gốc.

### 3.4. AI, tư vấn và tương tác

- **FR-AI-01:** API AI chỉ nhận JPEG/PNG/WebP tối đa 10 MB và từ chối tệp không
  giải mã được.
- **FR-AI-02:** khi model đã nạp, API trả nhãn chính, Top-3, confidence, model
  version, cờ `uncertain`, Grad-CAM dạng data URL và disclaimer.
- **FR-AI-03:** khi chưa có checkpoint, API phải fail-closed với HTTP 503; không
  tạo kết quả giả.
- **FR-AI-04:** frontend mục tiêu cho phép Patient/Doctor tải ảnh và hiển thị kết
  quả như tham khảo, tách biệt với trường chẩn đoán cuối của bác sĩ.
- **FR-CHAT-01:** chatbot Gemini công khai chỉ tư vấn kiến thức chăm sóc da,
  không chẩn đoán chắc chắn, kê đơn hoặc nêu liều thuốc.
- **FR-RAG-01:** RAG là mô-đun mở rộng có citation; khi index chưa sẵn sàng phải
  trả lời không đủ bằng chứng thay vì bịa nội dung.
- **FR-SUP-01:** Patient và lễ tân chat hỗ trợ realtime; lễ tân nhìn thấy danh
  tính, tên và số điện thoại của đúng cuộc hội thoại.
- **FR-REV-01:** mỗi lịch `COMPLETED` chỉ được đánh giá một lần; chỉ review
  `APPROVED` xuất hiện công khai.

## 4. Vòng đời lịch khám

Các trạng thái hiện có:

`HELD`, `PROPOSED`, `PENDING`, `ASSIGNED`, `CONFIRMED`, `IN_PROGRESS`,
`COMPLETED`, `FOLLOW_UP_REQUIRED`, `NO_SHOW`, `CANCELLED`.

Luồng chính:

```text
HELD -> ASSIGNED -> CONFIRMED -> IN_PROGRESS -> COMPLETED
PROPOSED -> CONFIRMED -> IN_PROGRESS -> COMPLETED
PENDING -> ASSIGNED -> CONFIRMED -> IN_PROGRESS -> COMPLETED
COMPLETED -> FOLLOW_UP_REQUIRED -> tạo lịch mới liên kết lịch gốc
CONFIRMED -> NO_SHOW
HELD|PROPOSED|PENDING|ASSIGNED|CONFIRMED -> CANCELLED
```

Mọi chuyển trạng thái không hợp lệ trả lỗi 409. `HELD` và `PROPOSED` hết hạn
được chuyển hủy tự động và không hiển thị như lịch bình thường của Patient.

## 5. Yêu cầu phi chức năng

- **Bảo mật:** BCrypt, JWT access 15 phút, refresh token rotation, RBAC, secret
  qua biến môi trường, không commit `.env`, không ghi PII/ảnh vào log.
- **Tính toàn vẹn:** transaction, idempotency, ràng buộc chống khoảng thời gian
  giao nhau, Flyway migration và validation phía server.
- **Khả dụng:** healthcheck cho container; WebSocket reconnect; notification có
  retry/dead-letter sau khi cấu hình routing được kiểm chứng.
- **Hiệu năng:** frontend lazy loading, cache asset tĩnh, index database; metric
  p95 chỉ được công bố sau khi đo trên môi trường xác định.
- **Riêng tư:** cần consent trước khi dùng ảnh; chỉ role phù hợp được xem hồ sơ;
  không gửi PII/ảnh bệnh nhân tới Gemini hoặc provider ngoài.
- **Khả năng tiếp cận:** responsive, keyboard/focus rõ ràng, giảm chuyển động
  theo `prefers-reduced-motion` và độ tương phản đủ đọc.
- **Vận hành:** PostgreSQL có volume; production cần volume/backup cho RabbitMQ,
  secret mạnh, TLS, rate limit, metrics, alert và quy trình restore đã thử.

## 6. Tiêu chí nghiệm thu trọng yếu

1. Hai request đồng thời chỉ có một request giữ/đặt được cùng slot.
2. Slot phản ánh ca làm, nghỉ trưa, nghỉ phép, ngày đóng cửa và booking window.
3. Hủy/đổi lịch giải phóng slot và tab khác cập nhật không cần F5.
4. Patient không đọc dữ liệu người khác; lễ tân không ghi hồ sơ hay kê đơn.
5. Model chưa nạp trả 503; model đã nạp trả Top-3 và Grad-CAM đúng schema.
6. AI không tự ghi vào chẩn đoán cuối hoặc tự sinh đơn thuốc.
7. Lịch hotline được liên kết đúng tài khoản theo số điện thoại chuẩn hóa.
8. Review chỉ tạo một lần cho lịch hoàn thành và phải qua Admin duyệt.
9. Luồng hoàn chỉnh chạy được bằng Docker Compose và có test booking race.
