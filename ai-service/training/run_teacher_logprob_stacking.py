"""Fixed three-parent log-probability stacking; exploratory grouped development.

Meta-learning uses only the relevant outer fold's inner validation predictions.
Never pool other folds' OOF predictions to train the target fold's combiner:
their CNN parents may have trained on the target fold's outer images.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import warnings

import numpy as np
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

import run_teacher_priorities_ensemble_specialist as previous

base = previous.base
ROOT = base.ROOT
NAME = 'teacher_logprob_stacking_seed42_20261023'
OUT = ROOT / 'ai-service/reports' / NAME
MODELS = ROOT / 'ai-service/candidates' / NAME
PARENTS = ['efficientnet_b0', 'convnext_tiny', 'resnet50']
C = .1
EPS = 1e-7


def now():
    return datetime.now(timezone.utc).isoformat()


def features(probabilities):
    if len(probabilities) != 3:
        raise ValueError('Exactly three original parent models required')
    arrays = [np.asarray(p, dtype=np.float64) for p in probabilities]
    n = len(arrays[0])
    for p in arrays:
        if (p.shape != (n, 8) or not np.isfinite(p).all() or (p < 0).any()
                or (p > 1).any() or not np.allclose(p.sum(1), 1, atol=1e-6)):
            raise ValueError('Expected aligned finite Nx8 parent probabilities')
    return np.concatenate([np.log(np.clip(p, EPS, 1)) for p in arrays], axis=1)


def assignments(truth, groups):
    parts = np.full(len(truth), -1, dtype=np.int64)
    splitter = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42)
    for part, (train, hold) in enumerate(splitter.split(np.zeros(len(truth)), truth, groups)):
        assert set(groups[train]).isdisjoint(groups[hold])
        assert np.unique(truth[train]).tolist() == list(range(8))
        parts[hold] = part
    assert (parts >= 0).all()
    return parts


def fit(x, truth):
    if np.unique(truth).tolist() != list(range(8)):
        raise ValueError('Meta-training requires all eight classes')
    scaler = StandardScaler().fit(x)
    with warnings.catch_warnings():
        warnings.simplefilter('error', ConvergenceWarning)
        head = LogisticRegression(C=C, penalty='l2', solver='lbfgs',
            multi_class='multinomial', class_weight=None, max_iter=3000,
            tol=1e-7, random_state=42).fit(scaler.transform(x), truth)
    return scaler, head


def predict(scaler, head, x):
    assert head.classes_.tolist() == list(range(8))
    return head.predict_proba(scaler.transform(x))


def crossfit(x, truth, parts):
    probability = np.full((len(truth), 8), np.nan)
    audit = []
    for part in range(3):
        train, hold = parts != part, parts == part
        scaler, head = fit(x[train], truth[train])
        probability[hold] = predict(scaler, head, x[hold])
        audit.append(dict(part=part, fit_images=int(train.sum()), held_images=int(hold.sum()),
                          iterations=head.n_iter_.tolist(), fit_class_counts=np.bincount(truth[train], minlength=8).tolist()))
    assert np.isfinite(probability).all()
    return probability, audit


def route(current, probability):
    current, probability = np.asarray(current), np.asarray(probability)
    if (probability.shape != (len(current), 8) or not np.isfinite(probability).all()
            or (probability < 0).any() or not np.allclose(probability.sum(1), 1, atol=1e-8)):
        raise ValueError('Expected Nx8 head probabilities')
    allowed = np.asarray([i for i in range(8) if i != base.CANCER])
    result = current.copy()
    mask = current != base.CANCER
    result[mask] = allowed[probability[mask][:, allowed].argmax(1)]
    assert np.array_equal(result == base.CANCER, current == base.CANCER)
    return result


def saved_probability(path, x):
    with np.load(path, allow_pickle=False) as h:
        assert h['classes'].tolist() == list(range(8))
        logits = ((x - h['mean']) / h['scale']) @ h['coef'].T + h['intercept']
    logits -= logits.max(1, keepdims=True)
    values = np.exp(logits)
    return values / values.sum(1, keepdims=True)


def prepare():
    path = OUT / 'protocol.json'
    if path.exists():
        p = base.read(path)
        previous.verify(p)
        return p
    parent_path = previous.OUT / 'protocol.json'
    parent = base.read(parent_path)
    previous.verify(parent)
    registry = base.read(ROOT / 'ai-service/reports/active_research_track.json')
    assert registry['active_track'] == 'original_eight' and registry['next_experiment'] is None
    sources = [Path(__file__), Path(previous.__file__), Path(base.__file__), parent_path,
               base.OUT / 'oof_decisions.json', base.SERVING]
    for f in range(5):
        sources += [base.fold_dir(f) / 'validation_predictions.npz',
                    base.fold_dir(f) / 'test_predictions.json']
    base.write(OUT / 'research_registry_before.json', registry)
    p = dict(name=NAME, registered_utc=now(), classes=base.CLASSES, sklearn=sklearn.__version__,
        parent_protocol=parent_path.relative_to(ROOT).as_posix(), images=5937,
        frozen_sha256={x.relative_to(ROOT).as_posix(): base.sha(x) for x in sources},
        method=dict(parents=PARENTS, features='Concatenate log(clip(p,1e-7,1)): 24 features, fixed order.',
            scaler='Unweighted StandardScaler fitted only on each meta-fit subset.',
            head='Unweighted eight-class multinomial logistic regression, L2.',
            C=C, solver='lbfgs', max_iter=3000, tol=1e-7, random_state=42,
            meta_fit_role='Only the target outer fold inner validation; no CNN training images and no cross-outer-fold pooling.',
            selection_predictions='Three StratifiedGroupKFold(shuffle=True,random_state=42) cross-fits inside inner validation. Each held group excluded from both scaler and meta-head fit.',
            final_head='Fit on entire inner validation after cross-fit selection. Never select by this in-sample score.',
            routing='Keep exact baseline SkinCancer mask; for all remaining images choose maximal head score among the seven non-cancer classes. No confidence threshold.',
            candidates=['current_fusion', 'logprob_stack'], hyperparameter_search=False),
        selection='Same previous strict guards: Accuracy/MacroF1 and each Lupus/Psoriasis/Tinea Recall/F1 cannot decline; focus precision loss<=.02; other recall loss<=.02; exact SkinCancer Recall/Precision. Rank MacroF1, mean focus Recall, Accuracy, baseline wins ties. All5 choices locked before outer evaluation.',
        reporting='Raw fixed stack AND cross-fit-validation-selected method; all classes, folds, sources, changed errors and paired 1000-group-bootstrap intervals.',
        limitations=['Exploratory development on repeatedly inspected data, not an untouched independent test.',
            'CNN checkpoints previously used the entire inner validation for epoch selection. Meta cross-fitting does not undo that exposure or produce fully nested CNN training.',
            'Baseline weights already selected on entire inner validation: baseline and meta cross-fit have different selection histories.',
            'Cross-fit heads train on two-thirds of inner validation; final head trains on all inner images. Selection is a proxy, not a guarantee.',
            'One parent training seed; scene/case groups are not verified patient IDs; SCIN Lupus only11 images.',
            'Fixed cancer mask also retains existing cancer false positives and false negatives.',
            'Head scores are not clinically calibrated confidence values. No API replacement.'],
        references=['https://scikit-learn.org/1.3/modules/generated/sklearn.ensemble.StackingClassifier.html',
            'https://scikit-learn.org/1.3/modules/generated/sklearn.linear_model.LogisticRegression.html',
            'https://scikit-learn.org/1.3/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html'],
        serving_changed=False)
    base.write(path, p)
    base.write(OUT / 'status.json', dict(state='registered', registered_utc=p['registered_utc']))
    return p


def fit_all(p):
    parent = base.read(ROOT / p['parent_protocol'])
    previous.verify(parent)
    for f in range(5):
        folder = OUT / f'fold_{f}'
        head_path = MODELS / f'fold_{f}/stack.npz'
        lock_path = folder / 'selection_locked.json'
        if lock_path.exists():
            lock = base.read(lock_path)
            for path, expected in lock['artifacts_sha256'].items():
                assert base.sha(ROOT / path) == expected
            assert lock['protocol_sha256'] == base.sha(OUT / 'protocol.json')
            continue
        paths, truth, _, _, current = previous.validation(parent, f)
        groups = np.asarray([parent['manifest'][path]['scene_or_case_group'] for path in paths])
        with np.load(base.fold_dir(f) / 'validation_predictions.npz', allow_pickle=False) as a:
            assert a['paths'].tolist() == paths
            assert np.array_equal(a['truth'], truth)
            x = features([a[key] for key in PARENTS])
        parts = assignments(truth, groups)
        held_probability, audit = crossfit(x, truth, parts)
        decision = route(current, held_probability)
        lock = previous.choose(dict(current_fusion=current, logprob_stack=decision), truth)
        # Selection is decided before the final full-inner fit, using held meta-predictions only.
        scaler, head = fit(x, truth)
        head_path.parent.mkdir(parents=True, exist_ok=True)
        assert not head_path.exists(), 'Do not overwrite an interrupted artifact; inspect first.'
        np.savez_compressed(head_path, mean=scaler.mean_, scale=scaler.scale_, coef=head.coef_,
                            intercept=head.intercept_, classes=head.classes_)
        assert np.allclose(saved_probability(head_path, x), predict(scaler, head, x), atol=1e-12)
        folder.mkdir(parents=True, exist_ok=True)
        prediction_path = folder / 'inner_crossfit.npz'
        np.savez_compressed(prediction_path, paths=paths, truth=truth, groups=groups, parts=parts,
            probability=held_probability, current=current, decision=decision,
            protocol_sha256=base.sha(OUT / 'protocol.json'))
        base.write(folder / 'training_report.json', dict(fold=f, inner_images=len(paths),
            inner_groups=len(set(groups)), target_counts=np.bincount(truth, minlength=8).tolist(),
            temporary_fits=audit, final_iterations=head.n_iter_.tolist(), final_fit_images=len(paths),
            CNN_updated=False, final_fit_not_used_for_selection=True))
        lock.update(locked_utc=now(), protocol_sha256=base.sha(OUT / 'protocol.json'),
            artifacts_sha256={x.relative_to(ROOT).as_posix(): base.sha(x) for x in
                [head_path, prediction_path, folder / 'training_report.json']})
        base.write(lock_path, lock)
        print(json.dumps(dict(fold=f, selected=lock['selected'],
            failures=lock['trials']['logprob_stack']['guard_failures'])), flush=True)
    locks = {str(f): base.sha(OUT / f'fold_{f}/selection_locked.json') for f in range(5)}
    path = OUT / 'all_selections_locked.json'
    if path.exists():
        assert base.read(path)['selections_sha256'] == locks
    else:
        base.write(path, dict(locked_utc=now(), selections_sha256=locks,
            protocol_sha256=base.sha(OUT / 'protocol.json'), outer_evaluation_started=False))
    previous.verify(p)
    base.write(OUT / 'status.json', dict(state='all_five_choices_locked', utc=now()))


def evaluate(p):
    if (OUT / 'results.json').exists():
        previous.verify(p)
        assert base.sha(OUT / 'results.json') == base.read(OUT / 'verification.json')['results_sha256']
        return base.read(OUT / 'results.json')
    locks = base.read(OUT / 'all_selections_locked.json')
    assert locks['selections_sha256'] == {str(f): base.sha(OUT / f'fold_{f}/selection_locked.json') for f in range(5)}
    assert locks['protocol_sha256'] == base.sha(OUT / 'protocol.json')
    parent = base.read(ROOT / p['parent_protocol'])
    rows = []
    started = now()
    for f in range(5):
        original, _, _, current = previous.outer_rows(parent, f)
        lock = base.read(OUT / f'fold_{f}/selection_locked.json')
        for path, expected in lock['artifacts_sha256'].items():
            assert base.sha(ROOT / path) == expected
        x = features([np.asarray([r['probabilities'][key] for r in original]) for key in PARENTS])
        probability = saved_probability(MODELS / f'fold_{f}/stack.npz', x)
        decisions = dict(current_fusion=current, logprob_stack=route(current, probability))
        decisions['validation_selected'] = decisions[lock['selected']]
        rows += previous.records(original, f, decisions)
    rows.sort(key=lambda r:r['path'])
    assert len(rows) == len({r['path'] for r in rows}) == 5937
    truth = np.asarray([base.CLASSES.index(r['label']) for r in rows])
    current = np.asarray([r['predictions']['current_fusion'] for r in rows])
    frozen = {r['path']:r['predictions'][base.SELECTED] for r in base.read(base.OUT / 'oof_decisions.json')}
    assert current.tolist() == [frozen[r['path']] for r in rows]
    methods = {}
    with threadpool_limits(limits=1):
        for name in rows[0]['predictions']:
            pred = np.asarray([r['predictions'][name] for r in rows])
            assert np.array_equal(pred == base.CANCER, current == base.CANCER)
            score = base.metrics(pred, truth)
            score.update(correct=int((pred == truth).sum()), changed=int((pred != current).sum()),
                corrected=int(((current != truth) & (pred == truth)).sum()),
                broken=int(((current == truth) & (pred != truth)).sum()),
                paired_delta_95pct=previous.paired_intervals(rows, pred, current, truth))
            score['per_source'] = {source: dict(images=int((mask := np.asarray([r['source'] == source for r in rows])).sum()),
                **base.metrics(pred[mask], truth[mask])) for source in ['original_train', 'SCIN']}
            methods[name] = score
    per_fold = []
    for f in range(5):
        subset = [r for r in rows if r['fold'] == f]
        y = np.asarray([base.CLASSES.index(r['label']) for r in subset])
        per_fold.append(dict(fold=f, selected=base.read(OUT / f'fold_{f}/selection_locked.json')['selected'],
            methods={name:base.metrics(np.asarray([r['predictions'][name] for r in subset]), y) for name in methods}))
    result = dict(status='complete_exploratory_five_fold', images=len(rows), methods=methods,
        per_fold=per_fold, outer_started_utc=started, completed_utc=now(),
        protocol_sha256=base.sha(OUT / 'protocol.json'), all_selections_sha256=base.sha(OUT / 'all_selections_locked.json'),
        limitations=p['limitations'], baseline_changed=False, serving_changed=False)
    base.write(OUT / 'oof_decisions.json', rows)
    base.write(OUT / 'results.json', result)
    previous.verify(parent)
    previous.verify(p)
    base.write(OUT / 'verification.json', dict(status='PASS', results_sha256=base.sha(OUT / 'results.json'),
        decisions_sha256=base.sha(OUT / 'oof_decisions.json'), baseline_reproduced=True,
        cancer_mask_unchanged=True, all_choices_locked_before_outer=True,
        scope='Technical consistency, not clinical validation'))
    base.write(OUT / 'status.json', dict(state='complete', utc=now()))
    print(json.dumps({name:{k:score[k] for k in ['accuracy','macro_f1','correct','changed']} for name,score in methods.items()}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['register', 'fit', 'evaluate', 'all'], default='all')
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        p = prepare()
        if args.stage in ['fit', 'all']:
            fit_all(p)
        if args.stage in ['evaluate', 'all']:
            evaluate(p)


if __name__ == '__main__':
    main()
