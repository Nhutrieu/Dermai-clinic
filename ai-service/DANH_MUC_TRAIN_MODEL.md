# Danh mục train model: từng file dùng để làm gì?

Phạm vi: `ai-service/training/`. Hướng đang giữ gồm tám nhóm bệnh gốc với
EfficientNet-B0, ConvNeXt-Tiny và ResNet50; API mặc định dùng pipeline E/G/S
năm fold theo [bản tích hợp ngày 08/11/2026](../docs/AP_DUNG_PIPELINE_AI_20261108.md).
Các bảng dưới đây giải thích chức năng script, không yêu cầu chạy tất cả.

Trạng thái kết quả hiện tại nằm trong [tổng hợp nghiên cứu](../docs/ai-research-summary.md).
Các lượt thử cũ được lưu trong [bản nén lịch sử và hướng dẫn khôi phục](reports/README.md).
Khôi phục dữ liệu phụ thuộc trước khi chạy lại script của một thí nghiệm đã lưu.

## 1. Muốn train model nào thì xem file nào trước?

| Bạn muốn làm gì? | File cần xem | Train gì, dùng dữ liệu gì? | Kết quả chính |
|---|---|---|---|
| Train một model phân loại tám bệnh | [train_v2.py](training/train_v2.py) | Chọn `--model efficientnet_b0`, `convnext_tiny` hoặc `resnet50`; ảnh và cách chia do tham số quy định. | `best_model.pth`, log và báo cáo chọn checkpoint trong `--output`. |
| Train B0 và ConvNeXt đủ năm fold theo cấu hình nghiên cứu | [run_scene_grouped_oof.py](training/run_scene_grouped_oof.py) | Gọi `train_v2.py` cho B0/ConvNeXt, dùng ảnh nguồn cũ và SCIN theo manifest chia nhóm. | `candidates/oof_b0_fold{0..4}_seed42/` và `oof_convnext_fold{0..4}_seed42/`. |
| Train ResNet50 cho fold 0 của bộ tám bệnh | [pilot_original_eight_resnet50.py](training/pilot_original_eight_resnet50.py) | ResNet50 khởi tạo ImageNet, tối đa 24 epoch; dùng các vai trò dữ liệu của fold 0. | `candidates/original_eight_resnet50_pilot_fold0_seed42/`. |
| Hoàn thành năm fold ResNet50 | [run_original_eight_resnet50_cv.py](training/run_original_eight_resnet50_cv.py) | Tái dùng fold 0 đã kiểm chứng, train thêm fold 1–4. | `candidates/original_eight_resnet50_cv_fold{1..4}_seed42/`. |
| Xem lượt train thử ImageNet và MixUp mới nhất | [pilot_original_eight_imagenet_mixup.py](training/pilot_original_eight_imagenet_mixup.py) | Hai nhánh ResNet50 cùng khởi tạo ImageNet V2: thường và MixUp; chỉ fold 0. | `candidates/original_eight_imagenet_mixup_fold0_seed42_20261021/`. |

**Fold** là một phần dữ liệu trong cách chia nhiều lượt. **OOF** là dự đoán cho ảnh bằng model của lượt không dùng ảnh đó để train. Với năm fold, mỗi ảnh có một dự đoán OOF. Chọn checkpoint và trọng số gộp dùng validation bên trong từng fold.

### Trình tự của luồng tám bệnh trong nghiên cứu

1. `prepare_scene_grouped_oof_folds.py`: chuẩn bị năm fold, giữ ảnh cùng ca/cảnh trong cùng nhóm.
2. `prepare_scene_grouped_oof_inner_splits.py`: chuẩn bị train và validation bên trong mỗi fold.
3. `run_scene_grouped_oof.py`: train B0 và ConvNeXt qua năm fold.
4. `pilot_original_eight_resnet50.py`, sau đó `run_original_eight_resnet50_cv.py`: train ResNet50 qua năm fold.
5. `prepare_scene_grouped_oof_inner_predictions.py`: lấy dự đoán validation B0/ConvNeXt để chọn trọng số theo bệnh.
6. `evaluate_scene_grouped_oof_classwise_fusion.py`: tính bản gộp B0/ConvNeXt; `evaluate_original_eight_cancer_locked_fusion.py`: thử thêm ResNet và giữ quyết định SkinCancer của bản tham chiếu.

Đây là thứ tự để hiểu luồng đã thực hiện. Khi chạy lại, xem giao thức và thư mục đầu ra trong `reports/` trước: nhiều chương trình dùng đường dẫn cố định và giữ nguyên kết quả đã hoàn tất. Các script đánh giá/gộp ở bước cuối không train thêm một CNN.

## 2. Các file thực sự train model hoặc đầu phân loại

### 2.1. Phân loại tám bệnh và các runner chính

| File | Train gì? | Vai trò |
|---|---|---|
| [train.py](training/train.py) | B0, ConvNeXt-Tiny hoặc ResNet50 cho tám bệnh, theo tham số `--model`. | Luồng cũ, có đánh giá trên test cố định lịch sử; giữ để đối chiếu. |
| [train_v2.py](training/train_v2.py) | B0, ConvNeXt-Tiny hoặc ResNet50 cho tám bệnh; chọn checkpoint bằng validation. | Bộ train dùng chung của V2 và B0/ConvNeXt OOF. |
| [run_scene_grouped_oof.py](training/run_scene_grouped_oof.py) | Điều phối B0/ConvNeXt qua năm fold bằng `train_v2.py`. | Runner của nghiên cứu tám bệnh. |
| [pilot_original_eight_resnet50.py](training/pilot_original_eight_resnet50.py) | ResNet50 tám bệnh, fold 0. | Pilot ban đầu, đồng thời là nguồn checkpoint fold 0. |
| [run_original_eight_resnet50_cv.py](training/run_original_eight_resnet50_cv.py) | Train thêm bốn ResNet50 cho fold 1–4. | Hoàn thành năm checkpoint ResNet50. |

