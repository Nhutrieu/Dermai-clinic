# AI Training và RAG

## Classification

1. Chạy validator để phát hiện file hỏng, trùng hash và leakage train/test.
2. Chọn 8 lớp, ánh xạ `Tinea` thành ringworm; stratified split train/validation.
3. Resize 256, random crop 224, flip/rotate/color jitter nhẹ; validation chỉ
   resize + center crop + normalize ImageNet.
4. Transfer learning, weighted cross entropy hoặc weighted sampler; freeze
   backbone warm-up rồi fine-tune; early stopping theo macro F1.
5. Báo cáo accuracy, per-class precision/recall/F1, macro/weighted F1, confusion
   matrix và one-vs-rest ROC-AUC khi mỗi lớp có cả positive và negative.
6. Giữ test set bất biến đến lần đánh giá cuối. Lưu seed, class map, transform,
   git commit, metrics và checksum model.

So sánh cùng split, epoch budget và augmentation. EfficientNet-B0 là lựa chọn
triển khai mặc định; chỉ đổi nếu challenger cải thiện macro F1 có ý nghĩa và
đáp ứng latency. Với dữ liệu y khoa, recall từng lớp và calibration quan trọng
hơn accuracy đơn lẻ.

Grad-CAM lấy gradient tại layer convolution cuối, trọng số hóa activation, ReLU,
resize và phủ heatmap. Heatmap chỉ giải thích mô hình nhìn đâu, không chứng minh
lập luận y khoa.

## RAG

PDF được trích theo trang, làm sạch header/footer, chunk 700-900 token overlap
100-150 và lưu `source`, `page`, `section`, checksum. Embedding được index FAISS.
Query qua policy guard, retrieval top-k, threshold, prompt chỉ cho phép dùng
context. Câu trả lời phải có `[Tên tài liệu, trang N]`; thiếu context thì từ chối.

Môi trường offline dùng sentence-transformers + template extractive. Khi cấu
hình OpenAI/Gemini, chỉ thay generator/embedding adapter; policy và citation
validator vẫn chạy. Không gửi PII hoặc ảnh bệnh nhân tới provider bên ngoài.

Đánh giá RAG gồm retrieval hit@k, MRR, faithfulness, citation correctness,
answer relevance và bộ red-team về kê thuốc, prompt injection, thiếu nguồn.

