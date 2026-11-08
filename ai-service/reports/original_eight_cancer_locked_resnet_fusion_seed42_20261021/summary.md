# Kết quả gộp ResNet và giữ quyết định SkinCancer

Ngày 21/10/2026. Giữ đủ tám bệnh gốc và cùng 5.937 ảnh phát triển OOF.

**Kết quả chọn bằng validation: Accuracy 78,68%, Macro F1 77,24%, Recall SkinCancer giữ nguyên 88,04%. Đúng thêm 36 ảnh so với bộ gộp cũ.**

## So sánh với bộ gộp cũ

| Chỉ số | Bộ gộp cũ | Bộ gộp mới được chọn | Thay đổi |
|---|---:|---:|---:|
| Accuracy | 78,07% | 78,68% | +0,61 điểm % |
| Macro F1 | 76,82% | 77,24% | +0,41 điểm % |
| Recall SkinCancer | 88,04% | 88,04% | +0,00 điểm % |
| Precision SkinCancer | 86,25% | 86,25% | +0,00 điểm % |
| Số ảnh đúng | 4635/5.937 | 4671/5.937 | +36 ảnh |

## Cách kết hợp

Dùng lại dự đoán từ EfficientNet-B0, ConvNeXt-Tiny và ResNet50 đã huấn luyện trên đúng fold của từng model. Không train thêm CNN hoặc thêm ảnh trong lượt này.

1. Bộ B0 và ConvNeXt theo bệnh là đối chứng. Giữ nguyên tập ảnh mà bộ này dự đoán SkinCancer.
2. Ảnh ngoài tập trên chỉ được chọn trong bảy bệnh còn lại bằng điểm gộp 75% đối chứng và 25% ResNet.
3. Trên inner validation, nếu một bệnh ngoài mục tiêu bị giảm Recall quá 2 điểm phần trăm, hoặc Precision Lupus/Psoriasis/Tinea giảm quá 2 điểm, khóa thêm toàn bộ quyết định của bệnh đó theo bộ cũ. Lặp đến khi không cần khóa thêm.
4. Giữ nhánh mới ở fold đó chỉ khi Accuracy và Macro F1 validation đều không giảm, đồng thời đạt các điều kiện từng bệnh. Nếu không đạt, dùng bộ cũ. Chọn Macro F1 cao hơn, rồi Accuracy; bộ cũ thắng khi bằng điểm.

**Các phép so sánh này chỉ dùng validation của fold tương ứng. Toàn bộ năm lựa chọn và các nhãn cần khóa được lưu trước khi chương trình đọc mảng dự đoán outer để chấm lượt này.** Các ảnh outer đã được nghiên cứu trong những lượt trước, nên đây vẫn là kết quả thăm dò trên tập phát triển.

## Lựa chọn từng fold

| Fold | Phương án được giữ | Nhãn khóa theo bộ cũ |
|---|---|---|
| 1 | Gộp có bảo vệ theo validation | Candidiasis, Lupus, SkinCancer |
| 2 | Gộp có bảo vệ theo validation | Candidiasis, SkinCancer |
| 3 | Bộ cũ | Acne, Candidiasis, Eczema, Lupus, Psoriasis, SkinCancer, Tinea, Warts |
| 4 | Gộp có bảo vệ theo validation | Candidiasis, SkinCancer |
| 5 | Gộp có bảo vệ theo validation | Candidiasis, SkinCancer |

Bốn fold giữ nhánh gộp mới; fold 3 giữ bộ cũ vì nhánh mới giảm Accuracy và Macro F1 trên validation. Không đổi lựa chọn theo điểm outer.

## Kết quả từng bệnh

| Bệnh | Ảnh | Recall cũ | Recall mới | Precision cũ | Precision mới | F1 cũ | F1 mới |
|---|---:|---:|---:|---:|---:|---:|---:|
| Acne | 663 | 89,44% | 90,05% | 82,94% | 82,57% | 86,07% | 86,15% |
| Candidiasis | 243 | 72,84% | 72,84% | 67,82% | 67,82% | 70,24% | 70,24% |
| Eczema | 1577 | 82,82% | 83,51% | 76,60% | 76,88% | 79,59% | 80,06% |
| Lupus | 315 | 59,68% | 59,68% | 71,76% | 70,15% | 65,16% | 64,49% |
| Psoriasis | 897 | 67,78% | 68,90% | 75,72% | 76,87% | 71,53% | 72,66% |
| SkinCancer | 677 | 88,04% | 88,04% | 86,25% | 86,25% | 87,13% | 87,13% |
| Tinea | 989 | 66,73% | 67,54% | 76,48% | 79,43% | 71,27% | 73,01% |
| Warts | 576 | 88,02% | 88,54% | 79,59% | 80,19% | 83,59% | 84,16% |