### 2.2. Các thử nghiệm cải thiện model tám bệnh

Các file dưới đây thử những cách học khác nhau. Có file train tiếp checkpoint cũ, có file chỉ học một đầu phụ. **Có kết quả thí nghiệm không có nghĩa là đã được chọn thay bản đang giữ.** Xem kết luận từng lượt trong `reports/`.

| File | Train gì hoặc học thêm điều gì? |
|---|---|
| [train_supcon_convnext.py](training/train_supcon_convnext.py) | Fine-tune ConvNeXt-Tiny tám bệnh với CE và học đối sánh có giám sát SupCon. |
| [train_source_balance_convnext.py](training/train_source_balance_convnext.py) | Train tiếp ConvNeXt-Tiny; so lấy mẫu thường với cân bằng theo nguồn ảnh. |
| [run_original_eight_focus_replay.py](training/run_original_eight_focus_replay.py) | Train tiếp ConvNeXt-Tiny qua năm fold; so đối chứng với ưu tiên nhẹ ba bệnh yếu, cùng bốn epoch bổ sung. |
| [train_dermacon_adaptation.py](training/train_dermacon_adaptation.py) | Fine-tune EfficientNet-B0 tám bệnh; thử lấy mẫu bổ sung từ DermaCon so với đối chứng. |
| [pilot_original_eight_supplement_adaptation.py](training/pilot_original_eight_supplement_adaptation.py) | Train tiếp ResNet50 fold 0 trong ba epoch; so replay ảnh cũ với bổ sung ảnh DermaCon/Lupus. |
| [pilot_original_eight_ensemble_teacher.py](training/pilot_original_eight_ensemble_teacher.py) | Train tiếp ResNet50 học cả nhãn và đầu ra mềm B0/ConvNeXt; so với nhánh không có loss teacher. |
| [pilot_original_eight_pad_addition.py](training/pilot_original_eight_pad_addition.py) | Train tiếp ResNet50; thử thêm ảnh cancer từ PAD vào lịch lấy mẫu, có đối chứng. |
| [pilot_original_eight_negative_supervision.py](training/pilot_original_eight_negative_supervision.py) | Train tiếp ResNet50; thêm loss “không thuộc SkinCancer” cho PAD NEV/SEK. Bản thử ban đầu dùng AMP, giữ để đối chiếu vấn đề cập nhật. |
| [pilot_original_eight_negative_supervision_fp32.py](training/pilot_original_eight_negative_supervision_fp32.py) | Lặp thí nghiệm nhãn phủ định bằng FP32 để kiểm chứng cập nhật; NEV/SEK không bị ép thành nhãn bệnh trong tám lớp. |
| [pilot_original_eight_balanced_softmax.py](training/pilot_original_eight_balanced_softmax.py) | Train tiếp ResNet50 fold 0, ba epoch; so CE với Balanced Softmax để xử lý mất cân bằng lớp. |
| [pilot_original_eight_psoriasis_replay.py](training/pilot_original_eight_psoriasis_replay.py) | Train tiếp ResNet50; thử 321 ảnh Psoriasis phụ đã audit, giữ số vị trí mỗi lớp và nhánh đối chứng. |
| [pilot_original_eight_source_softlabels.py](training/pilot_original_eight_source_softlabels.py) | Train tiếp ResNet50; so nhãn cứng với phân bố nhãn mềm từ nguồn SCIN trên phần train fold 0. |
| [pilot_original_eight_imagenet_mixup.py](training/pilot_original_eight_imagenet_mixup.py) | Train mới hai nhánh ResNet50 cùng khởi tạo ImageNet V2: thường và MixUp, 24 epoch mỗi nhánh. |
| [run_teacher_priorities_ensemble_specialist.py](training/run_teacher_priorities_ensemble_specialist.py) | Thực hiện hai ưu tiên của thầy qua năm fold: A chỉ chọn tỷ trọng ResNet trong ensemble; B học đầu chuyên biệt Lupus/Psoriasis/Tinea/Eczema/Khác trên ResNet cố định. Hai phép thử tách biệt, không train thêm backbone. |
| [run_teacher_balanced_specialist.py](training/run_teacher_balanced_specialist.py) | Lượt tiếp theo của đầu chuyên biệt: chỉ thay loss bằng trọng số lớp cân bằng qua năm fold, đối chứng với đầu B không cân bằng; giữ cùng cache, scaler, mức điều chuẩn và ngưỡng, không train lại CNN. |
| [run_teacher_hard_mining_specialist.py](training/run_teacher_hard_mining_specialist.py) | Một lượt mining cố định: dùng ba đầu tạm chấm các nhóm giữ lại bên trong train, ưu tiên 25% ảnh khó mỗi lớp rồi học đầu chuyên biệt qua năm fold. Không dùng lỗi validation/outer để mining; không train thêm backbone. |
| [pilot_teacher_partial_resnet.py](training/pilot_teacher_partial_resnet.py) | Pilot fold 0: so chỉ học fc với học layer4+fc của cùng ResNet50 tám nhãn, sáu epoch mỗi nhánh. Cùng loss ưu tiên nhẹ ba bệnh yếu, giữ BatchNorm cố định; chỉ định tuyến lại nhóm Lupus/Psoriasis/Tinea/Eczema và giữ SkinCancer. Chưa phải train mới đủ năm fold. |
| [run_teacher_logprob_stacking.py](training/run_teacher_logprob_stacking.py) | Học bộ gộp Logistic Regression từ 24 log-điểm của ba CNN gốc. Mỗi outer fold chỉ học trên inner validation của chính fold đó; ba phần cross-fit theo nhóm để chọn, rồi học đầu cuối trên toàn inner. Giữ mọi quyết định SkinCancer, không train thêm CNN, không gộp OOF các fold khác làm train. Đã thử đủ năm fold; điểm bản thử và bản được chọn được báo riêng. |
| [run_teacher_conservative_gate.py](training/run_teacher_conservative_gate.py) | Học cổng giữ baseline hay chuyển sang stacking đã cố định; Logistic Regression nhị phân từ 22 đặc trưng điểm/phiếu model, ngưỡng chuyển >2/3. Chia inner ba phần, bên trong mỗi phần fit lại chia hai nhóm để tạo target cổng không dùng nhãn meta-held. Đủ năm fold, 50 fit stack + 20 fit cổng; không cập nhật CNN. Validation chọn cổng ở fold 0/3, tổng thăm dò 78,81% Accuracy/77,54% Macro F1; F1 Psoriasis/Tinea vẫn giảm nhẹ. |
| [run_teacher_macro_f1_gate.py](training/run_teacher_macro_f1_gate.py) | Đối chứng cổng cũ với cổng học theo tác động từng lần chuyển lên Macro F1, gồm đổi nhãn sai→sai. Tái dùng candidate lồng nhau đã khóa, 22 đặc trưng/scaler/ngưỡng chung, chuẩn hóa tổng trọng số loss bằng đối chứng. Fit 20 cổng đối chứng + 20 cổng utility, không train CNN hoặc stack mới. Validation chọn utility ở fold 0/3; 78,93% Accuracy/77,72% Macro F1 trên bộ phát triển, chưa cải thiện toàn bộ recall/bệnh. |
| [run_teacher_nonlinear_specialist.py](training/run_teacher_nonlinear_specialist.py) | Kiểm tra đầu chuyên biệt phi tuyến: hai lớp 2048→128→5 cùng tham số/khởi tạo, đối chứng identity so ReLU, cùng AdamW và train gốc mỗi ảnh một lần/epoch. Đủ 10 đầu/20 epoch qua năm fold, không train CNN; giữ cổng yếu 0,8 và SkinCancer. ReLU 78,41%/77,31% chưa hơn cổng hiện có; cả năm validation giữ 78,93%/77,72%. |
| [run_teacher_dropout_specialist.py](training/run_teacher_dropout_specialist.py) | Thử giảm quá khớp đầu ReLU: chỉ thêm Dropout lớp ẩn p=0,5, đối chứng p=0 tái lập ReLU cũ. Cùng train/scaler/batch/20 epoch và ngưỡng 0,8, RNG Dropout độc lập lịch lấy ảnh. Đủ 10 đầu qua năm fold, không train CNN. Validation chọn Dropout fold 1/2; 78,95%/77,73%, đúng thêm một ảnh so cổng 78,93%/77,72%, nhưng Recall/F1 Psoriasis giảm và chưa hết quá khớp. Kiểm tra nguồn chưa tốt đều; kiểm chứng chính/nguồn PASS, 184/184 kiểm thử đạt. |
| [pilot_teacher_multifeature_specialist.py](training/pilot_teacher_multifeature_specialist.py) | Pilot fold 0: đầu logistic từ 4.096 đặc trưng ghép B0/ConvNeXt/ResNet, so đầu 2.048 đặc trưng ResNet. Train 4.043 ảnh, scaler và hệ số cân năng lượng chỉ tính từ train, C=0,001/ngưỡng 0,8 cố định. Chọn bằng 718 validation trước 1.176 outer và 1.709 ảnh nguồn. Chưa đạt Lupus/Tinea/Macro F1 trên validation, giữ bản trước; không train CNN hoặc đổi điểm tổng 5.937 ảnh. |
| [pilot_teacher_class_expert_bank.py](training/pilot_teacher_class_expert_bank.py) | Pilot fold 0: học ba đầu riêng trên đặc trưng B0/ConvNeXt/ResNet. So chọn chung một đầu với chọn theo nhãn hiện đang dự đoán. Chọn bằng ba phần inner theo nhóm trước khi khóa và chấm outer/nguồn; ngưỡng 0,8/mask SkinCancer giữ nguyên. Chưa giữ Recall/F1 Psoriasis trên inner giữ riêng; không thay bản nghiên cứu trước. [Báo cáo và phân tích khả năng sửa lỗi](reports/teacher_class_expert_bank_fold0_seed42_20261024/summary.md). |
| [pilot_teacher_pairwise_specialists.py](training/pilot_teacher_pairwise_specialists.py) | Pilot fold 0: từ train-head cross-fit theo nhóm chọn ba cặp Lupus–Acne, Psoriasis–Eczema, Tinea–Eczema; so điểm cặp từ đầu tám nhãn với ba đầu binary học riêng trên ResNet cố định. Bảy fit tổng cộng, loss-weight mass/C/scaler/ngưỡng chung, khóa cặp trước inner và lựa chọn trước outer. Macro F1 inner tăng nhẹ nhưng Accuracy/Recall bệnh yếu giảm; chưa chọn. [Báo cáo](reports/teacher_pairwise_specialists_fold0_seed42_20261024/summary.md). |
| [pilot_teacher_balanced_pairs.py](training/pilot_teacher_balanced_pairs.py) | Chỉ đổi loss binary của ba cặp đã khóa sang khối lượng hai lớp 50/50, cùng đặc trưng/scaler/C/tổng loss-weight mass/ngưỡng. Sáu fit gồm ba đối chứng tái lập đúng đầu cũ và ba đầu cân; F1 Lupus/Psoriasis inner tăng so bản đang giữ nhưng Recall ba bệnh/Tinea F1 giảm nên chưa chọn. [Báo cáo](reports/teacher_balanced_pairs_fold0_seed42_20261024/summary.md). |
| [pilot_teacher_spatial_multicrop.py](training/pilot_teacher_spatial_multicrop.py) | Đổi biểu diễn ảnh: resize320, năm vùng góc/giữa224, mean đặc trưng ResNet trong mỗi ảnh rồi học đầu 2.048→5. So đầu cùng kích thước trên crop giữa cũ, cùng C/ngưỡng/scaler train/cân năng lượng; hai đầu, 38.230 lượt crop, không thêm ảnh độc lập hoặc cập nhật CNN. Inner Accuracy/Psoriasis tăng nhưng Lupus/Macro F1/Tinea F1 giảm nên chưa chọn. [Báo cáo](reports/teacher_spatial_multicrop_fold0_seed42_20261024/summary.md). |
| [pilot_teacher_focal_cnn.py](training/pilot_teacher_focal_cnn.py) | Fine-tune thực sự layer4+fc của ResNet gốc: hai nhánh CE và Focal gamma=2, cùng sáu epoch, thứ tự/augmentation/trọng số lớp/LR và BN cố định. 1.518 cập nhật/nhánh, không thêm backbone; chọn checkpoint trên 718 inner và khóa trước outer/nguồn. Lưu probe loss, xác suất từng epoch, trạng thái optimizer và best checkpoint. [Báo cáo](reports/teacher_focal_cnn_fold0_seed42_20261024/summary.md). |
| [pilot_teacher_sam_cnn.py](training/pilot_teacher_sam_cnn.py) | Hai nhánh CNN ResNet layer4+fc: AdamW CE đối chứng và SAM–AdamW bán kính 0,05. Cùng sáu epoch/4.043 ảnh/augmentation/LR/trọng số loss; SAM tính gradient hai lần trên cùng batch rồi khôi phục trọng số chính xác trước cập nhật. Chỉ hỗ trợ Tinea–Eczema, giữ sáu lớp ngoài cặp. Inner chọn SAM epoch 5; inner 77,86% Accuracy/76,90% Macro F1, outer 79,08%/78,32%. Mới một fold, chưa đổi điểm tổng/API. [Báo cáo và kiểm chứng](reports/teacher_sam_cnn_fold0_seed42_20261025/summary.md). |
| [run_teacher_sam_cv.py](training/run_teacher_sam_cv.py) | Hoàn tất SAM đủ năm fold: tái dùng hai nhánh fold 0, train tám nhánh CE/SAM mới, sáu epoch/nhánh. Inner chọn SAM fold 0/1, CE fold 2, current fold 3/4; chỉ hỗ trợ Tinea–Eczema. OOF đúng 4.688 so bản giữ 4.687, Accuracy 78,9624% / Macro F1 77,7551%, Recall SkinCancer giữ 88,0355%. Tinea Recall tăng nhưng Eczema giảm; khoảng bất định chứa 0, official test DermaCon lịch sử giảm. [Báo cáo và kiểm chứng](reports/teacher_sam_cv_seed42_20261025/summary.md). Suy luận độc lập 28.898 lượt ảnh/362 bộ chỉ số khớp; chưa thay bản nghiên cứu/API. |
| [run_teacher_sam_seed_repeat.py](training/run_teacher_sam_seed_repeat.py) | Hoàn tất lặp CE/SAM bằng seed dữ liệu 43: năm fold/mười nhánh/sáu epoch, cùng parent, chỉ đổi order/augmentation. Lựa chọn trùng seed 42 nhưng OOF đúng 4.673 so nền 4.687 và seed 42 4.688; Accuracy 78,7098% / MF 77,6068%, Recall SkinCancer giữ 88,0355%. Chưa lặp mức tăng cũ; không trộn/chọn seed theo OOF. [Báo cáo](reports/teacher_sam_cv_seed43_20261025/summary.md). Forward độc lập 36.104 lượt ảnh/363 bộ chỉ số và năm probe SAM đầu khớp. Chỉ lặp continuation, không khởi tạo CNN độc lập hoặc đổi API/bản giữ. |
| [pilot_teacher_cosine_classifier.py](training/pilot_teacher_cosine_classifier.py) | Hai đầu tám nhãn trên đặc trưng ResNet cố định: tuyến tính với cosine, cùng 4.043 ảnh/khởi tạo/scale 16/400 cập nhật Adam FP64. Chỉ hỗ trợ nhầm lẫn Lupus/Psoriasis với Acne/Eczema; giữ Cancer/Candidiasis/Tinea/Warts. Inner tuyến tính Macro F1 77,20% nhưng giảm Recall Lupus; cosine 76,65% so nền 76,82%, chưa chọn. [Báo cáo và bài báo tham khảo](reports/teacher_cosine_classifier_fold0_seed42_20261025/summary.md). Hai refit độc lập NumPy/800 cập nhật, 43 bộ chỉ số khớp; không train/forward CNN mới, không đổi điểm tổng/API. |
| [pilot_teacher_ldam_classifier.py](training/pilot_teacher_ldam_classifier.py) | Hai đầu cosine tám nhãn, CE đối chứng với LDAM theo số ảnh train; cùng 4.043 ảnh/400 cập nhật. | Pilot inner-only Lupus/Psoriasis; chưa qua guard, không chấm outer/source. [Báo cáo](reports/teacher_ldam_classifier_fold0_seed42_20261025/summary.md). |
| [train_source_aware_resnet_baseline.py](training/train_source_aware_resnet_baseline.py) | Baseline ResNet50 từ ImageNet trên chia nguồn/bệnh mới; fold 0, 4.043 train/718 inner, 24 epoch, raw/EMA và khôi phục từng epoch. | Không dùng checkpoint cũ hoặc chấm outer. [Trạng thái và kết quả](reports/teacher_source_aware_resnet_baseline_fold0_seed42_20261026/summary.md). |
| [train_source_aware_l2sp.py](training/train_source_aware_l2sp.py) | Train ResNet50 mới từ ImageNet, cùng baseline 24 epoch/fold 0; thêm phạt L2-SP vào backbone, hệ số 0,01. | So riêng trên 718 inner mới; giữ điều kiện SkinCancer và ba bệnh yếu. [Theo dõi](reports/teacher_source_aware_l2sp_fold0_seed42_20261026/summary.md). |
| [pilot_teacher_case_retrieval.py](training/pilot_teacher_case_retrieval.py) | Tra bảy nhóm train gần nhất từ đặc trưng L2 của ba CNN gốc; 4.043 ảnh/3.602 nhóm, mỗi nhóm tối đa một phiếu và chặn trùng path/SHA/group với query. So phiếu đều với nghịch khoảng cách, k/ngưỡng cố định. Chưa giữ Lupus/Tinea F1 và tổng trên inner; không train thêm CNN. [Báo cáo, hàng xóm và ảnh đối chiếu](reports/teacher_case_retrieval_fold0_seed42_20261024/summary.md). |
| [pilot_teacher_group_dro.py](training/pilot_teacher_group_dro.py) | Học hai đầu tuyến tính trên ResNet cố định: trọng số cố định so Group DRO cho 15 nhóm bệnh–nguồn, trung bình theo ca/cảnh trong mỗi nhóm. Cùng 4.043 ảnh, 400 cập nhật/head, scaler train-only, L2 và ngưỡng như giao thức. Tinea Recall tăng một ảnh nhưng Lupus/Psoriasis và Macro F1 chưa giữ được; chưa chọn, không train CNN. [Báo cáo đối chứng và trọng số nhóm](reports/teacher_group_dro_fold0_seed42_20261024/summary.md). |
| [pilot_teacher_dro_pair_gate.py](training/pilot_teacher_dro_pair_gate.py) | Giữ bản hiện tại làm nền, chỉ cho DRO hỗ trợ Tinea–Eczema. So điểm cố định ≥0,8 với cổng logistic cross-fit ba phần nhóm trên 718 inner; bốn fit, không train CNN/DRO mới. Validation chọn quy tắc cố định nhưng outer fold 0 giảm một ảnh đúng; chưa áp dụng toàn bộ năm fold. [Báo cáo kết hợp](reports/teacher_dro_pair_gate_fold0_seed42_20261024/summary.md). |
| [run_teacher_dro_pair_cv.py](training/run_teacher_dro_pair_cv.py) | Kiểm tra quy tắc cặp đã qua validation trên đủ năm fold; tái dùng đầu DRO fold 0, train bốn đầu còn lại trên ResNet cố định với cùng cấu hình. Chọn hỗ trợ ở fold 0/3, giữ nền ba fold khác. Trên 5.937 OOF Tinea thêm ba ảnh đúng, Eczema mất bốn; tổng 4.686 đúng so 4.687, chưa thay bản đang giữ. Không train CNN. [Kết quả OOF và 1.709 ảnh nguồn](reports/teacher_dro_pair_cv_seed42_20261024/summary.md). |
| [pilot_teacher_balanced_sampling.py](training/pilot_teacher_balanced_sampling.py) | Pilot class-balanced sampling ở fold 0: hai ResNet50 cùng checkpoint, cùng layer4+fc và CE không trọng số, sáu epoch mỗi nhánh. Chỉ thay lịch lấy 4.043 ảnh/epoch: mỗi ảnh một lần so với lấy có hoàn lại theo nghịch đảo số ảnh từng lớp. Giữ cổng chuyên biệt và quyết định SkinCancer; không coi lượt ảnh lặp là ảnh mới hoặc điểm một fold là điểm tổng. |
| [pilot_teacher_coral_head.py](training/pilot_teacher_coral_head.py) | Pilot hai đầu nhỏ trên 2.048 đặc trưng ResNet cố định: Linear/LayerNorm/ReLU 128 chiều và đầu tám nhãn. Cùng 4.043 train gốc + 590 DermaCon train phụ, 20 epoch, đối chứng CE so CE + CORAL covariance loss; chỉ nhánh sau thêm căn chỉnh trên batch train. Không cập nhật CNN, dùng hai validation để chọn, khóa trước chấm phần giữ lại; chỉ fold 0. |
| [pilot_teacher_coral_retention.py](training/pilot_teacher_coral_retention.py) | Tái lập đầu CORAL làm đối chứng, so với cùng đầu có thêm distillation giữ đầu ra ResNet gốc trên 4.043 ảnh train gốc. Teacher dùng fc gốc trên đặc trưng thô, T=2, hệ số 1; không lấy target từ validation/test hoặc ảnh phụ. Hai nhánh cùng batch/20 epoch, hai validation, chỉ fold 0; chưa đạt điều kiện, giữ baseline. |

