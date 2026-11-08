"""Return to original eight diagnoses; a registered grouped-fold0 ResNet pilot.

Use only original scene/case manifests and old B0/ConvNeXt fold0 parents.
No serving changes and no new-eight dataset/model dependencies.
"""
import argparse
import copy
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from common import CLASSES,ImageSample,ImageSampleDataset,build_model,evaluation_transform,save_json,sha256_file,seed_everything
import train_v2 as trainer
from prepare_scene_grouped_oof_inner_splits import checked_outer_rows,OUTPUT as INNER
from prepare_scene_grouped_oof_folds import OUTPUT as OUTER
from evaluate_scene_grouped_oof_ensemble import ARCHITECTURES,RUN_ROOT,read_probabilities,score,paired_cluster_interval
from evaluate_scene_grouped_oof_classwise_fusion import aligned_inner_predictions,choose_class_weights,classwise_blend

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'ai-service/reports/original_eight_resnet50_pilot_fold0_seed42'
MODEL=ROOT/'ai-service/candidates/original_eight_resnet50_pilot_fold0_seed42'
CONFIG=dict(architecture='resnet50',max_epochs=24,freeze_epochs=2,batch_size=16,workers=2,learning_rate=.0002,
            backbone_lr_ratio=.25,weight_decay=.0002,label_smoothing=.05,effective_number_beta=.999,ema_decay=.995,patience=7,seed=42)
PARENTS=('efficientnet_b0','convnext_tiny'); REFERENCE='old_classwise'; NEW='resnet50'


def read(path): return json.loads(path.read_text(encoding='utf-8'))


def register():
    outer,samples,_=checked_outer_rows(); inner=read(INNER); plan=inner['folds'][0]
    assert inner['outer_manifest_sha256']==outer['manifest_sha256']
    inner_paths=set(plan['inner_validation_paths']); rows={r['path']:r for r in outer['images']}
    roles={r:[] for r in ('train','inner_validation','outer_holdout')}
    for sample in samples:
        path=sample.path.relative_to(ROOT).as_posix(); row=rows[path]
        role='outer_holdout' if row['fold']==0 else ('inner_validation' if path in inner_paths else 'train')
        roles[role].append(sample)
    for role,items in roles.items(): assert len(items)==plan[role+'_images']
    groups={r:{s.group_id or s.digest for s in items} for r,items in roles.items()}
    for a,b in [('train','inner_validation'),('train','outer_holdout'),('inner_validation','outer_holdout')]: assert groups[a].isdisjoint(groups[b])
    dependencies=('pilot_original_eight_resnet50.py','common.py','train_v2.py','prepare_scene_grouped_oof_inner_splits.py',
                  'evaluate_scene_grouped_oof_ensemble.py','evaluate_scene_grouped_oof_classwise_fusion.py')
    sources={}
    for m in PARENTS:
        folder=RUN_ROOT/ARCHITECTURES[m].format(fold=0)
        for n in ('best_model.pth','inner_predictions.json','oof_predictions.json','selection_report.json','dataset_summary.json'):
            p=folder/n; sources[str(p.relative_to(ROOT))]=sha256_file(p)
    weights=Path(torch.hub.get_dir())/'checkpoints/resnet50-11ad3fa6.pth'; assert weights.exists()
    protocol=dict(status='registered_original_eight_resnet50_pilot_reused_fold0',classes=CLASSES,configuration=CONFIG,
        outer_manifest_sha256=sha256_file(OUTER),inner_plan_sha256=sha256_file(INNER),manifest_content_sha256=outer['manifest_sha256'],
        sources=sources,pretrained_sha256=sha256_file(weights),code_sha256={n:sha256_file(ROOT/'ai-service/training'/n) for n in dependencies},
        roles={r:[s.path.relative_to(ROOT).as_posix() for s in items] for r,items in roles.items()},
        initialization='Fresh torchvision ImageNet V2 ResNet50, replace8-way fc; never load new-eight or historical skin-trained ResNet weights.',
        recipe='Original train_v2 transforms, effective-number weighted smoothed CE, AdamW, progressive2-epoch freeze then full fine-tune, cosine scheduler and once-per-epoch EMA. Same images/roles as old parents; batch16/architecture and optimizer budget differ from B0, not a compute-matched causal architecture comparison.',
        batchnorm='Train mode updates BatchNorm statistics even in2-epoch parameter freeze; EMA averages floating buffers once per epoch. Evaluation always eval mode.',
        checkpoint_selection='Original validation MacroF1 then Top3 then lower weighted CE; EMA chosen when MacroF1 ties raw; patience7 after warmup, max24.',
        family='Nine fixed candidates: B0, ConvNeXt, newResNet, original classwise reference, three reference/ResNet global weights .25/.5/.75, prior paired-count classwise reference/ResNet, equal3 models.',
        guard='On validation: SkinCancer recall>=reference; MacroF1>=reference; Accuracy>=reference-.005; each non-target recall>=reference-.02; target precision>=reference-.02. Reference is fallback.',
        fusion_selection='Among guarded validation candidates maximize minimum Lupus/Psoriasis recall, average targetF1, overallMacroF1, Accuracy, lower complexity and lexical name. Lock before any outer probability access/new inference.',
        limitations=['Exploratory return to previously inspected development cohort; not independent external test.',
                      'One outer fold only; do not replace the5937-photo five-fold benchmark with its pilot score.',
                      'Known SCIN case/scene groups are preserved; many original photos lack verified patient IDs.',
                      'No labels/images deleted, no new-eight inputs, no serving checkpoint changes.'],
        literature={'paper':'https://arxiv.org/abs/1512.03385','implementation':'https://docs.pytorch.org/vision/0.20/models/generated/torchvision.models.resnet50.html'})
    if (OUT/'protocol.json').exists(): assert read(OUT/'protocol.json')==protocol,'Preserve registered pilot'
    else: save_json(OUT/'protocol.json',protocol)
    return outer,inner,roles,protocol


