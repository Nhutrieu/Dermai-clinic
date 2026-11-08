"""Verify original-eight three-architecture CV and report all outcomes."""
import json
import math
from pathlib import Path

import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import pilot_original_eight_resnet50 as pilot
from run_original_eight_resnet50_cv import ROOT,OUT,F0,F0MODEL,PARENTS,NEW,REFERENCE,read
from common import CLASSES,save_json,sha256_file
from prepare_scene_grouped_oof_folds import OUTPUT as OUTER
from prepare_scene_grouped_oof_inner_splits import OUTPUT as INNER
from evaluate_scene_grouped_oof_classwise_fusion import aligned_inner_predictions,choose_class_weights,classwise_blend
from evaluate_scene_grouped_oof_ensemble import read_probabilities,score
from summarize_original_eight_resnet50 import independently_score


def paired_bootstrap(rows,a,b,seed=20261013,reps=2000):
    y=np.asarray([CLASSES.index(r['label']) for r in rows]); names,group=np.unique([r['group'] for r in rows],return_inverse=True)
    c=len(CLASSES); g=len(names)
    def blocks(p):
        return np.bincount(group*c*c+y*c+p.argmax(1),minlength=g*c*c).reshape(g,c,c)
    ca,cb=blocks(a),blocks(b); rng=np.random.default_rng(seed); acc=[]; f1=[]
    def m(cm):
        tp=np.diag(cm); denom=cm.sum(0)+cm.sum(1)
        return tp.sum()/cm.sum(),np.divide(2*tp,denom,out=np.zeros(c),where=denom>0).mean()
    for _ in range(reps):
        ids=rng.integers(0,g,size=g); aa,af=m(ca[ids].sum(0)); ba,bf=m(cb[ids].sum(0)); acc.append(aa-ba); f1.append(af-bf)
    return dict(replicates=reps,seed=seed,groups=g,accuracy_delta_ci95=np.quantile(acc,[.025,.975]).tolist(),
                macro_f1_delta_ci95=np.quantile(f1,[.025,.975]).tolist(),
                caveat='Exploratory developed cohort, paired case/scene bootstrap, one seed; unknown patient identities remain unknown; no multiple-comparison adjustment.')


