"""Matched eight-disease continuation: uniform replay versus mild weak-class focus.

Five fixed original folds, eight labels, original ConvNeXt starting checkpoints.
Both arms receive exactly four further epochs. Only sampling weights differ.
All training/fusion choices use inner validation before outer inference.
"""
from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import json
import math
import os
import random
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Subset

from common import CLASSES, ImageSample, ImageSampleDataset, build_model, evaluation_transform, save_json, seed_everything, sha256_file
import train_v2 as trainer
from evaluate_scene_grouped_oof_classwise_fusion import aligned_inner_predictions, choose_class_weights, classwise_blend
from evaluate_scene_grouped_oof_ensemble import ARCHITECTURES, RUN_ROOT, read_probabilities, score, source_score, paired_cluster_interval
from prepare_scene_grouped_oof_inner_splits import checked_outer_rows, OUTPUT as INNER
from prepare_scene_grouped_oof_folds import OUTPUT as OUTER

ROOT=Path(__file__).resolve().parents[2]
NAME='original_eight_focus_replay_cv_seed42_20261020'
OUT=ROOT/'ai-service/reports'/NAME
MODELS=ROOT/'ai-service/candidates'/NAME
FOCUS=['Lupus','Psoriasis','Tinea']
BRANCHES=['control','focus']
CONFIG=dict(seed=42,epochs=4,batch_size=16,workers=0,backbone_lr=.00001,head_lr=.00005,
    weight_decay=.01,label_smoothing=.1,effective_number_beta=.9999,ema_decay=.5,
    focus_sampling_multiplier=1.5,amp=True,grad_scaler_init_scale=1024,torch_threads=4)
HAS_LOCK=False
LOCK_HANDLE=None


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def status(state,**values):
    save_json(OUT/'status.json',dict(state=state,pid=os.getpid(),updated_unix=time.time(),**values))


