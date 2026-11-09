# Lượt 305 — pilot bổ sung ba ảnh Lupus

Hoàn thành ngày 08/11/2026. **Đã train hai nhánh, đủ sáu epoch mỗi nhánh. Chưa chọn thay bản đang giữ vì ảnh mới chưa tốt hơn đối chứng tương đương.**

## Kết quả trên cùng 1.332 query TRAIN lịch sử

| Phương án | Accuracy | Macro F1 | Lupus đúng /78 | Psoriasis đúng /193 | Tinea đúng /205 | Recall SkinCancer |
|---|---:|---:|---:|---:|---:|---:|
| Tham chiếu NLL296 (chưa được chọn) | 72,15% | 70,44% | 43 | 118 | 128 | 79,52% |
| Full CE cũ | 71,85% | 69,94% | 43 | 116 | 127 | 79,52% |
| Lặp thêm ba ảnh Lupus cũ | 71,70% | 70,25% | 45 | 112 | 125 | 79,52% |
| Thêm ba ảnh Lupus mới | 71,70% | 70,09% | 45 | 111 | 126 | 79,52% |

Cả hai nhánh mới đúng 955/1.332 ảnh. So đối chứng lặp ảnh cũ, nhánh ảnh mới đổi sáu dự đoán: sửa đúng hai ảnh, làm sai hai ảnh, hai ảnh vẫn sai. Macro F1 giảm 0,1520 điểm phần trăm; cả ba block query đều có Macro F1 thấp hơn đối chứng. Chênh lệch được tính từ số chưa làm tròn.

Lupus tăng từ 43 lên 45 ảnh đúng so Full CE cũ, nhưng nhánh lặp ảnh cũ cũng đạt 45. Vì vậy không thể quy mức tăng này cho ba ảnh mới. Precision Lupus của nhánh ảnh mới là 54,22%, thấp hơn 56,25% ở đối chứng; F1 là 55,90% so 56,96%. Psoriasis đúng ít hơn đối chứng một ảnh, Tinea đúng nhiều hơn một ảnh. Chưa cải thiện đồng thời ba bệnh yếu.

## Đã train những gì

- Hai ConvNeXt-Tiny tám lớp từ cùng khởi tạo ImageNet, seed 42; chỉ đầu phân loại và stage cuối được cập nhật. Không thêm backbone mới.
- Mỗi nhánh giữ 2.699 ảnh fit cũ. Nhánh chính thêm ba ảnh Lupus đơn từ ba bài ca bệnh; nhánh đối chứng thêm ba lượt ảnh Lupus cũ thuộc ba nhóm fit khác nhau. Nhãn nguồn do tác giả báo cáo, chưa được bác sĩ dự án xác nhận lại.
- Hai nhánh cùng 2.702 lượt ảnh mỗi epoch, cùng nhãn/thứ tự/augmentation của ảnh nền, cùng sáu epoch cố định. Mỗi nhánh có 1.014 cập nhật; tổng 2.028 cập nhật và 32.424 lượt tensor ảnh. Đây không phải 32.424 ảnh mới.
- Nhánh ảnh mới có 2.702 ảnh fit riêng biệt theo SHA; đối chứng vẫn có 2.699. Ba ảnh mới được gặp tổng 18 lượt. Tám tệp hình ghép từ đợt thu nhận vẫn chưa dùng.
- Khóa protocol trước train, khóa cả hai checkpoint trước khi chấm query, khóa dự đoán trước khi tính chỉ số. Giữ nguyên luật thay nhãn và các điều kiện bảo toàn đã đăng ký.

## Đủ tám bệnh của nhánh thêm ảnh mới

| Bệnh | Precision | Recall | F1 | Số ảnh query |
|---|---:|---:|---:|---:|
| Acne | 81,82% | 83,24% | 82,52% | 173 |
| Candidiasis | 72,92% | 57,38% | 64,22% | 61 |
| Eczema | 67,62% | 80,31% | 73,42% | 325 |
| Lupus | 54,22% | 57,69% | 55,90% | 78 |
| Psoriasis | 69,81% | 57,51% | 63,07% | 193 |
| SkinCancer | 83,02% | 79,52% | 81,23% | 166 |
| Tinea | 67,74% | 61,46% | 64,45% | 205 |
| Warts | 74,81% | 77,10% | 75,94% | 131 |

## Quyết định và giới hạn

Không chọn cả hai nhánh thay mốc nghiên cứu; không nới điều kiện sau kết quả và không đổi sang nhánh đối chứng vì nó có điểm thuận lợi hơn. Nhánh ảnh mới chưa tăng Recall Lupus so đối chứng, giảm precision/F1 Lupus và Macro F1, đồng thời chưa bảo toàn toàn bộ các mốc khác.

**Mốc grouped OOF 5.937 ảnh vẫn là Accuracy 78,95%, Macro F1 77,73%, Recall SkinCancer 88,04%. API vẫn dùng EfficientNet-B0 đơn.** Recall SkinCancer 79,52% trong bảng pilot thuộc tập query 1.332 ảnh khác; không so trực tiếp với 88,04% OOF. Luật giữ nguyên mặt nạ dự đoán SkinCancer cũng giữ các lỗi cũ, không làm tăng khả năng nhận ung thư.

Đây là một pilot seed 42 trên query TRAIN lịch sử đã dùng phát triển nhiều lần; không phải test mù, ảnh bệnh nhân mới hay đánh giá lâm sàng. Ba ảnh mới chỉ vào fit, không vào query/validation/outer. Chưa có bằng chứng để mở rộng phương án này sang đủ năm fold. Kết quả không chứng minh mọi dữ liệu bổ sung đều vô ích, và không đủ để kết luận ảnh mới có nhãn sai.

## Kiểm chứng kỹ thuật

Bốn unit test đạt. Khôi phục đúng byte 48 tệp phụ thuộc từ ZIP lịch sử. Đối chiếu 351 tệp đã khóa; kiểm tra split, luồng ảnh nền/nhãn/thứ tự của cả sáu epoch, tính lại ma trận và chỉ số bằng NumPy cùng sklearn, kiểm lại luật dự đoán. Replay 61 cập nhật đầu mỗi nhánh tới bước đầu gặp ảnh bổ sung: tensor tham số trùng chính xác checkpoint đã lưu.

Checker ban đầu dừng vì so loss với sai số tuyệt đối 1e-7: công thức NLL tính riêng khác CE đã lưu đúng một ULP FP32 (1,1920928955078125e-7). Kiểm tra chẩn đoán giữ ngưỡng tham số cũ, xác nhận tham số sai khác bằng 0 và CE trên cùng logits khớp loss đã lưu. Giữ nguyên checker gốc, log lỗi và protocol chẩn đoán; không sửa kết quả hay điều kiện lựa chọn.

Chưa replay độc lập toàn bộ sáu epoch hoặc forward lại toàn bộ query; chưa có rà nhãn lâm sàng mới. PASS chỉ áp dụng cho các kiểm tra đã nêu.

[Protocol cục bộ](protocol.json) · [Kết quả](results.json) · [Kiểm chứng](verification.json) · [Nguồn ảnh](../teacher_open_case_photo_intake_20261106/ATTRIBUTION.md)
