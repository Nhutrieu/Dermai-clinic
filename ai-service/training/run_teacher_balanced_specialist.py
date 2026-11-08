"""Matched class-weight-only follow-up to the frozen five-way specialist."""
from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

import run_teacher_priorities_ensemble_specialist as previous

base = previous.base
ROOT = previous.ROOT
NAME = 'teacher_balanced_specialist_seed42_20261022'
OUT = ROOT / 'ai-service/reports' / NAME
MODELS = ROOT / 'ai-service/candidates' / NAME
CONTROL = 'unweighted_control'
BALANCED = 'balanced_specialist'


def balanced_weights(target):
    target = np.asarray(target)
    if target.ndim != 1 or target.dtype.kind not in 'iu' or set(target.tolist()) != set(range(5)):
        raise ValueError('Expected all five integer training targets')
    counts = np.bincount(target, minlength=5)
    return len(target)/(5*counts)


def choose(decisions, truth):
    result = previous.choose(decisions, truth)
    trials = result['trials']
    candidate = trials[BALANCED]['metrics']
    control = trials[CONTROL]['metrics']
    if candidate['macro_f1']+1e-12 < control['macro_f1']:
        trials[BALANCED]['guard_failures'].append('macro_f1_below_unweighted_control')
    mean_f1 = lambda s: np.mean([s['per_class'][base.CLASSES[i]]['f1'] for i in previous.FOCUS])
    if mean_f1(candidate)+1e-12 < mean_f1(control):
        trials[BALANCED]['guard_failures'].append('focus_mean_f1_below_unweighted_control')
    passing = [n for n, trial in trials.items() if not trial['guard_failures']]
    result['selected'] = max(passing, key=lambda n: (trials[n]['metrics']['macro_f1'],
        np.mean([trials[n]['metrics']['per_class'][base.CLASSES[i]]['recall'] for i in previous.FOCUS]),
        trials[n]['metrics']['accuracy'], n == 'current_fusion', n == CONTROL))
    return result


def verify(p):
    for relative, expected in p['frozen_sha256'].items():
        assert base.sha(ROOT / relative) == expected, relative


def prepare():
    if (OUT/'protocol.json').exists():
        p = base.read(OUT/'protocol.json')
        verify(p)
        return p
    parent = base.read(previous.OUT/'protocol.json')
    previous.verify(parent)
    assert base.read(previous.OUT/'independent_review.json')['status'] == 'PASS'
    assert base.read(ROOT/'ai-service/reports/active_research_track.json')['next_experiment'] is None
    frozen = dict(parent['frozen_sha256'])
    sources = [Path(__file__), previous.OUT/'protocol.json', previous.OUT/'independent_review.json',
               previous.OUT/'B_specialist/results.json', previous.OUT/'B_specialist/oof_decisions.json',
               previous.OUT/'B_specialist/all_selections_locked.json']
    for f in range(5):
        folder = previous.OUT/f'B_specialist/fold_{f}'
        sources += [folder/name for name in ['train_features.npz','inner_validation_features.npz',
                                             'outer_holdout_features.npz','selection_locked.json']]
        sources.append(previous.MODELS/f'fold_{f}/specialist.npz')
    frozen.update({x.relative_to(ROOT).as_posix():base.sha(x) for x in sources})
    for path, row in parent['manifest'].items():
        assert base.sha(ROOT/path) == row['sha256'], path
    p = dict(name=NAME,date='2026-10-22',parent_protocol=(previous.OUT/'protocol.json').relative_to(ROOT).as_posix(),
        frozen_sha256=frozen,classes=base.CLASSES,folds=5,images=5937,
        change='Only class weights in the five-way multinomial logistic training loss; no new backbone, scaler, data, sampler, threshold or C.',
        targets=['Lupus','Psoriasis','Tinea','Eczema','Other'],
        formula='w_k=N/(5*n_k), only training counts. Sum of all sample weights=N; each target receives N/5 total weight.',
        config=dict(C=.001,solver='lbfgs',multi_class='multinomial',class_weight='balanced',
                    max_iter=3000,tol=1e-7,random_state=42,threshold=.8),
        control='Refit class_weight=None on identical train/scaler and compare coefficients with the saved B head; reuse that exact saved head for control inference.',
        scaling='Reuse original B unweighted train-only StandardScaler exactly; only loss weighting changes. No new scaler fit on validation/test.',
        routing='Reuse B: change only current Lupus/Psoriasis/Tinea/Eczema calls with score>=.8; Other abstains. Complete SkinCancer prediction mask is fixed.',
        selection='Reuse original B validation guards/ranking and fallback. Balanced must additionally have MacroF1 and mean focus F1 at least equal to the unweighted control. Lock all5 choices before outer arrays. No threshold/weight sweep.',
        reporting='Raw control/raw balanced/validation-selected against current baseline; each disease, fold and source, fixed 1000 paired group bootstrap. No automatic deployment or baseline replacement.',
        limitations=parent['limitations']+['Loss weights also change the head score distribution; fixed .8 routing threshold is intentional to isolate the whole class-weight-only intervention. No calibrated probability claim.'],
        references=['https://scikit-learn.org/1.3/modules/generated/sklearn.linear_model.LogisticRegression.html'],
        serving_changed=False)
    base.write(OUT/'protocol.json',p)
    base.write(OUT/'status.json',dict(state='registered',new_backbones=0))
    return p


