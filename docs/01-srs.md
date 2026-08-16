# Đặc tả yêu cầu phần mềm — DermAI Clinic

> Phiên bản 2.0 · Đồng bộ với mã nguồn và SRS Word ngày 11/08/2026.

## 1. Mục tiêu và phạm vi

**Tên đề tài:** Hệ thống đặt lịch khám và hỗ trợ chẩn đoán y tế bằng trí tuệ
nhân tạo cho phòng khám da liễu.

DermAI Clinic lấy quy trình đặt lịch làm nghiệp vụ trung tâm. Computer Vision
cho phép bệnh nhân kiểm tra ảnh da sơ bộ trước khi đặt lịch; hồ sơ y khoa, đơn
thuốc, thông báo, chat và dashboard tạo thành quy trình khám liên tục. AI chỉ
cung cấp thông tin tham khảo, không tự tạo chẩn đoán cuối cùng, không kê thuốc
và không thay bác sĩ.

Phạm vi hiện tại gồm ứng dụng web bốn vai trò, các dịch vụ Spring Boot, dịch vụ
AI FastAPI và hạ tầng Docker Compose. Giá khám cố định theo từng bác sĩ được
hiển thị trước khi đặt và sao chụp vào lịch; Patient thanh toán trực tiếp tại
phòng khám. Gói dịch vụ, thanh toán online, hóa đơn điện tử, bảo hiểm, SMS
thương mại, kết nối bệnh viện và AI thay bác sĩ nằm ngoài phạm vi.

### 1.1. Trạng thái phạm vi AI

- Backend AI đã có API nhận ảnh, Top-3, confidence, ngưỡng không chắc chắn và
  Grad-CAM.
- Checkpoint `efficientnet_b0-20260728T185742Z` đã được huấn luyện cục bộ; test
  gốc cố định 564 ảnh đạt Accuracy 78,90%, Macro F1 78,31%, Weighted F1 78,58%
  và Top-3 Accuracy 93,62%.
- SCIN external test 240 ảnh đạt Accuracy 67,92%, Macro F1 41,57% và Top-3
  92,92%; tập này lệch lớp và không có mẫu `SkinCancer`.
- Frontend dùng Gemini cho tư vấn công khai. Sau mỗi prediction, RAG tự truy hồi
  nội dung liên quan từ PDF hướng dẫn da liễu trong `SkinDisease`, rồi trả tối đa
  ba ý xử trí an toàn, ngắn gọn theo nhóm bệnh.
- Frontend Patient đã có luồng tải ảnh, xem Top-3/Grad-CAM, lưu lịch sử và
  chuyển sang đặt lịch. Patient Service lưu metadata cùng ảnh gốc trong
  `ai_assessments`; Grad-CAM không được lưu. Patient sở hữu được xem/xóa ảnh,
  còn Doctor chỉ đọc khi Patient chia sẻ với đúng appointment phụ trách.

### 1.2. Ngoài phạm vi

- Gói dịch vụ nhiều mức giá, hóa đơn và xác nhận thanh toán trong hệ thống.
- Thanh toán trực tuyến, bảo hiểm, quản lý kho và SMS thương mại.
- AI tự chẩn đoán cuối, tự kê đơn hoặc tự lập phác đồ cá nhân.

## 2. Tác nhân và quyền chính

| Tác nhân | Chức năng |
|---|---|
| Bệnh nhân | Đăng ký OTP, đăng nhập mật khẩu/Google; hồ sơ và avatar; AI; chủ động chia sẻ ảnh/kết quả; xem bác sĩ/giá; giữ/đặt/đổi/hủy trong thời hạn; notification; chat; hồ sơ/đơn; đánh giá |
| Bác sĩ | Hồ sơ nghề nghiệp, avatar, mô tả; ca làm/nghỉ phép; xem lịch và AI được chia sẻ; bắt đầu/hoàn tất; hồ sơ/đơn/tái khám khi cần; không sửa giá khám |
| Lễ tân | Tra cứu và đặt hotline; xác nhận/đề nghị/đổi/hủy; reminder; check-in; hàng đợi; no-show; nhận phụ trách support conversation |
| Quản trị viên | Nhân sự và tài khoản; bác sĩ/giá; bệnh nhân; ngày đóng cửa; review; dashboard; audit; giám sát chat và sửa ca bị quên trạng thái |

