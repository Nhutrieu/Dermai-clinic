"""Isolated 50/50 class-loss mass ablation for locked binary disease pairs."""
from __future__ import annotations
import argparse
from pathlib import Path

import numpy as np
from scipy.special import expit
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

import pilot_teacher_pairwise_specialists as parent

ROOT,base,prior,latest,features=parent.ROOT,parent.base,parent.prior,parent.latest,parent.features
NAME='teacher_balanced_pairs_fold0_seed42_20261024'
OUT=ROOT/'ai-service/reports'/NAME
MODELS=ROOT/'ai-service/candidates'/NAME
METHODS=['current_policy','uniform_pairs','balanced_pairs']


def weights(y,total,balanced):
    labels,counts=np.unique(y,return_counts=True)
    if len(labels)!=2 or total<=0:raise ValueError('Two classes and positive total mass required')
    return (np.array([total/(2*counts[np.flatnonzero(labels==c)[0]]) for c in y])
            if balanced else np.full(len(y),total/len(y)))


def choose(decisions,truth):
    scores={n:base.metrics(d,truth) for n,d in decisions.items()}
    trials={n:dict(metrics=s,guard_failures=prior.failures(s,scores['current_policy'])) for n,s in scores.items()}
    treatment=scores['balanced_pairs']
    if treatment['macro_f1']+1e-12<scores['uniform_pairs']['macro_f1']:
        trials['balanced_pairs']['guard_failures'].append('macro_f1_below_uniform_control')
    for name in ['uniform_pairs','current_policy']:
        if latest.previous.mean_focus(treatment)<=latest.previous.mean_focus(scores[name])+1e-12:
            trials['balanced_pairs']['guard_failures'].append('no_weak_mean_f1_gain_vs_'+name)
    passing=[n for n in METHODS if not trials[n]['guard_failures']]
    selected=max(passing,key=lambda n:(scores[n]['macro_f1'],latest.previous.mean_focus(scores[n],'recall'),
                    scores[n]['accuracy'],n=='current_policy',n=='uniform_pairs'))
    return dict(selected=selected,trials=trials)


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');prior.verify(p);return p
    registry=base.read(ROOT/'ai-service/reports/active_research_track.json');assert registry['next_experiment'] is None
    old=base.read(parent.OUT/'protocol.json');prior.verify(old)
    assert base.read(parent.OUT/'completion.json')['status']=='complete_verified_pilot_not_selected'
    pairs=base.read(parent.OUT/'pairs_locked.json')['pairs']
    files=[Path(__file__),ROOT/'ai-service/tests/test_teacher_balanced_pairs.py',
        ROOT/'ai-service/training/pilot_teacher_pairwise_specialists.py',
        parent.OUT/'protocol.json',parent.OUT/'completion.json',parent.OUT/'independent_review.json',
        parent.OUT/'pairs_locked.json',parent.OUT/'pair_discovery.json',parent.OUT/'selection_locked.json',
        parent.OUT/'inner_decisions.npz',parent.OUT/'results.json',parent.OUT/'held_decisions.json']
    files+=[parent.MODELS/f'pair_{a}_{b}.npz' for a,b in pairs]
    p=dict(name=NAME,registered_utc=features.utc(),fold=0,classes=base.CLASSES,pairs=pairs,
        parent_protocol=old['parent_protocol'],configuration=parent.CONFIG,
        frozen_sha256={**old['frozen_sha256'],**{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},
        intervention='Only change binary pair sample loss weights: uniform4043/n_pair versus4043/(2*n_class), equal total mass4043. No change to locked train-discovered pairs, original frozen ResNet2048 features, full-train StandardScaler, C=.001, original labels, fixed.8 threshold or conflict routing.',
        control='Refit all3 uniform pair heads and require their scaler, coefficients and intercept to reproduce the completed parent within1e-10. Both arms use the same full-train scaler; fit6 binary heads, no rediscovery, no CNN training or auxiliary data.',
        selection='Strict existing perweakRecall/F1,Accuracy/MacroF1,weakPrecision and otherRecall guards versus current. Balanced additionally MF>=uniform and meanweakF1 strictly above both uniform/current. Rank MF,meanweakRecall,Accuracy,ties current then uniform. Choose on718inner, lock before new outer/source prediction; no threshold/weight search.',
        routing=old['routing'],scope='Onefold pilot4043train/718inner/1176outer/1709known-source. No new5937score; any follow-up fullCV separately registered.',
        limitations=old['limitations']+[
            'The 50/50 loss deliberately changes pair class priors. It may improve rare-disease recall while increasing false positives. No claim of calibrated confidence.',
            'Pair selection is inherited unchanged, including only one train-head held Lupus-Acne confusion. The balance ablation does not establish a robust rival for Lupus.'],
        new_CNN_fits=0,new_backbones=0,global_5937_score_changed=False,serving_changed=False)
    OUT.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p);base.write(OUT/'research_registry_before.json',registry)
    registry['next_experiment']=OUT.relative_to(ROOT).as_posix();registry['next_experiment_status']='registered_binary_pair_class_balance_fold0'
    base.write(ROOT/'ai-service/reports/active_research_track.json',registry)
    return p


