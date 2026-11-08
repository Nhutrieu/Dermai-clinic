"""Two isolated five-fold development experiments requested by the supervisor.

A changes only ResNet fusion weight. B adds one frozen-feature specialist.
All choices are validation-only, with all five selections locked before each
experiment's outer evaluation. Existing data have historical research exposure.
"""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import torch
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from torch.utils.data import DataLoader

import evaluate_original_eight_cancer_locked_fusion as base
from common import ImageSample, ImageSampleDataset, build_model, evaluation_transform

ROOT = base.ROOT
NAME = 'teacher_priorities_ensemble_specialist_seed42_20261022'
OUT = ROOT / 'ai-service/reports' / NAME
MODELS = ROOT / 'ai-service/candidates' / NAME
FOCUS = [3, 4, 6]
SPECIAL = [3, 4, 6, 2]  # Lupus, Psoriasis, Tinea and the common confusion Eczema.
ALPHAS = [0., .1, .2, .3, .4, .5]
THRESHOLD = .8


def checkpoint(fold):
    suffix = ('original_eight_resnet50_pilot_fold0_seed42' if fold == 0
              else f'original_eight_resnet50_cv_fold{fold}_seed42')
    return ROOT / 'ai-service/candidates' / suffix / 'best_model.pth'


def verify(p):
    for relative, expected in p['frozen_sha256'].items():
        assert base.sha(ROOT / relative) == expected, relative


def prepare():
    path = OUT / 'protocol.json'
    if path.exists():
        p = base.read(path)
        verify(p)
        return p
    base.verify_frozen(base.read(base.OUT / 'protocol.json'))
    assert base.read(base.OUT / 'verification.json')['status'] == 'PASS'
    registry = base.read(ROOT / 'ai-service/reports/active_research_track.json')
    assert registry['active_track'] == 'original_eight' and registry['next_experiment'] is None
    manifest = {r['path']: r for r in base.read(base.MANIFEST)['images']}
    cv = base.read(base.CV / 'protocol.json')
    sources = [Path(__file__), ROOT / 'ai-service/training/common.py',
               ROOT / 'ai-service/training/evaluate_original_eight_cancer_locked_fusion.py',
               base.CV / 'protocol.json', base.MANIFEST, base.SERVING,
               base.OUT / 'protocol.json', base.OUT / 'results.json',
               base.OUT / 'all_selections_locked.json', base.OUT / 'oof_decisions.json']
    folds = []
    for fold in range(5):
        roles = cv['folds'][fold]['roles']
        assert set().union(*(set(v) for v in roles.values())) == set(manifest)
        assert sum(map(len, roles.values())) == len(manifest) == 5937
        groups = {role: {manifest[x]['scene_or_case_group'] for x in paths}
                  for role, paths in roles.items()}
        for a, b in [('train', 'inner_validation'), ('train', 'outer_holdout'),
                     ('inner_validation', 'outer_holdout')]:
            assert groups[a].isdisjoint(groups[b])
        lock = base.read(base.OUT / f'fold_{fold}/selection_locked.json')
        protection = lock['trials'][lock['selected']]['spec']['protected']
        folds.append(dict(fold=fold, roles=roles, baseline_protected=protection,
                          checkpoint=checkpoint(fold).relative_to(ROOT).as_posix()))
        sources += [checkpoint(fold), base.OUT / f'fold_{fold}/selection_locked.json',
                    base.fold_dir(fold) / 'selection_locked.json',
                    base.fold_dir(fold) / 'validation_predictions.npz',
                    base.fold_dir(fold) / 'test_predictions.json']
    for relative, row in manifest.items():
        assert base.sha(ROOT / relative) == row['sha256'], relative
    p = dict(name=NAME, date='2026-10-22', classes=base.CLASSES, images=5937,
             folds=folds, manifest=manifest,
             frozen_sha256={x.relative_to(ROOT).as_posix(): base.sha(x) for x in sources},
             A=dict(change='Only ResNet mixture weight; reuse baseline class protection and B0/ConvNeXt reference.',
                    resnet_weights=ALPHAS, fallback='current_fusion', train_new_models=False),
             B=dict(change='Only add one five-way specialist to the current baseline; no A weight used.',
                    backbone='Original fold-specific ResNet50, eval/FP32/frozen; 2048 features.',
                    labels=['Lupus', 'Psoriasis', 'Tinea', 'Eczema', 'Other'],
                    train='Every original training image once; unweighted scaler and unweighted multinomial logistic loss. No auxiliary images, mining or resampling.',
                    C=.001, solver='lbfgs', multi_class='multinomial', max_iter=3000,
                    tol=1e-7, random_state=42, threshold=THRESHOLD,
                    routing='Only baseline Lupus/Psoriasis/Tinea/Eczema calls may change; Other abstains; max head score must be >=.8. Never add or remove a SkinCancer call.'),
             selection='Against current fusion on each inner validation: Accuracy/MacroF1 no decline; each focus Recall/F1 no decline, focus Precision loss<=.02; other Recall loss<=.02; exact SkinCancer Recall/Precision. Rank MacroF1, mean focus Recall, Accuracy, prefer baseline on tie. Lock all5 selections before each experiment outer evaluation.',
             reporting='Report raw and validation-selected methods separately; all folds, all classes, source slices and 1000 group-bootstrap paired Accuracy/MacroF1 deltas. No combined A+B trial.',
             limitations=['Exploratory development on repeatedly inspected data; no new independent patient test.',
                          'Frozen CNN parents already used inner validation for epoch selection; not fully nested retraining.',
                          'One parent CNN seed. Five folds are not five random training seeds.',
                          'Scene/case groups are not verified patient IDs. SCIN Lupus has only11 images.',
                          'Fixed SkinCancer mask preserves previous false positives and false negatives.',
                          'Head/mixture scores are not calibrated clinical probabilities.'],
             references=['https://scikit-learn.org/1.3/modules/generated/sklearn.linear_model.LogisticRegression.html',
                         'https://scikit-learn.org/1.3/common_pitfalls.html',
                         'https://scikit-learn.org/1.3/modules/ensemble.html#voting-classifier'],
             serving_changed=False)
    base.write(path, p)
    base.write(OUT / 'status.json', dict(state='registered', priorities=[1, 2]))
    return p


