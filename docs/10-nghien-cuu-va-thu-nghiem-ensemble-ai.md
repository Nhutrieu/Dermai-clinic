# Nghiên cứu mô hình da liễu và thử nghiệm kết hợp mô hình

> Ngày 08/10/2026. Đây là kết quả nghiên cứu trên dữ liệu hiện có của DermAI Clinic, chưa phải đánh giá lâm sàng hay thay thế bác sĩ. Artifact chi tiết: [`paper_ensemble_benchmark.json`](../ai-service/reports/paper_ensemble_benchmark/paper_ensemble_benchmark.json).

Xem thêm [thử nghiệm học đối sánh có giám sát cho ConvNeXt-Tiny](../ai-service/reports/paper_ensemble_benchmark/convnext_supcon_balanced_dataset.json) và [đánh giá trên ảnh PAD-UFES-20 từ nguồn mới](../ai-service/reports/paper_ensemble_benchmark/pad_ufes_external_evaluation.json).

## 1. Các công trình được đối chiếu

| Công trình gốc | Cách làm có liên quan | Quyết định cho dự án |
|---|---|---|
| [Esteva và cộng sự, *Nature* 2017](https://www.nature.com/articles/nature21056) ([bản PDF của tác giả](https://cs.stanford.edu/people/esteva/home/assets/nature_skincancer.pdf)) | Fine-tune CNN Inception v3 từ ImageNet trên 129.450 ảnh lâm sàng. | Giữ transfer learning làm nền. Quy mô dữ liệu và tác vụ của bài báo khác dự án; không mượn số accuracy của họ. |
| [Liu và cộng sự, *Nature Medicine* 2020](https://pubmed.ncbi.nlm.nih.gov/32424212/) | Dùng ảnh **và** thông tin lâm sàng của 16.114 ca để đưa ra chẩn đoán phân biệt 26 bệnh thường gặp. | Ảnh đơn lẻ không chứa đủ ngữ cảnh. Chỉ thử nhánh triệu chứng/metadata khi có nhãn và dữ liệu được thu thập nhất quán; không tự thêm câu trả lời của người bệnh vào model ảnh hiện tại. |
| [Gessert và cộng sự, ISIC 2019](https://arxiv.org/abs/1910.03910) ([bảng xếp hạng chính thức](https://challenge.isic-archive.com/leaderboards/2019/)) | Kết hợp EfficientNet nhiều độ phân giải, SENet và ResNeXt; xử lý mất cân bằng lớp và ảnh ngoài các lớp đã học. Ensemble đạt hạng nhất, nhưng điểm test chính thức thấp hơn cross-validation. | Thử kết hợp các kiến trúc đã huấn luyện trên **cùng ảnh test**, báo kết quả theo từng lớp và phân biệt holdout theo ca với kiểm định ở nguồn hoàn toàn mới. Không sao chép cấu hình dermoscopy sang ảnh lâm sàng. |
| [Ha và cộng sự, SIIM-ISIC 2020](https://arxiv.org/abs/2010.05351) | Ensemble nhiều CNN, backbone và kích thước ảnh, chú trọng validation ổn định. | Dùng trung bình xác suất đơn giản làm phép thử đầu tiên; tránh tìm trọng số tối ưu bằng tập test. |
| [Liu và cộng sự, CVPR 2022](https://openaccess.thecvf.com/content/CVPR2022/html/Liu_A_ConvNet_for_the_2020s_CVPR_2022_paper.html) | Đề xuất họ kiến trúc ConvNeXt cho nhận dạng ảnh nói chung. | Huấn luyện ConvNeXt-Tiny như một backbone thứ ba; chỉ kết quả trên dữ liệu da liễu của dự án mới quyết định nó có ích hay không. |
| [Daneshjou và cộng sự, *Science Advances* 2022](https://arxiv.org/abs/2203.08807) | Bộ DDI có nhãn chuyên gia và nhiều tông da cho thấy hiệu năng mô hình giảm mạnh khi đổi nguồn dữ liệu. | Không suy từ một bộ test sang bệnh nhân Việt Nam. Cần đánh giá riêng theo tông da, nguồn ảnh và lớp bệnh trước khi triển khai. |

SCIN do [nhóm nghiên cứu phát hành](https://github.com/google-research-datasets/scin) gồm ảnh do người dùng tự gửi, có nhãn hồi cứu của bác sĩ và metadata. Dự án đã dùng **977 ảnh SCIN để train** và giữ **240 ảnh từ các ca SCIN khác** để test. Vì vậy, 240 ảnh này là *SCIN case holdout*: kiểm tra ca chưa thấy từ cùng nguồn SCIN, **không phải kiểm định ở một nguồn hoàn toàn mới**. Nhãn và phân bố lớp cũng không tương đương một bộ test lâm sàng tại Việt Nam.

## 2. Phép thử đã chạy trên dữ liệu dự án

Bốn checkpoint thuộc **ba kiến trúc** gồm EfficientNet-B0 hiện tại, EfficientNet-B0 V2c, ResNet50 và ConvNeXt-Tiny. ConvNeXt được khởi tạo từ trọng số ImageNet chính thức, train trên 5.045 ảnh, chọn checkpoint epoch 12 theo macro F1 của 892 ảnh validation; 564 ảnh test gốc và 240 ảnh SCIN holdout chỉ dùng để đánh giá sau đó. [Cấu hình/epoch được chọn](../ai-service/reports/paper_ensemble_benchmark/convnext_training_selection.json) và [tóm tắt dữ liệu](../ai-service/reports/paper_ensemble_benchmark/convnext_dataset_summary.json) được lưu cùng kết quả.

Mỗi mô hình xuất xác suất `softmax(logits / temperature)`; ensemble lấy **trung bình đều** xác suất theo lớp. Nhiệt độ lấy từ checkpoint, không fit trên test. Mã thử nghiệm: [`benchmark_paper_ensembles.py`](../ai-service/training/benchmark_paper_ensembles.py). Bảy phép so sánh ban đầu và hai phép thêm ConvNeXt (model riêng, tổ hợp bốn model) đều được khai báo trước khi xem kết quả tương ứng; không dò trọng số trên test.

| Mô hình / tổ hợp | Test gốc: accuracy | Test gốc: macro F1 | SCIN: accuracy | SCIN: macro F1 | Test gốc: recall SkinCancer |
|---|---:|---:|---:|---:|---:|
| EfficientNet-B0 hiện tại | 78,90% | 78,31% | 67,92% | 41,57% | 90,91% |
| EfficientNet-B0 V2c | 81,03% | 79,75% | 69,58% | 42,00% | 84,42% |
| ResNet50 | 77,30% | 76,70% | 70,00% | 40,93% | 84,42% |
| ConvNeXt-Tiny | 78,19% | 76,84% | 70,83% | 37,94% | 72,73% |
| EfficientNet hiện tại + ResNet50 (1:1) | 79,96% | 78,96% | 73,75% | 44,36% | 87,01% |
| EfficientNet V2c + ResNet50 (1:1) | 81,56% | 80,84% | 73,75% | 46,14% | 87,01% |
| Hai EfficientNet (1:1) | 83,87% | 82,62% | 72,92% | 45,94% | 88,31% |
| **Cả ba, trọng số bằng nhau** | **83,87%** | **82,52%** | **75,00%** | **48,01%** | **92,21%** |
| Cả bốn, trọng số bằng nhau | 84,57% | 83,88% | 73,75% | 45,41% | 90,91% |

Test gốc có 564 ảnh; SCIN case holdout có 240 ảnh. So với EfficientNet hiện tại, tổ hợp ba mô hình tăng **4,96 điểm phần trăm** accuracy test gốc và **7,08 điểm phần trăm** accuracy SCIN holdout. Trên cùng từng ảnh, tổ hợp sửa được 42 lỗi và tạo 14 lỗi mới ở test gốc; với SCIN là 26 và 9. Khoảng 95% bootstrap ghép cặp cho mức tăng accuracy là **2,30–7,45 điểm phần trăm** ở test gốc và **2,27–12,08 điểm phần trăm** ở SCIN. Bootstrap lấy theo `case_id` nơi có thông tin; ảnh gốc không có patient ID đã xác minh nên phần đó chỉ có thể lấy theo ảnh.

Các chỉ số khác cần trình bày cùng kết quả tốt: recall Lupus test gốc tăng từ **47,06% lên 55,88%**, nhưng vẫn thấp. Top-3 trên SCIN giảm từ **92,92% xuống 89,58%**. ECE test gốc tăng từ **0,0405 lên 0,0781**, tức xác suất của ensemble cần hiệu chuẩn lại; ECE SCIN giảm từ 0,0775 xuống 0,0636. Các giá trị ECE ở đây dùng checkpoint EfficientNet đã hiệu chuẩn, nên khác báo cáo softmax thô trước đây.

**Lượt ConvNeXt đầu tiên** không vượt baseline trên test gốc và có recall `SkinCancer` **72,73%**. Train macro F1 cuối gần 100% trong khi validation tốt nhất là 77,34%, cho thấy overfit trong cấu hình này. Tổ hợp bốn model với checkpoint đầu tiên tăng accuracy test gốc thêm 0,71 điểm phần trăm so với tổ hợp ba, nhưng SCIN accuracy giảm 1,25 điểm và SCIN macro F1 giảm 2,60 điểm; recall `SkinCancer` test gốc giảm từ 92,21% xuống 90,91%. ECE test gốc của tổ hợp bốn là 0,1040. Đây là ví dụ thực tế rằng thêm backbone không bảo đảm tốt hơn ở mọi tập ảnh. So với baseline, khoảng 95% bootstrap ghép cặp cho mức tăng accuracy của tổ hợp bốn là **3,01–8,34 điểm phần trăm** ở test gốc và **0,86–10,79 điểm phần trăm** ở SCIN.

### 2.1. Huấn luyện lại ConvNeXt để kiểm tra overfit

[Cấu hình thử lại được ghi trước khi chạy](../ai-service/reports/paper_ensemble_benchmark/convnext_retrain_protocol.md): giữ nguyên dữ liệu/split, đóng băng backbone 2 epoch, sau đó dùng learning rate backbone bằng 0,1 lần classifier; tăng label smoothing và weight decay, sửa EMA ở mức epoch. Checkpoint mới được chọn tại epoch 23 theo validation macro F1. [Báo cáo chọn checkpoint](../ai-service/reports/paper_ensemble_benchmark/convnext_regularized_selection.json) và [metric đầy đủ](../ai-service/reports/paper_ensemble_benchmark/convnext_regularized_evaluation.json) được lưu riêng.

| Chỉ số | ConvNeXt ban đầu | ConvNeXt huấn luyện lại |
|---|---:|---:|
| Train macro F1 ở epoch được chọn | 98,64% | 99,66% |
| Validation macro F1 | 77,34% | 77,47% |
| Test gốc: accuracy / macro F1 | 78,19% / 76,84% | **82,45% / 81,34%** |
| Test gốc: recall SkinCancer / Lupus | 72,73% / 41,18% | **88,31% / 61,76%** |
| SCIN holdout: accuracy / macro F1 | 70,83% / 37,94% | **73,75% / 44,28%** |

Kết quả trên hai holdout tốt hơn, nhưng train–validation gap **không giảm**. Train F1 được đo trên ảnh có augmentation còn validation trên ảnh xử lý cố định, nên khoảng cách này chỉ là tín hiệu overfit, không phải phép đo ghi nhớ từng ảnh. Không thể tuyên bố model đã hết “học vẹt”. Kết quả tổ hợp bốn model khi thay bằng checkpoint mới là **85,28% test gốc, 75,00% SCIN holdout**; recall `SkinCancer` test gốc **90,91%**, thấp hơn tổ hợp ba model **92,21%**. [Báo cáo ensemble với checkpoint mới](../ai-service/reports/paper_ensemble_benchmark/regularized_ensemble/paper_ensemble_benchmark.json) chỉ có giá trị khám phá vì hai holdout đã được dùng để so sánh nhiều ứng viên.

## 3. Kết luận kỹ thuật và giới hạn

**Có thể kết hợp các model; tổ hợp ba mô hình dự đoán Top-1 tốt hơn từng model riêng trong thí nghiệm đầu tiên trên cả hai tập đang có.** Lượt train lại cải thiện ConvNeXt và tổ hợp bốn về accuracy, nhưng không loại bỏ dấu hiệu overfit và chưa vượt recall `SkinCancer` của tổ hợp ba. Đây vẫn là kết quả khám phá trên hai holdout hiện có. [Audit sau đó](47-audit-anh-trung-gan-test-cu.md) xác nhận ít nhất 19 ảnh test gốc cùng cảnh với ảnh trong nguồn train cũ nhưng khác byte: 18 ảnh đối ứng thuộc train thực tế, một thuộc validation. Vì vậy điểm test gốc không phải kiểm chứng độc lập theo người. Chọn tổ hợp vì nhìn thấy điểm test rồi tiếp tục chỉnh trọng số trên chính test sẽ khiến kết quả bị thiên lệch. Chưa đưa tổ hợp vào API đang phục vụ bệnh nhân.

Các giới hạn cần xử lý trước khi thay model chạy thật:

1. SCIN holdout lệch lớp rất mạnh: không có `SkinCancer`, chỉ có 1 ảnh `Candidiasis` và 4 ảnh `Lupus`. Model đã học từ phần train của cùng bộ SCIN, nên tập này không xác nhận được khả năng tổng quát hóa sang nguồn ảnh hoàn toàn mới hoặc độ nhạy ung thư da ngoài bộ test gốc.
2. Bộ `SkinDisease` gốc chưa có nguồn/giấy phép và patient ID được xác minh. Kiểm tra duplicate hiện có không chứng minh được tách bệnh nhân hoàn toàn.
3. Hai EfficientNet và ResNet50 có lịch sử chia validation khác nhau. Cần một tập **calibration mới, tách theo ca/bệnh nhân và chưa từng được bất kỳ mô hình nào dùng để train**, để fit xác suất ensemble và khóa cấu hình trước lần test cuối.
4. Cần thêm tập ảnh có xác nhận của bác sĩ tại bối cảnh sử dụng, gồm nhiều tông da, thiết bị chụp và bệnh ngoài 8 nhóm; đo sensitivity/specificity theo lớp, calibration, OOD, latency và Grad-CAM của tổ hợp.
5. ConvNeXt đã được train với hai cấu hình nhưng chỉ một seed. Lượt regularization cải thiện holdout mà không giảm train–validation gap; cần thêm dữ liệu đa dạng, kiểm tra nhãn và đánh giá bằng **holdout mới**, vì hai tập test hiện đã được dùng để so sánh nhiều ứng viên.

## 4. Tái lập

Chạy từ thư mục gốc dự án, với bốn checkpoint đã được tạo sẵn:

```powershell
python ai-service/training/benchmark_paper_ensembles.py `
  --baseline ai-service/candidates/production_calibrated/best_model.pth `
  --candidate ai-service/candidates/classifier_v2c_seed42/evaluation/calibrated_model.pth `
  --resnet ai-service/candidates/resnet50_scin_seed42/best_model.pth `
  --convnext ai-service/candidates/convnext_tiny_seed42/evaluation/calibrated_model.pth `
  --output ai-service/reports/paper_ensemble_benchmark
```

JSON kết quả lưu phiên bản, SHA-256 và nhiệt độ từng checkpoint cùng metric chi tiết từng lớp, calibration và phép so sánh bootstrap.
Các file checkpoint trong `ai-service/candidates/` hiện bị `.gitignore` loại khỏi Git; muốn tái lập trên máy khác cần lưu chúng riêng hoặc chạy lại lệnh huấn luyện theo cấu hình trong `convnext_training_selection.json`.

## 5. Đường chạy thử nghiệm trong API và bộ đánh giá mới

API đã hỗ trợ [manifest ensemble ba model](../ai-service/ensemble_research.json) dưới dạng **tùy chọn nghiên cứu**. Mặc định `ENSEMBLE_MANIFEST_PATH` không được đặt nên API vẫn chạy một EfficientNet-B0. Khi chạy thử trong thư mục `ai-service`, đặt `ENSEMBLE_MANIFEST_PATH=ensemble_research.json` để nạp ba checkpoint; mỗi file được kiểm SHA-256 và thứ tự lớp. API lấy trung bình xác suất sau temperature calibration, dùng OOD profile của EfficientNet hiện tại làm cổng kiểm tra ảnh và tạo Grad-CAM từ trung bình bản đồ của ba model. Thiếu checkpoint hoặc OOD profile sẽ khiến chế độ ensemble không khởi động, thay vì âm thầm chạy thiếu model. Chưa bật tùy chọn này cho bệnh nhân vì xác suất ensemble chưa được hiệu chuẩn độc lập, kiểm tra OOD/Grad-CAM mới chỉ ở mức chức năng và chưa có tập test đủ độc lập.

Để đánh giá trên ảnh mới, dùng [hướng dẫn và mẫu CSV tám lớp](../ai-service/reports/paper_ensemble_benchmark/pad_ufes_image_fingerprints.json). CSV có các cột `image_path,label,case_id,source,label_reviewer`; giữ nguyên bộ ảnh ngoài mọi bước train/chọn trọng số và có đủ ca `SkinCancer`.

```powershell
python ai-service/training/evaluate_new_ensemble_holdout.py `
  --images-root D:\du-lieu-moi\images `
  --labels-csv D:\du-lieu-moi\labels.csv `
  --output ai-service/reports/new_holdout_ensemble.json
```

Lệnh này yêu cầu tối thiểu 20 ca mỗi lớp, từ chối ảnh trùng byte với các split train/test cũ, so sánh baseline với tổ hợp ba model trên đúng cùng ảnh và xuất accuracy, macro F1, chỉ số từng lớp, calibration cùng bootstrap ghép theo ca. Đây là ngưỡng tối thiểu cho **báo cáo nghiên cứu**, không phải tiêu chuẩn đủ để dùng lâm sàng. Kiểm tra hash không chứng minh được bệnh nhân không trùng vì bộ ảnh cũ thiếu patient ID; nguồn ảnh và người xác nhận trong CSV cần được đối chiếu thủ công. Chỉ quyết định đưa vào sử dụng sau khi đánh giá thêm độ nhạy ung thư da, ảnh ngoài phạm vi tám lớp, calibration, thời gian chạy và chất lượng giải thích trên bộ dữ liệu mới.

## 6. Tìm nguồn ảnh ngoài mới (08/10/2026)

| Nguồn chính thức | Phù hợp với dự án | Giới hạn cần giữ khi báo cáo |
|---|---|---|
| [PAD-UFES-20, Mendeley Data](https://data.mendeley.com/datasets/zr7vgbcyr2/1) ([mã của nhóm tạo dữ liệu](https://github.com/labcin-ufes/PAD-UFES-20)) | 2.298 ảnh tổn thương chụp bằng điện thoại, 1.373 bệnh nhân, có mã bệnh nhân; ba nhãn ung thư BCC/SCC/MEL đã được sinh thiết xác nhận. Ưu tiên để kiểm tra riêng độ nhạy `SkinCancer` và hành vi trên tổn thương lành tính. Giấy phép trên trang dữ liệu là CC BY 4.0. | Ba nhóm còn lại là ACK/NEV/SEK, không tương ứng với 7 lớp bệnh không ung thư của model. Không lấy accuracy 8 lớp từ nguồn này. Cần kiểm tra trùng ảnh với `SkinDisease` trước khi dùng. |
| [Fitzpatrick17k, kho tác giả](https://github.com/mattgroh/fitzpatrick17k) | 16.577 ảnh lâm sàng, 114 chẩn đoán và thông tin tông da; có thể tạo một phép kiểm tra **theo các nhãn khớp hẹp** như Acne, Eczema, Lupus, Psoriasis và một số ung thư da. Giấy phép CC BY-NC-SA 3.0. | Kiểm tra CSV chính thức cho thấy không có nhãn Candidiasis, Tinea, Warts; không có patient ID. Ảnh lấy từ các atlas công khai nên phải so trùng với nguồn ảnh gốc chưa rõ của `SkinDisease`. Một số URL ảnh hỏng; không thể dùng để báo một con số accuracy cho đủ 8 lớp. |
| [DDI, Stanford AIMI](https://aimi.stanford.edu/datasets/ddi-diverse-dermatology-images) ([điều kiện truy cập](https://ddi-dataset.github.io/)) | 656 ảnh/570 bệnh nhân, nhãn tổn thương lành tính hoặc ác tính xác nhận bằng giải phẫu bệnh, có nhiều tông da. Phù hợp phép kiểm tra bổ sung về ung thư da và sai khác theo tông da. | Cần người nghiên cứu đăng ký và chấp nhận điều khoản truy cập riêng; chỉ dùng nghiên cứu phi thương mại, không chia sẻ lại ảnh. Không phải bộ nhãn đủ 8 bệnh. |

**Quyết định:** ưu tiên PAD-UFES-20 cho phép thử ung thư da từ nguồn chụp điện thoại, giữ nguyên toàn bộ ảnh ngoài train/validation; nếu lấy được DDI thì thêm phép kiểm tra theo tông da. Fitzpatrick17k chỉ dùng cho các lớp có ánh xạ chẩn đoán rõ và đánh giá riêng từng lớp. Các nguồn này bổ sung kiểm tra ngoài dữ liệu hiện tại; chưa nguồn nào trong danh sách tự tạo được một bộ test độc lập, đủ tám lớp để xác nhận chung mức 83,87–85,28%. Không gộp ảnh mới vào train trước khi chốt phép test đầu tiên.

Đã tải gói PAD-UFES-20 bản 1 từ nguồn chính thức, giải nén đủ 2.298 ảnh và đối chiếu với 1.373 `patient_id` trong metadata; trong đó BCC 845 ảnh, SCC 192, MEL 52. Đã rà ảnh trùng và chạy các checkpoint đã khóa; kết quả cùng giới hạn nhãn, ảnh gần trùng và metadata mâu thuẫn được trình bày trong [báo cáo PAD-UFES-20](../ai-service/reports/paper_ensemble_benchmark/pad_ufes_external_evaluation.json). Đây là phép đo gắn cờ SkinCancer, không phải accuracy tám lớp.
