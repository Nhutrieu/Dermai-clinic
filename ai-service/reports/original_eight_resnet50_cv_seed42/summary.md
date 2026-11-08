# ResNet-50 và ensemble trên bộ tám bệnh cũ — đủ 5 fold

**Hoàn tất; kiểm chứng PASS. 5.937 ảnh OOF, ba kiến trúc. Đây là đánh giá nội bộ trên tập phát triển.**

## Phạm vi và cách chọn

- Tám bệnh: Acne, Candidiasis, Eczema, Lupus, Psoriasis, SkinCancer, Tinea, Warts.
- Giữ nguyên 5 fold theo nhóm ảnh/cảnh/ca và inner validation cũ. Tái sử dụng ResNet fold 0 đã xác minh; train thêm bốn ResNet từ ImageNet V2, seed 42.
- Mỗi fold chọn checkpoint trên validation bằng Macro F1, Top-3, rồi loss; tối đa 24 epoch, freeze 2 epoch và patience 7.
- Đánh giá chín công thức cố định. Chọn bằng validation với điều kiện: Recall SkinCancer và Macro F1 không giảm; Accuracy giảm tối đa 0,5 điểm %; Recall các bệnh ngoài mục tiêu giảm tối đa 2 điểm %; Precision Lupus/Psoriasis giảm tối đa 2 điểm %. Đối chứng luôn là phương án dự phòng.
- Trong các phương án đạt điều kiện, ưu tiên Recall thấp hơn giữa Lupus/Psoriasis, rồi F1 trung bình hai bệnh và chỉ số tổng. Khóa lựa chọn trước khi tạo kết quả outer.
- Công thức 75% đối chứng + 25% ResNet là giả thuyết lặp lại sau khi đã thấy kết quả fold 0. Báo cáo riêng 4.761 ảnh ở fold 1–4; không gọi phương án có điểm outer cao nhất là phương án được chọn trên validation.

## Điểm tổng trên cùng 5.937 ảnh

| Phương án | Accuracy | Macro F1 | Recall Lupus | Recall Psoriasis | Recall SkinCancer |
|---|---:|---:|---:|---:|---:|
| EfficientNet-B0 | 72.01% | 71.00% | 53.65% | 63.88% | 78.73% |
| ConvNeXt-Tiny | 76.96% | 75.40% | 60.00% | 62.32% | 87.44% |
| ResNet-50 | 74.06% | 73.16% | 62.54% | 65.22% | 81.39% |
| B0/ConvNeXt theo bệnh (đối chứng) | 78.07% | 76.82% | 59.68% | 67.78% | 88.04% |
| 75% đối chứng + 25% ResNet | 79.06% | 77.98% | 62.22% | 69.23% | 87.15% |
| 50% đối chứng + 50% ResNet | 78.04% | 77.23% | 62.54% | 68.90% | 85.08% |
| 25% đối chứng + 75% ResNet | 75.96% | 75.18% | 62.22% | 67.11% | 82.42% |
| Đối chứng/ResNet theo bệnh | 78.32% | 77.49% | 61.90% | 69.45% | 85.67% |
| Trung bình đều ba model | 78.71% | 77.73% | 61.27% | 69.01% | 86.85% |
| Chọn bằng validation với điều kiện đã khóa | 78.07% | 76.82% | 59.68% | 67.78% | 88.04% |

### Phương án chính: chọn bằng validation

Accuracy 78.07% (+0.00 điểm % so với đối chứng), Macro F1 76.82% (+0.00 điểm %).
Điều kiện áp dụng trên validation; không bảo đảm từng chỉ số trên outer cũng giữ nguyên.

### Vì sao công thức 75:25 được giữ hoặc loại trên validation

