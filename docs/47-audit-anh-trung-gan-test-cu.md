# Audit ảnh cùng cảnh giữa train và test cố định cũ

Ngày 09/10/2026, dựng lại đúng split của lần huấn luyện EfficientNet-B0 đang dùng: **5.053 train, 894 validation, 564 test**. Kết quả khớp `ai-service/models/dataset_summary.json`; 564 dự đoán B0 lưu trước đó khớp SHA-256 từng ảnh và đúng **445/564 (78,90%)**. Pipeline cũ đã loại ảnh trùng **byte** giữa train/test, nhưng không loại ảnh cùng cảnh được lưu với nội dung byte khác nhau.

Script `ai-service/training/audit_historical_split_shortcuts.py` chỉ tạo danh sách cần xem bằng tên file và dHash. Nó đánh dấu 374 ảnh test có phần tên mô tả giống ảnh train/validation, và 45 ảnh có ít nhất một dHash cách tối đa 3 bit. **Không được gọi toàn bộ các ảnh này là trùng người hoặc trùng ảnh.** Tên thường là tên bệnh/kiểu tổn thương chung; dHash thấp cũng xuất hiện giữa ảnh khác bệnh và nền ảnh giống nhau.

Đã mở trực tiếp và đối chiếu các cặp dưới đây. Đây là nhận xét về **cùng cảnh/tổn thương trong ảnh**, không phải xác nhận chẩn đoán hay mã bệnh nhân. Danh sách được ghi kèm SHA-256 từng file trong `ai-service/reports/historical_same_scene_review.json`:

| Ảnh test cũ | Ảnh trong nguồn train cũ | Quan sát |
| --- | --- | --- |
| `Eczema/05AtopicPop.jpeg` | `Eczema/05AtopicPop1.jpeg` | Cùng vùng hai đầu gối, thay đổi sáng/màu. |
| `Candidiasis/candidiasis-large-skin-folds-169.jpeg` | `Candidiasis/candidiasis-large-skin-folds-165.jpeg` | Cùng tổn thương và đường viền, thay đổi cắt ảnh/sáng. |
| `Psoriasis/Psoriasis-Guttate-33.jpeg` | `Psoriasis/Psoriasis-Guttate-34.jpeg` | Cùng bàn tay, thay đổi sáng/màu. |
| `Psoriasis/Psoriasis-Guttate-36.jpeg` | `Psoriasis/Psoriasis-Guttate-20.jpeg` | Cùng ảnh thân người. |
| `Tinea/tinea-foot-plantar-48.jpeg` | `Tinea/tinea-foot-plantar-49.jpeg` | Cùng bàn chân, thay đổi sáng/màu. |
| `Tinea/tinea-incognito-44.jpeg` | `Tinea/tinea-incognito-36.jpeg` | Cùng vùng lưng và tổn thương, thay đổi sáng/màu. |
| `Warts/genital-warts-30.jpeg` | `Warts/genital-warts-29.jpeg` | Cùng vùng tổn thương da, khung hình dịch nhẹ. |
| `Candidiasis/candida-penis-22.jpeg` | `Candidiasis/candida-penis-40.jpeg` | Cùng ảnh, khác sáng/màu. |
| `Candidiasis/candidiasis-large-skin-folds-154.jpeg` | `Candidiasis/candida-groin-2.jpeg` | Cùng ảnh, khác tên và cách nén. |
| `Candidiasis/candidiasis-large-skin-folds-184.jpeg` | `Candidiasis/candidiasis-large-skin-folds-148.jpeg` | Cùng ảnh, khác sáng/màu. |
| `Eczema/eczema-face-2.jpeg` | `Eczema/eczema-chronic-19.jpeg` | Cùng ảnh, khác tên. |
| `Lupus/2561__Protect…jpeg` | `Lupus/dle-scalp__Protect…jpeg` | Cùng ảnh vùng da đầu, khác tên. |
| `Tinea/tinea-groin-26.jpeg` | `Tinea/tinea-groin-119.jpeg` | Cùng ảnh, khác sáng/màu. |
| `Tinea/tinea-scalp-50.jpeg` | `Tinea/tinea-scalp-26.jpeg` | Cùng ảnh, khác sáng/màu. |
| `Warts/genital-warts-31.jpeg` | `Warts/genital-warts-29.jpeg` | Cùng vùng da; test có hai bản gần giống nhau. |
| `Warts/genital-warts-68.jpeg` | `Warts/genital-warts-88.jpeg` | Cùng ảnh, khác sáng/màu. |
| `Warts/genital-warts-83.jpeg` | `Warts/genital-warts-133.jpeg` | Cùng ảnh, khác sáng/màu. |
| `Warts/warts-common-30.jpeg` | `Warts/warts-digitate-12.jpeg` | Cùng ảnh, khác tên. |
| `Warts/warts-digitate-13.jpeg` | `Warts/warts-common-32.jpeg` | Cùng ảnh, khác tên. |

Cả **19 ảnh test** đã xác nhận cùng cảnh với ảnh trong nguồn train cũ đều được B0 đoán đúng. Khi dựng lại split thực tế, **18 ảnh đối ứng nằm trong train, một ảnh nằm trong validation** (`candidiasis-large-skin-folds-184.jpeg` đối ứng với `...-148.jpeg`). Nếu **chỉ** loại 19 ảnh test này, điểm B0 còn **426/545 (78,17%)**, giảm 0,74 điểm phần trăm so với 445/564 (78,90%). Script `ai-service/training/summarize_historical_same_scene_review.py` xác minh SHA-256 của từng cặp, đối chiếu dự đoán đã lưu và xuất `ai-service/reports/historical_same_scene_sensitivity.json`. Đây là phép tính nhạy cảm tối thiểu, **không phải điểm test đã sửa**: các cặp khác chưa được xem đầy đủ và dữ liệu không có mã bệnh nhân để tách người. Không thể dùng fixed test cũ làm bằng chứng độc lập theo người cho mức 78,90% hoặc mức 83,87% của ensemble. Khoảng cách rất lớn với các nguồn ngoài cũng không thể quy hết cho 19 ảnh này.

Một ví dụ cảnh báo sai đã được mở: `SkinCancer/basal-cell-carcinoma-superficial-31.jpeg` và `SkinCancer/basal-cell-carcinoma-superficial-40.jpeg` có dHash gần nhưng là hai tổn thương/cảnh khác nhau. Vì thế không tự loại 45 ảnh bị dHash đánh dấu. Báo cáo máy cục bộ ở `ai-service/reports/historical_split_shortcut_audit.json` lưu danh sách, số ảnh và kết quả dự đoán; không chứa bản sao ảnh.

Hướng xử lý: giữ nguyên test và checkpoint để bảo toàn lịch sử kết quả; ghi rõ giới hạn của test cũ trong mọi bảng so sánh. `training/train.py` nay mặc định không chạy đánh giá fixed test sau mỗi lần huấn luyện; `--evaluate-test` chỉ dành cho tái lập kết quả lịch sử. Muốn đo độ chính xác mới, cần bộ ảnh có mã ca/người, nguồn và nhãn xác minh, tách khỏi toàn bộ train/validation/test đã xem. Không chọn hay tinh chỉnh model theo chính tập test cố định này.
