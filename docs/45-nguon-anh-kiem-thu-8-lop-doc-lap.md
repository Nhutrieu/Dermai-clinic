# Nguồn ảnh cho phép thử 8 bệnh độc lập

## Kết luận hiện tại

Kết quả 83,87% trên 564 ảnh test cố định và 75,00% trên 240 ảnh SCIN cho ensemble ba mô hình là kết quả nghiên cứu. Chưa có điểm accuracy 8 bệnh trên một bộ ảnh mới, đủ tám lớp, được khóa trước khi chọn mô hình. Không dùng kết quả phân loại ung thư so với lành tính trên SLICE-3D làm điểm accuracy 8 bệnh.

## Nguồn có thể khảo sát tiếp

| Nguồn | Điểm hữu ích | Điều kiện trước khi chấm 8 bệnh |
| --- | --- | --- |
| Fitzpatrick17k | 16.577 ảnh lâm sàng, 114 bệnh, có CSV nhãn và URL ảnh gốc | Metadata đã được rà ở [báo cáo nguồn trước](ai-research-summary.md): không có nhãn Tinea, Candidiasis, Warts. Vì vậy không thể dùng làm test đủ tám lớp; ảnh từ atlas còn cần kiểm tra trùng nguồn và quyền sử dụng. Giấy phép CC BY-NC-SA 3.0. |
| SCIN | Hơn 10.000 ảnh, nhãn bác sĩ theo từng ca | Đã dùng để thăm dò; thiếu độ phủ chắc chắn cho cả tám lớp và có các ảnh trùng được nhóm phát hành ghi nhận. Không coi kết quả SCIN cũ là test mới. |
| DDI | Ảnh đa dạng sắc da, nhãn được xác nhận bằng giải phẫu bệnh | Phù hợp hơn với đánh giá ung thư và công bằng giữa nhóm sắc da; điều khoản chỉ cho nghiên cứu phi thương mại. Không mặc định đủ tám bệnh. |

## Sàng lọc thêm nguồn công bố năm 2026 (10/10/2026)

