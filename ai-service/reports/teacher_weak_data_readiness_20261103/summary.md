# Lượt 255 — rà dữ liệu ba bệnh yếu và việc cần làm

Ngày 03/11/2026. **Đã đối chiếu ảnh/metadata với đúng tập fit của ba phần hiện tại và tạo danh sách rà riêng. Chưa train mới, chưa sửa nhãn, chưa tăng điểm.** Đây là bước chuyển từ tiếp tục thử công thức sang xác định việc dữ liệu có thể xử lý được.

## Kết quả chính

Đã kiểm byte SHA và pixel RGB **4,031 ảnh cũ** trong cohort hiện tại. Có **8,062 lượt thuộc tập fit** do mỗi ảnh được học ở các phần khác nhau; không phải 8,062 ảnh riêng hoặc ảnh mới. Metadata đối chiếu từ inventory5.937ảnh đã audit ngày21/10. Không lấy dự đoán đúng/sai, loss hoặc điểm query để chọn ảnh rà.

| Phần | Ảnh fit | Lupus SCIN: ảnh / mã ca nguồn | Psoriasis SCIN: ảnh / mã ca | Tinea SCIN: ảnh / mã ca | Ảnh fit cần xem metadata |
|---|---:|---|---|---|---:|
| fold1_cv0 | 2699 | 1 / 1 | 53 / 26 | 52 / 24 | 60 |
| fold1_cv1 | 2697 | 8 / 4 | 58 / 25 | 59 / 26 | 63 |
| fold1_cv2 | 2666 | 9 / 5 | 47 / 21 | 35 / 20 | 57 |


Ba danh sách có **90 ảnh riêng biệt**. Số dòng giữa các phần có thể lặp cùng ảnh. Danh sách bao gồm Lupus/Psoriasis/Tinea và Eczema để rà nhãn cạnh tranh; không gọi tất cả là ảnh bệnh yếu bị gán sai. Ô bác sĩ/người rà, nhãn xác nhận và bằng chứng đều để trống.

Số tín hiệu giao nhau fit–query theo SHA/pixel/nhóm/mã ca nguồn: **0**. Số cụm fit chứa nhiều nhãn dataset theo bốn khóa này, tính riêng từng phần: **0**. Hai số là phép kiểm dữ liệu đã có; cụm cùng cảnh/mã ca có nhiều nhãn vẫn có thể hợp lệ, không tự kết luận nhãn sai. Mã ca SCIN và nhóm dHash/cùng cảnh chưa phải mã bệnh nhân xác minh.

## Máy đã kiểm tra và phần còn chưa biết

- Đã kiểm file khớp SHA, đọc được RGB, kích thước và pixel khớp inventory; đúng path/nhãn/source/group với manifest hiện tại.
- Đã thống kê nguồn và mức đại diện; nhãn differential đồng hạng được đưa vào hàng đợi riêng trong **đúng fit của từng phần**.
- Chưa xác nhận ảnh thực sự mắc bệnh nào. SCIN có nhãn phân biệt hồi cứu; nhãn thư mục nguồn cũ thiếu bằng chứng chẩn đoán trong metadata. Thiếu bằng chứng không đồng nghĩa tất cả nhãn sai.
- Trọng số annotation dưới0,75 chỉ kế thừa cờ mô tả cũ, không phải xác suất bệnh và không dùng tự loại ảnh hoặc đổi nhãn.

## Giờ làm gì

1. **Giữ checkpoint và kết quả cũ**, tách rõ nhánh từng tăng ba bệnh với các thử nghiệm chưa đạt. Không ghi rằng điểm tổng đã tăng sau lượt254.
2. **Xử lý danh sách metadata dưới đây trước khi train tiếp.** Đối chiếu nguồn gốc, mã ca, quy tắc ánh xạ và bằng chứng nhãn. Máy có thể kiểm phần kỹ thuật; nhãn chẩn đoán cần căn cứ chuyên môn. Nếu chưa có người/căn cứ xác nhận thì giữ nhãn và trạng thái chưa rà.
3. **Ưu tiên dữ liệu bổ sung có nhãn và quyền dùng rõ ràng**, nhất là Lupus dạng ảnh bệnh nhân tự chụp. Bảng một ảnh/một mã ca ở fit0 cho thấy mức đại diện rất ít, chưa chứng minh đây là nguyên nhân duy nhất của điểm thấp. Không đếm augmentation thành ca mới, không ép ảnh bệnh khác vào tám nhãn.
4. Chỉ khi có thay đổi dữ liệu hợp lệ mới khóa một đối chứng train mới: cùng split/cấu hình, ghi ảnh/nhãn nào thay đổi và căn cứ. Chọn bằng phần phát triển riêng; so Accuracy/Macro F1/precision–recall–F1 tám bệnh và Recall SkinCancer. Các query hiện tại đã xem nhiều lần, không được gọi thành test mù mới.

Việc rà không tự tạo mức tăng điểm. Nếu chưa có dữ liệu/nhãn tốt hơn, có thể gửi thầy **báo cáo tiến độ có cả kết quả tăng và thử nghiệm thất bại**, kèm giới hạn dữ liệu cụ thể. Không cần tuyên bố đã tối ưu xong để trình bày phần nghiên cứu đã làm.


## fold1_cv0 — chỉ thống kê phần fit