Phân quyền sử dụng RBAC với bốn role: `PATIENT`, `DOCTOR`, `RECEPTIONIST` và
`ADMIN`. Gateway xác thực JWT và truyền danh tính/role cho dịch vụ phía sau.

## 3. Yêu cầu chức năng

### 3.1. Xác thực và hồ sơ

- **FR-AUTH-01:** đăng ký Patient bằng email/mật khẩu và OTP 6 số hết hạn sau 5
  phút; đăng nhập mật khẩu hoặc Google OAuth.
- **FR-AUTH-02:** access token 15 phút; refresh token 14 ngày được lưu dạng hash,
  rotate khi dùng; frontend tự refresh một lần khi nhận 401; logout thu hồi token.
- **FR-AUTH-03:** quên/đặt lại mật khẩu bằng OTP email; reset thu hồi phiên cũ.
- **FR-AUTH-04:** Admin tạo, đổi tên, đặt lại mật khẩu, khóa/mở và xem audit
  Doctor/Receptionist; khóa/mở tài khoản Patient.
- **FR-PAT-01:** Patient tạo/cập nhật họ tên, ngày sinh, điện thoại, tiền sử và
  dị ứng. Điện thoại được chuẩn hóa về dạng bắt đầu bằng `0` và là duy nhất.
- **FR-PAT-02:** Lễ tân/Admin tạo hồ sơ khách hotline. Khi bệnh nhân đăng ký bằng
  đúng số điện thoại, hệ thống liên kết hồ sơ, lịch, chat và thông báo cũ với
  tài khoản mới mà không đổi patient ID.
- **FR-PAT-03:** Patient/Receptionist tải avatar JPEG/PNG/WebP tối đa 2 MB;
  Admin đọc avatar khi quản lý tài khoản.
- **FR-DOC-01:** Doctor quản lý họ tên, chuyên môn, số năm kinh nghiệm, chứng
  chỉ, avatar và mô tả công khai.
- **FR-DOC-02:** Doctor sở hữu hoặc Admin cấu hình lịch làm việc định kỳ và nghỉ
  phép; ca cùng ngày không chồng lấn.
- **FR-DOC-03:** Admin cấu hình `consultation_fee` riêng từng Doctor; lịch lưu
  `consultation_fee_snapshot`; Doctor không tự sửa giá.
- **FR-DOC-04:** không lưu lịch làm/nghỉ mới nếu thay đổi chồng lấn hoặc làm mất
  một lịch `CONFIRMED`, `CHECKED_IN` hoặc `IN_PROGRESS`; khi không xác minh được
  Appointment Service, thao tác phải fail-closed.

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
- **FR-APT-06:** Patient có tối đa ba lịch sắp tới, không được đặt hai Doctor
  trùng giờ hoặc cùng một Doctor hai lần trong một ngày. Nhân viên được vượt
  giới hạn ba lịch khi xử lý ngoại lệ nhưng vẫn phải tôn trọng overlap.
- **FR-APT-07:** Patient chỉ tự đổi/hủy lịch `PENDING` hoặc `ASSIGNED` trong 30
  phút đầu và trước khi lễ tân xác nhận; sau đó phải chat/gọi lễ tân. Lịch hủy
  giải phóng slot ngay và có thể được Patient ẩn.
- **FR-APT-08:** Lễ tân/Admin có thể tạo đề nghị lịch giữ 10 phút để Patient đồng ý
  hoặc từ chối.
- **FR-APT-09:** Scheduling Engine đề xuất tối đa số lượng được yêu cầu, mặc
  định 5, kèm điểm và lý do.
- **FR-APT-10:** WebSocket phát sự kiện khi slot, lịch, chat, notification,
  avatar hoặc giá thay đổi; client tự reconnect và tải dữ liệu chuẩn từ REST.
- **FR-APT-11:** lễ tân/Admin đặt hộ, phân Doctor, xác nhận, check-in, đổi/hủy và
  ghi audit. Hai nhân viên xử lý đồng thời không được ghi đè kết quả người trước.
- **FR-APT-12:** nhắc lịch tự động trước khoảng 24 giờ và 2 giờ; lễ tân có thể
  lưu trạng thái đã gọi, gửi lại hoặc không liên hệ được.
