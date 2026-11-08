# Thử gộp B0 và ConvNeXt theo từng bệnh

Mỗi fold chọn tám trọng số bằng ảnh inner validation, rồi áp dụng lên ảnh outer fold mà bước chọn trọng số chưa xem nhãn. Đây là đánh giá phát triển; không phải test độc lập mới.

| Phương án | Accuracy | Macro recall | Macro F1 | SkinCancer recall |
| --- | ---: | ---: | ---: | ---: |
| EfficientNet-B0 | 72.01% | 70.52% | 71.00% | 78.73% |
| ConvNeXt-Tiny | 76.96% | 76.39% | 75.40% | 87.44% |
| Gộp đều 50:50 | 77.65% | 76.36% | 76.35% | 87.30% |
| Trọng số cố định được chọn | 77.78% | 76.85% | 76.37% | 87.89% |
| Gộp theo từng bệnh | 78.07% | 76.92% | 76.82% | 88.04% |

**Đề xuất để kiểm thử độc lập:** Gộp theo từng bệnh. Quy tắc: recall SkinCancer không thấp hơn model đơn tốt nhất, rồi so macro recall, macro F1 và accuracy. Phương án cố định dùng 0.75 trọng số ConvNeXt và đã được chọn trên chính OOF, nên đây chỉ là đề xuất phát triển.

| Phương án | Train gốc accuracy | SCIN accuracy | Train gốc macro recall | SCIN macro recall trên lớp có ảnh |
| --- | ---: | ---: | ---: | ---: |
| EfficientNet-B0 | 73.35% | 65.16% | 72.53% | 33.05% |
| ConvNeXt-Tiny | 78.41% | 69.57% | 78.11% | 39.83% |
| Gộp đều 50:50 | 79.32% | 69.16% | 78.43% | 35.79% |
| Trọng số cố định được chọn | 79.28% | 70.18% | 78.69% | 38.51% |
| Gộp theo từng bệnh | 79.80% | 69.26% | 79.02% | 35.46% |

## Recall từng bệnh theo nguồn ảnh

| Nguồn | Bệnh | Số ảnh | B0 | ConvNeXt | 50:50 | Trọng số cố định | Theo bệnh |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| original_train | Acne | 584 | 85.45% | 91.95% | 91.27% | 92.12% | 92.12% |
| original_train | Candidiasis | 236 | 69.92% | 75.85% | 74.58% | 75.85% | 74.15% |
| original_train | Eczema | 932 | 75.75% | 76.18% | 79.40% | 77.79% | 79.29% |
| original_train | Lupus | 304 | 54.93% | 62.17% | 59.54% | 60.53% | 61.84% |
| original_train | Psoriasis | 790 | 69.62% | 66.96% | 72.66% | 70.13% | 73.04% |
| original_train | SkinCancer | 677 | 78.73% | 87.44% | 87.30% | 87.89% | 88.04% |
| original_train | Tinea | 886 | 64.00% | 73.93% | 72.46% | 73.70% | 72.57% |
| original_train | Warts | 552 | 81.88% | 90.40% | 90.22% | 91.49% | 91.12% |
| SCIN | Acne | 79 | 56.96% | 72.15% | 69.62% | 73.42% | 69.62% |
| SCIN | Candidiasis | 7 | 28.57% | 42.86% | 28.57% | 42.86% | 28.57% |
| SCIN | Eczema | 645 | 84.50% | 86.51% | 87.29% | 88.22% | 87.91% |
| SCIN | Lupus | 11 | 18.18% | 0.00% | 0.00% | 0.00% | 0.00% |
| SCIN | Psoriasis | 107 | 21.50% | 28.04% | 29.91% | 28.97% | 28.97% |
| SCIN | Tinea | 103 | 17.48% | 24.27% | 18.45% | 19.42% | 16.50% |
| SCIN | Warts | 24 | 4.17% | 25.00% | 16.67% | 16.67% | 16.67% |

## Chỉ số riêng của từng bệnh trên cùng 5.937 ảnh OOF

| Bệnh | Số ảnh | B0 recall | ConvNeXt recall | 50:50 recall | Theo bệnh recall | B0 F1 | ConvNeXt F1 | 50:50 F1 | Theo bệnh F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Acne | 663 | 82.05% | 89.59% | 88.69% | 89.44% | 82.05% | 85.16% | 85.47% | 86.07% |
| Candidiasis | 243 | 68.72% | 74.90% | 73.25% | 72.84% | 68.02% | 67.91% | 71.34% | 70.24% |
| Eczema | 1577 | 79.33% | 80.41% | 82.63% | 82.82% | 74.35% | 78.68% | 79.09% | 79.59% |
| Lupus | 315 | 53.65% | 60.00% | 57.46% | 59.68% | 57.58% | 63.00% | 62.63% | 65.16% |
| Psoriasis | 897 | 63.88% | 62.32% | 67.56% | 67.78% | 65.19% | 69.61% | 71.55% | 71.53% |
| SkinCancer | 677 | 78.73% | 87.44% | 87.30% | 88.04% | 79.97% | 85.92% | 86.34% | 87.13% |
| Tinea | 989 | 59.15% | 68.76% | 66.84% | 66.73% | 63.48% | 72.15% | 71.27% | 71.27% |
| Warts | 576 | 78.65% | 87.67% | 87.15% | 88.02% | 77.37% | 80.74% | 83.11% | 83.59% |

