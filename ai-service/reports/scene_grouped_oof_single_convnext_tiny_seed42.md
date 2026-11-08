# ConvNeXt-Tiny: đánh giá OOF năm fold

Tập phát triển **5,937 ảnh** chia năm fold theo nhóm ca/cảnh đã biết. Mỗi dự đoán đến từ checkpoint không train và không chọn epoch trên fold chứa ảnh đó. Đây không phải bộ test bệnh nhân mới; nhiều ảnh không có mã người bệnh để xác nhận tách hoàn toàn.

| Accuracy | Macro recall | Macro F1 | SkinCancer recall | Top-3 accuracy |
| ---: | ---: | ---: | ---: | ---: |
| 76.96% | 76.39% | 75.40% | 87.44% | 91.88% |

## Từng bệnh

| Bệnh | Số ảnh | Recall | Precision | F1 |
| --- | ---: | ---: | ---: | ---: |
| Acne | 663 | 89.59% | 81.15% | 85.16% |
| Candidiasis | 243 | 74.90% | 62.12% | 67.91% |
| Eczema | 1577 | 80.41% | 77.04% | 78.68% |
| Lupus | 315 | 60.00% | 66.32% | 63.00% |
| Psoriasis | 897 | 62.32% | 78.84% | 69.61% |
| SkinCancer | 677 | 87.44% | 84.45% | 85.92% |
| Tinea | 989 | 68.76% | 75.89% | 72.15% |
| Warts | 576 | 87.67% | 74.81% | 80.74% |

## Ma trận nhầm lẫn

Hàng là nhãn thật, cột là nhãn dự đoán.

| Nhãn thật / dự đoán | Acne | Candidiasis | Eczema | Lupus | Psoriasis | SkinCancer | Tinea | Warts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Acne | 594 | 5 | 23 | 10 | 4 | 11 | 5 | 11 |
| Candidiasis | 5 | 182 | 9 | 0 | 10 | 2 | 23 | 12 |
| Eczema | 40 | 23 | 1268 | 19 | 74 | 19 | 85 | 49 |
| Lupus | 27 | 12 | 20 | 189 | 19 | 15 | 25 | 8 |
| Psoriasis | 21 | 43 | 142 | 32 | 559 | 23 | 43 | 34 |
| SkinCancer | 8 | 8 | 21 | 9 | 5 | 592 | 21 | 13 |
| Tinea | 25 | 15 | 142 | 22 | 35 | 27 | 680 | 43 |
| Warts | 12 | 5 | 21 | 4 | 3 | 12 | 14 | 505 |

## Theo fold và nguồn ảnh

| Fold | Số ảnh | Accuracy | Macro F1 |
| ---: | ---: | ---: | ---: |
| 0 | 1176 | 76.11% | 74.02% |
| 1 | 1193 | 76.19% | 75.77% |
| 2 | 1206 | 79.35% | 78.11% |
| 3 | 1201 | 74.94% | 73.27% |
| 4 | 1161 | 78.21% | 75.76% |

| Nguồn | Số ảnh | Accuracy | Macro recall trên các lớp có ảnh |
| --- | ---: | ---: | ---: |
| original_train | 4961 | 78.41% | 78.11% |
| SCIN | 976 | 69.57% | 39.83% |

| Nguồn | Bệnh | Số ảnh | Recall |
| --- | --- | ---: | ---: |
| original_train | Acne | 584 | 91.95% |
| original_train | Candidiasis | 236 | 75.85% |
| original_train | Eczema | 932 | 76.18% |
| original_train | Lupus | 304 | 62.17% |
| original_train | Psoriasis | 790 | 66.96% |
| original_train | SkinCancer | 677 | 87.44% |
| original_train | Tinea | 886 | 73.93% |
| original_train | Warts | 552 | 90.40% |
| SCIN | Acne | 79 | 72.15% |
| SCIN | Candidiasis | 7 | 42.86% |
| SCIN | Eczema | 645 | 86.51% |
| SCIN | Lupus | 11 | 0.00% |
| SCIN | Psoriasis | 107 | 28.04% |
| SCIN | Tinea | 103 | 24.27% |
| SCIN | Warts | 24 | 25.00% |

SCIN có 645/976 ảnh Eczema, nên accuracy của nguồn này chịu ảnh hưởng lớn từ Eczema; hãy xem cả macro recall và từng bệnh trong bảng trên.

SCIN trong tập này không có ảnh SkinCancer. Chỉ số riêng SCIN vì thế không đo được lớp đó. Báo cáo so sánh OOF hai model và các phép gộp dùng cùng 5.937 ảnh. Các kết quả này hỗ trợ chọn ứng viên phát triển; cần bộ test mới để xác nhận sau khi chọn.
