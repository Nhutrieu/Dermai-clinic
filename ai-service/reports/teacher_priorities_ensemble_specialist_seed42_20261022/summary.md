# Kết quả hai ưu tiên theo góp ý thầy

Ngày 22/10/2026. Cùng tám bệnh, cùng 5.937 ảnh phát triển OOF, không thêm backbone.

**Giữ baseline: Accuracy 78,68%; Macro F1 77,24%; Recall SkinCancer 88,04%.** Hai phép thử A/B đã hoàn tất đủ năm fold và được đối chiếu độc lập; chưa chứng minh được cải thiện ổn định. Không thay checkpoint/API hoặc gán các điểm này cho API B0.

## Kết quả tổng

| Phương án | Accuracy | Macro F1 | Recall SkinCancer | Số ảnh đúng |
|---|---:|---:|---:|---:|
| Baseline hiện hành | 78,68% | 77,24% | 88,04% | 4671/5.937 |
| A — chọn tỷ trọng bằng validation | 78,66% | 77,24% | 88,04% | 4670/5.937 |
| B — dùng đầu chuyên biệt ở cả năm fold | 78,42% | 77,07% | 88,04% | 4656/5.937 |
| B — chọn bằng validation, có baseline dự phòng | 78,68% | 77,24% | 88,04% | 4671/5.937 |

A/B được thử độc lập. Hàng B dùng đầu ở cả năm fold là kết quả phương pháp thô, chưa qua điều kiện lựa chọn; hàng B chọn bằng validation cho thấy quyết định có giữ phương pháp đó hay quay về baseline. Không lấy phương án có điểm outer tốt hơn để chọn lại.

## A. Tỷ trọng ResNet trong ensemble

Tập tỷ trọng được ghi trước: 0/10/20/30/40/50%. Giữ các lớp được baseline bảo vệ; không thay mô hình, dữ liệu hay các trọng số tham chiếu B0/ConvNeXt. Chọn bằng inner validation; cả năm lựa chọn được khóa trước chấm outer.

| Fold (đánh số từ 0) | Lựa chọn validation | Accuracy baseline → được chọn | Macro F1 baseline → được chọn |
|---|---|---:|---:|
| 0 | weight_0.30 | 78,32% → 78,23% | 76,94% → 76,97% |
| 1 | current_fusion | 77,62% → 77,62% | 76,55% → 76,55% |
| 2 | current_fusion | 80,85% → 80,85% | 80,83% → 80,83% |
| 3 | current_fusion | 77,85% → 77,85% | 75,33% → 75,33% |
| 4 | current_fusion | 78,73% → 78,73% | 76,23% → 76,23% |

A chỉ chọn tỷ trọng 30% ở fold 0; bốn fold còn lại giữ baseline. Tổng số đúng giảm một ảnh (4.671 → 4.670), Macro F1 tăng khoảng 0,0033 điểm phần trăm, làm tròn hai chữ số vẫn là 77,24%. Vì vậy không kết luận A tăng đồng thời Accuracy/Macro F1 hoặc đã tốt hơn ổn định.

## B. Chuyên biệt nhóm bệnh yếu

Đã học năm đầu Logistic Regression đa lớp trên đặc trưng ResNet50 cố định của từng fold. Đầu học Lupus/Psoriasis/Tinea/Eczema/Khác; mỗi scaler và đầu chỉ fit trên train fold tương ứng. Không train lại CNN, không bổ sung ảnh, cân bằng lấy mẫu hoặc mining trong phép thử này.

Chỉ xét đổi dự đoán hiện tại thuộc bốn bệnh mục tiêu khi điểm đầu ≥0,8 và đầu không chọn Khác. Đây là điểm nội bộ, không phải xác suất chẩn đoán đã hiệu chỉnh. Mọi quyết định SkinCancer giữ nguyên.

| Fold | Ảnh train | Lựa chọn | Điều kiện nhánh chuyên biệt không đạt trên validation |
|---|---:|---|---|
| 0 | 4043 | current_fusion | Lupus_f1, Lupus_recall, Psoriasis_f1, Psoriasis_recall, Tinea_f1, accuracy, macro_f1, precision_Lupus, precision_Tinea |
| 1 | 4031 | current_fusion | Lupus_f1, Lupus_recall, accuracy, macro_f1 |
| 2 | 4020 | current_fusion | Lupus_f1, Lupus_recall, Psoriasis_f1, Psoriasis_recall, accuracy, macro_f1 |
| 3 | 4024 | current_fusion | Psoriasis_f1, Psoriasis_recall, macro_f1 |
| 4 | 4060 | current_fusion | Lupus_f1, Lupus_recall, Psoriasis_f1, Psoriasis_recall, Tinea_f1, Tinea_recall, accuracy, macro_f1, precision_Tinea |

**Cả năm fold giữ baseline.** Đầu chuyên biệt theo công thức này chưa đạt điều kiện validation. Đây là kết luận cho phép thử cố định này, không phải kết luận rằng mọi mô hình chuyên biệt đều không có ích.

## Recall / F1 từng bệnh trên OOF

