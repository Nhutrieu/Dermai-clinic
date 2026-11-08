"""Publish verified exploratory cancer-only fusion results, preserving primary OOF."""
from copy import deepcopy
from pathlib import Path

from common import save_json, sha256_file
import pilot_original_eight_frozen_cancer_head as pilot


def pct(value): return f'{100*value:.2f}'


def main():
    out = pilot.OUT; root = pilot.ROOT
    v = pilot.read(out/'verification.json'); r = pilot.read(out/'results.json'); p = pilot.read(out/'protocol.json')
    assert v['status'] == 'PASS' and v['results_sha256'] == sha256_file(out/'results.json')
    statepath = root/'ai-service/reports/active_research_track.json'; state = pilot.read(statepath)
    benchmark = deepcopy(state['benchmark']); serving = state['serving_checkpoint_sha256']
    assert sha256_file(root/benchmark['report_path']) == benchmark['report_sha256']
    assert sha256_file(root/state['serving_checkpoint']) == serving
    proto = dict(publisher_sha256=sha256_file(Path(__file__)), verification_sha256=sha256_file(out/'verification.json'),
                 results_sha256=sha256_file(out/'results.json'), protocol_sha256=sha256_file(out/'protocol.json'),
                 scope='Descriptive publication of locked family; no weight/threshold refit or pooled cross-source accuracy.')
    assert not (out/'publication_protocol.json').exists(), 'Preserve published analysis'
    save_json(out/'publication_protocol.json', proto)
    names = ['old_classwise','binary_cancer25','subtype_cancer25']
    display = dict(old_classwise='Bộ gộp cũ',binary_cancer25='Nhánh 2 nhóm + ghép điểm cancer',subtype_cancer25='Nhánh 5 nhóm + ghép điểm cancer')
    text = ['# Pilot nhánh phụ cancer trên ResNet đóng băng', '', 'Ngày 14/10/2026. Bộ tám bệnh gốc; nghiên cứu một fold/một seed, nguồn đánh giá đã khảo sát.', '',
            f'**Kiểm chứng: PASS. Phương án được khóa chọn: `{r["selected"]}`.**', '',
            '## Đã làm', '',
            '- Đọc lại đầu B0 nhị phân và đầu B0 PAD+MILK bốn nhóm đã thử; cả hai còn đánh đổi giữa melanoma/ung thư và gắn cờ nhầm.',
            '- Huấn luyện hai đầu logistic trên cùng 1.169 ảnh PAD đã audit: 816 ảnh BCC/SCC/MEL và 353 NEV/SEK. Tất cả ảnh được dùng một lần để trích đặc trưng, không có ảnh tăng cường mới.',
            '- Giữ nguyên ResNet50 fold 0, toàn bộ trọng số và BN; lấy 2.048 đặc trưng. Cùng scaler, trọng số theo phân nhóm/bệnh nhân/ảnh, tổng khối lượng cancer và benign đều 50%.',
            '- Nhánh đối chứng học hai nhóm; nhánh thử học riêng BCC, SCC, MEL, NEV, SEK. ACK không train. C=0,001 cố định, không dò tham số/ngưỡng theo kết quả.',
            '- Ghép 25% điểm cancer nhánh phụ với 75% điểm SkinCancer bộ cũ, phân bổ lại bảy điểm còn lại theo tỷ lệ cũ. Thứ tự giữa bảy bệnh được giữ, nhưng quyết định so với SkinCancer vẫn có thể đổi.',
            '- Khóa lựa chọn bằng validation gốc/DermaCon/PAD trước khi suy luận các vai trò held; kiểm chứng lại xác suất bằng NumPy, metrics, SHA và một batch suy luận thật.', '',
            '## Accuracy / Macro F1', '',
            'Macro F1 dưới đây dùng danh mục tám lớp; DermaCon official test chỉ có bảy lớp và SkinDisNet chỉ có hai lớp, nên không so trực tiếp F1 giữa các nguồn.', '',
            '| Vai trò | Ảnh | Bộ gộp cũ | Nhánh 2 nhóm | Nhánh 5 nhóm |',
            '|---|---:|---:|---:|---:|']
    for split in pilot.pad.prior.SPLITS:
        cells = [f'{pct(r["results"][split][n]["accuracy"])}% / {pct(r["results"][split][n]["macro_f1"])}%' for n in names]
        text.append(f'| {split} | {len(p["splits"][split])} | '+ ' | '.join(cells)+' |')
    text += ['', '## PAD validation: quyết định argmax SkinCancer', '',
             'Các tỷ lệ dưới đây là nhận/gắn cờ SkinCancer theo nhãn PAD, không phải accuracy tám bệnh. ACK được báo riêng; không gán ACK là ung thư hoặc nhãn âm để train.', '',
             '| Phương án | BCC /150 | SCC /41 | MEL /7 | Tổng cancer /198 | NEV+SEK /100 | ACK /149 |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for n in names:
        d = r['pad_validation'][n]['by_diagnosis']
        text.append(f'| {display[n]} | {d["BCC"]["flagged"]} | {d["SCC"]["flagged"]} | {d["MEL"]["flagged"]} | '+
            f'{sum(d[k]["flagged"] for k in ("BCC","SCC","MEL"))} | {d["NEV"]["flagged"]+d["SEK"]["flagged"]} | {d["ACK"]["flagged"]} |')
    text += ['', '## Điều kiện chọn và giới hạn', '']
    for n in names[1:]: text.append(f'- `{n}`: '+(', '.join(v['guard_failures'][n]) or 'đạt điều kiện validation')+'.')
    text += ['', f'Phương án giữ lại sau điều kiện đã đăng ký: **{display[r["selected"]]}**. Kết quả giảm gắn cờ nhầm phải được đọc cùng mức giữ lại ung thư, F1, recall và precision từng lớp; tăng một nguồn chưa xác nhận tốt hơn toàn bộ.', '',
             'Bảng nhánh độc lập dùng ngưỡng cố định 0,5 được lưu trong `results.json/standalone_pad_flags`; không dùng ngưỡng đó để tự động thay quyết định ứng dụng. Xác suất của đầu PAD không phải nguy cơ lâm sàng đã hiệu chỉnh.', '',
             'NEV/SEK không có trong tám bệnh và không được đổi nhãn. Nhãn công bố chưa được nhóm bác sĩ rà soát riêng; không phải mọi ảnh âm đều có sinh thiết. MEL validation chỉ bảy ảnh. Đây là thử nghiệm thăm dò trên nguồn và validation đã xem, chưa có test bệnh nhân mới độc lập.', '',
             f'**Điểm chuẩn 5.937 ảnh không đổi: Accuracy {pct(benchmark["accuracy"])}%, Macro F1 {pct(benchmark["macro_f1"])}%.** Checkpoint và cấu hình phục vụ ứng dụng giữ nguyên.', '',
             '## Bước tiếp có căn cứ', '',
             'Đối chiếu nguồn/nhóm ảnh trên train và validation giữa đầu cancer và bộ gộp cũ trước khi đăng ký thêm mô hình. Không dò lại hệ số ghép bằng các điểm held đã đọc. Đầu PAD riêng chỉ thấy cancer/NEV/SEK nên cần kiểm tra nhầm lẫn với các bệnh viêm da trước khi mở rộng nguồn huấn luyện.', '',
             '## Bằng chứng', '',
             '- `ai-service/reports/original_eight_frozen_cancer_head_fold0_seed42/{protocol,training_report,selection_locked,results,verification,publication_protocol}.json`',
             '- `ai-service/candidates/original_eight_frozen_cancer_head_fold0_seed42/{binary,subtype}.npz`: scaler và hệ số đầu đã học; không có CNN mới.',
             '- Các cache `.npz` lưu feature, nhãn thật, điểm nhánh phụ và xác suất tám lớp; `results.json` có recall/precision/F1 từng lớp và confusion matrix.',
             '- Tham chiếu thử nghiệm trước: `docs/32-*`, `docs/39-*`, `docs/83-pilot-nhan-phu-khong-skincancer.md`.']
    report = '\n'.join(text)+'\n'
    doc = root/'docs/84-pilot-nhanh-cancer-resnet-dong-bang.md'; doc.write_text(report,encoding='utf-8')
    (out/'summary.md').write_text(report,encoding='utf-8')
    completed = dict(name=out.name,verification='PASS',selected_method=r['selected'],architecture='frozen_resnet50_plus_logistic_heads',
        auxiliary_train_images=1169,positive_images=816,negative_images=353,trainable_cnn=False,
        cancer_mass_weight=.25,results_sha256=sha256_file(out/'results.json'),guard_failures=v['guard_failures'],
        results={s:{n:{k:m[k] for k in ('accuracy','macro_f1')} for n,m in z.items()} for s,z in r['results'].items()},
        report_path=doc.relative_to(root).as_posix(),scope='Onefold/seed exploratory previously inspected sources; no new independent confirmation.')
    old = state['latest_completed_experiment']
    state.setdefault('completed_experiment_history',[]).append(dict(name=old['name'],report_path=old.get('report_path'),verification=old.get('verification')))
    state['previous_completed_experiment']=old; state['latest_completed_experiment']=completed
    state['latest_pilot']=dict(name=out.name,status='complete_verified',report_path=completed['report_path'])
    state['next_experiment']=None; state['next_experiment_status']='last_pilot_complete_verified'
    state['next_step']='Train/validation-only source and disagreement audit of frozen cancer heads versus original classwise reference before further intervention; do not refit fusion to viewed held-role scores. Preserve 5937 OOF and serving.'
    state['updated_on']='2026-10-14'
    assert state['benchmark']==benchmark and state['serving_checkpoint_sha256']==serving and not state['serving_changed']
    save_json(statepath,state)
    readme=root/'README.md'; content=readme.read_text(encoding='utf-8')
    paragraph='\n[Pilot nhánh cancer ResNet đóng băng](docs/84-pilot-nhanh-cancer-resnet-dong-bang.md) đã train hai đầu trên 1.169 ảnh PAD và kiểm chứng PASS. Chỉ ghép điểm SkinCancer với hệ số cố định 25%; kết quả và điều kiện giữ lại từng bệnh được báo riêng. Điểm chuẩn 5.937 ảnh và model ứng dụng không đổi.\n\n'
    assert paragraph.strip() not in content
    assert '## Tài liệu' in content
    readme.write_text(content.replace('## Tài liệu',paragraph+'## Tài liệu',1),encoding='utf-8')
    print('Published verified frozen cancer-head pilot; primary benchmark and serving preserved.')


if __name__=='__main__': main()
