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

## 2. Trạng thái triển khai hiện tại

| Thành phần | Trạng thái |
|---|---|
| FastAPI, upload validation | Đã có |
| EfficientNet-B0, ResNet50, ConvNeXt Tiny | Đã có code khởi tạo/huấn luyện/inference |
| Top-3, confidence, uncertain, Grad-CAM | Đã có trong response `/predict` |
| Dataset cục bộ | Có trong `SkinDisease/`; không đưa lên Git |
| Checkpoint `best_model.pth` | Đã huấn luyện cục bộ, AI health `modelReady=true` |
| Metric test độc lập | Accuracy 76,60%; Macro F1 75,27%; Top-3 95,21% |
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

Lần kiểm tra ngày 28/07/2026 trên tám lớp ghi nhận 5.747 ảnh, 0 ảnh hỏng, 189
nhóm trùng, 38 nhóm trùng xuyên split và 9 nhóm xung đột nhãn. Pipeline train
tự loại các nhóm không an toàn, khử trùng và tạo 4.224 train, 746 validation,
564 test mà không sao chép hoặc xóa dataset gốc.

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

### 5.1. Lần huấn luyện baseline hiện tại

EfficientNet-B0 được fine-tune 20 epoch, batch size 32, seed 42, class-weighted
Cross Entropy, cosine scheduler và AMP trên RTX 4050 Laptop. Validation có
transform riêng và split phân tầng theo nhóm SHA-256. Checkpoint epoch 17 được
chọn theo validation Macro F1 78,58%.

Test độc lập 564 ảnh đạt Accuracy 76,60%, Macro F1 75,27%, Weighted F1 76,34%
và Top-3 Accuracy 95,21%. Lupus có recall thấp nhất 44,12%, là giới hạn quan
trọng phải hiển thị trong model card và error analysis.

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
7. Frontend lưu metadata kết quả qua Patient Service; ảnh gốc và Grad-CAM không
   được lưu lâu dài.

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

## 10. Nguyên tắc riêng tư và an toàn

- Không gửi ảnh/PII bệnh nhân tới Gemini hoặc provider ngoài nếu chưa có consent
  và thiết kế bảo vệ dữ liệu phù hợp.
- Không lưu ảnh chẩn đoán vào database/object storage khi chưa có retention và
  access control.
- Không cho nút tự sao chép output AI thành final diagnosis.
- Bệnh nhân phải chủ động chọn chia sẻ; chỉ tóm tắt kết quả được đưa vào lý do
  khám khi đặt lịch, không đưa ảnh gốc sang hồ sơ bác sĩ.
- Bác sĩ không chạy model trong dashboard và luôn ghi kết luận độc lập.
- Ảnh/dấu hiệu nguy hiểm phải được điều hướng khám trực tiếp; kết quả AI âm tính
  không được dùng để trì hoãn chăm sóc.
