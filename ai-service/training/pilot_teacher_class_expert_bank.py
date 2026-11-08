"""Class-specific parent-feature specialists with grouped inner cross-fitting.

Fold-0 pilot: three frozen CNN feature heads, shared versus class-specific
selection. No threshold search or access to outer labels during selection.
"""
from __future__ import annotations
import argparse
from itertools import product
from pathlib import Path
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

import pilot_teacher_multifeature_specialist as features

latest, base, prior = features.latest, features.base, features.prior
ROOT = features.ROOT
NAME = 'teacher_class_expert_bank_fold0_seed42_20261024'
OUT = ROOT / 'ai-service/reports' / NAME
MODELS = ROOT / 'ai-service/candidates' / NAME
ARCHS = features.ARCHS
METHODS = ['current_policy', 'shared_selector', 'class_selector']


def cached_blocks(role, rows):
    values = []
    for arch, dim in zip(ARCHS, features.DIMS):
        if arch == 'resnet50':
            path = (features.SOURCE / 'fold_0_resnet_features.npz' if role == 'source_transfer'
                    else prior.OUT / f'B_specialist/fold_0/{role}_features.npz')
        else:
            path = features.OUT / f'{role}_{arch}_features.npz'
        with np.load(path, allow_pickle=False) as z:
            paths = z['paths'].tolist()
            assert len(paths) == len(set(paths))
            lookup = {x:i for i,x in enumerate(paths)}
            array = z['features'][[lookup[r['path']] for r in rows]].copy()
        assert array.shape == (len(rows), dim) and np.isfinite(array).all()
        values.append(array)
    return values


def candidates(current, probabilities):
    """Columns: keep, B0 head, ConvNeXt head, ResNet head; no chaining."""
    return np.column_stack([current] + [prior.route(current, q) for q in probabilities])


def apply_actions(current, options, actions):
    current = np.asarray(current)
    options = np.asarray(options)
    if (options.shape != (len(current), 4) or len(actions) != 4
            or any(int(a) != a or a < 0 or a > 3 for a in actions)):
        raise ValueError('Four expert actions and Nx4 decisions required')
    if not np.array_equal(options[:, 0], current):
        raise ValueError('First action must keep current predictions')
    if not np.all((options == base.CANCER) == (current[:, None] == base.CANCER)):
        raise ValueError('Every expert must preserve the exact cancer mask')
    result = current.copy()
    for label, action in zip(prior.SPECIAL, actions):
        ids = np.flatnonzero(current == label)
        result[ids] = options[ids, int(action)]
    return result


def select_actions(current, options, truth, class_specific):
    """Only fit-part labels enter this finite 4 versus 256 action comparison."""
    reference = base.metrics(current, truth)
    settings = product(range(4), repeat=4) if class_specific else ((i,)*4 for i in range(4))
    best = None
    passing = 0
    for actions in settings:
        score = base.metrics(apply_actions(current, options, actions), truth)
        if prior.failures(score, reference):
            continue
        passing += 1
        # Exact ties retain more classes; then prefer earlier actions deterministically.
        key = (score['macro_f1'], latest.previous.mean_focus(score, 'recall'), score['accuracy'],
               -sum(a != 0 for a in actions), tuple(-a for a in actions))
        if best is None or key > best[0]:
            best = (key, list(actions), score)
    assert best is not None  # keep is always feasible
    return dict(actions=best[1], metrics=best[2], passing=passing,
                evaluated=256 if class_specific else 4)


def choose(decisions, truth):
    scores = {n:base.metrics(pred, truth) for n,pred in decisions.items()}
    trials = {n:dict(metrics=s, guard_failures=prior.failures(s, scores['current_policy'])) for n,s in scores.items()}
    treatment = scores['class_selector']
    if treatment['macro_f1'] + 1e-12 < scores['shared_selector']['macro_f1']:
        trials['class_selector']['guard_failures'].append('macro_f1_below_shared_control')
    for name in ['shared_selector', 'current_policy']:
        if latest.previous.mean_focus(treatment) <= latest.previous.mean_focus(scores[name]) + 1e-12:
            trials['class_selector']['guard_failures'].append('no_weak_mean_f1_gain_vs_' + name)
    passing = [n for n in METHODS if not trials[n]['guard_failures']]
    selected = max(passing, key=lambda n:(scores[n]['macro_f1'], latest.previous.mean_focus(scores[n], 'recall'),
                    scores[n]['accuracy'], n == 'current_policy', n == 'shared_selector'))
    return dict(selected=selected, trials=trials)


