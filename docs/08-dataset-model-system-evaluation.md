# Dataset, đánh giá mô hình và đánh giá hệ thống

> Tài liệu này là nội dung có thể đưa vào chương thực nghiệm của báo cáo DermAI Clinic.
> Kết quả được trích từ checkpoint `efficientnet_b0-20260728T185742Z`; đây là mô hình
> hỗ trợ sàng lọc/chuẩn bị thông tin đặt lịch, **không phải công cụ chẩn đoán lâm sàng**.

## 1. Dataset và quy trình chuẩn bị dữ liệu

### 1.1. Nguồn dữ liệu và các lớp dự đoán

Hệ thống phân loại một ảnh vào một trong 8 nhóm: `Acne`, `Candidiasis`, `Eczema`,
`Lupus`, `Psoriasis`, `SkinCancer`, `Tinea` và `Warts`. Đây là bài toán phân loại
đa lớp, single-label; vì vậy kết quả chỉ là gợi ý trong tập nhãn đã học và không
được diễn giải là chẩn đoán bệnh.

Hai nguồn dữ liệu được dùng trong nghiên cứu:

| Nguồn | Mục đích | Tình trạng nguồn/giấy phép |
|---|---|---|
| `SkinDisease/` cục bộ | Nguồn chính để huấn luyện và test cố định 8 lớp | Nguồn gốc, giấy phép, đơn vị bệnh nhân và metadata chưa xác minh được; không công bố ảnh hoặc dùng để tuyên bố hiệu năng lâm sàng. |
| [SCIN 1.0.0](https://github.com/google-research-datasets/scin) | Bổ sung dữ liệu train và tạo external test | Dùng theo [SCIN Data Use License](https://github.com/google-research-datasets/scin/blob/main/LICENSE); có attribution, không tái nhận dạng/liên kết người đóng góp. |

SCIN chỉ nhận các nhãn có trọng số chẩn đoán đứng đầu từ 0,50 trở lên và ánh xạ hẹp
vào 7 lớp: Acne, Candidiasis, Eczema, Lupus da, Psoriasis, Tinea và Warts.
`SkinCancer` không được bổ sung từ SCIN do số nhãn hồi cứu quá ít. Sau xác thực,
SCIN có 1.217 ảnh hợp lệ: 977 ảnh ở train pool và 240 ảnh external test.

### 1.2. Làm sạch và kiểm soát leakage

Mỗi ảnh được Pillow kiểm tra khả năng đọc và tính SHA-256. Pipeline tự động loại:

- 20 file thuộc 9 nhóm có cùng nội dung nhưng nhãn khác nhau;
- 159 bản sao chính xác trong train;
- 34 ảnh train trùng chính xác với test;
- 2 bản sao chính xác trong SCIN; ưu tiên giữ ảnh external test.

Với SCIN, split được thực hiện **theo `case_id` trước khi tải ảnh**; toàn bộ ảnh của
một ca chỉ thuộc train hoặc external test. Với `SkinDisease` gốc không có patient ID/case ID
đã xác minh. Do đó, pipeline chỉ có thể chống exact-duplicate và giữ các ảnh trong cùng thư
mục con ở cùng nhóm khi metadata cấu trúc thư mục có mặt; **không được tuyên bố đây là
patient-level split cho nguồn này**. Trước khi triển khai rộng hơn, nhóm phải có manifest
`image_id, patient_id/case_id, source, label, split` và split theo `patient_id`/`case_id`.

### 1.3. Chia train, validation và test

Test gốc được giữ cố định, không dùng chọn tham số. Phần train sạch được chia stratified,
seed 42, thành train 85% và validation 15%; checkpoint được chọn theo Macro F1 trên validation.

| Tập | Acne | Candidiasis | Eczema | Lupus | Psoriasis | SkinCancer | Tinea | Warts | Tổng |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | 564 | 207 | 1.341 | 269 | 763 | 575 | 842 | 492 | 5.053 |
| Validation | 99 | 36 | 239 | 47 | 135 | 102 | 149 | 87 | 894 |
| Fixed test | 65 | 27 | 111 | 34 | 88 | 77 | 98 | 64 | 564 |
| SCIN external test | 19 | 1 | 156 | 4 | 22 | 0 | 31 | 7 | 240 |

External test SCIN được giữ hoàn toàn ngoài train/validation và case-disjoint, nhưng lệch lớp
mạnh (đặc biệt chỉ có 1 Candida, 4 Lupus, không có SkinCancer). Vì thế chỉ dùng nó để đánh giá
khả năng tổng quát hóa ban đầu, không suy diễn hiệu năng riêng từng lớp thiếu mẫu.

### 1.4. Tiền xử lý và augmentation

Ảnh được chuyển RGB. Train áp dụng `Resize(256)` → `RandomResizedCrop(224, scale=0,8–1,0)`
→ lật ngang ngẫu nhiên → xoay ngẫu nhiên ±12° → `ColorJitter(0,15; 0,15; 0,15; 0,05)`
→ chuẩn hóa ImageNet. Validation, fixed test và external test chỉ dùng `Resize(256)` →
`CenterCrop(224)` → chuẩn hóa ImageNet; không augmentation trên các tập đánh giá.

## 2. Đánh giá ở mức mô hình

### 2.1. Thiết lập thí nghiệm

Model là EfficientNet-B0 khởi tạo ImageNet và fine-tune toàn bộ. Huấn luyện 20 epoch,
batch size 32, AdamW (`lr=3e-4`, `weight_decay=1e-4`), class-weighted cross entropy,
CosineAnnealingLR, mixed precision và seed 42. Best checkpoint là epoch 18, đạt Accuracy
validation 78,86% và Macro F1 validation 77,40%.

Các chỉ số được báo cáo gồm Accuracy, Top-3 Accuracy, Precision, Recall, F1-score theo từng
lớp, Macro F1 và Weighted F1. Macro F1 quan trọng vì dữ liệu mất cân bằng: mỗi lớp có trọng số
như nhau; Weighted F1 phản ánh hiệu năng theo số lượng mẫu thực tế.

### 2.2. So sánh baseline và model được chọn

| Tập đánh giá | Model | Accuracy | Macro F1 | Weighted F1 | Top-3 Accuracy |
|---|---|---:|---:|---:|---:|
| Fixed test, 564 ảnh | Baseline EfficientNet-B0 | 76,60% | 75,27% | 76,34% | 95,21% |
| Fixed test, 564 ảnh | EfficientNet-B0 + SCIN | **78,90%** | **78,31%** | **78,58%** | 93,62% |
| SCIN external, 240 ảnh | Baseline EfficientNet-B0 | 22,50% | 22,68% | 24,07% | 38,75% |
| SCIN external, 240 ảnh | EfficientNet-B0 + SCIN | **67,92%** | **41,57%** | **65,94%** | **92,92%** |

Model mới cải thiện 2,30 điểm % Accuracy và 3,04 điểm % Macro F1 trên fixed test;
hiệu năng trên SCIN external tăng đáng kể. Đổi lại Top-3 trên fixed test giảm 1,59 điểm %,
nên không chỉ báo cáo các chỉ số tăng.

### 2.3. Kết quả chi tiết trên fixed test

| Lớp | Precision | Recall | F1 | Số ảnh test |
|---|---:|---:|---:|---:|
| Acne | 85,07% | 87,69% | 86,36% | 65 |
| Candidiasis | 95,24% | 74,07% | 83,33% | 27 |
| Eczema | 75,21% | 79,28% | 77,19% | 111 |
| Lupus | 94,12% | 47,06% | 62,75% | 34 |
| Psoriasis | 72,53% | 75,00% | 73,74% | 88 |
| SkinCancer | 76,92% | 90,91% | 83,33% | 77 |
| Tinea | 82,56% | 72,45% | 77,17% | 98 |
| Warts | 77,03% | 89,06% | 82,61% | 64 |
| **Tổng hợp** | — | — | **Macro F1 78,31%** | **564** |

Confusion matrix và classification report được lưu tại
`ai-service/models/test_confusion_matrix.png`, `test_confusion_matrix.json` và
`test_classification_report.json`. Ba nhầm lẫn nhiều nhất là Tinea→Eczema (13),
Lupus→Psoriasis (8), Psoriasis→Eczema (8). Recall Lupus chỉ 47,06%; vì vậy UI không
được dùng kết quả âm tính để loại trừ lupus.

### 2.4. Độ tin cậy, an toàn và giới hạn

| Tập | Accuracy | ECE | Brier | NLL | Lỗi confidence ≥ 0,90 |
|---|---:|---:|---:|---:|---:|
| Fixed test | 78,90% | 0,1061 | 0,3222 | 0,8385 | 38 |
| SCIN external | 67,92% | 0,1902 | 0,4822 | 1,2197 | 22 |

Softmax hiện quá tự tin. Ngưỡng `uncertain=0,55` vẫn chấp nhận 98/119 lỗi fixed test
và 62/77 lỗi external. Sáu ảnh probe phi lâm sàng cũng không bị từ chối (0/6), nên đây là
**giới hạn đã biết**, không phải cơ chế phát hiện OOD đáng tin cậy. Bởi vậy kết quả UI chỉ hiển
thị Top-3, cờ không chắc chắn và khuyến nghị đặt lịch; không tự chẩn đoán hoặc kê đơn.

Độ trễ local cho một ảnh đã decode: CPU p50/p95 92,09/98,90 ms và CUDA p50/p95
56,87/61,51 ms cho `app.predict` kèm Grad-CAM. Số đo này chưa bao gồm upload HTTP,
decode ảnh, RAG và frontend.

## 3. Đánh giá ở mức hệ thống

### 3.1. Tiêu chí và test end-to-end

Đánh giá hệ thống không dùng Accuracy của model mà kiểm tra toàn bộ quy trình nghiệp vụ,
phân quyền, tính toàn vẹn dữ liệu và phản hồi người dùng. Lượt chạy E2E gần nhất trên Docker
Compose cô lập với PostgreSQL 16 cho kết quả **5/5 PASS, 0 fail, 0 skip trong 38,798 giây**.

| Mã E2E | Nghiệp vụ được kiểm tra | Kết quả quan sát |
|---|---|---|
| E2E-BOOK-001 | Patient chọn bác sĩ/slot, giữ chỗ và xác nhận | Tạo hold rồi lịch `ASSIGNED`; phí khám được snapshot. |
| E2E-BOOK-002 | Hai Patient cùng giữ một slot | Đúng một request thành công (201), request còn lại conflict (409), chỉ một lịch tồn tại. |
| E2E-FLOW-001 | Vòng đời khám | Đặt lịch → lễ tân xác nhận/check-in → bác sĩ hoàn tất hồ sơ → Patient review. |
| E2E-AI-001 | Luồng AI có kiểm soát | Upload → Top-3/Grad-CAM → lưu assessment → Patient tự bật chia sẻ khi gắn với lịch. |
| E2E-CHAT-001 | Handoff hỗ trợ | Trợ lý chuyển yêu cầu cho lễ tân; lễ tân nhận/ phản hồi và Patient nhận realtime. |

### 3.2. Luồng nghiệp vụ bám sát phòng khám

```text
Patient tải ảnh + khai báo triệu chứng
        ↓
AI trả Top-3 / confidence / cảnh báo (chỉ tham khảo)
        ↓
Patient chủ động lưu và chia sẻ assessment khi đặt lịch
        ↓
Lễ tân xác nhận, check-in và điều phối lịch
        ↓
Bác sĩ phụ trách xem ảnh AI đã được chia sẻ + tiền sử
        ↓
Bác sĩ khám trực tiếp, ghi hồ sơ và đưa chẩn đoán/đơn cuối cùng
```

Các ràng buộc nghiệp vụ chính đã được test gồm: không trùng slot khi request đồng thời,
hold hết hạn giải phóng slot, giá khám được chốt tại thời điểm đặt, Patient chỉ truy cập dữ
liệu của mình, Doctor chỉ đọc assessment khi Patient chia sẻ và có quan hệ appointment, AI
không tự ghi vào chẩn đoán cuối hoặc đơn thuốc. Những ràng buộc này quan trọng hơn việc thêm
chức năng trang trí vì phản ánh luồng vận hành thật của phòng khám.

### 3.3. Bằng chứng, tái lập và việc tiếp theo

- Artifact model: `ai-service/reports/ai_evidence/`, gồm checksum checkpoint, calibration,
  per-image errors bằng SHA-256, latency, OOD probes và Grad-CAM metadata.
- Bằng chứng hệ thống: `docs/test-results.json`, `docs/test-evidence.md` và các E2E trong
  `frontend/e2e/`. Chỉ case có evidence trực tiếp mới ghi PASS.
- Cần bổ sung trước khi phát biểu kết quả rộng hơn: xác minh nguồn/giấy phép `SkinDisease`,
  patient-level manifest, near-duplicate, nhiều random seed/khoảng tin cậy, external set cân
  bằng được chuyên gia xác nhận, OOD lâm sàng có nhãn và khảo sát usability với người dùng
  mục tiêu.

## 4. Cách tái lập

```powershell
python ai-service\scripts\prepare_scin.py --metadata ai-service\data-sources\scin --output SkinDisease\scin-v1 --minimum-weight 0.5 --external-ratio 0.2 --seed 42
python ai-service\training\train.py --data SkinDisease --extra-data SkinDisease\scin-v1 --model efficientnet_b0 --epochs 20 --batch-size 32 --seed 42 --output ai-service\candidates\scin_v1
python ai-service\training\evaluate_evidence.py --checkpoint ai-service\models\best_model.pth --expected-sha256 914f83a85c4dbff06424e0a48f1121950f10e3c0ce8d5a9f68369b38106cc3df --data SkinDisease --external-data SkinDisease\scin-v1 --output ai-service\reports\ai_evidence --latency-devices cpu cuda
```

Xem thêm [Model card](model-card-scin-v1.md), [SRS](01-srs.md) và
[hướng dẫn E2E](../frontend/e2e/README.md).