### 2.3. Chỉ học đầu phụ, không train lại toàn bộ CNN

| File | Học gì? |
|---|---|
| [pilot_original_eight_frozen_cancer_head.py](training/pilot_original_eight_frozen_cancer_head.py) | Giữ nguyên ResNet50 lấy đặc trưng; học Logistic Regression hai nhóm cancer/không cancer hoặc năm nhóm nguồn PAD. |
| [pilot_original_eight_cancer_head_original_replay.py](training/pilot_original_eight_cancer_head_original_replay.py) | Học đầu cancer nhị phân từ đặc trưng cố định; so chỉ dùng PAD với thêm replay ảnh train tám bệnh. |
| [pilot_original_eight_psoriasis_verifier.py](training/pilot_original_eight_psoriasis_verifier.py) | Học đầu kiểm tra Psoriasis từ đặc trưng cố định; so train gốc với thêm ảnh phụ, không cập nhật backbone. |

### 2.4. Train cổng kiểm tra ảnh ngoài phạm vi

Các file này học cách phân biệt ảnh thuộc/ngoài phạm vi dữ liệu (**OOD**), không phải model mới để phân loại tám bệnh.

| File | Train gì? |
|---|---|
| [train_scope_gate.py](training/train_scope_gate.py) | Cổng Logistic Regression nhị phân từ đặc trưng ảnh để nhận diện ảnh ngoài phạm vi. |
| [train_wound_scope_gate.py](training/train_wound_scope_gate.py) | Cổng phạm vi có bổ sung ảnh vết thương WSeg và ảnh da ngoài phạm vi. |
| [train_wound_mlp_from_cache.py](training/train_wound_mlp_from_cache.py) | Cổng MLP từ cache đặc trưng của thí nghiệm WSeg. |
| [train_broad_ood_mlp.py](training/train_broad_ood_mlp.py) | Cổng MLP từ cache ảnh thuộc phạm vi và ảnh ngoài phạm vi đa dạng. |

