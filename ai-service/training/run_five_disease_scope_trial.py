"""Train two fresh five-disease model families across the fixed five folds.

Run with --prepare-only to audit and register; without flags to train, evaluate,
verify and generate the final comparison automatically. Interrupted epochs can
resume from the last completed epoch; all random states are saved (workers=0).
"""
from __future__ import annotations

import argparse
import copy
import csv
import gc
import json
import math
import os
import random
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

import train_v2 as trainer
import five_disease_scope_trial as trial
from common import build_model, evaluation_transform, ImageSampleDataset, save_json, seed_everything, sha256_file

HAS_RUN_LOCK=False
RUN_LOCK_HANDLE=None


def acquire_run_lock():
    global HAS_RUN_LOCK,RUN_LOCK_HANDLE
    import msvcrt
    trial.OUT.mkdir(parents=True,exist_ok=True)
    handle=(trial.OUT/'runner.lock').open('a+b')
    if handle.tell()==0:handle.write(b'0');handle.flush()
    handle.seek(0)
    try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        handle.close();raise RuntimeError('Another five-disease training process holds the run lock')
    RUN_LOCK_HANDLE=handle;HAS_RUN_LOCK=True


def write_status(state, **kw):
    save_json(trial.OUT/'status.json',dict(state=state,pid=os.getpid(),updated_unix=time.time(),**kw))


