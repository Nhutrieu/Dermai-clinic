"""Matched case-averaged source/class group heads: uniform versus Group DRO.

Frozen original fold-0 ResNet features; no CNN fits, new photos or relabeling.
"""
from __future__ import annotations
import argparse
from pathlib import Path

import numpy as np
from scipy.special import softmax
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import torch
from torch.nn import functional as F

import pilot_teacher_case_retrieval as previous
import pilot_teacher_pairwise_specialists as cache

ROOT, base, prior, latest, features = previous.ROOT, previous.base, previous.prior, previous.latest, previous.features
OUT=ROOT/'ai-service/reports/teacher_group_dro_fold0_seed42_20261024'
MODELS=ROOT/'ai-service/candidates'/OUT.name
METHODS=['current_policy','uniform_groups','group_dro']
CONFIG=dict(updates=400, lr=.01, dual_step=.01, C=.001, seed=42,
            optimizer='Adam', betas=[.9,.999], epsilon=1e-8, precision='CPU float64', threads=2)


def group_matrix(rows):
    """One group per source/original class; average cases, then photos in a case."""
    keys=[r['label']+'|'+('SCIN' if r['path'].startswith('SkinDisease/scin-v1/') else 'original_train') for r in rows]
    names=sorted(set(keys));matrix=np.zeros((len(names),len(rows)),dtype=np.float64);counts=[]
    for j,name in enumerate(names):
        ids=[i for i,k in enumerate(keys) if k==name];cases={rows[i]['group'] for i in ids}
        sizes={g:sum(rows[i]['group']==g for i in ids) for g in cases}
        for i in ids:matrix[j,i]=1/(len(cases)*sizes[rows[i]['group']])
        counts.append(dict(name=name,images=len(ids),scene_case_groups=len(cases)))
    if not len(names) or not np.allclose(matrix.sum(1),1.,atol=1e-12):raise ValueError('Nonempty normalized training groups required')
    return matrix,counts


def dual_update(q,losses,step):
    q=np.asarray(q,dtype=np.float64);losses=np.asarray(losses,dtype=np.float64)
    if (q.ndim!=1 or q.shape!=losses.shape or not len(q) or not np.isfinite(q).all()
        or (q<=0).any() or not np.isclose(q.sum(),1.) or not np.isfinite(losses).all() or not np.isfinite(step) or step<0):
        raise ValueError('Positive normalized weights and finite aligned losses required')
    if step==0:return q.copy()
    logits=np.log(q)+step*losses;logits-=logits.max()
    result=np.exp(logits);result/=result.sum()
    return result


def fit(x,y,matrix,robust,config=CONFIG):
    """Fixed final iterate; no validation/checkpoint/step search."""
    torch.set_num_threads(config['threads']);torch.manual_seed(config['seed'])
    xx=torch.as_tensor(np.asarray(x),dtype=torch.float64);yy=torch.as_tensor(y,dtype=torch.long)
    mm=torch.as_tensor(matrix,dtype=torch.float64)
    coef=torch.zeros((5,xx.shape[1]),dtype=torch.float64,requires_grad=True)
    intercept=torch.zeros(5,dtype=torch.float64,requires_grad=True)
    opt=torch.optim.Adam([coef,intercept],lr=config['lr'],betas=tuple(config['betas']),eps=config['epsilon'])
    q=np.full(len(matrix),1/len(matrix));lam=1/(len(x)*config['C']);history=[]
    for step in range(1,config['updates']+1):
        opt.zero_grad(set_to_none=True)
        losses=F.cross_entropy(F.linear(xx,coef,intercept),yy,reduction='none')
        group_losses=mm@losses
        if robust:q=dual_update(q,group_losses.detach().numpy(),config['dual_step'])
        objective=torch.as_tensor(q)@group_losses+.5*lam*coef.square().sum()
        if not torch.isfinite(objective):raise FloatingPointError('Nonfinite Group DRO objective')
        objective.backward();opt.step()
        if step==1 or step%20==0:
            history.append(dict(step=step,objective_before_update=float(objective.detach()),
                group_losses_before_update=group_losses.detach().tolist(),q=q.tolist()))
    w=coef.detach().numpy().copy();b=intercept.detach().numpy().copy()
    if not np.isfinite(w).all() or not np.isfinite(b).all():raise FloatingPointError('Nonfinite parameters')
    return dict(coef=w,intercept=b,q=q),history