def train(roles,protocol):
    MODEL.mkdir(parents=True,exist_ok=True); seed_everything(42)
    model=build_model('resnet50',8,pretrained=True).cuda(); ema=copy.deepcopy(model).eval()
    for p in ema.parameters(): p.requires_grad_(False)
    backbone,head=trainer.classifier_parameters(model)
    for p in backbone: p.requires_grad_(False)
    optimizer=torch.optim.AdamW([dict(params=backbone,lr=.00005),dict(params=head,lr=.0002)],weight_decay=.0002)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=22,eta_min=1e-6)
    weights,counts=trainer.effective_number_weights(roles['train'],.999,torch.device('cuda'))
    criterion=torch.nn.CrossEntropyLoss(weight=weights,label_smoothing=.05); scaler=torch.amp.GradScaler('cuda')
    loaders={r:trainer.make_loader(ImageSampleDataset(items,trainer.training_transform_v2() if r=='train' else evaluation_transform()),16,r=='train',2,True)
             for r,items in roles.items() if r!='outer_holdout'}
    history=[]; best=None; stale=0; updates={'count':0}; original_step=optimizer.step
    def counted_step(*args,**kwargs):
        value=original_step(*args,**kwargs); updates['count']+=1; return value
    optimizer.step=counted_step
    for epoch in range(1,25):
        began=time.monotonic(); before=updates['count']
        if epoch==3:
            for p in backbone: p.requires_grad_(True)
        training=trainer.run_epoch(model,loaders['train'],criterion,torch.device('cuda'),optimizer,scaler)
        trainer.update_ema(ema,model,.995)
        raw=trainer.run_epoch(model,loaders['inner_validation'],criterion,torch.device('cuda'))
        averaged=trainer.run_epoch(ema,loaders['inner_validation'],criterion,torch.device('cuda'))
        if epoch>2: scheduler.step()
        source='ema' if averaged['macro_f1']>=raw['macro_f1'] else 'raw'; validation=averaged if source=='ema' else raw
        key=(validation['macro_f1'],validation['top3_accuracy'],-validation['loss'])
        chosen=best is None or key>tuple(best['objective'])
        if chosen:
            best=dict(epoch=epoch,source=source,objective=list(key),validation=validation)
            torch.save(dict(model_state_dict=(ema if source=='ema' else model).state_dict(),architecture='resnet50',classes=CLASSES,
                            research_only=True,epoch=epoch,protocol_sha256=sha256_file(OUT/'protocol.json')),MODEL/'best_model.pth')
            stale=0
        else: stale+=1
        history.append(dict(epoch=epoch,train=training,validation_raw=raw,validation_ema=averaged,selected_weights=source,
                            actual_optimizer_updates=updates['count']-before,attempted_optimizer_updates=len(loaders['train']),
                            selected_new_best=chosen,seconds=time.monotonic()-began,backbone_frozen=epoch<=2))
        save_json(MODEL/'history.json',history)
        print(json.dumps(dict(epoch=epoch,validation_accuracy=validation['accuracy'],validation_macro_f1=validation['macro_f1'],
                              best_epoch=best['epoch'],actual_updates=history[-1]['actual_optimizer_updates'],seconds=history[-1]['seconds'])),flush=True)
        if epoch>2 and stale>=7: break
    save_json(MODEL/'selection_report.json',dict(best=best,configuration=CONFIG,protocol_sha256=sha256_file(OUT/'protocol.json'),
        checkpoint_sha256=sha256_file(MODEL/'best_model.pth'),epochs_completed=len(history),actual_optimizer_updates=updates['count'],
        amp_skipped_updates=sum(h['attempted_optimizer_updates']-h['actual_optimizer_updates'] for h in history)))
    del model,ema,optimizer; torch.cuda.empty_cache()


