"""Publish verified PAD data preparation and matched pilot metrics."""
from collections import Counter
from pathlib import Path
import numpy as np

from common import CLASSES,save_json,sha256_file
import pilot_original_eight_pad_addition as e
from summarize_original_eight_resnet50_cv import paired_bootstrap


def pct(x): return f'{100*x:.2f}%'.replace('.',',')


def failures(t,reference):
    a,b=t['original_validation'],reference['original_validation']; out=[]
    if a['accuracy']<b['accuracy']-.005-1e-12: out.append('Accuracy validation cũ giảm quá 0,5 điểm %')
    if a['macro_f1']<b['macro_f1']-1e-12: out.append('Macro F1 validation cũ thấp hơn reference')
    if a['per_class']['SkinCancer']['recall']<b['per_class']['SkinCancer']['recall']-1e-12: out.append('Recall SkinCancer validation cũ giảm')
    for c in CLASSES:
        if c not in ('Lupus','Psoriasis') and a['per_class'][c]['recall']<b['per_class'][c]['recall']-.02-1e-12: out.append('Recall '+c+' validation cũ giảm quá 2 điểm %')
    for c in ('Lupus','Psoriasis'):
        if a['per_class'][c]['precision']<b['per_class'][c]['precision']-.02-1e-12: out.append('Precision '+c+' validation cũ giảm quá 2 điểm %')
    a,b=t['dermacon_validation'],reference['dermacon_validation']
    if a['macro_f1']<b['macro_f1']-1e-12: out.append('Macro F1 validation DermaCon giảm')
    if a['per_class']['SkinCancer']['recall']<b['per_class']['SkinCancer']['recall']-1e-12: out.append('Recall SkinCancer validation DermaCon giảm')
    if np.mean([a['per_class'][c]['recall'] for c in ('Candidiasis','Lupus','Tinea')])<np.mean([b['per_class'][c]['recall'] for c in ('Candidiasis','Lupus','Tinea')])-1e-12: out.append('Recall trung bình Candidiasis/Lupus/Tinea validation DermaCon giảm')
    a,b=t['pad_validation'],reference['pad_validation']
    for d in ('BCC','SCC','MEL'):
        if a['by_diagnosis'][d]['flag_rate']<b['by_diagnosis'][d]['flag_rate']-1e-12: out.append('Recall '+d+' PAD validation giảm')
    if a['non_cancer_flag_rate']>b['non_cancer_flag_rate']+1e-12: out.append('Tỷ lệ gắn cờ SkinCancer trên ACK/NEV/SEK PAD validation tăng')
    return out