def probabilities(x,pairs):
    result={}
    for name in ['uniform_pairs','balanced_pairs']:
        qq=[]
        for a,b in pairs:
            with np.load(MODELS/f'{name}_{a}_{b}.npz',allow_pickle=False) as z:model={k:z[k].copy() for k in z.files}
            positive=expit(parent.logits(model,x)[:,0]);qq.append(np.column_stack([1-positive,positive]))
        result[name]=np.stack(qq,axis=1) if qq else np.empty((len(x),0,2))
    return result


def fit_and_lock(p):
    old=base.read(ROOT/p['parent_protocol']);rows=prior.role_rows(old,0,'train')
    x=parent.cached('train',rows);truth=np.array([base.CLASSES.index(r['label']) for r in rows])
    scaler=StandardScaler().fit(x);MODELS.mkdir(parents=True,exist_ok=True);report={};max_error=0.
    for name,balanced in [('uniform_pairs',False),('balanced_pairs',True)]:
        for a,b in p['pairs']:
            mask=np.isin(truth,[a,b]);w=weights(truth[mask],len(rows),balanced)
            model,it=parent.fit(x[mask],truth[mask],w,scaler)
            assert abs(w.sum()-len(rows))<1e-9
            np.savez_compressed(MODELS/f'{name}_{a}_{b}.npz',**model)
            report[f'{name}_{a}_{b}']=dict(images=int(mask.sum()),iterations=it,total_mass=float(w.sum()),
                class_mass={base.CLASSES[c]:float(w[truth[mask]==c].sum()) for c in [a,b]},
                class_weight={base.CLASSES[c]:float(w[truth[mask]==c][0]) for c in [a,b]})
            if not balanced:
                with np.load(parent.MODELS/f'pair_{a}_{b}.npz',allow_pickle=False) as z:
                    error=max(float(np.abs(z[k]-model[k]).max()) for k in ['mean','scale','coef','intercept','classes','logit_multiplier'])
                assert error<1e-10;max_error=max(max_error,error)
    base.write(OUT/'training_report.json',dict(head_fits=len(report),uniform_control_max_error=max_error,heads=report))
    inner=prior.role_rows(old,0,'inner_validation')
    with np.load(latest.OUT/'fold_0/inner_decisions.npz',allow_pickle=False) as z:
        assert z['paths'].tolist()==[r['path'] for r in inner]
        current=z[base.read(latest.OUT/'fold_0/selection_locked.json')['selected']].copy();yy=z['truth'].copy()
    qq=probabilities(parent.cached('inner_validation',inner),p['pairs'])
    dd=dict(current_policy=current);dd.update({n:parent.pair_route(current,q,p['pairs']) for n,q in qq.items()})
    with np.load(parent.OUT/'inner_decisions.npz',allow_pickle=False) as z:assert np.array_equal(z['binary_pairs'],dd['uniform_pairs'])
    lock=choose(dd,yy)
    np.savez_compressed(OUT/'inner_decisions.npz',paths=[r['path'] for r in inner],truth=yy,
        uniform_probability=qq['uniform_pairs'],balanced_probability=qq['balanced_pairs'],**dd)
    lock.update(locked_utc=features.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
        artifacts_sha256={x.relative_to(ROOT).as_posix():base.sha(x) for x in [*MODELS.glob('*.npz'),OUT/'training_report.json',OUT/'inner_decisions.npz']})
    base.write(OUT/'selection_locked.json',lock)
    print(dict(selected=lock['selected'],failures={n:t['guard_failures'] for n,t in lock['trials'].items()}),flush=True)