def infer(samples):
    cp=torch.load(MODEL/'best_model.pth',map_location='cpu',weights_only=False)
    assert cp['classes']==CLASSES and cp['protocol_sha256']==sha256_file(OUT/'protocol.json')
    model=build_model('resnet50',8,pretrained=False); model.load_state_dict(cp['model_state_dict']); model.cuda().eval()
    loader=trainer.make_loader(ImageSampleDataset(samples,evaluation_transform()),16,False,2,True); p=[]
    with torch.inference_mode():
        for x,_ in loader: p.append(model(x.cuda(non_blocking=True)).softmax(1).cpu().numpy())
    del model,cp; torch.cuda.empty_cache(); return np.concatenate(p).astype(float)


def combine(spec,p):
    if spec['kind']=='single': return p[spec['model']].copy()
    if spec['kind']=='equal3': return np.mean([p[m] for m in PARENTS+(NEW,)],axis=0)
    w=np.asarray(spec['weights']) if spec['kind']=='classwise' else spec['weight']
    out=(1-w)*p[REFERENCE]+w*p[NEW]; return out/out.sum(1,keepdims=True)


def candidates(vp,y):
    specs=[dict(name=m,kind='single',model=m,complexity=0 if m!=REFERENCE else 1) for m in PARENTS+(NEW,REFERENCE)]
    specs.extend(dict(name=f'reference_resnet_w{w:.2f}',kind='global',weight=w,complexity=2) for w in (.25,.5,.75))
    w,details=choose_class_weights(vp[REFERENCE],vp[NEW],y)
    specs.append(dict(name='reference_resnet_classwise',kind='classwise',weights=w.tolist(),details=details,complexity=3))
    specs.append(dict(name='equal3',kind='equal3',complexity=2)); return specs


def passes(a,b):
    return (a['per_class']['SkinCancer']['recall']>=b['per_class']['SkinCancer']['recall']-1e-12
        and a['macro_f1']>=b['macro_f1']-1e-12 and a['accuracy']>=b['accuracy']-.005-1e-12
        and all(a['per_class'][c]['recall']>=b['per_class'][c]['recall']-.02-1e-12 for c in CLASSES if c not in ('Lupus','Psoriasis'))
        and all(a['per_class'][c]['precision']>=b['per_class'][c]['precision']-.02-1e-12 for c in ('Lupus','Psoriasis')))


