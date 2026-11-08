# Rà soát và chuẩn bị split phát triển chống ảnh cùng cảnh

Ngày 09/10/2026, dựng lại split V2/SupCon đã dùng nhiều lần: **5.045 train, 892 validation**. Split này nhóm ảnh có cùng dHash hoàn toàn (`radius=0`) và giữ ảnh cùng ca SCIN ở một phía. Script `ai-service/training/audit_validation_scene_overlap.py` tìm thêm **48 ảnh validation** có ít nhất một ảnh train cách tối đa 3 bit dHash; chỉ là danh sách cần xem, không phải 48 ca trùng.

Đã mở trực tiếp ứng viên gần nhất cùng nhãn, ứng viên gần nhất khác nhãn và năm ứng viên cùng nhãn thứ cấp. **Ít nhất 21 ảnh validation** cho thấy cùng cảnh hoặc cùng tổn thương với ảnh train, gồm 6 Tinea, 4 SkinCancer, 4 Acne, 2 Eczema, 2 Warts, 2 Psoriasis và 1 Lupus. Danh sách từng cặp, đường dẫn và SHA-256 có trong `ai-service/reports/historical_validation_same_scene_review.json`; báo cáo ứng viên ban đầu ở `ai-service/reports/historical_validation_scene_overlap_candidates.json`. Nhận xét trực quan không xác nhận mã bệnh nhân, nhãn chẩn đoán hay toàn bộ ảnh cùng người. dHash cũng báo nhầm nhiều ảnh nền/da tương tự.

## Split nghiên cứu mới

Với các lần train **mới**, tách hai tác vụ dHash: ngưỡng loại láng giềng của fixed test cũ vẫn là `0`; ngưỡng tìm **ứng viên nhóm ảnh cùng nhãn trước khi chia train/validation** là `3`. Hai ngưỡng dùng chung trước đây khiến đặt `3` cũng loại 99 ảnh train vì gần fixed test đã xem, so với 10 ảnh ở ngưỡng `0`. Chỉ số dHash gần nhau không đủ để kết luận cùng cảnh: một lần thử nhóm theo dHash đơn lẻ đã ghép thành nhóm 16 ảnh Psoriasis, trong đó có ảnh nhìn khác nhau.

Phiên bản cuối chỉ tự nhóm cặp cùng nhãn nếu **dHash cách ≤3 và tương quan ảnh xám chuẩn hóa ≥0,85**. Ngoài ra, 21 cặp đã được xem trực tiếp được nối với nhau bằng manifest có SHA-256; ảnh cùng ca SCIN cũng ở cùng một phía. Ngưỡng 0,85 được chọn sau khi xem các cặp ứng viên trong chính bộ phát triển, nên chưa phải ngưỡng kiểm định độc lập.

Script `ai-service/training/prepare_leak_aware_development_split.py` tái tạo và kiểm tra split: **5.047 train, 890 validation**; 21/21 cặp đã xác nhận nằm cùng phía; không có ca SCIN bị chia đôi. Có 5 ảnh validation còn láng giềng train cùng nhãn ở dHash ≤3, nhưng **0 cặp** trong số đó đạt thêm điều kiện tương quan ≥0,85. Nhóm lớn nhất có 8 ảnh; không có nhóm trên 10 ảnh. Fingerprint của phép chia là `922f900cfed05bca4c5e9ea6b3ae65b4f64381363bed22ca2e007c23c7e6f9c4`; tóm tắt máy ở `ai-service/reports/leak_aware_development_split_seed42.json`.

`train_v2.py` và `train_supcon_convnext.py` nhận các cờ sau để tạo split này:

```text
--near-duplicate-distance 3 --near-test-distance 0 --near-pixel-correlation 0.85 --reviewed-scene-manifest ai-service/reports/historical_validation_same_scene_review.json
```

Không thay split của các checkpoint lịch sử hoặc tính lại chỉ số cũ theo split mới. Vì `SkinDisease` thiếu mã người và fixed test đã được xem lặp lại, split mới vẫn **không** phải phép chia theo người hay test độc lập. Các cặp cùng người chụp khác góc có thể còn sót; phép chia này chỉ giảm một nguồn rò rỉ dữ liệu đã quan sát. Kết quả [huấn luyện lại hai model trên split này](../ai-service/reports/scene_split_external_ensemble_seed42.json) chỉ là validation phát triển, chưa phải accuracy test độc lập.
