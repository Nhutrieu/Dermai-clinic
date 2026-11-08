# Phân biệt cặp bệnh dễ nhầm — pilot fold 0 ngày 24/10/2026

## Kết luận

**Chưa được chọn.** Đầu học riêng theo cặp tăng Macro F1 inner nhẹ nhưng làm Accuracy và Recall cả ba bệnh yếu giảm; F1 Psoriasis/Tinea giảm. Khóa giữ `current_policy`, không chọn lại bằng outer. Điểm tổng năm fold vẫn **78,95% Accuracy / 77,73% Macro F1 / 88,04% Recall SkinCancer**, API vẫn B0 đơn.

## Phép thử

- Dùng 2.048 đặc trưng ResNet cố định, 4.043 train / 718 inner / 1.176 outer, không thêm ảnh hoặc backbone.
- Chia nhóm train ba phần. Mỗi đầu tám nhãn tạm fit scaler bằng phần fit, dự đoán phần train giữ riêng. Chọn một đối thủ cho từng Lupus/Psoriasis/Tinea theo lỗi đối ứng có cân support; loại SkinCancer, không dùng inner/outer để chọn cặp.
- **Ba đầu khám phá + một đầu tám nhãn đối chứng + ba đầu binary = bảy fit**, tất cả Logistic Regression C=0,001, không train CNN. Scaler cuối dùng toàn train và dùng chung giữa đối chứng/đầu riêng.
- Đối chứng lấy điểm điều kiện trong từng cặp từ đầu tám nhãn; nhánh thử học riêng chỉ ảnh thuộc cặp. Trọng số đều của từng ảnh cặp bằng 4.043/số ảnh cặp để tổng trọng số loss bằng đối chứng, không phải cân bằng hai lớp. Số mục tiêu/tham số và phân bố ảnh khác nhau; cân tổng trọng số không loại mọi khác biệt điều chuẩn.
- Cả hai nhánh dùng điểm hai nhãn, ngưỡng 0,8, cùng phạm vi hai đầu cặp. Nếu các cặp đề xuất nhiều đích khác nhau thì giữ nhãn cũ; không chuyển nối tiếp. Không đổi bất kỳ dự đoán SkinCancer nào. Điểm nhị phân không phải xác suất chẩn đoán đã hiệu chỉnh.

| Cặp chọn từ train | Số ảnh mỗi bệnh | Lỗi đối ứng trong khám phá |
|---|---|---:|
| Acne – Lupus | {'Acne': 446, 'Lupus': 206} | 1 |
| Eczema – Psoriasis | {'Eczema': 1072, 'Psoriasis': 639} | 12 |
| Eczema – Tinea | {'Eczema': 1072, 'Tinea': 688} | 13 |

Cặp Lupus–Acne chỉ dựa trên **một lỗi đối ứng** trong khám phá train, nên chưa có bằng chứng lựa chọn cặp ổn định. Các đầu tạm dùng đặc trưng CNN đã học toàn train: đây là giữ riêng cho **đầu tuyến tính**, không phải OOF độc lập toàn CNN.

## Validation dùng chọn

| Phương pháp | Accuracy | Macro F1 | Recall SkinCancer |
|---|---:|---:|---:|
| Bản đang giữ | 77.72% | 76.82% | 87.01% |
| Điểm cặp từ đầu tám nhãn | 77.30% | 76.57% | 87.01% |
| Học riêng từng cặp | 77.58% | 76.86% | 87.01% |

| Bệnh | Bản đang giữ Recall / F1 | Đầu riêng Recall / F1 |
|---|---:|---:|
| Lupus | 63.89% / 56.79% | 61.11% / 59.46% |
| Psoriasis | 67.26% / 71.03% | 63.72% / 70.59% |
| Tinea | 72.95% / 76.72% | 71.31% / 75.65% |

Macro F1 tăng rất nhẹ không bù được recall từng bệnh hoặc Accuracy giảm. Không nới điều kiện để chọn nhánh thử. Giữ cả nhánh điểm cặp từ tám nhãn làm đối chứng.

## Outer sau khóa — chỉ một fold

| Phương pháp | Accuracy | Macro F1 | Recall SkinCancer |
|---|---:|---:|---:|
| Bản đang giữ | 78.91% | 78.21% | 86.06% |
| Điểm cặp từ đầu tám nhãn | 78.40% | 77.76% | 86.06% |
| Học riêng từng cặp | 78.23% | 77.77% | 86.06% |

Đầu riêng sửa 11 / làm sai 19 / đổi sai sang sai 17 ảnh. Bản được chọn vẫn giống bản trước trên cả 2.885 ảnh outer/nguồn, không tạo điểm tổng mới hoặc chứng minh cải thiện bệnh nhân độc lập.

![F1 ba bệnh yếu](weak_class_f1.png)

## Chuyển nguồn — một hệ thống fold 0

| Nguồn / vai trò lịch sử | Ảnh | Bản đang giữ Acc / Macro F1 | Đầu riêng Acc / Macro F1 |
|---|---:|---:|---:|
| dermacon_all | 986 | 36.31% / 31.62% | 37.02% / 32.51% |
| dermacon_historical_aux_train | 590 | 33.39% / 26.18% | 34.92% / 27.42% |
| dermacon_historical_validation | 213 | 45.07% / 42.41% | 43.66% / 41.67% |
| dermacon_historical_official_test | 183 | 35.52% / 30.75% | 36.07% / 31.37% |
| skindisnet_transfer | 723 | 21.30% / 6.63% | 25.17% / 7.58% |

DermaCon 590/213/183 giữ vai trò lịch sử và cùng thuộc 986 ảnh, không cộng trùng. Official test không có Lupus. SkinDisNet chỉ Eczema/Tinea; Macro F1 cố định tám nhãn, F1 trung bình hai nhãn có ảnh thật bằng bốn lần con số này. Nguồn đã khảo sát nhiều lần, không phải test bệnh nhân mới hay trung bình năm hệ thống.

## Kiểm chứng

Fit lại độc lập **7 đầu**, tham số khớp hoàn toàn; dựng lại cặp từ 4.043 dự đoán giữ riêng trong train, 27 bộ chỉ số, 2.885 ảnh và 11,540 lượt kiểm mask Cancer. Kiểm tra trực tiếp `sklearn.predict_proba`, bao gồm quy ước binary multinomial. [Biên bản độc lập](independent_review.json). Toàn bộ 196 kiểm thử đạt; PASS là tính nhất quán mã/phép tính, không phải chứng nhận độ chính xác lâm sàng.

[Giao thức](protocol.json), [khóa cặp trước inner](pairs_locked.json), [khóa lựa chọn](selection_locked.json), [chỉ số/ma trận đầy đủ](results.json), [đổi đúng/đổi sai](transitions.json).

## Bước có thể thử riêng tiếp theo

Số ảnh train hai đầu cặp lệch rõ (206 Lupus so 446 Acne; 639 Psoriasis hoặc 688 Tinea so 1.072 Eczema). Có thể thử **cân khối lượng loss hai bệnh 50/50**, đối chứng bằng tái fit đúng đầu binary ở đây; giữ nguyên cặp đã khóa, đặc trưng/scaler/C/ngưỡng và điều kiện. Đây là giả thuyết, chưa có kết quả cân loss trong báo cáo này.
