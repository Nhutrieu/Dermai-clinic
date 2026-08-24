# Test case bổ sung cho chương kiểm thử

Tài liệu này bổ sung **30 test case** cho các nhánh rủi ro chưa được mô tả đầy đủ
trong catalog 81 test case trước đây. Tất cả case mới mặc định là `NOT_RUN` cho đến
khi được thực thi trên một revision xác định và có bằng chứng đối chiếu.

## 1. Quy ước

- `P0`: lỗi có thể làm lộ dữ liệu, tạo lịch trùng hoặc sai toàn vẹn nghiệp vụ.
- `P1`: chức năng chính không hoạt động hoặc trả kết quả sai.
- `P2`: lỗi phụ, thông báo hoặc trải nghiệm người dùng.
- `NOT_RUN`: mới thiết kế, chưa được phép tính vào số test pass.
- Khi chạy phải ghi thêm: revision, thời gian, người chạy, Actual Result, Evidence
  và Defect ID nếu kết quả là `FAIL`.
- Không dùng tài khoản, ảnh y tế, OTP, token hoặc thông tin bệnh nhân thật.

## 2. Xác thực và tài khoản

| ID | Ưu tiên | Mục tiêu | Tiền điều kiện | Các bước chính | Kết quả mong đợi | Trạng thái |
|---|---|---|---|---|---|---|
| AUTH-004 | P1 | OTP hết hạn không thể xác minh email | Có tài khoản chưa xác minh và OTP đã hết hạn | 1. Mở màn hình nhập OTP. 2. Nhập OTP đã hết hạn. 3. Xác nhận. | API từ chối; tài khoản vẫn chưa xác minh; giao diện báo OTP hết hạn và cho phép gửi lại. | NOT_RUN |
| AUTH-005 | P1 | OTP sai không xác minh được tài khoản | Có tài khoản chưa xác minh | 1. Nhập OTP sai định dạng hợp lệ. 2. Xác nhận. | API trả lỗi phù hợp; không đổi trạng thái xác minh; không đăng nhập tự động. | NOT_RUN |
| AUTH-006 | P1 | OTP đã dùng không được tái sử dụng | Có OTP hợp lệ | 1. Xác minh thành công. 2. Gửi lại cùng OTP lần hai. | Lần đầu thành công; lần hai bị từ chối; không tạo thêm phiên hoặc thay đổi dữ liệu. | NOT_RUN |
| AUTH-007 | P0 | Refresh token không dùng được sau đăng xuất | Đã đăng nhập và có access/refresh token | 1. Gọi logout bằng refresh token. 2. Dùng lại token đó để refresh. | Logout thành công; lần refresh sau trả 401/403; không cấp access token mới. | NOT_RUN |
| AUTH-008 | P0 | Tài khoản bị khóa không thể đăng nhập | Admin đã khóa một tài khoản demo | 1. Đăng nhập đúng email/mật khẩu của tài khoản bị khóa. | Không cấp token; giao diện hiển thị trạng thái tài khoản bị khóa, không báo sai thành lỗi kết nối chung. | NOT_RUN |

## 3. Đặt lịch, nghỉ phép và ngày phòng khám nghỉ

