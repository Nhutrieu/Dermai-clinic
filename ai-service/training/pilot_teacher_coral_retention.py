"""Matched frozen CORAL heads, with/without train-only parent distillation.

This is supervised replay plus distillation, not a reproduction of LwF.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import time

import numpy as np
import torch
from torch.nn import functional as F
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

import pilot_teacher_coral_head as prior

shared=prior.shared
base=prior.base
ROOT=prior.ROOT
NAME='teacher_coral_retention_fold0_seed42_20261023'
OUT=ROOT/'ai-service/reports'/NAME
MODELS=ROOT/'ai-service/candidates'/NAME
BRANCHES=['coral_control','coral_retention']
CONFIG={**prior.CONFIG,'temperature':2.,'retention_lambda':1.,
    'teacher':'Original unchanged fold0 ResNet fc applied to raw ORIGINAL TRAIN features only'}
ORIGINAL={'train':'train','original_validation':'inner_validation','original_outer':'outer_holdout'}
ROLES=['train','auxiliary_train','original_validation','dermacon_validation',
    'original_outer','dermacon_official_test','skindisnet_transfer']


def utc():return datetime.now(timezone.utc).isoformat()


def cache_path(role):
    if role in ORIGINAL:
        return shared.specialist.OUT/f'B_specialist/fold_0/{ORIGINAL[role]}_features.npz'
    return prior.OUT/f'{role}_features.npz'


def arrays(p,role):
    rows=p['roles'][ORIGINAL.get(role,role)]
    with np.load(cache_path(role),allow_pickle=False) as z:
        assert z['paths'].tolist()==[r['path'] for r in rows]
        return z['features'].copy(),np.array([base.CLASSES.index(r['label']) for r in rows]),rows


def parent_logits(raw_features,state):
    """Use unscaled frozen-CNN features, not the student's standardized inputs."""
    x=torch.as_tensor(raw_features,dtype=torch.float32)
    if x.ndim!=2 or x.shape[1]!=2048:raise ValueError('Expected Nx2048 raw features')
    with torch.no_grad():return F.linear(x,state['fc.weight'],state['fc.bias']).detach()


def retention_loss(student,teacher,temperature=2.):
    if student.shape!=teacher.shape or student.ndim!=2 or temperature<=0:
        raise ValueError('Equal NxC logits and positive temperature required')
    q=F.softmax(teacher.detach()/temperature,dim=1)
    return F.kl_div(F.log_softmax(student/temperature,dim=1),q,reduction='batchmean')*temperature**2


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');shared.verify(p);return p
    registry=base.read(ROOT/'ai-service/reports/active_research_track.json')
    assert registry['next_experiment'] is None
    old=base.read(prior.OUT/'protocol.json');shared.verify(old)
    assert base.read(prior.OUT/'completion.json')['status']=='complete_verified_exploratory'
    files=[ROOT/'ai-service/training/pilot_teacher_coral_retention.py',
        ROOT/'ai-service/tests/test_teacher_coral_retention.py',
        prior.OUT/'protocol.json',prior.OUT/'results.json',prior.OUT/'independent_review.json',
        prior.OUT/'completion.json',prior.MODELS/'pooled_coral/best_model.pth',
        prior.MODELS/'pooled_coral/resume_state.pth']+[cache_path(r) for r in ROLES]
    frozen={**old['frozen_sha256'],**{f.relative_to(ROOT).as_posix():base.sha(f) for f in files}}
    p=dict(name=NAME,registered_utc=utc(),fold=0,classes=base.CLASSES,roles=old['roles'],
        baseline_protected=old['baseline_protected'],configuration=CONFIG,frozen_sha256=frozen,
        isolated_change='Both arms repeat the preceding CE+100CORAL configuration exactly. Add only 1*T^2*KL(parent||student), T=2, on16 ORIGINAL TRAIN rows. Same init/draws20epochs. No sweep.',
        teacher='Original single ResNet parent fc on cached unscaled original training features, frozen/detached. No teacher outputs on auxiliary, validation, outer or transfer used in training.',
        parent_probability_check='CPU fc softmax must match cached original train CNN probabilities within max absolute1e-4 and identical argmax; threshold fixed before run.',
        checkpoint=old['checkpoint'],
        selection='Same two-validation guards/objective as preceding pilot. Retention additionally mean MacroF1>=matchedCORAL and strictly higher mean weak-disease F1. Baseline wins ties. Lock before reading held feature arrays.',
        control_replication='Before held inference, require best and final control tensors and chosen epoch bit-identical to completed pooled_coral arm. No alteration of old experiment.',
        limits=old['limits']+[
            'Earlier end-to-end B0/ConvNeXt ensemble distillation was already tried and rejected. This is a different matched small-head retention test with a single ResNet parent.',
            'Parent has seen original train labels; soft targets can preserve its errors/overfit, not new ground truth. Passing train retention does not guarantee validation or external improvement.',
            'Inspired by Hinton distillation and old-output preservation, but uses original replay data/same labels/frozenCNN; not the original no-old-data LwF setting.',
            'Only original training targets are used. No source-code identity or teacher branch required for inference.'],
        references=['https://arxiv.org/abs/1503.02531','https://arxiv.org/abs/1606.09282','https://arxiv.org/abs/1607.01719'],
        serving_changed=False)
    OUT.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p)
    base.write(OUT/'research_registry_before.json',registry)
    registry['next_experiment']=OUT.relative_to(ROOT).as_posix()
    registry['next_experiment_status']='registered_matched_coral_parent_retention_fold0'
    base.write(ROOT/'ai-service/reports/active_research_track.json',registry)
    base.write(OUT/'status.json',dict(state='registered',utc=utc()))
    return p