def atomic_torch_save(payload, path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.partial')
    torch.save(payload, temporary); os.replace(temporary,path)


def infer(model, rows, batch_size, device):
    loader=trainer.make_loader(ImageSampleDataset(trial.samples(rows),evaluation_transform()),batch_size,False,0,True)
    result=[]; model.eval()
    with torch.inference_mode():
        for x,_ in loader:
            p=model(x.to(device,non_blocking=True)).float().softmax(1)
            result.append(p.cpu().numpy())
    return trial.normalized(np.concatenate(result))


def train_one(architecture, fold, roles, protocol):
    directory=trial.MODELS/architecture/f'fold_{fold}'; directory.mkdir(parents=True,exist_ok=True)
    lock_sha=sha256_file(trial.OUT/'protocol.json')
    if (directory/'selection_report.json').exists():
        report=trial.read(directory/'selection_report.json')
        if report['protocol_sha256']!=lock_sha or report['checkpoint_sha256']!=sha256_file(directory/'best_model.pth'):
            raise ValueError('Completed checkpoint identity changed')
        return directory
    trainer.CLASSES=list(trial.FIVE)  # Module-local metric labels; no frozen source files are edited.
    seed_everything(42); device=torch.device('cuda'); config=trial.RECIPES[architecture]
    model=build_model(architecture,len(trial.FIVE),pretrained=True).to(device)
    ema=copy.deepcopy(model).eval()
    for p in ema.parameters():p.requires_grad_(False)
    backbone,head=trainer.classifier_parameters(model)
    for p in backbone:p.requires_grad_(False)
    optimizer=torch.optim.AdamW([dict(params=backbone,lr=config['learning_rate']*config['backbone_lr_ratio']),
        dict(params=head,lr=config['learning_rate'])],weight_decay=config['weight_decay'])
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=22,eta_min=1e-6)
    counts=np.asarray([sum(x['class']==c for x in roles['train']) for c in trial.FIVE],dtype=float)
    beta=config['effective_number_beta']; weights=(1-beta)/(1-np.power(beta,counts)); weights/=weights.mean()
    loss=torch.nn.CrossEntropyLoss(weight=torch.tensor(weights,dtype=torch.float32,device=device),label_smoothing=config['label_smoothing'])
    scaler=torch.amp.GradScaler('cuda'); loaders={}
    for role in ('train','inner_validation'):
        transform=trainer.training_transform_v2() if role=='train' else evaluation_transform()
        loaders[role]=trainer.make_loader(ImageSampleDataset(trial.samples(roles[role]),transform),config['batch_size'],role=='train',0,True)
    history=[]; best=None; stale=0; start=1;updates=[0]
    def count_step(*args,**kwargs):updates[0]+=1
    optimizer.register_step_post_hook(count_step)
    resume=directory/'resume_state.pth'
    if resume.exists():
        saved=torch.load(resume,map_location='cpu',weights_only=False)
        if saved['protocol_sha256']!=lock_sha:raise ValueError('Resume protocol changed')
        model.load_state_dict(saved['model']); ema.load_state_dict(saved['ema']); optimizer.load_state_dict(saved['optimizer'])
        scheduler.load_state_dict(saved['scheduler']); scaler.load_state_dict(saved['scaler'])
        history,best,stale=saved['history'],saved['best'],saved['stale']; start=saved['epoch']+1
        updates[0]=saved['actual_optimizer_updates']
        atomic_torch_save(saved['best_checkpoint'],directory/'best_model.pth')
        random.setstate(saved['random']); np.random.set_state(saved['numpy']); torch.set_rng_state(saved['torch'])
        torch.cuda.set_rng_state_all(saved['cuda'])
        if start>3:
            for p in backbone:p.requires_grad_(True)
        print(json.dumps(dict(resume=architecture,fold=fold,next_epoch=start)),flush=True)
    print(json.dumps(dict(start=architecture,fold=fold,train=len(roles['train']),validation=len(roles['inner_validation']))),flush=True)
    for epoch in range(start,25):
        if epoch>2 and stale>=config['patience']:break
        if epoch==3:
            for p in backbone:p.requires_grad_(True)
        write_status('training',architecture=architecture,fold=fold,epoch=epoch,epochs_limit=24,completed_epochs=epoch-1)
        began=time.monotonic()
        updates_before=updates[0]
        training=trainer.run_epoch(model,loaders['train'],loss,device,optimizer,scaler)
        trainer.update_ema(ema,model,config['ema_decay'])
        raw=trainer.run_epoch(model,loaders['inner_validation'],loss,device)
        averaged=trainer.run_epoch(ema,loaders['inner_validation'],loss,device)
        if epoch>2:scheduler.step()
        source='ema' if averaged['macro_f1']>=raw['macro_f1'] else 'raw'
        validation=averaged if source=='ema' else raw
        if not all(math.isfinite(v['loss']) for v in (training,raw,averaged)):
            raise FloatingPointError('Nonfinite training/validation loss; no silent checkpoint selection')
        key=[validation['macro_f1'],validation['top3_accuracy'],-validation['loss']]
        improved=best is None or tuple(key)>tuple(best['objective'])
        if improved:
            best=dict(epoch=epoch,source=source,objective=key,validation=validation)
            checkpoint=dict(model_state_dict={k:v.detach().cpu().clone() for k,v in (ema if source=='ema' else model).state_dict().items()},
                architecture=architecture,classes=trial.FIVE,version=f'{trial.NAME}-{architecture}-fold{fold}',
                research_only=True,protocol_sha256=lock_sha,epoch=epoch,input_size=224,temperature=1.,pretrained=True)
            atomic_torch_save(checkpoint,directory/'best_model.pth'); stale=0
        else:stale+=1
        history.append(dict(epoch=epoch,train=training,validation_raw=raw,validation_ema=averaged,
            selected_weights=source,selected_new_best=improved,backbone_frozen=epoch<=2,
            actual_optimizer_updates=updates[0]-updates_before,attempted_optimizer_updates=len(loaders['train']),
            seconds=time.monotonic()-began,learning_rates=[g['lr'] for g in optimizer.param_groups]))
        save_json(directory/'history.json',history)
        best_checkpoint=torch.load(directory/'best_model.pth',map_location='cpu',weights_only=False)
        atomic_torch_save(dict(protocol_sha256=lock_sha,epoch=epoch,model=model.state_dict(),ema=ema.state_dict(),
            optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),scaler=scaler.state_dict(),
            history=history,best=best,stale=stale,best_checkpoint=best_checkpoint,actual_optimizer_updates=updates[0],
            random=random.getstate(),numpy=np.random.get_state(),torch=torch.get_rng_state(),cuda=torch.cuda.get_rng_state_all()),resume)
        print(json.dumps(dict(architecture=architecture,fold=fold,epoch=epoch,
            validation_accuracy=validation['accuracy'],validation_macro_f1=validation['macro_f1'],
            best_epoch=best['epoch'],seconds=history[-1]['seconds'])),flush=True)
    if best is None:raise RuntimeError('No selected checkpoint')
    save_json(directory/'selection_report.json',dict(architecture=architecture,fold=fold,classes=trial.FIVE,
        protocol_sha256=lock_sha,checkpoint_sha256=sha256_file(directory/'best_model.pth'),best=best,
        epochs_completed=len(history),selection_role='inner_validation_only',outer_used_for_selection=False))
    del model,ema,optimizer,loaders
    gc.collect(); torch.cuda.empty_cache()
    return directory


