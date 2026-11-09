# Bản AI được tích hợp vào đồ án ngày 08/11/2026

API mặc định được cấu hình nạp **`dermai-eight-esg-v1-20261108`**, thay cho B0 đơn. Bản này dùng các thành phần đã được giữ trong nghiên cứu; không dùng hai nhánh bổ sung ảnh Lupus của pilot 305 vừa bị loại.

## Thành phần được nạp

| Thành phần | Cách sử dụng |
|---|---|
| EfficientNet-B0, ConvNeXt-Tiny, ResNet50 | Năm checkpoint mỗi kiến trúc, tổng 15 CNN; giữ nguyên trọng số đã học. |
| Ensemble E | Trọng số B0/ConvNeXt theo bệnh; thêm 25% ResNet ở fold 0/1/3/4, với các lớp bảo vệ đã khóa; fold 2 dùng B0/ConvNeXt. |
| Cổng G và stacking | Dùng tại fold 0/3; giữ 24 đầu vào stacking, 22 đầu vào cổng và ngưỡng đổi nhãn > 2/3. |
| Specialist S | Dùng tại fold 1/2; đặc trưng ResNet 2.048 chiều, scaler train, đầu 128 → 5; luật nhận nhãn từ 0,8. |
| Kiểm tra ảnh ngoài phạm vi | Giữ checkpoint B0 và profile cũ cho cổng OOD, không dùng nhầm profile đó cho đặc trưng CNN khác. |

Các checkpoint và tensor được sao chép sang `ai-service/models/research_pipeline/`. Manifest chứa SHA-256 của 26 tài sản. API kiểm tra đủ file/hash trước khi nạp; thiếu hoặc sai file thì khởi động lỗi, không âm thầm chuyển sang model khác. Mã phục vụ không import `training/`, `tmp/`, dữ liệu ảnh hoặc các báo cáo nghiên cứu.

## Ảnh mới được tổng hợp thế nào?

Điểm OOF trước đây chấm mỗi ảnh bằng **một cấu hình của fold không train ảnh đó**. Để phục vụ ảnh mới, bản tích hợp chạy cả năm cấu hình rồi dùng quy tắc cố định sau:

1. Mỗi fold tạo nhãn B0/ConvNeXt và nhãn cuối E/G/S theo đúng lựa chọn đã khóa.
2. Đếm phiếu nhãn B0/ConvNeXt để tạo nhãn tham chiếu. Khi hòa phiếu, dùng điểm B0/ConvNeXt trung bình, làm tròn 12 chữ số thập phân; nếu vẫn hòa thì dùng thứ tự tám lớp đã quy định.
3. Đếm phiếu của năm nhãn cuối. Nếu nhãn tham chiếu là SkinCancer, giữ SkinCancer; nếu không, chỉ chọn trong bảy lớp còn lại. Như vậy giữ mặt nạ SkinCancer của bộ biểu quyết tham chiếu, không có thêm hoặc mất phiếu SkinCancer trong từng fold.
4. `confidence` và các số trong `top3[].probability` là **số fold đồng ý chia 5**, do hợp đồng API cũ giữ tên trường. API ghi rõ `score_type=fold_vote_fraction`, `confidence_is_calibrated=false`. Không đổi chỗ các giá trị để làm nhãn được chọn trông chắc chắn hơn.
5. Nhãn được đề xuất đứng đầu danh sách. Khi quy tắc bảo toàn làm nó khác nhãn có nhiều phiếu nhất, thứ tự có thể khác thứ tự tỷ lệ; bật `uncertain=true`. Hòa phiếu hoặc mức đồng thuận thấp cũng được đánh dấu chưa chắc chắn. Giao diện giải thích ý nghĩa tỷ lệ này.

Năm cấu hình có dữ liệu học chồng lặp; mức đồng thuận không phải xác suất mắc bệnh, độ chính xác hay ý kiến của năm bác sĩ. Quy tắc trên không tự chứng minh Recall SkinCancer trên ảnh mới đạt 88,04%.

Grad-CAM hiển thị vùng chú ý của **B0 fold 0**, với nhãn cuối được yêu cầu. Đây là ảnh minh họa của một thành viên, không phải giải thích đầy đủ cho cổng, specialist hoặc phép biểu quyết. Giao diện ghi rõ giới hạn đó.

