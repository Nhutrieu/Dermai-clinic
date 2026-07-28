# Model Card — DermAI Image Classifier

## 1. Trạng thái tài liệu

| Thuộc tính | Giá trị hiện tại |
|---|---|
| Trạng thái model | **Chưa phát hành** |
| Checkpoint trong repository | Chưa có `ai-service/models/best_model.pth` |
| Dataset trong repository | Chưa có |
| Metric chính thức | Chưa có |
| Kiến trúc baseline | EfficientNet-B0 |
| Kiến trúc có thể so sánh | ResNet50, ConvNeXt Tiny |
| Số lớp code hiện hỗ trợ | 8 |
| Ngưỡng `uncertain` mặc định | Top-1 confidence < 0,55 |

Tài liệu này là model card trước phát hành. Không được thêm accuracy, F1, số
lượng ảnh hoặc tuyên bố đại diện dữ liệu nếu không có artifact/báo cáo tái lập.

## 2. Mục đích sử dụng

Model được thiết kế để **hỗ trợ tham khảo** khi bác sĩ phân tích ảnh da liễu
trong DermAI Clinic. Output gồm Top-3 nhãn, confidence, cảnh báo không chắc chắn
và Grad-CAM. Bác sĩ phải kết hợp khám trực tiếp, triệu chứng, tiền sử và xét
nghiệm cần thiết trước khi ghi chẩn đoán cuối.

Model có thể được dùng trong đồ án để:

- minh họa quy trình Computer Vision trong phòng khám da liễu;
- hỗ trợ bác sĩ xem các khả năng cần cân nhắc;
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

Repository hiện không chứa dataset nên chưa xác nhận được:

- nguồn và giấy phép;
- số ảnh theo lớp/split;
- đơn vị split là ảnh hay bệnh nhân;
- phân bố màu da, tuổi, giới, địa lý, thiết bị và điều kiện ánh sáng;
- chất lượng nhãn và mức đồng thuận giữa người gán nhãn;
- mức đại diện cho bệnh nhân Việt Nam.

Trước huấn luyện chính thức phải chạy validator ảnh hỏng và duplicate hash,
kiểm tra near-duplicate/leakage, loại PII, tạo data version và báo cáo phân bố.
Split test phải được khóa trước khi lựa chọn model.

## 6. Huấn luyện dự kiến

- Pretrained ImageNet.
- Input RGB 224×224 sau resize/crop.
- Normalize ImageNet.
- AdamW, Cross Entropy và checkpoint theo validation macro F1.
- So sánh model với cùng split, seed, augmentation, epoch budget và tiêu chí.

Script hiện tại cần tách transform validation khỏi augmentation train và phải
đánh giá thư mục test độc lập trước khi dùng kết quả trong báo cáo.

## 7. Đánh giá bắt buộc trước phát hành

| Nhóm | Artifact cần có |
|---|---|
| Hiệu năng phân loại | Accuracy, Top-3 accuracy, precision/recall/F1 từng lớp, macro/weighted F1 |
| Sai nhầm | Confusion matrix và phân tích cặp lớp thường nhầm |
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
- Disclaimer cố định và review bắt buộc bởi bác sĩ.
- Không có thao tác tự chép AI sang final diagnosis hoặc đơn thuốc.
- Kiểm tra dữ liệu, group split, error analysis và đánh giá theo subgroup.
- Lưu model version/checksum và hỗ trợ rollback.
- Cho bác sĩ báo kết quả sai và thu thập feedback có consent.
- Theo dõi phân phối input, latency, lỗi và drift sau triển khai thử nghiệm.
- Điều hướng đi khám khi ảnh/dấu hiệu nguy hiểm hoặc ngoài phạm vi.

## 11. Checklist phát hành

- [ ] Dataset report và giấy phép đã hoàn tất.
- [ ] Test split độc lập, không leakage.
- [ ] Metric và confusion matrix được tạo từ checkpoint bàn giao.
- [ ] Checkpoint checksum, config, code commit và class map được lưu.
- [ ] UI hiển thị Top-3, uncertain, Grad-CAM và disclaimer.
- [ ] Bác sĩ xác nhận wording lớp và cảnh báo.
- [ ] Quyền upload, consent, retention và xóa ảnh được thiết kế.
- [ ] Test ảnh hỏng, ảnh lớn, ảnh ngoài phân phối và model unavailable.
- [ ] Không có API key, PII hoặc ảnh bệnh nhân thật trong Git/demo.
