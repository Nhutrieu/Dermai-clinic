"""One fixed train-only grouped hard-mining pass for the frozen specialist."""
from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

import run_teacher_balanced_specialist as balanced

previous = balanced.previous
base = previous.base
ROOT = previous.ROOT
NAME = 'teacher_hard_mining_specialist_seed42_20261022'
OUT = ROOT/'ai-service/reports'/NAME
MODELS = ROOT/'ai-service/candidates'/NAME
CONFIG = dict(C=.001,solver='lbfgs',multi_class='multinomial',max_iter=3000,tol=1e-7,random_state=42)
CONTROL = 'unweighted_control'
MINED = 'hard_mined_specialist'


def assignments(target, groups):
    target,groups = np.asarray(target),np.asarray(groups)
    result = np.full(len(target),-1,dtype=int)
    split = StratifiedGroupKFold(n_splits=3,shuffle=True,random_state=42)
    for part,(train,held) in enumerate(split.split(np.zeros((len(target),1)),target,groups)):
        if set(target[train]) != set(range(5)) or not set(groups[train]).isdisjoint(groups[held]):
            raise ValueError('Invalid mining class/group split')
        assert (result[held]==-1).all()
        result[held] = part
    assert (result>=0).all()
    return result


def weights(target, loss, paths):
    target,loss = np.asarray(target),np.asarray(loss)
    if (target.ndim!=1 or target.shape!=loss.shape or len(paths)!=len(target)
        or set(target.tolist())!=set(range(5)) or not np.isfinite(loss).all()):
        raise ValueError('Invalid train-only mining inputs')
    hard = np.zeros(len(target),dtype=bool)
    sample_weight = np.ones(len(target))
    for label in range(5):
        indices = np.flatnonzero(target==label)
        order = sorted(indices,key=lambda i:(-float(loss[i]),paths[i]))
        hard[order[:int(np.ceil(.25*len(indices)))]] = True
        values = np.where(hard[indices],2.,1.)
        sample_weight[indices] = values*len(indices)/values.sum()
        assert np.isclose(sample_weight[indices].sum(),len(indices))
    assert np.isclose(sample_weight.sum(),len(target))
    return sample_weight,hard


def fit(x,y,sample_weight=None):
    with warnings.catch_warnings():
        warnings.simplefilter('error',ConvergenceWarning)
        return LogisticRegression(**CONFIG).fit(x,y,sample_weight=sample_weight)


def mining_scores(x,target,parts):
    probability = np.zeros((len(target),5))
    traces = []
    for part in range(3):
        train,held = np.flatnonzero(parts!=part),np.flatnonzero(parts==part)
        assert len(train) and len(held) and set(target[train])==set(range(5))
        scaler = StandardScaler().fit(x[train])
        model = fit(scaler.transform(x[train]),target[train])
        assert model.classes_.tolist()==list(range(5))
        probability[held] = model.predict_proba(scaler.transform(x[held]))
        traces.append(dict(part=part,subtrain=len(train),held=len(held),iterations=model.n_iter_.tolist()))
    assert np.isfinite(probability).all() and np.allclose(probability.sum(1),1)
    return probability,traces


def select(decisions,truth):
    result = previous.choose(decisions,truth)
    trials = result['trials']
    a,b = trials[MINED]['metrics'],trials[CONTROL]['metrics']
    if a['macro_f1']+1e-12 < b['macro_f1']:
        trials[MINED]['guard_failures'].append('macro_f1_below_unweighted_control')
    mean = lambda s:np.mean([s['per_class'][base.CLASSES[i]]['f1'] for i in previous.FOCUS])
    if mean(a)+1e-12 < mean(b):
        trials[MINED]['guard_failures'].append('focus_mean_f1_below_unweighted_control')
    passing = [n for n,t in trials.items() if not t['guard_failures']]
    result['selected'] = max(passing,key=lambda n:(trials[n]['metrics']['macro_f1'],
        np.mean([trials[n]['metrics']['per_class'][base.CLASSES[i]]['recall'] for i in previous.FOCUS]),
        trials[n]['metrics']['accuracy'],n=='current_fusion',n==CONTROL))
    return result


