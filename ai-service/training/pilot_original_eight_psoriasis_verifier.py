"""Fixed Psoriasis promotion verifier. No threshold search or backbone updates."""
from __future__ import annotations

import argparse
import json
import warnings
from collections import Counter

import numpy as np
import torch
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

import evaluate_original_eight_cancer_locked_fusion as fusion
import pilot_original_eight_balanced_softmax as prior
import pilot_original_eight_psoriasis_replay as replay
from pilot_original_eight_frozen_cancer_head import Features

ROOT=prior.ROOT
NAME='original_eight_psoriasis_verifier_fold0_seed42_20261021'
OUT=ROOT/'ai-service/reports'/NAME
MODELS=ROOT/'ai-service/candidates'/NAME
BRANCHES=['original_only','with_auxiliary']
THRESHOLD=.8


def route(current,proposal,probability):
    current=np.asarray(current);proposal=np.asarray(proposal);probability=np.asarray(probability)
    if current.ndim!=1 or current.shape!=proposal.shape or current.shape!=probability.shape:
        raise ValueError('Expected aligned one-dimensional inputs')
    if not np.isfinite(probability).all() or ((probability<0)|(probability>1)).any():
        raise ValueError('Invalid verifier scores')
    result=current.copy()
    promote=np.isin(current,[2,6]) & (proposal==4) & (probability>=THRESHOLD)
    result[promote]=4
    assert np.array_equal(result==5,current==5)
    return result


def sample_weights(rows,auxiliary):
    strata=[('negative',[i for i,r in enumerate(rows) if r['label']!='Psoriasis'],.5),
            ('original_positive',[i for i,r in enumerate(rows) if r['label']=='Psoriasis' and not r.get('auxiliary',False)],.375 if auxiliary else .5)]
    if auxiliary:strata.append(('auxiliary_positive',[i for i,r in enumerate(rows) if r.get('auxiliary',False)],.125))
    w=np.zeros(len(rows))
    for _,indices,mass in strata:
        if not indices:raise ValueError('Empty training stratum')
        groups=Counter(rows[i]['group'] for i in indices)
        for i in indices:w[i]=mass/len(groups)/groups[rows[i]['group']]
    assert np.isclose(w.sum(),1) and (w>0).all()
    return w*len(rows)


def failures(candidate,current):
    result=fusion.guard_failures(candidate,current)
    for label in ['Lupus','Psoriasis','Tinea']:
        if candidate['per_class'][label]['f1']+1e-12<current['per_class'][label]['f1']:
            result.append(label+'_f1')
    for key in ['precision','recall']:
        if candidate['per_class']['Psoriasis'][key]+1e-12<current['per_class']['Psoriasis'][key]:
            result.append('Psoriasis_'+key)
    return result


def choose(scores):
    trials={name:dict(metrics=value,guard_failures=[] if name=='current_fusion' else failures(value,scores['current_fusion'])) for name,value in scores.items()}
    eligible=[name for name,value in trials.items() if not value['guard_failures']]
    selected=max(eligible,key=lambda name:(scores[name]['macro_f1'],scores[name]['per_class']['Psoriasis']['f1'],scores[name]['accuracy'],name=='current_fusion',name=='original_only'))
    return selected,trials


def check(p):
    for path,h in p['frozen_sha256'].items():assert fusion.sha(ROOT/path)==h,path