Recall của cách gộp theo bệnh thấp hơn ConvNeXt đơn ở: Acne (89.59% xuống 89.44%); Candidiasis (74.90% xuống 72.84%); Lupus (60.00% xuống 59.68%); Tinea (68.76% xuống 66.73%).

## Ảnh sửa đúng và làm sai theo từng bệnh so với trọng số cố định

| Bệnh thật | Số ảnh | Gộp theo bệnh sửa đúng | Gộp theo bệnh làm sai | Chênh số ảnh đúng |
| --- | ---: | ---: | ---: | ---: |
| Acne | 663 | 2 | 5 | -3 |
| Candidiasis | 243 | 2 | 7 | -5 |
| Eczema | 1577 | 29 | 17 | 12 |
| Lupus | 315 | 10 | 6 | 4 |
| Psoriasis | 897 | 39 | 16 | 23 |
| SkinCancer | 677 | 3 | 2 | 1 |
| Tinea | 989 | 7 | 20 | -13 |
| Warts | 576 | 1 | 3 | -2 |

## Ma trận nhầm lẫn của từng phương án

Hàng là nhãn thật, cột là nhãn dự đoán; thứ tự lớp giống nhau ở cả bốn bảng.

### EfficientNet-B0

| Nhãn thật \ dự đoán | Acne | Candidiasis | Eczema | Lupus | Psoriasis | SkinCancer | Tinea | Warts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Acne | 544 | 3 | 30 | 24 | 18 | 10 | 18 | 16 |
| Candidiasis | 4 | 167 | 11 | 4 | 26 | 3 | 20 | 8 |
| Eczema | 31 | 12 | 1251 | 11 | 116 | 25 | 99 | 32 |
| Lupus | 17 | 9 | 25 | 169 | 36 | 24 | 28 | 7 |
| Psoriasis | 19 | 23 | 163 | 24 | 573 | 14 | 51 | 30 |
| SkinCancer | 8 | 7 | 49 | 8 | 17 | 533 | 34 | 21 |
| Tinea | 30 | 20 | 212 | 26 | 65 | 23 | 585 | 28 |
| Warts | 10 | 7 | 47 | 6 | 10 | 24 | 19 | 453 |

### ConvNeXt-Tiny

| Nhãn thật \ dự đoán | Acne | Candidiasis | Eczema | Lupus | Psoriasis | SkinCancer | Tinea | Warts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Acne | 594 | 5 | 23 | 10 | 4 | 11 | 5 | 11 |
| Candidiasis | 5 | 182 | 9 | 0 | 10 | 2 | 23 | 12 |
| Eczema | 40 | 23 | 1268 | 19 | 74 | 19 | 85 | 49 |
| Lupus | 27 | 12 | 20 | 189 | 19 | 15 | 25 | 8 |
| Psoriasis | 21 | 43 | 142 | 32 | 559 | 23 | 43 | 34 |
| SkinCancer | 8 | 8 | 21 | 9 | 5 | 592 | 21 | 13 |
| Tinea | 25 | 15 | 142 | 22 | 35 | 27 | 680 | 43 |
| Warts | 12 | 5 | 21 | 4 | 3 | 12 | 14 | 505 |

### Gộp đều 50:50

| Nhãn thật \ dự đoán | Acne | Candidiasis | Eczema | Lupus | Psoriasis | SkinCancer | Tinea | Warts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Acne | 588 | 3 | 27 | 10 | 9 | 9 | 7 | 10 |
| Candidiasis | 5 | 178 | 9 | 3 | 16 | 2 | 20 | 10 |
| Eczema | 37 | 12 | 1303 | 12 | 84 | 20 | 73 | 36 |
| Lupus | 22 | 8 | 23 | 181 | 26 | 23 | 24 | 8 |
| Psoriasis | 19 | 28 | 137 | 22 | 606 | 14 | 45 | 26 |
| SkinCancer | 6 | 6 | 24 | 9 | 8 | 591 | 22 | 11 |
| Tinea | 27 | 17 | 167 | 22 | 44 | 22 | 661 | 29 |
| Warts | 9 | 4 | 28 | 4 | 4 | 11 | 14 | 502 |

### Trọng số cố định được chọn

| Nhãn thật \ dự đoán | Acne | Candidiasis | Eczema | Lupus | Psoriasis | SkinCancer | Tinea | Warts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Acne | 596 | 4 | 26 | 10 | 3 | 9 | 5 | 10 |
| Candidiasis | 6 | 182 | 9 | 1 | 10 | 3 | 21 | 11 |
| Eczema | 36 | 18 | 1294 | 13 | 76 | 21 | 79 | 40 |
| Lupus | 25 | 11 | 20 | 184 | 22 | 20 | 25 | 8 |
| Psoriasis | 20 | 36 | 140 | 27 | 585 | 18 | 45 | 26 |
| SkinCancer | 8 | 6 | 25 | 8 | 5 | 595 | 22 | 8 |
| Tinea | 28 | 16 | 151 | 20 | 40 | 24 | 673 | 37 |
| Warts | 9 | 4 | 22 | 2 | 4 | 11 | 15 | 509 |

