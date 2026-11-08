# AI service của DermAI Clinic

## Bắt đầu xem từ đâu

| Nội dung | Vị trí |
|---|---|
| API và luồng xử lý ảnh | [app/main.py](app/main.py) |
| Nạp model, dự đoán và Grad-CAM | [app/model.py](app/model.py) |
| Cấu hình đường dẫn và ngưỡng | [app/config.py](app/config.py) |
| Model phục vụ | `models/best_model.pth`, `models/ood_profile.json` |
| RAG và trợ lý | `app/rag.py`, `app/support_assistant.py`, `rag-data/` |
| Danh mục script train và đánh giá | [Danh mục train](DANH_MUC_TRAIN_MODEL.md) |
| Pipeline nghiên cứu đang giữ | [Giải trình pipeline](../docs/GIAI_TRINH_PIPELINE_AI_CHO_THAY_20261108.md) |
| Báo cáo và lịch sử đã nén | [Hướng dẫn reports](reports/README.md) |

## Model phục vụ và nghiên cứu

API mặc định nạp **EfficientNet-B0 đơn**. `training/` chứa mã huấn luyện và
đánh giá; `candidates/` giữ checkpoint nghiên cứu; `reports/` giữ bằng chứng
cần dùng. Pipeline ensemble trong nghiên cứu chưa được bật trong API.

Bản nghiên cứu đang giữ trên 5.937 ảnh OOF đạt **78,9456% Accuracy,
77,7287% Macro F1 và 88,0355% Recall SkinCancer**. Đây là điểm phát triển,
chưa phải test bệnh nhân mới. Xem [tổng hợp nghiên cứu](../docs/ai-research-summary.md)
để đọc kết luận và giới hạn.

## Chạy API tại máy

Mở PowerShell tại thư mục `ai-service`:

```powershell
$env:RAG_INDEX_PATH = 'rag-data'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Kiểm tra `http://127.0.0.1:8000/health`. Docker dùng cấu hình và volume trong
Compose của dự án. Mã ứng dụng, model và dữ liệu train được giữ nguyên khi dọn báo cáo.