def mixture(reference, resnet, protected, alpha):
    base.check_probabilities(reference, resnet)
    if not 0 <= alpha <= 1 or base.CANCER not in protected:
        raise ValueError('Invalid weight or missing cancer protection')
    original = reference.argmax(1)
    result = original.copy()
    allowed = [i for i in range(8) if i not in protected]
    mask = ~np.isin(original, protected)
    if allowed:
        score = (1-alpha) * reference + alpha * resnet
        result[mask] = np.asarray(allowed)[score[mask][:, allowed].argmax(1)]
    for i in protected:
        assert np.array_equal(result == i, original == i)
    return result


def route(current, probability):
    current = np.asarray(current)
    probability = np.asarray(probability)
    if (probability.shape != (len(current), 5) or not np.isfinite(probability).all()
            or (probability < 0).any() or not np.allclose(probability.sum(1), 1, atol=1e-8)):
        raise ValueError('Expected Nx5 head probabilities')
    winner = probability.argmax(1)
    accepted = np.isin(current, SPECIAL) & (winner < 4) & (probability.max(1) >= THRESHOLD)
    prediction = current.copy()
    prediction[accepted] = np.asarray(SPECIAL)[winner[accepted]]
    assert np.array_equal(prediction == base.CANCER, current == base.CANCER)
    return prediction


def failures(candidate, baseline):
    failed = base.guard_failures(candidate, baseline)
    for i in FOCUS:
        label = base.CLASSES[i]
        for key in ['recall', 'f1']:
            if candidate['per_class'][label][key] + 1e-12 < baseline['per_class'][label][key]:
                failed.append(label + '_' + key)
    return sorted(set(failed))


def choose(decisions, truth):
    scores = {name: base.metrics(pred, truth) for name, pred in decisions.items()}
    reference = scores['current_fusion']
    trials = {name: dict(metrics=score, guard_failures=failures(score, reference))
              for name, score in scores.items()}
    passing = [name for name, trial in trials.items() if not trial['guard_failures']]
    selected = max(passing, key=lambda name: (scores[name]['macro_f1'],
        np.mean([scores[name]['per_class'][base.CLASSES[i]]['recall'] for i in FOCUS]),
        scores[name]['accuracy'], name == 'current_fusion'))
    return dict(selected=selected, trials=trials)


def validation(p, fold):
    paths, truth, reference, resnet = base.validation_arrays(fold)
    assert paths == p['folds'][fold]['roles']['inner_validation']
    current = base.decide(reference, resnet, p['folds'][fold]['baseline_protected'])
    return paths, truth, reference, resnet, current


def lock_all(experiment):
    folder = OUT / experiment
    hashes = {str(f): base.sha(folder / f'fold_{f}/selection_locked.json') for f in range(5)}
    base.write(folder / 'all_selections_locked.json', dict(selections_sha256=hashes,
        protocol_sha256=base.sha(OUT / 'protocol.json'), outer_evaluation_started=False))
    return hashes


