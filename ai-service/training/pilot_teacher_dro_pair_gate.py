"""Cross-fitted keep/switch gate for the frozen Group DRO Tinea/Eczema proposals."""
from __future__ import annotations
import argparse
from pathlib import Path
import warnings

import numpy as np
from scipy.special import expit
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

import pilot_teacher_group_dro as previous

ROOT,base,prior,latest,latent=previous.ROOT,previous.base,previous.prior,previous.latest,previous.features
OUT=ROOT/'ai-service/reports/teacher_dro_pair_gate_fold0_seed42_20261024'
MODELS=ROOT/'ai-service/candidates'/OUT.name
METHODS=['current_policy','fixed_pair_control','learned_pair_gate']
THRESHOLD=2/3
FEATURE_NAMES=['b0_log_T_over_E','convnext_log_T_over_E','resnet_log_T_over_E',
    'dro_Lupus','dro_Psoriasis','dro_Tinea','dro_Eczema','dro_Other',
    'parent_Tinea_votes','parent_Eczema_votes','current_is_Tinea','dro_pair_mass','dro_pair_margin','dro_entropy']


def proposals(current,q):
    current=np.asarray(current);q=np.asarray(q,dtype=float)
    if (current.ndim!=1 or q.shape!=(len(current),5) or not np.isfinite(q).all()
        or (q<0).any() or not np.allclose(q.sum(1),1,atol=1e-8)):
        raise ValueError('Aligned current calls and five-way probabilities required')
    target=q.argmax(1);pred=current.copy()
    mask=np.isin(current,[2,6]) & np.isin(target,[2,3])
    pred[mask]=np.array([3,4,6,2,0])[target[mask]]
    return pred,mask&(pred!=current)


def inputs(parent_probabilities,q,current):
    arrays=[np.asarray(a,dtype=float) for a in parent_probabilities]
    if len(arrays)!=3 or any(a.shape!=(len(current),8) or not np.isfinite(a).all() or (a<0).any()
                              or not np.allclose(a.sum(1),1,atol=1e-6) for a in arrays):
        raise ValueError('Three aligned original-eight probability matrices required')
    proposals(current,q)  # validate the candidate probabilities too
    q=np.asarray(q,dtype=float);pair=q[:,2]+q[:,3]
    odds=np.column_stack([np.log(np.maximum(a[:,6],1e-12))-np.log(np.maximum(a[:,2],1e-12)) for a in arrays])
    votes=np.column_stack([np.mean([a.argmax(1)==label for a in arrays],axis=0) for label in [6,2]])
    extra=np.column_stack([np.asarray(current)==6,pair,
        np.divide(q[:,2]-q[:,3],pair,out=np.zeros(len(q)),where=pair>0),
        -(q*np.log(np.maximum(q,1e-12))).sum(1)])
    result=np.column_stack([odds,q,votes,extra]);assert result.shape==(len(current),14)
    return result


def targets(current,candidate,truth):
    current,candidate,truth=[np.asarray(a) for a in [current,candidate,truth]]
    if current.ndim!=1 or current.shape!=candidate.shape or current.shape!=truth.shape:
        raise ValueError('Aligned one-dimensional predictions/labels required')
    result=np.full(len(current),-1,dtype=int)
    scope=np.isin(current,[2,6]) & np.isin(candidate,[2,6]) & (candidate!=current)
    result[scope&(candidate==truth)]=1
    result[scope&(current==truth)]=0
    return result


def fit_gate(x,target,groups):
    mask=target>=0;counts=np.bincount(target[mask],minlength=2)
    by_sign=[len(set(np.asarray(groups)[mask&(target==sign)])) for sign in [0,1]]
    report=dict(input_rows=len(x),fit_rows=int(mask.sum()),targets=counts.tolist(),scene_groups_by_target=by_sign)
    if min(by_sign)<2:
        model=dict(kind=np.array('always_keep'),mean=np.zeros(14),scale=np.ones(14),coef=np.zeros((1,14)),intercept=np.zeros(1),classes=np.array([0,1]))
        report.update(kind='always_keep',iterations=[],reason='Fewer than two distinct scene/case groups for either fix or harm target')
    else:
        scaler=StandardScaler().fit(x[mask])
        with warnings.catch_warnings():
            warnings.simplefilter('error',ConvergenceWarning)
            head=LogisticRegression(C=.1,solver='lbfgs',max_iter=3000,tol=1e-7,random_state=42).fit(scaler.transform(x[mask]),target[mask])
        model=dict(kind=np.array('logistic'),mean=scaler.mean_,scale=scaler.scale_,coef=head.coef_,intercept=head.intercept_,classes=head.classes_)
        report.update(kind='logistic',iterations=head.n_iter_.tolist())
    return model,report