### Gộp theo từng bệnh

| Nhãn thật \ dự đoán | Acne | Candidiasis | Eczema | Lupus | Psoriasis | SkinCancer | Tinea | Warts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Acne | 593 | 4 | 26 | 7 | 10 | 9 | 5 | 9 |
| Candidiasis | 6 | 177 | 8 | 3 | 16 | 2 | 21 | 10 |
| Eczema | 32 | 15 | 1306 | 13 | 84 | 19 | 72 | 36 |
| Lupus | 23 | 10 | 18 | 188 | 26 | 19 | 24 | 7 |
| Psoriasis | 17 | 30 | 136 | 20 | 608 | 16 | 45 | 25 |
| SkinCancer | 5 | 5 | 25 | 10 | 7 | 596 | 21 | 8 |
| Tinea | 28 | 16 | 164 | 19 | 47 | 20 | 660 | 35 |
| Warts | 11 | 4 | 22 | 2 | 5 | 10 | 15 | 507 |


Quy tắc đã khóa: ở mỗi bệnh, nếu ConvNeXt nhận đúng hơn B0 ít nhất `max(3, ceil(5% số ảnh của bệnh))` ảnh trên inner validation thì đặt trọng số ConvNeXt 0,75; nếu B0 hơn mức đó thì đặt 0,25; còn lại 0,50. Cả tám điểm được chuẩn hóa về tổng 1 trước khi chọn nhãn.

| Bệnh | Trọng số ConvNeXt ở fold 0 | Fold 1 | Fold 2 | Fold 3 | Fold 4 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Acne | 0.50 | 0.75 | 0.50 | 0.50 | 0.75 |
| Candidiasis | 0.75 | 0.75 | 0.50 | 0.50 | 0.75 |
| Eczema | 0.50 | 0.75 | 0.50 | 0.75 | 0.50 |
| Lupus | 0.50 | 0.75 | 0.50 | 0.50 | 0.75 |
| Psoriasis | 0.50 | 0.25 | 0.50 | 0.50 | 0.50 |
| SkinCancer | 0.50 | 0.75 | 0.75 | 0.75 | 0.75 |
| Tinea | 0.75 | 0.75 | 0.75 | 0.75 | 0.75 |
| Warts | 0.75 | 0.75 | 0.75 | 0.75 | 0.75 |

## Bộ trọng số đề xuất để kiểm thử lần sau

Sau khi đã chấm outer fold, quy tắc tương tự được áp dụng lên toàn bộ dự đoán OOF để đề xuất một bộ tám trọng số cho mô hình cuối. **Không chấm bộ trọng số này trên chính OOF rồi gọi đó là điểm kiểm thử**; cần mô hình huấn luyện cuối và bộ test mới.

| Bệnh | B0 chỉ mình đúng | ConvNeXt chỉ mình đúng | Trọng số ConvNeXt đề xuất |
| --- | ---: | ---: | ---: |
| Acne | 11 | 61 | 0.75 |
| Candidiasis | 19 | 34 | 0.75 |
| Eczema | 127 | 144 | 0.50 |
| Lupus | 30 | 50 | 0.75 |
| Psoriasis | 107 | 93 | 0.50 |
| SkinCancer | 17 | 76 | 0.75 |
| Tinea | 72 | 167 | 0.75 |
| Warts | 19 | 71 | 0.75 |

## Đổi đúng/sai so với model đơn và các cách gộp

So với EfficientNet-B0, cách theo bệnh sửa đúng **548** ảnh và làm sai **188** ảnh. Chênh accuracy 6.06%; khoảng bootstrap theo nhóm ca/cảnh [5.18%; 6.96%].
So với ConvNeXt-Tiny, cách theo bệnh sửa đúng **227** ảnh và làm sai **161** ảnh. Chênh accuracy 1.11%; khoảng bootstrap theo nhóm ca/cảnh [0.47%; 1.80%].
So với Gộp đều 50:50, cách theo bệnh sửa đúng **98** ảnh và làm sai **73** ảnh. Chênh accuracy 0.42%; khoảng bootstrap theo nhóm ca/cảnh [0.00%; 0.85%].
So với Trọng số cố định được chọn, cách theo bệnh sửa đúng **93** ảnh và làm sai **76** ảnh. Chênh accuracy 0.29%; khoảng bootstrap theo nhóm ca/cảnh [-0.15%; 0.73%].

Khoảng bootstrap chỉ mô tả biến thiên trong tập phát triển. Nhiều ảnh chưa có mã bệnh nhân; công thức train hai model cũng từng được nghiên cứu trên nguồn này. Phải đo trên bộ test mới đủ tám bệnh và tách bệnh nhân trước khi kết luận cải thiện thực tế.
SCIN trong tập này không có ảnh SkinCancer, nên chỉ số riêng SCIN không đo được bệnh đó.
