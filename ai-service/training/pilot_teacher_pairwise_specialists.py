"""Train-only confusion pairs: conditional eight-way versus binary specialists.

Frozen ResNet features, fixed threshold and exact SkinCancer preservation.
This is one exploratory fold, not a replacement for five-fold evaluation.
"""
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

import pilot_teacher_class_expert_bank as previous

features, latest, base, prior = previous.features, previous.latest, previous.base, previous.prior
ROOT = previous.ROOT
NAME = 'teacher_pairwise_specialists_fold0_seed42_20261024'
OUT = ROOT / 'ai-service/reports' / NAME
MODELS = ROOT / 'ai-service/candidates' / NAME
CONFIG = features.CONFIG
METHODS = ['current_policy', 'conditional_control', 'binary_pairs']


def cached(role, rows):
    path = (features.SOURCE / 'fold_0_resnet_features.npz' if role == 'source_transfer'
            else prior.OUT / f'B_specialist/fold_0/{role}_features.npz')
    with np.load(path, allow_pickle=False) as z:
        lookup = {x:i for i,x in enumerate(z['paths'].tolist())}
        assert len(lookup) == len(z['paths'])
        xx = z['features'][[lookup[r['path']] for r in rows]].copy()
    assert xx.shape == (len(rows), 2048) and np.isfinite(xx).all()
    return xx


def select_pairs(truth, prediction):
    """One rival per weak label, using grouped train-head held decisions only."""
    cm = np.bincount(np.asarray(truth)*8+np.asarray(prediction), minlength=64).reshape(8, 8)
    support = cm.sum(1)
    if np.any(support == 0):
        raise ValueError('All eight training classes are required')
    selected = set(); details = {}
    for target in prior.FOCUS:
        rivals = [j for j in range(8) if j not in [target, base.CANCER]]
        counts = {j:int(cm[target,j]+cm[j,target]) for j in rivals}
        rates = {j:float(.5*(cm[target,j]/support[target]+cm[j,target]/support[j])) for j in rivals}
        rival = max(rivals, key=lambda j:(rates[j], counts[j], -j))
        # No arbitrary pair when discovery contains no confusion for this disease.
        if counts[rival] > 0:
            selected.add(tuple(sorted([target, rival])))
        details[base.CLASSES[target]] = dict(rival=base.CLASSES[rival],
            confusion_count=counts[rival], balanced_symmetric_rate=rates[rival],
            used=bool(counts[rival]), candidates={base.CLASSES[j]:dict(count=counts[j],rate=rates[j]) for j in rivals})
    return dict(pairs=[list(p) for p in sorted(selected)], details=details, confusion_matrix=cm.tolist())


def pair_route(current, probabilities, pairs):
    current = np.asarray(current); q = np.asarray(probabilities)
    if (current.ndim != 1 or q.shape != (len(current), len(pairs), 2)
            or not np.isfinite(q).all() or (q < 0).any() or not np.allclose(q.sum(2), 1, atol=1e-8)
            or any(len(pair)!=2 or pair[0]>=pair[1] or min(pair)<0 or max(pair)>7 or base.CANCER in pair for pair in pairs)
            or len({tuple(p) for p in pairs}) != len(pairs)):
        raise ValueError('Aligned pair probabilities and unique non-cancer pairs required')
    result = current.copy()
    for i,label in enumerate(current):
        proposals = set()
        for j,pair in enumerate(pairs):
            if label in pair:
                target = pair[int(q[i,j].argmax())]
                if target != label and q[i,j].max() >= .8:
                    proposals.add(target)
        # Multiple contradictory destinations abstain; decisions never chain.
        if len(proposals) == 1:
            result[i] = next(iter(proposals))
    assert np.array_equal(result == base.CANCER, current == base.CANCER)
    return result


def conditional(logits, pairs):
    # Stable within-pair normalization avoids underflow from full softmax.
    result = []
    for a,b in pairs:
        p = expit(logits[:,b]-logits[:,a]); result.append(np.column_stack([1-p,p]))
    return np.stack(result, axis=1) if result else np.empty((len(logits),0,2))