| Bệnh | Nguồn | Ảnh | Nhóm proxy | Mã ca nguồn có sẵn | Ảnh có nhãn đầu đồng hạng | Ảnh thiếu bằng chứng chẩn đoán trong metadata nguồn cũ |
|---|---|---:|---:|---:|---:|---:|
| Lupus | original_train | 138 | 129 | 0 | 0 | 138 |
| Lupus | SCIN | 1 | 1 | 1 | 0 | 0 |
| Psoriasis | original_train | 363 | 355 | 0 | 0 | 363 |
| Psoriasis | SCIN | 53 | 26 | 26 | 15 | 0 |
| Tinea | original_train | 406 | 395 | 0 | 0 | 406 |
| Tinea | SCIN | 52 | 24 | 24 | 8 | 0 |
| Eczema | original_train | 434 | 428 | 0 | 0 | 434 |
| Eczema | SCIN | 306 | 137 | 137 | 37 | 0 |

Số mã ca bằng0 ở nguồn cũ nghĩa là không có mã trong metadata, không nghĩa0bệnh nhân. Không dùng số nhóm proxy làm số bệnh nhân đã xác minh.

Có 60 ảnh trong danh sách. [Danh sách ảnh fit](fold1_cv0_fit_review.md) và [JSONL](fold1_cv0_fit_review.jsonl).

Các lý do rà: equal_top_differential_annotations: 60

## fold1_cv1 — chỉ thống kê phần fit

| Bệnh | Nguồn | Ảnh | Nhóm proxy | Mã ca nguồn có sẵn | Ảnh có nhãn đầu đồng hạng | Ảnh thiếu bằng chứng chẩn đoán trong metadata nguồn cũ |
|---|---|---:|---:|---:|---:|---:|
| Lupus | original_train | 132 | 127 | 0 | 0 | 132 |
| Lupus | SCIN | 8 | 4 | 4 | 0 | 0 |
| Psoriasis | original_train | 360 | 354 | 0 | 0 | 360 |
| Psoriasis | SCIN | 58 | 25 | 25 | 10 | 0 |
| Tinea | original_train | 392 | 384 | 0 | 0 | 392 |
| Tinea | SCIN | 59 | 26 | 26 | 7 | 0 |
| Eczema | original_train | 412 | 406 | 0 | 0 | 412 |
| Eczema | SCIN | 288 | 139 | 139 | 46 | 0 |

Số mã ca bằng0 ở nguồn cũ nghĩa là không có mã trong metadata, không nghĩa0bệnh nhân. Không dùng số nhóm proxy làm số bệnh nhân đã xác minh.

Có 63 ảnh trong danh sách. [Danh sách ảnh fit](fold1_cv1_fit_review.md) và [JSONL](fold1_cv1_fit_review.jsonl).

Các lý do rà: equal_top_differential_annotations: 63

## fold1_cv2 — chỉ thống kê phần fit

| Bệnh | Nguồn | Ảnh | Nhóm proxy | Mã ca nguồn có sẵn | Ảnh có nhãn đầu đồng hạng | Ảnh thiếu bằng chứng chẩn đoán trong metadata nguồn cũ |
|---|---|---:|---:|---:|---:|---:|
| Lupus | original_train | 146 | 140 | 0 | 0 | 146 |
| Lupus | SCIN | 9 | 5 | 5 | 0 | 0 |
| Psoriasis | original_train | 337 | 331 | 0 | 0 | 337 |
| Psoriasis | SCIN | 47 | 21 | 21 | 7 | 0 |
| Tinea | original_train | 382 | 371 | 0 | 0 | 382 |
| Tinea | SCIN | 35 | 20 | 20 | 3 | 0 |
| Eczema | original_train | 428 | 420 | 0 | 0 | 428 |
| Eczema | SCIN | 262 | 122 | 122 | 47 | 0 |

Số mã ca bằng0 ở nguồn cũ nghĩa là không có mã trong metadata, không nghĩa0bệnh nhân. Không dùng số nhóm proxy làm số bệnh nhân đã xác minh.

Có 57 ảnh trong danh sách. [Danh sách ảnh fit](fold1_cv2_fit_review.md) và [JSONL](fold1_cv2_fit_review.jsonl).

Các lý do rà: equal_top_differential_annotations: 57

## Kiểm chứng và giới hạn

Reviewer độc lập dựng lại các cụm bằng sort/groupby, tính lại24ô thống kê, xác nhận180dòng fit cần rà và90ảnh riêng biệt; kiểm ô xác nhận vẫn trống. Đọc lại toàn bộ4031ảnh và SHA/pixel RGB, đối chiếu manifest/vai trò theo path/source/label/group. Protocol/code/reviewer/finisher/nguồn khóa trước khi đếm; không dùng file dự đoán hay điểm model.

PASS chỉ xác nhận dữ liệu và phép đếm. Không có rà nhãn lâm sàng mới, không thêm ảnh, fit model, tính điểm chất lượng model, chọn checkpoint hay đổi API/registry. Hai nguồn/nhóm có mức đại diện khác nhau; bảng không tách riêng tác động nhãn, nguồn, độ khó hay kiểu ảnh. Giữ nguyên tám bệnh và toàn bộ file gốc. Việc bổ sung nguồn nào chưa được thực hiện ở lượt này.

[Protocol](protocol.json), [kết quả](results.json), [ảnh kiểm byte/pixel](image_integrity.json), [kiểm chứng](independent_review.json).
