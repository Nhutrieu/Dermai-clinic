# Lượt 293 — Vì sao ba bệnh yếu chưa tăng sau khi lặp seed?

**Đây là phân tích nguyên nhân trên cache đã khóa, không phải phương án AI mới được chọn hoặc lần tăng điểm mới.** Không train, không chạy CNN trên ảnh, không đổi dự đoán và không tìm thêm ngưỡng. Phân tích cùng 2.699 ảnh OOF lịch sử / 2.407 nhóm ảnh có sẵn, ba fold cố định. Nguồn này đã được dùng phát triển thích ứng nhiều lần; không gọi là test mù, bệnh nhân mới hay điểm tổng 5.937 ảnh.

## Điểm cần hiểu trước

Lượt 290/292 chỉ cho phép **thêm nhãn Lupus** và giữ các nhãn Lupus/SkinCancer sẵn có. Do đó Recall Psoriasis và Tinea không thể tăng qua luật này: ảnh chưa được nhận đúng hai bệnh ấy không có tuyến đổi sang Psoriasis/Tinea. Dự đoán Psoriasis/Tinea có thể đổi sang Lupus nên recall còn có thể giảm; precision có thể tăng hoặc giảm. Bảng chỉ số phải kiểm tra điều này, không thể suy từ việc hai CNN được train đủ tám nhãn.

Phần tăng Lupus của seed42 chưa lặp ở seed43. Phân tích này tách: CNN chưa đưa nhãn đúng vào top-1, CNN đã đúng nhưng luật bất đồng/margin chặn, luật chỉ-Lupus chặn hai bệnh khác, hoặc CNN6 không xác nhận. Không sửa luật sau khi đọc nhãn thật.

## Độ phủ nhãn đúng của các đầu ra có sẵn

Năm đầu ra là CE42, CB42, CE43, CB43 (CNN8 native) và CNN6 native đúng fold. CNN6 chỉ dùng ba đầu Lupus/Psoriasis/Tinea; không ép OtherRest thành một bệnh tám nhãn. Bốn CNN8 và CNN6 dùng cùng họ ConvNeXt/dữ liệu, có lỗi tương quan; không coi là năm chuyên gia độc lập.

| Bệnh | Đúng ở nền 288 | Lỗi còn lại | Có ≥1/5 đầu ra top-1 đúng trong lỗi | Cả 5 đều sai trong lỗi | Cả CB42 và CB43 cùng đúng trong lỗi |
|---|---:|---:|---:|---:|---:|
| Lupus | 62/139 | 77 | 12 | 65 | 1 |
| Psoriasis | 245/416 | 171 | 42 | 129 | 6 |
| Tinea | 247/458 | 211 | 38 | 173 | 2 |

**Cột “có ≥1 đầu ra đúng” dùng nhãn thật để soi lỗi (oracle), không phải độ chính xác ensemble hoặc số ảnh chắc chắn sửa được.** Muốn chọn đúng đầu ra trên ảnh chưa biết nhãn cần một phương pháp được học/chọn chỉ trong train và kiểm ngoài nhóm. Cột “cả 5 sai” cũng chỉ giới hạn ngân hàng top-1 này; không chứng minh ảnh không thể phân loại hay bệnh không học được.

| Đầu ra cố định — cùng 2.699 ảnh | Accuracy | Macro F1 | Recall Lupus | Recall Psoriasis | Recall Tinea | Recall SkinCancer |
|---|---:|---:|---:|---:|---:|---:|
| parent288 | 66,54% | 65,45% | 44,60% | 58,89% | 53,93% | 73,00% |
| ce42 | 66,17% | 64,70% | 40,29% | 58,65% | 53,28% | 73,00% |
| cb42 | 66,25% | 65,52% | 46,76% | 60,10% | 54,15% | 72,00% |
| ce43 | 66,99% | 65,52% | 38,13% | 63,70% | 52,62% | 74,00% |
| cb43 | 66,43% | 65,03% | 39,57% | 62,74% | 48,91% | 74,33% |
| confirmed42 | 66,58% | 65,51% | 45,32% | 58,89% | 53,93% | 73,00% |
| confirmed43 | 66,54% | 65,45% | 44,60% | 58,89% | 53,93% | 73,00% |

## CE và cân bằng lớp: thay đổi trực tiếp theo seed

Đơn vị là **điểm phần trăm**. Khoảng 95% mô tả lấy mẫu lại nguyên 2.407 nhóm, 2.000 lượt, cùng một lượt nhóm cho mọi đầu ra. Tham số CNN/dự đoán cố định; không train lại trong bootstrap.