def choose(decisions, truth):
    scores = {n:base.metrics(d,truth) for n,d in decisions.items()}
    trials = {n:dict(metrics=s,guard_failures=prior.failures(s,scores['current_policy'])) for n,s in scores.items()}
    treatment = scores['binary_pairs']
    if treatment['macro_f1']+1e-12 < scores['conditional_control']['macro_f1']:
        trials['binary_pairs']['guard_failures'].append('macro_f1_below_conditional_control')
    for n in ['current_policy','conditional_control']:
        if latest.previous.mean_focus(treatment) <= latest.previous.mean_focus(scores[n])+1e-12:
            trials['binary_pairs']['guard_failures'].append('no_weak_mean_f1_gain_vs_'+n)
    passing = [n for n in METHODS if not trials[n]['guard_failures']]
    chosen = max(passing,key=lambda n:(scores[n]['macro_f1'],latest.previous.mean_focus(scores[n],'recall'),
                    scores[n]['accuracy'],n=='current_policy',n=='conditional_control'))
    return dict(selected=chosen,trials=trials)


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');prior.verify(p);return p
    registry=base.read(ROOT/'ai-service/reports/active_research_track.json')
    assert registry['next_experiment'] is None
    parent=base.read(previous.OUT/'protocol.json');prior.verify(parent)
    assert base.read(previous.OUT/'completion.json')['status']=='complete_verified_pilot_not_selected'
    files=[Path(__file__),ROOT/'ai-service/tests/test_teacher_pairwise_specialists.py',
           previous.OUT/'protocol.json',previous.OUT/'completion.json',previous.OUT/'independent_review.json',
           ROOT/'ai-service/training/pilot_teacher_class_expert_bank.py',
           ROOT/'ai-service/training/pilot_teacher_multifeature_specialist.py']
    p=dict(name=NAME,registered_utc=features.utc(),fold=0,classes=base.CLASSES,
        parent_protocol=parent['parent_protocol'],configuration=CONFIG,
        frozen_sha256={**parent['frozen_sha256'],**{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},
        representation='Only original frozen fold0 ResNet2048 cached features; original4043train,718inner,1176outer and1709known-source rows.',
        pair_discovery='StratifiedGroupKFold3 shuffle seed42 within original train. Each temporary eight-way logistic fits its own fit-part StandardScaler; fit rows have uniform weight4043/n_fit. Stitch train-head held decisions, compute symmetric balanced confusion .5*(CM[a,b]/support[a]+CM[b,a]/support[b]). For each Lupus/Psoriasis/Tinea select one highest non-cancer rival, then total pair confusion count, then lowest label index. Skip zero-confusion targets; deduplicate sorted pairs. Lock pairs before reading inner labels/predictions.',
        comparison='One final eight-way multinomial logistic on all4043train versus one binary logistic per discovered pair on pair train rows only. Final scaler fits all4043train and is shared, C=.001 same, binary uniform sample weight4043/n_pair so total loss-weight mass equals eight-way control. No class balancing, auxiliary images or new backbone. Binary targets keep original label indices.',
        control='Use sigmoid(logit_b-logit_a) from eight-way head for each pair. Both arms have the same binary score arity, pair endpoints, >=.8 threshold and conflict policy. The conditional control discards outside-pair evidence; scores are not calibrated clinical confidence.',
        routing='Only current predictions belonging to a discovered pair may change to its other endpoint with confidence>=.8. Gather switch proposals from all applicable pairs against original current prediction. Exactly one unique destination switches; conflicting destinations abstain, keep votes do not veto. No chaining. Cancer is excluded from every pair and its exact prediction mask is fixed.',
        selection='Fixed current/conditional-control/binary-pairs comparison on inner labels, strict existing per-weak Recall/F1,totalAccuracy/MacroF1,weakPrecision and otherRecall guards. Binary additionally MF>=control and meanweakF1 strictly above both control/current. Rank MF,meanweakRecall,Accuracy,ties current then control. Lock heads and choice before new outer/source inference. No C/pair/threshold grid using inner or outer.',
        scope='Onefold exploratory pilot, not a new5937 score. If selected, full-fivefold confirmation needs a separately frozen protocol; no automatic claim of global improvement.',
        limitations=parent['limitations']+[
            'Train-head held folds share a CNN already trained on all original train rows. They only discover pairs; they are not independent end-to-end OOF performance.',
            'Pair heads have two targets and fewer parameters than the full eight-way head. Matching total sample-weight mass does not match feature covariance, class priors or every form of regularization.',
            'A two-way task may force confident wrong choices for images belonging to another disease. Endpoint routing, conflict abstention and validation guards can limit, not eliminate, this risk.',
            'All roles are historically inspected; one seed/fold and no new patient test. Preserving the Cancer mask preserves its prior errors.'],
        new_CNN_fits=0,new_backbones=0,global_5937_score_changed=False,serving_changed=False)
    OUT.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p)
    base.write(OUT/'research_registry_before.json',registry)
    registry['next_experiment']=OUT.relative_to(ROOT).as_posix();registry['next_experiment_status']='registered_train_discovered_pairwise_pilot'
    base.write(ROOT/'ai-service/reports/active_research_track.json',registry)
    return p