def load_prediction_file(path, rows):
    payload=trial.read(path)
    if payload['classes']!=trial.FIVE or payload['paths']!=[r['path'] for r in rows]:
        raise ValueError('Prediction row alignment changed')
    if payload['protocol_sha256']!=sha256_file(trial.OUT/'protocol.json'):
        raise ValueError('Prediction protocol changed')
    if payload['checkpoint_sha256']!=sha256_file(Path(path).parent/'best_model.pth'):
        raise ValueError('Prediction checkpoint changed')
    p=trial.normalized(payload['probabilities'])
    if p.shape!=(len(rows),5):raise ValueError('Prediction shape changed')
    return p


def prediction_file(directory, rows, name):
    path=directory/(name+'.json')
    if path.exists():return load_prediction_file(path,rows)
    checkpoint=torch.load(directory/'best_model.pth',map_location='cpu',weights_only=False)
    model=build_model(checkpoint['architecture'],5,pretrained=False).to('cuda')
    model.load_state_dict(checkpoint['model_state_dict'])
    p=infer(model,rows,trial.RECIPES[checkpoint['architecture']]['batch_size'],torch.device('cuda'))
    save_json(path,dict(classes=trial.FIVE,protocol_sha256=sha256_file(trial.OUT/'protocol.json'),
        checkpoint_sha256=sha256_file(directory/'best_model.pth'),paths=[r['path'] for r in rows],probabilities=p.tolist()))
    del model; gc.collect(); torch.cuda.empty_cache()
    return p


def evaluate_fold(fold, roles, outer, inner, directories):
    folder=trial.OUT/f'fold_{fold}';folder.mkdir(parents=True,exist_ok=True)
    vrows=roles['inner_validation']; truth=[r['class'] for r in vrows]
    vp={a:prediction_file(d,vrows,'inner_predictions') for a,d in directories.items()}
    w,details=trial.classwise_weights(vp['efficientnet_b0'],vp['convnext_tiny'],[trial.FIVE.index(c) for c in truth])
    lock=dict(fold=fold,protocol_sha256=sha256_file(trial.OUT/'protocol.json'),weights=w.tolist(),details=details,
        checkpoint_sha256={a:sha256_file(d/'best_model.pth') for a,d in directories.items()},
        inner_metrics={a:trial.metrics(p,truth) for a,p in vp.items()},
        inner_classwise=trial.metrics(trial.blend(vp['efficientnet_b0'],vp['convnext_tiny'],w),truth))
    if (folder/'selection_locked.json').exists():
        if trial.read(folder/'selection_locked.json')!=lock:raise ValueError('Validation fusion lock changed')
    else:save_json(folder/'selection_locked.json',lock)
    # Only now produce/read outer predictions. Nothing below changes training or fusion.
    write_status('evaluating_fold',fold=fold)
    rows=sorted(roles['outer_holdout']+roles['out_of_scope'],key=lambda r:r['path'])
    tp={a:prediction_file(d,rows,'outer_predictions') for a,d in directories.items()}
    tp['five_b0']=tp.pop('efficientnet_b0');tp['five_convnext']=tp.pop('convnext_tiny')
    tp['five_equal']=(tp['five_b0']+tp['five_convnext'])/2
    tp['five_classwise_inner_fitted']=trial.blend(tp['five_b0'],tp['five_convnext'],w)
    paths=[r['path'] for r in rows]
    old={a:trial.old_probabilities(a,fold,'outer_holdout',paths,outer) for a in directories}
    all_inner=inner['folds'][fold]['inner_validation_paths'];by_path={r['path']:r for r in outer['images']}
    old_v={a:trial.old_probabilities(a,fold,'inner_validation',all_inner,outer) for a in directories}
    ow,_=trial.classwise_weights(old_v['efficientnet_b0'],old_v['convnext_tiny'],
        [trial.EIGHT.index(by_path[p]['class']) for p in all_inner],trial.EIGHT)
    tp['old_eight_b0_full_decision']=old['efficientnet_b0']
    tp['old_eight_convnext_full_decision']=old['convnext_tiny']
    tp['old_eight_classwise_full_decision']=trial.blend(old['efficientnet_b0'],old['convnext_tiny'],ow)
    tp['old_eight_classwise_restricted_to_five']=trial.restrict_eight(tp['old_eight_classwise_full_decision'])
    payload=[dict(path=r['path'],class_name=r['class'],source=trial.source_name(r),group=r['scene_or_case_group'],fold=fold,
        probabilities={m:p[i].tolist() for m,p in tp.items()}) for i,r in enumerate(rows)]
    save_json(folder/'predictions.json',payload)
    mask=np.asarray([r['class'] in trial.FIVE for r in rows]); y=np.asarray([r['class'] for r in rows])
    results={m:trial.metrics(p[mask],y[mask],trial.EIGHT if p.shape[1]==8 else trial.FIVE) for m,p in tp.items()}
    result=dict(fold=fold,images=int(mask.sum()),out_of_scope_images=int((~mask).sum()),methods=results,
        out_of_scope=trial.out_of_scope(tp['five_classwise_inner_fitted'][~mask],y[~mask],tp['five_classwise_inner_fitted'][mask],y[mask]))
    save_json(folder/'results.json',result)
    print(json.dumps(dict(fold_complete=fold,images=result['images'],five_accuracy=results['five_classwise_inner_fitted']['accuracy'],
        old_accuracy=results['old_eight_classwise_full_decision']['accuracy'])),flush=True)