| So sánh CB − CE | Accuracy | Macro F1 | Recall Lupus | Recall Psoriasis | Recall Tinea |
|---|---:|---:|---:|---:|---:|
| seed 42 | +0,07 [-0,67; +0,82] | +0,82 [-0,09; +1,78] | +6,47 [+2,27; +11,19] | +1,44 [+0,00; +3,03] | +0,87 [-0,89; +2,78] |
| seed 43 | -0,56 [-1,20; +0,07] | -0,49 [-1,36; +0,47] | +1,44 [-2,31; +5,56] | -0,96 [-2,43; +0,49] | -3,71 [-5,53; -2,10] |

Khoảng bootstrap phản ánh lấy mẫu lại nhóm ảnh lịch sử, không phải bất định của quần thể seed, kiểm chứng chuyển nguồn hoặc hiệu quả lâm sàng. Không có p-value, tuyên bố kiểm định nhiều giả thuyết, chọn seed đẹp hoặc dùng khoảng này thay điều kiện chọn bản mới. Hai seed chỉ đổi cặp CNN8; nền 288 và CNN6 vẫn seed42.

## Theo từng bước lọc — seed 42

Mỗi dòng là tập con của dòng trước, chỉ xét đề xuất có đích thuộc ba bệnh yếu. “Sửa đúng/làm sai/trung tính” được tính sau khi khóa dự đoán, không dùng nhãn thật để định tuyến.

| Bước | Đề xuất còn lại | Sửa đúng | Làm sai ảnh vốn đúng | Sai → sai | Sửa Lupus | Sửa Psoriasis | Sửa Tinea |
|---|---:|---:|---:|---:|---:|---:|---:|
| CB đề xuất đổi sang một trong ba bệnh yếu | 74 | 21 | 32 | 21 | 6 | 7 | 8 |
| Cần CE và CB bất đồng | 70 | 21 | 30 | 19 | 6 | 7 | 8 |
| Giữ Cancer và margin CB dương | 68 | 20 | 30 | 18 | 5 | 7 | 8 |
| Mức tăng margin > ln(2) | 33 | 10 | 18 | 5 | 3 | 5 | 2 |
| Chỉ giữ đích Lupus | 6 | 3 | 2 | 1 | 3 | 0 | 0 |
| CNN6 xác nhận Lupus top-1 | 2 | 1 | 0 | 1 | 1 | 0 | 0 |

Mỗi lỗi của nền 288 được gán vào **điều kiện thất bại đầu tiên**, nên không cộng trùng các lý do.

| Lý do đầu tiên | Lupus | Psoriasis | Tinea |
|---|---:|---:|---:|
| CB chưa đưa ra nhãn đúng | 71 | 164 | 203 |
| CE và CB cùng đúng nên bị điều kiện bất đồng chặn | 0 | 0 | 0 |
| Nền đang là SkinCancer nên giữ | 1 | 0 | 0 |
| Margin mới không dương | 0 | 0 | 0 |
| Mức tăng margin chưa vượt ln(2) | 2 | 2 | 6 |
| Luật chỉ thêm Lupus chặn bệnh khác | 0 | 5 | 2 |
| CNN6 chưa xác nhận Lupus | 2 | 0 | 0 |
| Được nhận và sửa đúng | 1 | 0 | 0 |

## Theo từng bước lọc — seed 43

Mỗi dòng là tập con của dòng trước, chỉ xét đề xuất có đích thuộc ba bệnh yếu. “Sửa đúng/làm sai/trung tính” được tính sau khi khóa dự đoán, không dùng nhãn thật để định tuyến.

| Bước | Đề xuất còn lại | Sửa đúng | Làm sai ảnh vốn đúng | Sai → sai | Sửa Lupus | Sửa Psoriasis | Sửa Tinea |
|---|---:|---:|---:|---:|---:|---:|---:|
| CB đề xuất đổi sang một trong ba bệnh yếu | 225 | 71 | 89 | 65 | 7 | 38 | 26 |
| Cần CE và CB bất đồng | 20 | 2 | 8 | 10 | 1 | 1 | 0 |
| Giữ Cancer và margin CB dương | 19 | 2 | 8 | 9 | 1 | 1 | 0 |
| Mức tăng margin > ln(2) | 5 | 0 | 3 | 2 | 0 | 0 | 0 |
| Chỉ giữ đích Lupus | 2 | 0 | 1 | 1 | 0 | 0 | 0 |
| CNN6 xác nhận Lupus top-1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Mỗi lỗi của nền 288 được gán vào **điều kiện thất bại đầu tiên**, nên không cộng trùng các lý do.

