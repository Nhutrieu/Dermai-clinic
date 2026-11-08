# Lượt 303 — pilot nhãn đầu duy nhất SCIN có đối chứng

Ngày 06/11/2026. **Đã train và kiểm tra xong hai nhánh. Lọc nhãn đầu đồng hạng chưa cải thiện kết quả; không chọn thay mốc hiện tại.**

## Kết quả trên cùng 1.332 query TRAIN lịch sử

| Phương án cùng luật ghép | Accuracy | Macro F1 | Lupus đúng /78 | Psoriasis đúng /193 | Tinea đúng /205 | Recall SkinCancer |
|---|---:|---:|---:|---:|---:|---:|
| Tham chiếu NLL296 | 72,15% | 70,44% | 43 | 118 | 128 | 79,52% |
| Full CE đối chứng | 71,85% | 69,94% | 43 | 116 | 127 | 79,52% |
| Bỏ ca tương đương | 71,92% | 69,97% | 43 | 114 | 129 | 79,52% |
| Lọc nhãn đầu đồng hạng | 71,55% | 69,61% | 43 | 113 | 127 | 79,52% |

Nhánh lọc đúng 953 ảnh, thấp hơn Full CE bốn ảnh và nhánh bỏ ca tương đương năm ảnh. So Full CE, Lupus và Tinea không tăng số đúng, Psoriasis giảm ba ảnh; precision/F1 Lupus cũng giảm. So tham chiếu NLL296, giảm tám ảnh đúng. Không dùng nhánh đối chứng tốt hơn để thay nhánh chính sau khi đọc kết quả.

Đây là pilot trên dữ liệu TRAIN lịch sử đã dùng phát triển nhiều lần, chưa phải test mù, bệnh nhân mới hay điểm tổng 5.937 ảnh. NLL296 cũng chưa đạt toàn bộ điều kiện và chỉ là tham chiếu nghiên cứu. **Mốc OOF 78,95% Accuracy / 77,73% Macro F1 / 88,04% Recall SkinCancer và API B0 giữ nguyên.**

## Đã thay đổi gì trong dữ liệu học

Tiếp [lượt 302](../teacher_scin_unique_top_audit_20261106/results.json), đối chiếu trực tiếp CSV nguồn, giữ ánh xạ bệnh hẹp và ngưỡng cũ. Trong fit đầu tiên có 60 ảnh thuộc 28 mã ca SCIN có nhãn đầu đồng hạng: 37 Eczema, 15 Psoriasis, 8 Tinea, không có Lupus. Các chẩn đoán đồng hạng có thể liên quan nhau; không tự coi đó là nhãn sai.

- Nhánh chính cho trọng số loss bằng 0 với toàn bộ ảnh fit thuộc những ca trên; không xóa ảnh hoặc sửa nhãn.
- Nhánh đối chứng bỏ các ca SCIN đầu duy nhất khác, khớp chính xác bệnh và số ảnh trong từng ca; chọn cố định bằng SHA trước khi train.
- Cả hai có 2.639 ảnh góp loss; mỗi lớp giữ tổng trọng số bằng số ảnh lớp gốc. 60 ảnh vẫn được forward để giữ nguyên luồng tính toán, nhưng không góp gradient từ nhãn.

Nhãn đầu duy nhất chỉ là thuộc tính metadata nguồn, không phải chẩn đoán đã xác nhận. Quy tắc lọc không tạo thêm dữ liệu Lupus: fit vẫn chỉ có một Lupus SCIN. Không thêm ảnh mới, không đổi checkpoint cũ hoặc đưa query vào tập học.

## Huấn luyện và điều kiện đã khóa

Train **hai ConvNeXt-Tiny mới**, cùng ImageNet seed42 như CE279, chỉ classifier và stage cuối học. Cùng 2.699 ảnh/order/crop/lật của CE279, sáu epoch cố định, 1.014 cập nhật mỗi nhánh; AdamW head 0,0002/stage cuối 0,00005, weight decay 0,0002, clip 2, batch 16, BF16 forward và FP32 loss/tham số, model.eval tắt DropPath. Không thêm loss, backbone, augmentation hoặc chọn epoch bằng query.