### 2.5. Thử nghiệm năm bệnh đã ngừng dùng

| File | Làm gì? |
|---|---|
| [five_disease_scope_trial.py](training/five_disease_scope_trial.py) | Hàm dùng chung, kế hoạch và kiểm tra cho thử nghiệm chỉ giữ Acne, Candidiasis, Eczema, SkinCancer, Warts. Không tự chạy toàn bộ lượt train. |
| [run_five_disease_scope_trial.py](training/run_five_disease_scope_trial.py) | Runner train B0/ConvNeXt năm bệnh qua năm fold, đánh giá và so với bản tám bệnh. |

Hướng này đã dừng khi quay lại tám bệnh. 50 file đầu ra, gồm 10 checkpoint, đã được [lưu riêng](../backups/five_disease_trial_20261022/README.md). Khôi phục trước khi chạy lại việc kiểm chứng cần đọc các file đó.

## 3. Chuẩn bị dữ liệu và dự đoán đầu vào — không train model

| File | Làm gì? |
|---|---|
| [download_fitzpatrick_c_supplement.py](training/download_fitzpatrick_c_supplement.py) | Tải các ảnh Fitzpatrick17k-C được chọn, kiểm CRC/MD5 và ghi bằng chứng nguồn. |
| [download_original_eight_lupus_supplement.py](training/download_original_eight_lupus_supplement.py) | Lấy ảnh Lupus atlas thuộc phần train nguồn đã sửa nhãn để bổ sung tám bệnh. |
| [prepare_original_eight_supplement.py](training/prepare_original_eight_supplement.py) | Rà trùng/chồng lấn ảnh phụ DermaCon và Lupus với các vai trò được bảo vệ. |
| [prepare_original_eight_psoriasis_supplement.py](training/prepare_original_eight_psoriasis_supplement.py) | Chọn ảnh Psoriasis phụ từ cache, cách ly ảnh nghi trùng và tạo danh sách train. |
| [inventory_original_eight_pad_train.py](training/inventory_original_eight_pad_train.py) | Kiểm kê ứng viên cancer từ PAD train lịch sử; chưa tự đưa vào train. |
| [prepare_original_eight_pad_supplement.py](training/prepare_original_eight_pad_supplement.py) | Rà theo người bệnh và nhóm ảnh liên quan trước khi dùng PAD cancer bổ sung. |
| [prepare_original_eight_pad_joint.py](training/prepare_original_eight_pad_joint.py) | Audit chung PAD cancer và NEV/SEK; tách vai trò nhãn cancer và nhãn phủ định. |
| [prepare_dermacon_holdout.py](training/prepare_dermacon_holdout.py) | Chuẩn bị danh sách ảnh DermaCon để đánh giá nguồn ngoài và kiểm thông tin nguồn. |
| [extract_dermacon_holdout.py](training/extract_dermacon_holdout.py) | Trích xuất đúng các ảnh DermaCon đã chọn từ archive được kiểm tra. |
| [finalize_dermacon_holdout.py](training/finalize_dermacon_holdout.py) | Loại ảnh gần trùng theo dHash trước suy luận để chốt tập DermaCon. |
| [prepare_dermacon_adaptation.py](training/prepare_dermacon_adaptation.py) | Tạo các phần phát triển DermaCon tách theo ca/người có thông tin. |
| [prepare_leak_aware_development_split.py](training/prepare_leak_aware_development_split.py) | Tạo cách chia phát triển có nhóm ảnh gần trùng; không sửa hồi tố điểm lịch sử. |
| [prepare_scene_grouped_oof_folds.py](training/prepare_scene_grouped_oof_folds.py) | Chốt năm outer fold theo ca và liên kết ảnh cùng cảnh. |
| [prepare_scene_grouped_oof_inner_splits.py](training/prepare_scene_grouped_oof_inner_splits.py) | Chốt train/validation bên trong từng outer fold để chọn checkpoint. |
| [prepare_scene_grouped_oof_inner_predictions.py](training/prepare_scene_grouped_oof_inner_predictions.py) | Dùng checkpoint B0/ConvNeXt đã có dự đoán inner validation cho việc gộp. |
| [build_validation_review_queue.py](training/build_validation_review_queue.py) | Tạo danh sách ảnh validation cần người có chuyên môn rà soát; không tự sửa nhãn. |
| [build_broad_ood_cache.py](training/build_broad_ood_cache.py) | Tạo/bổ sung cache đặc trưng ảnh ngoài phạm vi cho các cổng OOD. |
| [build_ood_profile.py](training/build_ood_profile.py) | Tạo hồ sơ đặc trưng OOD từ model đã có. |
| [add_hard_negative_exemplar.py](training/add_hard_negative_exemplar.py) | Bổ sung mẫu ngoài phạm vi đã xác nhận vào hồ sơ OOD. |

