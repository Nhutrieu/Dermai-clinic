# AI, Computer Vision và RAG — DermAI Clinic

## 1. Vai trò của AI trong đề tài

AI cho phép bệnh nhân kiểm tra ảnh da sơ bộ và cung cấp kiến thức chăm sóc da.
AI không thay thế bác sĩ, không tự ghi chẩn đoán cuối, không kê đơn và không
dùng confidence để khẳng định người dùng mắc hoặc không mắc bệnh.

Hai luồng AI cần được phân biệt rõ:

1. **Computer Vision + RAG:** `/ai/predict` dùng checkpoint PyTorch để phân loại
   ảnh, trả Top-3/Grad-CAM rồi truy hồi nội dung đúng chương bệnh từ tài liệu cục bộ.
2. **Chat kiến thức:** `/ai/public-chat` dùng Gemini; `/ai/chat` dùng RAG
   extractive local. Gemini public chat hiện không phải RAG và không có citation.
3. **Trợ lý hỗ trợ:** `/ai/support-chat` phân loại ý định bằng policy nội bộ,
   trả FAQ hoặc yêu cầu handoff sang lễ tân.

## 2. Trạng thái triển khai hiện tại

| Thành phần | Trạng thái |
|---|---|
| FastAPI, upload validation | Đã có |
| EfficientNet-B0, ResNet50, ConvNeXt Tiny | Đã có code khởi tạo/huấn luyện/inference |
| Top-3, confidence, uncertain, Grad-CAM | Đã có trong response `/predict` |
| Dataset cục bộ | Có trong `SkinDisease/`; không đưa lên Git |
| Checkpoint `best_model.pth` | Đã huấn luyện cục bộ, AI health `modelReady=true` |
| Metric test gốc cố định (564 ảnh) | Accuracy 78,90%; Macro F1 78,31%; Weighted F1 78,58%; Top-3 93,62% |
| SCIN external test (240 ảnh) | Accuracy 67,92%; Macro F1 41,57%; Weighted F1 65,94%; Top-3 92,92% |
| UI tải ảnh và xem kết quả | Đã tích hợp cho Patient; có Top-3, Grad-CAM, lịch sử và chuyển sang đặt lịch |
| Gemini public chat | Đã nối trang chủ |
| RAG local có citation | Đã index 625 đoạn/330 trang, tự chạy sau prediction và hiển thị trên UI Patient |

Health trả `modelReady` và `ragReady`. Health HTTP 200 không có nghĩa model đã
sẵn sàng; trước demo AI phải kiểm tra hai cờ này.

## 3. Nhãn mục tiêu

Code hiện định nghĩa tám nhóm:

| Nhãn | Diễn giải sử dụng trong hệ thống |
|---|---|
| `Acne` | Mụn trứng cá |
| `Candidiasis` | Nhiễm nấm Candida |
| `Eczema` | Chàm/viêm da dạng eczema |
| `Lupus` | Biểu hiện da liên quan lupus trong phạm vi dữ liệu |
| `Psoriasis` | Vảy nến |
| `SkinCancer` | Nhãn nhóm nguy cơ ung thư da, không xác định subtype |
| `Tinea` | Nấm da/ringworm |
| `Warts` | Mụn cóc |

Tên lớp phản ánh dataset, không phải ontology chẩn đoán hoàn chỉnh. Trước huấn
luyện phải xác nhận nguồn, quyền sử dụng, tiêu chí gán nhãn và mức độ phù hợp với
đối tượng bệnh nhân Việt Nam.

## 4. Chuẩn bị và kiểm tra dữ liệu

Script `ai-service/scripts/validate_dataset.py` hiện:

- đọc cấu trúc `train/<class>` và `test/<class>`;
- xác minh ảnh bằng Pillow;
- tính SHA-256;
- phát hiện file trùng, xung đột nhãn và nhóm trùng xuyên train/test;
- xuất báo cáo JSON và hỗ trợ chế độ `--strict`.

Dataset gốc được kiểm tra ngày 28/07/2026 có 5.747 ảnh, 0 ảnh hỏng, 189 nhóm
trùng, 38 nhóm trùng xuyên split và 9 nhóm xung đột nhãn. Bản model hiện hành
bổ sung SCIN 1.0.0 theo case-level split: 1.217 ảnh hợp lệ, trong đó 977 ảnh dùng
cho train pool và 240 ảnh giữ riêng làm external test. Sau làm sạch, các split
hiện hành là 5.053 train, 894 validation, 564 test gốc cố định và 240 SCIN
external test; pipeline không xóa dataset nguồn.

Trước khi công bố kết quả cần bổ sung:

1. Loại ảnh hỏng, ảnh trùng gần giống và ảnh chứa thông tin nhận dạng.
2. Split theo bệnh nhân/nguồn nếu metadata cho phép, không chỉ split ngẫu nhiên
   theo file.
