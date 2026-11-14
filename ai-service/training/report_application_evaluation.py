"""Render the verified application evaluation; no training or model selection."""
from pathlib import Path
import argparse
import hashlib
import json


AI=Path(__file__).resolve().parents[1]
DEFAULT=AI/'reports/application_evaluation_20261110'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def pct(value):
    return '—' if value is None else f'{value*100:.2f}%'.replace('.',',')


def main(out):
    verification=read(out/'verification.json')
    assert verification['status']=='PASS'
    results=read(out/'results.json');protocol=read(out/'protocol.json')
    assert hashlib.sha256((out/'results.json').read_bytes()).hexdigest()==verification['results_sha256']
    retries=read(out/'execution_retries.json') if (out/'execution_retries.json').exists() else []
    if retries:
        import importlib.util
        source=Path(__file__).with_name('evaluate_application_model.py')
        spec=importlib.util.spec_from_file_location('app_eval_report_metrics',source)
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        records=[json.loads(x) for x in (out/'predictions.jsonl').read_text(encoding='utf-8').splitlines()]
        retried={r['next_manifest_index'] for r in retries}
        first=[dict(r) for r in records]
        for i in retried:
            first[i].update(http_status=0,disease=None,uncertain=None,detail='Transport timeout before any response; retry output excluded from this first-attempt diagnostic')
        reliability=dict(scope='Post hoc operational diagnostic; main classification results use complete final responses after a documented retry. No model or data selection.',
            transport_timeout_events=len(retries),retried_images=len(retried),all_images_preserved=True,
            first_attempt_metrics_by_dataset={k:helper.metrics([r for r in first if r['dataset']==k]) for k in results['datasets']})
        (out/'execution_reliability.json').write_text(json.dumps(reliability,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    names={'historical_fixed_test':'Test lịch sử đã rà trùng', 'SCIN_case_holdout':'SCIN giữ lại đã rà trùng'}
    lines=['# Đánh giá đúng bản AI đã tích hợp vào đồ án','',
        '**Phiên bản:** `'+results['version']+'`. Dữ liệu và cấu hình được khóa trước khi chấm. Không huấn luyện lại, đổi ngưỡng hoặc chọn ảnh theo kết quả mới.','',
        '**Phạm vi:** đánh giá hồi cứu trên các tập test lịch sử đã được nghiên cứu trước đây. Đây là phép đo của bản phục vụ, nhưng chưa phải test mù mới hoặc đánh giá lâm sàng độc lập.','',
        ('**Thử lại:** có '+str(len(retries))+' sự cố timeout HTTP 60 giây. Bảng chính dùng kết quả cuối sau khi khởi động lại service không đổi và gửi lại đúng ảnh; không bỏ ảnh đó. Đây không phải tỷ lệ thành công ngay yêu cầu đầu tiên. Xem bảng sự cố thực thi phía dưới.' if retries else 'Toàn bộ đầu vào được ghi nhận theo danh sách đã khóa.'),'',
        '## Bản nào được chấm?','',
        'Luồng thật `/predict`: kiểm tra file/chất lượng ảnh → OOD → 15 CNN thuộc năm cấu hình E/G/S → biểu quyết có bảo toàn SkinCancer → nhãn, điểm đồng thuận, cờ chưa chắc chắn, Grad-CAM và RAG. Mọi ảnh bị API từ chối vẫn được ghi lại. Các ảnh trả nhãn nhưng có cờ `uncertain` vẫn nằm trong mẫu tính chỉ số.','',
        '## Kết quả','',
        '| Tập dữ liệu | Tổng ảnh gửi | API trả nhãn | API từ chối | Tỷ lệ nhận ảnh | Độ đúng trên ảnh trả nhãn | Trả đúng / toàn bộ ảnh | Macro F1 tám lớp, tính cả ảnh từ chối |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,entry in results['datasets'].items():
        m=entry['metrics']
        lines.append('| '+names[name]+' | '+str(m['input_images'])+' | '+str(m['returned_predictions'])+' | '+str(m['rejected_images'])+' | '+pct(m['coverage'])+' | '+pct(m['accuracy_on_returned'])+' | '+pct(m['correct_return_rate'])+' | '+pct(m['macro_f1_8class_with_abstentions'])+' |')
    lines+=['','**Cách đọc:** “Độ đúng trên ảnh trả nhãn” chỉ tính những ảnh API nhận xử lý; luôn đọc kèm tỷ lệ nhận ảnh. “Trả đúng / toàn bộ ảnh” lấy số ảnh có nhãn dự đoán đúng chia cho toàn bộ ảnh được gửi trong tập đã rà; ảnh từ chối không được tính là đã trả đúng. Ảnh từ chối là yêu cầu chụp lại/ngoài phạm vi, không phải một chẩn đoán bệnh sai cụ thể.','',
        'Macro F1 toàn luồng dùng cố định tám nhãn; dự đoán từ chối nằm ở cột thứ chín của ma trận và làm giảm recall/F1 của lớp thật. Đây là chỉ số khác với Macro F1 chỉ tính trên ảnh được trả nhãn. Không được bỏ ảnh bị từ chối để làm điểm tổng cao hơn mà không báo coverage.','',
        '## Kết quả từng nguồn','']
    for name,entry in results['datasets'].items():
        m=entry['metrics'];ci=entry['bootstrap_95']['percentile_95']
        lines += ['### '+names[name],'',
            f"Có {m['correct_returned']}/{m['returned_predictions']} ảnh trả nhãn đúng; API nhận {m['returned_predictions']}/{m['input_images']} ảnh. Số kết quả có cờ chưa chắc chắn: {m['uncertain_returned']}; không loại các kết quả này khỏi phép đo.",'',
            '| Bệnh | Ảnh gửi | Trả nhãn | Nhận đúng | Từ chối | Precision | Recall trên toàn bộ ảnh của bệnh | F1 toàn luồng |',
            '|---|---:|---:|---:|---:|---:|---:|---:|']
        for i,(disease,c) in enumerate(m['per_class'].items()):
            predicted_count=sum(row[i] for row in m['confusion_matrix_8x9'])
            defined=bool(c['support'] or predicted_count)
            lines.append('| '+disease+' | '+str(c['support'])+' | '+str(c['returned'])+' | '+str(c['correct'])+' | '+str(c['rejected'])+' | '+(pct(c['precision']) if defined else '—')+' | '+pct(c['recall'])+' | '+(pct(c['f1']) if defined else '—')+' |')
        lines+=['','Macro F1 trên ảnh được trả nhãn, giữ tám lớp: **'+pct(m['macro_f1_8class_on_returned'])+'**.']
        if not m['all_8_classes_present']:
            cancer_calls=sum(row[5] for row in m['confusion_matrix_8x9'])
            lines+=['','Nguồn này không đủ tám bệnh. Không có ảnh SkinCancer nên Recall SkinCancer là **không xác định**, không phải 0%. Có '+str(cancer_calls)+' ảnh được API gán SkinCancer nhưng nhãn dataset thuộc nhóm khác; không diễn giải điều này thành kết luận mô bệnh học. Macro F1 trung bình trên các lớp có ảnh là '+pct(m['macro_f1_present_classes_with_abstentions'])+'; không dùng nó để thay điểm đủ tám lớp. Lupus/Candidiasis có rất ít mẫu, chưa đủ để kết luận ổn định.']
        lines+=['','Khoảng 95% bootstrap theo nhóm proxy (1.000 lượt, seed 42):','',
            '| Chỉ số | Khoảng 95% |','|---|---|']
        for key,label in [('coverage','Tỷ lệ nhận ảnh'),('accuracy_on_returned','Độ đúng trên ảnh trả nhãn'),('correct_return_rate','Trả đúng / toàn bộ ảnh'),('macro_f1_8class_with_abstentions','Macro F1 tám lớp toàn luồng')]:
            bounds=ci[key];lines.append('| '+label+' | '+('—' if bounds is None else pct(bounds[0])+' – '+pct(bounds[1]))+' |')
        lines+=['','Nhóm SCIN dùng mã ca nguồn và liên kết dHash; nhóm ảnh nguồn cũ dựa vào dHash. Đây chưa phải ID bệnh nhân đã xác minh. Khoảng này không bao gồm bất định từ việc từng dùng dữ liệu để nghiên cứu nhiều phương pháp.','',
            '**Lý do API từ chối:**','']
        for reason,count in m['rejection_reasons'].items():lines.append(f'- {count} ảnh: {reason}')
        if not m['rejection_reasons']:lines.append('- Không có.')
        matrix=np.asarray(m['confusion_matrix_8x9']);fig,ax=plt.subplots(figsize=(12.8,8))
        im=ax.imshow(matrix,cmap='Blues');fig.colorbar(im,ax=ax,label='Images')
        ax.set_xticks(range(9),m['predicted_labels'],rotation=40,ha='right')
        ax.set_yticks(range(8),m['true_labels']);ax.set_xlabel('API prediction');ax.set_ylabel('Dataset label')
        ax.set_title(name+' | frozen serving API | abstentions retained')
        maximum=matrix.max()
        for i in range(8):
            for j in range(9):ax.text(j,i,str(matrix[i,j]),ha='center',va='center',fontsize=10,color='white' if matrix[i,j]>maximum*.55 else '#1f2937')
        fig.tight_layout();chart='confusion_matrix_'+name+'.png';fig.savefig(out/chart,dpi=180);plt.close(fig)
        lines+=['',f'![Confusion matrix — {name}]({chart})','']
    lines+=['## Rà dữ liệu trước khi chấm','',
        f"Đối chiếu {protocol['protected_images']} ảnh thuộc các thư mục train tám lớp, bao phủ toàn bộ cohort 5.937 ảnh dùng cho CNN, inner validation, specialist và cổng. Phạm vi bảo vệ mở rộng này cũng giữ cả ảnh raw có thể đã bị loại khỏi các lượt train riêng; loại trùng là thận trọng, không có nghĩa mọi ảnh raw đều đã được model học.",'',
        '| Nguồn | Ứng viên | Được giữ | Loại trước khi chấm |','|---|---:|---:|---:|']
    for name,a in protocol['source_summary'].items():lines.append('| '+names[name]+' | '+str(a['candidates'])+' | '+str(a['eligible'])+' | '+str(a['excluded'])+' |')
    lines+=['','Kiểm tra SHA-256, pixel RGB, dHash khoảng cách ≤3, mã ca SCIN và các cặp cùng cảnh đã rà trước đó. Chỉ nhận các ảnh thuộc tập tham chiếu đã xử lý xung đột nhãn; kiểm tra trùng giữa các ứng viên. dHash có thể gắn cờ các ảnh chỉ giống nhau về hình thức; việc loại cờ trước chấm là bảo thủ và không xác nhận độc lập bệnh nhân. Nhãn là nhãn dataset/nguồn, chưa có bác sĩ của dự án xác nhận lại.','',
        '## Kiểm chứng và sự cố thực thi','',
        'Bốn unit test cho kiểm tra rò rỉ và cách tính khi có ảnh từ chối đạt. Đối chiếu thêm 100 bộ dữ liệu giả lập với sklearn đạt. Sau khi khóa toàn bộ dự đoán, kiểm tra lại từng dòng theo manifest; tính độc lập confusion matrix 8×9, độ đúng có điều kiện, tỷ lệ trả đúng và Macro F1 bằng sklearn. SHA của mã ứng dụng, dữ liệu và 26 tài sản model được giữ nguyên.','']
    amendment=out/'execution_amendment.json'
    if amendment.exists():
        a=read(amendment)
        lines+=['Lượt native Windows gặp access violation khi Pillow mã hóa ảnh PNG Grad-CAM. '+str(a['native_attempt_records'])+' kết quả dở đã được lưu riêng và **không đưa vào các chỉ số ở báo cáo này**. Trước khi chấm lại, khóa phụ lục đổi môi trường sang API Linux Docker. Toàn bộ danh sách ảnh được chạy lại từ đầu, cùng mã, checkpoint, ngưỡng và tiêu chí. Không sửa model để vượt qua lỗi; không bỏ mẫu gây lỗi.','']
    if retries:
        lines+=['Có '+str(len(retries))+' sự cố timeout trong lượt Docker. Ghi sự cố trước khi thử lại cùng ảnh, giữ nguyên prefix và toàn bộ checkpoint/cấu hình. Bảng chính mô tả phân loại sau khi thu được phản hồi cuối. Bảng phụ sau coi yêu cầu timeout là **chưa trả được nhãn ở lần đầu**, không dùng nhãn thành công sau retry để che lỗi vận hành.','',
            '| Nguồn | API trả nhãn ngay lần đầu | Độ đúng trên nhãn trả ngay lần đầu | Trả đúng / toàn bộ ảnh ở lần đầu |','|---|---:|---:|---:|']
        for name,m in reliability['first_attempt_metrics_by_dataset'].items():
            lines.append('| '+names[name]+' | '+str(m['returned_predictions'])+'/'+str(m['input_images'])+' | '+pct(m['accuracy_on_returned'])+' | '+pct(m['correct_return_rate'])+' |')
        lines+=['','Chẩn đoán vận hành này được bổ sung sau sự cố và không dùng để chọn model. Lượt thử gọi trực tiếp AI API với timeout 60 giây; chưa phải kiểm thử toàn bộ giao diện/gateway hoặc cam kết độ trễ của ứng dụng.','']
    lines+=['## Được phép kết luận gì?','',
        'Đã có phép đo của đúng pipeline phục vụ trên các tập lịch sử sau rà trùng, bao gồm cả các cổng từ chối. Đây là đánh giá hồi cứu có giá trị kiểm tra ứng dụng, không phải kết quả test mù trên bệnh nhân mới.','',
        'Không so trực tiếp các tỷ lệ trong báo cáo này với OOF 78,95% / 77,73% / 88,04% rồi quy toàn bộ chênh lệch cho cách biểu quyết: tập dữ liệu, phân bố và việc có cổng chất lượng/OOD đều khác. Mốc OOF vẫn thuộc thí nghiệm cũ. Các chỉ số độc lập của bản phục vụ trong manifest vẫn để null, vì chưa có tập test độc lập mới.','',
        'Không gộp hai nguồn thành một điểm chính: nguồn SCIN không có SkinCancer và phân bố lớp khác. Không dùng kết quả này để chọn lại trọng số, ngưỡng, model hoặc các ảnh được báo cáo.','',
        '[Kết quả máy đọc](results.json) · [Kiểm chứng](verification.json) · [Môi trường thực thi](environment.json) · [Protocol cục bộ](protocol.json) · [Phụ lục đổi môi trường](execution_amendment.json)']
    (out/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Wrote summary.md and separate 8x9 confusion matrices; no pooled or independent-test claim')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=DEFAULT)
    main(parser.parse_args().output.resolve())