def ranking(t):
    a=t['validation']; weak=[a['per_class'][c] for c in ('Lupus','Psoriasis')]
    return (-min(c['recall'] for c in weak),-np.mean([c['f1'] for c in weak]),-a['macro_f1'],-a['accuracy'],t['spec']['complexity'],t['spec']['name'])


def evaluate(outer,inner,roles,protocol):
    vp={}; vy=None
    for m in PARENTS: vp[m],vy=aligned_inner_predictions(m,0,outer,inner)
    paths=protocol['roles']['inner_validation']; by_path={s.path.relative_to(ROOT).as_posix():s for s in roles['inner_validation']}
    vp[NEW]=infer([by_path[p] for p in paths]); assert np.array_equal(vy,[CLASSES.index(next(r['class'] for r in outer['images'] if r['path']==p)) for p in paths])
    w,details=choose_class_weights(vp[PARENTS[0]],vp[PARENTS[1]],vy); vp[REFERENCE]=classwise_blend(vp[PARENTS[0]],vp[PARENTS[1]],w)
    np.savez_compressed(OUT/'validation_predictions.npz',paths=paths,truth=vy,**vp)
    specs=candidates(vp,vy); reference=score(vp[REFERENCE],vy)
    trials=[dict(spec=s,validation=score(combine(s,vp),vy)) for s in specs]
    for t in trials: t['passes_validation_guard']=passes(t['validation'],reference)
    winner=sorted([t for t in trials if t['passes_validation_guard']],key=ranking)[0]['spec']
    save_json(OUT/'selection_locked.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),checkpoint_sha256=sha256_file(MODEL/'best_model.pth'),
        reference_weights=w.tolist(),reference_details=details,selected=winner,trials=trials))
    # First access to existing outer probabilities and new outer inference.
    expected={r['path']:r for r in outer['images'] if r['fold']==0}; order=sorted(expected)
    tp={m:np.stack([v[p] for p in order]) for m in PARENTS for v in [read_probabilities(m,0,outer,expected)]}
    test_by_path={s.path.relative_to(ROOT).as_posix():s for s in roles['outer_holdout']}; tp[NEW]=infer([test_by_path[p] for p in order])
    tp[REFERENCE]=classwise_blend(tp[PARENTS[0]],tp[PARENTS[1]],w); ty=np.asarray([CLASSES.index(expected[p]['class']) for p in order])
    p={s['name']:combine(s,tp) for s in specs}; p['validation_selected']=combine(winner,tp)
    predictions=[dict(path=path,sha256=expected[path]['sha256'],label=expected[path]['class'],group=expected[path]['scene_or_case_group'],
                      probabilities={k:a[j].tolist() for k,a in p.items()}) for j,path in enumerate(order)]
    save_json(OUT/'test_predictions.json',predictions)
    save_json(OUT/'results.json',dict(status='original_eight_resnet_pilot_complete_reused_fold0_not5fold',classes=CLASSES,images=len(order),
        selected_method=winner['name'],results={k:score(a,ty) for k,a in p.items()},protocol_sha256=sha256_file(OUT/'protocol.json'),
        selection_sha256=sha256_file(OUT/'selection_locked.json')))
    print(json.dumps(dict(selected=winner['name'],results={k:{n:score(a,ty)[n] for n in ('accuracy','macro_f1')} for k,a in p.items()})),flush=True)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--prepare-only',action='store_true'); args=parser.parse_args()
    torch.set_num_threads(4); outer,inner,roles,protocol=register()
    if args.prepare_only: print(json.dumps(dict(registered=str(OUT/'protocol.json'),role_counts={r:len(v) for r,v in roles.items()})),flush=True); return
    assert torch.cuda.is_available() and not MODEL.exists(),'Preserve existing pilot model; no automatic partial-run overwrite'
    train(roles,protocol); evaluate(outer,inner,roles,protocol)


if __name__=='__main__': main()