def probabilities(x,model):
    return softmax(((np.asarray(x,dtype=float)-model['mean'])/model['scale'])@model['coef'].T+model['intercept'],axis=1)


def choose(decisions,truth):
    scores={n:base.metrics(d,truth) for n,d in decisions.items()}
    trials={n:dict(metrics=s,guard_failures=prior.failures(s,scores['current_policy'])) for n,s in scores.items()}
    s=scores['group_dro']
    if s['macro_f1']+1e-12<scores['uniform_groups']['macro_f1']:trials['group_dro']['guard_failures'].append('macro_f1_below_uniform_group_control')
    for n in ['current_policy','uniform_groups']:
        if latest.previous.mean_focus(s)<=latest.previous.mean_focus(scores[n])+1e-12:
            trials['group_dro']['guard_failures'].append('no_weak_mean_f1_gain_vs_'+n)
    passing=[n for n in METHODS if not trials[n]['guard_failures']]
    selected=max(passing,key=lambda n:(scores[n]['macro_f1'],latest.previous.mean_focus(scores[n],'recall'),
                                      scores[n]['accuracy'],n=='current_policy',n=='uniform_groups'))
    return dict(selected=selected,trials=trials)


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');prior.verify(p);return p
    reg=base.read(ROOT/'ai-service/reports/active_research_track.json');assert reg['next_experiment'] is None
    old=base.read(previous.OUT/'protocol.json');prior.verify(old)
    assert base.read(previous.OUT/'completion.json')['status']=='complete_verified_pilot_not_selected'
    files=[Path(__file__),ROOT/'ai-service/tests/test_teacher_group_dro.py',
        ROOT/'ai-service/training/pilot_teacher_case_retrieval.py',ROOT/'ai-service/training/pilot_teacher_pairwise_specialists.py',
        previous.OUT/'protocol.json',previous.OUT/'completion.json',previous.OUT/'independent_review.json',
        ROOT/'ai-service/reports/teacher_weak_error_audit_20261024/results.json',
        ROOT/'ai-service/reports/teacher_weak_error_audit_20261024/independent_review.json']
    parent=base.read(ROOT/old['parent_protocol']);rows=prior.role_rows(parent,0,'train');_,counts=group_matrix(rows)
    p=dict(name=OUT.name,registered_utc=features.utc(),fold=0,classes=base.CLASSES,parent_protocol=old['parent_protocol'],
        configuration=CONFIG,train_group_counts=counts,
        frozen_sha256={**old['frozen_sha256'],**{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},
        hypothesis='Repeated source slices show weak SCIN recall. Test adaptive worst-training-group loss against fixed equal-group loss, not source-conditioned inference or label correction.',
        representation='Original fold0 frozen ResNet2048 cache, StandardScaler fit on4043train only. Same zero-init linear5way head in both arms. No CNN fitting, B0/ConvNeXt concatenation, external photos or auxiliary labels.',
        groups='Every nonempty original8label x recorded source(SCIN/original_train) training cell; no minimum-size filtering. Within cell average scene/case groups equally; within case average photos equally. Group metadata not verified patientIDs. Same cells and averaging in both arms.',
        intervention='Control q uniform across all nonempty cells at all400updates. DRO starts same uniform q, then q <- softmax(log(q)+.01*detached group CE) before each primal Adam update. Only q adaptation changes. Full batch CPUfloat64, seed42 zero-init,lr.01,400updates,weight L2 coefficient1/(4043*.001),bias unpenalized. No grid, early stopping or intermediate checkpoint selection; use final iterate.',
        routing=old['routing'],
        selection='Same strict Accuracy/MacroF1 nondecrease, each weakRecall/F1 nondecrease, weakPrecision loss<=.02, otherRecall loss<=.02 and exactCancerP/R versus current on718inner. DRO additionally MF>=uniform and meanweakF1 strictly above current/uniform. Rank MF,meanweakRecall,Accuracy; ties current thenuniform. Lock parameters and selection before outer/source scoring.',
        scope='Exploratory onefold4043train/718inner/1176outer/1709historically examined source photos. ParentCNNs used inner for epoch selection, historical outer read repeatedly. No fresh test or fivefold/global-score update.',
        limitations=old['limitations']+[
            'Full-batch fixed-feature, case-averaged linear-head adaptation of Group DRO; not reproduction of full-network paper benchmarks or a claimed robust diagnosis guarantee.',
            'Source/class groups can be very small and source labels uncertain; adaptive weights can overfocus noise. Regularization and a matched control do not prove reliable labels or causal source-shift correction.',
            'Source grouping uses training metadata only; inference uses image features alone. Final head scores are not calibrated clinical probabilities.',
            'Already completed source-balanced ConvNeXt and source-soft-label ResNet pilots remain separate; this tests dynamic adversarial group weights against uniform group weights.'],
        references=['https://arxiv.org/abs/1911.08731','https://github.com/kohpangwei/group_DRO/blob/master/loss.py'],
        head_fits=2,new_CNN_fits=0,new_backbones=0,global_5937_score_changed=False,serving_changed=False)
    OUT.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p);base.write(OUT/'research_registry_before.json',reg)
    reg['next_experiment']=OUT.relative_to(ROOT).as_posix();reg['next_experiment_status']='registered_matched_group_dro_head_fold0'
    base.write(ROOT/'ai-service/reports/active_research_track.json',reg);return p


