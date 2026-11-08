"""Verify matched source-data pilot, frozen checkpoint and validation choice."""
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

from common import CLASSES,save_json,sha256_file
import pilot_original_eight_supplement_adaptation as pilot
from summarize_original_eight_resnet50 import independently_score
from summarize_original_eight_resnet50_cv import paired_bootstrap

ROOT,OUT,MODELS=pilot.ROOT,pilot.OUT,pilot.MODELS


def present_f1(m): return float(np.mean([r['f1'] for r in m['per_class'].values() if r['support']]))


def verify():
    p=pilot.read(OUT/'protocol.json'); d=pilot.read(OUT/'results.json'); lock=pilot.read(OUT/'selection_locked.json'); predictions=pilot.read(OUT/'predictions.json')
    assert p['classes']==CLASSES and p['configuration']==pilot.CONFIG
    assert d['protocol_sha256']==lock['protocol_sha256']==sha256_file(OUT/'protocol.json') and d['selection_sha256']==sha256_file(OUT/'selection_locked.json')
    for name,h in p['sources'].items(): assert sha256_file(ROOT/name)==h
    for name,h in p['code_sha256'].items(): assert sha256_file(ROOT/'ai-service/training'/name)==h
    train_paths={r['path'] for r in p['train']+p['supplement']}; train_sha={r['sha256'] for r in p['train']+p['supplement']}
    assert len(p['train'])==4043 and len(p['supplement'])==807
    original_roles=pilot.read(pilot.BASE/'protocol.json')['roles']
    assert [r['path'] for r in p['train']]==original_roles['train']
    assert [r['path'] for r in p['splits']['original_validation']]==original_roles['inner_validation']
    assert [r['path'] for r in p['splits']['original_outer']]==sorted(original_roles['outer_holdout'])
    manifests={r['path']:r for r in pilot.read(pilot.OUTER)['images']}
    for r in p['train']+p['splits']['original_validation']+p['splits']['original_outer']:
        expected=manifests[r['path']]
        assert (r['label'],r['sha256'],r['group'])==(expected['class'],expected['sha256'],expected['scene_or_case_group'])
    for rr in [p['train'],p['supplement'],*p['splits'].values()]:
        for r in rr: assert sha256_file(ROOT/r['path'])==r['sha256'] and r['label'] in CLASSES
    for name,rr in p['splits'].items():
        assert len({r['path'] for r in rr})==len(rr) and train_paths.isdisjoint(r['path'] for r in rr) and train_sha.isdisjoint(r['sha256'] for r in rr)
    derma_train={r['path']:r for r in p['supplement'] if r['source']=='DermaCon-IN-v1'}
    original_supplement=[json.loads(line) for line in (pilot.SUP/'training_candidates.jsonl').read_text(encoding='utf-8').splitlines()]
    assert {r['path'] for r in p['supplement']}=={r['path'] for r in original_supplement}
    derma_cases={r['source_case_id'] for r in original_supplement if r['source']=='DermaCon-IN-v1'}
    for name in ('dermacon_validation','dermacon_official_test'): assert derma_cases.isdisjoint(r['group'] for r in p['splits'][name])
    class_counts=np.bincount([CLASSES.index(r['label']) for r in p['train']],minlength=8)
    w=(1-.999)/np.maximum(1-np.power(.999,class_counts),1e-12); w/=w.mean(); reports={}
    for branch in ('control','supplement'):
        directory=MODELS/branch; report=pilot.read(directory/'training_report.json'); history=pilot.read(directory/'history.json')
        assert report['configuration']==p['configuration'] and report['protocol_sha256']==sha256_file(OUT/'protocol.json')
        assert report['initial_checkpoint_sha256']==p['initial_checkpoint_sha256']==sha256_file(pilot.INITIAL)
        assert report['checkpoint_sha256']==lock['checkpoint_sha256'][branch]==sha256_file(directory/'final_model.pth')
        assert report['class_counts']==class_counts.tolist() and np.array_equal(np.asarray(report['class_weights']),w.astype(np.float32).astype(float))
        assert [h['epoch'] for h in history]==[1,2,3] and report['epochs']==3 and report['attempted_updates']==759
        rr=p['train']+(p['supplement'] if branch=='supplement' else [])
        for h in history:
            # Independent sampler weight reconstruction (no runner draws helper).
            probs=[1/4043]*4043 if branch=='control' else [.9/4043]*4043+[.1/807]*807
            indices=torch.multinomial(torch.tensor(probs,dtype=torch.float64),4043,replacement=True,
                generator=torch.Generator().manual_seed(42+h['epoch'])).tolist()
            assert hashlib.sha256(json.dumps(indices,separators=(',',':')).encode()).hexdigest()==h['sample_indices_sha256']
            assert dict(Counter(rr[j].get('source','original') for j in indices))==h['source_draws']
            assert h['attempted_updates']==253 and 0<h['actual_updates']<=253 and math.isfinite(h['train']['loss'])
        assert report['actual_updates']==sum(h['actual_updates'] for h in history)
        cp=torch.load(directory/'final_model.pth',map_location='cpu',weights_only=False)
        assert cp['architecture']=='resnet50' and cp['classes']==CLASSES and cp['epoch']==3 and cp['branch']==branch and cp['protocol_sha256']==sha256_file(OUT/'protocol.json') and cp['initial_checkpoint_sha256']==p['initial_checkpoint_sha256']; del cp
        reports[branch]=report
    assert reports['control']['class_weights']==reports['supplement']['class_weights']
    trials={n:dict(name=n) for n in ('old_classwise','control_mix25','supplement_mix25')}; bysplit={}; expected=[]
    for name in pilot.SPLITS:
        rr=p['splits'][name]; y=np.asarray([CLASSES.index(r['label']) for r in rr]); baseline=pilot.baseline(name,rr)
        with np.load(OUT/f'{name}.npz') as data:
            assert data['paths'].tolist()==[r['path'] for r in rr] and np.array_equal(data['truth'],y)
            values={k:data[k] for k in data.files if k not in ('paths','truth')}
        assert np.array_equal(values['old_classwise'],baseline['old_classwise']) and np.array_equal(values['baseline_resnet'],baseline['resnet50'])
        for prefix in ('baseline','control','supplement'):
            a=values[prefix+'_resnet']; blended=.75*values['old_classwise']+.25*a; blended/=blended.sum(1,keepdims=True)
            assert np.array_equal(values[prefix+'_mix25'],blended)
        if name in pilot.SPLITS[:2]:
            assert (OUT/f'{name}.npz').stat().st_mtime_ns<(OUT/'selection_locked.json').stat().st_mtime_ns
            for k,t in trials.items(): t[name]=independently_score(y,values[k])
        else: assert (OUT/'selection_locked.json').stat().st_mtime_ns<(OUT/f'{name}.npz').stat().st_mtime_ns
        values['validation_selected']=values[lock['selected']]
        assert set(values)==set(pilot.METHODS)
        for k,a in values.items(): assert independently_score(y,a)==d['results'][name][k]
        expected.extend(dict(**r,split=name,probabilities={k:a[j].tolist() for k,a in values.items()}) for j,r in enumerate(rr))
        bysplit[name]=values
    assert predictions==expected
    for t in trials.values(): t['eligible']=bool(pilot.eligible(t,trials['old_classwise']))
    assert list(trials.values())==lock['trials'] and sorted([t for t in trials.values() if t['eligible']],key=pilot.rank)[0]['name']==lock['selected']==d['selected']
    # Spot-check actual saved models against the first full evaluation batch.
    torch.set_num_threads(4)
    for branch in ('control','supplement'):
        fresh=pilot.infer(branch,p['splits']['original_validation'][:16])
        assert np.allclose(fresh,bysplit['original_validation'][branch+'_resnet'][:16],atol=1e-6,rtol=0)
    state=pilot.read(ROOT/'ai-service/reports/active_research_track.json')
    assert state['active_track']=='original_eight' and state['classes']==CLASSES
    assert sha256_file(ROOT/state['benchmark']['report_path'])==state['benchmark']['report_sha256'] and sha256_file(ROOT/state['serving_checkpoint'])==state['serving_checkpoint_sha256']
    return p,d,bysplit,reports


