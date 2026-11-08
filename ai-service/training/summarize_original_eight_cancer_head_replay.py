"""Publish verified disagreement audit and fixed original-train replay pilot."""
from copy import deepcopy
from pathlib import Path

import numpy as np

from common import CLASSES,save_json,sha256_file
import audit_original_eight_cancer_head_disagreements as audit
import pilot_original_eight_cancer_head_original_replay as pilot


def pct(v):return f'{v*100:.2f}'


def write(path,lines):path.write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    av=pilot.prior.read(audit.OUT/'verification.json');ar=pilot.prior.read(audit.OUT/'results.json')
    pv=pilot.prior.read(pilot.OUT/'verification.json');pr=pilot.prior.read(pilot.OUT/'results.json')
    assert av['status']==pv['status']=='PASS'
    assert av['results_sha256']==sha256_file(audit.OUT/'results.json') and pv['results_sha256']==sha256_file(pilot.OUT/'results.json')
    root=pilot.ROOT;statepath=root/'ai-service/reports/active_research_track.json';state=pilot.prior.read(statepath)
    benchmark=deepcopy(state['benchmark']);serving=state['serving_checkpoint_sha256']
    assert sha256_file(root/benchmark['report_path'])==benchmark['report_sha256'] and sha256_file(root/state['serving_checkpoint'])==serving
    for directory in (audit.OUT,pilot.OUT):
        assert not (directory/'publication_protocol.json').exists(),'Preserve publication'
        save_json(directory/'publication_protocol.json',dict(publisher_sha256=sha256_file(Path(__file__)),
            protocol_sha256=sha256_file(directory/'protocol.json'),results_sha256=sha256_file(directory/'results.json'),
            verification_sha256=sha256_file(directory/'verification.json'),
            scope='Descriptive publication only; no new parameter fit, relabel, threshold search or pooled overall accuracy.'))
    at=['# Rà sai khác nhánh cancer theo nguồn và bệnh','',
        'Ngày 14/10/2026. Kiểm chứng **PASS**. Phân tích sau pilot, chỉ train và validation; không fit hoặc đọc thêm điểm held/test trong lượt audit.','',
        '## Phạm vi','',
        '- Trích đặc trưng từ ResNet đóng băng cho 4.043 ảnh train gốc và 807 ảnh train bổ sung. Tái sử dụng các cache validation đã khóa: gốc 718, DermaCon 213, PAD 447.',
        '- So sánh bộ gộp B0/ConvNeXt cũ, ghép đầu cancer hai nhóm và năm nhóm. Giữ hệ số 25%, không sửa nhãn.',
        '- Đếm ảnh đúng thành sai, sai thành đúng và thay đổi sang SkinCancer theo nhãn hiện có. Đây là sai khác với nhãn công bố/thư mục, chưa phải lỗi chẩn đoán đã có bác sĩ xác nhận.','',
        '## Thay đổi khi ghép nhánh năm nhóm','',
        '| Vai trò | Ảnh đổi dự đoán | Đúng → sai | Sai → đúng | Sai → bệnh sai khác |',
        '|---|---:|---:|---:|---:|']
    for s in ('original_train','supplement_train','original_validation','dermacon_validation'):
        d=ar['results'][s]['total']['transitions']['subtype_cancer25']
        at.append(f'| {s} | {d["changed"]} | {d["correct_to_wrong"]} | {d["wrong_to_correct"]} | {d["wrong_to_other_wrong"]} |')
    at+=['','Hai hàng train mô tả độ khớp trên ảnh đã dùng học, không phải accuracy tổng quát hóa.','',
         '## Đầu phụ chạy riêng trên validation nguồn Original-local','',
         'Ngưỡng cố định 0,5; điểm đầu phụ chưa phải xác suất bệnh đã hiệu chỉnh.','',
         '| Nhãn ảnh | Ảnh | Nhánh 2 nhóm gắn cờ | Nhánh 5 nhóm gắn cờ | Bộ gộp cũ gắn cờ | Sau ghép nhánh 5 nhóm |',
         '|---|---:|---:|---:|---:|---:|']
    for c in ar['results']['original_validation']['cells']:
        if c['source']=='Original-local':
            at.append(f'| {c["label"]} | {c["images"]} | {c["raw_auxiliary_flags"]["binary"]} | {c["raw_auxiliary_flags"]["subtype"]} | {c["cancer_flags"]["old_classwise"]} | {c["cancer_flags"]["subtype_cancer25"]} |')
    at+=['','## Kết luận có căn cứ','',
         'Đầu PAD chỉ được học cancer so với NEV/SEK; Lupus, Candidiasis và các bệnh viêm da không có trong cohort học của đầu này. Trên validation gốc, bản ghép năm nhóm tạo 20 cờ cancer mới: 9 ảnh vốn đúng thành sai, chỉ 1 ảnh vốn sai thành đúng. Đây là bằng chứng về nhầm lẫn ngoài cohort học; chưa cô lập được tác động nguồn ảnh và tác động nhãn bệnh.','',
         'Trên train nguồn Original-local, đầu năm nhóm cũng gắn cờ 181/201 Lupus và 147/163 Candidiasis khi chạy riêng. Bộ gộp cũ vẫn giữ được phần lớn quyết định vì tự tin cao trên train đã thấy; kết quả train tốt có thể che nhược điểm của đầu phụ.','',
         'SCIN có nhãn differential hồi cứu; Original-local và atlas thiếu thông tin bệnh nhân/nhãn phân nhóm đầy đủ. Không tự sửa nhãn hoặc gọi các ảnh sai khác là ảnh sai nhãn.','',
         '## Artifacts','',
         '- `prediction_disagreements.jsonl`: đủ 65 ảnh thay đổi trong nhánh năm nhóm trên train/validation; có nguồn, vai trò, nhãn hiện có, dự đoán trước/sau và điểm cancer. `diagnosis_verified=false`, `automatic_relabel=false`.',
         '- `protocol.json`, `results.json`, `verification.json`: thống kê từng nguồn/từng bệnh, SHA dữ liệu/mã; kiểm chứng counts bằng cách đếm độc lập và suy luận lại batch train thật.',
         '- Báo cáo tiếp theo: [pilot bổ sung train tám bệnh cho đầu cancer](86-pilot-nhanh-cancer-hoc-lai-train-tam-benh.md).']
    adoc=root/'docs/85-ra-sai-khac-nhanh-cancer-theo-nguon.md'
    write(adoc,at);write(audit.OUT/'summary.md',at)
    pt=['# Pilot đầu cancer học thêm train tám bệnh gốc','',
        'Ngày 14/10/2026. Kiểm chứng **PASS**. Phương án lựa chọn vẫn là `old_classwise`.','',
        '## Đã sửa thử điều gì','',
        'Audit trước phát hiện đầu chỉ học PAD gắn cờ nhiều Lupus/Candidiasis. Pilot này thêm nhãn binary từ chính train cũ: SkinCancer là nhóm cancer; bảy bệnh còn lại là nhóm không cancer cho nhiệm vụ phụ. Nhãn tám bệnh trong ứng dụng giữ nguyên.','',
        '- Đối chứng: tái lập đúng đầu binary trước trên 1.169 ảnh PAD; hệ số và xác suất đối chứng khớp đầu trước.',
        '- Thử nghiệm: dùng 1.169 ảnh PAD và 4.043 ảnh train gốc, tổng 5.212 đường dẫn ảnh hiện có. Không tải ảnh mới hoặc coi đây là 5.212 bệnh nhân.',
        '- Tổng trọng số mẫu giữ 1.169 cho cả hai nhánh; bản thử chia PAD 75%, train gốc 25%. Cancer/không cancer cùng 50% khối lượng trong mỗi nguồn. Nhóm không cancer gốc chia đều bảy bệnh, rồi nhóm scene/case và ảnh.',
        '- Cùng đặc trưng ResNet 2.048 chiều, scaler từ PAD train và hệ số C=0,001. CNN và scaler đóng băng. Không đổi augmentation, không dò C/ngưỡng/weight theo test.',
        '- Ghép cancer-only cố định 25%; khóa lựa chọn trên validation gốc/DermaCon/PAD trước suy luận held-role. Tất cả các nguồn đã được khảo sát trước, nên kết quả held vẫn là thăm dò.','',
        '## Accuracy / Macro F1','',
        '| Vai trò | Bộ gộp cũ | Đầu chỉ học PAD + ghép | Đầu học thêm train gốc + ghép |',
        '|---|---:|---:|---:|']
    for s in pilot.prior.pad.prior.SPLITS:
        cells=[f'{pct(pr["results"][s][n]["accuracy"])}% / {pct(pr["results"][s][n]["macro_f1"])}%' for n in pilot.METHODS]
        pt.append(f'| {s} | '+' | '.join(cells)+' |')
    pt+=['','Macro F1 dùng tám lớp; DermaCon test chỉ có bảy lớp, SkinDisNet chỉ hai lớp. Không gộp các nguồn thành một chỉ số tổng vì khác vai trò, phân bố bệnh và có bệnh ngoài taxonomy.','',
         '## Validation tám bệnh: bản thử so với bộ gộp cũ','',
         '| Bệnh | Recall cũ | Recall mới | Precision cũ | Precision mới | F1 cũ | F1 mới |',
         '|---|---:|---:|---:|---:|---:|---:|']
    a=pr['results']['original_validation']['old_classwise']['per_class'];b=pr['results']['original_validation']['replay_cancer25']['per_class']
    for c in CLASSES:
        cells=[pct(z[c][field])+'%' for field in ('recall','precision','f1') for z in (a,b)]
        pt.append(f'| {c} | '+' | '.join(cells)+' |')
    pt+=['','## PAD validation: số ảnh được gắn cờ cancer','',
         '| Phương án | BCC /150 | SCC /41 | MEL /7 | Cancer /198 | NEV+SEK /100 | ACK /149 |',
         '|---|---:|---:|---:|---:|---:|---:|']
    for n in pilot.METHODS:
        d=pr['pad_validation'][n]['by_diagnosis']
        pt.append(f'| {n} | {d["BCC"]["flagged"]} | {d["SCC"]["flagged"]} | {d["MEL"]["flagged"]} | '+
                  f'{sum(d[k]["flagged"] for k in ("BCC","SCC","MEL"))} | {d["NEV"]["flagged"]+d["SEK"]["flagged"]} | {d["ACK"]["flagged"]} |')
    pt+=['','PAD ở đây là phép đánh giá cờ SkinCancer, không phải accuracy tám bệnh. ACK được theo dõi riêng và chưa từng dùng làm nhãn âm để train.','',
         '## Kết luận','',
         'Bổ sung train gốc cải thiện so với đầu chỉ học PAD: trên validation gốc, Macro F1 74,92% → 75,73% và F1 Lupus 51,28% → 55,00%. Nhưng bộ gộp cũ vẫn đạt Macro F1 76,66%; recall Candidiasis của bản mới còn 86,67% so với 90,00% của bộ cũ. Precision SkinCancer mới cũng thấp hơn bộ cũ.','',
         'Trên outer 1.176 ảnh, bản thử đạt Accuracy 77,21%, Macro F1 76,14%, nhỉnh hơn bộ gộp cũ 77,04% / 75,88% ở chính fold này. Mức tăng nhỏ trên vai trò đã khảo sát không đủ xác nhận cải thiện tổng thể, nhất là bản thử không đạt điều kiện validation.','',
         'Các điều kiện không đạt của bản thử: Macro F1 và Accuracy validation gốc; recall Candidiasis; tổng cờ ACK/NEV/SEK PAD (143/249 so với 141/249 bộ cũ). Giữ các ngưỡng đã đăng ký; không nới điều kiện sau khi xem điểm.','',
         f'**Điểm chuẩn 5.937 ảnh giữ nguyên: Accuracy {pct(benchmark["accuracy"])}%, Macro F1 {pct(benchmark["macro_f1"])}%. Model ứng dụng không đổi.**','',
         '## Giới hạn và bước tiếp','',
         'Nhãn SkinCancer gốc chưa có phân nhóm BCC/SCC/MEL hoặc xác nhận sinh thiết đầy đủ; nhãn SCIN và nguồn cũ cũng có giới hạn. Replay dùng lại ảnh train, không tạo bệnh nhân mới. Head nhị phân có trọng số cancer/không cancer 50/50, khác cấu trúc tám lớp; điểm đầu phụ chưa được hiệu chỉnh thành xác suất bệnh lâm sàng.','',
         'Bước tiếp: rà độ lệch phân bố nhãn và nguồn trên train để quyết định liệu cần hiệu chỉnh điểm đầu phụ bằng một quy tắc từ train hay đổi nhiệm vụ học. Khóa quy tắc trước thử nghiệm; không dò tỷ lệ ghép theo các điểm held đã đọc, không tự đổi nhãn ảnh.','',
         '## Bằng chứng','',
         '- `ai-service/reports/original_eight_cancer_head_original_replay_fold0_seed42/{protocol,training_report,selection_locked,results,verification,publication_protocol}.json`.',
         '- `control_training_targets.npz`, `replay_training_targets.npz`: nhãn binary và trọng số; không có nhãn tám bệnh giả cho PAD NEV/SEK.',
         '- `results.json`: Accuracy, Macro F1, recall/precision/F1 từng lớp, confusion matrix và calibration theo từng vai trò.',
         '- [Audit trước thử nghiệm](85-ra-sai-khac-nhanh-cancer-theo-nguon.md).']
    pdoc=root/'docs/86-pilot-nhanh-cancer-hoc-lai-train-tam-benh.md';write(pdoc,pt);write(pilot.OUT/'summary.md',pt)
    old=state['latest_completed_experiment']
    state.setdefault('completed_experiment_history',[]).append(dict(name=old['name'],verification=old['verification'],report_path=old.get('report_path')))
    state['previous_completed_experiment']=old
    state['latest_completed_experiment']=dict(name=pilot.OUT.name,verification='PASS',selected_method=pr['selected'],
        architecture='frozen_resnet50_binary_head_original_replay',pad_train_images=1169,original_train_images=4043,
        trainable_cnn=False,original_mass=.25,cancer_mass_weight=.25,control_reproduced_prior=True,
        guard_failures=pv['guard_failures'],results_sha256=sha256_file(pilot.OUT/'results.json'),
        results={s:{n:{k:m[k] for k in ('accuracy','macro_f1')} for n,m in z.items()} for s,z in pr['results'].items()},
        report_path=pdoc.relative_to(root).as_posix(),scope=pr['scope'])
    state['latest_cancer_disagreement_audit']=dict(name=audit.OUT.name,verification='PASS',train_images=4850,
        roles=['original_train','supplement_train','original_validation','dermacon_validation','pad_validation'],
        prediction_changes=65,source_labels_not_clinically_verified=True,report_path=adoc.relative_to(root).as_posix())
    state['latest_pilot']=dict(name=pilot.OUT.name,status='complete_verified',report_path=pdoc.relative_to(root).as_posix())
    state['next_experiment']=None;state['next_experiment_status']='last_pilot_complete_verified';state['updated_on']='2026-10-14'
    state['next_step']='Audit train-only target/source prior mismatch of balanced binary head versus eight-class task before registering prior-aware score correction or different auxiliary task; no coefficient/threshold search on viewed held roles. Preserve original labels, primary5937OOF and serving.'
    assert state['benchmark']==benchmark and state['serving_checkpoint_sha256']==serving and not state['serving_changed']
    save_json(statepath,state)
    readme=root/'README.md';text=readme.read_text(encoding='utf-8');paragraph='\n[Audit sai khác nhánh cancer](docs/85-ra-sai-khac-nhanh-cancer-theo-nguon.md) và [pilot học thêm train tám bệnh](docs/86-pilot-nhanh-cancer-hoc-lai-train-tam-benh.md) đã kiểm chứng PASS. Replay train gốc cải thiện đầu chỉ học PAD nhưng vẫn chưa đạt điều kiện validation; chọn bộ gộp cũ, giữ nguyên điểm chuẩn 5.937 ảnh và model ứng dụng.\n\n'
    assert paragraph.strip() not in text and '## Tài liệu' in text
    readme.write_text(text.replace('## Tài liệu',paragraph+'## Tài liệu',1),encoding='utf-8')
    print('Published audit and replay pilot; primary benchmark and serving preserved.')


if __name__=='__main__':main()
