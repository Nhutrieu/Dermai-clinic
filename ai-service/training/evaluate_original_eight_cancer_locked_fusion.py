"""Exploratory decision fusion of frozen original-eight predictions.

Preserve the reference cancer decision mask exactly. Select only on each
fold's existing inner validation; lock all folds before loading outer scores.
This is a decision policy, not calibrated final probabilities or a new CNN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parents[2]
NAME = 'original_eight_cancer_locked_resnet_fusion_seed42_20261021'
OUT = ROOT / 'ai-service/reports' / NAME
CV = ROOT / 'ai-service/reports/original_eight_resnet50_cv_seed42'
PILOT = ROOT / 'ai-service/reports/original_eight_resnet50_pilot_fold0_seed42'
MANIFEST = ROOT / 'ai-service/reports/scene_grouped_oof_folds_seed42.json'
BENCHMARK = ROOT / 'ai-service/reports/scene_grouped_oof_classwise_fusion_seed42.json'
SERVING = ROOT / 'ai-service/models/best_model.pth'
CLASSES = ['Acne', 'Candidiasis', 'Eczema', 'Lupus', 'Psoriasis', 'SkinCancer', 'Tinea', 'Warts']
CANCER = CLASSES.index('SkinCancer')
FOCUS = {'Lupus', 'Psoriasis', 'Tinea'}
REFERENCE = 'old_classwise'
FIXED = 'cancer_locked_resnet25'
ADAPTIVE = 'validation_protected_resnet25'
SELECTED = 'validation_selected'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def fold_dir(fold):
    return PILOT if fold == 0 else CV / f'fold_{fold}'


def check_probabilities(reference, resnet):
    for array in (reference, resnet):
        if array.ndim != 2 or array.shape[1] != 8 or not np.isfinite(array).all():
            raise ValueError('Expected finite Nx8 probabilities')
        if (array < 0).any() or not np.allclose(array.sum(axis=1), 1, atol=1e-5):
            raise ValueError('Invalid probability distribution')
    if reference.shape != resnet.shape:
        raise ValueError('Prediction shapes differ')


def decide(reference, resnet, protected):
    """Lock complete predicted-class masks; other rows cannot enter those classes.

    No truth labels are accepted by the prediction function. The returned
    labels are decisions, not argmaxes of a claimed calibrated distribution.
    """
    check_probabilities(reference, resnet)
    protected = sorted(set(protected))
    if CANCER not in protected or any(i not in range(8) for i in protected):
        raise ValueError('Protected classes must contain SkinCancer')
    original = reference.argmax(axis=1)
    fixed = np.isin(original, protected)
    allowed = [i for i in range(8) if i not in protected]
    result = original.copy()
    if allowed:
        mixture = .75 * reference + .25 * resnet
        result[~fixed] = np.asarray(allowed)[mixture[~fixed][:, allowed].argmax(axis=1)]
    for index in protected:
        assert np.array_equal(result == index, original == index)
    return result


def metrics(prediction, truth):
    precision, recall, f1, support = precision_recall_fscore_support(
        truth, prediction, labels=np.arange(8), zero_division=0)
    return dict(accuracy=float(accuracy_score(truth, prediction)), macro_f1=float(f1.mean()),
                macro_recall=float(recall.mean()),
                confusion_matrix=confusion_matrix(truth, prediction, labels=np.arange(8)).tolist(),
                per_class={label:dict(precision=float(precision[i]), recall=float(recall[i]),
                                     f1=float(f1[i]), support=int(support[i])) for i, label in enumerate(CLASSES)})


def protected_violations(candidate, reference):
    """Class-specific guards determine extra locks using validation alone."""
    failures = []
    for i, label in enumerate(CLASSES):
        key = 'precision' if label in FOCUS else 'recall'
        allowance = 0 if label == 'SkinCancer' else .02
        if candidate['per_class'][label][key] + 1e-12 < reference['per_class'][label][key] - allowance:
            failures.append(i)
    return failures


def guard_failures(candidate, reference):
    failures = []
    # The user asked to keep BOTH total scores, so neither may decline here.
    for key in ('accuracy', 'macro_f1'):
        if candidate[key] + 1e-12 < reference[key]:
            failures.append(key)
    for i in protected_violations(candidate, reference):
        failures.append(('precision_' if CLASSES[i] in FOCUS else 'recall_') + CLASSES[i])
    for key in ('recall', 'precision'):
        if abs(candidate['per_class']['SkinCancer'][key] - reference['per_class']['SkinCancer'][key]) > 1e-12:
            failures.append('SkinCancer_exact_' + key)
    return failures


def learn_protected(reference, resnet, truth):
    """Monotone protection, <=8 evaluations, no threshold/weight search."""
    baseline = metrics(reference.argmax(axis=1), truth)
    protected = {CANCER}
    trace = []
    for _ in range(8):
        score = metrics(decide(reference, resnet, protected), truth)
        new = set(protected_violations(score, baseline)) - protected
        trace.append(dict(protected=sorted(protected), added=sorted(new), metrics=score))
        if not new:
            return sorted(protected), trace
        protected |= new
    raise AssertionError('Protection did not converge')


def select(reference, resnet, truth):
    protected, trace = learn_protected(reference, resnet, truth)
    specs = {REFERENCE:dict(kind='reference', protected=list(range(8))),
             FIXED:dict(kind='locked', protected=[CANCER]),
             ADAPTIVE:dict(kind='locked', protected=protected)}
    baseline = metrics(reference.argmax(axis=1), truth)
    trials = {}
    for name, spec in specs.items():
        candidate = metrics(decide(reference, resnet, spec['protected']), truth)
        trials[name] = dict(spec=spec, metrics=candidate, guard_failures=guard_failures(candidate, baseline))
    eligible = [name for name in specs if not trials[name]['guard_failures']]
    # Original wins an exact tie; no outer input is accepted here.
    selected = max(eligible, key=lambda name: (trials[name]['metrics']['macro_f1'],
                   trials[name]['metrics']['accuracy'], name == REFERENCE, name == FIXED))
    return dict(selected=selected, trials=trials, protection_trace=trace)


def prepare():
    if (OUT / 'protocol.json').exists():
        protocol = read(OUT / 'protocol.json')
        verify_frozen(protocol)
        return protocol
    previous = read(CV / 'protocol.json')
    assert previous['classes'] == CLASSES and read(CV / 'verification.json')['status'] == 'PASS'
    assert sha(MANIFEST) == previous['outer_manifest_sha256']
    assert sha(BENCHMARK) == previous['benchmark_sha256']
    for relative, expected in previous['sources'].items():
        assert sha(ROOT / relative) == expected, relative
    for name, expected in previous['code_sha256'].items():
        assert sha(ROOT / 'ai-service/training' / name) == expected, name
    sources = {str(path.relative_to(ROOT)).replace('\\', '/'):sha(path) for path in
               [CV/'protocol.json', CV/'verification.json', MANIFEST, BENCHMARK, SERVING]}
    manifest = {row['path']:row for row in read(MANIFEST)['images']}
    assert len(manifest) == 5937
    for fold in range(5):
        folder = fold_dir(fold)
        for name in ('validation_predictions.npz', 'test_predictions.json', 'selection_locked.json'):
            path = folder / name
            sources[path.relative_to(ROOT).as_posix()] = sha(path)
        checkpoint = ROOT / ('ai-service/candidates/original_eight_resnet50_pilot_fold0_seed42/best_model.pth'
                       if fold == 0 else f'ai-service/candidates/original_eight_resnet50_cv_fold{fold}_seed42/best_model.pth')
        assert sha(checkpoint) == read(folder/'selection_locked.json')['checkpoint_sha256']
        sources[checkpoint.relative_to(ROOT).as_posix()] = sha(checkpoint)
        roles = previous['folds'][fold]['roles']
        groups = {role:{manifest[path]['scene_or_case_group'] for path in paths} for role,paths in roles.items()}
        assert sum(len(paths) for paths in roles.values()) == 5937
        assert set().union(*(set(paths) for paths in roles.values())) == set(manifest)
        for a,b in [('train','inner_validation'),('train','outer_holdout'),('inner_validation','outer_holdout')]:
            assert groups[a].isdisjoint(groups[b])
    protocol = dict(name=NAME, date='2026-10-21', classes=CLASSES, images=5937, folds=5,
        parent_model_architectures=['efficientnet_b0','convnext_tiny','resnet50'], newly_trained_models=0,
        code_sha256=sha(Path(__file__)), source_sha256=sources,
        fixed_weight=.25, candidates=[REFERENCE,FIXED,ADAPTIVE],
        decision_rule='Reference argmax SkinCancer mask is unchanged. Lock protected reference-class predictions and prohibit other rows entering protected classes. On remaining rows choose largest 75% reference +25% original ResNet score among unprotected labels.',
        adaptive_rule='Start protected={SkinCancer}; add all labels violating non-focus recall>=reference-.02 or Lupus/Psoriasis/Tinea precision>=reference-.02 on inner validation; repeat until no new labels, at most8 evaluations. No weight/threshold grid.',
        guard='Inner validation Accuracy and MacroF1 cannot decline; exact reference SkinCancer recall AND precision; nonfocus recall loss<=.02; focus precision loss<=.02.',
        selection='Within passing candidates maximize MacroF1, then Accuracy, prefer original on exact tie. Save all5 selections before reading outer prediction arrays.',
        probabilities='Hard hierarchical decisions only. Raw component probabilities are retained separately; no final confidence, calibration or Top3 claim.',
        limitations=['Exploratory follow-up informed by already-studied OOF scores and weaknesses; not a fresh independent test or clinical validation.',
            'Existing inner validation was used by parent checkpoints; layer selection is not fully nested retraining.',
            'Holding the entire SkinCancer mask preserves its existing false positives and false negatives as well as recall/precision.',
            'Class-specific validation locks can overfit; one seed and incomplete patient IDs. Known scene/case groups only.',
            'No new images, labels, checkpoint training or API deployment. Original Word report and benchmark remain intact.'])
    write(OUT / 'protocol.json', protocol)
    write(OUT / 'status.json', dict(state='registered', images=5937, serving_changed=False))
    return protocol


def verify_frozen(protocol):
    assert sha(Path(__file__)) == protocol['code_sha256'], 'Frozen evaluator changed'
    for relative, expected in protocol['source_sha256'].items():
        assert sha(ROOT / relative) == expected, relative


def validation_arrays(fold):
    with np.load(fold_dir(fold)/'validation_predictions.npz', allow_pickle=False) as archive:
        paths = archive['paths'].tolist()
        truth = archive['truth'].astype(int)
        reference, resnet = archive[REFERENCE].copy(), archive['resnet50'].copy()
        parents = .0 + archive['efficientnet_b0']
        convnext = archive['convnext_tiny'].copy()
    previous = read(CV/'protocol.json')
    assert paths == previous['folds'][fold]['roles']['inner_validation']
    manifest = {row['path']:row for row in read(MANIFEST)['images']}
    assert truth.tolist() == [CLASSES.index(manifest[path]['class']) for path in paths]
    assert all(manifest[path]['fold'] != fold for path in paths)
    weights = np.asarray(read(fold_dir(fold)/'selection_locked.json')['reference_weights'])
    reproduced = (1-weights)*parents + weights*convnext
    reproduced /= reproduced.sum(axis=1, keepdims=True)
    assert np.allclose(reproduced, reference, rtol=0, atol=1e-12)
    check_probabilities(reference, resnet)
    return paths, truth, reference, resnet


def paired_accuracy_interval(rows, predictions, baseline, truth):
    _, inverse = np.unique([row['group'] for row in rows], return_inverse=True)
    sizes = np.bincount(inverse)
    differences = np.bincount(inverse, weights=(predictions==truth).astype(int)-(baseline==truth).astype(int))
    rng = np.random.default_rng(20261021)
    values = []
    for _ in range(2000):
        sample = rng.integers(0, len(sizes), size=len(sizes))
        values.append(float(differences[sample].sum()/sizes[sample].sum()))
    return np.quantile(values, [.025,.975]).tolist()


def evaluate(protocol):
    assert not (OUT/'results.json').exists(), 'Preserve completed experiment'
    selections = {}
    for fold in range(5):
        paths, truth, reference, resnet = validation_arrays(fold)
        selection = select(reference, resnet, truth)
        selection.update(fold=fold, protocol_sha256=sha(OUT/'protocol.json'), images=len(paths),
                         validation_paths_sha256=hashlib.sha256('\n'.join(paths).encode()).hexdigest())
        lock = OUT/f'fold_{fold}'/'selection_locked.json'
        if lock.exists():
            assert read(lock) == selection
        else:
            write(lock, selection)
        selections[fold] = selection
        print(json.dumps(dict(fold=fold, selected=selection['selected'], protected=selection['trials'][ADAPTIVE]['spec']['protected'])), flush=True)
    # One boundary record freezes every fold before any new outer-array load.
    locks = {str(fold):sha(OUT/f'fold_{fold}'/'selection_locked.json') for fold in range(5)}
    boundary = dict(protocol_sha256=sha(OUT/'protocol.json'), selections_sha256=locks,
                    outer_array_evaluation_started=False, scope='These outer data have been studied in prior experiments.')
    write(OUT/'all_selections_locked.json', boundary)
    write(OUT/'status.json', dict(state='evaluating_locked_outer', serving_changed=False))
    manifest = {row['path']:row for row in read(MANIFEST)['images']}
    rows = []
    for fold in range(5):
        old = read(fold_dir(fold)/'test_predictions.json')
        assert {row['path'] for row in old} == {path for path,item in manifest.items() if item['fold']==fold}
        reference = np.array([row['probabilities'][REFERENCE] for row in old])
        resnet = np.array([row['probabilities']['resnet50'] for row in old])
        decisions = {name:decide(reference,resnet,item['spec']['protected']) for name,item in selections[fold]['trials'].items()}
        decisions[SELECTED] = decisions[selections[fold]['selected']]
        for i, old_row in enumerate(old):
            source = manifest[old_row['path']]
            assert (old_row['sha256'],old_row['label'],old_row['group']) == (source['sha256'],source['class'],source['scene_or_case_group'])
            rows.append(dict(path=old_row['path'],sha256=source['sha256'],label=source['class'],group=source['scene_or_case_group'],fold=fold,
                source='SCIN' if old_row['path'].startswith('SkinDisease/scin-v1/') else 'original_train',
                raw_component_probabilities={REFERENCE:reference[i].tolist(),'resnet50':resnet[i].tolist()},
                predictions={name:int(pred[i]) for name,pred in decisions.items()}))
    rows.sort(key=lambda row:row['path'])
    assert len(rows)==len({row['path'] for row in rows})==5937
    truth = np.array([CLASSES.index(row['label']) for row in rows])
    methods = {}
    for name in [REFERENCE,FIXED,ADAPTIVE,SELECTED]:
        predicted = np.array([row['predictions'][name] for row in rows])
        methods[name] = metrics(predicted,truth)
        base_pred = np.array([row['predictions'][REFERENCE] for row in rows])
        assert np.array_equal(predicted==CANCER,base_pred==CANCER)
        methods[name]['paired_accuracy_delta_95pct'] = paired_accuracy_interval(rows,predicted,base_pred,truth)
        methods[name]['per_source'] = {}
        for source in ['original_train','SCIN']:
            matching = np.array([row['source']==source for row in rows])
            methods[name]['per_source'][source] = dict(images=int(matching.sum()),**metrics(predicted[matching],truth[matching]))
    old = read(BENCHMARK)['methods']['classwise_inner_fitted']
    for key in ['accuracy','macro_f1','confusion_matrix']:
        if isinstance(old[key],list): assert old[key]==methods[REFERENCE][key]
        else: assert abs(old[key]-methods[REFERENCE][key])<1e-12
    per_fold = []
    for fold in range(5):
        subset = [row for row in rows if row['fold']==fold]
        y = np.array([CLASSES.index(row['label']) for row in subset])
        per_fold.append(dict(fold=fold,images=len(subset),selected=selections[fold]['selected'],methods={name:metrics(np.array([row['predictions'][name] for row in subset]),y) for name in methods}))
    result = dict(status='complete_exploratory_cancer_locked_decision_fusion',classes=CLASSES,images=5937,
        protocol_sha256=sha(OUT/'protocol.json'),methods=methods,per_fold=per_fold,
        all_fold_selections_locked_sha256=sha(OUT/'all_selections_locked.json'),
        limitations=protocol['limitations'],newly_trained_models=0,serving_changed=False)
    write(OUT/'oof_decisions.json',rows)
    write(OUT/'results.json',result)
    verify_frozen(protocol)
    assert {str(fold):sha(OUT/f'fold_{fold}'/'selection_locked.json') for fold in range(5)} == locks
    write(OUT/'verification.json',dict(status='PASS',scope='Technical consistency, not independent clinical validation',
        results_sha256=sha(OUT/'results.json'),images=5937,cancer_decision_masks_identical=True,
        all_folds_locked_before_outer_evaluation=True,original_benchmark_reproduced=True,sources_unchanged=True,serving_changed=False))
    write(OUT/'status.json',dict(state='complete',images=5937,results_path=(OUT/'results.json').relative_to(ROOT).as_posix(),serving_changed=False))
    print(json.dumps({name:{key:score[key] for key in ['accuracy','macro_f1']} for name,score in methods.items()}),flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-only',action='store_true')
    args = parser.parse_args()
    protocol = prepare()
    if not args.prepare_only:
        evaluate(protocol)


if __name__=='__main__':
    main()