| ID | Ưu tiên | Mục tiêu | Tiền điều kiện | Các bước chính | Kết quả mong đợi | Trạng thái |
|---|---|---|---|---|---|---|
| BOOK-031 | P0 | Slot được giải phóng sau khi bệnh nhân hủy lịch | Bệnh nhân có lịch đang khóa slot 16:30 | 1. Hủy lịch. 2. Tải lại availability cùng bác sĩ/ngày. 3. Đặt lại 16:30. | Lịch cũ là `CANCELLED`; slot 16:30 xuất hiện lại; lịch mới được tạo mà không báo trùng với lịch đã hủy. | NOT_RUN |
| BOOK-032 | P0 | Không cho bác sĩ nghỉ khi còn lịch hoạt động | Bác sĩ có lịch HELD/ASSIGNED/CONFIRMED nằm trong khoảng xin nghỉ | 1. Bác sĩ thêm khoảng nghỉ trùng lịch. | API trả conflict; không tạo `leave_period`; thông báo nêu phải đổi/hủy lịch trước. | NOT_RUN |
| BOOK-033 | P0 | Không cho admin đóng phòng khám khi còn lịch hoạt động | Ngày được chọn có ít nhất một lịch hoạt động | 1. Admin thêm ngày phòng khám nghỉ. | API trả conflict; không tạo `clinic_closure`; giao diện hiển thị lý do rõ ràng. | NOT_RUN |
| BOOK-034 | P1 | Không đặt lịch chồng giờ nghỉ trưa | Bác sĩ làm việc 08:00–17:00, nghỉ trưa 12:00–13:00 | 1. Chọn slot bắt đầu trước 12:00 nhưng kết thúc sau 12:00. 2. Thử đặt. | Slot không được đề xuất hoặc API từ chối; không tạo appointment. | NOT_RUN |
| BOOK-035 | P1 | Không đặt ngoài giờ làm việc bác sĩ | Có lịch làm việc đã cấu hình | 1. Gửi request với thời gian trước giờ bắt đầu hoặc sau giờ kết thúc. | API trả lỗi availability; không lưu appointment. | NOT_RUN |
| BOOK-036 | P0 | Một bệnh nhân không có hai lịch chồng thời gian | Bệnh nhân đã có một lịch hoạt động | 1. Đặt thêm lịch với bác sĩ khác nhưng trùng thời gian. | Database/application từ chối; chỉ tồn tại một lịch hoạt động trong khoảng đó. | NOT_RUN |
| BOOK-037 | P0 | Retry cùng Idempotency-Key không tạo lịch trùng | Có slot hợp lệ | 1. Gửi hai request đặt lịch giống nhau với cùng `Idempotency-Key`. | Hai response tham chiếu cùng appointment; database chỉ có một bản ghi mới. | NOT_RUN |
| BOOK-038 | P1 | Hold hết hạn tự giải phóng slot | Tạo được slot ở trạng thái `HELD` | 1. Không xác nhận hold. 2. Chờ quá hạn hoặc chạy job hết hạn. 3. Kiểm tra availability. | Hold chuyển trạng thái hết hiệu lực/hủy; slot xuất hiện lại; người khác có thể giữ slot. | NOT_RUN |

## 4. Hồ sơ và lịch bác sĩ

| ID | Ưu tiên | Mục tiêu | Tiền điều kiện | Các bước chính | Kết quả mong đợi | Trạng thái |
|---|---|---|---|---|---|---|
| DOC-007 | P0 | Bác sĩ không sửa được hồ sơ của bác sĩ khác | Có hai tài khoản bác sĩ A và B | 1. Đăng nhập A. 2. Gọi endpoint cập nhật lịch/nghỉ của B. | API trả 403; hồ sơ, lịch làm và ngày nghỉ của B không thay đổi. | NOT_RUN |
| DOC-008 | P0 | Không cho đổi lịch làm nếu làm mất hiệu lực lịch đã đặt | Bác sĩ có lịch xác nhận 16:30 | 1. Đổi giờ kết thúc làm việc thành 16:00. | API trả conflict; lịch làm việc cũ được giữ nguyên; appointment không bị thay đổi âm thầm. | NOT_RUN |
| DOC-009 | P1 | Xóa ngày nghỉ mở lại các slot phù hợp | Có ngày nghỉ không còn xung đột lịch | 1. Kiểm tra ngày nghỉ không có slot. 2. Bác sĩ xóa ngày nghỉ. 3. Tải availability. | Ngày nghỉ bị xóa; các slot theo lịch làm việc xuất hiện lại; WebSocket hoặc refresh cập nhật UI. | NOT_RUN |

## 5. Hồ sơ bệnh án và đơn thuốc