def prepare():
    assert not (OUT/'protocol.json').exists(),'Preserve registered experiment'
    source=fusion.read(replay.OUT/'protocol.json')
    assert fusion.read(replay.OUT/'independent_review.json')['status']=='PASS'
    roles=source['roles'];aux=[dict(r,auxiliary=True) for r in source['auxiliary']]
    assert len(aux)==321
    files=[replay.OUT/'protocol.json',replay.OUT/'results.json',replay.OUT/'independent_review.json',
        replay.OUT/'outer_decisions.json',replay.MODELS/'psoriasis_aux/inner_predictions.json',
        prior.PARENT,prior.PARENT_REPORT/'validation_predictions.npz',prior.PARENT_REPORT/'test_predictions.json',
        prior.CURRENT/'fold_0/selection_locked.json',fusion.SERVING,fusion.BENCHMARK,
        ROOT/'ai-service/reports/active_research_track.json']
    # Registry is live metadata, not a frozen experimental input.
    files=files[:-1]
    files += [ROOT/'ai-service/training'/name for name in ['pilot_original_eight_psoriasis_verifier.py',
        'pilot_original_eight_frozen_cancer_head.py','common.py','evaluate_original_eight_cancer_locked_fusion.py']]
    p=dict(name=NAME,date='2026-10-21',classes=fusion.CLASSES,roles=roles,auxiliary=aux,
        initial_checkpoint=prior.PARENT.relative_to(ROOT).as_posix(),
        frozen_sha256={path.relative_to(ROOT).as_posix():fusion.sha(path) for path in files},
        config=dict(C=.001,solver='lbfgs',max_iter=3000,tol=1e-7,seed=42,threshold=THRESHOLD),
        training='Frozen original fold0 ResNet50, eval FP32 2048 features. Two fixed logistic heads: original4043 only and original4043+321auxiliary. Fit each scaler only on its own train rows with identical weights used by the head. Positive/negative mass .5/.5; with auxiliary, positive original/aux mass .375/.125. Equal scene-group mass within each stratum, then equal photo mass within group. No C/threshold/epoch search.',
        routing='Start current cancer-locked fusion. Only current Eczema/Tinea predictions may change to Psoriasis, only if the fixed .75 original B0/Conv reference + .25 previously trained auxiliary ResNet proposes Psoriasis AND verifier score >=.8. Preserve all current Psoriasis calls and every other class decision mask. Scores are not calibrated clinical confidence.',
        selection='On718 inner images: Accuracy and MacroF1 no decline; existing cancer/nonfocus/focus guards; Lupus/Psoriasis/Tinea F1 no decline; Psoriasis precision and recall no decline. Rank MacroF1, PsoriasisF1, Accuracy; prefer current on tie, then original-only. Lock before reading outer arrays. Report both heads, no tuning after results.',
        limitations=['Previously explored fold0/seed; all roles have historical research exposure. This is exploratory development, not a new independent clinical test.',
            'Frozen backbone had already learned training labels and used inner validation for checkpoint selection; this is not fully cross-fitted backbone training.',
            'No new CNN architecture; two lightweight heads and existing auxiliary proposal. Eight labels unchanged.',
            'Scene groups are not verified patient IDs. Auxiliary atlas labels are not newly doctor reviewed.',
            'One fold only. Full5937 OOF score, serving checkpoint and Word unchanged. No automatic expansion.'])
    for rr in [*roles.values(),aux]:
        for r in rr:assert fusion.sha(ROOT/r['path'])==r['sha256']
    fusion.write(OUT/'protocol.json',p)
    registry_path=ROOT/'ai-service/reports/active_research_track.json'
    registry=fusion.read(registry_path)
    registry['next_experiment']=str(OUT.relative_to(ROOT)).replace('\\','/')
    registry['next_experiment_status']='registered_fixed_psoriasis_verifier'
    fusion.write(registry_path,registry)
    return p


def probability(path,x):
    with np.load(path,allow_pickle=False) as a:
        logits=((x-a['mean'])/a['scale'])@a['coefficients'].T+a['intercept']
    return 1/(1+np.exp(-np.clip(logits[:,0],-700,700)))


def cache(extractor,rows,name):
    path=OUT/(name+'_features.npz')
    assert not path.exists(),'Preserve feature cache'
    x,raw=extractor.infer(rows)
    np.savez_compressed(path,paths=[r['path'] for r in rows],features=x,original_resnet=raw)
    print(json.dumps(dict(features=name,images=len(rows))),flush=True)
    return x,raw


