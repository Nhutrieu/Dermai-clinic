# Model Card — DermAI Image Classifier with SCIN

## Trạng thái

| Thuộc tính | Giá trị |
|---|---|
| Trạng thái | Thử nghiệm phục vụ đồ án, chưa được thẩm định lâm sàng |
| Kiến trúc | EfficientNet-B0, fine-tune toàn bộ từ trọng số ImageNet |
| Model đang chạy | `efficientnet_b0-20260728T185742Z` |
| Checkpoint | `ai-service/models/best_model.pth` |
| SHA-256 | `914f83a85c4dbff06424e0a48f1121950f10e3c0ce8d5a9f68369b86ea48796` |
| Số lớp | 8 |
| Ngưỡng `uncertain` | Top-1 confidence dưới 0,55 |

Model chỉ hỗ trợ bệnh nhân kiểm tra ảnh da sơ bộ và chuẩn bị thông tin đặt lịch. Kết quả
không phải chẩn đoán, không được dùng để loại trừ bệnh và không thay thế bác sĩ da liễu.

## Nhãn đầu ra

`Acne`, `Candidiasis`, `Eczema`, `Lupus`, `Psoriasis`, `SkinCancer`, `Tinea`, `Warts`.

`SkinCancer` là nhóm rộng, không xác định subtype. `Lupus` chỉ là nhãn hình ảnh da, không đủ
để kết luận lupus hệ thống. Model single-label luôn buộc chọn trong tám nhóm, kể cả ảnh ngoài
phạm vi; UI phải giữ Top-3, cờ `uncertain` và hướng dẫn đi khám.

## Dữ liệu

### Dataset gốc

`SkinDisease/` có 5.178 ảnh train và 569 ảnh test thô. Nguồn, giấy phép, đơn vị bệnh nhân và
tính đại diện cho người Việt Nam chưa được xác minh. Không đưa ảnh lên GitHub và không dùng
kết quả để tuyên bố hiệu năng lâm sàng. Pipeline giữ test cố định, tự loại xung đột nhãn,
exact duplicate và bản sao train–test khỏi phía train.

### SCIN 1.0.0

