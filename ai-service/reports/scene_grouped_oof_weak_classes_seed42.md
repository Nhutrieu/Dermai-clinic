# Kiểm tra bổ sung cho Lupus và Psoriasis

Thí nghiệm được đề xuất sau khi đã xem OOF. Mỗi fold chỉ chọn cấu hình bằng inner validation; điểm outer vẫn là dữ liệu phát triển đã xem, không phải xác nhận trên test mới.

| Phương án | Accuracy | Macro F1 | Lupus recall | Lupus precision | Psoriasis recall | Psoriasis precision | SkinCancer recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| convnext_tiny | 76.96% | 75.40% | 60.00% | 66.32% | 62.32% | 78.84% | 87.44% |
| classwise_baseline | 78.07% | 76.82% | 59.68% | 71.76% | 67.78% | 75.72% | 88.04% |
| weak_class_trial | 77.99% | 76.88% | 62.54% | 70.61% | 66.56% | 75.19% | 88.04% |

## Từng bệnh

| Bệnh | Ảnh | Recall cũ | Recall thử | Precision cũ | Precision thử | F1 cũ | F1 thử | Sửa đúng | Đổi sai |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Acne | 663 | 89.44% | 89.59% | 82.94% | 82.73% | 86.07% | 86.02% | 1 | 0 |
| Candidiasis | 243 | 72.84% | 73.66% | 67.82% | 67.80% | 70.24% | 70.61% | 2 | 0 |
| Eczema | 1577 | 82.82% | 82.63% | 76.60% | 76.78% | 79.59% | 79.60% | 1 | 4 |
| Lupus | 315 | 59.68% | 62.54% | 71.76% | 70.61% | 65.16% | 66.33% | 10 | 1 |
| Psoriasis | 897 | 67.78% | 66.56% | 75.72% | 75.19% | 71.53% | 70.61% | 6 | 17 |
| SkinCancer | 677 | 88.04% | 88.04% | 86.25% | 86.38% | 87.13% | 87.20% | 0 | 0 |
| Tinea | 989 | 66.73% | 66.43% | 76.48% | 76.66% | 71.27% | 71.18% | 0 | 3 |
| Warts | 576 | 88.02% | 88.02% | 79.59% | 79.47% | 83.59% | 83.53% | 0 | 0 |

## Theo nguồn

| Nguồn | Bệnh | Số ảnh | Recall cũ | Recall thử |
| --- | --- | ---: | ---: | ---: |
| original_train | Lupus | 304 | 61.84% | 64.80% |
| original_train | Psoriasis | 790 | 73.04% | 71.90% |
| SCIN | Lupus | 11 | 0.00% | 0.00% |
| SCIN | Psoriasis | 107 | 28.97% | 27.10% |

## Lỗi của hai model ban đầu

Không thể chọn đúng bằng cách chỉ chọn nhãn argmax của B0 hoặc ConvNeXt khi cả hai cùng sai. Điểm này không phải giới hạn của mọi cách gộp xác suất hoặc mô hình mới.

- Lupus: cả hai cùng sai 96/315 ảnh. Bản gộp cũ nhầm nhiều nhất sang: Psoriasis: 26 ảnh; Tinea: 24 ảnh; Acne: 23 ảnh; SkinCancer: 19 ảnh; Eczema: 18 ảnh; Candidiasis: 10 ảnh; Warts: 7 ảnh.
- Psoriasis: cả hai cùng sai 231/897 ảnh. Bản gộp cũ nhầm nhiều nhất sang: Eczema: 136 ảnh; Tinea: 45 ảnh; Candidiasis: 30 ảnh; Warts: 25 ảnh; Lupus: 20 ảnh; Acne: 17 ảnh; SkinCancer: 16 ảnh.

## Confusion matrix: classwise_baseline

| Nhãn thật / dự đoán | Acne | Candidiasis | Eczema | Lupus | Psoriasis | SkinCancer | Tinea | Warts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Acne | 593 | 4 | 26 | 7 | 10 | 9 | 5 | 9 |
| Candidiasis | 6 | 177 | 8 | 3 | 16 | 2 | 21 | 10 |
| Eczema | 32 | 15 | 1306 | 13 | 84 | 19 | 72 | 36 |
| Lupus | 23 | 10 | 18 | 188 | 26 | 19 | 24 | 7 |
| Psoriasis | 17 | 30 | 136 | 20 | 608 | 16 | 45 | 25 |
| SkinCancer | 5 | 5 | 25 | 10 | 7 | 596 | 21 | 8 |
| Tinea | 28 | 16 | 164 | 19 | 47 | 20 | 660 | 35 |
| Warts | 11 | 4 | 22 | 2 | 5 | 10 | 15 | 507 |

## Confusion matrix: weak_class_trial

| Nhãn thật / dự đoán | Acne | Candidiasis | Eczema | Lupus | Psoriasis | SkinCancer | Tinea | Warts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Acne | 594 | 4 | 27 | 7 | 9 | 9 | 4 | 9 |
| Candidiasis | 7 | 179 | 7 | 1 | 15 | 3 | 21 | 10 |
| Eczema | 32 | 15 | 1303 | 13 | 87 | 19 | 72 | 36 |
| Lupus | 23 | 9 | 16 | 197 | 23 | 18 | 22 | 7 |
| Psoriasis | 19 | 32 | 137 | 25 | 597 | 16 | 45 | 26 |
| SkinCancer | 5 | 5 | 24 | 9 | 8 | 596 | 22 | 8 |
| Tinea | 27 | 16 | 161 | 24 | 50 | 19 | 657 | 35 |
| Warts | 11 | 4 | 22 | 3 | 5 | 10 | 14 | 507 |

## Kết luận theo tiêu chí bổ sung

Nhánh thử chưa đồng thời tăng recall cả Lupus/Psoriasis, giữ recall SkinCancer và macro F1. Giữ bản gộp cũ làm ứng viên; chưa có căn cứ thay bằng nhánh thử.

Hệ số điểm làm thay đổi xác suất và có thể làm calibration kém hơn; chưa hiệu chỉnh lại, không diễn giải các điểm đó như xác suất lâm sàng đã xác nhận. Không thay checkpoint hoặc bảng Excel kết quả cũ.
