# Báo cáo AI cần giữ

Bản GitHub chỉ chứa mã nguồn, báo cáo tổng hợp và biểu đồ chỉ số. Dự đoán
từng ảnh, manifest chứa danh tính ảnh, dữ liệu rà nhãn và bản nén lịch sử
được giữ cục bộ. Đường dẫn tới các tệp đó trong giao thức gốc phục vụ tái
lập trên máy có đủ dữ liệu; bản GitHub không kèm các đầu vào này.

Thư mục này giữ bằng chứng model phục vụ, pipeline nghiên cứu đang giữ,
baseline so sánh và hồ sơ nguồn dữ liệu cần cho báo cáo đồ án.
Model API vẫn là EfficientNet-B0 đơn; pipeline ensemble chưa được triển khai vào API.

## Đọc từ đâu

- [Tổng hợp nghiên cứu](../../docs/ai-research-summary.md).
- [Giải trình ensemble, cổng và specialist](../../docs/GIAI_TRINH_PIPELINE_AI_CHO_THAY_20261108.md).
- [Tính lại đóng góp từng thành phần](teacher_pipeline_explanation_20261108/results.json).
- [Specialist đang giữ](teacher_dropout_specialist_seed42_20261023/summary.md).
- [Cổng Macro F1](teacher_macro_f1_gate_seed42_20261023/summary.md).
- [Ensemble có bảo vệ SkinCancer](original_eight_cancer_locked_resnet_fusion_seed42_20261021/summary.md).

Các báo cáo OOF, audit trùng cảnh, kiểm nhãn và nguồn ảnh được giữ ở đường dẫn cũ.
`active_research_track.json` và các status là bản ghi lịch sử, giữ nguyên byte để
đối chiếu hash; xem bản giải trình ngày 08/11/2026 để biết mốc nghiên cứu đang giữ.

## Lịch sử đã lưu gọn

Các lượt thử cũ, nhánh không được chọn và log đã được nén vào
[một bản lưu lịch sử](../../backups/ai_reports_history_20261108.zip).
Trong ZIP có manifest đường dẫn, kích thước và SHA-256 của từng tệp.
Đã kiểm tra nội dung ZIP trước khi xoá các bản rời khỏi thư mục này.

Báo cáo gốc được giữ nguyên nội dung. Một số mã tái lập, test nghiên cứu và
đường dẫn lịch sử trong báo cáo cần khôi phục thêm tệp từ ZIP; chúng không nằm
trên luồng chạy API. Bản nén cũng giữ các hướng dẫn dài trước lần dọn này.

Để lấy lại một thí nghiệm, giải nén vào thư mục tạm từ gốc dự án:

```powershell
python -m zipfile -e backups/ai_reports_history_20261108.zip tmp/restore-ai-reports
```

Sau đó chép đúng thư mục cần dùng từ `tmp/restore-ai-reports/ai-service/reports/`
về `ai-service/reports/`. Giữ đường dẫn gốc khi chạy lại script nghiên cứu.