def run(p):
    assert not (OUT/'results.json').exists(),'Preserve completed experiment'
    shared.verify(p)
    roles=['train','auxiliary_train','original_validation','dermacon_validation']
    raw={r:arrays(p,r) for r in roles}
    scaler=StandardScaler().fit(raw['train'][0])
    xs={r:torch.from_numpy(scaler.transform(a[0]).astype(np.float32)) for r,a in raw.items()}
    ys={r:torch.as_tensor(a[1],dtype=torch.long) for r,a in raw.items()}
    np.savez_compressed(OUT/'scaler.npz',mean=scaler.mean_,scale=scaler.scale_)
    parent=torch.load(shared.utility.PARENT,map_location='cpu',weights_only=False)['model_state_dict']
    teacher=parent_logits(raw['train'][0],parent)
    with np.load(cache_path('train'),allow_pickle=False) as z:
        cached=z['probabilities'].copy()
    error=float(np.abs(teacher.softmax(1).numpy()-cached).max())
    assert error<1e-4 and np.array_equal(teacher.argmax(1).numpy(),cached.argmax(1)),error
    np.savez_compressed(OUT/'teacher_train_logits.npz',paths=[r['path'] for r in raw['train'][2]],
        logits=teacher.numpy(),parent_sha256=base.sha(shared.utility.PARENT),
        protocol_sha256=base.sha(OUT/'protocol.json'))
    base.write(OUT/'teacher_verification.json',dict(max_abs_cached_train_probability_error=error,
        rows=len(teacher),original_train_only=True,teacher_detached=not teacher.requires_grad))
    del parent
    val_roles=['original_validation','dermacon_validation']
    current={r:prior.baseline(p,r,raw[r][2]) for r in val_roles}
    truth={r:raw[r][1] for r in val_roles}
    reference={r:base.metrics(current[r],truth[r]) for r in val_roles}
    best_scores={};histories={};initial=None
    for branch in BRANCHES:
        folder=MODELS/branch;folder.mkdir(parents=True,exist_ok=True)
        torch.manual_seed(42);model=prior.Head()
        init=shared.state_sha(model.state_dict())
        if initial is None:initial=init
        assert initial==init
        opt=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.001)
        history=[];best=None
        for epoch in range(1,21):
            base.write(OUT/'status.json',dict(state='training',branch=branch,epoch=epoch,utc=utc()))
            model.train();oi,ai=prior.draws(4043,590,epoch);totals=np.zeros(4);start=time.monotonic()
            for old,aux in zip(oi,ai):
                opt.zero_grad(set_to_none=True)
                logits,z=model(torch.cat([xs['train'][old],xs['auxiliary_train'][aux]]))
                ce=F.cross_entropy(logits,torch.cat([ys['train'][old],ys['auxiliary_train'][aux]]))
                alignment=prior.coral(z[:16],z[16:])
                kd=retention_loss(logits[:16],teacher[old],2.)
                loss=ce+100*alignment
                if branch=='coral_retention':loss=loss+kd
                if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss')
                loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),2.,error_if_nonfinite=True)
                opt.step();totals += [float(v.detach()) for v in [loss,ce,alignment,kd]]
            predictions={r:shared.decision(current[r],prior.probability(model,xs[r])) for r in val_roles}
            scores,failed,key=prior.assess(predictions,truth,reference)
            improved=best is None or tuple(key)>tuple(best['objective'])
            if improved:
                best=dict(epoch=epoch,objective=key,scores=scores,guard_failures=failed)
                shared.utility.atomic_save(dict(model_state_dict=model.state_dict(),classes=base.CLASSES,
                    epoch=epoch,branch=branch,protocol_sha256=base.sha(OUT/'protocol.json')),folder/'best_model.pth')
            history.append(dict(epoch=epoch,actual_updates=128,**{k:float(totals[i]/128) for i,k in enumerate(['loss','ce','coral','retention'])},
                sampling_sha256=hashlib.sha256(oi.numpy().tobytes()+ai.numpy().tobytes()).hexdigest(),
                scores=scores,guard_failures=failed,new_best=improved,best_epoch=best['epoch'],seconds=time.monotonic()-start))
            base.write(folder/'history.json',history)
            print(json.dumps(dict(branch=branch,epoch=epoch,loss=history[-1]['loss'],retention=history[-1]['retention'],best_epoch=best['epoch'])),flush=True)
        shared.utility.atomic_save(dict(model=model.state_dict(),optimizer=opt.state_dict(),history=history,
            initial_state_sha256=initial,protocol_sha256=base.sha(OUT/'protocol.json')),folder/'resume_state.pth')
        if branch=='coral_control':
            old_final=torch.load(prior.MODELS/'pooled_coral/resume_state.pth',map_location='cpu',weights_only=False)
            old_best=torch.load(prior.MODELS/'pooled_coral/best_model.pth',map_location='cpu',weights_only=False)
            new_best=torch.load(folder/'best_model.pth',map_location='cpu',weights_only=False)
            assert best['epoch']==old_best['epoch']
            assert all(torch.equal(v,old_final['model'][k]) for k,v in model.state_dict().items())
            assert all(torch.equal(v,old_best['model_state_dict'][k]) for k,v in new_best['model_state_dict'].items())
            base.write(OUT/'control_replication.json',dict(status='PASS',best_epoch=best['epoch'],all_best_and_final_tensors_bit_identical=True))
        model.load_state_dict(torch.load(folder/'best_model.pth',weights_only=False)['model_state_dict'])
        probabilities={r:prior.probability(model,xs[r]) for r in val_roles}
        base.write(folder/'validation_probabilities.json',{r:pp.tolist() for r,pp in probabilities.items()})
        decisions={r:shared.decision(current[r],probabilities[r]) for r in val_roles}
        scores,failed,key=prior.assess(decisions,truth,reference)
        best_scores[branch]=dict(scores=scores,guard_failures=failed,objective=key)
        base.write(folder/'training_report.json',dict(initial_state_sha256=initial,actual_updates=2560,epochs=20,best=best,
            checkpoint_sha256=base.sha(folder/'best_model.pth'),protocol_sha256=base.sha(OUT/'protocol.json')))
        histories[branch]=history
    assert [h['sampling_sha256'] for h in histories[BRANCHES[0]]]==[h['sampling_sha256'] for h in histories[BRANCHES[1]]]
    _,_,key=prior.assess(current,truth,reference)
    trials={'current_fusion':dict(scores=reference,guard_failures=[],objective=key),**best_scores}
    a,b=trials['coral_retention'],trials['coral_control']
    if a['objective'][1]+1e-12<b['objective'][1]:a['guard_failures'].append('mean_macro_f1_below_matched_coral')
    if a['objective'][2]<=b['objective'][2]+1e-12:a['guard_failures'].append('no_mean_focus_f1_gain_vs_matched_coral')
    # The control repeats an already rejected historical candidate; it cannot be newly promoted.
    eligible=['current_fusion']+(['coral_retention'] if not a['guard_failures'] else [])
    selected=max(eligible,key=lambda n:(*trials[n]['objective'][1:],n=='current_fusion'))
    base.write(OUT/'selection_locked.json',dict(locked_utc=utc(),selected=selected,trials=trials,
        control_eligible_for_promotion=False,checkpoints={b:base.sha(MODELS/b/'best_model.pth') for b in BRANCHES},
        scaler_sha256=base.sha(OUT/'scaler.npz')))
    started=utc();results={};output=[]
    for role in ['original_outer','dermacon_official_test','skindisnet_transfer']:
        x,y,rows=arrays(p,role);x=torch.from_numpy(scaler.transform(x).astype(np.float32))
        reference_pred=prior.baseline(p,role,rows);decisions=dict(current_fusion=reference_pred);pp={}
        for branch in BRANCHES:
            model=prior.Head();model.load_state_dict(torch.load(MODELS/branch/'best_model.pth',weights_only=False)['model_state_dict'])
            pp[branch]=prior.probability(model,x);decisions[branch]=shared.decision(reference_pred,pp[branch])
        decisions['validation_selected']=decisions[selected]
        for pred in decisions.values():assert np.array_equal(pred==5,reference_pred==5)
        results[role]={n:base.metrics(pred,y) for n,pred in decisions.items()}
        output.extend(dict(**row,role=role,predictions={n:int(pred[i]) for n,pred in decisions.items()},
            probabilities={n:v[i].tolist() for n,v in pp.items()}) for i,row in enumerate(rows))
    base.write(OUT/'held_decisions.json',output)
    base.write(OUT/'results.json',dict(status='complete_exploratory_coral_parent_retention_onefold',selected=selected,
        validations=trials,held=results,held_started_utc=started,protocol_sha256=base.sha(OUT/'protocol.json'),
        selection_sha256=base.sha(OUT/'selection_locked.json'),global_5937_score_changed=False,serving_changed=False,limits=p['limits']))
    shared.verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',updates_each=2560,identical_batches=True,
        unchanged_parent=True,teacher_original_train_only=True,control_bit_identical=True,results_sha256=base.sha(OUT/'results.json')))
    base.write(OUT/'status.json',dict(state='complete',selected=selected,utc=utc()))
    print(json.dumps(dict(complete=True,selected=selected,held={r:{n:{k:s[k] for k in ['accuracy','macro_f1']} for n,s in v.items()} for r,v in results.items()})),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    torch.set_num_threads(2)
    with threadpool_limits(limits=1):
        p=prepare()
        if not args.prepare_only:run(p)


if __name__=='__main__':main()
