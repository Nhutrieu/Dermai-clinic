"""Verify original-eight pilot and keep the full five-fold benchmark separate."""
import json
from pathlib import Path

import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from pilot_original_eight_resnet50 import ROOT,OUT,MODEL,OUTER,INNER,CLASSES,PARENTS,NEW,REFERENCE,read,candidates,combine,passes,ranking
from common import save_json,sha256_file
from evaluate_scene_grouped_oof_classwise_fusion import aligned_inner_predictions,choose_class_weights,classwise_blend
from evaluate_scene_grouped_oof_ensemble import read_probabilities,score,paired_cluster_interval


def independently_score(y,p):
    assert p.shape==(len(y),8) and np.isfinite(p).all() and (p>=0).all() and np.allclose(p.sum(1),1,atol=1e-6,rtol=0)
    cm=np.zeros((8,8),dtype=int); np.add.at(cm,(y,p.argmax(1)),1)
    tp=np.diag(cm); precision=np.divide(tp,cm.sum(0),out=np.zeros(8),where=cm.sum(0)>0)
    recall=np.divide(tp,cm.sum(1),out=np.zeros(8),where=cm.sum(1)>0)
    f1=np.divide(2*precision*recall,precision+recall,out=np.zeros(8),where=precision+recall>0)
    actual=score(p,y)
    assert actual['confusion_matrix']==cm.tolist() and abs(actual['accuracy']-tp.sum()/len(y))<1e-12
    assert abs(actual['macro_f1']-f1.mean())<1e-12
    for i,label in enumerate(CLASSES):
        for k,v in [('precision',precision[i]),('recall',recall[i]),('f1',f1[i]),('support',int(cm[i].sum()))]: assert abs(actual['per_class'][label][k]-v)<1e-12
    return actual