| Lý do đầu tiên | Lupus | Psoriasis | Tinea |
|---|---:|---:|---:|
| CB chưa đưa ra nhãn đúng | 70 | 133 | 185 |
| CE và CB cùng đúng nên bị điều kiện bất đồng chặn | 6 | 37 | 26 |
| Nền đang là SkinCancer nên giữ | 0 | 0 | 0 |
| Margin mới không dương | 0 | 0 | 0 |
| Mức tăng margin chưa vượt ln(2) | 1 | 1 | 0 |
| Luật chỉ thêm Lupus chặn bệnh khác | 0 | 0 | 0 |
| CNN6 chưa xác nhận Lupus | 0 | 0 | 0 |
| Được nhận và sửa đúng | 0 | 0 | 0 |

## Theo nguồn — các lỗi còn lại của nền 288

| Bệnh | Nguồn | Lỗi còn lại | Có ≥1 top-1 đúng | Cả năm top-1 sai |
|---|---|---:|---:|---:|
| Lupus | SCIN | 1 | 0 | 1 |
| Lupus | original_train | 76 | 12 | 64 |
| Psoriasis | SCIN | 42 | 2 | 40 |
| Psoriasis | original_train | 129 | 40 | 89 |
| Tinea | SCIN | 46 | 7 | 39 |
| Tinea | original_train | 165 | 31 | 134 |

Chỉ có **một ảnh Lupus SCIN** trong 2.699 ảnh này; bảng không đủ để ước lượng kết quả Lupus trên SCIN. Không có ảnh/nhãn bác sĩ mới. “Nhóm” là mã ca/cảnh/ảnh có sẵn để giảm rò rỉ, chưa phải định danh bệnh nhân độc lập đã xác minh.

## Hướng làm tiếp được phép rút ra

1. Muốn tăng cả ba bệnh, thiết kế tiếp theo phải có đề xuất/đường nhận nhãn Psoriasis và Tinea; không thể kỳ vọng luật chỉ-Lupus làm recall hai bệnh ấy tăng.
2. Có đề xuất đúng trong ngân hàng chỉ là lý do nghiên cứu bộ chọn/ghép bằng train lồng nhau. Không bỏ điều kiện bảo vệ chỉ vì đã nhìn thấy một số ca sửa đúng; phải tính cả số ảnh làm sai thêm và kiểm từng fold.
3. Những lỗi cả năm top-1 đều sai cần cải thiện biểu diễn/nguồn ảnh hoặc bộ sinh đề xuất, thay vì chỉ đổi cách chọn top-1 của các đầu ra này. Cần rà nhãn và bổ sung ví dụ có nhãn đáng tin ở nguồn thiếu; tăng cường ảnh không tạo bệnh nhân hoặc nhãn độc lập.

Lượt này **không chọn** một công thức theo nhãn thật, không gộp seed42/43 hoặc nới guard; `selected=None`, `promotion_eligible=False`. Giữ ứng viên nghiên cứu 288 và toàn bộ kết quả 290/292 như đã ghi. Chưa có tăng chỉ số được xác nhận thêm, chưa đổi API.

## Kiểm chứng

Ba kiểm thử đạt: funnel/biên strict ln(2)/Cancer/identity; trọng số bootstrap giữ nguyên nhóm; chỉ số ở ma trận biết trước và lớp vắng. Reviewer tái dựng 13495 hàng cache native từ 15 file holdout của 281/289/292/271, tính lại 5398 lượt qua funnel, 459 ca lỗi ba bệnh, 2000 lượt nhóm / 14000 vector chỉ số / 168000 giá trị chỉ số và 60 khoảng chênh. Sai số vector bootstrap lớn nhất 2.22e-16. Không chạy lại CNN hoặc train lại model; dựa trên SHA và chứng từ forward độc lập đã hoàn tất ở các lượt nguồn.

Điểm tổng 5.937, API EfficientNet-B0 đơn, registry, 126 script train và 96 script gốc giữ nguyên. Không chấm query 1.332 ảnh, hai ownpool khác hoặc validation chính. PASS kiểm chứng phép tính không phải xác nhận hiệu quả chẩn đoán.

![Độ phủ và độ chênh CE/CB](seed_pair_error_diagnosis.png)

[Protocol](protocol.json), [kết quả](results.json), [ca lỗi](error_cases.json), [kiểm chứng](independent_review.json).