- **FR-APT-13:** sau khi ngày khám kết thúc, lịch chờ mà bác sĩ chưa bắt đầu được
  tự động chuyển `CANCELLED`.
- **FR-APT-14:** lễ tân/Admin chỉ check-in lịch `CONFIRMED` đúng ngày và chỉ ghi
  `NO_SHOW` sau giờ bắt đầu 30 phút.
- **FR-APT-15:** Doctor phụ trách bắt đầu/hoàn tất. Hoàn tất không bắt buộc hồ
  sơ/đơn; lễ tân/Admin chỉ hoàn tất ca `IN_PROGRESS` bị quên sau grace period.

### 3.3. Khám, hồ sơ và đơn thuốc

- **FR-MED-01:** chỉ Doctor phụ trách lịch được bắt đầu lượt khám và tạo hồ sơ y
  khoa; hoàn tất lượt khám không bắt buộc tạo hồ sơ hoặc đơn thuốc.
- **FR-MED-02:** hồ sơ gồm chẩn đoán cuối, ghi chú lâm sàng, kế hoạch điều trị,
  mức độ và thời điểm tái khám nếu có.
- **FR-RX-01:** chỉ Doctor tạo và ký đơn thuốc gắn với hồ sơ; Patient chỉ đọc
  đơn của chính mình.
- **FR-MED-03:** Doctor không được liệt kê toàn bộ Patient. Doctor chỉ xem hồ sơ
  hành chính khi có quan hệ điều trị và chỉ đọc hồ sơ/đơn do mình ký; Admin giữ
  quyền đối soát toàn phòng khám. Patient chỉ đọc dữ liệu thuộc identity của mình.
- **FR-FUP-01:** Doctor đánh dấu cần tái khám và ngày sớm nhất; Patient/lễ tân
  chọn lịch mới liên kết lịch gốc.

### 3.4. AI, tư vấn và tương tác

- **FR-AI-01:** API AI chỉ nhận JPEG/PNG/WebP tối đa 10 MB và từ chối tệp không
  giải mã được.
- **FR-AI-02:** khi model đã nạp, API trả nhãn chính, Top-3, confidence, model
  version, cờ `uncertain`, Grad-CAM dạng data URL và disclaimer.
- **FR-AI-03:** khi chưa có checkpoint, API phải fail-closed với HTTP 503; không
  tạo kết quả giả.
- **FR-AI-04:** frontend chỉ cho Patient chạy model. Patient Service lưu
  metadata, model version, trạng thái chia sẻ và ảnh gốc trong assessment;
  Grad-CAM không được lưu.
- **FR-AI-05:** Patient sở hữu đọc/xóa ảnh assessment. Doctor chỉ đọc ảnh và
  metadata khi Patient chia sẻ với đúng appointment mà Doctor phụ trách; ảnh
  trả về với `Cache-Control: no-store`.
- **FR-CHAT-01:** chatbot Gemini công khai chỉ tư vấn kiến thức chăm sóc da,
  không chẩn đoán chắc chắn, kê đơn hoặc nêu liều thuốc.
- **FR-RAG-01:** sau prediction, RAG truy hồi theo nhãn từ tài liệu y khoa cục bộ,
  trả đoạn tham khảo cùng tên nguồn/số trang; khi index chưa sẵn sàng hoặc không
  đủ bằng chứng phải fail-closed thay vì bịa nội dung.
- **FR-RAG-02:** nội dung tự động cho Patient không chứa liều hoặc tên thuốc kê
  đơn; chỉ tóm tắt tối đa ba ý xử trí/chăm sóc được kiểm soát theo trang điều trị.
- **FR-SUP-01:** Patient và lễ tân chat hỗ trợ realtime; lễ tân nhìn thấy danh
  tính, tên và số điện thoại của đúng cuộc hội thoại.
- **FR-SUP-02:** lễ tân phải nhận conversation trước khi trả lời; một
  conversation chỉ có một lễ tân phụ trách tại một thời điểm. Lễ tân đang phụ
  trách có thể hoàn tất yêu cầu để lần chat tiếp theo quay lại AI; Admin chỉ giám sát.
- **FR-SUP-03:** trợ lý hỗ trợ tự động chỉ hướng dẫn thủ tục đã được duyệt và
  phân loại yêu cầu. Đổi/hủy/đặt hộ, trạng thái lịch cá nhân, tài khoản, phản ánh
  và câu hỏi chuyên môn phải chuyển lễ tân; AI không tự thao tác dữ liệu.