def fit(x,y,weight,scaler):
    with warnings.catch_warnings():
        warnings.simplefilter('error',ConvergenceWarning)
        model=LogisticRegression(**CONFIG).fit(scaler.transform(x),y,sample_weight=weight)
    saved=dict(mean=scaler.mean_,scale=scaler.scale_,coef=model.coef_,intercept=model.intercept_,classes=model.classes_,
               logit_multiplier=np.array(2. if len(model.classes_)==2 else 1.))
    # sklearn multinomial binary predict_proba is softmax(-s,+s), not sigmoid(s).
    check=logits(saved,x[:16])
    if len(model.classes_)==2:
        p=expit(check[:,0]);manual=np.column_stack([1-p,p])
    else:
        check-=check.max(1,keepdims=True);manual=np.exp(check);manual/=manual.sum(1,keepdims=True)
    assert np.max(np.abs(manual-model.predict_proba(scaler.transform(x[:16]))))<1e-12
    return saved,model.n_iter_.tolist()


def logits(model,x):
    return (features.standardize(x,model['mean'],model['scale'])@model['coef'].T+model['intercept'])*model['logit_multiplier']


def train_and_lock(p):
    parent=base.read(ROOT/p['parent_protocol']);rows=prior.role_rows(parent,0,'train')
    x=cached('train',rows);truth=np.array([base.CLASSES.index(r['label']) for r in rows]);groups=np.array([r['group'] for r in rows])
    MODELS.mkdir(parents=True,exist_ok=True)
    held=np.zeros((len(rows),8));coverage=np.zeros(len(rows),dtype=int);parts=[]
    for i,(fi,hi) in enumerate(StratifiedGroupKFold(3,shuffle=True,random_state=42).split(x,truth,groups)):
        assert set(groups[fi]).isdisjoint(groups[hi])
        model,it=fit(x[fi],truth[fi],np.full(len(fi),len(rows)/len(fi)),StandardScaler().fit(x[fi]))
        np.savez_compressed(MODELS/f'discovery_part_{i}.npz',**model)
        held[hi]=features.probability(model,features.standardize(x[hi],model['mean'],model['scale']))
        coverage[hi]+=1;parts.append(dict(fit_indices=fi.tolist(),hold_indices=hi.tolist(),iterations=it,uniform_weight=len(rows)/len(fi)))
    assert np.all(coverage==1)
    plan=select_pairs(truth,held.argmax(1));plan.update(parts=parts,images=len(rows))
    base.write(OUT/'pair_discovery.json',plan)
    np.savez_compressed(OUT/'train_head_held_predictions.npz',paths=[r['path'] for r in rows],truth=truth,groups=groups,probability=held)
    pair_lock=dict(pairs=plan['pairs'],locked_utc=features.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
        discovery_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in [OUT/'pair_discovery.json',OUT/'train_head_held_predictions.npz',*MODELS.glob('discovery_part_*.npz')]})
    base.write(OUT/'pairs_locked.json',pair_lock)
    scaler=StandardScaler().fit(x);training={}
    model,it=fit(x,truth,np.ones(len(rows)),scaler)
    np.savez_compressed(MODELS/'conditional_control.npz',**model)
    training['conditional_control']=dict(images=len(rows),uniform_weight=1.,iterations=it,classes=model['classes'].tolist())
    for a,b in plan['pairs']:
        mask=np.isin(truth,[a,b]);mass=len(rows)/int(mask.sum())
        binary,it=fit(x[mask],truth[mask],np.full(mask.sum(),mass),scaler)
        assert binary['classes'].tolist()==[a,b]
        np.savez_compressed(MODELS/f'pair_{a}_{b}.npz',**binary)
        training[f'pair_{a}_{b}']=dict(images=int(mask.sum()),uniform_weight=mass,iterations=it,
            classes=binary['classes'].tolist(),class_counts={base.CLASSES[c]:int((truth[mask]==c).sum()) for c in [a,b]})
    base.write(OUT/'training_report.json',dict(head_fits=len(training)+3,discovery_fits=3,final_heads=training,
        pairs_locked_before_inner=True,inner_started_utc=features.utc()))
    inner=prior.role_rows(parent,0,'inner_validation')
    with np.load(latest.OUT/'fold_0/inner_decisions.npz',allow_pickle=False) as z:
        assert z['paths'].tolist()==[r['path'] for r in inner]
        current=z[base.read(latest.OUT/'fold_0/selection_locked.json')['selected']].copy();yy=z['truth'].copy()
    probabilities=pair_probabilities(cached('inner_validation',inner),plan['pairs'])
    dd=dict(current_policy=current)
    dd.update({n:pair_route(current,q,plan['pairs']) for n,q in probabilities.items()})
    lock=choose(dd,yy)
    np.savez_compressed(OUT/'inner_decisions.npz',paths=[r['path'] for r in inner],truth=yy,
        control_probability=probabilities['conditional_control'],binary_probability=probabilities['binary_pairs'],**dd)
    lock.update(locked_utc=features.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),pairs_sha256=base.sha(OUT/'pairs_locked.json'),
        artifacts_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in [*MODELS.glob('*.npz'),OUT/'training_report.json',OUT/'inner_decisions.npz']})
    base.write(OUT/'selection_locked.json',lock)
    print(dict(pairs=[[base.CLASSES[a],base.CLASSES[b]] for a,b in plan['pairs']],selected=lock['selected'],failures={n:t['guard_failures'] for n,t in lock['trials'].items()}),flush=True)


