# Lượt 304 — tìm và rà ảnh ca bệnh giấy phép mở

Ngày 06/11/2026. **Đã thu nhận và kiểm tra nguồn của 12 tệp hình; sau rà loại hình ảnh còn 11 tệp ảnh lâm sàng ứng viên. Chưa thêm vào train/test hoặc tăng điểm mô hình.**

## Kết quả thực tế

Hai lô truy vấn ca bệnh đã rà 65 bản ghi bài báo, kiểm 128 hình trong các bài qua điều kiện nguồn. Lấy được 12 tệp media xuất bản với giấy phép và chú thích truy nguyên được. Khi xem ảnh, phát hiện một hình Lupus thực chất là sơ đồ cơ chế bệnh; đã loại khỏi danh sách ảnh lâm sàng dù caption có từ bệnh.

| Nhãn nguồn | Tệp ảnh lâm sàng ứng viên | Nhóm bài báo proxy |
|---|---:|---:|
| Lupus | 4 | 4 |
| Psoriasis | 6 | 6 |
| Tinea | 1 | 1 |
| Tổng | 11 | 11 |

**Không gọi 11 nhóm bài báo là 11 bệnh nhân mới đã xác minh.** Một hình có thể ghép nhiều góc chụp, và một ca có thể được công bố ở nhiều bài. Nhãn là chẩn đoán/chú thích tác giả báo cáo, chưa được người chuyên môn của dự án xác nhận lại.

Trong 11 tệp, ba ảnh Lupus là ảnh chụp nguyên khung, không ghép panel hoặc có chữ/mũi tên nguồn phủ lên ảnh. Tám tệp còn lại là hình ghép nhiều ảnh lâm sàng; cần chuẩn bị panel và rà trùng lại ở cấp panel trước khi dùng cho model nhận ảnh chụp đơn. Không tạo ảnh bằng AI, không tự đổi nhãn hoặc đếm panel thành ca mới.

## Nguồn đã kiểm tra và cách lấy ảnh

- [DDI](https://ddi-dataset.github.io/) và [DDI-2](https://daneshjoulab.github.io/ddi2-dataset/) miễn phí cho nghiên cứu phi thương mại theo điều khoản nguồn, nhưng cần đăng ký người dùng. Chưa đăng ký, nhận ảnh hoặc gửi liên hệ thay nhóm; chưa xác minh số ảnh khớp đủ ba bệnh.
- [eSkinHealth](https://github.com/janet-sw/eSkinHealth) vẫn thông báo chưa phát hành vì đang rà đạo đức/pháp lý; chưa có lô ảnh được nhận.
- Lô ảnh hiện có lấy qua [PMC Cloud Service](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/) và ESearch chính thức. Chỉ nhận bài OA có giấy phép CC phù hợp, đối chiếu giấy phép trong XML và metadata, không dùng nhãn cấp bài để bỏ qua quyền riêng của hình. Không nhận ND/TDM hoặc hình có ghi công bên thứ ba chưa làm rõ.

Giữ truy vấn chỉ rõ ca bệnh ở tiêu đề và tên bệnh hẹp; loại mô học, soi da, biểu đồ, ảnh sau điều trị hoặc trộn trước–sau, caption không nêu rõ bệnh, nguồn bị rút bài và giấy phép không đạt. Quy tắc chưa bao phủ mọi biến thể caption; do đó vẫn cần xem ảnh để loại sơ đồ và đánh dấu hình ghép.

## Chống trùng và kiểm tra kỹ thuật

Đối chiếu **19.660 bản ghi bảo vệ**: 19.635 fingerprint lịch sử cộng 25 ảnh SkinDis-India từng dùng trong pilot trước. Giữ cả fingerprint lịch sử khi đường dẫn gốc không còn, không khôi phục corpus đã bỏ. So SHA byte, SHA pixel RGB và dHash Hamming ≤3; nối cùng bài báo và những ảnh gần trùng thành thành phần liên thông. Hiện chưa có hit bảo vệ ở 12 tệp đã nhận; điều này không chứng minh độc lập bệnh nhân hoặc bắt được mọi kiểu crop/chuyển đổi.

Mã kiểm tra riêng không import producer đã đọc lại từng ảnh, kiểm MD5 do nguồn cấp và liên kết ảnh–XML–caption, tính lại fingerprint; dùng BFS và bảng popcount NumPy để dựng lại nhóm trên cả hai lô. Không có sai khác quyền dùng hoặc fingerprint trong những kiểm tra đã thực hiện. 13 kiểm thử quy tắc và tương thích định dạng đạt.

Lượt đầu đã lưu riêng việc chưa đọc được WebP/URL giấy phép dạng văn bản và truy vấn Publication Type bị dịch sang All Fields. Lượt sửa tương thích giữ hồ sơ cũ, dùng đúng định dạng media xuất bản, truy vấn ca bệnh ở tiêu đề và bỏ tham số sort không được hỗ trợ. Không sửa tiêu chí theo điểm AI; toàn bộ lượt này không đọc dự đoán model.

## Việc có thể làm tiếp

Ba ảnh Lupus nguyên khung có thể dùng trong một pilot phụ riêng với nhãn tác giả và giới hạn đã nêu: giữ đủ tám bệnh, cùng encoder/loss/lịch học; có đối chứng tăng số lượt bằng ảnh Lupus cũ tương đương. Chỉ mở pilot với protocol đã khóa, ảnh mới chỉ ở fit, giữ toàn bộ query/validation/outer và mặt nạ SkinCancer. Tám hình ghép chưa dùng trực tiếp làm ảnh chụp đơn.

Mốc OOF 78,95% Accuracy / 77,73% Macro F1 / 88,04% Recall SkinCancer, registry và API B0 giữ nguyên. Số ảnh mới nhận không tự tạo cải thiện; chưa có kết quả train hoặc bộ test bệnh nhân mới ở lượt 304.

[Hồ sơ ghi công và chú thích](ATTRIBUTION.md) · [Danh sách 11 tệp ảnh lâm sàng](clinical_candidates.jsonl) · [Ba ứng viên ảnh đơn](single_photo_pilot_candidates.jsonl) · [Kiểm chứng](verification.json)