| Nguồn | Điều đã xác minh từ trang công bố | Vì sao chưa dùng làm test tám bệnh |
| --- | --- | --- |
| [Skin Disease Classification Dataset, Mendeley Data](https://data.mendeley.com/datasets/schhndjbjp/1) | Trang mô tả ghi 1.000 ảnh, nhưng phần tệp ghi 878 ảnh, 10 nhóm; có Atopic Dermatitis và một nhãn gộp “Tinea Ringworm Candidiasis”, giấy phép CC BY 4.0. | Nhãn nấm gộp không tách được Tinea với Candidiasis; không có các lớp Acne, Lupus, Psoriasis, Warts trong danh sách 10 nhóm. Trang mô tả không công bố mã người để xác minh split. Cần làm rõ chênh số ảnh trước khi dùng cho phép đo nhỏ hơn. |
| [32 Curated Categories of Skin Disease Images, Mendeley Data](https://data.mendeley.com/datasets/pgd42j3h5c/1) | Có lupus dạng discoid, psoriasis, Tinea corporis và một số ung thư; trang công bố nói ảnh được tổng hợp lại từ hai bộ Kaggle, giấy phép trang ghi CC BY 4.0. | Thiếu Acne, Eczema, Candidiasis, Warts trong bảng lớp; nguồn gốc tổng hợp cần kiểm tra trùng ảnh/quyền gốc và không có mã người được nêu trên trang. |
| [An Image Dataset of Common Skin Diseases of Bangladesh](https://arxiv.org/abs/2603.25229) | Bài báo nêu 1.612 ảnh nhưng chỉ 250 ảnh gốc khác nhau, còn lại tăng cường; năm bệnh gồm Eczema và Tinea Ringworm. | Chỉ khớp tối đa hai nhóm trong tám nhóm DermAI; phải tách ảnh gốc khỏi ảnh tăng cường trước mọi kiểm thử. |
| [DermNet dataset cho AI](https://dermnetnz.org/dermatology-image-dataset) | Trang chính thức nêu trên 60.000 ca, hơn 600 bệnh và ảnh điện thoại; cấp phép có phí theo ảnh, cần liên hệ để nhận mẫu. | Chưa có quyền truy cập, danh sách ca/nhãn tám bệnh và mã người để khóa tập; ảnh trên website công cộng không phải bộ dữ liệu AI được cấp phép. |
| [KODAS clinical photography archive](https://www.kodas.org/data.html) | Trang dự án mô tả trên 30.000 ảnh lâm sàng có mã ICD-10/SNOMED, cấp quyền qua hợp đồng sử dụng dữ liệu. | Chưa được cấp dữ liệu; trang công khai không xác nhận đủ số ca từng nhóm DermAI hay mã ca ổn định để tách người. Cần hỏi điều kiện và xem metadata trước khi cân nhắc. |
| [Derm104](https://pmc.ncbi.nlm.nih.gov/articles/PMC11088239/) | Bài báo gốc mô tả 4.483 ảnh/104 bệnh, ghép ảnh từ SD-198 và một atlas; có eczema, psoriasis, acne và melanoma trong mô tả. | Bài báo không cung cấp bằng chứng về mã người để tách ca, cũng không liệt kê số ảnh khớp đủ tám nhóm DermAI. Vì là tập ghép lại, phải kiểm tra trùng nguồn với dữ liệu cũ trước khi dùng. Chưa coi đây là test mới. |

Đây là sàng lọc dựa trên mô tả công bố, chưa tải và rà từng ảnh; không kết luận các nguồn này vô dụng cho nghiên cứu từng lớp. Chúng không giải quyết được yêu cầu **một** test mới đủ tám nhãn, tách người và không trùng nguồn đã học.

## Điều kiện để công bố chỉ số tổng mới

1. Chốt trước bảng ánh xạ tám bệnh và tiêu chí loại ảnh không rõ nhãn. Không ép bệnh khác vào một trong tám lớp.
2. Khóa danh sách ảnh và nhãn trước khi xem kết quả mô hình. Không dùng bộ này để chọn trọng số ensemble hoặc ngưỡng.
3. Loại ảnh trùng bằng hash chính xác và hash cảm nhận so với train, validation và các test cũ. Nếu có mã bệnh nhân hoặc ca, tách theo bệnh nhân hoặc ca.
4. Chấm B0 hiện hành và ensemble ba mô hình trên cùng ảnh. Báo cáo accuracy, macro F1, recall theo từng bệnh, ma trận nhầm lẫn, số ảnh mỗi lớp và khoảng tin cậy. Nêu riêng recall SkinCancer và trường hợp mô hình từ chối dự đoán.
5. Chỉ nói mô hình mới chính xác hơn khi chênh lệch trên test độc lập có ý nghĩa thực tế, không đổi lấy việc bỏ sót thêm các ca nguy hiểm, và giấy phép dữ liệu/trọng số cho phép cách triển khai dự kiến.

## Nguồn gốc thông tin

- Fitzpatrick17k: https://github.com/mattgroh/fitzpatrick17k/blob/main/README.md
- SCIN: https://github.com/google-research-datasets/scin/blob/main/README.md
- DDI: https://ddi-dataset.github.io/index.html

Danh sách tám nhãn đã có trong [giao thức holdout](../ai-service/reports/paper_ensemble_benchmark/pad_ufes_image_fingerprints.json). Fitzpatrick17k đã được kiểm tra ở mức metadata, nên không lặp lại bước đó như một nguồn test tám lớp. Script audit mới quét ảnh ở các nguồn ngoài đã thử, ngoài train/test và manifest PAD. Việc cần làm tiếp là tìm một nguồn khác có đủ nhãn đúng nghĩa, mã ca/người và ảnh gốc có quyền sử dụng rõ; nếu thiếu lớp, báo thiếu lớp thay vì công bố accuracy tám bệnh.

## Rà soát thêm khi không có bộ ảnh từ giảng viên (10/10/2026)

Nhóm tự tìm dữ liệu công khai; không cần giả định giảng viên có ảnh để cung cấp. Các nguồn đã tải và kiểm tra trong dự án gồm DermaCon-IN, SkinDisNet, DermatoNet, PAD-UFES-20 và các nguồn khác ở các báo cáo liên quan. DermatoNet đã được chấm trước đó trên 1.641 ảnh sau lọc trùng, chỉ cho phép đánh giá cờ `SkinCancer` trên một số loại tổn thương, không tạo ra accuracy tám lớp mới.

| Nguồn vừa rà soát | Kết quả sàng lọc |
| --- | --- |
| [SkinDis-India v2](https://data.mendeley.com/datasets/r7kdbj2wym/2) | Công bố ảnh psoriasis và vitiligo, CC BY 4.0. Chỉ psoriasis khớp một nhãn trong tám nhãn; trang công bố không xác nhận mã bệnh nhân hay số ảnh gốc tách khỏi ảnh tăng cường. Có thể khảo sát riêng psoriasis sau khi kiểm tra tệp, không thể dùng làm điểm tổng tám bệnh. |
| [MedPix, NLM](https://catalog.data.gov/dataset/medpix) | Danh mục chính thức mô tả dữ liệu theo ca và đường API Open-i. Chưa xác minh được số ảnh da có đủ tám chẩn đoán, phép ánh xạ nhãn và khả năng lấy ảnh qua API; chưa khóa được manifest nên chưa chấm mô hình. |
| [DermatoNet v2](https://data.mendeley.com/datasets/g5bj76p2z3/2) | Trang phiên bản mới vẫn mô tả 1.719 ảnh và sáu chẩn đoán tổn thương như nguồn DermatoNet đã dùng trong [đánh giá trước](ai-research-summary.md). Không coi việc tăng phiên bản trang là một bộ test độc lập mới khi chưa đối chiếu hash ảnh. |

Chưa có nguồn mới trong lần rà soát này đáp ứng đủ tám nhãn chính xác, ca độc lập và kiểm tra trùng với dữ liệu đã học. Vì vậy không cộng các bộ ảnh khác nhãn vào một mẫu số để tạo một tỷ lệ accuracy tổng. Kết quả ngoài nguồn hiện có được giữ theo từng nguồn và từng mục tiêu đánh giá.
