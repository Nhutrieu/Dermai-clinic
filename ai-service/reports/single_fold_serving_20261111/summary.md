# Bỏ biểu quyết năm fold

API chuyển sang `dermai-eight-single-fold4-v1-20261111`, dùng một bộ ba CNN
và luật fusion của fold 4. Chọn bằng Macro F1 inner validation đã lưu;
không đọc điểm test để chọn. Fold này không chọn specialist hoặc bộ chọn.

- [Cách chọn, luồng dự đoán, cấu hình và giới hạn](../../../docs/BO_BIEU_QUYET_NAM_FOLD_20261111.md).
- [Khớp toàn bộ 1.161 quyết định fold 4 đã lưu](branch_parity.json).
- [Tám lần gọi thử API Docker](docker_smoke.json).

Đây là thay đổi triển khai và kiểm tra chức năng. Chưa có điểm test đầy đủ của
bản một fold. Không gán điểm OOF tổng hoặc điểm bản biểu quyết cũ cho bản mới.