def outer_rows(p, fold):
    rows = base.read(base.fold_dir(fold) / 'test_predictions.json')
    assert {r['path'] for r in rows} == set(p['folds'][fold]['roles']['outer_holdout'])
    for row in rows:
        original = p['manifest'][row['path']]
        assert (row['label'], row['sha256'], row['group']) == (original['class'], original['sha256'], original['scene_or_case_group'])
    reference = np.asarray([r['probabilities'][base.REFERENCE] for r in rows])
    resnet = np.asarray([r['probabilities']['resnet50'] for r in rows])
    current = base.decide(reference, resnet, p['folds'][fold]['baseline_protected'])
    return rows, reference, resnet, current


def records(rows, fold, decisions):
    return [dict(path=r['path'], sha256=r['sha256'], group=r['group'], label=r['label'], fold=fold,
                 source='SCIN' if r['path'].startswith('SkinDisease/scin-v1/') else 'original_train',
                 predictions={name: int(pred[i]) for name, pred in decisions.items()}) for i, r in enumerate(rows)]


def paired_intervals(rows, predictions, current, truth):
    _, inverse = np.unique([r['group'] for r in rows], return_inverse=True)
    count = int(inverse.max()) + 1
    matrices = []
    for pred in [current, predictions]:
        group = np.zeros((count, 64))
        np.add.at(group, (inverse, truth*8 + pred), 1)
        matrices.append(group)
    rng = np.random.default_rng(20261022)
    deltas = []
    for _ in range(10):
        weights = rng.multinomial(count, np.ones(count)/count, size=100)
        scores = []
        for group in matrices:
            cm = (weights @ group).reshape(-1, 8, 8)
            tp = np.diagonal(cm, axis1=1, axis2=2)
            denom = cm.sum(1) + cm.sum(2)
            f1 = np.divide(2*tp, denom, out=np.zeros_like(tp), where=denom > 0).mean(1)
            scores.append(np.stack([tp.sum(1)/cm.sum((1, 2)), f1], axis=1))
        deltas.append(scores[1] - scores[0])
    values = np.concatenate(deltas)
    return {key: np.quantile(values[:, i], [.025, .975]).tolist()
            for i, key in enumerate(['accuracy', 'macro_f1'])}


def summarize(p, experiment, rows, locks):
    rows.sort(key=lambda r: r['path'])
    assert len(rows) == len({r['path'] for r in rows}) == 5937
    old = {r['path']: r['predictions'][base.SELECTED] for r in base.read(base.OUT / 'oof_decisions.json')}
    current = np.asarray([r['predictions']['current_fusion'] for r in rows])
    assert current.tolist() == [old[r['path']] for r in rows]
    truth = np.asarray([base.CLASSES.index(r['label']) for r in rows])
    methods = {}
    for name in rows[0]['predictions']:
        prediction = np.asarray([r['predictions'][name] for r in rows])
        assert np.array_equal(prediction == base.CANCER, current == base.CANCER)
        score = base.metrics(prediction, truth)
        score['correct'] = int((prediction == truth).sum())
        score['changed'] = int((prediction != current).sum())
        score['paired_delta_95pct'] = paired_intervals(rows, prediction, current, truth)
        score['per_source'] = {}
        for source in ['original_train', 'SCIN']:
            mask = np.asarray([r['source'] == source for r in rows])
            score['per_source'][source] = dict(images=int(mask.sum()), **base.metrics(prediction[mask], truth[mask]))
        methods[name] = score
    per_fold = []
    for fold in range(5):
        subset = [r for r in rows if r['fold'] == fold]
        y = np.asarray([base.CLASSES.index(r['label']) for r in subset])
        per_fold.append(dict(fold=fold, selected=base.read(OUT / experiment / f'fold_{fold}/selection_locked.json')['selected'],
            methods={name: base.metrics(np.asarray([r['predictions'][name] for r in subset]), y) for name in methods}))
    folder = OUT / experiment
    base.write(folder / 'oof_decisions.json', rows)
    result = dict(status='complete_exploratory_five_fold', images=5937, methods=methods, per_fold=per_fold,
                  protocol_sha256=base.sha(OUT / 'protocol.json'), limitations=p['limitations'], serving_changed=False)
    base.write(folder / 'results.json', result)
    assert locks == {str(f): base.sha(folder / f'fold_{f}/selection_locked.json') for f in range(5)}
    verify(p)
    base.write(folder / 'verification.json', dict(status='PASS', results_sha256=base.sha(folder / 'results.json'),
               baseline_reproduced=True, cancer_mask_unchanged=True, scope='Technical consistency; not clinical validation'))
    print(json.dumps(dict(experiment=experiment, complete=True, results={n: dict(accuracy=s['accuracy'], macro_f1=s['macro_f1'], correct=s['correct']) for n, s in methods.items()})), flush=True)
    return result


