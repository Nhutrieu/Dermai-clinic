# So sánh OOF năm fold: B0, ConvNeXt và tổ hợp

Tập phát triển: **5.937 ảnh**, chia năm fold theo nhóm ca/cảnh. Mỗi dự đoán được tạo từ checkpoint không học và không chọn epoch trên fold chứa ảnh đó.

**Đây là kết quả phát triển để chọn cách kết hợp, không phải độ chính xác trên test độc lập mới.** Công thức train đã được nghiên cứu trên nguồn này trước khi chia lại fold. Nhiều ảnh không có mã bệnh nhân nên không thể xác nhận tách hoàn toàn theo người.

| Tỉ trọng ConvNeXt | Accuracy | Macro recall | Macro F1 | SkinCancer recall | Train gốc accuracy | SCIN accuracy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00 | 72.01% | 70.52% | 71.00% | 78.73% | 73.35% | 65.16% |
| 0.25 | 74.84% | 73.50% | 73.78% | 82.72% | 76.23% | 67.73% |
| 0.50 | 77.65% | 76.36% | 76.35% | 87.30% | 79.32% | 69.16% |
| 0.75 **được chọn** | 77.78% | 76.85% | 76.37% | 87.89% | 79.28% | 70.18% |
| 1.00 | 76.96% | 76.39% | 75.40% | 87.44% | 78.41% | 69.57% |

Quy tắc chọn đã định trước: recall SkinCancer không thấp hơn model đơn tốt nhất; sau đó ưu tiên macro recall, macro F1 rồi accuracy trong năm tỉ trọng đã khóa.
Phương án được chọn là tổ hợp với tỉ trọng ConvNeXt 0.75.

## Kết quả của phương án được chọn theo từng bệnh

| Bệnh | Số ảnh | Recall | Precision | F1 |
| --- | ---: | ---: | ---: | ---: |
| Acne | 663 | 89.89% | 81.87% | 85.69% |
| Candidiasis | 243 | 74.90% | 65.70% | 70.00% |
| Eczema | 1577 | 82.05% | 76.70% | 79.29% |
| Lupus | 315 | 58.41% | 69.43% | 63.45% |
| Psoriasis | 897 | 65.22% | 78.52% | 71.25% |
| SkinCancer | 677 | 87.89% | 84.88% | 86.36% |
| Tinea | 989 | 68.05% | 76.05% | 71.82% |
| Warts | 576 | 88.37% | 78.43% | 83.10% |

## Theo nguồn ảnh

| Nguồn | Số ảnh | Số lớp có ảnh | Accuracy | Macro recall trên lớp có ảnh |
| --- | ---: | ---: | ---: | ---: |
| original_train | 4961 | 8 | 79.28% | 78.69% |
| SCIN | 976 | 7 | 70.18% | 38.51% |

## So sánh ghép theo cùng ảnh với từng model đơn

| Model đơn | Phương án chọn sửa đúng | Phương án chọn làm sai | Chênh accuracy | Khoảng bootstrap 95% theo nhóm ca/cảnh |
| --- | ---: | ---: | ---: | ---: |
| efficientnet_b0 | 616 | 273 | 5.78% | [4.77%; 6.75%] |
| convnext_tiny | 141 | 92 | 0.83% | [0.34%; 1.37%] |

Khoảng bootstrap này mô tả biến thiên trên chính tập phát triển. Vì tỉ trọng tổ hợp được chọn bằng dự đoán OOF của tập này, khoảng đó không xác nhận mức cải thiện trên dữ liệu mới.

SCIN trong tập này không có ảnh SkinCancer. Chỉ số SCIN không đánh giá được khả năng phát hiện lớp đó. Ma trận nhầm lẫn, top-3, hiệu chuẩn, kết quả từng fold và số ảnh sửa/làm sai so với model đơn nằm trong tệp JSON cùng tên.

Sau khi chọn phương án, cần một bộ test mới đủ tám bệnh, tách bệnh nhân/nguồn và có nhãn đáng tin cậy để xác nhận khả năng tổng quát hóa trước khi thay mô hình đang dùng.