def cached(fold, role, parent):
    with np.load(previous.OUT/f'B_specialist/fold_{fold}/{role}_features.npz',allow_pickle=False) as a:
        paths = a['paths'].tolist()
        assert a['protocol_sha256'].item() == base.sha(previous.OUT/'protocol.json')
        assert set(paths) == set(parent['folds'][fold]['roles'][role])
        return paths,a['features'].copy(),a['probabilities'].copy()


def fit_and_select(p,parent):
    for f in range(5):
        folder = OUT/f'fold_{f}'
        head_path = MODELS/f'fold_{f}/balanced_specialist.npz'
        if (folder/'selection_locked.json').exists():
            assert base.sha(head_path) == base.read(folder/'selection_locked.json')['balanced_head_sha256']
            continue
        paths,x,_ = cached(f,'train',parent)
        assert paths == parent['folds'][f]['roles']['train']
        labels = [base.CLASSES.index(parent['manifest'][path]['class']) for path in paths]
        target = np.array([previous.SPECIAL.index(i) if i in previous.SPECIAL else 4 for i in labels])
        class_weights = balanced_weights(target)
        control_path = previous.MODELS/f'fold_{f}/specialist.npz'
        with np.load(control_path,allow_pickle=False) as saved:
            mean,scale = saved['mean'].copy(),saved['scale'].copy()
            z = x.copy(); z -= mean; z /= scale
            config = {k:v for k,v in p['config'].items() if k not in ['class_weight','threshold']}
            with warnings.catch_warnings():
                warnings.simplefilter('error',ConvergenceWarning)
                control = LogisticRegression(**config).fit(z,target)
                balanced = LogisticRegression(**config,class_weight='balanced').fit(z,target)
            difference = max(float(np.abs(control.coef_-saved['coef']).max()),
                             float(np.abs(control.intercept_-saved['intercept']).max()))
            assert difference < 1e-10, difference
        if head_path.exists():
            assert np.allclose(previous.head_probability(head_path,x),balanced.predict_proba(z),atol=1e-12)
        else:
            head_path.parent.mkdir(parents=True,exist_ok=True)
            np.savez_compressed(head_path,mean=mean,scale=scale,coef=balanced.coef_,
                                intercept=balanced.intercept_,classes=balanced.classes_)
        assert np.allclose(previous.head_probability(head_path,x),balanced.predict_proba(z),atol=1e-12)
        base.write(folder/'training_report.json',dict(train_images=len(paths),target_counts=np.bincount(target).tolist(),
            class_weights=class_weights.tolist(),weighted_mass=(class_weights*np.bincount(target)).tolist(),
            control_max_abs_coefficient_difference=difference,control_iterations=control.n_iter_.tolist(),
            balanced_iterations=balanced.n_iter_.tolist(),scaler_changed=False,backbone_updated=False,
            control_sha256=base.sha(control_path),balanced_sha256=base.sha(head_path)))
        paths,xx,raw = cached(f,'inner_validation',parent)
        expected_paths,truth,_,expected,current = previous.validation(parent,f)
        assert paths == expected_paths and np.abs(raw-expected).max() < 2e-6
        q_control = previous.head_probability(control_path,xx)
        q_balanced = previous.head_probability(head_path,xx)
        decisions = dict(current_fusion=current,unweighted_control=previous.route(current,q_control),
                         balanced_specialist=previous.route(current,q_balanced))
        selection = choose(decisions,truth)
        selection.update(balanced_head_sha256=base.sha(head_path),control_head_sha256=base.sha(control_path))
        base.write(folder/'selection_locked.json',selection)
        np.savez_compressed(folder/'inner_decisions.npz',paths=paths,truth=truth,current=current,
                            unweighted_probability=q_control,balanced_probability=q_balanced)
        print(base.json.dumps(dict(fold=f,selected=selection['selected'],
              balanced_failures=selection['trials'][BALANCED]['guard_failures'])),flush=True)
    locks = {str(f):base.sha(OUT/f'fold_{f}/selection_locked.json') for f in range(5)}
    base.write(OUT/'all_selections_locked.json',dict(protocol_sha256=base.sha(OUT/'protocol.json'),
               selections_sha256=locks,outer_evaluation_started=False))
    return locks