def run_a(p):
    experiment = 'A_ensemble_weight'
    folder = OUT / experiment
    if (folder / 'results.json').exists():
        return base.read(folder / 'results.json')
    for fold in range(5):
        _, truth, reference, resnet, current = validation(p, fold)
        decisions = {'current_fusion': current}
        for alpha in ALPHAS:
            decisions[f'weight_{alpha:.2f}'] = mixture(reference, resnet, p['folds'][fold]['baseline_protected'], alpha)
        selection = choose(decisions, truth)
        path = folder / f'fold_{fold}/selection_locked.json'
        if path.exists():
            assert base.read(path) == selection
        else:
            base.write(path, selection)
        print(json.dumps(dict(experiment='A', fold=fold, selected=selection['selected'])), flush=True)
    locks = lock_all(experiment)
    output = []
    for fold in range(5):
        rows, reference, resnet, current = outer_rows(p, fold)
        decisions = {'current_fusion': current}
        for alpha in ALPHAS:
            decisions[f'weight_{alpha:.2f}'] = mixture(reference, resnet, p['folds'][fold]['baseline_protected'], alpha)
        selected = base.read(folder / f'fold_{fold}/selection_locked.json')['selected']
        decisions['validation_selected'] = decisions[selected]
        output += records(rows, fold, decisions)
    return summarize(p, experiment, output, locks)


class Extractor:
    def __init__(self, fold):
        cp = torch.load(checkpoint(fold), map_location='cpu', weights_only=False)
        assert cp['classes'] == base.CLASSES and cp['architecture'] == 'resnet50'
        self.model = build_model('resnet50', 8, pretrained=False)
        self.model.load_state_dict(cp['model_state_dict'])
        self.model.cuda().eval().requires_grad_(False)
        self.slot = []
        self.hook = self.model.avgpool.register_forward_hook(lambda m, x, y: self.slot.append(y.flatten(1)))

    def infer(self, rows):
        samples = [ImageSample(ROOT / r['path'], 0, r['sha256'], r['group']) for r in rows]
        loader = DataLoader(ImageSampleDataset(samples, evaluation_transform()), batch_size=16,
                            shuffle=False, num_workers=0, pin_memory=True)
        features, probabilities = [], []
        with torch.inference_mode():
            for images, _ in loader:
                logits = self.model(images.cuda(non_blocking=True))
                x = self.slot.pop()
                assert torch.equal(logits, self.model.fc(x))
                features.append(x.cpu().numpy())
                probabilities.append(logits.softmax(1).cpu().numpy())
        assert not self.slot
        return np.concatenate(features), np.concatenate(probabilities)

    def close(self):
        self.hook.remove()
        del self.model
        torch.cuda.empty_cache()


def role_rows(p, fold, role):
    return [dict(path=path, sha256=p['manifest'][path]['sha256'],
                 group=p['manifest'][path]['scene_or_case_group'], label=p['manifest'][path]['class'])
            for path in p['folds'][fold]['roles'][role]]