## 4. Đánh giá, hiệu chỉnh và gộp — không train lại CNN

Một số file chọn trọng số, temperature hoặc ngưỡng trên validation. Đây là hiệu chỉnh/gộp model có sẵn, không phải train một CNN mới. Điểm OOF là kết quả phát triển; đánh giá chuyển nguồn và test độc lập cần được phân biệt trong báo cáo.

| File | Đánh giá hoặc hiệu chỉnh điều gì? |
|---|---|
| [evaluate.py](training/evaluate.py) | Đo checkpoint trên split được chỉ định. |
| [evaluate_evidence.py](training/evaluate_evidence.py) | Xuất bằng chứng về chỉ số, calibration, lỗi, độ trễ và OOD. |
| [evaluate_v2_candidate.py](training/evaluate_v2_candidate.py) | Hiệu chỉnh temperature của một candidate V2 bằng validation và đánh giá. |
| [evaluate_v2_ensemble.py](training/evaluate_v2_ensemble.py) | Chọn cách gộp hai checkpoint bằng validation, sau đó đo trên test. |
| [benchmark_paper_ensembles.py](training/benchmark_paper_ensembles.py) | So các công thức gộp xác suất/checkpoint theo thiết kế benchmark. |
| [evaluate_scene_grouped_oof_single.py](training/evaluate_scene_grouped_oof_single.py) | Tổng hợp dự đoán OOF năm fold của riêng một kiến trúc. |
| [evaluate_scene_grouped_oof_ensemble.py](training/evaluate_scene_grouped_oof_ensemble.py) | So các công thức gộp B0/ConvNeXt có trọng số cố định. |
| [evaluate_scene_grouped_oof_classwise_fusion.py](training/evaluate_scene_grouped_oof_classwise_fusion.py) | Chọn trọng số B0/ConvNeXt theo bệnh bằng inner validation rồi đo outer OOF. |
| [evaluate_scene_grouped_oof_weak_classes.py](training/evaluate_scene_grouped_oof_weak_classes.py) | Thử cách gộp chú trọng Lupus/Psoriasis, chọn trong inner validation. |
| [run_scene_grouped_oof_classwise_after_base.py](training/run_scene_grouped_oof_classwise_after_base.py) | Chờ báo cáo gộp cố định rồi chạy đánh giá gộp theo bệnh; không train. |
| [evaluate_original_eight_cancer_locked_fusion.py](training/evaluate_original_eight_cancer_locked_fusion.py) | Chọn cách thêm ResNet vào bản tham chiếu, giữ nguyên quyết định SkinCancer. |
| [pilot_original_eight_calibrated_classwise.py](training/pilot_original_eight_calibrated_classwise.py) | Thử calibration và trọng số theo bệnh từ dự đoán cố định, có chia nhóm; tên `pilot` nhưng không train lại model ảnh. |
| [evaluate_original_eight_resnet_transfer.py](training/evaluate_original_eight_resnet_transfer.py) | Đo 15 checkpoint cố định trên các nguồn đã khảo sát, với công thức gộp cố định. |
| [evaluate_teacher_stack_transfer.py](training/evaluate_teacher_stack_transfer.py) | Kiểm tra nguyên trạng stacking đã khóa trên 986 ảnh DermaCon và 723 ảnh SkinDisNet đã từng khảo sát. Chấm cùng ảnh bằng từng cặp model của năm fold, báo từng lượt và trung bình chỉ số; không tạo classifier gộp năm fold mới. Tách vai trò train phụ/validation/test lịch sử, không fit/chọn lại hoặc gọi đây là test độc lập mới. |
| [evaluate_new_ensemble_holdout.py](training/evaluate_new_ensemble_holdout.py) | Kiểm trùng và so checkpoint trên bộ ảnh đánh giá tám lớp được cung cấp. Chữ `new` nói về holdout mới, không tự xác nhận đó là test độc lập. |
| [evaluate_pad_ufes_cancer_flag.py](training/evaluate_pad_ufes_cancer_flag.py) | Rà nguồn PAD-UFES-20 và đo các lần model gán SkinCancer. |
| [calibrate_production.py](training/calibrate_production.py) | Fit temperature trên validation cho checkpoint sản xuất; không dùng test để fit. |
| [calibrate_scope_gate.py](training/calibrate_scope_gate.py) | Hiệu chỉnh ngưỡng cổng phạm vi trên ảnh hợp lệ. |
| [calibrate_support_gate.py](training/calibrate_support_gate.py) | Hiệu chỉnh ngưỡng độ phủ đặc trưng/prototype cho cổng ngoài miền dữ liệu. |
| [evaluate_ood_benchmark.py](training/evaluate_ood_benchmark.py) | Đo khả năng nhận diện các nhóm ảnh ngoài tám lớp. |
| [evaluate_ood_profile.py](training/evaluate_ood_profile.py) | Đo tỷ lệ hồ sơ OOD từ chối nhầm ảnh da hợp lệ. |
| [evaluate_scope_gate.py](training/evaluate_scope_gate.py) | Đo tỷ lệ cổng phạm vi loại nhầm ảnh hợp lệ. |
| [evaluate_scope_ood.py](training/evaluate_scope_ood.py) | Đo tỷ lệ cổng phạm vi chặn ảnh ngoài phạm vi. |