Tổng 2.028 cập nhật và 32.388 lượt tensor ảnh; trong đó 31.668 lượt góp loss, không phải 32.388 ảnh hoặc bệnh nhân mới. Kiểm SHA luồng ảnh/nhãn/order đủ sáu epoch khớp đối chứng CE279. Khóa cả hai checkpoint/log trước 2.664 forward query; khóa cả hai bộ dự đoán trước tính chỉ số.

Dùng nguyên parent NLL296 và luật 294: chỉ đổi nhãn khi có đầu mút Lupus/Psoriasis/Tinea, không có đầu mút SkinCancer, và điểm đề xuất hơn điểm nhãn parent lớn hơn ln(2). Nhờ giữ đúng mặt nạ SkinCancer, cả lỗi cũ của lớp này cũng được giữ, không tuyên bố cải thiện ung thư.

Giữ các điều kiện 283 và các mốc 288/294/295/296, các block query; nhánh chính còn phải giữ Accuracy và P/R/F1 ba bệnh, tăng Macro F1 và Recall Lupus so cả Full CE và đối chứng bỏ ca tương đương. **Hai nhánh đều chưa đạt; không nới điều kiện sau kết quả.**

## Đủ tám bệnh của nhánh chính

| Bệnh | Precision | Recall | F1 | Số ảnh |
|---|---:|---:|---:|---:|
| Acne | 80,79% | 82,66% | 81,71% | 173 |
| Candidiasis | 73,33% | 54,10% | 62,26% | 61 |
| Eczema | 68,32% | 80,31% | 73,83% | 325 |
| Lupus | 55,13% | 55,13% | 55,13% | 78 |
| Psoriasis | 68,07% | 58,55% | 62,95% | 193 |
| SkinCancer | 83,02% | 79,52% | 81,23% | 166 |
| Tinea | 68,28% | 61,95% | 64,96% | 205 |
| Warts | 72,66% | 77,10% | 74,81% | 131 |

## Kết luận và giới hạn

Kết quả chưa ủng hộ cách loại toàn bộ ca có nhãn đầu đồng hạng trong cấu hình này. Không kết luận mọi cách cải thiện dữ liệu đều thất bại, nhãn đồng hạng chắc chắn sai, hoặc nhãn đầu duy nhất chắc chắn đúng. Đây là một lượt seed42 trên một query đã khảo sát; chưa kiểm hai phần còn lại hoặc validation/OOF chính. Chưa mở rộng cấu hình này sang ba pool vì pilot đầu không vượt các đối chứng.

Nhóm vẫn cần bằng chứng nhãn hoặc dữ liệu mới phù hợp để thử giả thuyết tiếp, thay vì tự sửa nhãn theo dự đoán. Các nhánh cũ từng tăng chỉ số vẫn được giữ; phép thử này không thay kết quả của chúng.

## Kiểm tra kỹ thuật

Mười kiểm thử đạt: bảy về quy tắc nguồn và ghép ca, ba về loss/gradient. Đối chiếu riêng từ CSV dựng lại các mask ca và strata ghép đối chứng; không có giao nhau fit với query/inner/outer theo path, SHA và nhóm, hoặc mã ca SCIN đã kiểm. Mã kiểm tra riêng tính lại ma trận, Accuracy, Macro F1, P/R/F1 và luật ghép; replay cập nhật AdamW đầu của cả hai nhánh từ ImageNet bằng công thức log-softmax độc lập. Hash nguồn, model phục vụ và registry giữ nguyên.

Không train lại độc lập toàn bộ sáu epoch, không forward lại độc lập toàn bộ 2.664 query và không có rà lâm sàng mới. PASS chỉ xác nhận những kiểm tra kỹ thuật đã nêu.

[Protocol](protocol.json) · [Kết quả gốc](results.json) · [Kiểm tra riêng](verification.json)
