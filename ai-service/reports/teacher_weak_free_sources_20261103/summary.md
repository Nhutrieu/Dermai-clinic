# Lượt 256 — tìm nguồn ảnh miễn phí và rà SkinDis-India

Ngày 03/11/2026. **Đã tải một nguồn chưa có trong kho cục bộ và tạo 25 ảnh đại diện Psoriasis để rà tiếp. Chưa đưa vào train hoặc test, chưa có điểm mới.** Chỉ xét nguồn miễn phí theo yêu cầu của nhóm.

## Nguồn mới đã kiểm tệp

[SkinDis-India v2](https://data.mendeley.com/datasets/r7kdbj2wym/2) công bố hai nhãn Psoriasis/Vitiligo và giấy phép CC BY4.0. ZIP84.460.167byte khớp SHA do Mendeley công bố. Tên nguồn có “Augmented”; tệp chứa nhiều tên `_frame_N`, không có bảng ánh xạ ảnh gốc–biến thể hoặc mã bệnh nhân. Mô tả nguồn nói ảnh lâm sàng, chưa xác minh mới từng chẩn đoán bằng bác sĩ trong dự án.

| Mục kiểm tra | Kết quả |
|---|---:|
| Tệp ảnh trong ZIP | 1594 |
| Ảnh mang nhãn thư mục Psoriasis | 889 |
| Ảnh mang nhãn thư mục Vitiligo | 705 |
| Nhóm tên tệp Psoriasis sau gom biến thể | 31 |
| Thành phần Psoriasis sau nối tên/hash/dHash | 29 |
| Ảnh Psoriasis có dấu hiệu trùng nguồn bảo vệ hoặc Vitiligo | 12 |
| Thành phần bị cách ly do liên quan ảnh trùng | 4 |
| Ảnh đại diện tạm lưu để rà tiếp | 25 |
| Ảnh được thêm vào train hiện hành | 0 |
| Ảnh được thêm vào đánh giá | 0 |


**Không diễn giải 889 tệp Psoriasis thành 889 ca/bệnh nhân mới.** Nhóm tên tệp và thành phần dHash chỉ là proxy. Những góc chụp hoặc ảnh gốc khác nhau của cùng người vẫn có thể chưa nối được. Tổng bệnh nhân mới xác minh: chưa biết. Vitiligo không thuộc tám nhãn gốc, không gộp vào một bệnh khác.

## Cách giảm lặp và bảo vệ dữ liệu đã dùng

Đọc toàn bộ1594JPEG trực tiếp từ ZIP, kiểm byte SHA, pixelRGB sau EXIF, kích thước và dHash. Với Psoriasis, nối cùng tiền tố tên sau bỏ `_frame_N`, hậu tố bản sao `(n)` và `_n`; mọi `frame_N` không có tiền tố được gom chung một nhóm chưa rõ gốc. Nối thêm byte/pixel trùng và dHash Hamming≤3. Duyệt thành phần liên thông để không tách những ảnh đã biết liên quan.

So từng ảnh Psoriasis với **19635 bản ghi bảo vệ cũ** gồm các nguồn train/validation/test đã audit và kho train phụ; so cả705ảnh Vitiligo trong ZIP. Một ảnh chạm hash/dHash bảo vệ làm cách ly toàn bộ thành phần liên quan. Trong các path bảo vệ,19438còn là file cục bộ; 197là path đã xóa/đường dẫn thành viên archive hoặc không còn tại máy. Vẫn bảo vệ bằng fingerprint lịch sử và ghi rõ giới hạn; không khôi phục dữ liệu nhiệm vụ đã bỏ.

Mỗi thành phần không bị cách ly lấy **một đại diện cố định theo SHA nhỏ nhất**, không chọn bằng dự đoán AI hoặc điểm model. Các bản sao JPEG nguyên byte nằm ở `SkinDisease/sources/skindis_india_v2/review_candidates`; chỉ là ứng viên tạm. Manifest giữ `training_eligible=False`, `evaluation_eligible=False`, mã bệnh nhân null và chưa xác nhận chẩn đoán mới. Cần một phép thử riêng khóa vai trò nguồn, nhóm và đối chứng trước khi dùng chúng làm train phụ; không thay manifest cũ.

## Các nguồn khác đã đối chiếu

| Nguồn | Quyết định lượt này |
|---|---|
| [SkinDis-India v2](https://data.mendeley.com/datasets/r7kdbj2wym/2) | Nguồn chưa có trong kho cục bộ; đã tải để rà Psoriasis. Có Vitiligo ngoài tám nhãn và nhiều tên frame, cần gom ảnh liên quan. CC BY 4.0 theo bản ghi nguồn; chưa admit train/test. |
| [32 Curated Categories](https://data.mendeley.com/datasets/pgd42j3h5c/1) | Có tên Lupus dạng discoid/Psoriasis/Tinea corporis nhưng nguồn tổng hợp Kaggle, trộn ảnh lâm sàng và soi da. Chưa xác minh nhãn gốc/quyền gốc/ca/trùng; chưa thêm vào dữ liệu. |
| [SkinDiseaseBD v3](https://data.mendeley.com/datasets/9ggd3shdr7/3) | Nguồn đã tải trước, không tính ảnh mới. ZIP197ảnh raw tên phẳng chưa có ánh xạ nhãn từng ảnh đủ rõ; không tự gán Tinea bằng AI hoặc lấy ảnh tăng cường làm ca mới. |
| [DermaCon-IN](https://doi.org/10.7910/DVN/W7OUZM) | Nguồn đã dùng trong kho train phụ; chưa có bằng chứng một phiên bản trang tạo ảnh mới. Không cộng lại590ảnh train cũ thành nguồn bổ sung mới. |
| [Fitzpatrick17k-C](https://zenodo.org/records/11101338) | 217ảnh Lupus và321ảnh Psoriasis sau audit đã có trong các pilot trước. Không tính lại là ảnh mới hoặc ảnh được xác nhận lâm sàng mới. |
| [SCIN](https://github.com/google-research-datasets/scin) | Nguồn đã dùng. Không nới điều kiện nhãn để tăng số lượng hoặc đổi ảnh differential thành chẩn đoán chắc chắn. |
| [MMDLS Lupus study](https://onlinelibrary.wiley.com/doi/10.1111/jdv.20031) | Bài nghiên cứu Lupus nói dữ liệu không công khai; có thể xin qua tác giả và hội đồng dữ liệu. Chưa có quyền tải; chưa gửi yêu cầu hoặc liên hệ thay nhóm. |
| [Siriraj Psoriasis/dermatophytosis/eczema study](https://www.nature.com/articles/s41598-025-29562-6) | Ảnh phù hợp hướng nghiên cứu nhưng dữ liệu chỉ cung cấp khi yêu cầu tác giả. Chưa có kho tải công khai được xác minh; không báo là đã có ảnh. |
| [Psorcast](https://datacatalog.med.nyu.edu/dataset/10718) | Có ảnh tự chụp và dữ liệu qua Synapse; mục công bố miễn phí không tự chứng minh tải được một tập ảnh gốc kèm nhãn đủ cho đề tài. Chưa có lô ảnh mới được xác minh. |
| [DermNet AI dataset](https://dermnetnz.org/dermatology-image-dataset) | Trang chính thức nêu có phí. Loại khỏi hướng tìm nguồn miễn phí; không dùng nhãn gộp Lupus và các bệnh mô liên kết từ bản reupload làm Lupus riêng. |


Danh sách là kết quả sàng lọc có giới hạn, không kết luận không còn nguồn miễn phí nào khác. Các phiên bản trang mới chưa được tính thành ảnh mới nếu chưa đối chiếu hash. Nguồn Lupus/Tinea tải ngay, có nhãn phù hợp và đủ điều kiện bổ sung chưa được xác minh thêm trong lượt này.

## Việc tiếp theo có cơ sở

1. Rà ảnh đại diện và metadata của nguồn SkinDis-India; làm rõ ảnh gốc/biến thể và nhóm ca nếu có tài liệu nguồn. Cờ ảnh cần rà không tự xác nhận chẩn đoán.
2. Nếu chấp nhận dùng ở mức nghiên cứu với nhãn nguồn và giới hạn đã ghi, đăng ký một thử nghiệm **train phụ Psoriasis riêng**: đối chứng cùng encoder/seed/loss/augmentation/lịch học, giữ số lượt và cách lấy mẫu rõ ràng, chỉ thay dữ liệu phụ; toàn bộ nguồn chưa dùng làm test độc lập. Không chỉ tăng số ảnh trong báo cáo bằng cách cộng tất cả frame.
3. Báo riêng tác động lên Lupus/Psoriasis/Tinea/Eczema và SkinCancer; một nguồn chỉ có Psoriasis không tự giải quyết Lupus hoặc Tinea. Chưa mở trial mới trong lượt sàng lọc này.

## Kiểm chứng và giới hạn

Reviewer tự tính lại fingerprint của1594ảnh, dùng popcount bằng bảng byte NumPy để kiểm toàn bộ cặp bảo vệ, dựng lại thành phần bằng BFS khác UnionFind producer và kiểm25bản sao đại diện bằng nguyên byte trong ZIP. SHA nguồn/code/reviewer/finisher khóa trước giai đoạn tính trùng; tên thư mục ZIP đã được xem thăm dò trước đăng ký và được khai báo. Không đọc dự đoán/loss, tính Accuracy/F1, train CNN, chọn checkpoint, gửi thư hoặc gửi yêu cầu truy cập.

PASS xác nhận archive/đếm/nhóm/bản sao, không xác nhận bệnh nhân độc lập, nhãn lâm sàng hoặc nguồn sẽ làm model tăng điểm. Kho cũ/checkpoint/API/registry/điểm tổng5.937ảnh giữ nguyên.


[Manifest](provisional_candidates.jsonl), [protocol](protocol.json), [kiểm chứng](independent_review.json), [nhóm và trùng](similarity_audit.json), [ma trận dữ liệu nguồn](results.json).

## Hiệu chỉnh mã kiểm chứng độc lập

Quy tắc gom tên của producer đã giữ đúng mã camera/timestamp dài. Khi kiểm tra mã reviewer, phát hiện bản sửa hậu tố đã giới hạn nhầm chữ số ở frame index thay vì hậu tố bản sao. Giữ nguyên reviewer/protocol gốc đã khóa; đăng ký reviewer v2 riêng sau khi có số đếm producer và trước khi kiểm chứng độc lập. Bốn kiểm tra tên tệp cố định đạt, rồi v2 dựng lại toàn bộ fingerprint, giao nhau và nhóm. Kết quả producer không thay đổi, không có chọn phương pháp theo điểm model. Lịch sử và SHA được lưu trong `reviewer_correction_protocol.json`; PASS cuối dùng bản v2.