def fit_and_lock(p):
    parent=base.read(ROOT/p['parent_protocol']);rows=prior.role_rows(parent,0,'train');x=cache.cached('train',rows)
    scaler=StandardScaler().fit(x);xx=scaler.transform(x.astype(np.float64))
    y=latest.fiveway(np.array([base.CLASSES.index(r['label']) for r in rows]));matrix,counts=group_matrix(rows)
    assert counts==p['train_group_counts'];MODELS.mkdir(parents=True,exist_ok=True);reports={};models={}
    for n,robust in [('uniform_groups',False),('group_dro',True)]:
        model,history=fit(xx,y,matrix,robust,p['configuration'])
        model.update(mean=scaler.mean_,scale=scaler.scale_);models[n]=model
        np.savez_compressed(MODELS/f'{n}.npz',**model,protocol_sha256=base.sha(OUT/'protocol.json'))
        reports[n]=dict(history=history,updates=p['configuration']['updates'],final_q=model['q'].tolist(),
                        final_train_group_losses=(matrix@(-np.log(np.maximum(probabilities(x,model)[np.arange(len(y)),y],1e-300)))).tolist())
        print(dict(branch=n,updates=p['configuration']['updates'],q_range=[float(model['q'].min()),float(model['q'].max())]),flush=True)
    base.write(OUT/'training_report.json',dict(head_fits=2,new_CNN_fits=0,heads=reports,groups=counts))
    rows=prior.role_rows(parent,0,'inner_validation');x=cache.cached('inner_validation',rows)
    with np.load(latest.OUT/'fold_0/inner_decisions.npz',allow_pickle=False) as z:
        assert z['paths'].tolist()==[r['path'] for r in rows]
        truth=z['truth'].copy();current=z[base.read(latest.OUT/'fold_0/selection_locked.json')['selected']].copy()
    qq={n:probabilities(x,m) for n,m in models.items()};dd=dict(current_policy=current)
    dd.update({n:prior.route(current,q) for n,q in qq.items()});lock=choose(dd,truth)
    np.savez_compressed(OUT/'inner_decisions.npz',paths=[r['path'] for r in rows],truth=truth,**dd,**{n+'_q':q for n,q in qq.items()})
    artifacts=[MODELS/f'{n}.npz' for n in models]+[OUT/'training_report.json',OUT/'inner_decisions.npz']
    lock.update(locked_utc=features.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
                artifacts_sha256={x.relative_to(ROOT).as_posix():base.sha(x) for x in artifacts})
    base.write(OUT/'selection_locked.json',lock)
    print(dict(selected=lock['selected'],failures={n:t['guard_failures'] for n,t in lock['trials'].items()}),flush=True)