def gate_score(model,x):
    return np.zeros(len(x)) if str(model['kind'])=='always_keep' else expit(((x-model['mean'])/model['scale'])@model['coef'][0]+model['intercept'][0])


def route(current,candidate,score,threshold=THRESHOLD):
    pred=np.asarray(current).copy();candidate=np.asarray(candidate);score=np.asarray(score)
    mask=np.isin(pred,[2,6]) & np.isin(candidate,[2,6]) & (candidate!=pred) & (score>threshold)
    pred[mask]=candidate[mask]
    assert np.array_equal(pred==5,np.asarray(current)==5)
    return pred


def choose(decisions,truth):
    scores={n:base.metrics(d,truth) for n,d in decisions.items()}
    trials={n:dict(metrics=s,guard_failures=prior.failures(s,scores['current_policy'])) for n,s in scores.items()}
    new=scores['learned_pair_gate'];control=scores['fixed_pair_control']
    for key in ['accuracy','macro_f1']:
        if new[key]+1e-12<control[key]:trials['learned_pair_gate']['guard_failures'].append(key+'_below_fixed_control')
    if latest.previous.mean_focus(new)+1e-12<latest.previous.mean_focus(control):
        trials['learned_pair_gate']['guard_failures'].append('mean_weak_f1_below_fixed_control')
    passing=[n for n in METHODS if not trials[n]['guard_failures']]
    selected=max(passing,key=lambda n:(scores[n]['macro_f1'],latest.previous.mean_focus(scores[n],'recall'),
                                      scores[n]['accuracy'],n=='current_policy',n=='fixed_pair_control'))
    return dict(selected=selected,trials=trials)


def parent_probabilities(role,paths):
    result=[]
    for arch in ['efficientnet_b0','convnext_tiny','resnet50']:
        path=(latent.SOURCE/'fold_0_resnet_features.npz' if role=='source_transfer' else prior.OUT/f'B_specialist/fold_0/{role}_features.npz') if arch=='resnet50' else latent.OUT/f'{role}_{arch}_features.npz'
        with np.load(path,allow_pickle=False) as z:
            lookup={p:i for i,p in enumerate(z['paths'].tolist())};result.append(z['probabilities'][[lookup[p] for p in paths]].copy())
    return result


