# Model Card - DermAI Image Classifier

## Intended use

Sàng lọc tham khảo 8 nhóm ảnh da liễu trong bối cảnh DermAI Clinic. Không dùng
để tự chẩn đoán, loại trừ ung thư, kê đơn, cấp cứu hoặc thay ý kiến bác sĩ.

## Dữ liệu

Nguồn workspace hiện có 14.529 tệp; test có 9 lớp và 630 ảnh. Cấu hình chọn 8
lớp. Trước huấn luyện phải chạy kiểm tra ảnh hỏng, duplicate/leakage, bản quyền,
consent và phân bố theo màu da/tuổi/giới. Chưa có bằng chứng dataset đại diện cho
dân số Việt Nam.

## Chỉ số phát hành

Chưa có checkpoint được huấn luyện, vì vậy chưa công bố accuracy/F1. Chỉ phát
hành model khi có macro F1, recall từng lớp, confusion matrix, calibration,
one-vs-rest ROC-AUC, latency và đánh giá theo subgroup. Không được điền số giả.

## Rủi ro

Domain shift do camera/ánh sáng, nhiều bệnh cùng tồn tại, tên lớp rộng, mất cân
bằng và shortcut theo nền ảnh. `SkinCancer` là nhãn nhóm, không xác định subtype.
Confidence không đồng nghĩa xác suất mắc bệnh. Grad-CAM có thể tạo cảm giác giải
thích quá mức.

## Giảm thiểu

Ngưỡng không chắc chắn, top-3, review bắt buộc bởi bác sĩ, monitoring drift,
version/checksum, rollback, audit và nút báo kết quả sai. Ảnh có dấu hiệu nguy
hiểm phải được điều hướng đi khám, không dựa vào kết quả âm tính của mô hình.