## 5. Audit dữ liệu và lỗi — không train

| File | Rà điều gì? |
|---|---|
| [audit_validation_sources.py](training/audit_validation_sources.py) | Tách chỉ số validation theo nguồn ảnh từ dự đoán đã có. |
| [audit_original_eight_training_sources.py](training/audit_original_eight_training_sources.py) | Kiểm nguồn, nhãn, mức xuất hiện khi replay và suy luận cố định trên train; điểm train không phải điểm test. |
| [audit_original_eight_weak_training.py](training/audit_original_eight_weak_training.py) | Kiểm metadata train qua các fold và danh tính pixel ảnh, không đổi nhãn. |
| [audit_original_eight_error_sources.py](training/audit_original_eight_error_sources.py) | Phân tích lỗi OOF đã khoá theo nguồn và tạo hồ sơ rà ảnh. |
| [audit_original_eight_cancer_head_disagreements.py](training/audit_original_eight_cancer_head_disagreements.py) | Phân tích bất đồng đầu cancer trên train/validation, không fit model. |

## 6. Tổng hợp kết quả đã có — không train

Một số file tổng hợp cũng chạy bước kiểm chứng trước khi viết báo cáo.

| File | Tổng hợp báo cáo nào? |
|---|---|
| [summarize_original_eight_resnet50.py](training/summarize_original_eight_resnet50.py) | Pilot ResNet50 fold 0. |
| [summarize_original_eight_resnet50_cv.py](training/summarize_original_eight_resnet50_cv.py) | ResNet50 năm fold và so ba kiến trúc. |
| [summarize_original_eight_resnet_transfer.py](training/summarize_original_eight_resnet_transfer.py) | So sánh nguồn khác bằng dự đoán cố định. |
| [summarize_original_eight_supplement.py](training/summarize_original_eight_supplement.py) | Audit danh tính ảnh phụ, cách ly và vai trò dữ liệu. |
| [summarize_original_eight_supplement_adaptation.py](training/summarize_original_eight_supplement_adaptation.py) | Pilot ResNet dùng thêm dữ liệu phụ so với đối chứng. |
| [summarize_original_eight_ensemble_teacher.py](training/summarize_original_eight_ensemble_teacher.py) | Pilot truyền đầu ra mềm B0/ConvNeXt sang ResNet. |
| [summarize_original_eight_pad_addition.py](training/summarize_original_eight_pad_addition.py) | Chuẩn bị PAD và pilot bổ sung cancer. |
| [summarize_original_eight_negative_supervision.py](training/summarize_original_eight_negative_supervision.py) | Pilot nhãn phủ định FP32 và vấn đề bản AMP ban đầu. |
| [summarize_original_eight_frozen_cancer_head.py](training/summarize_original_eight_frozen_cancer_head.py) | Các đầu cancer trên đặc trưng ResNet cố định. |
| [summarize_original_eight_cancer_head_replay.py](training/summarize_original_eight_cancer_head_replay.py) | Audit bất đồng và đầu cancer có replay ảnh train gốc. |