def paired_intervals(rows, newer, older):
    groups=np.asarray([r['group'] for r in rows]); _,inv=np.unique(groups,return_inverse=True)
    y=np.asarray([trial.FIVE.index(r['class_name']) for r in rows]); n=len(rows)
    a=np.asarray([trial.EIGHT.index(trial.FIVE[i]) for i in newer.argmax(1)])
    b=older.argmax(1); y8=np.asarray([trial.EIGHT.index(trial.FIVE[i]) for i in y])
    g=int(inv.max()+1); ac=np.zeros((g,5,8));bc=np.zeros_like(ac)
    np.add.at(ac,(inv,y,a),1);np.add.at(bc,(inv,y,b),1)
    def summarize(cm):
        cols=[trial.EIGHT.index(c) for c in trial.FIVE];tp=cm[np.arange(5),cols]
        f1=np.divide(2*tp,cm.sum(1)+cm[:,cols].sum(0),out=np.zeros(5),where=(cm.sum(1)+cm[:,cols].sum(0))>0)
        return float(tp.sum()/cm.sum()),float(f1.mean())
    rng=np.random.default_rng(42);delta=[]
    for _ in range(1000):
        drawn=rng.integers(0,g,size=g);aa=summarize(ac[drawn].sum(0));bb=summarize(bc[drawn].sum(0))
        delta.append([aa[0]-bb[0],aa[1]-bb[1]])
    ci=np.quantile(np.asarray(delta),[.025,.975],axis=0)
    return dict(bootstrap_unit='known_case_or_scene',repetitions=1000,
        accuracy_difference_95pct=ci[:,0].tolist(),macro_f1_difference_95pct=ci[:,1].tolist())


