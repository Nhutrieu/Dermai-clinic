"""Verify matched ensemble teacher, frozen state, inputs and validation choice."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from common import CLASSES,ImageSampleDataset,evaluation_transform,save_json,sha256_file
import pilot_original_eight_ensemble_teacher as pilot
from summarize_original_eight_resnet50 import independently_score
from summarize_original_eight_resnet50_cv import paired_bootstrap

ROOT,OUT,MODELS=pilot.ROOT,pilot.OUT,pilot.MODELS


def present_f1(m):return float(np.mean([v['f1'] for v in m['per_class'].values() if v['support']]))


def verify():
    p=pilot.read(OUT/'protocol.json');r=pilot.read(OUT/'results.json');lock=pilot.read(OUT/'selection_locked.json');pred=pilot.read(OUT/'predictions.json')
    assert p['classes']==CLASSES and p['configuration']==pilot.CONFIG
    assert r['protocol_sha256']==lock['protocol_sha256']==sha256_file(OUT/'protocol.json') and r['selection_sha256']==sha256_file(OUT/'selection_locked.json')
    for name,h in p['sources'].items():assert sha256_file(ROOT/name)==h
    for name,h in p['code_sha256'].items():assert sha256_file(ROOT/'ai-service/training'/name)==h
    prior=pilot.read(pilot.PRIOR/'protocol.json')
    for role in ('train','supplement','splits'):assert p[role]==prior[role]
    for rr in [p['train'],p['supplement'],*p['splits'].values()]:
        for row in rr:assert sha256_file(ROOT/row['path'])==row['sha256']
    reports={};histories={};counts=np.bincount([CLASSES.index(q['label']) for q in p['train']],minlength=8)
    ww=(1-.999)/np.maximum(1-np.power(.999,counts),1e-12);ww/=ww.mean()
    for b in pilot.BRANCHES:
        directory=MODELS/b;report=pilot.read(directory/'training_report.json');history=pilot.read(directory/'history.json');reports[b]=report;histories[b]=history
        assert report['configuration']==p['configuration'] and report['coefficient']==p['configuration']['distillation_weights'][b]
        assert report['protocol_sha256']==sha256_file(OUT/'protocol.json') and report['initial_checkpoint_sha256']==p['initial_checkpoint_sha256']
        assert report['checkpoint_sha256']==lock['checkpoint_sha256'][b]==sha256_file(directory/'final_model.pth')
        assert report['teacher_state_before']==report['teacher_state_after'] and report['teacher_frozen']
        assert report['class_counts']==counts.tolist() and np.array_equal(np.asarray(report['class_weights']),ww.astype(np.float32).astype(float))
        assert report['epochs']==3 and [h['epoch'] for h in history]==[1,2,3] and report['attempted_updates']==759
        rr=p['train']+p['supplement']
        for h in history:
            weights=torch.tensor([.9/4043]*4043+[.1/807]*807,dtype=torch.float64)
            ids=torch.multinomial(weights,4043,replacement=True,generator=torch.Generator().manual_seed(42+h['epoch'])).tolist()
            assert h['sample_indices_sha256']==hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()
            assert h['source_draws']==dict(Counter(rr[j].get('source','original') for j in ids)) and h['teacher_images']==h['source_draws']['original']
            assert h['attempted_updates']==253 and 0<h['actual_updates']<=253
            assert all(math.isfinite(h[k]) for k in ('loss','cross_entropy','distillation')) and h['distillation']>=-1e-6
            assert abs(h['loss']-(h['cross_entropy']+report['coefficient']*h['distillation']))<1e-6
            assert len(h['augmentation_stream_sha256'])==64
        assert report['actual_updates']==sum(h['actual_updates'] for h in history)
        cp=torch.load(directory/'final_model.pth',map_location='cpu',weights_only=False)
        assert cp['architecture']=='resnet50' and cp['classes']==CLASSES and cp['epoch']==3 and cp['branch']==b and cp['protocol_sha256']==sha256_file(OUT/'protocol.json') and cp['initial_checkpoint_sha256']==p['initial_checkpoint_sha256'];del cp
    assert reports['control']['teacher_state_before']==reports['distill']['teacher_state_before']
    assert reports['control']['class_weights']==reports['distill']['class_weights']
    for a,b in zip(histories['control'],histories['distill']):
        for k in ('epoch','sample_indices_sha256','source_draws','teacher_images','augmentation_stream_sha256','attempted_updates'):assert a[k]==b[k]
    # Test actual teacher mixture/temperature math against float64 numpy on images.
    torch.set_num_threads(4);teachers=[pilot.load_teacher(m) for m in p['teachers']]
    assert [pilot.tensor_state_hash(m) for m in teachers]==reports['control']['teacher_state_before']
    dataset=ImageSampleDataset(pilot.previous.samples(p['splits']['original_validation'][:16]),evaluation_transform())
    x=torch.stack([dataset[i][0] for i in range(16)]).cuda()
    weights=torch.tensor(p['teacher_classwise_weights'],device='cuda',dtype=torch.float32)
    actual=pilot.teacher_target(teachers,x,weights,2.).cpu().numpy()
    with torch.no_grad(): parents=[m(x).softmax(1).cpu().numpy().astype(float) for m in teachers]
    w=np.asarray(p['teacher_classwise_weights']);q=(1-w)*parents[0]+w*parents[1];q/=q.sum(1,keepdims=True);q=np.maximum(q,1e-12)**.5;q/=q.sum(1,keepdims=True)
    assert np.allclose(actual,q,atol=1e-6,rtol=0)
    del teachers,x;torch.cuda.empty_cache()
    trials={n:dict(name=n) for n in ('old_classwise','control_mix25','distill_mix25')};all_values={};expected=[]
    for name in pilot.previous.SPLITS:
        rr=p['splits'][name];yy=np.asarray([CLASSES.index(q['label']) for q in rr]);base=pilot.previous.baseline(name,rr)
        with np.load(OUT/f'{name}.npz') as data:
            assert data['paths'].tolist()==[q['path'] for q in rr] and np.array_equal(data['truth'],yy)
            values={k:data[k] for k in data.files if k not in ('paths','truth')}
        assert np.array_equal(values['old_classwise'],base['old_classwise']) and np.array_equal(values['baseline_resnet'],base['resnet50'])
        for prefix in ('baseline','control','distill'):
            fused=.75*values['old_classwise']+.25*values[prefix+'_resnet'];fused/=fused.sum(1,keepdims=True)
            assert np.array_equal(values[prefix+'_mix25'],fused)
        if name in pilot.previous.SPLITS[:2]:
            assert (OUT/f'{name}.npz').stat().st_mtime_ns<(OUT/'selection_locked.json').stat().st_mtime_ns
            for k,t in trials.items():t[name]=independently_score(yy,values[k])
        else:assert (OUT/'selection_locked.json').stat().st_mtime_ns<(OUT/f'{name}.npz').stat().st_mtime_ns
        values['validation_selected']=values[lock['selected']];assert set(values)==set(pilot.METHODS)
        for k,a in values.items():assert independently_score(yy,a)==r['results'][name][k]
        expected.extend(dict(**row,split=name,probabilities={k:a[j].tolist() for k,a in values.items()}) for j,row in enumerate(rr));all_values[name]=values
    assert pred==expected
    for t in trials.values():t['eligible']=bool(pilot.previous.eligible(t,trials['old_classwise']))
    assert list(trials.values())==lock['trials'] and sorted([t for t in trials.values() if t['eligible']],key=pilot.previous.rank)[0]['name']==lock['selected']==r['selected']
    for b in pilot.BRANCHES:assert np.allclose(pilot.infer(b,p['splits']['original_validation'][:16]),all_values['original_validation'][b+'_resnet'][:16],atol=1e-6,rtol=0)
    state=pilot.read(ROOT/'ai-service/reports/active_research_track.json');assert state['active_track']=='original_eight' and state['classes']==CLASSES
    assert sha256_file(ROOT/state['benchmark']['report_path'])==state['benchmark']['report_sha256'] and sha256_file(ROOT/state['serving_checkpoint'])==state['serving_checkpoint_sha256']
    return p,r,reports,all_values


def main():
    p,r,reports,values=verify();comparisons={}
    for name,pp in values.items():
        comparisons[name]={}
        for a,b in [('distill_resnet','control_resnet'),('distill_mix25','control_mix25'),('validation_selected','old_classwise')]:
            ci=paired_bootstrap(p['splits'][name],pp[a],pp[b]);ci.update(accuracy_delta=r['results'][name][a]['accuracy']-r['results'][name][b]['accuracy'],macro_f1_8_delta=r['results'][name][a]['macro_f1']-r['results'][name][b]['macro_f1'])
            comparisons[name][a+'_vs_'+b]=ci
    save_json(OUT/'paired_comparisons.json',comparisons)
    save_json(OUT/'verification.json',dict(status='PASS',verifier_code_sha256=sha256_file(Path(__file__)),protocol_sha256=sha256_file(OUT/'protocol.json'),result_sha256=sha256_file(OUT/'results.json'),prediction_sha256=sha256_file(OUT/'predictions.json'),comparisons_sha256=sha256_file(OUT/'paired_comparisons.json'),selected=r['selected'],actual_updates={b:v['actual_updates'] for b,v in reports.items()},
        checks=['Source/code/init/final checkpoint hashes; old-eight original roles unchanged','Same807supplemented pool and4043draws per epoch',
            'Independent sampler/source-count reconstruction; entire augmentation stream hashes match','Both compute teacher; only coefficient differs0/.5',
            'Teacher image count equals old-image count; frozen teacher states match checkpoints and remain unchanged','Actual teacher probability mixture andT2softening match float64 independent calculation',
            'Equal fixed3epoch attempted updates and loss-weight reconstruction','All fusions, NumPy metrics and row identities reconstructed',
            'Dual validation guard/ranking; lock before new held-role prediction','Actual student checkpoint first-batch inference matches artifact','Full5fold benchmark and serving unchanged']))
    lines=['# Pilot ensemble teacher giữ kiến thức bộ cũ','', '**Hoàn tất; kiểm chứng PASS. Một fold, dữ liệu phát triển đã được khảo sát.**','',
        'Hai ResNet cùng checkpoint khởi đầu,3epoch,90%ảnh cũ/10%807ảnh phụ, cùng optimizer/class weights và cùng toàn bộ luồng augmentation. Cả hai tính teacher B0/ConvNeXt cố định; chỉ hệ số KL khác0/.5. Teacher dùng cùng ảnh đã tăng cường, chỉ trên train cũ; không hướng dẫn trên ảnh phụ.',
        'Teacher ghép xác suất bằng trọng số từng bệnh cũ, chuẩn hóa rồi làm mềmq^(1/T) tạiT2; loss là CE+lambda*T²*KL(q_T||student_T). Đây là biến thể của đồ án, không tái lập nguyên bản [Hinton và cộng sự](https://arxiv.org/abs/1503.02531) hay [Learning without Forgetting](https://arxiv.org/abs/1606.09282).',
        '',f"Phương án được hai validation chọn: `{r['selected']}`. Guard và ranking giữ nguyên pilot bổ sung trước; không đổi công thức25%ResNet theo held-role.",'']
    for name in pilot.previous.SPLITS:
        mm=r['results'][name];lines+=[f'## {name}','',f"{len(p['splits'][name])} ảnh.",'',
            '| Phương án | Accuracy | Macro F1, 8 lớp | Macro F1, lớp có mẫu | Recall Lupus | Recall Psoriasis | Recall SkinCancer |',
            '|---|---:|---:|---:|---:|---:|---:|']
        for k in pilot.METHODS:
            m=mm[k];recalls=[f"{m['per_class'][c]['recall']:.2%}" if m['per_class'][c]['support'] else '—' for c in ('Lupus','Psoriasis','SkinCancer')]
            lines.append(f"| {k} | {m['accuracy']:.2%} | {m['macro_f1']:.2%} | {present_f1(m):.2%} | "+' | '.join(recalls)+' |')
        for k in ('distill_resnet_vs_control_resnet','distill_mix25_vs_control_mix25'):
            ci=comparisons[name][k];ac=ci['accuracy_delta_ci95'];fc=ci['macro_f1_delta_ci95']
            lines+=['',f"{k}: ΔAccuracy{ci['accuracy_delta']*100:+.2f} điểm %, CI95%[{ac[0]*100:+.2f};{ac[1]*100:+.2f}]; ΔMacroF1(8lớp){ci['macro_f1_8_delta']*100:+.2f}, CI95%[{fc[0]*100:+.2f};{fc[1]*100:+.2f}]."]
    lines+=['','## Bằng chứng và giới hạn','',f"Cập nhật thật: control{reports['control']['actual_updates']}/759; distill{reports['distill']['actual_updates']}/759. Hash toàn bộ đầu vào đã augmentation, sampler và teacher-state được đối chiếu; teacher không cập nhật.",
        '- Một fold, một seed; bootstrap2000lần là thăm dò trên dự đoán đã có, không hiệu chỉnh nhiều so sánh hay phản ánh đầy đủ bất định khi train lại.',
        '- Official DermaCon test183không có Lupus và chỉ6ảnh SkinCancer; SkinDisNet chỉEczema/Tinea. MacroF1lớp có mẫu không biến model thành classifier2lớp.',
        '- Giữ590DermaContrain riêng; không gọi toàn bộ986ảnh là holdout sau thích nghi. Các nguồn/OOFđã được xem trước, không phải test mới độc lập.',
        '- Giữ mốc5937OOF và checkpoint ứng dụng. Không chọn trọng số bằng điểm held-role thuận lợi.',
        '', '[Giao thức](protocol.json), [lựa chọn](selection_locked.json), [mọi chỉ số/từng bệnh/confusion](results.json), [bootstrap](paired_comparisons.json), [kiểm chứng](verification.json), [log](run.log).','']
    (OUT/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    for name in ('original_outer','dermacon_official_test'):
        cm=np.asarray(r['results'][name]['validation_selected']['confusion_matrix']);fig,ax=plt.subplots(figsize=(11,9));im=ax.imshow(cm,cmap='Blues');fig.colorbar(im,ax=ax)
        ax.set(xticks=range(8),yticks=range(8),xticklabels=CLASSES,yticklabels=CLASSES,xlabel='Predicted',ylabel='Recorded label',title=f'Ensemble teacher pilot: {name} - {r["selected"]}');plt.setp(ax.get_xticklabels(),rotation=40,ha='right')
        for i in range(8):
            for j in range(8):ax.text(j,i,str(cm[i,j]),ha='center',va='center',color='white' if cm[i,j]>cm.max()/2 else 'black')
        fig.tight_layout();fig.savefig(OUT/f'{name}_selected_confusion.png',dpi=160);plt.close(fig)
    print(json.dumps(dict(verification='PASS',selected=r['selected'],updates={b:v['actual_updates'] for b,v in reports.items()},results={name:{k:{f:r['results'][name][k][f] for f in ('accuracy','macro_f1')} for k in ('old_classwise','control_mix25','distill_mix25')} for name in pilot.previous.SPLITS})),flush=True)


if __name__=='__main__':main()
