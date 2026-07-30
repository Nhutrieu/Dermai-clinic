# Model Card — DermAI Image Classifier

> Bản model đang chạy sau khi bổ sung SCIN được mô tả đầy đủ tại
> [`model-card-scin-v1.md`](model-card-scin-v1.md). Phần dưới đây được giữ như hồ sơ baseline.

## 1. Trạng thái tài liệu

| Thuộc tính | Giá trị hiện tại |
|---|---|
| Trạng thái model | **Thử nghiệm nội bộ, chưa dùng lâm sàng** |
| Checkpoint cục bộ | `ai-service/models/best_model.pth` (16,4 MB) |
| Model version | `efficientnet_b0-20260728T110848Z` |
| Dataset cục bộ | `SkinDisease/`, không đưa lên Git |
| Test độc lập đã làm sạch | 564 ảnh |
| Accuracy / Macro F1 | 76,60% / 75,27% |
| Kiến trúc baseline | EfficientNet-B0 |
| Kiến trúc có thể so sánh | ResNet50, ConvNeXt Tiny |
| Số lớp code hiện hỗ trợ | 8 |
| Ngưỡng `uncertain` mặc định | Top-1 confidence < 0,55 |

Kết quả trong tài liệu được tạo ngày 28/07/2026 từ seed 42 và checkpoint có
SHA-256 `66493a9d23b781c88257a579196a6ab0999226eca751f0276291ce2ac14a4a2c`.
Đây là kết quả đồ án thử nghiệm, không phải chứng nhận hiệu năng lâm sàng.

## 2. Mục đích sử dụng

Model được thiết kế để bệnh nhân đã đăng nhập **kiểm tra ảnh da sơ bộ** trước khi
đặt lịch trong DermAI Clinic. Output gồm Top-3 nhãn, confidence, cảnh báo không
chắc chắn và Grad-CAM. Kết quả giúp bệnh nhân mô tả nhu cầu khám, không phải chẩn
đoán. Bác sĩ không chạy model trong dashboard và phải kết luận độc lập dựa trên
khám trực tiếp, triệu chứng, tiền sử và xét nghiệm cần thiết.

Model có thể được dùng trong đồ án để:

- minh họa quy trình Computer Vision trong phòng khám da liễu;
- giúp bệnh nhân diễn đạt lý do khám và quyết định đi khám phù hợp;
- nghiên cứu error analysis và khả năng giải thích bằng Grad-CAM;
- so sánh kiến trúc trong cùng điều kiện dữ liệu/huấn luyện.

## 3. Không được sử dụng cho

- Tự chẩn đoán hoặc thay tư vấn của bác sĩ.
- Kê đơn, nêu liều thuốc hoặc tự tạo kế hoạch điều trị.
- Loại trừ ung thư hay trì hoãn khám/cấp cứu dựa trên kết quả âm tính.
- Chẩn đoán bệnh ngoài tám nhóm trong class map.
- Suy luận trên ảnh không phải tổn thương da hoặc ảnh chất lượng không đủ.
- Triển khai như thiết bị y tế đã được chứng nhận.

## 4. Nhãn đầu ra

```text
Acne
Candidiasis
Eczema
Lupus
Psoriasis
SkinCancer
Tinea
Warts
```

`SkinCancer` là nhãn nhóm rộng và không xác định subtype. `Lupus` chỉ phản ánh
nhãn hình ảnh trong dataset, không đủ để chẩn đoán bệnh hệ thống. Tên nhãn cần
được bác sĩ/giảng viên chuyên môn xác nhận trước khi đưa lên UI tiếng Việt.

## 5. Dữ liệu

Dataset cục bộ có 5.747 ảnh thô thuộc tám lớp mục tiêu: 5.178 ảnh trong thư mục
train và 569 ảnh trong test. Validator SHA-256 ghi nhận 0 ảnh hỏng, 189 nhóm
trùng, 38 nhóm trùng xuyên train/test và 9 nhóm ảnh giống nhau nhưng khác nhãn.
Pipeline không xóa dữ liệu gốc mà tự động:

- loại 20 file thuộc 9 nhóm xung đột nhãn;
- loại 159 bản sao nội bộ;
- loại 34 ảnh train bị trùng với test;
- chia phần còn lại thành 4.224 train, 746 validation và 564 test sạch.

Thông tin vẫn chưa xác nhận được:

- nguồn và giấy phép;
- số ảnh theo lớp/split;
- đơn vị split là ảnh hay bệnh nhân;
- phân bố màu da, tuổi, giới, địa lý, thiết bị và điều kiện ánh sáng;
- chất lượng nhãn và mức đồng thuận giữa người gán nhãn;
- mức đại diện cho bệnh nhân Việt Nam.

Validator hiện phát hiện exact duplicate. Trước khi tuyên bố khả năng tổng quát
hóa vẫn phải kiểm tra near-duplicate, PII và split theo bệnh nhân/nguồn nếu có
metadata. Nguồn và giấy phép dataset phải được bổ sung trước khi phát hành.

## 6. Cấu hình huấn luyện đã chạy

- Pretrained ImageNet.
- Input RGB 224×224 sau resize/crop.
- Normalize ImageNet.
- EfficientNet-B0 pretrained ImageNet, fine-tune toàn bộ model.
- 20 epoch, batch size 32, seed 42, mixed precision trên RTX 4050 Laptop 6 GB.
- AdamW, learning rate `3e-4`, weight decay `1e-4`, class-weighted Cross Entropy.
- Cosine annealing; checkpoint theo validation Macro F1; patience 5.
- Train dùng augmentation; validation/test chỉ resize, center crop và normalize.