## Đã kiểm tra

- Mã định tuyến phục vụ tính lại và khớp đủ **5.937/5.937 quyết định OOF**, gồm từng ensemble E, nhãn cuối và mặt nạ SkinCancer. Đây là kiểm tra chuyển mã, không phải một đợt đo độ chính xác mới.
- 22 kiểm thử backend: luật specialist, phiếu/Cancer, hòa phiếu, file/hash sai, quay về cấu hình cũ, OOD, chất lượng ảnh và Grad-CAM.
- Sáu kiểm thử giao diện liên quan; TypeScript và build frontend đạt.
- API qua FastAPI TestClient nạp thật 15 CNN và xử lý được ảnh Lupus, Psoriasis, Tinea; kiểm tra quyền truy cập, loại tệp và ảnh hỏng. Không tính ba ảnh này thành một bộ test độ chính xác.
- Thử riêng trên CPU với RAG thật: model và RAG sẵn sàng, có hướng dẫn và Grad-CAM; một lượt khoảng 0,70 giây sau khởi động, RAM tiến trình khoảng 1.865 MiB trên máy này. Đây là thử chức năng, chưa phải đo tải nhiều người dùng. Compose đặt giới hạn 4 GiB cho AI.
- `docker compose config --quiet` đạt. Docker engine đang tắt tại thời điểm tích hợp nên chưa khởi chạy hoặc kiểm tra lại toàn bộ hệ thống qua Docker/gateway.

[Đối chiếu OOF](../ai-service/reports/research_runtime_integration_20261108/branch_parity.json) · [Thử API](../ai-service/reports/research_runtime_integration_20261108/api_smoke.json) · [Thử CPU/RAG](../ai-service/reports/research_runtime_integration_20261108/cpu_smoke.json)

## Chạy và kiểm tra phiên bản

Package đã có trên máy hiện tại. Trên máy khác chưa có package, cần checkpoint nghiên cứu gốc rồi chạy từ thư mục `ai-service`:

```powershell
.\.venv\Scripts\python.exe training\export_research_runtime.py
```

Lệnh không ghi đè một package đã có manifest. Model/tensor không được đẩy lên GitHub; clone mã nguồn không tự có các file này.

Chạy API trực tiếp từ `ai-service`:

```powershell
$env:RAG_INDEX_PATH = 'rag-data'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`/health` phải trả `modelMode=research_pipeline`, `modelVersion=dermai-eight-esg-v1-20261108` và `modelReady=true`. Nếu đang có tiến trình API cũ, phải khởi động lại để nó nạp cấu hình mới.

Khi Docker hoạt động, từ thư mục gốc dự án:

```powershell
docker compose up -d --build ai-service frontend
```

Compose mount toàn bộ `ai-service/models/` ở `/models`; môi trường production dùng `AI_MODEL_DIR` cũng phải chứa package đầy đủ. Frontend cần build lại để hiển thị đúng ý nghĩa mức đồng thuận.

## Quay về B0 khi cần

Không xóa hoặc ghi đè `models/best_model.pth` và `models/ood_profile.json`. Khi chạy trực tiếp, đặt `RESEARCH_MANIFEST_PATH=off` rồi khởi động lại API. Khi dùng Compose, đặt `AI_RESEARCH_MANIFEST_PATH=off` trong môi trường Compose và tạo lại container AI.

## Điểm nào được phép báo cáo?

Mốc nghiên cứu OOF vẫn là **78,9456% Accuracy, 77,7287% Macro F1, 88,0355% Recall SkinCancer**. Chưa có điểm test độc lập cho bộ biểu quyết năm cấu hình đang phục vụ; manifest để các chỉ số đó là `null`. Không gắn điểm OOF cho bộ biểu quyết hoặc gọi phần trăm đồng thuận trên một ảnh là độ chính xác của ứng dụng.

Các trường `serving_changed=false`, hash cấu hình cũ và câu “API dùng B0 đơn” trong protocol/báo cáo lịch sử giữ nguyên theo thời điểm thực hiện. Trạng thái phục vụ hiện hành xem ở manifest, `/health` và tài liệu này.