| Fold | Accuracy val cũ | Accuracy val 75:25 | F1 val cũ | F1 val 75:25 | Đạt điều kiện | Điều kiện chưa đạt |
|---|---:|---:|---:|---:|---|---|
| 0 | 77.72% | 77.72% | 76.66% | 76.48% | False | Macro F1 giảm; Recall Candidiasis giảm quá 2 điểm %; Precision Lupus giảm quá 2 điểm % |
| 1 | 81.07% | 81.77% | 81.47% | 81.47% | False | Recall Candidiasis giảm quá 2 điểm % |
| 2 | 76.79% | 76.93% | 76.57% | 76.18% | False | Macro F1 giảm |
| 3 | 77.81% | 79.21% | 76.51% | 77.57% | False | Recall Candidiasis giảm quá 2 điểm % |
| 4 | 81.70% | 83.52% | 82.08% | 83.85% | False | Recall Candidiasis giảm quá 2 điểm % |

## Từng bệnh: đối chứng, phương án chính và công thức 75:25

| Bệnh | Ảnh | Recall cũ | Recall chọn | Recall 75:25 | F1 cũ | F1 chọn | F1 75:25 | Precision cũ | Precision chọn | Precision 75:25 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Acne | 663 | 89.44% | 89.44% | 90.50% | 86.07% | 86.07% | 86.27% | 82.94% | 82.94% | 82.42% |
| Candidiasis | 243 | 72.84% | 72.84% | 72.84% | 70.24% | 70.24% | 73.14% | 67.82% | 67.82% | 73.44% |
| Eczema | 1577 | 82.82% | 82.82% | 83.96% | 79.59% | 79.59% | 80.19% | 76.60% | 76.60% | 76.75% |
| Lupus | 315 | 59.68% | 59.68% | 62.22% | 65.16% | 65.16% | 66.44% | 71.76% | 71.76% | 71.27% |
| Psoriasis | 897 | 67.78% | 67.78% | 69.23% | 71.53% | 71.53% | 72.80% | 75.72% | 75.72% | 76.76% |
| SkinCancer | 677 | 88.04% | 88.04% | 87.15% | 87.13% | 87.13% | 87.47% | 86.25% | 86.25% | 87.80% |
| Tinea | 989 | 66.73% | 66.73% | 68.35% | 71.27% | 71.27% | 73.64% | 76.48% | 76.48% | 79.81% |
| Warts | 576 | 88.02% | 88.02% | 88.54% | 83.59% | 83.59% | 83.88% | 79.59% | 79.59% | 79.69% |

## Từng fold

| Fold (0–4) | Ảnh outer | Phương án validation chọn | Accuracy cũ | Accuracy chọn | Accuracy 75:25 | F1 cũ | F1 chọn | F1 75:25 |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | 1176 | old_classwise | 77.04% | 77.04% | 78.49% | 75.88% | 75.88% | 77.76% |
| 1 | 1193 | old_classwise | 77.12% | 77.12% | 77.87% | 76.30% | 76.30% | 76.65% |
| 2 | 1206 | old_classwise | 80.85% | 80.85% | 81.67% | 80.83% | 80.83% | 82.06% |
| 3 | 1201 | old_classwise | 76.85% | 76.85% | 78.35% | 74.20% | 74.20% | 76.41% |
| 4 | 1161 | old_classwise | 78.47% | 78.47% | 78.90% | 76.58% | 76.58% | 76.54% |

## Lặp lại công thức trên fold 1–4: 4.761 ảnh

| Phương án | Accuracy | Macro F1 | Recall Lupus | Recall Psoriasis | F1 Lupus | F1 Psoriasis | Recall SkinCancer |
|---|---:|---:|---:|---:|---:|---:|---:|
| B0/ConvNeXt theo bệnh (đối chứng) | 78.32% | 77.02% | 60.33% | 68.09% | 65.62% | 72.68% | 88.67% |
| Chọn bằng validation với điều kiện đã khóa | 78.32% | 77.02% | 60.33% | 68.09% | 65.62% | 72.68% | 88.67% |
| 75% đối chứng + 25% ResNet | 79.21% | 77.99% | 62.81% | 69.15% | 66.67% | 73.65% | 88.48% |