def main():
    protocol=read(OUT/'protocol.json'); result=read(OUT/'results.json'); lock=read(OUT/'selection_locked.json')
    for n,h in protocol['code_sha256'].items(): assert sha256_file(ROOT/'ai-service/training'/n)==h
    for n,h in protocol['sources'].items(): assert sha256_file(ROOT/n)==h
    assert sha256_file(OUTER)==protocol['outer_manifest_sha256'] and sha256_file(INNER)==protocol['inner_plan_sha256']
    assert result['protocol_sha256']==lock['protocol_sha256']==sha256_file(OUT/'protocol.json')
    assert result['selection_sha256']==sha256_file(OUT/'selection_locked.json')
    selection=read(MODEL/'selection_report.json'); history=read(MODEL/'history.json')
    assert selection['checkpoint_sha256']==lock['checkpoint_sha256']==sha256_file(MODEL/'best_model.pth')
    assert selection['configuration']==protocol['configuration'] and selection['protocol_sha256']==sha256_file(OUT/'protocol.json')
    assert [h['epoch'] for h in history]==list(range(1,len(history)+1)) and 3<=len(history)<=24
    chosen=[]
    for h in history:
        raw=h['validation_raw']; ema=h['validation_ema']; source='ema' if ema['macro_f1']>=raw['macro_f1'] else 'raw'
        assert h['selected_weights']==source and h['backbone_frozen']==(h['epoch']<=2)
        assert h['attempted_optimizer_updates']==253 and 0<=h['actual_optimizer_updates']<=253
        v=ema if source=='ema' else raw
        chosen.append(dict(epoch=h['epoch'],source=source,objective=[v['macro_f1'],v['top3_accuracy'],-v['loss']],validation=v))
    assert max(chosen,key=lambda x:tuple(x['objective']))==selection['best']
    assert len(history)==selection['epochs_completed']
    assert sum(h['actual_optimizer_updates'] for h in history)==selection['actual_optimizer_updates']
    assert sum(h['attempted_optimizer_updates']-h['actual_optimizer_updates'] for h in history)==selection['amp_skipped_updates']
    cp=torch.load(MODEL/'best_model.pth',map_location='cpu',weights_only=False)
    assert cp['classes']==CLASSES and cp['architecture']=='resnet50' and cp['epoch']==selection['best']['epoch']
    assert cp['protocol_sha256']==sha256_file(OUT/'protocol.json'); del cp
    outer=read(OUTER); inner=read(INNER); by_path={r['path']:r for r in outer['images']}
    roles=protocol['roles']; groups={k:{by_path[p]['scene_or_case_group'] for p in paths} for k,paths in roles.items()}
    for a,b in [('train','inner_validation'),('train','outer_holdout'),('inner_validation','outer_holdout')]: assert groups[a].isdisjoint(groups[b])
    assert {p for paths in roles.values() for p in paths}==set(by_path)
    assert len(roles['train'])==4043 and len(roles['inner_validation'])==718 and len(roles['outer_holdout'])==1176
    assert set(roles['inner_validation'])==set(inner['folds'][0]['inner_validation_paths'])
    assert all(by_path[p]['fold']==0 for p in roles['outer_holdout'])
    vp={}; vy=None
    for m in PARENTS: vp[m],vy=aligned_inner_predictions(m,0,outer,inner)
    with np.load(OUT/'validation_predictions.npz') as data:
        assert data['paths'].tolist()==roles['inner_validation'] and np.array_equal(data['truth'],vy)
        for m in PARENTS: assert np.array_equal(data[m],vp[m])
        vp[NEW]=data[NEW]
    w,details=choose_class_weights(vp[PARENTS[0]],vp[PARENTS[1]],vy); vp[REFERENCE]=classwise_blend(vp[PARENTS[0]],vp[PARENTS[1]],w)
    assert lock['reference_weights']==w.tolist() and lock['reference_details']==details
    specs=candidates(vp,vy); reference=score(vp[REFERENCE],vy)
    trials=[dict(spec=s,validation=score(combine(s,vp),vy)) for s in specs]
    for t in trials: t['passes_validation_guard']=passes(t['validation'],reference)
    assert lock['trials']==trials and sorted([t for t in trials if t['passes_validation_guard']],key=ranking)[0]['spec']==lock['selected']
    assert result['selected_method']==lock['selected']['name']
    assert (OUT/'selection_locked.json').stat().st_mtime_ns<(OUT/'test_predictions.json').stat().st_mtime_ns
    predictions=read(OUT/'test_predictions.json'); order=sorted(roles['outer_holdout']); assert [r['path'] for r in predictions]==order
    tp={}
    expected={p:by_path[p] for p in order}
    for m in PARENTS:
        base=read_probabilities(m,0,outer,expected); tp[m]=np.stack([base[p] for p in order])
        assert np.array_equal(tp[m],np.asarray([r['probabilities'][m] for r in predictions]))
    for r in predictions:
        base=by_path[r['path']]
        assert r['sha256']==base['sha256'] and r['label']==base['class'] and r['group']==base['scene_or_case_group']
    tp[NEW]=np.asarray([r['probabilities'][NEW] for r in predictions]); tp[REFERENCE]=classwise_blend(tp[PARENTS[0]],tp[PARENTS[1]],w)
    p={s['name']:combine(s,tp) for s in specs}; p['validation_selected']=combine(lock['selected'],tp)
    y=np.asarray([CLASSES.index(by_path[path]['class']) for path in order])
    for name,prob in p.items():
        assert np.array_equal(prob,np.asarray([r['probabilities'][name] for r in predictions]))
        assert independently_score(y,prob)==result['results'][name]
    accuracy_ci=paired_cluster_interval(p['validation_selected'].argmax(1)==y,p[REFERENCE].argmax(1)==y,[r['group'] for r in predictions])
    save_json(OUT/'verification.json',dict(status='PASS',verifier_code_sha256=sha256_file(Path(__file__)),protocol_sha256=sha256_file(OUT/'protocol.json'),
        results_sha256=sha256_file(OUT/'results.json'),prediction_sha256=sha256_file(OUT/'test_predictions.json'),epochs_completed=len(history),
        actual_optimizer_updates=selection['actual_optimizer_updates'],amp_skipped_updates=selection['amp_skipped_updates'],images=1176,
        accuracy_delta_ci95=accuracy_ci,checks=['Original-eight classes only; sources/code/checkpoints hashed','Exact old4043/718/1176roles and group separation',
          'Raw/EMA checkpoint rule independently reconstructed','Actual optimizer update counts','All9 candidates and guard/ranking reconstructed from validation',
          'Choice locked before outer artifact','Old outer parents identical to verified fold0','All saved probability blends reconstructed',
          'Independent NumPy Accuracy/precision/recall/F1/confusion','1176unique pilot holdout rows; separate from5937OOFbenchmark'],
        log_note='PyTorch scheduler warning is caused by the optimizer-step counter wrapper installed after scheduler creation. Registered code calls scheduler.step only after training updates; counts confirm actual updates occurred.'))
    baseline=result['results'][REFERENCE]; selected=result['results']['validation_selected']
    lines=['# Pilot ResNet-50 trên tám bệnh ban đầu','', '**Hoàn tất, kiểm chứng PASS. Pilot một outer fold; không thay điểm 5 fold cũ.**','',
           f"Train4043/validation718/holdout1176ảnh; ResNet train{len(history)}epoch, chọn epoch{selection['best']['epoch']} ({selection['best']['source']}).",
           f"Cập nhật thật: {selection['actual_optimizer_updates']}; bước AMP bỏ qua: {selection['amp_skipped_updates']}.",'',
           f"Phương án validation chọn với guard: `{result['selected_method']}`.",'',
           '| Phương án | Val Accuracy | Val Macro F1 | Đạt guard | Outer Accuracy | Outer Macro F1 |',
           '|---|---:|---:|---|---:|---:|']
    for t in sorted(trials,key=ranking):
        name=t['spec']['name']; a=t['validation']; b=result['results'][name]
        lines.append(f"| {name} | {a['accuracy']:.2%} | {a['macro_f1']:.2%} | {t['passes_validation_guard']} | {b['accuracy']:.2%} | {b['macro_f1']:.2%} |")
    lines+=['','## Từng bệnh: đối chứng và phương án chọn','', '| Bệnh | Recall cũ | Recall chọn | F1 cũ | F1 chọn | Ảnh |','|---|---:|---:|---:|---:|---:|']
    for label in CLASSES:
        a=baseline['per_class'][label]; b=selected['per_class'][label]
        lines.append(f"| {label} | {a['recall']:.2%} | {b['recall']:.2%} | {a['f1']:.2%} | {b['f1']:.2%} | {a['support']} |")
    lines+=['','## Kết luận trong phạm vi pilot','',
            f"So với cùng đối chứng fold0: Accuracy {(selected['accuracy']-baseline['accuracy'])*100:+.2f} điểm %, Macro F1 {(selected['macro_f1']-baseline['macro_f1'])*100:+.2f} điểm %.",
            f"CI95% chênh Accuracy theo nhóm ảnh/ca,3000bootstrap: [{accuracy_ci[0]*100:+.2f}; {accuracy_ci[1]*100:+.2f}] điểm %. Phân tích thăm dò trên dữ liệu phát triển đã xem.",
            '- Không chọn lại tỷ lệ bằng điểm outer thuận lợi; guard áp dụng trên validation, không bảo đảm mọi chỉ số outer giữ nguyên.',
            '- Mốc cũ:78,07% Accuracy/76,82% MacroF1 trên5937ảnh qua5fold. Không gán mốc đó cho B0 đang phục vụ hoặc pilot1176ảnh.',
            '- Không dùng dữ liệu/model bộ tám bệnh mới; không đổi nhãn hoặc model phục vụ ứng dụng.',
            '- Nhóm ảnh/cảnh/ca không thay thế mã bệnh nhân còn thiếu. Cần đánh giá ngoài độc lập để khẳng định khả năng tổng quát.',
            '', 'Nguồn kiến trúc: [ResNet](https://arxiv.org/abs/1512.03385), [Torchvision0.20](https://docs.pytorch.org/vision/0.20/models/generated/torchvision.models.resnet50.html). Đây là áp dụng vào dữ liệu cũ, không tái lập bài báo.','']
    (OUT/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    fig,ax=plt.subplots(figsize=(11,9)); cm=np.asarray(selected['confusion_matrix']); im=ax.imshow(cm,cmap='Blues'); fig.colorbar(im,ax=ax)
    ax.set(xticks=range(8),yticks=range(8),xticklabels=CLASSES,yticklabels=CLASSES,xlabel='Predicted',ylabel='Recorded label',title='Original eight diagnoses: validation-selected pilot - fold0')
    plt.setp(ax.get_xticklabels(),rotation=40,ha='right')
    for i in range(8):
        for j in range(8): ax.text(j,i,str(cm[i,j]),ha='center',va='center',color='white' if cm[i,j]>cm.max()/2 else 'black')
    fig.tight_layout(); fig.savefig(OUT/'selected_confusion.png',dpi=160); plt.close(fig)
    print(json.dumps(dict(verification='PASS',selected=result['selected_method'],test_accuracy=selected['accuracy'],test_macro_f1=selected['macro_f1'],old_fold0_accuracy=baseline['accuracy'],old_fold0_macro_f1=baseline['macro_f1'])),flush=True)


if __name__=='__main__': main()