def evaluate(p,parent,locks):
    rows = []
    for f in range(5):
        outer,_,expected,current = previous.outer_rows(parent,f)
        paths,xx,raw = cached(f,'outer_holdout',parent)
        assert paths == [r['path'] for r in outer] and np.abs(raw-expected).max() < 2e-6
        control = previous.head_probability(previous.MODELS/f'fold_{f}/specialist.npz',xx)
        balanced = previous.head_probability(MODELS/f'fold_{f}/balanced_specialist.npz',xx)
        decisions = dict(current_fusion=current,unweighted_control=previous.route(current,control),
                         balanced_specialist=previous.route(current,balanced))
        selected = base.read(OUT/f'fold_{f}/selection_locked.json')['selected']
        decisions['validation_selected'] = decisions[selected]
        rows += previous.records(outer,f,decisions)
        np.savez_compressed(OUT/f'fold_{f}/outer_probabilities.npz',paths=paths,
                            unweighted_probability=control,balanced_probability=balanced)
    rows.sort(key=lambda r:r['path'])
    old = {r['path']:r for r in base.read(previous.OUT/'B_specialist/oof_decisions.json')}
    assert len(rows) == len({r['path'] for r in rows}) == 5937
    for r in rows:
        assert r['predictions']['current_fusion'] == old[r['path']]['predictions']['current_fusion']
        assert r['predictions'][CONTROL] == old[r['path']]['predictions']['specialist']
    y = np.array([base.CLASSES.index(r['label']) for r in rows])
    current = np.array([r['predictions']['current_fusion'] for r in rows])
    methods = {}
    for name in rows[0]['predictions']:
        pred = np.array([r['predictions'][name] for r in rows])
        assert np.array_equal(pred==base.CANCER,current==base.CANCER)
        score = base.metrics(pred,y)
        score.update(correct=int((pred==y).sum()),changed=int((pred!=current).sum()),
                     paired_delta_95pct=previous.paired_intervals(rows,pred,current,y))
        score['per_source'] = {}
        for source in ['original_train','SCIN']:
            mask = np.array([r['source']==source for r in rows])
            score['per_source'][source] = dict(images=int(mask.sum()),**base.metrics(pred[mask],y[mask]))
        methods[name] = score
    per_fold = []
    for f in range(5):
        mask = np.array([r['fold']==f for r in rows])
        per_fold.append(dict(fold=f,selected=base.read(OUT/f'fold_{f}/selection_locked.json')['selected'],
            methods={n:base.metrics(np.array([r['predictions'][n] for r in rows])[mask],y[mask]) for n in methods}))
    base.write(OUT/'oof_decisions.json',rows)
    result = dict(status='complete_exploratory_class_weight_only_five_fold',images=5937,classes=base.CLASSES,
        methods=methods,per_fold=per_fold,protocol_sha256=base.sha(OUT/'protocol.json'),
        limitations=p['limitations'],serving_changed=False)
    base.write(OUT/'results.json',result)
    assert locks == {str(f):base.sha(OUT/f'fold_{f}/selection_locked.json') for f in range(5)}
    verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',scope='Technical consistency; not clinical validation',
        results_sha256=base.sha(OUT/'results.json'),matched_control_reproduced=True,cancer_mask_unchanged=True))
    print(base.json.dumps({n:{k:s[k] for k in ['accuracy','macro_f1','correct']} for n,s in methods.items()}),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only',action='store_true')
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        p = prepare()
        if args.prepare_only:
            print(base.json.dumps(dict(registered=NAME,changed_factor='class_weight_only')),flush=True)
            return
        assert not (OUT/'results.json').exists(),'Preserve completed experiment'
        parent = base.read(ROOT/p['parent_protocol'])
        base.write(OUT/'status.json',dict(state='training_class_balanced_heads',serving_changed=False))
        locks = fit_and_select(p,parent)
        evaluate(p,parent,locks)
        base.write(OUT/'status.json',dict(state='complete',serving_changed=False))


if __name__ == '__main__':
    main()
