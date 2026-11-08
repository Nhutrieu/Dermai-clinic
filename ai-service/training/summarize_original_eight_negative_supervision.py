"""Publish the FP32matched complementary-supervision pilot, retaining AMP failure."""
import json
from collections import Counter
from pathlib import Path

import numpy as np
from common import CLASSES,save_json,sha256_file
import pilot_original_eight_negative_supervision_fp32 as e
from summarize_original_eight_resnet50_cv import paired_bootstrap
from summarize_original_eight_pad_addition import failures


def pct(x): return f'{100*x:.2f}%'.replace('.',',')


def main():
    root,out=e.ROOT,e.OUT; p=e.read(out/'protocol.json'); r=e.read(out/'results.json'); v=e.read(out/'verification.json'); lock=e.read(out/'selection_locked.json')
    s=e.read(e.joint.OUT/'summary.json'); dv=e.read(e.joint.OUT/'verification.json')
    assert v['status']=='PASS' and v['results_sha256']==sha256_file(out/'results.json')
    assert dv['status']=='PASS' and dv['summary_sha256']==sha256_file(e.joint.OUT/'summary.json')
    assert v['actual_updates']==dict(control=759,negative=759)
    repair=e.read(out/'numerical_repair.json'); assert repair['outcomes_used_for_repair'] is False
    pos=[]; neg=[]
    for epoch in range(1,4):
        ids,mapping=e.schedules(p,epoch); pos.extend(i-4850 for i in ids if i>=4850); neg.extend(mapping.values())
    posseen=set(pos); negseen=set(neg)
    exposure=dict(positive_draws=len(pos),positive_unique_images=len(posseen),positive_unique_patients=len({p['pad'][i]['source_patient_id'] for i in posseen}),
        negative_draws=len(neg),negative_unique_images=len(negseen),negative_unique_patients=len({p['negative'][i]['source_patient_id'] for i in negseen}))
    save_json(out/'exposure.json',exposure)
    trials={t['name']:t for t in lock['trials']}; reasons={n:failures(t,trials['old_classwise']) for n,t in trials.items()}
    for n,t in trials.items(): assert bool(reasons[n])== (not t['eligible'])
    save_json(out/'decision_reasons.json',reasons)
    analysis=dict(result_sha256=sha256_file(out/'results.json'),publisher_sha256=sha256_file(Path(__file__)),
        helpers={n:sha256_file(Path(__file__).parent/n) for n in ('summarize_original_eight_resnet50_cv.py','summarize_original_eight_pad_addition.py')},
        seed=20261014,replicates=2000,scope='Secondary exploratory grouped paired negative-minus-control, previously viewed sources; one seed/no multiplicity correction.')
    save_json(out/'analysis_protocol.json',analysis)
    intervals={}
    for split in e.previous.prior.SPLITS[2:]:
        with np.load(out/(split+'.npz')) as z:
            intervals[split]={n:paired_bootstrap(p['splits'][split],z['negative_'+n],z['control_'+n],seed=20261014,reps=2000) for n in ('resnet','mix25')}
    save_json(out/'paired_comparisons.json',intervals)
    lines=['# 83. Pilot nhãn phủ định SkinCancer trên ảnh NEV/SEK','',
        'Ngày 14/10/2026. **Audit dữ liệu và pilot FP32 đã hoàn tất, kiểm chứng PASS.** Đây là một fold/seed trên nguồn và validation đã khảo sát; không có bộ bệnh nhân kiểm thử mới.','',
        '## Mục đích và nhãn phụ','',
        '[Pilot chỉ thêm PAD cancer](82-pilot-bo-sung-pad-skincancer-co-doi-chung.md) tăng nhận đúng ảnh cancer nhưng tăng gắn cờ ở nhóm khác. Lượt này dùng ảnh NEV/SEK cùng nguồn làm dữ liệu đối chiếu, đo tác động riêng của loss phủ định.',
        '','Loss phụ là `-log(1-p[SkinCancer])`, mượn ý tưởng Eq.2 của [NLNL, Kim và cộng sự, ICCV 2019](https://arxiv.org/abs/1908.07387). Bài gốc dùng nhãn phủ định ngẫu nhiên để xử lý nhiễu trong tập lớp đóng. Pilot dùng nhãn SkinCancer cố định trên ảnh ngoài tám lớp; không tái lập SelNL/SelPL hoặc lọc nhãn theo AI.',
        '','NEV/SEK có `label=None`, chỉ có `complementary_label=SkinCancer`. Không gán chúng thành Acne/Eczema/Tinea, không tạo nhãn “da khỏe”. Loss giảm xác suất SkinCancer, nhưng **không làm AI nhận đúng NEV/SEK hoặc từ chối ảnh ngoài phạm vi**; khối xác suất còn lại vẫn nằm ở bảy lớp khác.','',
        '## Audit chung theo bệnh nhân','',
        'Tái tạo đúng 1.703 ảnh PAD train lịch sử, cùng 447 ảnh validation. Audit tất cả ảnh train, kể cả ACK chỉ dùng phát hiện mâu thuẫn; đối chiếu **17.201 ảnh bảo vệ** theo SHA/pixel RGB sau EXIF/dHash ≤3. Nối các ảnh theo mã bệnh nhân/ảnh tương tự; cách ly cả thành phần khi gặp nguồn bảo vệ hoặc cùng pixel có chẩn đoán mâu thuẫn.',
        '',f"Giữ {s['retained_images']} ảnh trong audit chung, cách ly {s['quarantined_images']}, bỏ {s['redundant_images']} ảnh lặp pixel. Ảnh được dùng train: **{s['positive_images']} cancer và {s['negative_images']} NEV/SEK**. {s['by_diagnosis']['ACK']['images']} ảnh ACK còn lại không được dùng làm mục tiêu loss phủ định.",'',
        '| Nhãn PAD | Ảnh giữ lại | Mã bệnh nhân theo nhãn | Vai trò |','|---|---:|---:|---|']
    for d,c in s['by_diagnosis'].items():
        role='CE SkinCancer' if d in ('BCC','SCC','MEL') else 'Chỉ nhãn phủ định SkinCancer' if d in ('NEV','SEK') else 'Audit, không train'
        lines.append(f"| {d} | {c['images']} | {c['patients']} | {role} |")
    lines += ['',f"NEV/SEK gồm **{s['negative_patients']} mã bệnh nhân**; {s['positive_negative_shared_train_patients']} mã có cả tổn thương cancer và NEV/SEK ở train. Có giao nhau giữa các subtype nên không cộng cột bệnh nhân. Tất cả bệnh nhân train tách khỏi PAD validation.",
        '','Metadata cancer ghi `biopsed=True`; NEV/SEK có cả nhãn lâm sàng và sinh thiết nguồn, không tuyên bố mọi ảnh đối chiếu đều sinh thiết xác nhận hoặc đã được bác sĩ mới rà. Kiểm chứng độc lập dùng Hamming lookup và dựng lại đồ thị, không chỉ lặp lại BK-tree.','',
        '## Đối chứng và sửa số học trước khi chọn kết quả','',
        '- Pilot AMP đầu có 759 cập nhật ở đối chứng, 758 ở nhánh loss phụ vì một bước bị GradScaler bỏ qua. Giữ toàn bộ mã/nhật ký/checkpoint/kết quả này, ghi gate chưa đạt. Chọn chạy lại FP32 từ **số bước cập nhật**, trước khi đọc chỉ số để quyết định sửa; không chọn bản theo điểm cao hơn.',
        '- Pilot báo chính dùng FP32 toàn bộ ở cả hai nhánh, GradScaler tắt, kiểm tra gradient hữu hạn. Cùng checkpoint ResNet fold 0 raw epoch 17, seed 42, dữ liệu/sampler/augmentation/loss weights/AdamW/LR, ba epoch và **759 cập nhật thật mỗi nhánh**.',
        '- Cả hai có cùng main replay 4.043 lượt/epoch với 202 vị trí PAD cancer như pilot trước, cùng 202 lượt NEV/SEK mỗi epoch. NEV/SEK lấy đều hai subtype rồi đều bệnh nhân/ảnh. Cả hai xử lý ảnh phụ và tính loss; đối chứng hệ số 0, can thiệp hệ số 1 cố định, không dò lưới.',
        '- Loss tổng: `CE(main) + lambda * sum(negative_loss) / số ảnh main của batch`. Negative forward ở `eval()` nhưng vẫn có gradient: không cập nhật BatchNorm/dropout; main ở `train()`. Hash luồng main x/y và luồng negative augmentation khớp cả ba epoch.',
        '- Không thừa kế weights của pilot PAD trước vì audit chung có thể đổi thành phần; cả hai bắt đầu từ checkpoint cũ. Precision FP32 là thay đổi kỹ thuật ở cả hai nhánh, không thay hệ số/epoch/tiêu chí.',
        '- Giữ gộp 75% reference B0/ConvNeXt +25% ResNet. Chọn qua guard original/DermaCon/PAD validation đã khóa; reference dự phòng. Khóa trước inference held-role. Không chỉnh lại trọng số bằng test.','',
        f"Qua ba epoch: 606 lượt cancer tương ứng **{exposure['positive_unique_images']} ảnh/{exposure['positive_unique_patients']} bệnh nhân**; 606 lượt NEV/SEK tương ứng **{exposure['negative_unique_images']} ảnh/{exposure['negative_unique_patients']} bệnh nhân**. Đây là lượt rút có lặp, không phải 1.212 ảnh mới.",'',
        '## ResNet riêng và ensemble trên tám bệnh','',
        '| Tập | Ảnh | Accuracy ResNet đối chứng | ResNet loss phụ | Accuracy gộp đối chứng | Gộp loss phụ |','|---|---:|---:|---:|---:|---:|']
    titles=dict(original_validation='Original validation',dermacon_validation='DermaCon validation',original_outer='Original outer fold 0',dermacon_official_test='DermaCon official test',skindisnet_transfer='SkinDisNet transfer')
    for split in e.previous.prior.SPLITS:
        rr=r['results'][split]
        lines.append(f"| {titles[split]} | {len(p['splits'][split]):,} | "+' | '.join(pct(rr[n]['accuracy']) for n in ('control_resnet','negative_resnet','control_mix25','negative_mix25'))+' |')
    lines += ['', '| Tập | Macro F1 ResNet đối chứng | ResNet loss phụ | Macro F1 gộp đối chứng | Gộp loss phụ |','|---|---:|---:|---:|---:|']
    for split in e.previous.prior.SPLITS:
        rr=r['results'][split]; present=sum(m['support']>0 for m in rr['control_resnet']['per_class'].values())
        lines.append(f"| {titles[split]} | "+' | '.join(pct(rr[n]['macro_f1']*8/present) for n in ('control_resnet','negative_resnet','control_mix25','negative_mix25'))+' |')
    lines += ['', 'Macro F1 ở bảng lấy trên lớp có mẫu: tám ở original/DermaCon validation, bảy ở DermaCon test, hai ở SkinDisNet. Mọi model vẫn dự đoán tám lớp; JSON có Macro F1 đủ tám lớp và confusion matrix.','',
        '## PAD validation: nhận cancer và gắn cờ nhóm khác','',
        '| Nhãn | Ảnh | Reference gắn cờ SkinCancer | ResNet đối chứng | ResNet loss phụ | Gộp đối chứng | Gộp loss phụ |','|---|---:|---:|---:|---:|---:|---:|']
    for d in ('BCC','SCC','MEL','NEV','SEK','ACK'):
        count=r['pad_validation']['old_classwise']['by_diagnosis'][d]['images']
        lines.append(f'| {d} | {count} | '+' | '.join(str(r['pad_validation'][n]['by_diagnosis'][d]['flagged']) for n in ('old_classwise','control_resnet','negative_resnet','control_mix25','negative_mix25'))+' |')
    for names,title in [(('control_resnet','negative_resnet'),'ResNet'),(('control_mix25','negative_mix25'),'Bản gộp')]:
        a,b=[r['pad_validation'][n] for n in names]; ca=sum(a['by_diagnosis'][d]['flagged'] for d in ('BCC','SCC','MEL')); cb=sum(b['by_diagnosis'][d]['flagged'] for d in ('BCC','SCC','MEL'))
        na=sum(a['by_diagnosis'][d]['flagged'] for d in ('NEV','SEK')); nb=sum(b['by_diagnosis'][d]['flagged'] for d in ('NEV','SEK'))
        lines += ['',f"{title}: cancer đúng {ca}/198 → {cb}/198; gắn cờ NEV/SEK **{na}/100 → {nb}/100**; gắn cờ ACK/NEV/SEK cộng lại {a['non_cancer_flagged']}/249 → {b['non_cancer_flagged']}/249."]
    lines += ['', 'PAD không có nhãn tám lớp cho NEV/SEK/ACK, không báo Accuracy tám lớp. PAD validation đã được khảo sát/chọn model trước và chỉ có bảy melanoma; kết quả không xác nhận độ nhạy lâm sàng ổn định. ACK được báo riêng theo nhãn nguồn.','',
        '## Giữ các bệnh cũ','',
        '| Original outer | Recall ResNet đối chứng | ResNet loss phụ | Recall gộp đối chứng | Gộp loss phụ |','|---|---:|---:|---:|---:|']
    rr=r['results']['original_outer']
    for c in CLASSES: lines.append(f'| {c} | '+' | '.join(pct(rr[n]['per_class'][c]['recall']) for n in ('control_resnet','negative_resnet','control_mix25','negative_mix25'))+' |')
    lines += ['', '## Quyết định theo validation','',f"**Chọn `{lock['selected']}` theo giao thức.**",'']
    for n in ('control_mix25','negative_mix25'): lines.append(f"- `{n}`: "+('; '.join(reasons[n]) if reasons[n] else 'qua các guard đã khóa')+'.')
    lines += ['', 'Chênh lệch Accuracy gộp loss phụ − gộp đối chứng, CI95% bootstrap theo nhóm ca/cảnh; phân tích thăm dò một seed, không điều chỉnh nhiều so sánh hoặc bất định chọn model:','']
    for split,comparisons in intervals.items():
        low,high=comparisons['mix25']['accuracy_delta_ci95']; delta=r['results'][split]['negative_mix25']['accuracy']-r['results'][split]['control_mix25']['accuracy']
        lines.append(f'- {titles[split]}: {100*delta:+.2f} điểm %; CI95% [{100*low:+.2f}; {100*high:+.2f}].')
    lines += ['', 'Mốc tổng 5.937 ảnh giữ nguyên: reference chính **78,07% Accuracy / 76,82% Macro F1**, công thức thử trước **79,06% / 77,98%** chưa qua guard. Pilot này chưa mở rộng năm fold và không đổi checkpoint ứng dụng. 353 ảnh phụ NEV/SEK không có nhãn tám lớp, không được cộng thành 353 mẫu mới của benchmark tám bệnh.','',
        '## Kiểm chứng và tệp','',
        'PASS: audit/nguồn/code/checkpoint SHA; vai trò/nhóm bệnh nhân; sampler main/negative độc lập; cùng luồng augmentation, cùng759cập nhật; loss và gradient tính lại bằng NumPy; BatchNorm giữ nguyên và gradient thật qua negative forward; Accuracy/Precision/Recall/F1/confusion/fusion/PAD subtype flags; guard/rank; khóa trước held-role; inference thật cùng batch16.','',
        '- [Audit chung](../ai-service/reports/original_eight_pad_joint_audit_20261014/summary.json), [PASS audit](../ai-service/reports/original_eight_pad_joint_audit_20261014/verification.json), [ảnh nhãn phụ](../ai-service/reports/original_eight_pad_joint_audit_20261014/negative_train.jsonl).',
        '- [Giao thức FP32](../ai-service/reports/original_eight_negative_supervision_pilot_fold0_seed42_fp32/protocol.json), [sửa số học](../ai-service/reports/original_eight_negative_supervision_pilot_fold0_seed42_fp32/numerical_repair.json), [gate AMP chưa đạt](../ai-service/reports/original_eight_negative_supervision_pilot_fold0_seed42/implementation_gate.json).',
        '- [Chỉ số/confusion từng bệnh](../ai-service/reports/original_eight_negative_supervision_pilot_fold0_seed42_fp32/results.json), [lựa chọn](../ai-service/reports/original_eight_negative_supervision_pilot_fold0_seed42_fp32/selection_locked.json), [lý do guard](../ai-service/reports/original_eight_negative_supervision_pilot_fold0_seed42_fp32/decision_reasons.json), [bootstrap](../ai-service/reports/original_eight_negative_supervision_pilot_fold0_seed42_fp32/paired_comparisons.json).',
        '- [PASS pilot](../ai-service/reports/original_eight_negative_supervision_pilot_fold0_seed42_fp32/verification.json), [mã FP32](../ai-service/training/pilot_original_eight_negative_supervision_fp32.py), [kiểm chứng FP32](../ai-service/training/verify_original_eight_negative_supervision_fp32.py).','']
    doc=root/'docs/83-pilot-nhan-phu-khong-skincancer.md'; doc.write_text('\n'.join(lines),encoding='utf-8')
    report='\n'.join(lines).replace('../ai-service/training/','../../training/').replace('../ai-service/reports/original_eight_negative_supervision_pilot_fold0_seed42_fp32/','').replace('../ai-service/reports/original_eight_negative_supervision_pilot_fold0_seed42/','../original_eight_negative_supervision_pilot_fold0_seed42/').replace('../ai-service/reports/original_eight_pad_joint_audit_20261014/','../original_eight_pad_joint_audit_20261014/').replace('(82-pilot-bo-sung-pad-skincancer-co-doi-chung.md)','(../../../docs/82-pilot-bo-sung-pad-skincancer-co-doi-chung.md)')
    (out/'summary.md').write_text(report,encoding='utf-8')
    statepath=root/'ai-service/reports/active_research_track.json'; state=e.read(statepath)
    assert sha256_file(root/state['serving_checkpoint'])==state['serving_checkpoint_sha256'] and sha256_file(root/state['benchmark']['report_path'])==state['benchmark']['report_sha256']
    if state['latest_completed_experiment']['name']!=out.name:
        history=state.setdefault('completed_experiment_history',[])
        for key in ('previous_completed_experiment','latest_completed_experiment'):
            if state.get(key) and all(x['name']!=state[key]['name'] for x in history): history.append(state[key])
        state['previous_completed_experiment']=state['latest_completed_experiment']
    state['latest_completed_experiment']=dict(name=out.name,verification='PASS',architecture='resnet50',epochs_each=3,precision='float32',
        actual_updates=v['actual_updates'],negative_coefficient=1,selected_method=lock['selected'],positive_images=len(p['pad']),negative_images=len(p['negative']),
        exposure=exposure,main_negative_streams_match=True,results_sha256=v['results_sha256'],
        results={s:{n:{k:m[k] for k in ('accuracy','macro_f1')} for n,m in rr.items()} for s,rr in r['results'].items()},pad_validation=r['pad_validation'],scope=r['scope'],
        report_path=doc.relative_to(root).as_posix(),verification_path=(out/'verification.json').relative_to(root).as_posix())
    state['latest_pilot']=dict(name=out.name,status='complete_verified',protocol_path=(out/'protocol.json').relative_to(root).as_posix())
    state['latest_joint_pad_preparation']=dict(name=e.joint.OUT.name,verification='PASS',positive_images=s['positive_images'],negative_images=s['negative_images'],negative_patients=s['negative_patients'],
        ack_audit_only_images=s['by_diagnosis']['ACK']['images'],protected_images=17201,report_path=(e.joint.OUT/'summary.json').relative_to(root).as_posix())
    state['numerical_repair']=dict(preliminary_name='original_eight_negative_supervision_pilot_fold0_seed42',preliminary_actual_updates=repair['actual_preliminary_updates'],
        status='FP32primary_repair_complete_verified',outcomes_used_for_repair=False)
    state['next_experiment']=None; state['next_experiment_status']='last_pilot_complete_verified'; state['updated_on']='2026-10-14'
    state['next_step']='Review registered loss effect on train/validation for cancer sensitivity, false positives and weak-original-class retention. Expand only a guarded passing configuration; if no pass, preserve reference and diagnose tradeoffs before another preregistered intervention. No coefficient/fusion search on viewed held-role scores or serving change.'
    save_json(statepath,state)
    print(json.dumps(dict(report=str(doc),selected=lock['selected'],exposure=exposure,benchmark_and_serving_unchanged=True)))


if __name__=='__main__': main()