- **FR-SUP-04:** mọi lượt Patient/AI/System được lưu trong cùng conversation.
  Trợ lý tự chuyển khi nghiệp vụ bắt buộc cần người thật, câu hỏi không khớp rõ
  quy tắc định tuyến, Patient
  không hài lòng hoặc hai lượt liên tiếp chưa giải quyết được; không hỏi xác nhận
  chuyển và không tạo hội thoại mới.
- **FR-SUP-05:** trước khi claim, lễ tân thấy toàn bộ transcript cùng intent,
  điểm khớp quy tắc, nội dung đã thử và lý do chuyển. Conversation còn ở
  `AI_ACTIVE` không
  xuất hiện trong hộp thư lễ tân; trạng thái chuyển/claim được đồng bộ realtime.
- **FR-REV-01:** mỗi lịch `COMPLETED` chỉ được đánh giá một lần; chỉ review
  `APPROVED` xuất hiện công khai.

## 4. Vòng đời lịch khám

Các trạng thái hiện có:

`HELD`, `PROPOSED`, `PENDING`, `ASSIGNED`, `CONFIRMED`, `CHECKED_IN`, `IN_PROGRESS`,
`COMPLETED`, `FOLLOW_UP_REQUIRED`, `NO_SHOW`, `CANCELLED`.

Luồng chính:

```text
HELD -> ASSIGNED -> CONFIRMED -> CHECKED_IN -> IN_PROGRESS -> COMPLETED
PROPOSED -> CONFIRMED -> CHECKED_IN -> IN_PROGRESS -> COMPLETED
PENDING -> ASSIGNED -> CONFIRMED -> CHECKED_IN -> IN_PROGRESS -> COMPLETED
COMPLETED -> FOLLOW_UP_REQUIRED -> tạo lịch mới liên kết lịch gốc
CONFIRMED -> NO_SHOW
HELD|PROPOSED|PENDING|ASSIGNED|CONFIRMED|CHECKED_IN -> CANCELLED
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
- **Riêng tư:** cần consent trước khi dùng ảnh; role và quan hệ sở hữu/điều trị
  đều phải được kiểm tra tại backend trước khi xem hồ sơ;
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
10. Giá lịch cũ không đổi khi Admin cập nhật giá Doctor.
11. Doctor chỉ đọc ảnh AI được Patient chia sẻ với đúng appointment.

## 7. Thuật toán đề xuất lịch

```text
score = 0.40 * specialty
      + 0.25 * earliness
      + 0.20 * freeCapacity
      + 0.10 * continuity
      + 0.05 * preference