Checkpoint tốt nhất đạt validation Accuracy 79,76% và Macro F1 78,58% tại
epoch 17. Metric test chỉ được tính sau khi chọn checkpoint này.

## 7. Kết quả test độc lập

| Metric | Kết quả |
|---|---:|
| Accuracy | 76,60% |
| Top-3 Accuracy | 95,21% |
| Macro F1 | 75,27% |
| Weighted F1 | 76,34% |

| Lớp | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| Acne | 78,87% | 86,15% | 82,35% | 65 |
| Candidiasis | 82,61% | 70,37% | 76,00% | 27 |
| Eczema | 74,59% | 81,98% | 78,11% | 111 |
| Lupus | 83,33% | 44,12% | 57,69% | 34 |
| Psoriasis | 72,63% | 78,41% | 75,41% | 88 |
| SkinCancer | 86,36% | 74,03% | 79,72% | 77 |
| Tinea | 70,19% | 74,49% | 72,28% | 98 |
| Warts | 80,00% | 81,25% | 80,62% | 64 |

Lupus có recall thấp nhất (44,12%); không được dùng kết quả âm tính để loại trừ
lupus. Confusion matrix và báo cáo chi tiết nằm trong `ai-service/models/`.

### Đánh giá còn thiếu trước phát hành

| Nhóm | Artifact cần có |
|---|---|
| Hiệu năng phân loại | Đã có metric cơ bản; cần lặp nhiều seed và khoảng tin cậy |
| Sai nhầm | Đã có confusion matrix; cần error analysis bởi chuyên gia |
| Độ tin cậy | Calibration/ECE hoặc reliability diagram; đánh giá threshold uncertain |
| Tổng quát hóa | Test độc lập; subgroup theo metadata sẵn có; ảnh ngoài phân phối |
| Hệ thống | Latency CPU/GPU, RAM/VRAM, model size, throughput |
| Giải thích | Grad-CAM mẫu đúng/sai và đánh giá shortcut nền ảnh |
| Tái lập | Data version, seed, code commit, config, class map, checksum checkpoint |

Không đặt ngưỡng metric phát hành tùy ý sau khi nhìn test. Tiêu chí phải được
thống nhất trước, phù hợp mục tiêu đồ án và được trình bày cùng giới hạn.

## 8. Đầu vào và đầu ra runtime

### Đầu vào

- MIME: `image/jpeg`, `image/png`, `image/webp`.
- Dung lượng tối đa: 10 MB.
- File phải giải mã được bằng Pillow.
- Ảnh được chuyển RGB; resize 256; center crop 224; normalize ImageNet.

### Đầu ra

- `disease`: nhãn Top-1.
- `confidence`: softmax score Top-1.
- `top3`: tối đa ba nhãn/score.
- `gradcam_image`: PNG data URL base64.
- `model_version`: phiên bản từ checkpoint.
- `uncertain`: cờ theo ngưỡng.
- `disclaimer`: giới hạn sử dụng.

Confidence là score của model trong class set, không phải xác suất lâm sàng
người bệnh mắc bệnh.

## 9. Rủi ro và giới hạn

- Domain shift do camera, ánh sáng, độ phân giải, góc chụp và xử lý ảnh.
- Mất cân bằng lớp hoặc nhãn sai.
- Một bệnh nhân có nhiều bệnh/biểu hiện nhưng model single-label chỉ trả một
  phân phối trên tám lớp.
- Shortcut từ nền, thước đo, watermark, màu da hoặc quy trình thu thập.
- Thiếu nhóm bệnh khiến model buộc chọn lớp gần nhất.
- Bias do dữ liệu không đại diện màu da/dân số Việt Nam.
- Grad-CAM tạo cảm giác giải thích quá mức; vùng sáng không chứng minh quan hệ
  nhân quả hay lập luận y khoa.

## 10. Biện pháp giảm thiểu

- Top-3 và `uncertain` thay vì chỉ hiển thị một kết luận chắc chắn.
- Disclaimer cố định, khuyến nghị đi khám và chẩn đoán cuối bắt buộc bởi bác sĩ.
- Không có thao tác tự chép AI sang final diagnosis hoặc đơn thuốc.
- Kiểm tra dữ liệu, group split, error analysis và đánh giá theo subgroup.
- Lưu model version/checksum và hỗ trợ rollback.
- Chỉ chia sẻ tóm tắt khi bệnh nhân chủ động chọn; không lưu ảnh gốc.
- Theo dõi phân phối input, latency, lỗi và drift sau triển khai thử nghiệm.
- Điều hướng đi khám khi ảnh/dấu hiệu nguy hiểm hoặc ngoài phạm vi.

## 11. Checklist phát hành

- [ ] Nguồn, giấy phép và dataset report đầy đủ đã hoàn tất.
- [x] Exact duplicate/leakage được loại tự động trước train và test.
- [x] Metric và confusion matrix được tạo từ checkpoint bàn giao.
- [x] Checkpoint checksum, config, seed và class map được lưu.
- [x] UI Patient hiển thị Top-3, uncertain, Grad-CAM và disclaimer.
- [ ] Bác sĩ xác nhận wording lớp và cảnh báo.
- [x] Upload chỉ dành cho Patient; không lưu ảnh gốc; metadata có chia sẻ và xóa.
- [ ] Test ảnh hỏng, ảnh lớn, ảnh ngoài phân phối và model unavailable.
- [ ] Không có API key, PII hoặc ảnh bệnh nhân thật trong Git/demo.