def run(p):
    assert not (OUT/'results.json').exists()
    check(p);torch.set_num_threads(4)
    extractor=Features(p);train=p['roles']['train'];aux=p['auxiliary']
    x,_=cache(extractor,train+aux,'train')
    training={};MODELS.mkdir(parents=True,exist_ok=False)
    for branch in BRANCHES:
        rows=train if branch=='original_only' else train+aux
        xx=x[:len(rows)];w=sample_weights(rows,branch=='with_auxiliary')
        y=np.array([r['label']=='Psoriasis' for r in rows],dtype=int)
        scaler=StandardScaler().fit(xx,sample_weight=w)
        with warnings.catch_warnings():
            warnings.simplefilter('error',ConvergenceWarning)
            head=LogisticRegression(C=.001,solver='lbfgs',max_iter=3000,tol=1e-7,random_state=42).fit(scaler.transform(xx),y,sample_weight=w)
        assert head.classes_.tolist()==[0,1]
        target=MODELS/(branch+'.npz')
        np.savez_compressed(target,mean=scaler.mean_,scale=scaler.scale_,coefficients=head.coef_,intercept=head.intercept_,classes=head.classes_)
        assert np.allclose(probability(target,xx),head.predict_proba(scaler.transform(xx))[:,1],atol=1e-12)
        training[branch]=dict(images=len(rows),iterations=head.n_iter_.tolist(),positive_images=int(y.sum()),
            negative_mass=float(w[y==0].sum()/w.sum()),positive_mass=float(w[y==1].sum()/w.sum()),sha256=fusion.sha(target))
    fusion.write(OUT/'training_report.json',training)
    inner=p['roles']['inner_validation'];xx,raw=cache(extractor,inner,'inner')
    paths,y,ref,expected=fusion.validation_arrays(0)
    assert paths==[r['path'] for r in inner]
    error=float(np.abs(raw-expected).max());assert error<2e-6
    lock=fusion.read(prior.CURRENT/'fold_0/selection_locked.json')
    protected=lock['trials'][lock['selected']]['spec']['protected']
    current=fusion.decide(ref,expected,protected)
    ii=fusion.read(replay.MODELS/'psoriasis_aux/inner_predictions.json')
    assert ii['paths']==paths
    proposal=(.75*ref+.25*np.array(ii['probabilities'])).argmax(1)
    q={b:probability(MODELS/(b+'.npz'),xx) for b in BRANCHES}
    decisions=dict(current_fusion=current,**{b:route(current,proposal,q[b]) for b in BRANCHES})
    scores={name:fusion.metrics(pred,y) for name,pred in decisions.items()}
    selected,trials=choose(scores)
    fusion.write(OUT/'selection_locked.json',dict(selected=selected,trials=trials,protected=protected,
        protocol_sha256=fusion.sha(OUT/'protocol.json'),heads=training,parent_max_abs_difference=error))
    np.savez_compressed(OUT/'inner_decisions.npz',paths=paths,truth=y,current=current,proposal=proposal,**q)
    print(json.dumps(dict(selection_locked=selected,validation={n:dict(accuracy=s['accuracy'],macro_f1=s['macro_f1']) for n,s in scores.items()})),flush=True)
    # No outer feature/proposal arrays read until selection has been written.
    previous=fusion.read(replay.OUT/'outer_decisions.json')
    lookup={r['path']:r for r in p['roles']['outer_holdout']}
    rows=[lookup[r['path']] for r in previous]
    xx,raw=cache(extractor,rows,'outer')
    ref=np.array([r['raw_component_probabilities']['old_classwise'] for r in previous])
    expected=np.array([r['raw_component_probabilities']['original_resnet50'] for r in previous])
    assert np.abs(raw-expected).max()<2e-6
    current=fusion.decide(ref,expected,protected)
    assert current.tolist()==[r['predictions']['current_fusion'] for r in previous]
    proposal=(.75*ref+.25*np.array([r['raw_component_probabilities']['psoriasis_aux'] for r in previous])).argmax(1)
    y=np.array([fusion.CLASSES.index(r['label']) for r in rows])
    q={b:probability(MODELS/(b+'.npz'),xx) for b in BRANCHES}
    decisions=dict(current_fusion=current,**{b:route(current,proposal,q[b]) for b in BRANCHES})
    decisions['validation_selected']=decisions[selected]
    np.savez_compressed(OUT/'outer_decisions.npz',paths=[r['path'] for r in rows],truth=y,current=current,proposal=proposal,**q)
    methods={n:fusion.metrics(pred,y) for n,pred in decisions.items()}
    changes={b:dict(proposed=int((np.isin(current,[2,6])&(proposal==4)).sum()),accepted=int((decisions[b]!=current).sum()),
        corrected=int(((decisions[b]!=current)&(y==4)).sum()),new_errors=int(((decisions[b]!=current)&(current==y)).sum())) for b in BRANCHES}
    result=dict(status='complete_exploratory_onefold_verifier',classes=fusion.CLASSES,images=len(rows),selected=selected,
        validation=scores,methods=methods,outer_changes=changes,global_5937_score_changed=False,serving_changed=False,
        protocol_sha256=fusion.sha(OUT/'protocol.json'),selection_sha256=fusion.sha(OUT/'selection_locked.json'),limitations=p['limitations'])
    check(p)
    fusion.write(OUT/'results.json',result)
    fusion.write(OUT/'verification.json',dict(status='PASS',scope='Technical consistency, not clinical validation',results_sha256=fusion.sha(OUT/'results.json')))
    print(json.dumps(dict(complete=True,selected=selected,outer_changes=changes,outer={n:dict(accuracy=s['accuracy'],macro_f1=s['macro_f1']) for n,s in methods.items()})),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    p=fusion.read(OUT/'protocol.json') if (OUT/'protocol.json').exists() else prepare()
    check(p)
    if not args.prepare_only:run(p)


if __name__=='__main__':main()
