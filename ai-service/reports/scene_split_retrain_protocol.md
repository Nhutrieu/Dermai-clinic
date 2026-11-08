# Rerun hai kiến trúc trên split phát triển đã rà ảnh cùng cảnh

Ngày 09/10/2026. Split cố định theo `leak_aware_development_split_seed42.json`:
5.047 train, 890 validation; seed 42; ngưỡng loại láng giềng fixed test cũ
`dHash=0`; nhóm ảnh cùng nhãn khi `dHash≤3` và tương quan xám `≥0,85`, cộng
21 cặp đã xem trực tiếp và ca SCIN. Fingerprint split phải là
`922f900cfed05bca4c5e9ea6b3ae65b4f64381363bed22ca2e007c23c7e6f9c4`.

Hai mô hình khởi tạo từ ImageNet, **không** từ checkpoint DermAI cũ vì những
checkpoint đó đã học trên một phần validation mới. Chọn checkpoint từng mô hình
theo macro F1 validation, rồi top-3 accuracy và loss. Không đo fixed test cũ,
SCIN holdout hay nguồn ngoài để chọn epoch, siêu tham số hoặc trọng số kết hợp.

1. EfficientNet-B0: công thức V2 trước đây, 24 epoch tối đa, freeze 2 epoch,
   batch 32, learning rate 2e-4, backbone ratio 0,25, weight decay 2e-4,
   label smoothing 0,05, effective-number beta 0,999, EMA 0,995, patience 7.
2. ConvNeXt-Tiny: công thức regularized trước đây, 24 epoch tối đa, freeze 2
   epoch, batch 16, learning rate 3e-4, backbone ratio 0,1, weight decay 0,01,
   label smoothing 0,1, effective-number beta 0,9999, EMA 0,5, patience 6.

Sau huấn luyện, so sánh accuracy, macro F1, recall từng lớp trên **cùng 890 ảnh**.
Nếu kết hợp, dùng trung bình xác suất 50:50 đặt trước, không dò trọng số trên
validation. Vì validation đã dùng chọn checkpoint và split được xây bằng rà ảnh
trong dữ liệu này, kết quả chỉ là phát triển nội bộ; không chứng minh độ chính
xác trên bệnh nhân mới. Chỉ số lịch sử trên split khác không được so trực tiếp.