def load_model(name):
    with np.load(MODELS/f'{name}.npz',allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}


def pair_probabilities(x,pairs):
    control=conditional(logits(load_model('conditional_control'),x),pairs)
    binary=[]
    for a,b in pairs:
        model=load_model(f'pair_{a}_{b}');positive=expit(logits(model,x)[:,0])
        binary.append(np.column_stack([1-positive,positive]))
    return dict(conditional_control=control,binary_pairs=np.stack(binary,axis=1) if binary else np.empty((len(x),0,2)))


def evaluate(p):
    assert not (OUT/'results.json').exists(),'Preserve completed pilot'
    lock=base.read(OUT/'selection_locked.json');pairs_lock=base.read(OUT/'pairs_locked.json')
    assert lock['protocol_sha256']==pairs_lock['protocol_sha256']==base.sha(OUT/'protocol.json')
    assert lock['pairs_sha256']==base.sha(OUT/'pairs_locked.json')
    for path,digest in {**lock['artifacts_sha256'],**pairs_lock['discovery_sha256']}.items():assert base.sha(ROOT/path)==digest,path
    started=features.utc();parent=base.read(ROOT/p['parent_protocol']);source=base.read(features.SOURCE/'protocol.json')
    outer={r['path']:r for r in base.read(latest.OUT/'oof_decisions.json')}
    external={r['path']:r for r in base.read(features.SOURCE/'source_decisions.json')}
    output=[];scores={}
    for role,rows in [('outer_holdout',prior.role_rows(parent,0,'outer_holdout')),('source_transfer',source['rows'])]:
        yy=np.array([base.CLASSES.index(r['label']) for r in rows])
        current=np.array([outer[r['path']]['predictions']['validation_selected'] if role=='outer_holdout' else external[r['path']]['predictions']['validation_selected'][0] for r in rows])
        probabilities=pair_probabilities(cached(role,rows),pairs_lock['pairs'])
        dd=dict(current_policy=current);dd.update({n:pair_route(current,q,pairs_lock['pairs']) for n,q in probabilities.items()})
        dd['validation_selected']=dd[lock['selected']]
        np.savez_compressed(OUT/f'{role}_probabilities.npz',paths=[r['path'] for r in rows],**probabilities)
        idx={r['path']:i for i,r in enumerate(rows)}
        slices={'original_outer':list(idx)} if role=='outer_holdout' else source['subsets']
        for name,paths in slices.items():
            ii=[idx[path] for path in paths]
            scores[name]=dict(images=len(ii),methods={n:base.metrics(pred[ii],yy[ii]) for n,pred in dd.items()})
        output.extend(dict(**r,role=role,predictions={n:int(pred[i]) for n,pred in dd.items()}) for i,r in enumerate(rows))
    base.write(OUT/'held_decisions.json',output)
    result=dict(status='complete_exploratory_pairwise_pilot',fold=0,selected=lock['selected'],pairs=pairs_lock['pairs'],
        validation=lock['trials'],held=scores,held_started_utc=started,completed_utc=features.utc(),
        head_fits=base.read(OUT/'training_report.json')['head_fits'],protocol_sha256=base.sha(OUT/'protocol.json'),
        selection_sha256=base.sha(OUT/'selection_locked.json'),new_CNN_fits=0,global_5937_score_changed=False,serving_changed=False,limitations=p['limitations'])
    base.write(OUT/'results.json',result);prior.verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),
        pairs_locked_before_inner=True,selection_locked_before_held=True))
    print(dict(outer={n:{k:s[k] for k in ['accuracy','macro_f1']} for n,s in scores['original_outer']['methods'].items()}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    with threadpool_limits(limits=1):
        p=prepare()
        if args.prepare_only:return
        assert not (OUT/'results.json').exists(),'Preserve completed pilot'
        if not (OUT/'selection_locked.json').exists():
            # A partially trained trial must be audited rather than silently refit.
            assert not (OUT/'pairs_locked.json').exists(),'Pair plan exists: inspect partial fit before resuming'
            train_and_lock(p)
        evaluate(p)


if __name__=='__main__':main()