## Lupus/Psoriasis theo nguồn ảnh phát triển

| Nguồn | Bệnh | Ảnh | Recall cũ | Recall chọn | Recall 75:25 | F1 cũ | F1 chọn | F1 75:25 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| original_train | Lupus | 304 | 61.84% | 61.84% | 64.47% | 68.12% | 68.12% | 69.38% |
| original_train | Psoriasis | 790 | 73.04% | 73.04% | 74.43% | 76.02% | 76.02% | 76.71% |
| scin_train | Lupus | 11 | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| scin_train | Psoriasis | 107 | 28.97% | 28.97% | 30.84% | 34.07% | 34.07% | 38.15% |

Đây là các phần của tập phát triển OOF, không phải ảnh kiểm thử ngoài mới. SCIN có ít ảnh Lupus và không có ảnh nhãn SkinCancer trong phần này.

## Độ bất định của chênh lệch

CI95% bootstrap cặp theo nhóm ảnh/cảnh/ca, 2.000 lần, seed 20261013. Đây là phân tích thăm dò, một seed huấn luyện, không hiệu chỉnh nhiều so sánh.

| Phạm vi | Phương án so với đối chứng | Δ Accuracy | CI95% Δ Accuracy | Δ Macro F1 | CI95% Δ Macro F1 |
|---|---|---:|---|---:|---|
| all_five_folds | Chọn bằng validation với điều kiện đã khóa | +0.00 | [+0.00; +0.00] | +0.00 | [+0.00; +0.00] |
| all_five_folds | 75% đối chứng + 25% ResNet | +0.99 | [+0.44; +1.56] | +1.16 | [+0.54; +1.83] |
| fold1_4_replication | Chọn bằng validation với điều kiện đã khóa | +0.00 | [+0.00; +0.00] | +0.00 | [+0.00; +0.00] |
| fold1_4_replication | 75% đối chứng + 25% ResNet | +0.88 | [+0.29; +1.48] | +0.98 | [+0.28; +1.71] |

Đơn vị trong bảng chênh lệch: điểm phần trăm. CI có chứa 0 chưa cho bằng chứng rõ về tăng trên phạm vi này.

## Huấn luyện đã chạy

| Fold | Epoch chạy | Epoch chọn | Cập nhật thật | AMP bỏ qua |
|---|---:|---:|---:|---:|
| 0 | 24 | 17 | 6070 | 2 |
| 1 | 23 | 16 | 5795 | 1 |
| 2 | 24 | 22 | 6046 | 2 |
| 3 | 24 | 18 | 6046 | 2 |
| 4 | 24 | 21 | 6094 | 2 |

Tổng năm ResNet (kể cả fold 0 tái sử dụng): 30051 bước cập nhật thật; 9 bước AMP bỏ qua.

## Giới hạn và tệp kết quả

- Tập phát triển và các kết quả cũ đã được dùng để xây dựng hướng thử nghiệm. Fold 0 góp phần tạo giả thuyết 75:25; fold 1–4 là lặp lại bổ sung, chưa phải tập ảnh bên ngoài độc lập.
- Chia theo nhóm ca/cảnh/ảnh có sẵn; nhiều ảnh gốc thiếu mã bệnh nhân. Không gọi đây là kiểm thử độc lập theo bệnh nhân.
- Không thêm ảnh của bộ tám bệnh mới. Checkpoint phục vụ ứng dụng giữ nguyên; điểm ensemble nghiên cứu không phải điểm của B0 đang phục vụ.
- [Giao thức](protocol.json), [kết quả mọi công thức và từng bệnh](results.json), [kiểm chứng](verification.json), [so sánh cặp](paired_comparisons.json), [từng nguồn](per_source.json), [log train](run.log).
- [Confusion matrix phương án chính](selected_confusion.png), [confusion matrix 75:25](fixed25_confusion.png).
