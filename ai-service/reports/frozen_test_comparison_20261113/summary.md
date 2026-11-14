# Đối chứng bộ phân loại trên hai tập test lịch sử

Đây là so sánh mới trên danh sách 486 ảnh nguồn cũ và 237 ảnh SCIN đã rà và khóa từ trước. Không train, chọn model, dò trọng số hoặc ngưỡng theo kết quả. Không đổi ứng dụng. Các nguồn đã được khảo sát nên không phải test mù mới độc lập theo bệnh nhân.

## Cùng dữ liệu và điều kiện đánh giá

- Giữ nguyên 15 checkpoint và các đầu G/S được chọn từ validation. Cùng RGB, Resize256, CenterCrop224, chuẩn hóa ImageNet, FP32/eval.
- Đối chứng một kiến trúc lấy trung bình xác suất năm checkpoint rồi argmax; các biến thể E dùng nhãn từng fold và cùng quy tắc biểu quyết bảo vệ SkinCancer. Không gọi các đối chứng kiến trúc này là một checkpoint đơn.
- Mỗi phương án đều phân loại đủ mọi ảnh; không có chất lượng/OOD từ chối, Grad-CAM hoặc HTTP. Điểm này không phải điểm API hay phép đo tốc độ.
- S chỉ ở fold1/2, G chỉ ở fold0/3; bỏ thành phần không fit lại. Dự đoán được khóa trước khi tính chỉ số.

## 486 ảnh test nguồn cũ

| Phương án | Ảnh đúng | Accuracy | Macro F1 cố định 8 lớp | Recall SkinCancer |
|---|---:|---:|---:|---:|
| EfficientNet-B0 · TB xác suất 5 checkpoint | 368/486 | 75,72% | 74,27% | 90,41% |
| ConvNeXt-Tiny · TB xác suất 5 checkpoint | 381/486 | 78,40% | 76,82% | 91,78% |
| ResNet50 · TB xác suất 5 checkpoint | 382/486 | 78,60% | 76,47% | 90,41% |
| E · biểu quyết 5 fold | 392/486 | 80,66% | 79,55% | 91,78% |
| E+S · biểu quyết 5 fold | 393/486 | 80,86% | 79,69% | 91,78% |
| E+G · biểu quyết 5 fold | 392/486 | 80,66% | 79,38% | 91,78% |
| E/G/S · biểu quyết 5 fold | 393/486 | 80,86% | 79,53% | 91,78% |

### Theo bệnh của E/G/S

| Bệnh | Số ảnh | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Acne | 55 | 89,66% | 94,55% | 92,04% |
| Candidiasis | 22 | 92,86% | 59,09% | 72,22% |
| Eczema | 94 | 75,00% | 86,17% | 80,20% |
| Lupus | 31 | 79,17% | 61,29% | 69,09% |
| Psoriasis | 77 | 79,71% | 71,43% | 75,34% |
| SkinCancer | 73 | 83,75% | 91,78% | 87,58% |
| Tinea | 79 | 78,67% | 74,68% | 76,62% |
| Warts | 55 | 81,03% | 85,45% | 83,19% |

## 237 ảnh SCIN giữ lại

| Phương án | Ảnh đúng | Accuracy | Macro F1 cố định 8 lớp | Recall SkinCancer |
|---|---:|---:|---:|---:|
| EfficientNet-B0 · TB xác suất 5 checkpoint | 157/237 | 66,24% | 30,31% | Không có mẫu |
| ConvNeXt-Tiny · TB xác suất 5 checkpoint | 181/237 | 76,37% | 45,59% | Không có mẫu |
| ResNet50 · TB xác suất 5 checkpoint | 170/237 | 71,73% | 31,13% | Không có mẫu |
| E · biểu quyết 5 fold | 180/237 | 75,95% | 43,02% | Không có mẫu |
| E+S · biểu quyết 5 fold | 179/237 | 75,53% | 40,34% | Không có mẫu |
| E+G · biểu quyết 5 fold | 181/237 | 76,37% | 44,20% | Không có mẫu |
| E/G/S · biểu quyết 5 fold | 180/237 | 75,95% | 41,51% | Không có mẫu |

### Theo bệnh của E/G/S

| Bệnh | Số ảnh | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Acne | 19 | 78,26% | 94,74% | 85,71% |
| Candidiasis | 1 | 0,00% | 0,00% | 0,00% |
| Eczema | 154 | 81,98% | 91,56% | 86,50% |
| Lupus | 4 | 25,00% | 25,00% | 25,00% |
| Psoriasis | 22 | 41,67% | 45,45% | 43,48% |
| SkinCancer | 0 | — | — | — |
| Tinea | 30 | 87,50% | 23,33% | 36,84% |
| Warts | 7 | 75,00% | 42,86% | 54,55% |

## Nhận xét và giới hạn

- Test nguồn cũ: E/G/S đạt 393/486 (80,86%), Macro F1 79,53%; cao hơn các đối chứng một kiến trúc về điểm tổng. So với E chỉ tăng ròng một ảnh, Macro F1 giảm khoảng 0,02 điểm phần trăm. E+S có Macro F1 79,69%, cao hơn E/G/S trong nguồn này; không chọn lại cấu hình theo test.
- SCIN: ConvNeXt đạt 76,37% Accuracy / 45,59% Macro F1 tám lớp; E/G/S đạt 75,95% / 41,51%. E/G/S chưa tốt hơn trên mọi nguồn.
- SCIN thiếu SkinCancer, có bốn Lupus và một Candidiasis; Macro F1 bảy lớp có mẫu của E/G/S là 47,44%, không thay điểm tám lớp hoặc so trực tiếp với nguồn đủ tám bệnh.
- E/G/S nhận đúng Lupus 1/4 trên SCIN; ConvNeXt và E nhận đúng 2/4. Specialist chưa tăng ổn định các lớp yếu.
- Khoảng bootstrap ghép cặp 1.000 lượt theo nhóm proxy được lưu trong results.json. Chênh so với ConvNeXt, ResNet và E còn chạm hoặc chứa0; chưa chứng minh cải thiện ổn định ngoài lịch sử. Các nhóm không xác minh đầy đủ bệnh nhân, không tính bất định seed hoặc lựa chọn thích ứng.
- Kiểm tra phụ từng nhánh fold trên cùng ảnh được lưu riêng; không phải năm seed hoặc năm tập test độc lập.

## Dẫn chứng

- `protocol.json`: ảnh, checkpoint, mã và quy tắc được khóa trước chấm.
- `predictions_locked.npz`, `prediction_lock.json`: khóa dự đoán trước tính chỉ số.
- `predictions.jsonl`: từng ảnh, nhãn nguồn và dự đoán của mọi phương án.
- `results.json`: chỉ số, từng fold, từng lớp, confusion matrix và khoảng bootstrap.
- `verification.json`: hash, đối chiếu sklearn và xác nhận nguồn/checkpoint không đổi.
- Nhãn E/G/S khớp cả 604 ảnh được API lịch sử trả nhãn. Đây là kiểm chứng nhất quán, không thay đổi phạm vi đánh giá bộ phân loại.
- 12 kiểm thử quy tắc runtime đạt. PASS không chứng nhận độ chính xác lâm sàng.