SCIN gồm ảnh do người trưởng thành tại Hoa Kỳ tự nguyện đóng góp có đồng thuận. Một đến ba
bác sĩ da liễu gán chẩn đoán phân biệt hồi cứu và độ tin cậy. Dữ liệu dùng theo
[SCIN Data Use License](https://github.com/google-research-datasets/scin/blob/main/LICENSE):
phải ghi nguồn khi chia sẻ và cấm tái nhận dạng hoặc liên kết người đóng góp.

Quy tắc chọn của DermAI:

- nhãn đứng đầu có trọng số tối thiểu 0,50;
- ánh xạ hẹp: Acne, Candida/Candida intertrigo, Eczema, Cutaneous lupus, Psoriasis, Tinea
  và Verruca vulgaris;
- không dùng SCIN cho `SkinCancer` vì dữ liệu quá ít;
- tách theo `case_id`, toàn bộ ảnh một ca nằm cùng split;
- giữ trước 20% ca làm external test;
- xác thực Pillow/SHA-256 và loại exact duplicate.

Kết quả: 1.217 ảnh hợp lệ, gồm 977 ảnh train và 240 ảnh external test. Hai ảnh trùng bị loại;
một object nguồn trả 404. External test lệch mạnh: Eczema 156, Tinea 31, Psoriasis 22,
Acne 19, Warts 7, Lupus 4, Candidiasis 1 và SkinCancer 0.

Nguồn: [SCIN repository](https://github.com/google-research-datasets/scin) và bài báo
[Creating an Empirical Dermatology Dataset Through Crowdsourcing With Web Search Advertisements](https://doi.org/10.1001/jamanetworkopen.2024.46615).

### Sau làm sạch và chia tập

| Split | Số ảnh |
|---|---:|
| Raw train gộp | 6.155 |
| Train sạch | 5.053 |
| Validation | 894 |
| Test gốc cố định | 564 |
| SCIN external test | 240 |

## Cấu hình huấn luyện

- RGB 224×224; augmentation chỉ áp dụng cho train; normalize ImageNet.
- 20 epoch, batch 32, seed 42, mixed precision trên RTX 4050 Laptop GPU.
- AdamW, learning rate `3e-4`, weight decay `1e-4`.
- Class-weighted Cross Entropy và CosineAnnealingLR.
- Chọn checkpoint theo validation Macro F1; best epoch 18.
- Best validation Accuracy 78,86%; Macro F1 77,40%.

## Test gốc cố định

| Metric | Baseline | Model mới | Chênh lệch |
|---|---:|---:|---:|
| Accuracy | 76,60% | 78,90% | +2,30 điểm % |
| Macro F1 | 75,27% | 78,31% | +3,04 điểm % |
| Weighted F1 | 76,34% | 78,58% | +2,24 điểm % |
| Top-3 Accuracy | 95,21% | 93,62% | -1,59 điểm % |

| Lớp | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| Acne | 85,07% | 87,69% | 86,36% | 65 |
| Candidiasis | 95,24% | 74,07% | 83,33% | 27 |
| Eczema | 75,21% | 79,28% | 77,19% | 111 |
| Lupus | 94,12% | 47,06% | 62,75% | 34 |
| Psoriasis | 72,53% | 75,00% | 73,74% | 88 |
| SkinCancer | 76,92% | 90,91% | 83,33% | 77 |
| Tinea | 82,56% | 72,45% | 77,17% | 98 |
| Warts | 77,03% | 89,06% | 82,61% | 64 |

Lupus vẫn có recall thấp; kết quả âm tính không được dùng để loại trừ lupus. Top-3 trên test
gốc giảm nhẹ và phải được báo cáo cùng các chỉ số tăng.

## SCIN external test

Macro F1 được tính trên bảy lớp có support; subset không có SkinCancer.

| Metric | Baseline | Model mới | Chênh lệch |
|---|---:|---:|---:|
| Accuracy | 22,50% | 67,92% | +45,42 điểm % |
| Macro F1 | 22,68% | 41,57% | +18,89 điểm % |
| Weighted F1 | 24,07% | 65,94% | +41,87 điểm % |
| Top-3 Accuracy | 38,75% | 92,92% | +54,17 điểm % |

Baseline bị domain shift mạnh và dữ liệu bổ sung giúp đáng kể. Tuy nhiên Tinea external recall
chỉ 12,90%; Lupus, Candida và Warts có quá ít ca. Cần external test cân bằng, được bác sĩ xác
nhận và đại diện bệnh nhân Việt Nam trước mọi tuyên bố rộng hơn.

## Runtime và giới hạn

API nhận JPEG/PNG/WebP tối đa 10 MB và trả Top-1, Top-3, confidence, Grad-CAM,
`model_version`, `uncertain`, disclaimer và tham khảo RAG. Confidence là softmax trong tám
nhãn, không phải xác suất lâm sàng.

Sau inference, frontend lưu metadata và ảnh gốc trong Patient Service. Patient có
quyền đọc/xóa; Doctor chỉ đọc khi Patient đã bật chia sẻ và Doctor phụ trách đúng
appointment. Endpoint ảnh dùng `Cache-Control: no-store`. Grad-CAM chỉ có trong
response hiện tại và không được lưu. Ảnh không được gửi sang Gemini, tự chép vào
chẩn đoán cuối hoặc ghi vào log.

Không được dùng để tự chẩn đoán, kê đơn, loại trừ ung thư/lupus, trì hoãn khám/cấp cứu hoặc
tái nhận dạng người đóng góp. Grad-CAM không chứng minh quan hệ nhân quả. Model còn rủi ro
bias theo màu da, tuổi, giới, camera, ánh sáng, nền ảnh và nguồn thu thập.

## Tái lập và rollback

```powershell
python ai-service\scripts\prepare_scin.py --metadata ai-service\data-sources\scin --output SkinDisease\scin-v1 --minimum-weight 0.5 --external-ratio 0.2 --seed 42
python ai-service\training\train.py --data SkinDisease --extra-data SkinDisease\scin-v1 --model efficientnet_b0 --epochs 20 --batch-size 32 --seed 42 --output ai-service\candidates\scin_v1
```

Baseline rollback nằm tại
`ai-service/models/archive/efficientnet_b0-20260728T110848Z/best_model.pth`, SHA-256
`66493a9d23b781c88257a579196a6ab0999226eca751f0276291ce2ac14a4a2c`.

## Việc còn thiếu

- Bác sĩ/giảng viên xác nhận class map và error analysis.
- Bổ sung external test cân bằng, nhất là Tinea, Lupus, Candida, Warts và SkinCancer.
- Đánh giá calibration/ECE, nhiều seed, khoảng tin cậy và near-duplicate.
- Đánh giá ảnh ngoài phân phối và cơ chế từ chối thay vì buộc chọn một trong tám lớp.
- Xác định retention, xóa tự động và quota dung lượng cho ảnh assessment lưu ở
  PostgreSQL trước khi triển khai công khai.
- Không đưa checkpoint, ảnh y khoa, metadata SCIN hoặc PII lên GitHub.