def verify():
    protocol=read(OUT/'protocol.json'); result=read(OUT/'results.json'); outer=read(OUTER); inner=read(INNER)
    assert protocol['classes']==result['classes']==CLASSES
    for n,h in protocol['code_sha256'].items(): assert sha256_file(ROOT/'ai-service/training'/n)==h
    for n,h in protocol['sources'].items(): assert sha256_file(ROOT/n)==h
    assert sha256_file(OUTER)==protocol['outer_manifest_sha256'] and sha256_file(INNER)==protocol['inner_plan_sha256']
    assert result['protocol_sha256']==sha256_file(OUT/'protocol.json')
    assert sha256_file(Path(torch.hub.get_dir())/'checkpoints/resnet50-11ad3fa6.pth')==protocol['pretrained_sha256']
    assert read(OUT/'pretrained_verification.json')['pretrained_sha256']==protocol['pretrained_sha256']
    expected=[]; updates=skips=0; counts=[]; source_rows={r['path']:r for r in outer['images']}
    for f,fold in enumerate(protocol['folds']):
        directory=F0 if f==0 else OUT/f'fold_{f}'
        model=F0MODEL if f==0 else ROOT/f'ai-service/candidates/original_eight_resnet50_cv_fold{f}_seed42'
        roles=fold['roles']; groups={k:{source_rows[p]['scene_or_case_group'] for p in paths} for k,paths in roles.items()}
        assert {p for paths in roles.values() for p in paths}==set(source_rows)
        for a,b in [('train','inner_validation'),('train','outer_holdout'),('inner_validation','outer_holdout')]: assert groups[a].isdisjoint(groups[b])
        assert roles['inner_validation']==inner['folds'][f]['inner_validation_paths']
        assert set(roles['outer_holdout'])=={r['path'] for r in outer['images'] if r['fold']==f}
        for role,paths in roles.items(): assert len(paths)==inner['folds'][f][role+'_images']
        lock=read(directory/'selection_locked.json'); selection=read(model/'selection_report.json'); history=read(model/'history.json')
        assert selection['configuration']==protocol['configuration']
        assert selection['protocol_sha256']==sha256_file(directory/'protocol.json')
        if f>0:
            child=read(directory/'protocol.json')
            assert child['benchmark_protocol_sha256']==sha256_file(OUT/'protocol.json') and child['fold']==f and child['roles']==roles
            assert lock['protocol_sha256']==sha256_file(OUT/'protocol.json') and lock['fold_protocol_sha256']==sha256_file(directory/'protocol.json')
        assert sha256_file(model/'best_model.pth')==selection['checkpoint_sha256']==lock['checkpoint_sha256']
        assert [h['epoch'] for h in history]==list(range(1,len(history)+1)) and 3<=len(history)<=24
        epochs=[]; attempts=math.ceil(len(roles['train'])/16)
        for h in history:
            a,b=h['validation_raw'],h['validation_ema']; source='ema' if b['macro_f1']>=a['macro_f1'] else 'raw'; v=b if source=='ema' else a
            assert h['selected_weights']==source and h['backbone_frozen']==(h['epoch']<=2)
            assert h['attempted_optimizer_updates']==attempts and 0<=h['actual_optimizer_updates']<=attempts
            epochs.append(dict(epoch=h['epoch'],source=source,objective=[v['macro_f1'],v['top3_accuracy'],-v['loss']],validation=v))
        assert max(epochs,key=lambda x:tuple(x['objective']))==selection['best']
        assert selection['epochs_completed']==len(history)
        assert selection['actual_optimizer_updates']==sum(h['actual_optimizer_updates'] for h in history)
        assert selection['amp_skipped_updates']==sum(h['attempted_optimizer_updates']-h['actual_optimizer_updates'] for h in history)
        updates+=selection['actual_optimizer_updates']; skips+=selection['amp_skipped_updates']; counts.append(dict(fold=f,epochs=len(history),best_epoch=selection['best']['epoch'],updates=selection['actual_optimizer_updates'],skipped=selection['amp_skipped_updates']))
        cp=torch.load(model/'best_model.pth',map_location='cpu',weights_only=False)
        assert cp['classes']==CLASSES and cp['architecture']=='resnet50' and cp['epoch']==selection['best']['epoch'] and cp['protocol_sha256']==sha256_file(directory/'protocol.json'); del cp
        vp={}; vy=None
        for m in PARENTS: vp[m],vy=aligned_inner_predictions(m,f,outer,inner)
        with np.load(directory/'validation_predictions.npz') as data:
            assert data['paths'].tolist()==roles['inner_validation'] and np.array_equal(data['truth'],vy)
            for m in PARENTS: assert np.array_equal(data[m],vp[m])
            vp[NEW]=data[NEW]
        assert score(vp[NEW],vy)['macro_f1']==selection['best']['validation']['macro_f1']
        w,details=choose_class_weights(vp[PARENTS[0]],vp[PARENTS[1]],vy); vp[REFERENCE]=classwise_blend(vp[PARENTS[0]],vp[PARENTS[1]],w)
        assert w.tolist()==lock['reference_weights'] and details==lock['reference_details']
        specs=pilot.candidates(vp,vy); reference=score(vp[REFERENCE],vy); trials=[dict(spec=s,validation=score(pilot.combine(s,vp),vy)) for s in specs]
        for t in trials: t['passes_validation_guard']=pilot.passes(t['validation'],reference)
        assert trials==lock['trials'] and sorted([t for t in trials if t['passes_validation_guard']],key=pilot.ranking)[0]['spec']==lock['selected']
        assert (directory/'selection_locked.json').stat().st_mtime_ns<(directory/'test_predictions.json').stat().st_mtime_ns
        pred=read(directory/'test_predictions.json'); order=sorted(roles['outer_holdout']); assert [r['path'] for r in pred]==order
        tp={}; erows={p:source_rows[p] for p in order}
        for m in PARENTS:
            source=read_probabilities(m,f,outer,erows); tp[m]=np.stack([source[p] for p in order])
            assert np.array_equal(tp[m],np.asarray([r['probabilities'][m] for r in pred]))
        for r in pred:
            row=source_rows[r['path']]
            assert r['sha256']==row['sha256'] and r['label']==row['class'] and r['group']==row['scene_or_case_group']
        tp[NEW]=np.asarray([r['probabilities'][NEW] for r in pred]); tp[REFERENCE]=classwise_blend(tp[PARENTS[0]],tp[PARENTS[1]],w)
        rebuilt={s['name']:pilot.combine(s,tp) for s in specs}; rebuilt['validation_selected']=pilot.combine(lock['selected'],tp)
        y=np.asarray([CLASSES.index(r['label']) for r in pred]); d=read(directory/'results.json')
        assert d['selected_method']==lock['selected']['name'] and d['selection_sha256']==sha256_file(directory/'selection_locked.json')
        for name,p in rebuilt.items():
            assert np.array_equal(p,np.asarray([r['probabilities'][name] for r in pred]))
            assert independently_score(y,p)==d['results'][name]
        assert result['per_fold'][f]==dict(fold=f,selected_method=d['selected_method'],results=d['results'])
        expected.extend(dict(r,fold=f) for r in pred)
    expected.sort(key=lambda r:r['path']); rows=read(OUT/'oof_predictions.json'); assert rows==expected
    assert len(rows)==len({r['path'] for r in rows})==5937 and set(r['path'] for r in rows)==set(source_rows)
    y=np.asarray([CLASSES.index(r['label']) for r in rows]); probs={k:np.asarray([r['probabilities'][k] for r in rows]) for k in rows[0]['probabilities']}
    for k,p in probs.items(): assert independently_score(y,p)==result['results'][k]
    benchmark=ROOT/'ai-service/reports/scene_grouped_oof_classwise_fusion_seed42.json'; assert sha256_file(benchmark)==protocol['benchmark_sha256']
    old=read(benchmark)
    for k,m in [(REFERENCE,'classwise_inner_fitted'),(PARENTS[0],PARENTS[0]),(PARENTS[1],PARENTS[1])]:
        for field in ('accuracy','macro_f1','confusion_matrix','per_class'): assert result['results'][k][field]==old['methods'][m][field]
    subset=[r for r in rows if r['fold']!=0]; sy=np.asarray([CLASSES.index(r['label']) for r in subset])
    assert result['fold1_4_replication']['images']==len(subset)==4761
    for k in probs: assert independently_score(sy,np.asarray([r['probabilities'][k] for r in subset]))==result['fold1_4_replication']['results'][k]
    return result,rows,probs,counts,updates,skips