def verify(p):
    for path,h in p['frozen_sha256'].items():
        assert base.sha(ROOT/path)==h,path


def prepare():
    if (OUT/'protocol.json').exists():
        p = base.read(OUT/'protocol.json');verify(p);return p
    prior = base.read(balanced.OUT/'protocol.json')
    balanced.verify(prior)
    assert base.read(balanced.OUT/'independent_review.json')['status']=='PASS'
    assert base.read(ROOT/'ai-service/reports/active_research_track.json')['next_experiment'] is None
    parent = base.read(ROOT/prior['parent_protocol'])
    frozen = dict(prior['frozen_sha256'])
    for path in [Path(__file__),ROOT/'ai-service/training/run_teacher_balanced_specialist.py',
                 balanced.OUT/'protocol.json',balanced.OUT/'results.json',balanced.OUT/'independent_review.json']:
        frozen[path.relative_to(ROOT).as_posix()] = base.sha(path)
    parts = {}
    for f in range(5):
        paths = parent['folds'][f]['roles']['train']
        labels = [base.CLASSES.index(parent['manifest'][p]['class']) for p in paths]
        target = np.array([previous.SPECIAL.index(i) if i in previous.SPECIAL else 4 for i in labels])
        groups = np.array([parent['manifest'][p]['scene_or_case_group'] for p in paths])
        parts[str(f)] = assignments(target,groups).tolist()
    for path,row in parent['manifest'].items():
        assert base.sha(ROOT/path)==row['sha256'],path
    p = dict(name=NAME,date='2026-10-22',parent_protocol=prior['parent_protocol'],
        classes=base.CLASSES,images=5937,folds=5,frozen_sha256=frozen,mining_parts=parts,config=CONFIG,
        changed_factor='Only per-image loss weights from fixed train-only grouped head cross-predictions; no class balancing, new backbone, data or threshold.',
        mining='Three StratifiedGroupKFold splits inside each outer-training role only, seed42. Each temporary scaler/head fits only subtrain; predict held training group. NLL of recorded five-way target, clipped probability>=1e-12. Select top ceil(25%*n_k) losses within each target; lexical path tie-break. Raw hard/easy weights2/1 then normalize within target to total n_k. Exactly one reweighting pass.',
        targets=['Lupus','Psoriasis','Tinea','Eczema','Other'],
        scaler='Final heads reuse the original B train-only scaler exactly; temporary mining heads fit independent scalers on their subtrain only.',
        control='Refit unweighted full-train head, require coefficients match B. Mined head same features/scaler/C/solver, only sample_weight changes.',
        routing='Original B threshold .8 and four-label routing; Other abstains; full SkinCancer mask unchanged.',
        selection='Original B validation guards/ranking plus mined MacroF1 and mean focus F1 >= unweighted control. Lock all5 selections before outer evaluation; baseline wins ties. No sweep or A+B combination.',
        reporting='Raw control/raw mined/validation-selected; each class, fold and source; 1000 paired group bootstrap versus current baseline. No automatic adoption.',
        limitations=parent['limitations']+[
            'Train-group cross-predictions cross-fit only temporary linear heads/scalers. The frozen CNN already learned all outer-training images; this is not full CNN OOF mining.',
            'High held-head loss may reflect ambiguity/noisy labels, not useful hard examples. No labels automatically changed.',
            'One offline reweighting pass on frozen features, not original minibatch OHEM detector training.'],
        references=['https://arxiv.org/abs/1604.03540','https://scikit-learn.org/1.3/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html'],
        serving_changed=False)
    base.write(OUT/'protocol.json',p)
    base.write(OUT/'status.json',dict(state='registered',new_backbones=0))
    return p