```

Mỗi thành phần nằm trong `[0,1]`. Kết quả sắp theo score giảm dần, sau đó theo
thời gian và UUID để ổn định. Recommendation không thay thế kiểm tra
availability, Booking Policy hoặc database constraint.

## 8. Use case trọng yếu

| ID | Use case | Actor | Luồng chính và ngoại lệ quan trọng |
|---|---|---|---|
| UC-01 | Đăng ký/xác minh | Patient | Nhập email/mật khẩu → OTP → tạo/nhận hồ sơ; OTP sai/hết hạn hoặc email/SĐT trùng bị từ chối |
| UC-02 | Đặt lịch | Patient | Chọn Doctor/ngày/slot → hold 5 phút → lý do → xem giá → xác nhận; xung đột, quá 3 lịch hoặc hold hết hạn bị từ chối |
| UC-03 | Đổi/hủy | Patient, Receptionist, Admin | Kiểm tra quyền/thời hạn → slot mới hoặc lý do → cập nhật/audit/realtime; Patient quá 30 phút hoặc đã xác nhận phải liên hệ hỗ trợ |
| UC-04 | Đặt hotline | Receptionist | Tìm/tạo hồ sơ bằng SĐT → chọn Doctor/slot → đọc lại thông tin → tạo lịch và audit |
| UC-05 | Xác nhận đồng thời | Receptionist, Admin | Khóa lịch → kiểm tra trạng thái → xác nhận; người bấm sau thấy lịch đã được nhân viên khác xử lý |
| UC-06 | Check-in/no-show | Receptionist, Admin | Check-in đúng ngày; no-show chỉ sau giờ bắt đầu 30 phút |
| UC-07 | Bắt đầu/hoàn tất | Doctor | Xem reason/AI được chia sẻ → bắt đầu → khám → hồ sơ/đơn nếu cần → hoàn tất |
| UC-08 | AI và chia sẻ | Patient, Doctor | Predict → Top-3/Grad-CAM/RAG → lưu assessment/ảnh → Patient chia sẻ → Doctor phụ trách đọc; ảnh lỗi 4xx, model thiếu 503 |
| UC-09 | Trợ lý/chat/claim | Patient, Receptionist, Admin | Patient nhắn → bộ định tuyến theo luật xác định nhóm yêu cầu; RAG/Gemini hỗ trợ nội dung trong phạm vi cho phép hoặc Scheduling Engine tra lịch đọc-only → tự chuyển khi cần → Receptionist thấy transcript + summary, claim và phản hồi realtime; Admin chỉ giám sát |
| UC-10 | Giá khám | Admin | Chọn Doctor → lưu giá không âm → profile update; lịch mới dùng giá mới, lịch cũ giữ snapshot |
| UC-11 | Đánh giá | Patient, Admin | Patient đánh giá lịch hoàn tất → Admin duyệt/ẩn; lịch chưa hoàn tất hoặc đã review bị từ chối |

## 9. Yêu cầu dữ liệu và riêng tư

| Dữ liệu | Ràng buộc |
|---|---|
| Identity/session | Email duy nhất, BCrypt, refresh token hash; không log token/OTP |
| Patient | SĐT chuẩn hóa/duy nhất khi liên kết; hotline có thể chưa có identity thật |
| Doctor | `consultation_fee` không âm; chỉ Admin sửa |
| Appointment | overlap constraint Doctor/Patient, snapshot, audit; Patient ẩn không xóa cứng |
| AI assessment | metadata, ảnh BLOB, MIME, share flag, appointmentId; owner/xóa/no-store; không lưu Grad-CAM |
| Medical data | owner/phụ trách/role hợp lệ; không dùng dữ liệu bệnh nhân thật trong demo |
| Chat/review | giữ lịch sử đối soát; review chỉ công khai sau duyệt |

Không gửi ảnh hoặc PII Patient tới Gemini. Không commit `.env`, secret, API key,
checkpoint, ảnh y khoa hoặc raw metadata SCIN.

## 10. Ma trận truy vết rút gọn

| Nghiệp vụ | Requirement | Use case | Nhóm test |
|---|---|---|---|
| Đăng ký/OTP | FR-AUTH-01..04 | UC-01 | AUTH-001..003 |
| Đặt lịch | FR-APT-01..10 | UC-02 | BOOK-001..022 |
| Đổi/hủy | FR-APT-07, FR-APT-11, FR-APT-13 | UC-03 | BOOK-023..028 |
| Hotline | FR-PAT-02, FR-APT-11 | UC-04 | REC-001..004 |
| Xác nhận | FR-APT-11 | UC-05 | BOOK-029..030 |
| Check-in/no-show | FR-APT-14 | UC-06 | REC-009..010 |
| Lượt khám | FR-APT-15, FR-MED-01..02 | UC-07 | DOC-001..006 |
| AI | FR-AI-01..05, FR-RAG-01..02 | UC-08 | AI-001..007 |
| Chat | FR-SUP-01..03 | UC-09 | CHAT-001..005 và AI support policy tests |
| Giá | FR-DOC-03 | UC-10 | ADM-001, BOOK-021 |
| Review | FR-REV-01 | UC-11 | Review functional tests |

## 11. Baseline kiểm thử AI hiện tại

Model runtime: `efficientnet_b0-20260728T185742Z`.

| Tập | Số ảnh | Accuracy | Macro F1 | Weighted F1 | Top-3 |
|---|---:|---:|---:|---:|---:|
| Test gốc cố định | 564 | 78,90% | 78,31% | 78,58% | 93,62% |
| SCIN external test | 240 | 67,92% | 41,57% | 65,94% | 92,92% |

Đây là bằng chứng kiểm thử của model thử nghiệm, không phải requirement hoặc
cam kết lâm sàng. External test lệch lớp và không có `SkinCancer`; xem
[`model-card-scin-v1.md`](model-card-scin-v1.md) để biết confusion matrix,
giới hạn và quy trình tái lập.
