# Kiểm tra chuyển nguồn của ensemble bộ cũ có ResNet

**Hoàn tất; kiểm chứng PASS. Các nguồn này đã được xem trước đây, không phải test mới độc lập.**

Giữ nguyên 15 checkpoint (ba kiến trúc × năm fold). Trung bình xác suất năm fold cho từng kiến trúc; đối chứng là trung bình năm ensemble B0/ConvNeXt theo bệnh với trọng số inner đã khóa. So sánh công thức cố định 75% đối chứng + 25% ResNet. Không chỉnh nhiệt độ, trọng số, ngưỡng hoặc chọn checkpoint theo các nguồn này.

Kiểm tra SHA-256 và dHash khoảng cách tối đa 3 với toàn bộ 5.937 ảnh phát triển trước khi suy luận; ảnh nghi trùng được để riêng. dHash là kiểm tra ảnh nghi trùng, không chứng minh tính độc lập theo bệnh nhân.

## dermacon_in

986 ảnh / 642 ca; 0 ảnh để riêng vì nghi trùng. Nhãn có mẫu: Acne, Candidiasis, Eczema, Lupus, Psoriasis, SkinCancer, Tinea, Warts.

| Phương án | Đúng | Accuracy | Macro F1, lớp có mẫu | Macro F1, đủ 8 lớp |
|---|---:|---:|---:|---:|
| B0 (trung bình 5 fold) | 355 | 36.00% | 30.53% | 30.53% |
| ConvNeXt (trung bình 5 fold) | 385 | 39.05% | 33.80% | 33.80% |
| ResNet (trung bình 5 fold) | 376 | 38.13% | 33.85% | 33.85% |
| Ensemble B0/ConvNeXt theo bệnh | 379 | 38.44% | 34.01% | 34.01% |
| 75% ensemble cũ + 25% ResNet | 391 | 39.66% | 35.48% | 35.48% |

Tất cả model vẫn dự đoán tám lớp. Macro F1 lớp có mẫu lấy trung bình F1 của các nhãn có ảnh thật trong nguồn; đây không phải việc giới hạn model chỉ dự đoán các nhãn đó.

| Bệnh | Ảnh | Ca | Recall cũ | Recall 75:25 | Precision cũ | Precision 75:25 | F1 cũ | F1 75:25 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Acne | 178 | 89 | 83.71% | 83.71% | 87.65% | 88.17% | 85.63% | 85.88% |
| Candidiasis | 112 | 101 | 16.07% | 14.29% | 85.71% | 84.21% | 27.07% | 24.43% |
| Eczema | 156 | 103 | 34.62% | 44.23% | 18.49% | 20.72% | 24.11% | 28.22% |
| Lupus | 11 | 4 | 18.18% | 18.18% | 11.76% | 15.38% | 14.29% | 16.67% |
| Psoriasis | 154 | 70 | 75.32% | 74.03% | 33.24% | 35.51% | 46.12% | 48.00% |
| SkinCancer | 17 | 11 | 64.71% | 70.59% | 32.35% | 36.36% | 43.14% | 48.00% |
| Tinea | 319 | 242 | 6.58% | 6.58% | 32.31% | 33.33% | 10.94% | 10.99% |
| Warts | 39 | 32 | 20.51% | 20.51% | 21.05% | 22.86% | 20.78% | 21.62% |

Chênh Accuracy 75:25 − cũ: +1.22 điểm %, CI95% [-0.31; +2.71], bootstrap cặp theo ca, 2.000 lần.
- Lupus: 11 ảnh/4 ca; Δ Recall +0.00 điểm %, CI95% [+0.00; +0.00].
- Psoriasis: 154 ảnh/70 ca; Δ Recall -1.30 điểm %, CI95% [-5.11; +2.69].
- SkinCancer: 17 ảnh/11 ca; Δ Recall +5.88 điểm %, CI95% [+0.00; +21.43].

[Ma trận đối chứng](dermacon_in_old_classwise_confusion.png), [ma trận 75:25](dermacon_in_reference_resnet_w0.25_confusion.png).

## skindisnet_v2

723 ảnh / 181 ca; 0 ảnh để riêng vì nghi trùng. Nhãn có mẫu: Eczema, Tinea.

| Phương án | Đúng | Accuracy | Macro F1, lớp có mẫu | Macro F1, đủ 8 lớp |
|---|---:|---:|---:|---:|
| B0 (trung bình 5 fold) | 190 | 26.28% | 26.85% | 6.71% |
| ConvNeXt (trung bình 5 fold) | 142 | 19.64% | 26.89% | 6.72% |
| ResNet (trung bình 5 fold) | 157 | 21.72% | 28.54% | 7.13% |
| Ensemble B0/ConvNeXt theo bệnh | 160 | 22.13% | 25.81% | 6.45% |
| 75% ensemble cũ + 25% ResNet | 155 | 21.44% | 25.89% | 6.47% |

Tất cả model vẫn dự đoán tám lớp. Macro F1 lớp có mẫu lấy trung bình F1 của các nhãn có ảnh thật trong nguồn; đây không phải việc giới hạn model chỉ dự đoán các nhãn đó.

| Bệnh | Ảnh | Ca | Recall cũ | Recall 75:25 | Precision cũ | Precision 75:25 | F1 cũ | F1 75:25 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Eczema | 458 | 113 | 30.13% | 28.17% | 51.11% | 49.24% | 37.91% | 35.83% |
| Tinea | 265 | 68 | 8.30% | 9.81% | 39.29% | 42.62% | 13.71% | 15.95% |

Chênh Accuracy 75:25 − cũ: -0.69 điểm %, CI95% [-2.79; +1.26], bootstrap cặp theo ca, 2.000 lần.

[Ma trận đối chứng](skindisnet_v2_old_classwise_confusion.png), [ma trận 75:25](skindisnet_v2_reference_resnet_w0.25_confusion.png).

## Cách đọc kết quả

- Báo cáo từng nguồn riêng; không gộp hai tỷ lệ accuracy thành điểm tổng tám bệnh.
- SkinDisNet chỉ có Eczema/Tinea. DermaCon có ít ca Lupus/SkinCancer; số liệu đó chưa đủ để xác nhận hiệu năng lâm sàng.
- Các nguồn đã được dùng trong nghiên cứu trước đây. Giữ phép đo chuyển nguồn này ở mức mô tả; một tập mới chưa xem mới có thể xác nhận khả năng tổng quát.
- Trung bình năm fold khác cách dự đoán OOF một model mỗi ảnh; không gọi chênh lệch với79,06%OOF là mức tăng/giảm trên cùng phép đo.
- Checkpoint ứng dụng giữ nguyên; kết quả nguồn không dùng để chỉnh thêm trọng số.

[Giao thức](protocol.json), [audit](audit.json), [kết quả từng nguồn](results.json), [xác minh](verification.json), [bootstrap cặp](paired_comparisons.json).
