# Khôi phục biểu quyết năm fold — 11/11/2026

Theo yêu cầu mới của nhóm, API trở lại bản **`dermai-eight-esg-v1-20261108`**,
manifest `ai-service/models/research_pipeline/manifest.json`. Không huấn luyện
lại, không thay trọng số hoặc ghép thêm đầu mới. Bản một fold dừng làm mặc định;
cấu hình và kết quả kiểm tra của giai đoạn đó vẫn được giữ làm lịch sử.

## Cách chạy hiện tại

Mỗi ảnh được kiểm chất lượng và OOD, sau đó chạy qua năm bộ model. Mỗi bộ có
EfficientNet-B0, ConvNeXt-Tiny, ResNet50 và đúng chính sách đã chọn trong fold:

| Fold | Thành phần hoạt động |
|---|---|
| 0 | Ensemble E + bộ chọn G |
| 1 | Ensemble E + specialist S |
| 2 | Ensemble E + specialist S |
| 3 | Ensemble E + bộ chọn G |
| 4 | Ensemble E |

Đếm năm nhãn cuối để chọn nhãn phục vụ. Giữ quy tắc cũ: mặt nạ SkinCancer trong
từng fold không đổi; nhãn Cancer của kết quả cuối được bảo vệ theo biểu quyết
tham chiếu B0/ConvNeXt. Khi hòa phiếu, dùng điểm trung bình B0/ConvNeXt, sau đó
thứ tự lớp cố định. Không chọn fold theo ảnh, nguồn dữ liệu hoặc nhãn thật.

API trả tỷ lệ phiếu thật, không đổi giá trị để làm nhãn được chọn có điểm cao
nhất. Nhãn được ưu tiên theo luật bảo vệ hoặc hòa phiếu được gắn cờ chưa chắc
chắn. Mức đồng thuận không phải xác suất mắc bệnh. Grad-CAM minh họa từ B0 fold 0,
không giải thích đầy đủ toàn bộ bộ gộp.

## Những chỉ số nào dùng được?

- **OOF nghiên cứu:** Accuracy 78,95%, Macro F1 77,73%, Recall SkinCancer 88,04%
  trên 5.937 ảnh, mỗi ảnh chấm bằng đúng nhánh không train ảnh đó.
- **Đánh giá hồi cứu của bản biểu quyết:** [báo cáo API ngày 10/11](../ai-service/reports/application_evaluation_20261110/summary.md).
  Trong 486 ảnh, trả nhãn cho 420 ảnh và đúng 341 ảnh: 81,19% trên ảnh được trả
  nhãn; 70,16% trên toàn đầu vào; 66 ảnh bị từ chối. Đây không phải test bệnh nhân
  mới độc lập. Không gán 78,95% OOF cho bản biểu quyết.

## Cấu hình và kiểm tra

Compose và cấu hình chạy trực tiếp mặc định trỏ manifest biểu quyết cũ.
`/health` phải có `aggregation: protected_fold_vote_v1`, `servingFold: null`
và phiên bản `dermai-eight-esg-v1-20261108`.

Script `ai-service/training/verify_restored_fold_vote.py` đối chiếu tám phản hồi
API với phản hồi biểu quyết đã lưu, gồm nhãn, tỷ lệ phiếu, Top-3, trạng thái chưa
chắc chắn và năm nhãn từng fold. Đây là kiểm tra khôi phục, không phải nghiên cứu
độ chính xác mới. [Bằng chứng Docker](../ai-service/reports/restored_fold_vote_20261111/docker_smoke.json).
