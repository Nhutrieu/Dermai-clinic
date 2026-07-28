# AI, Computer Vision và RAG — DermAI Clinic

## 1. Vai trò của AI trong đề tài

AI hỗ trợ phân tích ảnh da liễu và cung cấp kiến thức chăm sóc da. AI không thay
thế bác sĩ, không tự ghi chẩn đoán cuối, không kê đơn và không dùng confidence
để khẳng định người dùng mắc hoặc không mắc bệnh.

Hai luồng AI cần được phân biệt rõ:

1. **Computer Vision:** `/ai/predict`, dùng checkpoint PyTorch để phân loại ảnh,
   trả Top-3 và Grad-CAM.
2. **Chat kiến thức:** `/ai/public-chat` dùng Gemini; `/ai/chat` dùng RAG
   extractive local. Gemini public chat hiện không phải RAG và không có citation.

## 2. Trạng thái triển khai hiện tại

| Thành phần | Trạng thái |
|---|---|
| FastAPI, upload validation | Đã có |
| EfficientNet-B0, ResNet50, ConvNeXt Tiny | Đã có code khởi tạo/huấn luyện/inference |
| Top-3, confidence, uncertain, Grad-CAM | Đã có trong response `/predict` |
| Dataset trong repository | Chưa có |
| Checkpoint `best_model.pth` | Chưa có |
| Metric test độc lập | Chưa có, không được điền số giả |
| UI tải ảnh và xem kết quả | Chưa tích hợp vào frontend chính |
| Gemini public chat | Đã nối trang chủ |
| RAG local có citation | Có code nền, chưa có index và chưa nối frontend |

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
- phát hiện nhóm file trùng xuyên train/test;
- in phân bố số ảnh theo split và lớp.

Trước khi công bố kết quả cần bổ sung:

1. Loại ảnh hỏng, ảnh trùng gần giống và ảnh chứa thông tin nhận dạng.
2. Split theo bệnh nhân/nguồn nếu metadata cho phép, không chỉ split ngẫu nhiên
   theo file.
3. Tạo train/validation/test bất biến; test chỉ dùng một lần khi chọn model xong.
4. Thống kê mất cân bằng, màu da, tuổi, giới, camera, ánh sáng và nền ảnh nếu có.
5. Lưu data version, class map, seed, checksum và quy tắc loại dữ liệu.

Repository hiện không chứa dataset nên không ghi “14.529 ảnh” hoặc số lớp/test
nếu chưa có báo cáo validator tái lập được.

## 5. Huấn luyện

`ai-service/training/train.py` hỗ trợ ba kiến trúc:

- `efficientnet_b0` — baseline mặc định;
- `resnet50` — baseline đối chiếu;
- `convnext_tiny` — challenger khi đủ tài nguyên.

Pipeline hiện dùng pretrained ImageNet, resize 256, random resized crop 224,
horizontal flip, rotation, color jitter, normalize ImageNet, AdamW và Cross
Entropy. Checkpoint tốt nhất được chọn theo validation macro F1.

### 5.1. Điểm cần sửa trước khi huấn luyện chính thức

Script hiện dùng `random_split` từ cùng một `ImageFolder` đã gắn augmentation,
vì vậy validation cũng nhận random crop/flip/jitter. Trước khi tạo metric chính
thức phải:

- tạo dataset/transform validation riêng chỉ resize, center crop và normalize;
- ưu tiên stratified hoặc group split thay vì random split thuần;
- đánh giá trên thư mục `test` độc lập;
- xử lý mất cân bằng bằng class weight hoặc sampler sau khi phân tích dữ liệu;
- thêm early stopping, scheduler và lưu toàn bộ hyperparameter;
- đảm bảo mọi model so sánh dùng cùng split, seed, epoch budget và augmentation.

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

Chỉ phát hành checkpoint khi metric được tính trên test độc lập, inference tái
lập được và model card đã cập nhật. Không hard-code hoặc ước lượng metric.

## 7. Inference và Grad-CAM

`/ai/predict` nhận multipart field `image`:

1. Chỉ chấp nhận JPEG, PNG, WebP tối đa 10 MB.
2. Xác minh file thật sự giải mã được.
3. RGB → resize 256 → center crop 224 → tensor → normalize ImageNet.
4. Softmax, lấy tối đa ba lớp có score cao nhất.
5. Nếu Top-1 thấp hơn 0,55, đặt `uncertain=true`.
6. Tạo Grad-CAM tại convolution layer cuối và trả PNG base64 data URL.

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

`RagStore` hiện đọc `vectors.npy` và `chunks.json`, tạo embedding bằng
`paraphrase-multilingual-MiniLM-L12-v2`, lấy Top-4 và giữ chunk có similarity
từ 0,35. Response ghép tối đa hai đoạn gốc và trả `source`, `page`. Nếu thiếu
index hoặc không đủ bằng chứng, hệ thống fail-closed.

Đây là **extractive retrieval**, chưa phải RAG generator đầy đủ. Để nâng cấp:

1. Trích PDF theo trang; loại header/footer; lưu source, page, section, checksum.
2. Đánh giá chunk size/overlap thay vì cố định một con số chưa kiểm chứng.
3. Thêm citation validator và bảo đảm mọi câu sinh ra được nguồn hỗ trợ.
4. Kiểm thử retrieval hit@k, MRR, citation correctness, faithfulness, relevance.
5. Red-team kê thuốc, prompt injection, thiếu nguồn và nội dung ngoài da liễu.

## 10. Nguyên tắc riêng tư và an toàn

- Không gửi ảnh/PII bệnh nhân tới Gemini hoặc provider ngoài nếu chưa có consent
  và thiết kế bảo vệ dữ liệu phù hợp.
- Không lưu ảnh chẩn đoán vào database/object storage khi chưa có retention và
  access control.
- Không cho nút tự sao chép output AI thành final diagnosis.
- Luôn cho phép bác sĩ bỏ qua, phản hồi sai và ghi kết luận độc lập.
- Ảnh/dấu hiệu nguy hiểm phải được điều hướng khám trực tiếp; kết quả AI âm tính
  không được dùng để trì hoãn chăm sóc.
