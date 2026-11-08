# Pilot ResNet-50 trên tám bệnh ban đầu

**Hoàn tất, kiểm chứng PASS. Pilot một outer fold; không thay điểm 5 fold cũ.**

Train4043/validation718/holdout1176ảnh; ResNet train24epoch, chọn epoch17 (raw).
Cập nhật thật: 6070; bước AMP bỏ qua: 2.

Phương án validation chọn với guard: `old_classwise`.

| Phương án | Val Accuracy | Val Macro F1 | Đạt guard | Outer Accuracy | Outer Macro F1 |
|---|---:|---:|---|---:|---:|
| old_classwise | 77.72% | 76.66% | True | 77.04% | 75.88% |
| reference_resnet_w0.75 | 74.09% | 73.48% | False | 74.66% | 74.71% |
| resnet50 | 72.98% | 72.51% | False | 72.79% | 73.01% |
| reference_resnet_w0.25 | 77.72% | 76.48% | False | 78.49% | 77.76% |
| reference_resnet_classwise | 77.16% | 75.99% | False | 78.15% | 77.63% |
| convnext_tiny | 76.32% | 74.78% | False | 76.11% | 74.02% |
| equal3 | 77.02% | 75.27% | False | 78.32% | 77.62% |
| reference_resnet_w0.50 | 75.91% | 74.88% | False | 76.87% | 76.55% |
| efficientnet_b0 | 72.14% | 70.94% | False | 71.09% | 70.45% |

## Từng bệnh: đối chứng và phương án chọn

| Bệnh | Recall cũ | Recall chọn | F1 cũ | F1 chọn | Ảnh |
|---|---:|---:|---:|---:|---:|
| Acne | 92.75% | 92.75% | 87.07% | 87.07% | 138 |
| Candidiasis | 82.98% | 82.98% | 73.58% | 73.58% | 47 |
| Eczema | 76.36% | 76.36% | 77.85% | 77.85% | 313 |
| Lupus | 57.53% | 57.53% | 63.64% | 63.64% | 73 |
| Psoriasis | 66.21% | 66.21% | 65.98% | 65.98% | 145 |
| SkinCancer | 86.06% | 86.06% | 87.38% | 87.38% | 165 |
| Tinea | 67.60% | 67.60% | 69.34% | 69.34% | 179 |
| Warts | 85.34% | 85.34% | 82.16% | 82.16% | 116 |

## Kết luận trong phạm vi pilot

So với cùng đối chứng fold0: Accuracy +0.00 điểm %, Macro F1 +0.00 điểm %.
CI95% chênh Accuracy theo nhóm ảnh/ca,3000bootstrap: [+0.00; +0.00] điểm %. Phân tích thăm dò trên dữ liệu phát triển đã xem.
- Không chọn lại tỷ lệ bằng điểm outer thuận lợi; guard áp dụng trên validation, không bảo đảm mọi chỉ số outer giữ nguyên.
- Mốc cũ:78,07% Accuracy/76,82% MacroF1 trên5937ảnh qua5fold. Không gán mốc đó cho B0 đang phục vụ hoặc pilot1176ảnh.
- Không dùng dữ liệu/model bộ tám bệnh mới; không đổi nhãn hoặc model phục vụ ứng dụng.
- Nhóm ảnh/cảnh/ca không thay thế mã bệnh nhân còn thiếu. Cần đánh giá ngoài độc lập để khẳng định khả năng tổng quát.

Nguồn kiến trúc: [ResNet](https://arxiv.org/abs/1512.03385), [Torchvision0.20](https://docs.pytorch.org/vision/0.20/models/generated/torchvision.models.resnet50.html). Đây là áp dụng vào dữ liệu cũ, không tái lập bài báo.