## 7. Kiểm chứng lại thí nghiệm — không train

Các file này đối chiếu dữ liệu, phép tính, cách chọn và tính nhất quán của thí nghiệm. PASS xác nhận những phép kiểm đó, không phải chứng nhận chẩn đoán lâm sàng.

| File | Kiểm chứng điều gì? |
|---|---|
| [verify_original_eight_training_sources.py](training/verify_original_eight_training_sources.py) | Nhãn nguồn, lượt replay, chỉ số và suy luận cố định của audit train. |
| [verify_original_eight_training_sources_v2.py](training/verify_original_eight_training_sources_v2.py) | Phiên bản kiểm chứng bổ sung của audit nguồn train. |
| [verify_original_eight_pad_supplement.py](training/verify_original_eight_pad_supplement.py) | Đối chiếu trùng và nhóm liên quan của PAD cancer bổ sung. |
| [verify_original_eight_pad_joint.py](training/verify_original_eight_pad_joint.py) | Kiểm độc lập phép so dHash và đồ thị nhóm của audit PAD chung. |
| [verify_original_eight_pad_addition.py](training/verify_original_eight_pad_addition.py) | Lịch lấy mẫu PAD, augmentation, vai trò dữ liệu, gộp và suy luận. |
| [verify_original_eight_pad_addition_v2.py](training/verify_original_eight_pad_addition_v2.py) | Phiên bản kiểm chứng bổ sung cho pilot thêm PAD. |
| [verify_original_eight_negative_supervision.py](training/verify_original_eight_negative_supervision.py) | Lịch train, gradient loss phủ định, phép gộp và chỉ số của bản ban đầu. |
| [verify_original_eight_negative_supervision_fp32.py](training/verify_original_eight_negative_supervision_fp32.py) | Các phép kiểm tương ứng cho bản FP32. |
| [verify_original_eight_frozen_cancer_head.py](training/verify_original_eight_frozen_cancer_head.py) | Dựng lại phép tính đầu cancer/gộp bằng NumPy, kiểm nhãn và điều kiện giữ. |
| [verify_original_eight_cancer_head_disagreements.py](training/verify_original_eight_cancer_head_disagreements.py) | Kiểm số liệu bất đồng đầu cancer trên train/validation. |
| [verify_original_eight_cancer_head_original_replay.py](training/verify_original_eight_cancer_head_original_replay.py) | Nhãn nhị phân, trọng số nguồn, chuẩn hoá cố định và gộp của đầu replay. |
| [verify_original_eight_calibrated_classwise.py](training/verify_original_eight_calibrated_classwise.py) | Dựng lại kết quả calibration/gộp theo nhóm và cách lựa chọn. |