**Lupus chưa tốt hơn:** Recall vẫn 59,68%, Precision giảm 71,76% xuống 70,15%, F1 giảm 65,16% xuống 64,49%. Psoriasis và Tinea có cải thiện nhẹ. Không kết luận cả tám bệnh đều tăng.

## So sánh các quy tắc đã khóa

| Quy tắc | Accuracy OOF | Macro F1 OOF | Recall SkinCancer |
|---|---:|---:|---:|
| Bộ cũ | 78,07% | 76,82% | 88,04% |
| Chỉ khóa SkinCancer, gộp 75:25 | 78,95% | 77,78% | 88,04% |
| Khóa thêm bệnh theo validation, áp dụng mọi fold | 78,84% | 77,45% | 88,04% |
| Chọn có điều kiện trên validation, gồm phương án dự phòng | 78,68% | 77,24% | 88,04% |

Nhánh chỉ khóa SkinCancer đạt 78,95% / 77,78% OOF, nhưng không qua đầy đủ điều kiện validation ở bất kỳ fold nào, chủ yếu do Recall Candidiasis hoặc chỉ số tổng. Vì vậy không lấy nhánh có điểm OOF cao nhất thay cho lựa chọn đã khóa.

## Kết quả theo nguồn

| Nguồn | Ảnh | Accuracy cũ | Accuracy mới |
|---|---:|---:|---:|
| original_train | 4961 | 79,80% | 80,29% |
| SCIN | 976 | 69,26% | 70,49% |

Khoảng bootstrap 95% của mức tăng Accuracy theo nhóm ca/cảnh: [+0,18; +1,01] điểm phần trăm, 2.000 lần lấy mẫu. Đây là mô tả trên dữ liệu đã nghiên cứu; không tính hết bất định từ việc thử nhiều phương án hay chỉ huấn luyện một seed.

## Giới hạn cần ghi khi báo cáo

- Khóa toàn bộ quyết định SkinCancer giữ nguyên cả ảnh nhận đúng, bỏ sót và báo nhầm. Bộ cũ và bộ mới đều nhận đúng 596/677 ảnh nhãn SkinCancer, bỏ sót 81 ảnh; chưa cải thiện các lỗi này.
- Chưa có tập bệnh nhân mới độc lập. Các checkpoint cha từng dùng inner validation để chọn epoch; chia nhóm tầng quyết định không biến toàn bộ quy trình thành nested training hoàn chỉnh.
- SCIN có nhiều ảnh Eczema, ít ảnh ở một số bệnh và không có nhãn SkinCancer trong phần này. Accuracy nguồn chưa chứng minh mọi bệnh đều tốt.
- Đây là lớp quyết định có phân nhánh. Điểm xác suất gốc của hai thành phần được lưu riêng; chưa có xác suất cuối được hiệu chỉnh, chưa tuyên bố confidence hoặc Top-3 của lớp quyết định này.
- Giữ nguyên báo cáo Word cũ, dữ liệu, checkpoint và mốc đối chứng tám bệnh. API vẫn dùng EfficientNet-B0 đơn; các số trên chưa phải điểm của ứng dụng đang phục vụ.

## Tệp kết quả

- [Ma trận nhầm lẫn phương án được chọn](selected_confusion_matrix.png)
- [Toàn bộ chỉ số và từng fold](results.json)
- [Quy tắc đã khóa](protocol.json)
- [Dự đoán từng ảnh và điểm thành phần](oof_decisions.json)
- [Lựa chọn cả năm fold trước khi chấm outer](all_selections_locked.json)
- [Kiểm chứng kỹ thuật](verification.json)
- [Tính lại độc lập 32 bộ chỉ số](independent_review.json)