def finalize(protocol):
    rows=[]
    for f in range(5):rows.extend(trial.read(trial.OUT/f'fold_{f}/predictions.json'))
    rows.sort(key=lambda r:r['path'])
    if len(rows)!=5937 or len({r['path'] for r in rows})!=5937:raise ValueError('Incomplete OOF rows')
    known=[r for r in rows if r['class_name'] in trial.FIVE]; unknown=[r for r in rows if r['class_name'] in trial.REMOVED]
    y=[r['class_name'] for r in known];uy=[r['class_name'] for r in unknown]
    names=list(rows[0]['probabilities']);p={m:trial.normalized([r['probabilities'][m] for r in known]) for m in names}
    methods={m:trial.metrics(a,y,trial.EIGHT if a.shape[1]==8 else trial.FIVE) for m,a in p.items()}
    for name,a in p.items():
        methods[name]['per_source']={}
        for source in sorted({r['source'] for r in known}):
            mask=np.asarray([r['source']==source for r in known])
            methods[name]['per_source'][source]=trial.metrics(a[mask],np.asarray(y)[mask],trial.EIGHT if a.shape[1]==8 else trial.FIVE)
    primary=p['five_classwise_inner_fitted'];baseline=p['old_eight_classwise_full_decision']
    result=dict(status='complete_exploratory_five_disease_scope_trial',classes=trial.FIVE,removed_classes=trial.REMOVED,
        images=len(known),out_of_scope_images=len(unknown),protocol_sha256=sha256_file(trial.OUT/'protocol.json'),
        methods=methods,paired_against_old_eight=paired_intervals(known,primary,baseline),
        out_of_scope=trial.out_of_scope([r['probabilities']['five_classwise_inner_fitted'] for r in unknown],uy,primary,y),
        per_fold=[trial.read(trial.OUT/f'fold_{f}/results.json') for f in range(5)],
        limitations=protocol['limitations'],serving_changed=False,original_eight_benchmark_changed=False)
    save_json(trial.OUT/'results.json',result);save_json(trial.OUT/'oof_predictions.json',rows)
    with (trial.OUT/'common_five_predictions.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.writer(handle);writer.writerow(['path','truth','source','fold']+[m for m in names])
        for r in known:writer.writerow([r['path'],r['class_name'],r['source'],r['fold']]+[
            (trial.EIGHT if len(r['probabilities'][m])==8 else trial.FIVE)[int(np.argmax(r['probabilities'][m]))] for m in names])
    write_summary(result)
    verify(protocol)
    write_status('complete',images=len(known),out_of_scope_images=len(unknown),results=str(trial.OUT/'results.json'))
    print(json.dumps(dict(complete=True,images=len(known),methods={m:{k:v[k] for k in ('accuracy','macro_f1')} for m,v in methods.items()})),flush=True)


def write_summary(result):
    def pct(v):return f'{100*v:.2f}%'
    lines=['# Thử nghiệm thu hẹp còn năm bệnh','',
        '**Đánh giá phát triển có đối chứng; chưa phải test độc lập hoặc mô hình đã triển khai.**','',
        'Năm bệnh: '+', '.join(trial.FIVE)+'.',
        'Cùng 3.736 ảnh đánh giá OOF; 2.201 ảnh Lupus/Psoriasis/Tinea chỉ dùng để kiểm tra ngoài phạm vi.',
        'Không so trực tiếp các điểm dưới đây với Accuracy 78,07% trên toàn bộ 5.937 ảnh tám bệnh.','',
        '| Phương án | Số ảnh | Accuracy | Macro F1 | Recall SkinCancer |',
        '|---|---:|---:|---:|---:|']
    for name,m in result['methods'].items():
        lines.append(f"| {name} | {m['images']} | {pct(m['accuracy'])} | {pct(m['macro_f1'])} | {pct(m['per_class']['SkinCancer']['recall'])} |")
    lines+=['','## Từng bệnh của bộ gộp năm nhãn','','| Bệnh | Số ảnh | Precision | Recall | F1 |','|---|---:|---:|---:|---:|']
    for c,m in result['methods']['five_classwise_inner_fitted']['per_class'].items():
        lines.append(f"| {c} | {m['support']} | {pct(m['precision'])} | {pct(m['recall'])} | {pct(m['f1'])} |")
    lines+=['','## Ảnh ngoài phạm vi','','| Bệnh thật bị loại | Số ảnh | Acne | Candidiasis | Eczema | SkinCancer | Warts |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for c,m in result['out_of_scope']['by_class'].items():
        lines.append(f"| {c} | {m['images']} | "+' | '.join(str(m['forced_predictions'][x]) for x in trial.FIVE)+' |')
    lines+=['','Các cột trên là dự đoán buộc chọn một trong năm nhãn; không phải nhận diện đúng ba bệnh bị loại.',
        'Ngưỡng độ tin cậy cố định chỉ là phép kiểm tra; chưa có cơ chế từ chối ngoài phạm vi được xác nhận.','',
        '## Hạn chế','']+['- '+x for x in result['limitations']]
    (trial.OUT/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Scientific figures are generated directly from stored numeric predictions.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    m=result['methods']['five_classwise_inner_fitted'];cm=np.asarray(m['confusion_matrix'])
    fig,ax=plt.subplots(figsize=(8,7));im=ax.imshow(cm,cmap='Blues')
    ax.set_xticks(range(5),trial.FIVE,rotation=35,ha='right');ax.set_yticks(range(5),trial.FIVE)
    for i in range(5):
        for j in range(5):ax.text(j,i,str(cm[i,j]),ha='center',va='center',color='white' if cm[i,j]>cm.max()/2 else 'black')
    ax.set(xlabel='Predicted label',ylabel='Reference label',title='Five-disease ensemble · 3,736 development OOF images')
    fig.colorbar(im,ax=ax,label='Images');fig.tight_layout();fig.savefig(trial.OUT/'five_disease_confusion_matrix.png',dpi=200);plt.close(fig)
    ood=np.asarray([[result['out_of_scope']['by_class'][c]['forced_predictions'][p] for p in trial.FIVE] for c in trial.REMOVED])
    fig,ax=plt.subplots(figsize=(8,4.5));im=ax.imshow(ood,cmap='Oranges',aspect='auto')
    ax.set_xticks(range(5),trial.FIVE,rotation=30,ha='right');ax.set_yticks(range(3),trial.REMOVED)
    for i in range(3):
        for j in range(5):ax.text(j,i,str(ood[i,j]),ha='center',va='center',color='white' if ood[i,j]>ood.max()/2 else 'black')
    ax.set(xlabel='Forced five-class prediction',ylabel='Removed reference diagnosis',title='2,201 removed-disease images · out-of-scope stress test')
    fig.colorbar(im,ax=ax,label='Images');fig.tight_layout();fig.savefig(trial.OUT/'removed_disease_assignments.png',dpi=200);plt.close(fig)


def verify(protocol):
    for path,expected in protocol['sources_sha256'].items():
        if sha256_file(trial.ROOT/path)!=expected:raise ValueError(f'Original input changed: {path}')
    for name,expected in protocol['code_sha256'].items():
        if sha256_file(trial.ROOT/'ai-service/training'/name)!=expected:raise ValueError(f'Locked code changed: {name}')
    result=trial.read(trial.OUT/'results.json')
    assert result['images']==3736 and result['out_of_scope_images']==2201
    for m in result['methods'].values():
        assert m['images']==3736 and sum(x['support'] for x in m['per_class'].values())==3736
        assert np.asarray(m['confusion_matrix']).sum()==3736
    assert sum(x['images'] for x in result['out_of_scope']['by_class'].values())==2201
    for f in range(5):
        roles=trial.roles_for_fold(trial.read(trial.OUTER)['images'],trial.read(trial.INNER),f)
        for arch in trial.RECIPES:
            directory=trial.MODELS/arch/f'fold_{f}'
            selection=trial.read(directory/'selection_report.json')
            assert selection['outer_used_for_selection'] is False and selection['classes']==trial.FIVE
            assert selection['checkpoint_sha256']==sha256_file(directory/'best_model.pth')
    save_json(trial.OUT/'verification.json',dict(status='PASS',scope='Technical consistency only, not clinical performance approval.',
        protocol_sha256=sha256_file(trial.OUT/'protocol.json'),results_sha256=sha256_file(trial.OUT/'results.json'),
        common_images=3736,out_of_scope_images=2201,trained_checkpoints=10,original_sources_unchanged=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--verify-only',action='store_true');args=parser.parse_args()
    torch.set_num_threads(4)
    outer,inner,protocol=trial.prepare()
    if args.prepare_only:
        if not (trial.OUT/'status.json').exists():write_status('prepared',images=3736,out_of_scope_images=2201,training_started=False)
        print(json.dumps(dict(prepared=True,images=3736,out_of_scope=2201,
            folds=[dict(fold=f['fold'],counts={r:sum(v.values()) for r,v in f['counts'].items()}) for f in protocol['folds']])),flush=True);return
    if args.verify_only:verify(protocol);print('PASS',flush=True);return
    acquire_run_lock()
    if (trial.OUT/'results.json').exists():
        verify(protocol);write_status('complete',already_complete=True);print('Already complete and verified',flush=True);return
    if not torch.cuda.is_available():raise RuntimeError('CUDA GPU required for this registered run')
    # Decode audit happens before training, so a corrupt image cannot silently shrink a cohort.
    audit=trial.OUT/'image_decode_audit.json'
    if not audit.exists():
        for r in outer['images']:
            with Image.open(trial.ROOT/r['path']) as image:image.convert('RGB').load()
        save_json(audit,dict(images=5937,decode_errors=0,protocol_sha256=sha256_file(trial.OUT/'protocol.json')))
    for f in range(5):
        if (trial.OUT/f'fold_{f}/results.json').exists():continue
        roles=trial.roles_for_fold(outer['images'],inner,f)
        directories={a:train_one(a,f,roles,protocol) for a in trial.RECIPES}
        evaluate_fold(f,roles,outer,inner,directories)
    write_status('summarizing');finalize(protocol)


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        if HAS_RUN_LOCK:write_status('interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error=repr(exc))
        raise