def train_and_select(p,parent):
    for f in range(5):
        folder,model_path = OUT/f'fold_{f}',MODELS/f'fold_{f}/hard_mined_specialist.npz'
        if (folder/'selection_locked.json').exists():
            assert base.sha(model_path)==base.read(folder/'selection_locked.json')['mined_head_sha256']
            continue
        paths,x,_ = balanced.cached(f,'train',parent)
        assert paths==parent['folds'][f]['roles']['train']
        labels = [base.CLASSES.index(parent['manifest'][p]['class']) for p in paths]
        target = np.array([previous.SPECIAL.index(i) if i in previous.SPECIAL else 4 for i in labels])
        parts = np.array(p['mining_parts'][str(f)])
        probability,traces = mining_scores(x,target,parts)
        loss = -np.log(np.maximum(probability[np.arange(len(target)),target],1e-12))
        sample_weight,hard = weights(target,loss,paths)
        folder.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(folder/'mining_scores.npz',paths=paths,targets=target,parts=parts,
                            probabilities=probability,loss=loss,hard=hard,sample_weight=sample_weight)
        base.write(folder/'mining_trace.json',traces)
        control_path = previous.MODELS/f'fold_{f}/specialist.npz'
        with np.load(control_path,allow_pickle=False) as a:
            mean,scale = a['mean'].copy(),a['scale'].copy()
            z=x.copy();z-=mean;z/=scale
            control,mined = fit(z,target),fit(z,target,sample_weight)
            delta = max(float(np.abs(control.coef_-a['coef']).max()),float(np.abs(control.intercept_-a['intercept']).max()))
            assert delta<1e-10
        if model_path.exists():
            assert np.allclose(previous.head_probability(model_path,x),mined.predict_proba(z),atol=1e-12)
        else:
            model_path.parent.mkdir(parents=True,exist_ok=True)
            np.savez_compressed(model_path,mean=mean,scale=scale,coef=mined.coef_,intercept=mined.intercept_,classes=mined.classes_)
        assert np.allclose(previous.head_probability(model_path,x),mined.predict_proba(z),atol=1e-12)
        base.write(folder/'training_report.json',dict(images=len(paths),target_counts=np.bincount(target).tolist(),
            hard_counts=np.bincount(target[hard],minlength=5).tolist(),
            loss_weight_totals=np.bincount(target,weights=sample_weight,minlength=5).tolist(),
            control_max_coefficient_difference=delta,mined_iterations=mined.n_iter_.tolist(),
            unweighted_train_correct=int((control.predict(z)==target).sum()),mined_train_correct=int((mined.predict(z)==target).sum()),
            control_sha256=base.sha(control_path),mined_sha256=base.sha(model_path)))
        paths,xx,raw = balanced.cached(f,'inner_validation',parent)
        expected_paths,truth,_,expected,current = previous.validation(parent,f)
        assert paths==expected_paths and np.abs(raw-expected).max()<2e-6
        cq,mq = previous.head_probability(control_path,xx),previous.head_probability(model_path,xx)
        decisions=dict(current_fusion=current,unweighted_control=previous.route(current,cq),hard_mined_specialist=previous.route(current,mq))
        chosen=select(decisions,truth)
        chosen.update(control_head_sha256=base.sha(control_path),mined_head_sha256=base.sha(model_path))
        base.write(folder/'selection_locked.json',chosen)
        np.savez_compressed(folder/'inner_probabilities.npz',paths=paths,truth=truth,current=current,
                            unweighted_probability=cq,mined_probability=mq)
        print(base.json.dumps(dict(fold=f,selected=chosen['selected'],failures=chosen['trials'][MINED]['guard_failures'])),flush=True)
    locks={str(f):base.sha(OUT/f'fold_{f}/selection_locked.json') for f in range(5)}
    base.write(OUT/'all_selections_locked.json',dict(protocol_sha256=base.sha(OUT/'protocol.json'),
               selections_sha256=locks,outer_evaluation_started=False))
    return locks