| Bệnh | Baseline | A chọn bằng validation | B dùng đầu chuyên biệt | B chọn bằng validation |
|---|---:|---:|---:|---:|
| Acne | 90,05% / 86,15% | 90,05% / 86,15% | 90,05% / 86,15% | 90,05% / 86,15% |
| Candidiasis | 72,84% / 70,24% | 72,84% / 70,24% | 72,84% / 70,24% | 72,84% / 70,24% |
| Eczema | 83,51% / 80,06% | 83,32% / 79,95% | 83,01% / 79,65% | 83,51% / 80,06% |
| Lupus | 59,68% / 64,49% | 59,68% / 64,49% | 59,05% / 64,58% | 59,68% / 64,49% |
| Psoriasis | 68,90% / 72,66% | 69,23% / 72,76% | 67,34% / 71,61% | 68,90% / 72,66% |
| SkinCancer | 88,04% / 87,13% | 88,04% / 87,13% | 88,04% / 87,13% | 88,04% / 87,13% |
| Tinea | 67,54% / 73,01% | 67,44% / 72,98% | 68,45% / 73,03% | 67,54% / 73,01% |
| Warts | 88,54% / 84,16% | 88,54% / 84,23% | 88,54% / 84,16% | 88,54% / 84,16% |

## Theo nguồn: Recall ba bệnh yếu

| Nguồn | Bệnh | Số ảnh | Baseline | A chọn | B dùng đầu | B chọn |
|---|---|---:|---:|---:|---:|---:|
| original_train | Lupus | 304 | 61,84% | 61,84% | 61,18% | 61,84% |
| original_train | Psoriasis | 790 | 73,80% | 74,18% | 72,15% | 73,80% |
| original_train | Tinea | 886 | 73,81% | 73,70% | 74,72% | 73,81% |
| SCIN | Lupus | 11 | 0,00% | 0,00% | 0,00% | 0,00% |
| SCIN | Psoriasis | 107 | 32,71% | 32,71% | 31,78% | 32,71% |
| SCIN | Tinea | 103 | 13,59% | 13,59% | 14,56% | 13,59% |

SCIN Lupus chỉ có 11 ảnh; tỷ lệ từ mẫu nhỏ không xác định được nguyên nhân hoặc hiệu năng lâm sàng. Các phép thử này không sửa nhãn, không bỏ ảnh khó, không thêm dữ liệu ngoài để tăng điểm.

## Khoảng bootstrap ghép cặp theo nhóm

1.000 lần lấy mẫu lại nhóm ca/cảnh; khoảng 95% của chênh lệch so với baseline, đơn vị điểm phần trăm. Các khoảng chỉ mô tả trên dữ liệu đã nghiên cứu, chưa tính hết việc thử nhiều phương án hay khác biệt giữa seed.

| Phương án | Δ Accuracy | Δ Macro F1 |
|---|---:|---:|
| A — chọn tỷ trọng bằng validation | [-0,1178; +0,0841] | [-0,0651; +0,0685] |
| B — dùng đầu chuyên biệt ở cả năm fold | [-0,5868; +0,0836] | [-0,4578; +0,1024] |
| B — chọn bằng validation, có baseline dự phòng | [+0,0000; +0,0000] | [+0,0000; +0,0000] |

## Kiểm chứng và giới hạn

- Kiểm lại SHA 5.937 ảnh; refit năm đầu từ cache train, dựng lại mười lựa chọn validation và 88 bộ chỉ số bằng NumPy.
- Toàn bộ mặt nạ SkinCancer và nguồn checkpoint gốc giữ nguyên. Bản thân các lỗi SkinCancer cũ cũng giữ nguyên.
- Năm fold dùng các CNN cha seed hiện có; không phải kiểm chứng qua năm seed. Chưa đủ bằng chứng cải thiện ổn định.
- Các tập đã được dùng phát triển trước đó. Không có bộ test bệnh nhân mới độc lập; chia nhóm cảnh không đảm bảo có đủ mã bệnh nhân.
- PASS là nhất quán kỹ thuật. API, checkpoint phục vụ và các mốc nghiên cứu trước không bị thay.

## Tiếp theo theo hướng của thầy

Giữ A/B làm đối chứng đã hoàn tất. Nếu thử cách học chuyên biệt khác, đăng ký một thay đổi riêng (ví dụ cân bằng loss/lấy mẫu trong cùng đầu chuyên biệt) với đối chứng B này, không đồng thời đổi backbone/dữ liệu/ngưỡng. Chỉ dùng train để xác định ví dụ khó; không quét ngưỡng theo lỗi outer vừa thấy. Ưu tiên làm rõ chất lượng nhãn và khác biệt nguồn của các bệnh yếu trước khi mở rộng số lượt train.

## Tệp

- [Giao thức đã ghi trước](protocol.json).
- [Kiểm chứng độc lập](independent_review.json).
- [Kết quả A](A_ensemble_weight/results.json), [kết quả B](B_specialist/results.json).
- [So sánh confusion matrix](confusion_matrices.png).
- [Kế hoạch theo góp ý thầy](../../KE_HOACH_THEO_GOP_Y_THAY.md).