def main():
    p,d,values,reports=verify(); comparisons={}
    for name,pp in values.items():
        rr=p['splits'][name]; comparisons[name]={}
        for a,b in [('supplement_resnet','control_resnet'),('supplement_mix25','control_mix25'),('validation_selected','old_classwise')]:
            ci=paired_bootstrap(rr,pp[a],pp[b]); ci['scope']='Previously inspected exploratory pilot, one seed; conditional paired case/scene uncertainty, not independent confirmation.'
            ci['accuracy_delta']=d['results'][name][a]['accuracy']-d['results'][name][b]['accuracy']
            ci['macro_f1_8_delta']=d['results'][name][a]['macro_f1']-d['results'][name][b]['macro_f1']
            comparisons[name][a+'_vs_'+b]=ci
    save_json(OUT/'paired_comparisons.json',comparisons)
    save_json(OUT/'verification.json',dict(status='PASS',verifier_code_sha256=sha256_file(Path(__file__)),protocol_sha256=sha256_file(OUT/'protocol.json'),
        result_sha256=sha256_file(OUT/'results.json'),prediction_sha256=sha256_file(OUT/'predictions.json'),comparisons_sha256=sha256_file(OUT/'paired_comparisons.json'),
        actual_optimizer_updates={b:r['actual_updates'] for b,r in reports.items()},selected=d['selected'],
        checks=['Source/code/initial and final checkpoint hashes','Original4043/718/1176roles plus807supplement and protected clinical case roles',
                'Equal fixed-three-epoch attempted update budget; actual optimizer updates/AMP skips accounted',
                'Same original loss weights; deterministic independent sampler/source counts reconstruction',
                'Published original classwise reference and unchanged initial probabilities reconstructed',
                'All fixed probability fusions and metrics independently reconstructed','Dual validation guard/ranking reconstructed; lock before new held-role artifact',
                'Actual checkpoint inference matches first full original-validation batch','Original fullOOFbenchmark and serving checkpoint unchanged']))
    lines=['# Pilot bổ sung ảnh cho ResNet bộ cũ','',
        '**Hoàn tất, kiểm chứng PASS. Pilot một fold, đánh giá phát triển đã được khảo sát.**','',
        'Hai nhánh bắt đầu từ cùng checkpoint ResNet fold0 raw epoch17; cùng seed42, ba epoch,4043lượt rút ảnh/epoch, batch16, weighted CE tính từ4043ảnh train cũ, augmentation cũ. Control chỉ replay ảnh cũ; supplement rút90%khối xác suất cũ và10%807ảnh train phụ. Dùng checkpoint epoch3 cố định, không chọn epoch theo test.',
        '',f"Phương án ensemble chọn bằng hai validation: `{d['selected']}`. Chỉ so old reference/control25%/supplement25%; guard giữ original validation theo pilot cũ và clinical validation MacroF1/SkinCancer recall/meanRecallCandida-Lupus-Tinea không giảm.",'',
        'Không so điểm một fold với78,07%/76,82%hoặc79,06%/77,98%trên toàn bộ5937OOF. DermaCon đã dùng590ảnh train nên chỉ chấm các vai trò còn giữ riêng; nguồn này đã xem trước, không phải xác nhận mới độc lập.','']
    for name in pilot.SPLITS:
        m=d['results'][name]; lines += [f'## {name}', '', f"{len(p['splits'][name])} ảnh.",'',
            '| Phương án | Accuracy | Macro F1, 8 lớp | Macro F1, lớp có mẫu | Recall Lupus | Recall Candidiasis | Recall Tinea | Recall SkinCancer |',
            '|---|---:|---:|---:|---:|---:|---:|---:|']
        for k in pilot.METHODS:
            a=m[k]; rc=[f"{a['per_class'][c]['recall']:.2%}" if a['per_class'][c]['support'] else '—' for c in ('Lupus','Candidiasis','Tinea','SkinCancer')]
            lines.append(f"| {k} | {a['accuracy']:.2%} | {a['macro_f1']:.2%} | {present_f1(a):.2%} | "+' | '.join(rc)+' |')
        lines += ['','### Tác động thêm dữ liệu: supplement − control','',
            '| Phương án | Δ Accuracy | CI95% | Δ Macro F1, 8 lớp | CI95% |','|---|---:|---|---:|---|']
        for k in ('supplement_resnet_vs_control_resnet','supplement_mix25_vs_control_mix25'):
            q=comparisons[name][k]; ac=q['accuracy_delta_ci95']; fc=q['macro_f1_delta_ci95']
            lines.append(f"| {k} | {q['accuracy_delta']*100:+.2f} | [{ac[0]*100:+.2f}; {ac[1]*100:+.2f}] | {q['macro_f1_8_delta']*100:+.2f} | [{fc[0]*100:+.2f}; {fc[1]*100:+.2f}] |")
    lines += ['', '## Huấn luyện và giới hạn', '',
        f"Cập nhật thật: control{reports['control']['actual_updates']}/759, supplement{reports['supplement']['actual_updates']}/759; phần thiếu là bước AMP bỏ qua.",
        '- CI bootstrap cặp theo nhóm ca/cảnh,2000lượt. Một seed và tập đã xem không đủ xác nhận cải thiện ngoài độc lập.',
        '- Original validation718/outer1176giữ nguyên. Clinical validation213vàofficial test183tách ca train; official test không có Lupus và rất ít SkinCancer.',
        '- SkinDisNet chỉ Eczema/Tinea; model vẫn dự đoán8lớp. Macro F1 lớp có mẫu là trung bình trên nhãn cósupport>0, không phải bộ phân loại2lớp.',
        '- 217ảnh Lupus atlas thiếu patient ID chỉ tham gia train phụ; không chứng minh mọi nhãn nguồn đúng hoặc quần thể bệnh nhân độc lập.',
        '- Giữ nguyên checkpoint ứng dụng và mốc5fold. Không chọn thêm trọng số theo điểm held-role thuận lợi.',
        '', '[Protocol](protocol.json), [lựa chọn validation](selection_locked.json), [tất cả chỉ số/confusion matrix](results.json), [kiểm chứng](verification.json), [bootstrap](paired_comparisons.json), [log](run.log).','']
    (OUT/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    for name in ('original_outer','dermacon_official_test'):
        cm=np.asarray(d['results'][name]['validation_selected']['confusion_matrix']); fig,ax=plt.subplots(figsize=(11,9)); im=ax.imshow(cm,cmap='Blues');fig.colorbar(im,ax=ax)
        ax.set(xticks=range(8),yticks=range(8),xticklabels=CLASSES,yticklabels=CLASSES,xlabel='Predicted',ylabel='Recorded label',title=f'Supplement pilot: {name} - {d["selected"]}')
        plt.setp(ax.get_xticklabels(),rotation=40,ha='right')
        for i in range(8):
            for j in range(8): ax.text(j,i,str(cm[i,j]),ha='center',va='center',color='white' if cm[i,j]>cm.max()/2 else 'black')
        fig.tight_layout();fig.savefig(OUT/f'{name}_selected_confusion.png',dpi=160);plt.close(fig)
    print(json.dumps(dict(verification='PASS',selected=d['selected'],updates={b:r['actual_updates'] for b,r in reports.items()},
        results={s:{k:{f:d['results'][s][k][f] for f in ('accuracy','macro_f1')} for k in ('old_classwise','control_mix25','supplement_mix25','validation_selected')} for s in pilot.SPLITS})),flush=True)


if __name__=='__main__': main()