| ID | Ưu tiên | Mục tiêu | Tiền điều kiện | Các bước chính | Kết quả mong đợi | Trạng thái |
|---|---|---|---|---|---|---|
| MR-001 | P0 | Bác sĩ không có quan hệ khám không được đọc bệnh nhân | Bác sĩ A chưa từng phụ trách bệnh nhân X | 1. Đăng nhập A. 2. Gọi API lấy bệnh nhân/hồ sơ của X. | API trả 403/404; không trả PII hoặc dữ liệu y tế. | NOT_RUN |
| MR-002 | P0 | Bệnh nhân không đọc được bệnh án của người khác | Có bệnh nhân A, B và bệnh án của B | 1. Đăng nhập A. 2. Gọi trực tiếp ID bệnh án của B. | API trả 403/404; response không chứa chẩn đoán hoặc ghi chú của B. | NOT_RUN |
| RX-001 | P0 | Bác sĩ không kê đơn trên hồ sơ của bác sĩ khác | Hồ sơ thuộc bác sĩ B | 1. Đăng nhập bác sĩ A. 2. Gửi request tạo đơn gắn với hồ sơ đó. | Prescription Service từ chối; không tạo prescription hoặc item. | NOT_RUN |
| RX-002 | P0 | Bệnh nhân chỉ xem đơn thuốc của mình | Có đơn thuốc của bệnh nhân A và B | 1. Đăng nhập A. 2. Gọi `/prescriptions/mine`. | Chỉ trả đơn của A; không có ID, thuốc hoặc hướng dẫn của B. | NOT_RUN |

## 6. AI và ảnh y tế

| ID | Ưu tiên | Mục tiêu | Tiền điều kiện | Các bước chính | Kết quả mong đợi | Trạng thái |
|---|---|---|---|---|---|---|
| AI-012 | P1 | Từ chối file không phải ảnh dù đổi phần mở rộng | Chuẩn bị file văn bản/PDF đổi tên `.jpg` | 1. Upload file lên chức năng kiểm tra da. | API trả 4xx; không chạy inference; không lưu assessment hoặc ảnh. | NOT_RUN |
| AI-013 | P1 | Từ chối ảnh vượt giới hạn dung lượng | Chuẩn bị JPEG/PNG lớn hơn giới hạn API | 1. Upload ảnh. | API trả 413/4xx với thông báo dung lượng; không lưu BLOB. | NOT_RUN |
| AI-014 | P0 | Ảnh ngoài phạm vi không bị ép thành một trong tám bệnh | Chuẩn bị ảnh phong cảnh, đồ vật và vết thương WSeg held-out | 1. Gửi từng ảnh vào `/ai/predict`. | Ảnh được từ chối hoặc gắn trạng thái ngoài phạm vi/không chắc chắn; không hiển thị chẩn đoán chắc chắn. Nếu bị ép nhãn, ghi `FAIL` và Defect ID. | NOT_RUN |
| AI-015 | P1 | Ảnh quá mờ/tối không được phân tích như ảnh hợp lệ | Chuẩn bị ảnh blur mạnh và ảnh gần như đen | 1. Upload từng ảnh. | Quality gate trả lỗi hướng dẫn chụp lại; không lưu kết quả dự đoán sai lệch. | NOT_RUN |
| AI-016 | P0 | Không chia sẻ kết quả AI vào lịch của bệnh nhân khác | Bệnh nhân A có assessment; có appointment của B | 1. Đăng nhập A. 2. Gắn assessment của A vào appointment của B. | Patient Service trả conflict/forbidden; assessment không đổi `appointmentId`; bác sĩ của B không thấy ảnh. | NOT_RUN |

## 7. Chat hỗ trợ