def plot_confusion(metrics,filename,title):
    cm=np.asarray(metrics['confusion_matrix']); fig,ax=plt.subplots(figsize=(11,9))
    im=ax.imshow(cm,cmap='Blues'); fig.colorbar(im,ax=ax)
    ax.set(xticks=range(8),yticks=range(8),xticklabels=CLASSES,yticklabels=CLASSES,
           xlabel='Predicted',ylabel='Recorded label',title=title)
    plt.setp(ax.get_xticklabels(),rotation=40,ha='right')
    for i in range(8):
        for j in range(8):
            ax.text(j,i,str(cm[i,j]),ha='center',va='center',color='white' if cm[i,j]>cm.max()/2 else 'black')
    fig.tight_layout(); fig.savefig(OUT/filename,dpi=160); plt.close(fig)


def main():
    result,rows,probs,counts,updates,skips=verify()
    names={'efficientnet_b0':'EfficientNet-B0','convnext_tiny':'ConvNeXt-Tiny','resnet50':'ResNet-50',
           REFERENCE:'B0/ConvNeXt theo bệnh (đối chứng)',
           'reference_resnet_w0.25':'75% đối chứng + 25% ResNet',
           'reference_resnet_w0.50':'50% đối chứng + 50% ResNet',
           'reference_resnet_w0.75':'25% đối chứng + 75% ResNet',
           'reference_resnet_classwise':'Đối chứng/ResNet theo bệnh','equal3':'Trung bình đều ba model',
           'validation_selected':'Chọn bằng validation với điều kiện đã khóa'}
    selected='validation_selected'; fixed='reference_resnet_w0.25'
    comparisons={}; mask=np.asarray([r['fold']!=0 for r in rows])
    for scope,idx in [('all_five_folds',np.ones(len(rows),dtype=bool)),('fold1_4_replication',mask)]:
        rr=[r for r,keep in zip(rows,idx) if keep]; metrics=result['results'] if scope=='all_five_folds' else result['fold1_4_replication']['results']
        comparisons[scope]={}
        for k in (selected,fixed):
            ci=paired_bootstrap(rr,probs[k][idx],probs[REFERENCE][idx])
            ci.update(accuracy_delta=metrics[k]['accuracy']-metrics[REFERENCE]['accuracy'],
                      macro_f1_delta=metrics[k]['macro_f1']-metrics[REFERENCE]['macro_f1'])
            comparisons[scope][k]=ci
    save_json(OUT/'paired_comparisons.json',comparisons)
    sources={}; truth=np.asarray([CLASSES.index(r['label']) for r in rows])
    for source,prefix,count in [('original_train','SkinDisease/train/',4961),('scin_train','SkinDisease/scin-v1/train/',976)]:
        keep=np.asarray([r['path'].startswith(prefix) for r in rows]); assert int(keep.sum())==count
        sources[source]=dict(images=count,results={k:independently_score(truth[keep],probs[k][keep]) for k in (REFERENCE,selected,fixed)})
    assert sum(v['images'] for v in sources.values())==5937
    save_json(OUT/'per_source.json',dict(scope='Descriptive original development source slices, not external tests; SCIN has no SkinCancer support. Do not compare slice Macro F1 as an identical class distribution.',sources=sources))
    audit=[]
    for f in range(5):
        lock=read((F0 if f==0 else OUT/f'fold_{f}')/'selection_locked.json')
        trials={t['spec']['name']:t for t in lock['trials']}; a=trials[fixed]['validation']; b=trials[REFERENCE]['validation']; reasons=[]
        if a['macro_f1']<b['macro_f1']-1e-12: reasons.append('Macro F1 giảm')
        if a['accuracy']<b['accuracy']-.005-1e-12: reasons.append('Accuracy giảm quá 0,5 điểm %')
        if a['per_class']['SkinCancer']['recall']<b['per_class']['SkinCancer']['recall']-1e-12: reasons.append('Recall SkinCancer giảm')
        for c in CLASSES:
            if c not in ('Lupus','Psoriasis') and a['per_class'][c]['recall']<b['per_class'][c]['recall']-.02-1e-12:
                reasons.append(f'Recall {c} giảm quá 2 điểm %')
            if c in ('Lupus','Psoriasis') and a['per_class'][c]['precision']<b['per_class'][c]['precision']-.02-1e-12:
                reasons.append(f'Precision {c} giảm quá 2 điểm %')
        assert bool(reasons)==(not trials[fixed]['passes_validation_guard'])
        audit.append(dict(fold=f,reference=b,fixed25=a,guard_passed=trials[fixed]['passes_validation_guard'],failed_conditions=reasons,selected_method=lock['selected']['name']))
    save_json(OUT/'validation_fixed25_audit.json',audit)
    state=read(ROOT/'ai-service/reports/active_research_track.json')
    assert state['active_track']=='original_eight' and state['classes']==CLASSES
    assert sha256_file(ROOT/state['serving_checkpoint'])==state['serving_checkpoint_sha256']
    save_json(OUT/'verification.json',dict(status='PASS',verifier_code_sha256=sha256_file(Path(__file__)),
        protocol_sha256=sha256_file(OUT/'protocol.json'),results_sha256=sha256_file(OUT/'results.json'),
        predictions_sha256=sha256_file(OUT/'oof_predictions.json'),comparisons_sha256=sha256_file(OUT/'paired_comparisons.json'),
        per_source_sha256=sha256_file(OUT/'per_source.json'),
        validation_fixed25_audit_sha256=sha256_file(OUT/'validation_fixed25_audit.json'),
        images=5937,replication_images=4761,architectures=3,resnet_models=5,new_resnet_models=4,reused_resnet_models=1,
        model_training=counts,actual_optimizer_updates=updates,amp_skipped_updates=skips,
        serving_checkpoint_sha256=state['serving_checkpoint_sha256'],
        checks=['Registered code, sources, manifests, ImageNet cache and checkpoints unchanged',
                'All five group-disjoint train/inner validation/outer roles reconstructed',
                'Raw/EMA choice, checkpoint ranking, actual optimizer updates reconstructed',
                'Nine candidate recipes, validation guard and selector reconstructed for each fold',
                'Choice artifact predates outer predictions in every fold',
                'All parent probabilities and new fusion probabilities independently reconstructed',
                'Independent NumPy Accuracy, precision, recall, F1 and confusion matrices',
                'All 5937 unique outer identities and fold1-4 subset verified',
                'Old B0/ConvNeXt classwise benchmark reproduced exactly',
                'Original serving checkpoint unchanged']))
    baseline=result['results'][REFERENCE]; chosen=result['results'][selected]; secondary=result['results'][fixed]
    lines=['# ResNet-50 và ensemble trên bộ tám bệnh cũ — đủ 5 fold','',
        '**Hoàn tất; kiểm chứng PASS. 5.937 ảnh OOF, ba kiến trúc. Đây là đánh giá nội bộ trên tập phát triển.**','',
        '## Phạm vi và cách chọn','',
        '- Tám bệnh: '+', '.join(CLASSES)+'.',
        '- Giữ nguyên 5 fold theo nhóm ảnh/cảnh/ca và inner validation cũ. Tái sử dụng ResNet fold 0 đã xác minh; train thêm bốn ResNet từ ImageNet V2, seed 42.',
        '- Mỗi fold chọn checkpoint trên validation bằng Macro F1, Top-3, rồi loss; tối đa 24 epoch, freeze 2 epoch và patience 7.',
        '- Đánh giá chín công thức cố định. Chọn bằng validation với điều kiện: Recall SkinCancer và Macro F1 không giảm; Accuracy giảm tối đa 0,5 điểm %; Recall các bệnh ngoài mục tiêu giảm tối đa 2 điểm %; Precision Lupus/Psoriasis giảm tối đa 2 điểm %. Đối chứng luôn là phương án dự phòng.',
        '- Trong các phương án đạt điều kiện, ưu tiên Recall thấp hơn giữa Lupus/Psoriasis, rồi F1 trung bình hai bệnh và chỉ số tổng. Khóa lựa chọn trước khi tạo kết quả outer.',
        '- Công thức 75% đối chứng + 25% ResNet là giả thuyết lặp lại sau khi đã thấy kết quả fold 0. Báo cáo riêng 4.761 ảnh ở fold 1–4; không gọi phương án có điểm outer cao nhất là phương án được chọn trên validation.',
        '', '## Điểm tổng trên cùng 5.937 ảnh','',
        '| Phương án | Accuracy | Macro F1 | Recall Lupus | Recall Psoriasis | Recall SkinCancer |',
        '|---|---:|---:|---:|---:|---:|']
    for k in names:
        a=result['results'][k]; pc=a['per_class']
        lines.append(f"| {names[k]} | {a['accuracy']:.2%} | {a['macro_f1']:.2%} | {pc['Lupus']['recall']:.2%} | {pc['Psoriasis']['recall']:.2%} | {pc['SkinCancer']['recall']:.2%} |")
    lines+=['','### Phương án chính: chọn bằng validation','',
        f"Accuracy {chosen['accuracy']:.2%} ({(chosen['accuracy']-baseline['accuracy'])*100:+.2f} điểm % so với đối chứng), Macro F1 {chosen['macro_f1']:.2%} ({(chosen['macro_f1']-baseline['macro_f1'])*100:+.2f} điểm %).",
        'Điều kiện áp dụng trên validation; không bảo đảm từng chỉ số trên outer cũng giữ nguyên.',
        '', '### Vì sao công thức 75:25 được giữ hoặc loại trên validation','',
        '| Fold | Accuracy val cũ | Accuracy val 75:25 | F1 val cũ | F1 val 75:25 | Đạt điều kiện | Điều kiện chưa đạt |',
        '|---|---:|---:|---:|---:|---|---|']
    for d in audit:
        a,b=d['reference'],d['fixed25']
        lines.append(f"| {d['fold']} | {a['accuracy']:.2%} | {b['accuracy']:.2%} | {a['macro_f1']:.2%} | {b['macro_f1']:.2%} | {d['guard_passed']} | "+('; '.join(d['failed_conditions']) or 'Không có')+' |')
    lines += [
        '', '## Từng bệnh: đối chứng, phương án chính và công thức 75:25','',
        '| Bệnh | Ảnh | Recall cũ | Recall chọn | Recall 75:25 | F1 cũ | F1 chọn | F1 75:25 | Precision cũ | Precision chọn | Precision 75:25 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for c in CLASSES:
        a,b,d=[v['per_class'][c] for v in (baseline,chosen,secondary)]
        values=[v[field] for field in ('recall','f1','precision') for v in (a,b,d)]
        lines.append(f"| {c} | {a['support']} | "+' | '.join(f'{v:.2%}' for v in values)+' |')
    lines+=['','## Từng fold','',
        '| Fold (0–4) | Ảnh outer | Phương án validation chọn | Accuracy cũ | Accuracy chọn | Accuracy 75:25 | F1 cũ | F1 chọn | F1 75:25 |',
        '|---|---:|---|---:|---:|---:|---:|---:|---:|']
    for d in result['per_fold']:
        mm=d['results']; aa=[mm[k] for k in (REFERENCE,selected,fixed)]
        values=[v[field] for field in ('accuracy','macro_f1') for v in aa]
        count=sum(sum(r) for r in aa[0]['confusion_matrix'])
        lines.append(f"| {d['fold']} | {count} | {d['selected_method']} | "+' | '.join(f'{v:.2%}' for v in values)+' |')
    lines+=['','## Lặp lại công thức trên fold 1–4: 4.761 ảnh','',
        '| Phương án | Accuracy | Macro F1 | Recall Lupus | Recall Psoriasis | F1 Lupus | F1 Psoriasis | Recall SkinCancer |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for k in (REFERENCE,selected,fixed):
        m=result['fold1_4_replication']['results'][k]; pc=m['per_class']
        values=[m['accuracy'],m['macro_f1'],pc['Lupus']['recall'],pc['Psoriasis']['recall'],pc['Lupus']['f1'],pc['Psoriasis']['f1'],pc['SkinCancer']['recall']]
        lines.append(f"| {names[k]} | "+' | '.join(f'{v:.2%}' for v in values)+' |')
    lines+=['','## Lupus/Psoriasis theo nguồn ảnh phát triển','',
        '| Nguồn | Bệnh | Ảnh | Recall cũ | Recall chọn | Recall 75:25 | F1 cũ | F1 chọn | F1 75:25 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for source,d in sources.items():
        for c in ('Lupus','Psoriasis'):
            mm=[d['results'][k]['per_class'][c] for k in (REFERENCE,selected,fixed)]
            values=[m[field] for field in ('recall','f1') for m in mm]
            lines.append(f"| {source} | {c} | {mm[0]['support']} | "+' | '.join(f'{v:.2%}' for v in values)+' |')
    lines+=['','Đây là các phần của tập phát triển OOF, không phải ảnh kiểm thử ngoài mới. SCIN có ít ảnh Lupus và không có ảnh nhãn SkinCancer trong phần này.']
    lines+=['','## Độ bất định của chênh lệch','',
        'CI95% bootstrap cặp theo nhóm ảnh/cảnh/ca, 2.000 lần, seed 20261013. Đây là phân tích thăm dò, một seed huấn luyện, không hiệu chỉnh nhiều so sánh.',
        '', '| Phạm vi | Phương án so với đối chứng | Δ Accuracy | CI95% Δ Accuracy | Δ Macro F1 | CI95% Δ Macro F1 |',
        '|---|---|---:|---|---:|---|']
    for scope,cc in comparisons.items():
        for k,m in cc.items():
            ci=lambda field: '['+'; '.join(f'{v*100:+.2f}' for v in m[field])+']'
            lines.append(f"| {scope} | {names[k]} | {m['accuracy_delta']*100:+.2f} | {ci('accuracy_delta_ci95')} | {m['macro_f1_delta']*100:+.2f} | {ci('macro_f1_delta_ci95')} |")
    lines+=['','Đơn vị trong bảng chênh lệch: điểm phần trăm. CI có chứa 0 chưa cho bằng chứng rõ về tăng trên phạm vi này.',
        '', '## Huấn luyện đã chạy','',
        '| Fold | Epoch chạy | Epoch chọn | Cập nhật thật | AMP bỏ qua |',
        '|---|---:|---:|---:|---:|']
    for c in counts: lines.append(f"| {c['fold']} | {c['epochs']} | {c['best_epoch']} | {c['updates']} | {c['skipped']} |")
    lines += ['',f'Tổng năm ResNet (kể cả fold 0 tái sử dụng): {updates} bước cập nhật thật; {skips} bước AMP bỏ qua.',
        '', '## Giới hạn và tệp kết quả','',
        '- Tập phát triển và các kết quả cũ đã được dùng để xây dựng hướng thử nghiệm. Fold 0 góp phần tạo giả thuyết 75:25; fold 1–4 là lặp lại bổ sung, chưa phải tập ảnh bên ngoài độc lập.',
        '- Chia theo nhóm ca/cảnh/ảnh có sẵn; nhiều ảnh gốc thiếu mã bệnh nhân. Không gọi đây là kiểm thử độc lập theo bệnh nhân.',
        '- Không thêm ảnh của bộ tám bệnh mới. Checkpoint phục vụ ứng dụng giữ nguyên; điểm ensemble nghiên cứu không phải điểm của B0 đang phục vụ.',
        '- [Giao thức](protocol.json), [kết quả mọi công thức và từng bệnh](results.json), [kiểm chứng](verification.json), [so sánh cặp](paired_comparisons.json), [từng nguồn](per_source.json), [log train](run.log).',
        '- [Confusion matrix phương án chính](selected_confusion.png), [confusion matrix 75:25](fixed25_confusion.png).','']
    (OUT/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    plot_confusion(chosen,'selected_confusion.png','Original eight - validation-selected OOF (5937 photos)')
    plot_confusion(secondary,'fixed25_confusion.png','Original eight - secondary 75:25 ensemble OOF (5937 photos)')
    print(json.dumps(dict(verification='PASS',images=5937,fold_methods=[d['selected_method'] for d in result['per_fold']],
        results={k:{field:result['results'][k][field] for field in ('accuracy','macro_f1')} for k in (REFERENCE,selected,fixed)},
        replication={k:{field:result['fold1_4_replication']['results'][k][field] for field in ('accuracy','macro_f1')} for k in (REFERENCE,selected,fixed)})),flush=True)


if __name__=='__main__': main()
