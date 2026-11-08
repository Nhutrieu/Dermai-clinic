# Tổng hợp nghiên cứu AI

Cập nhật ngày **08/11/2026**. Các ghi chú riêng theo lượt thử nghiệm đã được
rút gọn; giao thức, kết quả máy đọc và bằng chứng gốc vẫn ở
[`ai-service/reports/`](../ai-service/reports/). Tài liệu này là điểm bắt đầu
để đọc kết luận, không thay thế giao thức của từng lượt.

## Model ứng dụng và bản nghiên cứu đang giữ

API nạp **EfficientNet-B0 đơn**. Cấu hình, dữ liệu và phép đo của checkpoint
phục vụ được mô tả trong [model card](model-card-scin-v1.md).

Bản nghiên cứu tham chiếu có **4.687/5.937 ảnh đúng**, Accuracy **78,9456%**,
Macro F1 **77,7287%**, Recall SkinCancer **88,0355%**. Ensemble kết hợp
EfficientNet-B0, ConvNeXt-Tiny và ResNet50; một số fold có cổng chọn nhãn hoặc
đầu specialist. Đây là đánh giá OOF phát triển, chưa được đóng gói để phục vụ
ảnh mới. [Bản giải trình pipeline](GIAI_TRINH_PIPELINE_AI_CHO_THAY_20261108.md)
giữ công thức, lựa chọn theo fold, pseudocode và bảng bỏ từng thành phần.

## Những kết luận cần giữ

- Thêm backbone hoặc tăng điểm tổng chưa bảo đảm giữ recall/F1 từng bệnh.
  [Ensemble ban đầu](10-nghien-cuu-va-thu-nghiem-ensemble-ai.md) mô tả các
  phép so sánh và giới hạn của test lịch sử.
- Test lịch sử có ảnh cùng cảnh với dữ liệu phát triển dù khác byte.
  [Audit ảnh trùng cảnh](47-audit-anh-trung-gan-test-cu.md) và
  [giao thức chia tập theo nhóm](49-split-validation-chong-anh-cung-canh.md)
  giải thích vì sao không diễn giải điểm test cũ là độc lập theo bệnh nhân.
- Giữ nguyên mặt nạ dự đoán SkinCancer chỉ bảo toàn hành vi của bản tham chiếu,
  bao gồm cả lỗi bỏ sót; không có nghĩa đã cải thiện phát hiện ung thư.
- Cổng Macro F1 tăng ròng 15 ảnh đúng so ensemble tham chiếu. Specialist được
  chọn tăng thêm một ảnh; nó sửa 11 ảnh nhưng làm sai thêm 10 ảnh. Chưa có
  bằng chứng cải thiện ổn định đồng đều Lupus, Psoriasis và Tinea.
- SAM, loss cân lớp, SupCon, CutMix, các đầu cặp bệnh, LDA và các cách ghép
  CNN4/CNN6/CNN8 là các nhánh đã khảo sát. Điểm của một fold, query TRAIN
  hoặc seed riêng không thay điểm OOF toàn bộ. Xem giao thức và quyết định
  lựa chọn trong báo cáo gốc trước khi dùng số liệu.

## Các báo cáo gốc nên mở

| Nội dung | Báo cáo |
|---|---|
| Ensemble giữ quyết định SkinCancer | [Fusion có bảo vệ](../ai-service/reports/original_eight_cancer_locked_resnet_fusion_seed42_20261021/summary.md) |
| Cổng theo tác động Macro F1 | [Cổng Macro F1](../ai-service/reports/teacher_macro_f1_gate_seed42_20261023/summary.md) |
| Specialist đang giữ | [Đầu Dropout](../ai-service/reports/teacher_dropout_specialist_seed42_20261023/summary.md) |
| Kiểm lại đóng góp từng thành phần | [Kết quả giải trình](../ai-service/reports/teacher_pipeline_explanation_20261108/results.json) |
| Vì sao ba bệnh yếu chưa tăng ổn định | [Phân tích lỗi theo seed](../ai-service/reports/teacher_seed_pair_error_diagnosis_20261105/summary.md) |
| Đối chiếu metadata nhãn SCIN | [Audit nhãn đầu duy nhất](../ai-service/reports/teacher_scin_unique_top_audit_20261106/results.json) |
| Pilot lọc ca SCIN có nhãn đồng hạng | [Kết quả đối chứng](../ai-service/reports/teacher_scin_unique_top_pilot_20261106/results.json) |
| Ảnh ca bệnh giấy phép mở | [Ghi công nguồn](../ai-service/reports/teacher_open_case_photo_intake_20261106/ATTRIBUTION.md), [ứng viên ảnh lâm sàng](../ai-service/reports/teacher_open_case_photo_intake_20261106/clinical_candidates.jsonl) |

## Trạng thái các lượt dữ liệu gần nhất

Đối chiếu SCIN phát hiện quy tắc lấy nhãn đầu khi đồng hạng phụ thuộc thứ tự
nhãn nguồn. Pilot lọc ca đồng hạng đã train xong nhưng chưa cải thiện: trên
cùng 1.332 query TRAIN lịch sử, nhánh lọc đạt 71,55% Accuracy / 69,61% Macro F1,
thấp hơn Full CE đối chứng 71,85% / 69,94%. Đây chưa phải test bệnh nhân mới;
không đổi nhãn gốc, mốc OOF hoặc model phục vụ.

Đợt thu nhận ảnh ca bệnh giữ 11 tệp ảnh lâm sàng ứng viên: bốn Lupus, sáu
Psoriasis và một Tinea. Chỉ ba tệp Lupus là ảnh đơn nguyên khung; tám tệp còn
lại là hình ghép cần xử lý và rà lại. Chưa đưa các ảnh này vào train/test.
Nhóm bài báo chưa tương đương bệnh nhân độc lập được xác minh; nhãn tác giả
chưa được chuyên môn của dự án xác nhận lại.

## Nguồn dữ liệu và giao thức lịch sử

[Danh mục nguồn đánh giá tám lớp](45-nguon-anh-kiem-thu-8-lop-doc-lap.md)
giữ thông tin về nguồn ảnh và giới hạn. Các phép thử DermaCon, SkinDisNet,
PAD, DermaTonet, HIBA, MILK10k, MED-NODE và SLICE3D là những tác vụ, tập lớp
và vai trò dữ liệu khác nhau; không cộng hoặc so trực tiếp điểm của chúng
thành một điểm tám bệnh chung. Các protocol riêng đã cũ được thay bằng
giao thức hiện hành và hồ sơ gốc trong `ai-service/reports/`.

Khi tiếp tục nghiên cứu, khóa giao thức trước khi chạy; chọn checkpoint,
ngưỡng và phương án trong train/inner validation, rồi mới chấm vai trò đánh
giá đã quy định. Giữ nhóm ca/cảnh và kiểm giao nhau; không tự đổi nhãn bằng
dự đoán model. Cần nguồn bệnh nhân mới và nhãn đáng tin để xác nhận cải thiện.
PASS kiểm chứng phép tính không chứng nhận chất lượng lâm sàng.