def evaluate(p,parent,locks):
    rows=[]
    for f in range(5):
        outer,_,expected,current=previous.outer_rows(parent,f)
        paths,x,raw=balanced.cached(f,'outer_holdout',parent)
        assert paths==[r['path'] for r in outer] and np.abs(raw-expected).max()<2e-6
        cq=previous.head_probability(previous.MODELS/f'fold_{f}/specialist.npz',x)
        mq=previous.head_probability(MODELS/f'fold_{f}/hard_mined_specialist.npz',x)
        decisions=dict(current_fusion=current,unweighted_control=previous.route(current,cq),hard_mined_specialist=previous.route(current,mq))
        selected=base.read(OUT/f'fold_{f}/selection_locked.json')['selected']
        decisions['validation_selected']=decisions[selected]
        rows+=previous.records(outer,f,decisions)
        np.savez_compressed(OUT/f'fold_{f}/outer_probabilities.npz',paths=paths,unweighted_probability=cq,mined_probability=mq)
    rows.sort(key=lambda r:r['path'])
    assert len(rows)==len({r['path'] for r in rows})==5937
    old={r['path']:r for r in base.read(previous.OUT/'B_specialist/oof_decisions.json')}
    for r in rows:
        assert r['predictions']['current_fusion']==old[r['path']]['predictions']['current_fusion']
        assert r['predictions'][CONTROL]==old[r['path']]['predictions']['specialist']
    y=np.array([base.CLASSES.index(r['label']) for r in rows])
    current=np.array([r['predictions']['current_fusion'] for r in rows])
    methods={}
    for name in rows[0]['predictions']:
        pred=np.array([r['predictions'][name] for r in rows])
        assert np.array_equal(pred==base.CANCER,current==base.CANCER)
        score=base.metrics(pred,y)
        score.update(correct=int((pred==y).sum()),changed=int((pred!=current).sum()),paired_delta_95pct=previous.paired_intervals(rows,pred,current,y))
        score['per_source']={}
        for source in ['original_train','SCIN']:
            mask=np.array([r['source']==source for r in rows])
            score['per_source'][source]=dict(images=int(mask.sum()),**base.metrics(pred[mask],y[mask]))
        methods[name]=score
    folds=[]
    for f in range(5):
        mask=np.array([r['fold']==f for r in rows])
        folds.append(dict(fold=f,selected=base.read(OUT/f'fold_{f}/selection_locked.json')['selected'],
            methods={n:base.metrics(np.array([r['predictions'][n] for r in rows])[mask],y[mask]) for n in methods}))
    base.write(OUT/'oof_decisions.json',rows)
    base.write(OUT/'results.json',dict(status='complete_exploratory_train_only_mining_five_fold',classes=base.CLASSES,
        images=5937,methods=methods,per_fold=folds,protocol_sha256=base.sha(OUT/'protocol.json'),limitations=p['limitations'],serving_changed=False))
    verify(p)
    assert locks=={str(f):base.sha(OUT/f'fold_{f}/selection_locked.json') for f in range(5)}
    base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),
        control_reproduced=True,cancer_mask_unchanged=True,scope='Technical consistency, not clinical validation'))
    print(base.json.dumps({n:{k:s[k] for k in ['accuracy','macro_f1','correct']} for n,s in methods.items()}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    with threadpool_limits(limits=2):
        p=prepare()
        if args.prepare_only:
            print(base.json.dumps(dict(registered=NAME,mining_group_splits=3,outer_folds=5)),flush=True);return
        assert not (OUT/'results.json').exists(),'Preserve completed experiment'
        parent=base.read(ROOT/p['parent_protocol'])
        base.write(OUT/'status.json',dict(state='training_train_only_hard_mining',serving_changed=False))
        locks=train_and_select(p,parent)
        evaluate(p,parent,locks)
        base.write(OUT/'status.json',dict(state='complete',serving_changed=False))


if __name__=='__main__':
    main()