def evaluate(p):
    assert not (OUT/'results.json').exists(),'Preserve completed pilot'
    lock=base.read(OUT/'selection_locked.json');assert lock['protocol_sha256']==base.sha(OUT/'protocol.json')
    for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
    models={}
    for n in ['uniform_groups','group_dro']:
        with np.load(MODELS/f'{n}.npz',allow_pickle=False) as z:models[n]={k:z[k].copy() for k in ['mean','scale','coef','intercept','q']}
    parent=base.read(ROOT/p['parent_protocol']);source=base.read(features.SOURCE/'protocol.json');started=features.utc()
    original={r['path']:r for r in base.read(latest.OUT/'oof_decisions.json')}
    external={r['path']:r for r in base.read(features.SOURCE/'source_decisions.json')};output=[];scores={}
    for role,rows in [('outer_holdout',prior.role_rows(parent,0,'outer_holdout')),('source_transfer',source['rows'])]:
        x=cache.cached(role,rows);truth=np.array([base.CLASSES.index(r['label']) for r in rows])
        current=np.array([original[r['path']]['predictions']['validation_selected'] if role=='outer_holdout' else external[r['path']]['predictions']['validation_selected'][0] for r in rows])
        qq={n:probabilities(x,m) for n,m in models.items()};dd=dict(current_policy=current)
        dd.update({n:prior.route(current,q) for n,q in qq.items()});dd['validation_selected']=dd[lock['selected']]
        np.savez_compressed(OUT/f'{role}_probabilities.npz',paths=[r['path'] for r in rows],**qq)
        idx={r['path']:i for i,r in enumerate(rows)};slices={'original_outer':list(idx)} if role=='outer_holdout' else source['subsets']
        for name,paths in slices.items():
            ids=[idx[path] for path in paths];scores[name]=dict(images=len(ids),methods={n:base.metrics(d[ids],truth[ids]) for n,d in dd.items()})
        output.extend(dict(**r,role=role,predictions={n:int(d[i]) for n,d in dd.items()}) for i,r in enumerate(rows))
    base.write(OUT/'held_decisions.json',output)
    r=dict(status='complete_exploratory_group_dro_head',fold=0,selected=lock['selected'],validation=lock['trials'],held=scores,
        held_started_utc=started,completed_utc=features.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),selection_sha256=base.sha(OUT/'selection_locked.json'),
        train_images=4043,train_groups=p['train_group_counts'],head_fits=2,updates_each=p['configuration']['updates'],new_CNN_fits=0,
        global_5937_score_changed=False,serving_changed=False,limitations=p['limitations'])
    base.write(OUT/'results.json',r);prior.verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json')))
    print(dict(inner={n:{k:t['metrics'][k] for k in ['accuracy','macro_f1']} for n,t in r['validation'].items()},
               outer={n:{k:s[k] for k in ['accuracy','macro_f1']} for n,s in scores['original_outer']['methods'].items()}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    with threadpool_limits(limits=2):
        p=prepare()
        if args.prepare_only:return
        assert not (OUT/'results.json').exists(),'Preserve completed pilot'
        if not (OUT/'selection_locked.json').exists():fit_and_lock(p)
        evaluate(p)


if __name__=='__main__':main()