def cached(p, extractor, fold, role, rows):
    path = OUT / 'B_specialist' / f'fold_{fold}' / (role + '_features.npz')
    if path.exists():
        with np.load(path, allow_pickle=False) as a:
            assert a['paths'].tolist() == [r['path'] for r in rows]
            assert a['protocol_sha256'].item() == base.sha(OUT / 'protocol.json')
            return a['features'].copy(), a['probabilities'].copy()
    x, probability = extractor.infer(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp.npz')
    np.savez_compressed(temporary, paths=[r['path'] for r in rows], features=x, probabilities=probability,
                        protocol_sha256=base.sha(OUT / 'protocol.json'))
    temporary.replace(path)
    print(json.dumps(dict(experiment='B', fold=fold, role=role, features=len(rows))), flush=True)
    return x, probability


def head_probability(path, features):
    with np.load(path, allow_pickle=False) as head:
        assert head['classes'].tolist() == list(range(5))
        logits = ((features - head['mean'])/head['scale']) @ head['coef'].T + head['intercept']
    logits -= logits.max(1, keepdims=True)
    values = np.exp(logits)
    return values/values.sum(1, keepdims=True)


def run_b(p):
    experiment = 'B_specialist'
    folder = OUT / experiment
    if (folder / 'results.json').exists():
        return base.read(folder / 'results.json')
    for fold in range(5):
        head_path = MODELS / f'fold_{fold}/specialist.npz'
        lock_path = folder / f'fold_{fold}/selection_locked.json'
        if lock_path.exists():
            assert base.sha(head_path) == base.read(lock_path)['head_sha256']
            continue
        extractor = Extractor(fold)
        rows = role_rows(p, fold, 'train')
        x, _ = cached(p, extractor, fold, 'train', rows)
        y8 = np.asarray([base.CLASSES.index(r['label']) for r in rows])
        target = np.asarray([SPECIAL.index(i) if i in SPECIAL else 4 for i in y8])
        scaler = StandardScaler().fit(x)
        assert np.unique(target).tolist() == list(range(5))
        with warnings.catch_warnings():
            warnings.simplefilter('error', ConvergenceWarning)
            head = LogisticRegression(C=.001, solver='lbfgs', multi_class='multinomial',
                max_iter=3000, tol=1e-7, random_state=42).fit(scaler.transform(x), target)
        if head_path.exists():
            # An interrupted fit must reproduce the same saved coefficients.
            assert np.allclose(head_probability(head_path, x), head.predict_proba(scaler.transform(x)), atol=1e-12)
        else:
            head_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(head_path, mean=scaler.mean_, scale=scaler.scale_, coef=head.coef_,
                                intercept=head.intercept_, classes=head.classes_)
        assert np.allclose(head_probability(head_path, x), head.predict_proba(scaler.transform(x)), atol=1e-12)
        base.write(folder / f'fold_{fold}/training_report.json', dict(images=len(rows), target_counts=np.bincount(target).tolist(),
            iterations=head.n_iter_.tolist(), backbone_updated=False, augmentation=False, resampling=False,
            head_sha256=base.sha(head_path), train_paths_sha256=base.hashlib.sha256('\n'.join(r['path'] for r in rows).encode()).hexdigest()))
        inner = role_rows(p, fold, 'inner_validation')
        xx, raw = cached(p, extractor, fold, 'inner_validation', inner)
        paths, truth, _, expected, current = validation(p, fold)
        assert paths == [r['path'] for r in inner]
        assert float(np.abs(raw-expected).max()) < 2e-6
        probability = head_probability(head_path, xx)
        decisions = dict(current_fusion=current, specialist=route(current, probability))
        selection = choose(decisions, truth)
        selection.update(head_sha256=base.sha(head_path), train_images=len(rows),
                         parent_max_abs_difference=float(np.abs(raw-expected).max()))
        base.write(lock_path, selection)
        np.savez_compressed(folder / f'fold_{fold}/inner_decisions.npz', paths=paths, truth=truth,
                            current=current, head_probability=probability, specialist=decisions['specialist'])
        extractor.close()
        print(json.dumps(dict(experiment='B', fold=fold, selected=selection['selected'],
                              changed=int((decisions['specialist'] != current).sum()),
                              failures=selection['trials']['specialist']['guard_failures'])), flush=True)
    locks = lock_all(experiment)
    output = []
    for fold in range(5):
        rows, _, expected, current = outer_rows(p, fold)
        extractor = Extractor(fold)
        xx, raw = cached(p, extractor, fold, 'outer_holdout', rows)
        assert float(np.abs(raw-expected).max()) < 2e-6
        probability = head_probability(MODELS / f'fold_{fold}/specialist.npz', xx)
        decisions = dict(current_fusion=current, specialist=route(current, probability))
        selected = base.read(folder / f'fold_{fold}/selection_locked.json')['selected']
        decisions['validation_selected'] = decisions[selected]
        np.savez_compressed(folder / f'fold_{fold}/outer_decisions.npz', paths=[r['path'] for r in rows],
                            head_probability=probability)
        output += records(rows, fold, decisions)
        extractor.close()
    return summarize(p, experiment, output, locks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', choices=['A', 'B', 'both'], default='both')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    torch.set_num_threads(4)
    with threadpool_limits(limits=2):
        p = prepare()
        if args.prepare_only:
            print(json.dumps(dict(registered=NAME, priorities=[1, 2], folds=5)), flush=True)
            return
        base.write(OUT / 'status.json', dict(state='running', experiment=args.experiment))
        if args.experiment in ['A', 'both']:
            run_a(p)
        if args.experiment in ['B', 'both']:
            run_b(p)
        verify(p)
        complete = all((OUT / name / 'results.json').exists() for name in ['A_ensemble_weight', 'B_specialist'])
        base.write(OUT / 'status.json', dict(state='complete' if complete else 'partial', serving_changed=False,
                                           experiments_requested=args.experiment))


if __name__ == '__main__':
    main()