## 8. Thư viện dùng chung

| File | Dùng để làm gì? |
|---|---|
| [common.py](training/common.py) | Nhãn tám bệnh, đọc ảnh/dữ liệu, augmentation, tạo B0/ConvNeXt/ResNet, seed và hàm lưu/đọc dùng chung. Không tự train khi chạy như một chương trình độc lập. |

## 9. File nào đã được đưa ra ngoài?

- **50 script lịch sử** đã chuyển ra khỏi `training`, giảm từ 146 còn 96 file Python. [Danh sách và cách khôi phục](../backups/ai_training_scripts_20261022/README.md).
- **50 file đầu ra thử nghiệm năm bệnh**, gồm 10 checkpoint, đã được lưu riêng. [Danh sách và cách khôi phục](../backups/five_disease_trial_20261022/README.md).
- Các trạng thái `resume_state.pth` đã lưu riêng trong đợt dọn trước. Nếu chạy lại việc cần đọc trạng thái resume, [khôi phục trạng thái phù hợp](../backups/ai_service_cleanup_20261022/README.md) trước.

Một số tài liệu lịch sử vẫn dẫn đường dẫn gốc. Phục hồi các file cần thiết về đúng chỗ trước khi chạy lại; không chạy trực tiếp script từ `backups` vì nhiều script xác định thư mục dự án từ vị trí của chính nó.