def role_data(p,role):
    parent=base.read(ROOT/p['parent_protocol'])
    rows=base.read(latent.SOURCE/'protocol.json')['rows'] if role=='source_transfer' else prior.role_rows(parent,0,role)
    paths=[r['path'] for r in rows];truth=np.array([base.CLASSES.index(r['label']) for r in rows])
    if role=='inner_validation':
        with np.load(previous.OUT/'inner_decisions.npz',allow_pickle=False) as z:
            assert z['paths'].tolist()==paths;current=z['current_policy'].copy();q=z['group_dro_q'].copy()
    else:
        original={r['path']:r for r in base.read(latest.OUT/'oof_decisions.json')}
        source={r['path']:r for r in base.read(latent.SOURCE/'source_decisions.json')}
        current=np.array([original[path]['predictions']['validation_selected'] if role=='outer_holdout' else source[path]['predictions']['validation_selected'][0] for path in paths])
        with np.load(previous.OUT/f'{role}_probabilities.npz',allow_pickle=False) as z:
            assert z['paths'].tolist()==paths;q=z['group_dro'].copy()
    x=inputs(parent_probabilities(role,paths),q,current);candidate,eligible=proposals(current,q)
    fixed=current.copy();change=eligible&(q.max(1)>=.8);fixed[change]=candidate[change]
    return rows,truth,current,q,x,candidate,eligible,fixed


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');prior.verify(p);return p
    old=base.read(previous.OUT/'protocol.json');prior.verify(old)
    assert base.read(previous.OUT/'completion.json')['status']=='complete_verified_pilot_not_selected'
    reg=base.read(ROOT/'ai-service/reports/active_research_track.json');assert reg['next_experiment'] is None
    files=[Path(__file__),Path(previous.__file__),ROOT/'ai-service/tests/test_teacher_dro_pair_gate.py',
        previous.OUT/'protocol.json',previous.OUT/'results.json',previous.OUT/'selection_locked.json',
        previous.OUT/'training_report.json',previous.OUT/'completion.json',previous.OUT/'independent_review.json',
        previous.OUT/'inner_decisions.npz',previous.OUT/'outer_holdout_probabilities.npz',previous.OUT/'source_transfer_probabilities.npz',
        previous.MODELS/'group_dro.npz']
    p=dict(name=OUT.name,registered_utc=latent.utc(),fold=0,classes=base.CLASSES,parent_protocol=old['parent_protocol'],
        frozen_sha256={**old['frozen_sha256'],**{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},
        candidate='Re-use verified GroupDRO head400updates trained on4043originaltrain only. Raw five-way argmax must be Tinea/Eczema and current must be the other member of that pair. All other current predictions kept, including Cancer. No true-label/source-based runtime rules or candidate refits.',
        inputs=FEATURE_NAMES,input_details='14image-derived runtime features:3originalparent log(Tinea/Eczema) with floor1e-12,5DRO scores,3parent top1 vote fractions forT/E,current-isTinea,DROpairmass,normalized pairmargin and5wayentropy. Frozen caches with inherited CPU/GPU numerical provenance; no raw photos/sourceIDs/labels as inputs.',
        control='Same frozen raw candidate, change only if its full5way maxscore>=.8. Learned policy replaces this cutoff with a logistic keep/switch gate and fixed switchscore>2/3. This compares complete gating policies, not isolated threshold or feature effects.',
        training='Only718inner labels train binary targets:1currentwrong/candidatecorrect,0currentcorrect/candidatewrong; ignore same/wrong-to-wrong. StandardScaler fit only decisive fit rows, LogisticRegression C.1 LBFGS tol1e-7 max3000 seed42,no class/sample weighting. Fallback alwayskeep if either outcome has fewer than2scene/casegroups. Source metadata and true disease never used at runtime.',
        crossfit='StratifiedGroupKFold3 shuffle seed42 over original718labels/groups. Fit on2parts, predict heldpart; every row held once. Select current/fixed/gate by pooled meta-held inner decisions, never gate in-sample scores. Final gate refit on all718inner for outer/source. Candidate heads fixed and trained on4043train, not on inner labels.',
        selection='Existing strict Accuracy/MacroF1, each weakRecall/F1, weakPrecision<=2pp decline, otherRecall<=2pp decline and exactCancerP/R. Learned must also Accuracy/MacroF1/meanweakF1>=fixedpair. Rank MF,meanweakRecall,Accuracy,prefercurrent thenfixed on tie. Lock allcrossfit/finalgate artifacts before outer/source application. No C/threshold/feature search.',
        threshold=THRESHOLD,C=.1,meta_parts=3,seed=42,min_outcome_groups=2,
        limitations=old['limitations']+[
            'This learns a selector for the already rejected head rather than selecting a head by its favorable outer result; all gate fitting/selection uses inner only. Historical outer and inner have already been inspected, so new comparison remains exploratory, not independent confirmation.',
            'Three meta parts are gate cross-fitting within one CNN fold, not three new independent training seeds or a fivefold improvement.',
            'Original CNN checkpoints and retained upstream policy previously used inner labels for selection/training. Cross-fitting this final gate alone does not make the full pipeline strictly nested.',
            'Restricting current calls to Tinea/Eczema does not guarantee preservation of trueLupus/Psoriasis or precision; their mislabeled-asEczema/Tinea rows may change, hence allclass guards remain.',
            'Fix/harm target neglects informative wrong-to-wrong F1 effects; strict full-metric selection checks resulting decisions. Very few disagreement groups can force alwayskeep.',
            'Gate switch score is not a calibrated probability of diagnosis or a guaranteed net benefit. No clinical label review/new patient test.'],
        references=['https://scikit-learn.org/1.3/modules/generated/sklearn.ensemble.StackingClassifier.html',
                    'https://scikit-learn.org/1.3/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html'],
        candidate_head_fits=0,new_CNN_fits=0,new_backbones=0,global_5937_score_changed=False,serving_changed=False)
    OUT.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p);base.write(OUT/'research_registry_before.json',reg)
    reg['next_experiment']=OUT.relative_to(ROOT).as_posix();reg['next_experiment_status']='registered_crossfit_dro_Tinea_Eczema_gate'
    base.write(ROOT/'ai-service/reports/active_research_track.json',reg);return p