def main():
    p=e.read(e.OUT/'protocol.json'); r=e.read(e.OUT/'results.json'); lock=e.read(e.OUT/'selection_locked.json'); v=e.read(e.OUT/'verification.json')
    ds=e.read(e.audit.OUT/'summary.json'); dv=e.read(e.audit.OUT/'verification.json')
    assert v['status']=='PASS' and v['results_sha256']==sha256_file(e.OUT/'results.json')
    assert dv['status']=='PASS' and dv['summary_sha256']==sha256_file(e.audit.OUT/'summary.json')
    history={b:e.read(e.MODELS/b/'history.json') for b in e.BRANCHES}
    seen=[]
    for epoch in range(1,4): seen.extend(i-4850 for i in e.paired_draws(p,epoch)[1] if i>=4850)
    unique=sorted(set(seen)); patient_count=len({p['pad'][i]['source_patient_id'] for i in unique})
    analysis_protocol=dict(result_sha256=sha256_file(e.OUT/'results.json'),bootstrap_helper_sha256=sha256_file(Path(__file__).parent/'summarize_original_eight_resnet50_cv.py'),
        publisher_sha256=sha256_file(Path(__file__)),replicates=2000,seed=20261014,
        scope='Secondary descriptive paired case/scene bootstrap of PAD-minus-control on3previously viewed held roles; one seed, no multiple-comparison correction or selection uncertainty.')
    save_json(e.OUT/'analysis_protocol.json',analysis_protocol)
    intervals={}
    for split in e.prior.SPLITS[2:]:
        with np.load(e.OUT/(split+'.npz')) as z:
            intervals[split]={name:paired_bootstrap(p['splits'][split],z['pad_'+name],z['control_'+name],seed=20261014,reps=2000) for name in ('resnet','mix25')}
    save_json(e.OUT/'paired_comparisons.json',intervals)
    trials={t['name']:t for t in lock['trials']}
    reasons={n:failures(t,trials['old_classwise']) for n,t in trials.items()}
    for n,t in trials.items(): assert bool(reasons[n])== (not t['eligible'])
    save_json(e.OUT/'decision_reasons.json',reasons)
    lines=['# 82. Bổ sung SkinCancer từ PAD: lọc bệnh nhân và pilot có đối chứng','',
        'Ngày 14/10/2026. **Đã lọc dữ liệu, train hai nhánh và kiểm chứng PASS.** Kết quả dưới đây là pilot một fold/seed trên các nguồn đã từng khảo sát.','',
        '## Dữ liệu đã đạt kiểm tra','',
        f"821 ứng viên [PAD train](81-ra-train-theo-nguon-va-ung-vien-skincancer.md) được đối chiếu với **{ds['protected_images']:,} ảnh bảo vệ**: toàn bộ 5.937 ảnh phát triển cũ, test lịch sử, các vai trò DermaCon/SkinDisNet, dữ liệu bổ sung trước, cùng manifest HIBA/DermaNet/MED-NODE/MILK/SLICE và PAD validation/bệnh nhân cách ly trước.",
        '','- So SHA-256, pixel RGB sau xử lý hướng EXIF, và dHash gốc ở khoảng cách ≤3. Nối ảnh theo bệnh nhân PAD và liên kết ảnh tương tự; cách ly cả thành phần khi có hit hoặc nhãn subtype mâu thuẫn trên cùng pixel.',
        f"- Giữ **{ds['retained_images']} ảnh / {ds['retained_patients']} bệnh nhân**; cách ly {ds['quarantined_images']} ảnh, bỏ lặp pixel {ds['redundant_images']} ảnh. Năm ảnh cách ly thuộc nhóm có nội dung pixel giống nhau nhưng chẩn đoán nguồn mâu thuẫn. Không có hit trực tiếp với các ảnh bảo vệ ở lượt audit hiện tại.",
        '- Bảo toàn 447 ảnh PAD validation và bệnh nhân của chúng. Không dùng ACK/NEV/SEK làm nhãn của bảy bệnh còn lại. Các ảnh cancer có `biopsed=True` trong metadata công bố; không có bác sĩ mới rà lại trong dự án.',
        '- Kiểm chứng độc lập bằng popcount Hamming và dựng lại đồ thị thành phần, không chỉ chạy lại BK-tree. Lọc tương tự không chứng minh độc lập tuyệt đối với những nguồn thiếu mã người bệnh.','',
        '| PAD train được giữ | Ảnh | Bệnh nhân theo subtype |','|---|---:|---:|---:|']
    for d,c in ds['by_diagnosis'].items(): lines.append(f"| {d} | {c['images']} | {c['patients']} |")
    lines += ['', 'Các nhóm bệnh nhân theo subtype có giao nhau. Không cộng cột người để ra tổng.','',
        '## Pilot được khóa trước train/đánh giá','',
        '- Hai ResNet-50 cùng checkpoint fold 0 raw epoch 17, seed 42, ba epoch, cùng AdamW/LR/loss weights cũ/smoothing/clip/AMP. Mỗi nhánh **759 bước cập nhật thật**, không chọn lại epoch.',
        '- Đối chứng giữ sampler 90% ảnh train cũ / 10% pool bổ sung 807 ảnh trước. Can thiệp giữ tất cả lượt 807 ảnh phụ và thay đúng **202 vị trí ảnh cũ mỗi epoch** bằng PAD (khoảng 5% lượt train). Cùng tổng 4.043 lượt/epoch, không tăng số bước.',
        '- PAD lấy theo ba subtype với khối xác suất đều 1/3, trong mỗi subtype lấy đều bệnh nhân rồi ảnh của bệnh nhân. Đây là thử thêm dữ liệu với sampler đã định; không tách riêng được tác động của ảnh thêm và cách lấy subtype.',
        '- Augmentation dùng seed riêng cho từng vị trí để kích thước ảnh PAD không làm lệch RNG của ảnh replay tiếp theo. Hash toàn bộ ảnh/nhãn sau augmentation ở các vị trí dùng chung khớp cả ba epoch. Luồng này khác các pilot trước; đối chứng mới được train lại.',
        '- Giữ công thức ensemble 75% reference B0/ConvNeXt + 25% ResNet, không dò nhiệt độ/trọng số hoặc sửa nhãn SCIN.',
        '- Chọn qua guard cũ trên original/DermaCon validation, đồng thời Recall BCC/SCC/MEL PAD validation không giảm và tỷ lệ gắn cờ nhầm trên ACK/NEV/SEK không tăng so với reference. Reference làm phương án dự phòng. Khóa lựa chọn trước inference mới ở original outer/DermaCon test/SkinDisNet.','',
        f"Pool PAD có 816 ảnh nhưng ba epoch thực sự lấy **606 lượt**, tương ứng **{len(unique)} ảnh khác nhau từ {patient_count} bệnh nhân**. Không nói toàn bộ 816 ảnh đều đã được train hay 606 lượt là 606 ảnh mới.",'',
        '| Epoch | Lượt BCC | Lượt SCC | Lượt MEL |','|---|---:|---:|---:|']
    for h in history['pad']: lines.append(f"| {h['epoch']} | {h['pad_subtype_draws'].get('BCC',0)} | {h['pad_subtype_draws'].get('SCC',0)} | {h['pad_subtype_draws'].get('MEL',0)} |")
    lines += ['', '## ResNet riêng: tác động thêm PAD','',
        '| Tập | Ảnh | Accuracy đối chứng | Accuracy PAD | Macro F1 đối chứng | Macro F1 PAD |','|---|---:|---:|---:|---:|---:|']
    titles=dict(original_validation='Original validation',dermacon_validation='DermaCon validation',original_outer='Original outer fold 0',dermacon_official_test='DermaCon official test',skindisnet_transfer='SkinDisNet transfer')
    for split in e.prior.SPLITS:
        a,b=r['results'][split]['control_resnet'],r['results'][split]['pad_resnet']; present=sum(m['support']>0 for m in b['per_class'].values())
        lines.append(f"| {titles[split]} | {len(p['splits'][split]):,} | {pct(a['accuracy'])} | {pct(b['accuracy'])} | {pct(a['macro_f1']*8/present)} | {pct(b['macro_f1']*8/present)} |")
    lines += ['', 'Macro F1 bảng này tính trên lớp có mẫu: tám ở original/DermaCon validation, bảy ở DermaCon test, hai ở SkinDisNet. Các model vẫn dự đoán đủ tám lớp; JSON có Macro F1 đủ tám lớp.','',
        '## Ensemble giữ cùng mức gộp 25%','',
        '| Tập | Accuracy reference | Accuracy đối chứng | Accuracy PAD | Macro F1 đối chứng đủ 8 lớp | Macro F1 PAD đủ 8 lớp |','|---|---:|---:|---:|---:|---:|']
    for split in e.prior.SPLITS:
        a,b,ref=[r['results'][split][n] for n in ('control_mix25','pad_mix25','old_classwise')]
        lines.append(f"| {titles[split]} | {pct(ref['accuracy'])} | {pct(a['accuracy'])} | {pct(b['accuracy'])} | {pct(a['macro_f1'])} | {pct(b['macro_f1'])} |")
    lines += ['', '### Các bệnh cần theo dõi trên original outer','',
        '| Bệnh | Recall ResNet đối chứng | Recall ResNet PAD | Recall gộp đối chứng | Recall gộp PAD |','|---|---:|---:|---:|---:|']
    rr=r['results']['original_outer']
    for c in CLASSES:
        lines.append(f"| {c} | "+' | '.join(pct(rr[n]['per_class'][c]['recall']) for n in ('control_resnet','pad_resnet','control_mix25','pad_mix25'))+' |')
    lines += ['', '## PAD validation: giữ riêng từng chẩn đoán','',
        '| Nhãn nguồn | Ảnh | Reference gắn cờ SkinCancer | ResNet đối chứng | ResNet PAD | Gộp đối chứng | Gộp PAD |','|---|---:|---:|---:|---:|---:|---:|']
    for d in ('BCC','SCC','MEL','ACK','NEV','SEK'):
        count=r['pad_validation']['old_classwise']['by_diagnosis'][d]['images']
        lines.append(f'| {d} | {count} | '+' | '.join(str(r['pad_validation'][n]['by_diagnosis'][d]['flagged']) for n in ('old_classwise','control_resnet','pad_resnet','control_mix25','pad_mix25'))+' |')
    lines += ['', 'BCC/SCC/MEL cần được gắn cờ; ACK/NEV/SEK báo tỷ lệ gắn cờ theo nhãn nguồn, không ghép thành nhãn khác của tám bệnh. Không có Accuracy tám lớp cho PAD vì ba nhóm ngoài phạm vi. PAD validation đã được dùng trong nghiên cứu trước, có ít melanoma nên không xác nhận độ nhạy ổn định.',
        '','Bản gộp PAD tăng ảnh ung thư được gắn cờ **144/198 → 165/198**, nhưng tăng gắn cờ ở ACK/NEV/SEK **124/249 → 157/249**. ResNet riêng tăng Recall cancer trên PAD nhưng giảm Recall SkinCancer original outer **122/165 → 120/165**; bản gộp original giữ 138/165, vẫn thấp hơn reference 142/165. Đây chưa phải cải thiện nhất quán giữa nguồn ảnh.',
        '','Pilot PAD chỉ thêm ảnh cancer. Mức tăng gắn cờ trên cả nhóm khác phù hợp với giả thuyết model học xu hướng gán ảnh nguồn PAD vào SkinCancer; kết quả này chưa chứng minh nguyên nhân. Một can thiệp tiếp theo có thể kiểm tra giả thuyết bằng dữ liệu đối chiếu cùng nguồn.','',
        '## Lựa chọn đã khóa và bất định','',f"**Phương án được chọn: `{lock['selected']}`.**",'']
    for name in ('control_mix25','pad_mix25'):
        lines.append(f"- `{name}`: "+('; '.join(reasons[name]) if reasons[name] else 'đạt các guard đã khóa')+'.')
    lines += ['', 'Các khoảng dưới là chênh lệch Accuracy **gộp PAD − gộp đối chứng**, bootstrap ghép theo ca/cảnh. Không tính bất định do nhiều thử nghiệm đã qua; không biến các nguồn đã xem thành test độc lập.','']
    for split,item in intervals.items():
        low,high=item['mix25']['accuracy_delta_ci95']; diff=r['results'][split]['pad_mix25']['accuracy']-r['results'][split]['control_mix25']['accuracy']
        lines.append(f"- {titles[split]}: {100*diff:+.2f} điểm %; CI95% [{100*low:+.2f}; {100*high:+.2f}].")
    lines += ['', '## Điểm tổng và trạng thái ứng dụng','',
        'Pilot này chưa phải năm fold hoặc bộ bệnh nhân mới. Mốc 5.937 ảnh giữ nguyên: reference chính **78,07% Accuracy / 76,82% Macro F1**, công thức thử trước **79,06% / 77,98%** chưa qua guard. Không cộng các bộ validation/test khác nhau thành một độ chính xác tổng mới. Checkpoint ứng dụng vẫn là B0 ban đầu.',
        '','**Bước tiếp cụ thể:** chuẩn bị các ảnh NEV/SEK từ đúng PAD train làm dữ liệu đối chiếu; audit chung theo bệnh nhân và ảnh với pool positive/bộ bảo vệ. Chúng không có nhãn tám lớp hợp lệ: nếu thử loss phụ hoặc head nhị phân thì chỉ dùng nhãn cancer-vs-noncancer nguồn đã công bố, không ép sang Acne/Eczema/Tinea hoặc “da khỏe”. ACK giữ báo riêng. Khóa một pilot có đối chứng để kiểm tra giảm dương tính giả và giữ các bệnh cũ; không mở rộng cấu hình positive-only này ra năm fold. Đây là hướng thử tiếp, chưa train thêm hoặc khẳng định sẽ cải thiện.','',
        '## Kiểm chứng và tệp','',
        'PASS: SHA nguồn/code/checkpoint/ảnh; sampler thay đúng 202 vị trí cũ, bảo toàn lượt auxiliary và các vị trí dùng chung; subtype/patient probability; cùng loss weights/759 cập nhật; hash augmentation dùng chung; tính lại Accuracy/Precision/Recall/F1/confusion/fusion; PAD flags từng subtype; guard/rank và khóa trước held-role; inference thật cùng batch 16 trên student/parent; dữ liệu và model phục vụ không đổi.','',
        '- [Audit dữ liệu PAD](../ai-service/reports/original_eight_pad_supplement_audit_20261014/summary.json), [PASS dữ liệu](../ai-service/reports/original_eight_pad_supplement_audit_20261014/verification.json).',
        '- [Giao thức pilot](../ai-service/reports/original_eight_pad_addition_pilot_fold0_seed42/protocol.json), [lựa chọn](../ai-service/reports/original_eight_pad_addition_pilot_fold0_seed42/selection_locked.json).',
        '- [Chỉ số từng bệnh/confusion](../ai-service/reports/original_eight_pad_addition_pilot_fold0_seed42/results.json), [bootstrap ghép](../ai-service/reports/original_eight_pad_addition_pilot_fold0_seed42/paired_comparisons.json), [lý do guard](../ai-service/reports/original_eight_pad_addition_pilot_fold0_seed42/decision_reasons.json).',
        '- [PASS pilot](../ai-service/reports/original_eight_pad_addition_pilot_fold0_seed42/verification.json), [mã pilot](../ai-service/training/pilot_original_eight_pad_addition.py), [kiểm chứng phiên bản 2](../ai-service/training/verify_original_eight_pad_addition_v2.py), [giao thức sửa kiểm chứng](../ai-service/reports/original_eight_pad_addition_pilot_fold0_seed42/verification_protocol_v2.json).',
        '- Phiên bản kiểm chứng đầu truyền protocol thay vì danh sách PAD vào hàm tính sampling weights. Phiên bản 2 sửa đúng đối số; giữ nguyên mã/manifest/train/checkpoint/predictions đã khóa.','']
    doc=e.ROOT/'docs/82-pilot-bo-sung-pad-skincancer-co-doi-chung.md'; doc.write_text('\n'.join(lines),encoding='utf-8')
    report='\n'.join(lines).replace('../ai-service/training/','../../training/').replace('../ai-service/reports/original_eight_pad_addition_pilot_fold0_seed42/','').replace('../ai-service/reports/original_eight_pad_supplement_audit_20261014/','../original_eight_pad_supplement_audit_20261014/').replace('(81-ra-train-theo-nguon-va-ung-vien-skincancer.md)','(../../../docs/81-ra-train-theo-nguon-va-ung-vien-skincancer.md)')
    (e.OUT/'summary.md').write_text(report,encoding='utf-8')
    statepath=e.ROOT/'ai-service/reports/active_research_track.json'; state=e.read(statepath)
    assert state['active_track']=='original_eight' and sha256_file(e.ROOT/state['serving_checkpoint'])==state['serving_checkpoint_sha256']
    assert sha256_file(e.ROOT/state['benchmark']['report_path'])==state['benchmark']['report_sha256']
    name=e.OUT.name
    if state['latest_completed_experiment']['name']!=name:
        historylist=state.setdefault('completed_experiment_history',[])
        for key in ('previous_completed_experiment','latest_completed_experiment'):
            if state.get(key) and all(x['name']!=state[key]['name'] for x in historylist): historylist.append(state[key])
        state['previous_completed_experiment']=state['latest_completed_experiment']
    state['updated_on']='2026-10-14'
    state['latest_completed_experiment']=dict(name=name,verification='PASS',architecture='resnet50',branches=['control','pad'],epochs_each=3,actual_updates=v['actual_updates'],
        pad_images=816,pad_patients=494,pad_draws=606,pad_unique_images_seen=len(unique),pad_unique_patients_seen=patient_count,
        shared_augmentation_matches=True,selected_method=lock['selected'],results={s:{n:{k:m[k] for k in ('accuracy','macro_f1')} for n,m in rr.items()} for s,rr in r['results'].items()},
        pad_validation=r['pad_validation'],scope=r['scope'],results_sha256=v['results_sha256'],
        report_path=doc.relative_to(e.ROOT).as_posix(),verification_path=(e.OUT/'verification.json').relative_to(e.ROOT).as_posix(),
        decision='Keep registered selection; onefold results do not change fullOOF or serving. Guard failures are in decision_reasons.json.')
    state['latest_pilot']=dict(name=name,status='complete_verified',protocol_path=(e.OUT/'protocol.json').relative_to(e.ROOT).as_posix())
    state['latest_pad_preparation']=dict(name=e.audit.OUT.name,status='verified_and_used_as_auxiliary_train_pool',verification='PASS',retained_images=816,retained_patients=494,quarantined_images=5,
        protected_images=17201,by_diagnosis=ds['by_diagnosis'],reserved_pad_validation_images=447,report_path=(e.audit.OUT/'summary.json').relative_to(e.ROOT).as_posix())
    state['latest_data_inventory']['status']='current_overlap_audit_complete_816retained_used_in_pilot'
    state['latest_data_inventory']['training_eligible_images']=816
    state['next_experiment']=None; state['next_experiment_status']='last_pilot_complete_verified'
    state['next_step']='Prepare same historical-PAD-train NEV/SEK comparison images with joint patient/pixel/near audit against positive pool and protected roles. They have no original8class target: register matched auxiliary cancer-vs-noncancer/complement supervision if eligible, ACK assessed separately. Test reduced false positives and old-class retention without further fusion tuning to viewed held scores; do not expand positive-onlypilot to5fold or alter serving.'
    save_json(statepath,state)
    print(dict(report=str(doc),selected=lock['selected'],pad_unique_images_seen=len(unique),pad_unique_patients_seen=patient_count,benchmark_and_serving_unchanged=True))


if __name__=='__main__': main()