def atomic_save(payload,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.partial');torch.save(payload,temporary);os.replace(temporary,path)


def process_lock():
    global HAS_LOCK,LOCK_HANDLE
    import msvcrt
    handle=(OUT/'runner.lock').open('a+b')
    if handle.tell()==0:handle.write(b'0');handle.flush()
    handle.seek(0)
    try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        handle.close();raise RuntimeError('Another eight-disease focus runner is active')
    HAS_LOCK=True;LOCK_HANDLE=handle


def parent(architecture,fold):return RUN_ROOT/ARCHITECTURES[architecture].format(fold=fold)


def sample_rows(samples):
    return [dict(path=s.path.relative_to(ROOT).as_posix(),label=CLASSES[s.label],sha256=s.digest,group=s.group_id) for s in samples]


def sample_objects(rows):
    return [ImageSample(ROOT/r['path'],CLASSES.index(r['label']),r['sha256'],r['group']) for r in rows]


def sampling_weights(rows,branch):
    if branch not in BRANCHES:raise ValueError('Unknown sampling branch')
    if any(r['label'] not in CLASSES for r in rows):raise ValueError('Not an original eight-class label')
    return torch.tensor([CONFIG['focus_sampling_multiplier'] if branch=='focus' and r['label'] in FOCUS else 1. for r in rows],dtype=torch.float64)


def sample_indices(rows,branch,fold,epoch):
    return torch.multinomial(sampling_weights(rows,branch),len(rows),replacement=True,
        generator=torch.Generator().manual_seed(42+100*fold+epoch)).tolist()


def failures(candidate,reference):
    eps=1e-12;reasons=[]
    if candidate['macro_f1']<reference['macro_f1']-eps:reasons.append('macro_f1')
    if candidate['accuracy']<reference['accuracy']-.005-eps:reasons.append('accuracy')
    if candidate['per_class']['SkinCancer']['recall']<reference['per_class']['SkinCancer']['recall']-eps:reasons.append('SkinCancer_recall')
    for c in CLASSES:
        if c not in FOCUS and candidate['per_class'][c]['recall']<reference['per_class'][c]['recall']-.02-eps:
            reasons.append('recall_'+c)
    for c in FOCUS:
        if candidate['per_class'][c]['precision']<reference['per_class'][c]['precision']-.02-eps:
            reasons.append('precision_'+c)
    if np.mean([candidate['per_class'][c]['f1'] for c in FOCUS])<np.mean([reference['per_class'][c]['f1'] for c in FOCUS])-eps:
        reasons.append('mean_focus_f1')
    return reasons


def choose_method(validation):
    reference=validation['original_classwise'];eligible=[];details={}
    for name,m in validation.items():
        reasons=failures(m,reference);details[name]=dict(metrics=m,guard_failures=reasons)
        if not reasons:eligible.append(name)
    selected=sorted(eligible,key=lambda name:(
        -validation[name]['macro_f1'],-np.mean([validation[name]['per_class'][c]['f1'] for c in FOCUS]),
        -validation[name]['accuracy'],0 if name=='original_classwise' else 1,name))[0]
    return selected,details


def register():
    assert CLASSES==['Acne','Candidiasis','Eczema','Lupus','Psoriasis','SkinCancer','Tinea','Warts']
    state=read(ROOT/'ai-service/reports/active_research_track.json')
    assert state['active_track']=='original_eight' and state['classes']==CLASSES
    outer,samples,_=checked_outer_rows();inner=read(INNER);by_path={r['path']:r for r in outer['images']}
    assert inner['outer_manifest_sha256']==outer['manifest_sha256']
    folds=[]
    for f,plan in enumerate(inner['folds']):
        validation=set(plan['inner_validation_paths']);outer_paths=sorted(r['path'] for r in outer['images'] if r['fold']==f)
        training=sorted(p for p,r in by_path.items() if r['fold']!=f and p not in validation)
        roles=dict(train=training,inner_validation=plan['inner_validation_paths'],outer_holdout=outer_paths)
        groups={role:{by_path[p]['scene_or_case_group'] for p in paths} for role,paths in roles.items()}
        for a,b in [('train','inner_validation'),('train','outer_holdout'),('inner_validation','outer_holdout')]:assert groups[a].isdisjoint(groups[b])
        for role,paths in roles.items():
            assert len(paths)==plan[role+'_images']
            assert dict(Counter(by_path[p]['class'] for p in paths))==plan['class_images'][role]
        folds.append(dict(fold=f,roles=roles))
    sources={}
    for p in [OUTER,INNER,ROOT/'ai-service/reports/scene_grouped_oof_classwise_fusion_seed42.json',ROOT/'ai-service/models/best_model.pth']:
        sources[p.relative_to(ROOT).as_posix()]=sha256_file(p)
    for f in range(5):
        for a in ('efficientnet_b0','convnext_tiny'):
            for filename in ('best_model.pth','inner_predictions.json','oof_predictions.json','selection_report.json'):
                p=parent(a,f)/filename;sources[p.relative_to(ROOT).as_posix()]=sha256_file(p)
    names=['run_original_eight_focus_replay.py','common.py','train_v2.py',
        'evaluate_scene_grouped_oof_classwise_fusion.py','evaluate_scene_grouped_oof_ensemble.py','evaluate_evidence.py',
        'prepare_scene_grouped_oof_inner_splits.py','prepare_scene_grouped_oof_folds.py']
    protocol=dict(name=NAME,date='2026-10-20',classes=CLASSES,focus_classes=FOCUS,configuration=CONFIG,
        folds=folds,sources_sha256=sources,code_sha256={n:sha256_file(ROOT/'ai-service/training'/n) for n in names},
        outer_manifest_content_sha256=outer['manifest_sha256'],images=5937,
        initialization='Each branch/fold starts from that exact original-eight ConvNeXt fold checkpoint; no five-label checkpoint or cross-fold weights.',
        treatment='Uniform replacement replay versus replacement replay with1.5x per-image sampling weight for Lupus/Psoriasis/Tinea; same epoch draw count and all other settings.',
        fixed_budget='Four further epochs in each arm; final epoch is primary. Final raw/EMA chosen by inner MacroF1 only. Epoch histories are not searched for a test-best checkpoint.',
        fusion='Original B0 retained. Each new ConvNeXt is fused using the original conservative classwise rule fitted on all eight-class inner-validation predictions.',
        guard='Compared with original classwise inner validation: preserve MacroF1 and SkinCancer recall; accuracy loss<=0.005; nonfocus recall loss<=0.02; all three focus precision losses<=0.02; preserve mean focus F1.',
        selector='Eligible original/control/focus blends: maximize validation MacroF1, then mean focusF1, then accuracy, then prefer original on ties. Lock before any new outer inference.',
        primary='validation_selected; report fixed control/focus blends and singles separately, never choose using outer results.',
        numerical='AMP initial scale1024; count real optimizer updates. Abort on skipped updates or nonfinite loss rather than silently compare different update budgets.',
        limitations=['Previously studied original5937development images and weak-class outcomes; exploratory, not independent clinical testing.',
            'Repeating/oversampling existing images does not add new patients or fix uncertain source labels.',
            'One seed; known scene/case groups do not prove unknown patient independence.',
            'Four-epoch continuation compares sampling strategies, not a fresh ImageNet architecture study.',
            'No API/deployment change and no overwrite of original benchmarks or the completed five-class trial.'])
    p=OUT/'protocol.json'
    if p.exists():assert read(p)==protocol,'Frozen replay protocol/code/inputs changed'
    else:save_json(p,protocol)
    return outer,inner,protocol


def rows_for_fold(protocol,outer,fold):
    by_path={r['path']:r for r in outer['images']}
    return {role:[dict(path=p,label=by_path[p]['class'],sha256=by_path[p]['sha256'],group=by_path[p]['scene_or_case_group']) for p in paths]
            for role,paths in protocol['folds'][fold]['roles'].items()}


def infer(model,rows):
    loader=trainer.make_loader(ImageSampleDataset(sample_objects(rows),evaluation_transform()),16,False,0,True)
    model.eval();pp=[]
    with torch.inference_mode():
        for x,_ in loader:pp.append(model(x.cuda(non_blocking=True)).float().softmax(1).cpu().numpy())
    return np.concatenate(pp).astype(float)


def infer_checkpoint(path,rows):
    checkpoint=torch.load(path,map_location='cpu',weights_only=False)
    assert checkpoint['classes']==CLASSES and checkpoint['architecture']=='convnext_tiny'
    model=build_model('convnext_tiny',8,pretrained=False);model.load_state_dict(checkpoint['model_state_dict']);model.cuda()
    pp=infer(model,rows);del model,checkpoint;gc.collect();torch.cuda.empty_cache();return pp


def train_branch(fold,branch,roles):
    directory=MODELS/f'fold_{fold}'/branch;directory.mkdir(parents=True,exist_ok=True)
    protocol_sha=sha256_file(OUT/'protocol.json');initial=parent('convnext_tiny',fold)/'best_model.pth'
    if (directory/'training_report.json').exists():
        report=read(directory/'training_report.json')
        assert report['protocol_sha256']==protocol_sha and report['checkpoint_sha256']==sha256_file(directory/'final_model.pth')
        return directory
    seed_everything(42);cp=torch.load(initial,map_location='cpu',weights_only=False)
    assert cp['classes']==CLASSES and cp['architecture']=='convnext_tiny'
    model=build_model('convnext_tiny',8,pretrained=False);model.load_state_dict(cp['model_state_dict']);del cp;model.cuda()
    ema=copy.deepcopy(model).eval()
    for p in ema.parameters():p.requires_grad_(False)
    backbone,head=trainer.classifier_parameters(model)
    optimizer=torch.optim.AdamW([dict(params=backbone,lr=CONFIG['backbone_lr']),dict(params=head,lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=4,eta_min=1e-6)
    weights,_=trainer.effective_number_weights(sample_objects(roles['train']),CONFIG['effective_number_beta'],torch.device('cuda'))
    criterion=torch.nn.CrossEntropyLoss(weight=weights,label_smoothing=CONFIG['label_smoothing'])
    scaler=torch.amp.GradScaler('cuda',init_scale=CONFIG['grad_scaler_init_scale'])
    dataset=ImageSampleDataset(sample_objects(roles['train']),trainer.training_transform_v2())
    validation_loader=trainer.make_loader(ImageSampleDataset(sample_objects(roles['inner_validation']),evaluation_transform()),16,False,0,True)
    updates=[0]
    def count_step(*args,**kwargs):updates[0]+=1
    optimizer.register_step_post_hook(count_step)
    history=[];start=1;resume=directory/'resume_state.pth'
    if resume.exists():
        saved=torch.load(resume,map_location='cpu',weights_only=False);assert saved['protocol_sha256']==protocol_sha
        model.load_state_dict(saved['model']);ema.load_state_dict(saved['ema']);optimizer.load_state_dict(saved['optimizer'])
        scheduler.load_state_dict(saved['scheduler']);scaler.load_state_dict(saved['scaler'])
        history=saved['history'];updates[0]=saved['actual_updates'];start=saved['epoch']+1
        random.setstate(saved['random']);np.random.set_state(saved['numpy']);torch.set_rng_state(saved['torch']);torch.cuda.set_rng_state_all(saved['cuda'])
        print(json.dumps(dict(resume=True,fold=fold,branch=branch,next_epoch=start)),flush=True)
    for epoch in range(start,5):
        status('training',fold=fold,branch=branch,epoch=epoch,epochs_limit=4,completed_epochs=epoch-1)
        ids=sample_indices(roles['train'],branch,fold,epoch)
        loader=trainer.make_loader(Subset(dataset,ids),16,False,0,True)
        began=time.monotonic();before=updates[0]
        training=trainer.run_epoch(model,loader,criterion,torch.device('cuda'),optimizer,scaler)
        if updates[0]-before!=len(loader):raise FloatingPointError('AMP skipped update; inspect numerics before continuing')
        trainer.update_ema(ema,model,CONFIG['ema_decay'])
        raw=trainer.run_epoch(model,validation_loader,criterion,torch.device('cuda'))
        averaged=trainer.run_epoch(ema,validation_loader,criterion,torch.device('cuda'));scheduler.step()
        if not all(math.isfinite(m['loss']) for m in (training,raw,averaged)):raise FloatingPointError('Nonfinite loss')
        source='ema' if averaged['macro_f1']>=raw['macro_f1'] else 'raw'
        chosen=averaged if source=='ema' else raw
        history.append(dict(epoch=epoch,train=training,validation_raw=raw,validation_ema=averaged,selected_weights=source,
            actual_updates=updates[0]-before,attempted_updates=len(loader),seconds=time.monotonic()-began,
            sampled_class_counts=dict(Counter(roles['train'][j]['label'] for j in ids)),
            unique_sampled_images=len(set(ids)),draws=len(ids),draw_indices_sha256=hashlib.sha256(json.dumps(ids).encode()).hexdigest()))
        save_json(directory/'history.json',history)
        atomic_save(dict(protocol_sha256=protocol_sha,epoch=epoch,model=model.state_dict(),ema=ema.state_dict(),
            optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),scaler=scaler.state_dict(),history=history,actual_updates=updates[0],
            random=random.getstate(),numpy=np.random.get_state(),torch=torch.get_rng_state(),cuda=torch.cuda.get_rng_state_all()),resume)
        print(json.dumps(dict(fold=fold,branch=branch,epoch=epoch,validation_accuracy=chosen['accuracy'],validation_macro_f1=chosen['macro_f1'],seconds=history[-1]['seconds'])),flush=True)
    assert len(history)==4
    source=history[-1]['selected_weights'];selected=ema if source=='ema' else model
    atomic_save(dict(model_state_dict=selected.state_dict(),architecture='convnext_tiny',classes=CLASSES,
        research_only=True,protocol_sha256=protocol_sha,initial_checkpoint_sha256=sha256_file(initial),
        fold=fold,branch=branch,epoch=4,version=f'{NAME}-fold{fold}-{branch}',temperature=1.),directory/'final_model.pth')
    save_json(directory/'training_report.json',dict(protocol_sha256=protocol_sha,checkpoint_sha256=sha256_file(directory/'final_model.pth'),
        initial_checkpoint_sha256=sha256_file(initial),classes=CLASSES,fold=fold,branch=branch,epochs=4,
        total_actual_updates=updates[0],selected_weights=source,validation=history[-1]['validation_ema' if source=='ema' else 'validation_raw'],
        outer_used_for_selection=False))
    del model,ema,optimizer,dataset,validation_loader;gc.collect();torch.cuda.empty_cache();return directory


def predictions(directory,rows,role):
    path=directory/(role+'_predictions.json');checkpoint=directory/'final_model.pth'
    identity=dict(protocol_sha256=sha256_file(OUT/'protocol.json'),checkpoint_sha256=sha256_file(checkpoint),classes=CLASSES,paths=[r['path'] for r in rows])
    if path.exists():
        payload=read(path);assert all(payload[k]==v for k,v in identity.items());return np.asarray(payload['probabilities'])
    pp=infer_checkpoint(checkpoint,rows);save_json(path,dict(**identity,probabilities=pp.tolist()));return pp


def evaluate_fold(fold,roles,directories,outer,inner):
    directory=OUT/f'fold_{fold}';directory.mkdir(parents=True,exist_ok=True)
    b0,vy=aligned_inner_predictions('efficientnet_b0',fold,outer,inner)
    original,oy=aligned_inner_predictions('convnext_tiny',fold,outer,inner);assert np.array_equal(vy,oy)
    weights,details=choose_class_weights(b0,original,vy)
    vp={'original_classwise':classwise_blend(b0,original,weights)};locks={}
    for branch,modeldir in directories.items():
        new=predictions(modeldir,roles['inner_validation'],'inner_validation')
        w,d=choose_class_weights(b0,new,vy);locks[branch]=dict(weights=w.tolist(),details=d)
        vp[branch+'_classwise']=classwise_blend(b0,new,w)
    selected,trials=choose_method({name:score(pp,vy) for name,pp in vp.items()})
    lock=dict(protocol_sha256=sha256_file(OUT/'protocol.json'),fold=fold,selected=selected,trials=trials,
        original_weights=weights.tolist(),original_details=details,branch_weights=locks,
        checkpoint_sha256={b:sha256_file(d/'final_model.pth') for b,d in directories.items()})
    if (directory/'selection_locked.json').exists():assert read(directory/'selection_locked.json')==lock
    else:save_json(directory/'selection_locked.json',lock)
    status('evaluating_fold',fold=fold)
    expected={r['path']:r for r in outer['images'] if r['fold']==fold};paths=[r['path'] for r in roles['outer_holdout']]
    base={a:read_probabilities(a,fold,outer,expected) for a in ('efficientnet_b0','convnext_tiny')}
    b0t=np.stack([base['efficientnet_b0'][p] for p in paths]);ct=np.stack([base['convnext_tiny'][p] for p in paths])
    methods={'original_convnext':ct,'original_classwise':classwise_blend(b0t,ct,weights)}
    for branch,modeldir in directories.items():
        pp=predictions(modeldir,roles['outer_holdout'],'outer')
        methods[branch+'_convnext']=pp;methods[branch+'_classwise']=classwise_blend(b0t,pp,np.asarray(locks[branch]['weights']))
    methods['validation_selected']=methods[selected]
    y=np.asarray([CLASSES.index(r['label']) for r in roles['outer_holdout']])
    rows=[dict(**r,fold=fold,source='SCIN' if r['path'].startswith('SkinDisease/scin-v1/') else 'original_train',
        probabilities={name:pp[i].tolist() for name,pp in methods.items()}) for i,r in enumerate(roles['outer_holdout'])]
    save_json(directory/'predictions.json',rows)
    save_json(directory/'results.json',dict(fold=fold,selected=selected,images=len(rows),methods={name:score(pp,y) for name,pp in methods.items()}))
    print(json.dumps(dict(fold_complete=fold,selected=selected,metrics={name:{k:score(pp,y)[k] for k in ('accuracy','macro_f1')} for name,pp in methods.items()})),flush=True)


def finalize(protocol):
    rows=[]
    for f in range(5):rows.extend(read(OUT/f'fold_{f}/predictions.json'))
    rows.sort(key=lambda r:r['path']);assert len(rows)==len({r['path'] for r in rows})==5937
    y=np.asarray([CLASSES.index(r['label']) for r in rows]);sources=np.asarray([r['source'] for r in rows])
    pp={m:np.asarray([r['probabilities'][m] for r in rows]) for m in rows[0]['probabilities']}
    methods={name:score(p,y) for name,p in pp.items()}
    for name,p in pp.items():
        methods[name]['per_source']={s:source_score(p[sources==s],y[sources==s]) for s in ('original_train','SCIN')}
        methods[name]['mean_focus_f1']=float(np.mean([methods[name]['per_class'][c]['f1'] for c in FOCUS]))
    benchmark=read(ROOT/'ai-service/reports/scene_grouped_oof_classwise_fusion_seed42.json')['methods']['classwise_inner_fitted']
    for key in ('accuracy','macro_f1'):
        assert abs(methods['original_classwise'][key]-benchmark[key])<1e-12
    assert methods['original_classwise']['confusion_matrix']==benchmark['confusion_matrix']
    result=dict(status='complete_exploratory_original_eight_focus_replay',classes=CLASSES,focus_classes=FOCUS,images=5937,
        protocol_sha256=sha256_file(OUT/'protocol.json'),methods=methods,
        per_fold=[read(OUT/f'fold_{f}/results.json') for f in range(5)],
        paired_accuracy_95pct=paired_cluster_interval(pp['validation_selected'].argmax(1)==y,pp['original_classwise'].argmax(1)==y,[r['group'] for r in rows]),
        limitations=protocol['limitations'],serving_changed=False)
    save_json(OUT/'oof_predictions.json',rows);save_json(OUT/'results.json',result)
    summary(result);verify(protocol)
    status('complete',images=5937,results=str(OUT/'results.json'))
    print(json.dumps(dict(complete=True,results={m:{k:v[k] for k in ('accuracy','macro_f1','mean_focus_f1')} for m,v in methods.items()})),flush=True)


def summary(result):
    pct=lambda v:f'{100*v:.2f}%'
    lines=['# Huấn luyện tiếp tám bệnh với đối chứng','',
        'Giữ đủ tám nhãn. 5.937 ảnh phát triển OOF, cùng fold với đối chứng; chưa phải kiểm thử bệnh nhân mới.','',
        '| Phương án | Accuracy | Macro F1 | F1 trung bình Lupus/Psoriasis/Tinea | Recall SkinCancer |',
        '|---|---:|---:|---:|---:|']
    for name,m in result['methods'].items():
        lines.append(f"| {name} | {pct(m['accuracy'])} | {pct(m['macro_f1'])} | {pct(m['mean_focus_f1'])} | {pct(m['per_class']['SkinCancer']['recall'])} |")
    lines+=['','## Từng bệnh của lựa chọn theo validation','',
        '| Bệnh | Ảnh | Recall cũ | Recall mới | Precision cũ | Precision mới | F1 cũ | F1 mới |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for c in CLASSES:
        a=result['methods']['original_classwise']['per_class'][c];b=result['methods']['validation_selected']['per_class'][c]
        lines.append(f"| {c} | {a['support']} | "+' | '.join(pct(x) for x in (a['recall'],b['recall'],a['precision'],b['precision'],a['f1'],b['f1']))+' |')
    lines+=['','## Lựa chọn từng fold','']+[f"- Fold {f['fold']+1}: {f['selected']}." for f in result['per_fold']]
    lines+=['','## Hạn chế','']+['- '+s for s in result['limitations']]
    (OUT/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cm=np.asarray(result['methods']['validation_selected']['confusion_matrix']);fig,ax=plt.subplots(figsize=(10,8))
    im=ax.imshow(cm,cmap='Blues');ax.set_xticks(range(8),CLASSES,rotation=40,ha='right');ax.set_yticks(range(8),CLASSES)
    for i in range(8):
        for j in range(8):ax.text(j,i,str(cm[i,j]),ha='center',va='center',color='white' if cm[i,j]>cm.max()/2 else 'black')
    ax.set(xlabel='Predicted label',ylabel='Reference label',title='Eight diseases · validation-selected continuation · 5,937 development OOF images')
    fig.colorbar(im,ax=ax,label='Images');fig.tight_layout();fig.savefig(OUT/'confusion_matrix.png',dpi=200);plt.close(fig)


def verify(protocol):
    for p,h in protocol['sources_sha256'].items():assert sha256_file(ROOT/p)==h,p
    for p,h in protocol['code_sha256'].items():assert sha256_file(ROOT/'ai-service/training'/p)==h,p
    result=read(OUT/'results.json');assert result['classes']==CLASSES and result['images']==5937
    rows=read(OUT/'oof_predictions.json');assert len(rows)==len({r['path'] for r in rows})==5937
    for f in range(5):
        for b in BRANCHES:
            d=MODELS/f'fold_{f}'/b;report=read(d/'training_report.json');history=read(d/'history.json')
            assert report['classes']==CLASSES and report['outer_used_for_selection'] is False
            assert report['checkpoint_sha256']==sha256_file(d/'final_model.pth')
            assert len(history)==4 and all(h['actual_updates']==h['attempted_updates'] for h in history)
    for m in result['methods'].values():assert np.asarray(m['confusion_matrix']).sum()==5937
    save_json(OUT/'verification.json',dict(status='PASS',scope='Technical consistency, not clinical approval',
        results_sha256=sha256_file(OUT/'results.json'),protocol_sha256=sha256_file(OUT/'protocol.json'),
        trained_continuations=10,original_sources_unchanged=True,serving_changed=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--verify-only',action='store_true');args=parser.parse_args()
    torch.set_num_threads(4);outer,inner,protocol=register()
    if args.prepare_only:
        if not (OUT/'status.json').exists():status('prepared',images=5937,training_started=False)
        print(json.dumps(dict(prepared=True,classes=CLASSES,images=5937,branches=BRANCHES,folds=5,epochs_per_branch=4)),flush=True);return
    if args.verify_only:verify(protocol);print('PASS',flush=True);return
    process_lock()
    if (OUT/'results.json').exists():verify(protocol);status('complete',already_complete=True);return
    assert torch.cuda.is_available(),'CUDA GPU required'
    for f in range(5):
        if (OUT/f'fold_{f}/results.json').exists():continue
        roles=rows_for_fold(protocol,outer,f)
        if not (OUT/f'fold_{f}/parent_reproduction.json').exists():
            status('checking_parent',fold=f)
            initial=infer_checkpoint(parent('convnext_tiny',f)/'best_model.pth',roles['inner_validation'])
            cached,y=aligned_inner_predictions('convnext_tiny',f,outer,inner)
            assert np.allclose(initial,cached,rtol=1e-4,atol=2e-5),'Original parent inference changed'
            save_json(OUT/f'fold_{f}/parent_reproduction.json',dict(status='PASS',max_absolute_probability_difference=float(np.max(np.abs(initial-cached)))))
        directories={b:train_branch(f,b,roles) for b in BRANCHES}
        evaluate_fold(f,roles,directories,outer,inner)
    status('summarizing');finalize(protocol)


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        if HAS_LOCK:status('interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error=repr(exc))
        raise