def fit_and_lock(p):
    rows,y,current,q,x,candidate,eligible,fixed=role_data(p,'inner_validation');groups=np.array([r['group'] for r in rows]);target=targets(current,candidate,y)
    MODELS.mkdir(parents=True,exist_ok=True);score=np.full(len(rows),np.nan);reports=[];folds=np.full(len(rows),-1)
    cv=StratifiedGroupKFold(n_splits=3,shuffle=True,random_state=42)
    for part,(fit,hold) in enumerate(cv.split(x,y,groups)):
        assert not set(groups[fit])&set(groups[hold]);model,report=fit_gate(x[fit],target[fit],groups[fit])
        np.savez_compressed(MODELS/f'meta_{part}.npz',**model)
        score[hold]=gate_score(model,x[hold]);folds[hold]=part
        np.savez_compressed(OUT/f'meta_{part}.npz',fit_indices=fit,hold_indices=hold,targets=target[fit],held_scores=score[hold])
        reports.append(dict(part=part,fit_indices=fit.tolist(),hold_indices=hold.tolist(),**report))
    assert np.isfinite(score).all() and (folds>=0).all()
    dd=dict(current_policy=current,fixed_pair_control=fixed,learned_pair_gate=route(current,candidate,score));lock=choose(dd,y)
    model,final=fit_gate(x,target,groups);np.savez_compressed(MODELS/'final_gate.npz',**model)
    np.savez_compressed(OUT/'inner_crossfit.npz',paths=[r['path'] for r in rows],truth=y,current=current,candidate=candidate,
        eligible=eligible,gate_features=x,targets=target,gate_scores=score,meta_part=folds,dro_q=q,**dd)
    base.write(OUT/'training_report.json',dict(meta_parts=reports,final=final,logistic_fits=sum(v['kind']=='logistic' for v in reports+[final]),
        always_keep=sum(v['kind']=='always_keep' for v in reports+[final]),candidate_head_fits=0,new_CNN_fits=0))
    artifacts=[*MODELS.glob('*.npz'),*OUT.glob('*.npz'),OUT/'training_report.json']
    lock.update(locked_utc=latent.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
                artifacts_sha256={z.relative_to(ROOT).as_posix():base.sha(z) for z in artifacts})
    base.write(OUT/'selection_locked.json',lock)
    print(dict(selected=lock['selected'],final=final,failures={n:v['guard_failures'] for n,v in lock['trials'].items()}),flush=True)


def evaluate(p):
    assert not (OUT/'results.json').exists(),'Preserve completed experiment'
    lock=base.read(OUT/'selection_locked.json');assert lock['protocol_sha256']==base.sha(OUT/'protocol.json')
    for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
    with np.load(MODELS/'final_gate.npz',allow_pickle=False) as z:model={k:z[k].copy() for k in z.files}
    source=base.read(latent.SOURCE/'protocol.json');started=latent.utc();output=[];scores={}
    for role in ['outer_holdout','source_transfer']:
        rows,y,current,q,x,candidate,eligible,fixed=role_data(p,role);score=gate_score(model,x)
        dd=dict(current_policy=current,fixed_pair_control=fixed,learned_pair_gate=route(current,candidate,score));dd['validation_selected']=dd[lock['selected']]
        np.savez_compressed(OUT/f'{role}_gate.npz',paths=[r['path'] for r in rows],gate_features=x,candidate=candidate,gate_scores=score,eligible=eligible)
        idx={r['path']:i for i,r in enumerate(rows)};slices={'original_outer':list(idx)} if role=='outer_holdout' else source['subsets']
        for name,paths in slices.items():
            ids=[idx[path] for path in paths];scores[name]=dict(images=len(ids),methods={n:base.metrics(d[ids],y[ids]) for n,d in dd.items()})
        output.extend(dict(**r,role=role,candidate=int(candidate[i]),gate_score=float(score[i]),predictions={n:int(d[i]) for n,d in dd.items()}) for i,r in enumerate(rows))
    base.write(OUT/'held_decisions.json',output)
    r=dict(status='complete_exploratory_crossfit_dro_pair_gate',fold=0,selected=lock['selected'],validation=lock['trials'],held=scores,
        held_started_utc=started,completed_utc=latent.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),selection_sha256=base.sha(OUT/'selection_locked.json'),
        candidate_head_fits=0,new_CNN_fits=0,global_5937_score_changed=False,serving_changed=False,limitations=p['limitations'])
    base.write(OUT/'results.json',r);prior.verify(p);base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json')))
    print(dict(inner={n:{k:v['metrics'][k] for k in ['accuracy','macro_f1']} for n,v in r['validation'].items()},outer={n:{k:s[k] for k in ['accuracy','macro_f1']} for n,s in scores['original_outer']['methods'].items()}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    with threadpool_limits(limits=2):
        p=prepare()
        if args.prepare_only:return
        assert not (OUT/'results.json').exists(),'Preserve completed pilot'
        if not (OUT/'selection_locked.json').exists():fit_and_lock(p)
        evaluate(p)


if __name__=='__main__':main()