def prepare():
    if (OUT / 'protocol.json').exists():
        p = base.read(OUT / 'protocol.json'); prior.verify(p); return p
    registry = base.read(ROOT / 'ai-service/reports/active_research_track.json')
    assert registry['next_experiment'] is None
    previous = base.read(features.OUT / 'protocol.json')
    assert base.read(features.OUT / 'completion.json')['status'] == 'complete_verified_pilot_not_selected'
    prior.verify(previous)
    files = [Path(__file__), ROOT / 'ai-service/tests/test_teacher_class_expert_bank.py',
             features.OUT / 'protocol.json', features.OUT / 'completion.json',
             features.OUT / 'independent_review.json', features.OUT / 'verification.json',
             ROOT / 'ai-service/training/pilot_teacher_multifeature_specialist.py',
             ROOT / 'ai-service/training/run_teacher_priorities_ensemble_specialist.py',
             ROOT / 'ai-service/training/run_teacher_dropout_specialist.py',
             prior.MODELS / 'fold_0/specialist.npz']
    files += list(features.OUT.glob('*_features.npz'))
    files += [prior.OUT / f'B_specialist/fold_0/{role}_features.npz'
              for role in ['train', 'inner_validation', 'outer_holdout']]
    files += [features.SOURCE / 'fold_0_resnet_features.npz']
    p = dict(name=NAME, registered_utc=features.utc(), fold=0, classes=base.CLASSES,
        parent_protocol=previous['parent_protocol'], configuration=features.CONFIG,
        frozen_sha256={**previous['frozen_sha256'], **{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},
        intervention='One five-way logistic specialist per original parent feature block. Shared control uses one action across four predicted classes; treatment chooses an action per CURRENT predicted Lupus/Psoriasis/Tinea/Eczema. No ground-truth class enters inference.',
        head_training='4043 original train only; same C=.001 and targets Lupus/Psoriasis/Tinea/Eczema/Other; train-only StandardScaler per block. Match each standardized block mean squared norm to standardized ResNet train norm. Three fits, frozen CNNs.',
        actions=['keep_current', 'efficientnet_b0_head', 'convnext_tiny_head', 'resnet50_head'],
        routing='Fixed >=.8 confidence and Other abstention, only current weak4 predictions change; no chained changes and exact SkinCancer mask.',
        selection='Three StratifiedGroupKFold inner parts, shuffle=True seed42. On each fit partition enumerate 4 shared or 256 class-specific action maps. Require strict original weak Recall/F1 and total guards on that fit partition; maximize MacroF1, mean weak Recall, Accuracy, then fewest non-keep class actions and lexicographic earlier actions. Evaluate selected maps only on held inner part. Choose method using stitched meta-held predictions and same strict guards. Treatment also MF>=shared and mean weak F1 strictly above shared and current. Exact method ties prefer current then shared. Fit final maps on all718 inner labels, lock before any new outer/source predictions. Final maps differ from cross-fit maps; report both.',
        scope='One fold-0 pilot; 4043 train,718 inner,1176 outer. Reuse SHA-frozen feature caches; no new CNN fits or fresh labels. Outer and1709 source images descriptive only, not used to choose action maps or method.',
        limitations=previous['limitations'] + [
            'The class selector has 256 candidate maps versus4 shared maps; grouped cross-fitting reduces but cannot remove selection overfit in only718 inner images.',
            'Frozen parents already used inner labels for epoch choice; meta-held head selection is not full nested CNN retraining.',
            'Actions depend on predicted classes, never true diagnoses. Preserving the cancer mask also preserves all previous cancer errors.',
            'No deployment or new global5937 score from this single-fold pilot.'],
        new_CNN_fits=0, new_backbones=0, global_5937_score_changed=False, serving_changed=False)
    OUT.mkdir(parents=True, exist_ok=True)
    base.write(OUT / 'protocol.json', p)
    base.write(OUT / 'research_registry_before.json', registry)
    registry['next_experiment'] = OUT.relative_to(ROOT).as_posix()
    registry['next_experiment_status'] = 'registered_class_specific_expert_bank_fold0'
    base.write(ROOT / 'ai-service/reports/active_research_track.json', registry)
    return p


def fit_and_lock(p):
    parent = base.read(ROOT / p['parent_protocol'])
    train_rows = prior.role_rows(parent, 0, 'train')
    rows = prior.role_rows(parent, 0, 'inner_validation')
    train = cached_blocks('train', train_rows); inner = cached_blocks('inner_validation', rows)
    scalers = [StandardScaler().fit(x) for x in train]
    zz = [s.transform(x) for s,x in zip(scalers, train)]
    energies = [float(np.square(x.astype(float)).sum(1).mean()) for x in zz]
    assert min(energies) > 0
    factors = np.sqrt(energies[2] / np.asarray(energies))
    target = latest.fiveway(np.array([base.CLASSES.index(r['label']) for r in train_rows]))
    MODELS.mkdir(parents=True, exist_ok=True)
    q = []; training = {}
    for i,arch in enumerate(ARCHS):
        x = np.multiply(zz[i], factors[i], dtype=np.float32)
        with warnings.catch_warnings():
            warnings.simplefilter('error', ConvergenceWarning)
            fitted = LogisticRegression(**p['configuration']).fit(x, target)
        model = dict(mean=scalers[i].mean_, scale=scalers[i].scale_, factor=factors[i],
                     coef=fitted.coef_, intercept=fitted.intercept_, classes=fitted.classes_)
        np.savez_compressed(MODELS / f'{arch}.npz', **model)
        z = np.multiply(features.standardize(inner[i], model['mean'], model['scale']), model['factor'], dtype=np.float32)
        q.append(features.probability(model, z))
        training[arch] = dict(dimensions=x.shape[1], factor=float(factors[i]),
            train_mean_squared_norm=float(np.square(x.astype(float)).sum(1).mean()), iterations=fitted.n_iter_.tolist())
        if arch == 'resnet50':
            with np.load(prior.MODELS / 'fold_0/specialist.npz', allow_pickle=False) as old:
                error = max(float(np.abs(model['coef']-old['coef']).max()), float(np.abs(model['intercept']-old['intercept']).max()))
            assert error < 1e-10, error
            training['resnet_control_parameter_error'] = error
    with np.load(latest.OUT / 'fold_0/inner_decisions.npz', allow_pickle=False) as z:
        assert z['paths'].tolist() == [r['path'] for r in rows]
        selected = base.read(latest.OUT / 'fold_0/selection_locked.json')['selected']
        current = z[selected].copy(); truth = z['truth'].copy()
    options = candidates(current, q)
    decisions = dict(current_policy=current.copy(), shared_selector=current.copy(), class_selector=current.copy())
    groups = np.array([r['group'] for r in rows]); parts = []; covered = np.zeros(len(rows), dtype=int)
    for fit, hold in StratifiedGroupKFold(3, shuffle=True, random_state=42).split(np.zeros(len(rows)), truth, groups):
        assert set(groups[fit]).isdisjoint(groups[hold])
        part = dict(fit_indices=fit.tolist(), hold_indices=hold.tolist())
        for name, specific in [('shared_selector', False), ('class_selector', True)]:
            spec = select_actions(current[fit], options[fit], truth[fit], specific)
            decisions[name][hold] = apply_actions(current[hold], options[hold], spec['actions'])
            part[name] = spec
        covered[hold] += 1; parts.append(part)
    assert np.all(covered == 1)
    lock = choose(decisions, truth)
    final = {name:select_actions(current, options, truth, specific)
             for name,specific in [('shared_selector', False), ('class_selector', True)]}
    np.savez_compressed(OUT / 'inner_decisions.npz', paths=[r['path'] for r in rows], truth=truth,
        options=options, probability=np.array(q), groups=groups, **decisions)
    training['meta_parts'] = parts
    training['raw_head_inner_metrics'] = {arch:base.metrics(options[:,i+1], truth) for i,arch in enumerate(ARCHS)}
    base.write(OUT / 'training_report.json', training)
    lock.update(final_maps=final, locked_utc=features.utc(), protocol_sha256=base.sha(OUT / 'protocol.json'),
        artifacts_sha256={x.relative_to(ROOT).as_posix():base.sha(x) for x in [*MODELS.glob('*.npz'), OUT / 'inner_decisions.npz', OUT / 'training_report.json']})
    base.write(OUT / 'selection_locked.json', lock)
    print(dict(selected=lock['selected'], trials={n:t['guard_failures'] for n,t in lock['trials'].items()}, final_actions={n:s['actions'] for n,s in final.items()}), flush=True)


def evaluate_locked(p):
    assert not (OUT / 'results.json').exists(), 'Preserve completed evaluation'
    lock = base.read(OUT / 'selection_locked.json')
    assert lock['protocol_sha256'] == base.sha(OUT / 'protocol.json')
    for path,digest in lock['artifacts_sha256'].items():
        assert base.sha(ROOT / path) == digest, path
    started = features.utc(); parent = base.read(ROOT / p['parent_protocol'])
    source = base.read(features.SOURCE / 'protocol.json')
    original = {r['path']:r for r in base.read(latest.OUT / 'oof_decisions.json')}
    external = {r['path']:r for r in base.read(features.SOURCE / 'source_decisions.json')}
    heads = []
    for arch in ARCHS:
        with np.load(MODELS / f'{arch}.npz', allow_pickle=False) as z:
            heads.append({k:z[k].copy() for k in z.files})
    output = []; scores = {}
    for role,rows in [('outer_holdout', prior.role_rows(parent, 0, 'outer_holdout')), ('source_transfer', source['rows'])]:
        xx = cached_blocks(role, rows); truth = np.array([base.CLASSES.index(r['label']) for r in rows])
        current = np.array([original[r['path']]['predictions']['validation_selected'] if role == 'outer_holdout'
                            else external[r['path']]['predictions']['validation_selected'][0] for r in rows])
        q = [features.probability(h, np.multiply(features.standardize(x, h['mean'], h['scale']), h['factor'], dtype=np.float32)) for h,x in zip(heads,xx)]
        options = candidates(current, q)
        dd = dict(current_policy=current)
        dd.update({arch+'_head':options[:,i+1] for i,arch in enumerate(ARCHS)})
        for name,spec in lock['final_maps'].items():
            dd[name] = apply_actions(current, options, spec['actions'])
        dd['validation_selected'] = dd[lock['selected']]
        np.savez_compressed(OUT / f'{role}_probabilities.npz', paths=[r['path'] for r in rows], probability=np.array(q))
        for pred in dd.values():
            assert np.array_equal(pred == 5, current == 5)
        index = {r['path']:i for i,r in enumerate(rows)}
        slices = {'original_outer':list(index)} if role == 'outer_holdout' else source['subsets']
        for name,paths in slices.items():
            ids = [index[x] for x in paths]
            scores[name] = dict(images=len(ids), methods={n:base.metrics(pred[ids], truth[ids]) for n,pred in dd.items()})
        output.extend(dict(**r, role=role, predictions={n:int(pred[i]) for n,pred in dd.items()}) for i,r in enumerate(rows))
    base.write(OUT / 'held_decisions.json', output)
    result = dict(status='complete_exploratory_class_expert_pilot', fold=0, selected=lock['selected'],
        validation=lock['trials'], held=scores, held_started_utc=started, completed_utc=features.utc(),
        protocol_sha256=base.sha(OUT / 'protocol.json'), selection_sha256=base.sha(OUT / 'selection_locked.json'),
        head_fits=3, new_CNN_fits=0, global_5937_score_changed=False, serving_changed=False, limitations=p['limitations'])
    base.write(OUT / 'results.json', result)
    prior.verify(p)
    base.write(OUT / 'verification.json', dict(status='PASS', results_sha256=base.sha(OUT / 'results.json'),
        group_crossfit_complete=True, exact_cancer_masks=True, selection_locked_before_held=True))
    print({k:{n:{m:s[m] for m in ['accuracy','macro_f1']} for n,s in v['methods'].items() if n in METHODS} for k,v in scores.items()}, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true'); args = parser.parse_args()
    with threadpool_limits(limits=1):
        p = prepare()
        if args.prepare_only:
            return
        assert not (OUT / 'results.json').exists(), 'Preserve completed pilot'
        if not (OUT / 'selection_locked.json').exists():
            fit_and_lock(p)
        evaluate_locked(p)


if __name__ == '__main__':
    main()