3. Tạo train/validation/test bất biến; test chỉ dùng một lần khi chọn model xong.
4. Thống kê mất cân bằng, màu da, tuổi, giới, camera, ánh sáng và nền ảnh nếu có.
5. Lưu data version, class map, seed, checksum và quy tắc loại dữ liệu.

Dataset bị loại khỏi Git vì dung lượng và yêu cầu giấy phép. Báo cáo validator,
dataset summary và metric được lưu riêng để kết quả có thể tái lập.

## 5. Huấn luyện

`ai-service/training/train.py` hỗ trợ ba kiến trúc:

- `efficientnet_b0` — baseline mặc định;
- `resnet50` — baseline đối chiếu;
- `convnext_tiny` — challenger khi đủ tài nguyên.

Pipeline hiện dùng pretrained ImageNet, resize 256, random resized crop 224,
horizontal flip, rotation, color jitter, normalize ImageNet, AdamW và Cross
Entropy. Checkpoint tốt nhất được chọn theo validation macro F1.

### 5.1. Model đang chạy sau khi bổ sung SCIN

EfficientNet-B0 được fine-tune toàn bộ trong 20 epoch, batch size 32, seed 42,
class-weighted Cross Entropy, cosine scheduler và AMP trên RTX 4050 Laptop.
Checkpoint epoch 18 được chọn theo validation Macro F1 77,40%; validation
Accuracy là 78,86%.

Trên test gốc cố định 564 ảnh, model đạt Accuracy 78,90%, Macro F1 78,31%,
Weighted F1 78,58% và Top-3 Accuracy 93,62%. Trên SCIN external test 240 ảnh,
model đạt lần lượt 67,92%, 41,57%, 65,94% và 92,92%. Lupus vẫn có recall thấp
trên test gốc; Tinea external recall chỉ 12,90%. Kết quả external chịu mất cân
bằng lớp rất mạnh và chưa đại diện bệnh nhân Việt Nam.

Baseline trước SCIN đạt Accuracy 76,60%, Macro F1 75,27%, Weighted F1 76,34%
và Top-3 95,21%. Các số baseline được giữ trong
[`model-card.md`](model-card.md); báo cáo model hiện hành nằm tại
[`model-card-scin-v1.md`](model-card-scin-v1.md).

## 6. Đánh giá và release gate

Không chọn model chỉ theo accuracy. Báo cáo tối thiểu gồm:

- accuracy và Top-3 accuracy;
- precision, recall, F1 từng lớp;
- macro/weighted F1;
- confusion matrix;
- ROC-AUC one-vs-rest khi hợp lệ;
- calibration/ECE hoặc reliability diagram nếu có thể;
- latency CPU và GPU trên phần cứng được ghi rõ;
- error analysis và đánh giá subgroup khi metadata cho phép.

Artifact hiện có gồm history, dataset summary, classification report, metric và
confusion matrix JSON/PNG. Vẫn cần calibration, nhiều seed, near-duplicate,
subgroup/error analysis và xác minh chuyên môn trước khi phát hành lâm sàng.

## 7. Inference và Grad-CAM

`/ai/predict` chỉ cho role `PATIENT` và nhận multipart field `image`:

1. Chỉ chấp nhận JPEG, PNG, WebP tối đa 10 MB.
2. Xác minh file thật sự giải mã được.
3. RGB → resize 256 → center crop 224 → tensor → normalize ImageNet.
4. Softmax, lấy tối đa ba lớp có score cao nhất.
5. Nếu Top-1 thấp hơn 0,55, đặt `uncertain=true`.
6. Tạo Grad-CAM tại convolution layer cuối và trả PNG base64 data URL.
7. Frontend lưu metadata và ảnh gốc qua Patient Service; Grad-CAM chỉ hiển thị
   trong response hiện tại và không được lưu lâu dài.

Grad-CAM chỉ cho biết vùng ảnh ảnh hưởng đến output. Nó không chứng minh mô hình
lập luận đúng và không phải bằng chứng y khoa. Mọi màn hình phải hiển thị
disclaimer cạnh kết quả.

## 8. Gemini public chat

`/ai/public-chat` gọi Gemini bằng API key ở server. System instruction giới hạn
trợ lý vào tư vấn chăm sóc da, yêu cầu đi khám/cấp cứu khi có dấu hiệu nguy hiểm
và cấm chẩn đoán chắc chắn, kê đơn, liều thuốc.

Hạng mục bắt buộc trước public deployment:

- rate limit theo IP/session và giới hạn chi phí;
- timeout, circuit breaker hoặc fallback rõ ràng;
- không gửi PII, hồ sơ hay ảnh bệnh nhân;
- rotate key từng bị lộ và chỉ lưu trong secret environment;
- lưu telemetry không chứa nội dung nhạy cảm.

