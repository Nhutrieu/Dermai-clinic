"""Matched hard/source-soft targets on original-eight fold0 train only."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import time
from collections import Counter

import numpy as np
import torch
from torch.nn import functional as F

from common import CLASSES,ImageSampleDataset,evaluation_transform,seed_everything
import train_v2 as trainer
import evaluate_original_eight_cancer_locked_fusion as fusion
import pilot_original_eight_balanced_softmax as prior
from pilot_original_eight_psoriasis_replay import SeededDrawDataset

ROOT=prior.ROOT
NAME='original_eight_source_softlabels_fold0_seed42_20261021'
OUT=ROOT/'ai-service/reports'/NAME
MODELS=ROOT/'ai-service/candidates'/NAME
BRANCHES=['hard_control','source_soft']
ALIASES={'Acne':'Acne','Candida':'Candidiasis','Candida intertrigo':'Candidiasis',
    'Eczema':'Eczema','Cutaneous lupus':'Lupus','Psoriasis':'Psoriasis','Tinea':'Tinea','Verruca vulgaris':'Warts'}
CONFIG=dict(seed=42,epochs=3,batch_size=16,workers=0,backbone_lr=1e-5,head_lr=5e-5,
    weight_decay=.0002,ema_decay=.5,effective_number_beta=.999,label_smoothing=0,
    source_mix=.5,precision='FP32',torch_threads=4)
HANDLE=None


def target(row):
    hard=np.eye(8,dtype=np.float64)[CLASSES.index(row['label'])]
    if row['source']!='SCIN':return hard
    weights=row['weighted_source_labels'];total=sum(weights.values())
    if not .98<=total<=1.02 or any(not np.isfinite(w) or w<0 for w in weights.values()):
        raise ValueError('Expected nonnegative rounded source differential weights')
    distribution=np.zeros(8,dtype=np.float64)
    for label,value in weights.items():
        # Unmapped concepts stay on the existing hard target: never invent an
        # eight-way diagnosis from a broad or unsupported source term.
        index=CLASSES.index(ALIASES[label]) if label in ALIASES else CLASSES.index(row['label'])
        distribution[index]+=value/total
    q=(1-CONFIG['source_mix'])*hard+CONFIG['source_mix']*distribution
    assert np.isfinite(q).all() and (q>=0).all() and np.isclose(q.sum(),1)
    return q


def weighted_loss(logits,targets,labels,weights):
    # Use the SAME original hard-label per-photo weight in both branches.
    # This isolates the target change from class-weight mass redistribution.
    w=weights[labels]
    return (-(targets*F.log_softmax(logits,dim=1)).sum(1)*w).sum()/w.sum()


def choose(scores):
    current=scores['current_fusion'];trials={}
    for name,value in scores.items():
        reasons=fusion.guard_failures(value,current)
        for label in ['Lupus','Psoriasis','Tinea']:
            for key in ['f1','recall']:
                if value['per_class'][label][key]+1e-12<current['per_class'][label][key]:reasons.append(label+'_'+key)
        if name=='source_soft':
            if value['macro_f1']+1e-12<scores['hard_control']['macro_f1']:reasons.append('macro_f1_below_matched_control')
            if prior.mean_focus(value)<=prior.mean_focus(scores['hard_control'])+1e-12:reasons.append('no_mean_focus_f1_gain_vs_control')
        trials[name]=dict(metrics=value,guard_failures=reasons)
    eligible=[name for name in scores if not trials[name]['guard_failures']]
    selected=max(eligible,key=lambda name:(scores[name]['macro_f1'],prior.mean_focus(scores[name]),scores[name]['accuracy'],name=='current_fusion',name=='hard_control'))
    return selected,trials


def status(state,**kwargs):
    fusion.write(OUT/'status.json',dict(state=state,pid=os.getpid(),updated_unix=time.time(),**kwargs))


def lock_process():
    global HANDLE
    import msvcrt
    OUT.mkdir(parents=True,exist_ok=True);handle=(OUT/'runner.lock').open('a+b')
    if handle.tell()==0:handle.write(b'0');handle.flush()
    handle.seek(0)
    try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        handle.close();raise RuntimeError('Source-softlabel pilot already running')
    HANDLE=handle


def verify(p):
    for path,h in p['frozen_sha256'].items():assert fusion.sha(ROOT/path)==h,path


def prepare():
    if (OUT/'protocol.json').exists():
        p=fusion.read(OUT/'protocol.json');verify(p);return p
    inventory={r['path']:r for r in fusion.read(prior.AUDIT/'image_inventory.json')}
    role_paths=fusion.read(fusion.CV/'protocol.json')['folds'][0]['roles']
    roles={role:[dict(path=path,label=inventory[path]['label'],sha256=inventory[path]['sha256'],group=inventory[path]['group']) for path in paths] for role,paths in role_paths.items()}
    assert [len(roles[role]) for role in ['train','inner_validation','outer_holdout']]==[4043,718,1176]
    for a,b in [('train','inner_validation'),('train','outer_holdout'),('inner_validation','outer_holdout')]:
        for key in ['path','sha256','group']:assert {r[key] for r in roles[a]}.isdisjoint(r[key] for r in roles[b])
    records=[]
    for row in roles['train']:
        meta=inventory[row['path']];hard=np.eye(8)[CLASSES.index(row['label'])];soft=target(meta)
        record=dict(**row,source=meta['source'],hard_target=hard.tolist(),soft_target=soft.tolist(),
            target_changed=bool(np.abs(hard-soft).max()>1e-12))
        if meta['source']=='SCIN':record.update(weighted_source_labels=meta['weighted_source_labels'],source_case_id=meta['source_case_id'])
        records.append(record)
    files=[prior.AUDIT/'image_inventory.json',prior.AUDIT/'verification.json',fusion.CV/'protocol.json',prior.PARENT,
        prior.PARENT_REPORT/'validation_predictions.npz',prior.PARENT_REPORT/'test_predictions.json',
        prior.CURRENT/'results.json',prior.CURRENT/'fold_0/selection_locked.json',prior.CURRENT/'independent_review.json',
        fusion.SERVING,fusion.BENCHMARK,ROOT/'ai-service/tests/test_source_softlabels_pilot.py']
    files += [ROOT/'ai-service/training'/name for name in ['pilot_original_eight_source_softlabels.py',
        'pilot_original_eight_balanced_softmax.py','pilot_original_eight_psoriasis_replay.py',
        'evaluate_original_eight_cancer_locked_fusion.py','common.py','train_v2.py']]
    for rows in roles.values():
        for row in rows:assert fusion.sha(ROOT/row['path'])==row['sha256']
    p=dict(name=NAME,date='2026-10-21',classes=CLASSES,configuration=CONFIG,aliases=ALIASES,roles=roles,train_targets=records,
        frozen_sha256={path.relative_to(ROOT).as_posix():fusion.sha(path) for path in files},
        target_definition='Original-source rows hard. SCIN normalize rounded published differential sum to1; map only exact existing source aliases. Unmapped weight stays on original hard class. Soft=.5hard+.5mapped differential. Never use inner/outer metadata as training targets, never change hard evaluation labels.',
        matched_design='Same4043photos, one deterministic permutation/epoch, same original hard labels/class counts, same per-position augmentation seed420000+epoch*10000+position. Same parent original ResNet50, optimizer, updates and class weights. No auxiliary321 or807 images. Only target distribution differs.',
        loss='Per-row soft CE, weighted by effective-number weight of ORIGINAL hard label in both branches, normalize by batch sum of those weights. Control one-hot is exactly ordinary weighted hard CE. No extra label smoothing.',
        training='Three fixed epochs FP32 AdamW, backbone1e-5/head5e-5, wd.0002, clip2, cosine eta_min1e-6. EMA.5 update once per epoch. Choose final epoch3raw/EMA on inner MacroF1, raw on tie. No epoch or parameter grid.',
        fusion='Same .75 original B0/Conv reference +.25 branch ResNet, monotone protected classes learned from inner using existing policy. Cancer decision mask exact.',
        selection='Accuracy/MacroF1>=current; existing class guards and exact SkinCancer precision/recall; each Lupus/Psoriasis/Tinea F1 and recall>=current. Soft additionally MacroF1>=matched hard control and mean weak3F1 strictly greater. Rank MacroF1, mean weak3F1, Accuracy, prefer current then control on tie. Lock before outer inference.',
        changed_targets=sum(r['target_changed'] for r in records),changed_by_hard_label=dict(Counter(r['label'] for r in records if r['target_changed'])),
        sources=['https://research.google/blog/scin-a-new-resource-for-representative-dermatology-images/','https://docs.pytorch.org/docs/stable/generated/torch.nn.CrossEntropyLoss.html'],
        limitations=['Exploratory single fold/seed with historically viewed development roles; not new independent clinical evidence.',
            'SCIN differential labels are retrospective, not newly confirmed diagnoses or calibrated disease risk.',
            'Half-mix and conservative unmapped-mass fallback are local design choices, not an exact paper reproduction.',
            'Continuation from already trained ResNet may limit correction of entrenched features. Threeepochs cannot establish method universally ineffective.',
            'No automatic fivefold expansion, Word/API/checkpoint replacement or global5937score change.'])
    fusion.write(OUT/'protocol.json',p);status('registered',changed_targets=p['changed_targets'])
    registry_path=ROOT/'ai-service/reports/active_research_track.json';registry=fusion.read(registry_path)
    registry['next_experiment']=OUT.relative_to(ROOT).as_posix();registry['next_experiment_status']='registered_matched_source_softlabels'
    fusion.write(registry_path,registry)
    return p


def train_branch(branch,p):
    directory=MODELS/branch;directory.mkdir(parents=True,exist_ok=True)
    if (directory/'training_report.json').exists():
        r=fusion.read(directory/'training_report.json');assert r['protocol_sha256']==fusion.sha(OUT/'protocol.json')
        assert r['checkpoint_sha256']==fusion.sha(directory/'final_model.pth');return
    seed_everything(42);model=prior.load_initial();ema=copy.deepcopy(model).eval().requires_grad_(False)
    backbone,head=trainer.classifier_parameters(model)
    optimizer=torch.optim.AdamW([dict(params=backbone,lr=CONFIG['backbone_lr']),dict(params=head,lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=3,eta_min=1e-6)
    train=p['roles']['train'];validation=p['roles']['inner_validation']
    weights,counts=trainer.effective_number_weights(prior.objects(train),CONFIG['effective_number_beta'],torch.device('cuda'))
    targets=torch.tensor([r['hard_target' if branch=='hard_control' else 'soft_target'] for r in p['train_targets']],dtype=torch.float32,device='cuda')
    base=ImageSampleDataset(prior.objects(train),trainer.training_transform_v2())
    vloader=trainer.make_loader(ImageSampleDataset(prior.objects(validation),evaluation_transform()),16,False,0,True)
    history=[];start=1;resume=directory/'resume_state.pth'
    if resume.exists():
        saved=torch.load(resume,map_location='cpu',weights_only=False);assert saved['protocol_sha256']==fusion.sha(OUT/'protocol.json')
        model.load_state_dict(saved['model']);ema.load_state_dict(saved['ema']);optimizer.load_state_dict(saved['optimizer']);scheduler.load_state_dict(saved['scheduler'])
        history=saved['history'];start=saved['epoch']+1
    for epoch in range(start,4):
        status('training',branch=branch,epoch=epoch,epochs_limit=3);seed_everything(42+epoch)
        indices=torch.randperm(len(train),generator=torch.Generator().manual_seed(42+epoch)).tolist()
        loader=trainer.make_loader(SeededDrawDataset(base,indices,epoch),16,False,0,True)
        augmentation_hash=hashlib.sha256();label_hash=hashlib.sha256();target_hash=hashlib.sha256()
        model.train();updates=0;loss_sum=0;began=time.monotonic()
        for x,y,positions in loader:
            augmentation_hash.update(x.numpy().tobytes());label_hash.update(y.numpy().tobytes())
            batch_indices=torch.tensor([indices[int(position)] for position in positions],device='cuda')
            q=targets[batch_indices];target_hash.update(q.cpu().numpy().tobytes())
            x=x.cuda();y=y.cuda();optimizer.zero_grad(set_to_none=True)
            loss=weighted_loss(model(x),q,y,weights)
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),2,error_if_nonfinite=True);optimizer.step()
            updates+=1;loss_sum+=float(loss.detach())
        assert updates==253
        assert all(torch.isfinite(value).all() for value in model.state_dict().values() if value.is_floating_point())
        trainer.update_ema(ema,model,CONFIG['ema_decay'])
        raw=trainer.run_epoch(model,vloader,torch.nn.CrossEntropyLoss(),torch.device('cuda'))
        averaged=trainer.run_epoch(ema,vloader,torch.nn.CrossEntropyLoss(),torch.device('cuda'));scheduler.step()
        history.append(dict(epoch=epoch,training_loss=loss_sum/updates,actual_updates=updates,draws=len(indices),unique_images=len(set(indices)),
            changed_target_draws=0 if branch=='hard_control' else p['changed_targets'],
            augmentation_sha256=augmentation_hash.hexdigest(),labels_sha256=label_hash.hexdigest(),targets_sha256=target_hash.hexdigest(),
            draw_indices_sha256=hashlib.sha256(json.dumps(indices).encode()).hexdigest(),class_draw_counts=dict(Counter(train[i]['label'] for i in indices)),
            validation_raw=raw,validation_ema=averaged,seconds=time.monotonic()-began))
        fusion.write(directory/'history.json',history)
        prior.atomic_save(dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),epoch=epoch,model=model.state_dict(),ema=ema.state_dict(),
            optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),history=history),resume)
        print(json.dumps(dict(branch=branch,epoch=epoch,raw_macro_f1=raw['macro_f1'],ema_macro_f1=averaged['macro_f1'],seconds=history[-1]['seconds'])),flush=True)
    source='ema' if history[-1]['validation_ema']['macro_f1']>history[-1]['validation_raw']['macro_f1'] else 'raw';chosen=ema if source=='ema' else model
    prior.atomic_save(dict(model_state_dict=chosen.state_dict(),architecture='resnet50',classes=CLASSES,epoch=3,branch=branch,
        selected_weights=source,protocol_sha256=fusion.sha(OUT/'protocol.json'),research_only=True),directory/'final_model.pth')
    probs=prior.infer(chosen,validation)
    fusion.write(directory/'inner_predictions.json',dict(paths=[r['path'] for r in validation],probabilities=probs.tolist()))
    fusion.write(directory/'training_report.json',dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),checkpoint_sha256=fusion.sha(directory/'final_model.pth'),
        initial_checkpoint_sha256=fusion.sha(prior.PARENT),classes=CLASSES,branch=branch,epochs=3,selected_weights=source,
        actual_updates=sum(r['actual_updates'] for r in history),class_counts=counts,class_weights=weights.cpu().tolist(),
        changed_target_images=0 if branch=='hard_control' else p['changed_targets'],outer_used_for_selection=False,precision='FP32'))
    del chosen,model,ema,optimizer;torch.cuda.empty_cache()


def evaluate(p):
    paths,y,ref,original=fusion.validation_arrays(0)
    parent=fusion.read(prior.CURRENT/'fold_0/selection_locked.json');protected=parent['trials'][parent['selected']]['spec']['protected']
    policies={'current_fusion':protected};traces={};raw_validation={}
    values={'current_fusion':fusion.decide(ref,original,protected)}
    for branch in BRANCHES:
        inner=fusion.read(MODELS/branch/'inner_predictions.json');assert inner['paths']==paths
        probs=np.array(inner['probabilities']);policies[branch],traces[branch]=fusion.learn_protected(ref,probs,y)
        values[branch]=fusion.decide(ref,probs,policies[branch]);raw_validation[branch]=fusion.metrics(probs.argmax(1),y)
    validation={name:fusion.metrics(pred,y) for name,pred in values.items()}
    selected,trials=choose(validation)
    fusion.write(OUT/'selection_locked.json',dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),selected=selected,trials=trials,
        protected=policies,protection_trace=traces,raw_validation=raw_validation,checkpoints={b:fusion.sha(MODELS/b/'final_model.pth') for b in BRANCHES}))
    print(json.dumps(dict(selection_locked=selected)),flush=True);status('evaluating_outer',selected=selected)
    old=fusion.read(prior.PARENT_REPORT/'test_predictions.json');lookup={r['path']:r for r in p['roles']['outer_holdout']}
    assert set(lookup)=={r['path'] for r in old};rows=[lookup[r['path']] for r in old]
    y=np.array([CLASSES.index(r['label']) for r in rows]);ref=np.array([r['probabilities']['old_classwise'] for r in old]);original=np.array([r['probabilities']['resnet50'] for r in old])
    raw={};values={'current_fusion':fusion.decide(ref,original,policies['current_fusion'])}
    for branch in BRANCHES:
        checkpoint=torch.load(MODELS/branch/'final_model.pth',map_location='cpu',weights_only=False)
        model=prior.build_model('resnet50',8,pretrained=False);model.load_state_dict(checkpoint['model_state_dict']);model.cuda()
        raw[branch]=prior.infer(model,rows);values[branch]=fusion.decide(ref,raw[branch],policies[branch])
        del model,checkpoint;torch.cuda.empty_cache()
    values['validation_selected']=values[selected]
    for value in values.values():assert np.array_equal(value==5,values['current_fusion']==5)
    output=[dict(**row,source='SCIN' if row['path'].startswith('SkinDisease/scin-v1/') else 'original_train',
        predictions={name:int(pred[i]) for name,pred in values.items()},
        raw_component_probabilities={'old_classwise':ref[i].tolist(),'original_resnet50':original[i].tolist(),**{branch:prob[i].tolist() for branch,prob in raw.items()}}) for i,row in enumerate(rows)]
    fusion.write(OUT/'outer_decisions.json',output)
    result=dict(status='complete_exploratory_matched_source_softlabels',classes=CLASSES,images=1176,selected=selected,
        protocol_sha256=fusion.sha(OUT/'protocol.json'),selection_sha256=fusion.sha(OUT/'selection_locked.json'),validation=validation,
        methods={name:fusion.metrics(value,y) for name,value in values.items()},raw_outer={b:fusion.metrics(prob.argmax(1),y) for b,prob in raw.items()},
        per_source={source:{name:fusion.metrics(value[np.array([r['source']==source for r in output])],y[np.array([r['source']==source for r in output])]) for name,value in values.items()} for source in ['original_train','SCIN']},
        global_5937_score_changed=False,serving_changed=False,labels_changed=0,limitations=p['limitations'])
    fusion.write(OUT/'results.json',result);return result


def run(p):
    assert not (OUT/'results.json').exists(),'Preserve completed experiment';verify(p)
    if not (OUT/'parent_reproduction.json').exists():
        _,_,_,expected=fusion.validation_arrays(0);model=prior.load_initial();actual=prior.infer(model,p['roles']['inner_validation'])
        error=float(np.abs(actual-expected).max());assert error<2e-6 and np.array_equal(actual.argmax(1),expected.argmax(1))
        fusion.write(OUT/'parent_reproduction.json',dict(status='PASS',images=718,max_abs_difference=error));del model;torch.cuda.empty_cache()
    for branch in BRANCHES:train_branch(branch,p)
    histories={b:fusion.read(MODELS/b/'history.json') for b in BRANCHES}
    for epoch in range(3):
        for key in ['augmentation_sha256','labels_sha256','draw_indices_sha256','class_draw_counts','actual_updates','draws','unique_images']:
            assert histories['hard_control'][epoch][key]==histories['source_soft'][epoch][key],key
    result=evaluate(p);verify(p)
    fusion.write(OUT/'verification.json',dict(status='PASS',scope='Technical matched-target consistency, not clinical validation',
        results_sha256=fusion.sha(OUT/'results.json'),matched_actual_augmentation=True,matched_hard_labels_and_exposure=True,
        actual_updates_each=759,changed_training_targets=p['changed_targets'],hard_evaluation_labels_changed=0,serving_changed=False))
    status('complete',selected=result['selected']);print(json.dumps(dict(complete=True,selected=result['selected'],outer={n:{k:s[k] for k in ['accuracy','macro_f1']} for n,s in result['methods'].items()})),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    torch.set_num_threads(4);lock_process();p=prepare()
    if not args.prepare_only:run(p)


if __name__=='__main__':main()
