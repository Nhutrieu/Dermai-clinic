# Hướng dẫn thư mục training

Đọc [danh mục script](../DANH_MUC_TRAIN_MODEL.md) để biết từng file train,
chuẩn bị dữ liệu hay chỉ đánh giá. API hiện dùng EfficientNet-B0 đơn;
ensemble là pipeline nghiên cứu riêng.

Luồng nghiên cứu tám bệnh:

1. `prepare_scene_grouped_oof_folds.py`: chia nhóm ca/cảnh thành năm fold.
2. `prepare_scene_grouped_oof_inner_splits.py`: chia train/inner validation.
3. `run_scene_grouped_oof.py`: huấn luyện B0 và ConvNeXt.
4. `pilot_original_eight_resnet50.py`, `run_original_eight_resnet50_cv.py`: huấn luyện ResNet50.
5. `prepare_scene_grouped_oof_inner_predictions.py`: tạo dự đoán inner.
6. `evaluate_scene_grouped_oof_classwise_fusion.py`, `evaluate_original_eight_cancer_locked_fusion.py`: đánh giá phép gộp đã quy định.

`train_v2.py` là chương trình train dùng chung. Chọn checkpoint, ngưỡng và
phương án bằng validation đúng giao thức; không chọn lại bằng điểm outer.

Xem [pipeline đang giữ](../../docs/GIAI_TRINH_PIPELINE_AI_CHO_THAY_20261108.md)
và [báo cáo cần giữ / cách khôi phục lịch sử](../reports/README.md).
Một số script có đường dẫn cố định và không cho ghi đè kết quả cũ. Đọc
protocol và khôi phục đúng báo cáo phụ thuộc trước khi tái lập thí nghiệm.