def evaluate(p):
    assert not (OUT/'results.json').exists(),'Preserve completed pilot'
    lock=base.read(OUT/'selection_locked.json');assert lock['protocol_sha256']==base.sha(OUT/'protocol.json')
    for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
    started=features.utc();old=base.read(ROOT/p['parent_protocol']);source=base.read(features.SOURCE/'protocol.json')
    outer={r['path']:r for r in base.read(latest.OUT/'oof_decisions.json')};external={r['path']:r for r in base.read(features.SOURCE/'source_decisions.json')}
    scores={};output=[]
    for role,rows in [('outer_holdout',prior.role_rows(old,0,'outer_holdout')),('source_transfer',source['rows'])]:
        yy=np.array([base.CLASSES.index(r['label']) for r in rows]);current=np.array([outer[r['path']]['predictions']['validation_selected'] if role=='outer_holdout' else external[r['path']]['predictions']['validation_selected'][0] for r in rows])
        qq=probabilities(parent.cached(role,rows),p['pairs']);dd=dict(current_policy=current)
        dd.update({n:parent.pair_route(current,q,p['pairs']) for n,q in qq.items()});dd['validation_selected']=dd[lock['selected']]
        np.savez_compressed(OUT/f'{role}_probabilities.npz',paths=[r['path'] for r in rows],**qq)
        idx={r['path']:i for i,r in enumerate(rows)};slices={'original_outer':list(idx)} if role=='outer_holdout' else source['subsets']
        for name,paths in slices.items():
            ii=[idx[path] for path in paths];scores[name]=dict(images=len(ii),methods={n:base.metrics(d[ii],yy[ii]) for n,d in dd.items()})
        output.extend(dict(**r,role=role,predictions={n:int(d[i]) for n,d in dd.items()}) for i,r in enumerate(rows))
    base.write(OUT/'held_decisions.json',output)
    r=dict(status='complete_exploratory_binary_balance_pilot',fold=0,selected=lock['selected'],pairs=p['pairs'],
        validation=lock['trials'],held=scores,head_fits=base.read(OUT/'training_report.json')['head_fits'],
        held_started_utc=started,completed_utc=features.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
        selection_sha256=base.sha(OUT/'selection_locked.json'),new_CNN_fits=0,global_5937_score_changed=False,serving_changed=False,limitations=p['limitations'])
    base.write(OUT/'results.json',r);prior.verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),uniform_control_reproduced=True))
    print(dict(inner={n:{k:t['metrics'][k] for k in ['accuracy','macro_f1']} for n,t in r['validation'].items()},
        outer={n:{k:s[k] for k in ['accuracy','macro_f1']} for n,s in scores['original_outer']['methods'].items()}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    with threadpool_limits(limits=1):
        p=prepare()
        if args.prepare_only:return
        assert not (OUT/'results.json').exists(),'Preserve completed pilot'
        if not (OUT/'selection_locked.json').exists():
            assert not (OUT/'training_report.json').exists(),'Audit partial fit before continuing'
            fit_and_lock(p)
        evaluate(p)


if __name__=='__main__':main()
