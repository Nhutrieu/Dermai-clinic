# Kiểm thử collection Postman — 09/11/2026

**Current Docker state:** the test project `dermai-e2e-postman-20261109` had its 16 containers and network removed at the user's request. Its database volume, private configuration and environment were retained. Test port `http://localhost:53000` is offline until services are recreated with `postman/start-test-environment.ps1`. For the main stack, use `http://localhost:8080` and accounts/IDs belonging to its database. The 184/187 results below are historical results from before cleanup.

Đã đối chiếu đủ **187 request** của `postman/DermAI_Clinic.postman_collection.json`: **184 PASS, 0 lỗi còn tồn tại, 3 BLOCKED**, với **360 assertion của kết quả cuối**. Tổng cộng 331 lượt HTTP qua các nhóm và fixture phù hợp; các request lặp lấy kết quả cuối, 18 lượt lỗi ban đầu được giữ trong artifact để đối chiếu.

Newman **6.2.2** thực thi request và script Postman. Điều khiển giao diện Windows lỗi khởi tạo sandbox nên không thao tác tài khoản/cửa sổ Postman. Đã đăng nhập **API DermAI** bằng cả Admin, Patient, Doctor, Receptionist và Pharmacist; lượt đăng nhập cuối của cả năm vai trò trả HTTP 200.

## Phạm vi và bằng chứng

- Stack/database riêng `dermai-e2e-postman-20261109`, dữ liệu và tài khoản tổng hợp; commit nền `be801397561f8cc0a3df9998241bc4fcc3f20177`, working tree chưa commit.
- Gateway `http://localhost:53000`; AI chẩn đoán trực tiếp `http://localhost:58000`; Inventory health `http://localhost:58010`. Cổng bổ sung chỉ bind loopback.
- AI/RAG nạp thật. PayOS dùng `FakePayOSGateway`, không chuyển tiền thật. Đăng ký/OTP/đổi mật khẩu dùng SMTP sink nội bộ Docker, không gửi email ra ngoài; giữ nguyên cooldown của backend.
- Đã chạy luồng giữ chỗ/cọc/xác nhận/check-in/khám/hồ sơ/đơn thuốc/dịch vụ; hóa đơn thu tiền mặt và online, hủy/tạo lại link thanh toán, đối soát, cấp thuốc; hoàn cọc có ảnh chứng từ và tải lại chứng từ; đề nghị lịch, nhắc lịch, no-show/phân công, chat, nghỉ phép, CRUD và vòng đời tài khoản.
- Bootstrap Admin được kiểm tra trên database auth trắng riêng; database/container bootstrap phụ đã dọn. Stack test chính và SMTP sink được giữ lúc nghiệm thu, sau đó đã xóa theo yêu cầu người dùng ngày 09/11/2026.

## Ba mục chưa thể ghi PASS đầy đủ

| Request | Trạng thái | Điều kiện còn thiếu |
|---|---|---|
| Google Login | BLOCKED | Google ID credential thật |
| Account Status Stream | BLOCKED trong runner thường | Kết nối SSE dài; đã kiểm tra riêng header **HTTP 200, text/event-stream**, chưa chạy assertion hoàn tất stream |
| PayOS webhook | BLOCKED | Payload PayOS có chữ ký thật; không suy từ provider giả lập |

Gate toàn collection còn BLOCKED theo ba mục này. Request public chat trả HTTP 200 theo assertion của collection; kết quả không xác nhận kết nối Gemini bên ngoài. Các phản hồi HTTP 4xx bị tính là chưa đạt ở lớp đối chiếu, kể cả khi assertion cũ chỉ kiểm tra `<500`.

## Đã sửa trong JSON và environment example

- Chỉnh lịch làm việc và slot policy dùng token **Admin** theo controller hiện tại.
- Sau tạo nhân sự, lưu `identityId` vào `staff_identity_id`; sau đổi lịch, lưu ID lịch trả về để thao tác tiếp đúng lịch.
- Cấp thuốc dùng `invoice_id` làm ID đơn của pharmacy, tách khỏi `prescription_id` của đơn lâm sàng.
- Tham số hóa `cash_amount_received` và `patient_phone`; tránh tiền thu ghi cứng và trùng số điện thoại giữa fixture.
- SSE có guard `run_sse=true` cho thao tác chủ động; tránh treo lượt collection thường.
- Thêm trường ảnh `evidence` tùy chọn, mặc định tắt, trong request hoàn tiền để kiểm tra tải chứng từ.

## Artifact và sử dụng tiếp

[Manifest đã đối chiếu](postman-test-results-20261109.json) lưu trạng thái của đủ 187 request, HTTP code, phase, số assertion, hash collection và phạm vi test. Các báo cáo Newman đầy đủ cùng lịch sử lỗi từng nằm ở `tmp/postman-20261109/*.newman.json`; thư mục này cùng artifact E2E của stack Postman đã được xóa theo yêu cầu dọn dữ liệu test. Báo cáo tổng hợp này và manifest vẫn được giữ; kết quả là bằng chứng lịch sử của lượt chạy trước khi dọn.

File môi trường cục bộ `postman/DermAI_Clinic_Test_20261109.postman_environment.json` chứa credential/token test đã được xóa. Database, container, network và SMTP sink của riêng stack Postman cũng đã dọn. Dữ liệu môi trường local chính không bị tác động. Bản environment đã import vào ứng dụng Postman có thể vẫn tồn tại, nhưng cần môi trường mới và ID/token mới để gửi request tiếp.

Sau đó người dùng yêu cầu giữ môi trường để test tiếp: đã tạo lại database, tài khoản, hồ sơ/đơn thuốc/hóa đơn mẫu, giữ stack chạy và xuất lại file environment cùng tên. Dữ liệu/credential mới thay thế phiên đã dọn. Lượt chuẩn bị mới đạt **9/9 E2E**, đăng nhập **5/5 vai trò**, kiểm tra đọc hồ sơ/lịch/hồ sơ y khoa/hóa đơn/kho đều **HTTP 200**, slot được xuất còn khả dụng và AI/RAG sẵn sàng. Artifact mới của bước chuẩn bị nằm tại `frontend/e2e-artifacts/dermai-e2e-postman-20261109/`; các báo cáo Newman cũ đã xóa không được phục hồi.

Dùng `postman/start-test-environment.ps1` để mở lại/refresh environment, hoặc thêm `-Stop` để dừng dịch vụ và **giữ dữ liệu**. Xem [hướng dẫn hiện tại](../postman/README.md).

Collection là danh mục API với các nhánh trạng thái khác nhau. Chạy theo nhóm và chọn ID/trạng thái phù hợp cho từng nhánh. Khi token hết hạn, chạy lại login từng vai trò. Upload cần chọn file và bật `run_file_uploads=true`; fixture avatar đã kiểm tra là JPEG 131 KB. Đọc thêm [hướng dẫn Postman](../postman/README.md).