## 9. RAG local

Nguồn hiện tại là `SkinDisease/Huong-dan-chan-doan-dieu-tri-Da-lieu.pdf`, gồm
330 trang. Script ingest làm sạch ký tự OCR, chia thành 625 đoạn theo trang, lưu
`chunks.json`, metadata và SHA-256. `RagStore` dựng TF-IDF word unigram/bigram
khi khởi động nên không phải tải thêm model embedding lớn.

Sau prediction, nhãn Top-1 ánh xạ vào các trang điều trị/phòng bệnh tương ứng của
tám nhóm. Retrieval xác minh có bằng chứng trong đúng trang rồi trả một bản tóm
tắt kiểm soát gồm tối đa ba ý xử trí/chăm sóc. Nội dung không có liều hoặc tên
thuốc kê đơn. Nếu thiếu chỉ mục hoặc không đủ bằng chứng, hệ thống fail-closed
với `has_evidence=false`.

Đây là **extractive retrieval**, chưa phải RAG generator đầy đủ. Để nâng cấp:

1. Loại header/footer tốt hơn và nhận diện section tự động.
2. Đánh giá chunk size/overlap thay vì chỉ dùng cấu hình hiện tại.
3. Thêm citation validator và kiểm tra mapping trang bởi bác sĩ/giảng viên.
4. Kiểm thử retrieval hit@k, MRR, citation correctness và relevance.
5. Red-team kê thuốc, prompt injection, thiếu nguồn và nội dung ngoài da liễu.

## 10. Trợ lý hỗ trợ Patient

Trợ lý này là tầng đầu của luồng hỗ trợ Patient. Nó xử lý hướng dẫn đặt lịch,
cách đổi/hủy, tìm bác sĩ, giá khám, hotline, giờ làm, cách dùng AI và cách hiểu
Top-3/Grad-CAM ở mức tham khảo. Câu hỏi da liễu chung được tra cứu bằng RAG local;
thiếu bằng chứng thì fail-closed và đề nghị kết nối lễ tân. Yêu cầu thực hiện
đổi/hủy/đặt hộ, trạng thái lịch cá nhân, tài khoản, phản ánh, dấu hiệu nguy hiểm,
chẩn đoán cá nhân và kê đơn luôn trả `requires_handoff=true`.

Category/handoff là quyết định deterministic trong `support_assistant.py`.
Gemini không nhận câu hỏi gốc; nó chỉ có thể biên tập một câu mẫu đã duyệt từ
category không nhạy cảm. Nếu Gemini lỗi hoặc chưa cấu hình, câu mẫu local vẫn
được trả. Appointment Service lưu nội dung gốc, transcript AI/System, intent và
summary bàn giao trong support chat nội bộ. Service tự chuyển người thật khi
policy bắt buộc, confidence thấp, Patient không hài lòng hoặc hai lượt liên tiếp
không giải quyết được; frontend không hiển thị nút bỏ qua AI. Lễ tân thấy toàn bộ
lịch sử và bản tóm tắt trong cùng conversation, sau đó claim để phản hồi realtime.

Với `DOCTOR_AVAILABILITY`, AI chỉ trích xuất tên bác sĩ/ngày; Appointment Service
đối chiếu Doctor Service và Scheduling Engine trước khi trả khung giờ thật. AI
không tự sinh slot và không thực hiện đặt, đổi, hủy hoặc xác nhận lịch.

## 11. Nguyên tắc riêng tư và an toàn

- Không gửi ảnh/PII bệnh nhân tới Gemini hoặc provider ngoài nếu chưa có consent
  và thiết kế bảo vệ dữ liệu phù hợp.
- Ảnh gốc hiện được lưu dạng BLOB trong Patient Service. Patient có quyền
  đọc/xóa; Doctor chỉ đọc khi Patient đã chia sẻ với đúng appointment mà Doctor
  phụ trách. Endpoint ảnh trả `Cache-Control: no-store`.
- Cần bổ sung chính sách retention, xóa tự động và giám sát dung lượng trước khi
  triển khai công khai.
- Không cho nút tự sao chép output AI thành final diagnosis.
- Bệnh nhân phải chủ động chọn chia sẻ. Ảnh không được chép sang hồ sơ y khoa;
  Doctor chỉ xem qua endpoint chia sẻ có kiểm tra quyền của appointment.
- Bác sĩ không chạy model trong dashboard và luôn ghi kết luận độc lập.
- Ảnh/dấu hiệu nguy hiểm phải được điều hướng khám trực tiếp; kết quả AI âm tính
  không được dùng để trì hoãn chăm sóc.
