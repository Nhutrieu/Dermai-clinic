# EfficientNet-B0: đánh giá OOF năm fold

Tập phát triển **5,937 ảnh** chia năm fold theo nhóm ca/cảnh đã biết. Mỗi dự đoán đến từ checkpoint không train và không chọn epoch trên fold chứa ảnh đó. Đây không phải bộ test bệnh nhân mới; nhiều ảnh không có mã người bệnh để xác nhận tách hoàn toàn.

| Accuracy | Macro recall | Macro F1 | SkinCancer recall | Top-3 accuracy |
| ---: | ---: | ---: | ---: | ---: |
| 72.01% | 70.52% | 71.00% | 78.73% | 92.67% |

## Từng bệnh

| Bệnh | Số ảnh | Recall | Precision | F1 |
| --- | ---: | ---: | ---: | ---: |
| Acne | 663 | 82.05% | 82.05% | 82.05% |
| Candidiasis | 243 | 68.72% | 67.34% | 68.02% |
| Eczema | 1577 | 79.33% | 69.97% | 74.35% |
| Lupus | 315 | 53.65% | 62.13% | 57.58% |
| Psoriasis | 897 | 63.88% | 66.55% | 65.19% |
| SkinCancer | 677 | 78.73% | 81.25% | 79.97% |
| Tinea | 989 | 59.15% | 68.50% | 63.48% |
| Warts | 576 | 78.65% | 76.13% | 77.37% |

## Ma trận nhầm lẫn

Hàng là nhãn thật, cột là nhãn dự đoán.

| Nhãn thật / dự đoán | Acne | Candidiasis | Eczema | Lupus | Psoriasis | SkinCancer | Tinea | Warts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Acne | 544 | 3 | 30 | 24 | 18 | 10 | 18 | 16 |
| Candidiasis | 4 | 167 | 11 | 4 | 26 | 3 | 20 | 8 |
| Eczema | 31 | 12 | 1251 | 11 | 116 | 25 | 99 | 32 |
| Lupus | 17 | 9 | 25 | 169 | 36 | 24 | 28 | 7 |
| Psoriasis | 19 | 23 | 163 | 24 | 573 | 14 | 51 | 30 |
| SkinCancer | 8 | 7 | 49 | 8 | 17 | 533 | 34 | 21 |
| Tinea | 30 | 20 | 212 | 26 | 65 | 23 | 585 | 28 |
| Warts | 10 | 7 | 47 | 6 | 10 | 24 | 19 | 453 |

## Theo fold và nguồn ảnh

| Fold | Số ảnh | Accuracy | Macro F1 |
| ---: | ---: | ---: | ---: |
| 0 | 1176 | 71.09% | 70.45% |
| 1 | 1193 | 71.84% | 70.41% |
| 2 | 1206 | 74.71% | 74.71% |
| 3 | 1201 | 71.19% | 69.32% |
| 4 | 1161 | 71.15% | 69.53% |

| Nguồn | Số ảnh | Accuracy | Macro recall trên các lớp có ảnh |
| --- | ---: | ---: | ---: |
| original_train | 4961 | 73.35% | 72.53% |
| SCIN | 976 | 65.16% | 33.05% |

| Nguồn | Bệnh | Số ảnh | Recall |
| --- | --- | ---: | ---: |
| original_train | Acne | 584 | 85.45% |
| original_train | Candidiasis | 236 | 69.92% |
| original_train | Eczema | 932 | 75.75% |
| original_train | Lupus | 304 | 54.93% |
| original_train | Psoriasis | 790 | 69.62% |
| original_train | SkinCancer | 677 | 78.73% |
| original_train | Tinea | 886 | 64.00% |
| original_train | Warts | 552 | 81.88% |
| SCIN | Acne | 79 | 56.96% |
| SCIN | Candidiasis | 7 | 28.57% |
| SCIN | Eczema | 645 | 84.50% |
| SCIN | Lupus | 11 | 18.18% |
| SCIN | Psoriasis | 107 | 21.50% |
| SCIN | Tinea | 103 | 17.48% |
| SCIN | Warts | 24 | 4.17% |

SCIN có 645/976 ảnh Eczema, nên accuracy của nguồn này chịu ảnh hưởng lớn từ Eczema; hãy xem cả macro recall và từng bệnh trong bảng trên.

SCIN trong tập này không có ảnh SkinCancer. Chỉ số riêng SCIN vì thế không đo được lớp đó. Báo cáo so sánh OOF hai model và các phép gộp dùng cùng 5.937 ảnh. Các kết quả này hỗ trợ chọn ứng viên phát triển; cần bộ test mới để xác nhận sau khi chọn.