| ID | Ưu tiên | Mục tiêu | Tiền điều kiện | Các bước chính | Kết quả mong đợi | Trạng thái |
|---|---|---|---|---|---|---|
| CHAT-006 | P0 | Hai lễ tân không thể đồng thời nhận cùng cuộc trò chuyện | Có một conversation đang chờ | 1. Hai lễ tân bấm nhận gần như đồng thời. | Chỉ một lễ tân được gán; người còn lại nhận conflict hoặc thấy trạng thái đã nhận; không mất transcript. | NOT_RUN |
| CHAT-007 | P0 | Lễ tân chưa nhận conversation không được trả lời | Conversation đang thuộc lễ tân A hoặc chưa được nhận | 1. Lễ tân B gửi reply trực tiếp qua API. | API trả 409/403; tin nhắn không được lưu; người bệnh không nhận tin giả danh. | NOT_RUN |

## 8. Bảo mật Gateway và liên service

| ID | Ưu tiên | Mục tiêu | Tiền điều kiện | Các bước chính | Kết quả mong đợi | Trạng thái |
|---|---|---|---|---|---|---|
| SEC-006 | P0 | Access token hết hạn bị từ chối | Có JWT hết hạn nhưng chữ ký hợp lệ | 1. Gọi API bảo vệ qua Gateway. | Gateway trả 401 `application/problem+json`; request không đến service nghiệp vụ. | NOT_RUN |
| SEC-007 | P0 | Không thể tự nâng quyền bằng header từ trình duyệt | Đăng nhập Patient | 1. Gửi request kèm `X-User-Role: ADMIN`. 2. Gọi API chỉ dành cho Admin. | Gateway dùng role trong JWT; API trả 403; không thực hiện thao tác admin. | NOT_RUN |
| SEC-008 | P0 | Endpoint nội bộ từ chối service token sai | Có endpoint `/internal/...` | 1. Gọi không token. 2. Gọi token sai. 3. Gọi token đúng trong môi trường test. | Hai lần đầu trả 403; lần cuối chỉ trả trường dữ liệu tối thiểu đúng thiết kế; không lộ dữ liệu dư. | NOT_RUN |

## 9. Mẫu ghi kết quả sau khi chạy

| Trường | Nội dung cần ghi |
|---|---|
| Test Case ID | Ví dụ `BOOK-032` |
| Revision | Commit SHA và `workingTreeDirty=true/false` |
| Môi trường | Local Docker/E2E staging, phiên bản trình duyệt, database test |
| Thời gian | Ngày giờ theo ICT |
| Actual Result | Kết quả thực tế quan sát được, gồm HTTP status và thay đổi dữ liệu |
| Status | `PASS`, `FAIL`, `BLOCKED` hoặc `NOT_RUN` |
| Evidence | Log, JUnit/JSON report, ảnh/video đã loại dữ liệu nhạy cảm |
| Defect ID | Bắt buộc nếu `FAIL` |

## 10. Gợi ý chọn test case để trình bày trong báo cáo

Nếu chương kiểm thử chỉ đủ chỗ cho 10 case tiêu biểu, ưu tiên:

1. `AUTH-007` – thu hồi refresh token sau logout.
2. `BOOK-031` – hủy lịch rồi đặt lại đúng slot.
3. `BOOK-032` – bác sĩ nghỉ trùng lịch đang hoạt động.
4. `BOOK-033` – phòng khám nghỉ nhưng còn lịch bệnh nhân.
5. `BOOK-036` – bệnh nhân không được có lịch chồng nhau.
6. `BOOK-037` – idempotency chống tạo lịch trùng khi retry.
7. `MR-002` – cách ly hồ sơ bệnh án giữa bệnh nhân.
8. `AI-014` – ảnh ngoài phạm vi tám nhóm bệnh.
9. `CHAT-006` – hai lễ tân tranh chấp nhận hội thoại.
10. `SEC-007` – không thể giả mạo role qua header.

Các test này bao phủ chức năng, concurrency, phân quyền, AI safety và tính toàn vẹn
dữ liệu. Chỉ đưa kết quả vào báo cáo sau khi đã chạy và lưu bằng chứng.
