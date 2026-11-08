"""Audited five-label scope trial on the original, fixed development folds.

This module never alters the original eight-label code, data, checkpoints or API.
Removed diagnoses are out-of-scope stress examples, not relabeled training data.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score

from common import CLASSES as EIGHT, ImageSample, save_json, sha256_file
from evaluate_evidence import calibration_metrics

ROOT = Path(__file__).resolve().parents[2]
NAME = 'five_disease_scope_trial_seed42_20261019'
OUT = ROOT / 'ai-service/reports' / NAME
MODELS = ROOT / 'ai-service/candidates' / NAME
OUTER = ROOT / 'ai-service/reports/scene_grouped_oof_folds_seed42.json'
INNER = ROOT / 'ai-service/reports/scene_grouped_oof_inner_seed42.json'
BENCHMARK = ROOT / 'ai-service/reports/scene_grouped_oof_classwise_fusion_seed42.json'
FIVE = ['Acne', 'Candidiasis', 'Eczema', 'SkinCancer', 'Warts']
REMOVED = ['Lupus', 'Psoriasis', 'Tinea']
RECIPES = {
    'efficientnet_b0': dict(batch_size=32, learning_rate=.0002, backbone_lr_ratio=.25,
        weight_decay=.0002, label_smoothing=.05, effective_number_beta=.999,
        ema_decay=.995, patience=7),
    'convnext_tiny': dict(batch_size=16, learning_rate=.0003, backbone_lr_ratio=.1,
        weight_decay=.01, label_smoothing=.1, effective_number_beta=.9999,
        ema_decay=.5, patience=6),
}
OLD_DIRECTORIES = {'efficientnet_b0': 'oof_b0_fold{fold}_seed42',
                   'convnext_tiny': 'oof_convnext_fold{fold}_seed42'}
THRESHOLDS = [.5, .55, .6, .7, .8, .9, .95]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def relative(path):
    return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()


def source_name(row):
    return 'SCIN' if row['path'].replace('\\','/').startswith('SkinDisease/scin-v1/') else 'original_train'


def normalized(probabilities):
    a = np.asarray(probabilities, dtype=np.float64)
    if a.ndim != 2 or not np.isfinite(a).all() or (a < 0).any() or (a.sum(1) <= 0).any():
        raise ValueError('Invalid probability array')
    return a / a.sum(1, keepdims=True)


def restrict_eight(probabilities):
    a = normalized(probabilities)
    if a.shape[1] != len(EIGHT):
        raise ValueError('Expected eight probabilities')
    return normalized(a[:, [EIGHT.index(c) for c in FIVE]])


def classwise_weights(b0, convnext, truth, classes=FIVE):
    b0, convnext = normalized(b0), normalized(convnext)
    y = np.asarray(truth, dtype=int)
    if b0.shape != convnext.shape or b0.shape != (len(y), len(classes)):
        raise ValueError('Inner validation shape mismatch')
    a, b = b0.argmax(1) == y, convnext.argmax(1) == y
    w = np.full(len(classes), .5); detail = {}
    for i, name in enumerate(classes):
        mask = y == i; support = int(mask.sum())
        if support == 0:
            raise ValueError(f'Missing validation class: {name}')
        a_only, b_only = int((mask & a & ~b).sum()), int((mask & b & ~a).sum())
        threshold = max(3, math.ceil(.05 * support)); advantage = b_only - a_only
        w[i] = .75 if advantage >= threshold else (.25 if advantage <= -threshold else .5)
        detail[name] = dict(inner_support=support, b0_only_correct=a_only,
            convnext_only_correct=b_only, threshold=threshold, convnext_weight=float(w[i]))
    return w, detail


def blend(b0, convnext, weights):
    a, b = normalized(b0), normalized(convnext); w = np.asarray(weights)
    if a.shape != b.shape or w.shape != (a.shape[1],) or not np.isfinite(w).all() or ((w < 0) | (w > 1)).any():
        raise ValueError('Invalid classwise fusion')
    return normalized((1-w) * a + w * b)


def metrics(probabilities, truth, output_classes=FIVE):
    a = normalized(probabilities); labels = np.asarray(truth)
    if a.shape != (len(labels), len(output_classes)) or not set(labels).issubset(FIVE):
        raise ValueError('Metrics must use the common five-disease cohort')
    predicted = np.asarray(output_classes)[a.argmax(1)]
    report = classification_report(labels, predicted, labels=FIVE,
        output_dict=True, zero_division=0)
    matrix = np.zeros((len(FIVE), len(output_classes)), dtype=int)
    for t, p in zip(labels, predicted):
        matrix[FIVE.index(t), output_classes.index(p)] += 1
    y = np.asarray([output_classes.index(c) for c in labels])
    calibration = calibration_metrics(a, y)
    present = [c for c in FIVE if c in set(labels)]
    return dict(images=len(labels), accuracy=float(accuracy_score(labels, predicted)),
        macro_f1=float(np.mean([report[c]['f1-score'] for c in present])),
        macro_recall=float(np.mean([report[c]['recall'] for c in present])),
        macro_classes=present, absent_target_classes=[c for c in FIVE if c not in present],
        top3_accuracy=float((np.argsort(-a, axis=1)[:, :3] == y[:, None]).any(1).mean()),
        per_class={c:dict(support=int(report[c]['support']), precision=float(report[c]['precision']),
            recall=float(report[c]['recall']), f1=float(report[c]['f1-score'])) for c in FIVE},
        confusion_matrix=matrix.tolist(), confusion_rows=FIVE, confusion_columns=output_classes,
        calibration={k:calibration[k] for k in ('expected_calibration_error',
            'negative_log_likelihood', 'multiclass_brier_score', 'mean_confidence')})


def out_of_scope(probabilities, truth, id_probabilities, id_truth):
    a, known = normalized(probabilities), normalized(id_probabilities)
    labels = np.asarray(truth)
    if a.shape[1] != 5 or not set(labels).issubset(REMOVED):
        raise ValueError('Unexpected out-of-scope labels')
    confidence = a.max(1); known_confidence = known.max(1)
    prediction = np.asarray(FIVE)[a.argmax(1)]
    known_correct = np.asarray(FIVE)[known.argmax(1)] == np.asarray(id_truth)
    by_class = {}
    for c in REMOVED:
        mask = labels == c
        by_class[c] = dict(images=int(mask.sum()), mean_max_softmax=float(confidence[mask].mean()),
            forced_predictions={p:int((prediction[mask] == p).sum()) for p in FIVE},
            accepted_at_preset_thresholds={str(t):int((confidence[mask] >= t).sum()) for t in THRESHOLDS})
    curves = []
    for t in THRESHOLDS:
        accept = known_confidence >= t
        curves.append(dict(threshold=t, known_coverage=float(accept.mean()),
            known_accepted=int(accept.sum()),
            known_accuracy_when_accepted=float(known_correct[accept].mean()) if accept.any() else None,
            out_of_scope_false_accept_rate=float((confidence >= t).mean())))
    auc = roc_auc_score(np.r_[np.zeros(len(known)), np.ones(len(a))],
                        1-np.r_[known_confidence, confidence])
    return dict(images=len(labels), scope='Known three removed diagnoses, development stress test; not novel independent OOD validation.',
        by_class=by_class, threshold_curves=curves, ood_auroc_using_one_minus_max_softmax=float(auc),
        threshold_selection='All thresholds fixed in protocol, no test-best threshold selected; softmax confidence is not a validated rejection gate.')


def roles_for_fold(rows, inner, fold):
    inner_paths = set(inner['folds'][fold]['inner_validation_paths'])
    roles = dict(train=[], inner_validation=[], outer_holdout=[], out_of_scope=[])
    for row in rows:
        if row['class'] in REMOVED:
            if row['fold'] == fold: roles['out_of_scope'].append(row)
        else:
            role = 'outer_holdout' if row['fold'] == fold else ('inner_validation' if row['path'] in inner_paths else 'train')
            roles[role].append(row)
    groups = {r:{x['scene_or_case_group'] for x in items} for r,items in roles.items()}
    for a in groups:
        for b in groups:
            if a != b and groups[a] & groups[b]: raise ValueError(f'Group crosses roles {fold}: {a}/{b}')
    for role in ('train', 'inner_validation', 'outer_holdout'):
        if set(x['class'] for x in roles[role]) != set(FIVE):
            raise ValueError(f'Missing class in {fold}/{role}')
    return roles


def samples(rows):
    return [ImageSample((ROOT/x['path']).resolve(), FIVE.index(x['class']) if x['class'] in FIVE else -1,
                        x['sha256'], x['scene_or_case_group']) for x in rows]


def old_directory(architecture, fold):
    return ROOT / 'ai-service/candidates' / OLD_DIRECTORIES[architecture].format(fold=fold)


def old_probabilities(architecture, fold, role, paths, outer):
    directory = old_directory(architecture, fold)
    payload = read(directory / ('inner_predictions.json' if role == 'inner_validation' else 'oof_predictions.json'))
    if payload['classes'] != EIGHT or payload['outer_fold'] != fold or payload['architecture'] != architecture:
        raise ValueError('Old prediction identity changed')
    if payload['outer_manifest_sha256'] != outer['manifest_sha256']:
        raise ValueError('Old prediction manifest changed')
    if payload['checkpoint_sha256'] != sha256_file(directory/'best_model.pth'):
        raise ValueError('Old prediction checkpoint changed')
    if role == 'inner_validation' and payload['inner_plan_sha256'] != sha256_file(INNER):
        raise ValueError('Old inner-validation manifest changed')
    by_path = {r['path']:r for r in payload['rows']}
    source = {r['path']:r for r in outer['images']}
    for p in paths:
        if by_path[p]['sha256'] != source[p]['sha256'] or by_path[p]['class'] != source[p]['class']:
            raise ValueError('Old prediction row changed')
    a = normalized([by_path[p]['probabilities'] for p in paths])
    if a.shape != (len(paths), 8): raise ValueError('Old probability shape changed')
    return a


def prepare():
    outer, inner = read(OUTER), read(INNER)
    rows = outer['images']
    canonical = ''.join(f"{x['fold']}\t{x['class']}\t{x['path']}\t{x['sha256']}\t{x['scene_or_case_group']}\n" for x in rows)
    if hashlib.sha256(canonical.encode()).hexdigest() != outer['manifest_sha256'] or inner['outer_manifest_sha256'] != outer['manifest_sha256']:
        raise ValueError('Original fold checksum mismatch')
    if len(rows) != 5937 or len({x['path'] for x in rows}) != 5937:
        raise ValueError('Unexpected original cohort')
    if set(FIVE) | set(REMOVED) != set(EIGHT) or set(FIVE) & set(REMOVED):
        raise ValueError('Class map is incomplete')
    for row in rows:
        p = (ROOT/row['path']).resolve()
        if not p.is_relative_to(ROOT.resolve()) or sha256_file(p) != row['sha256']:
            raise ValueError(f"Missing or changed source image: {row['path']}")
    folds = []
    for f in range(5):
        roles = roles_for_fold(rows, inner, f)
        folds.append(dict(fold=f, roles={r:[x['path'] for x in items] for r,items in roles.items()},
            counts={r:dict(Counter(x['class'] for x in items)) for r,items in roles.items()}))
    inputs = {relative(p):sha256_file(p) for p in (OUTER, INNER, BENCHMARK, ROOT/'ai-service/models/best_model.pth')}
    for arch in RECIPES:
        for f in range(5):
            for n in ('best_model.pth', 'inner_predictions.json', 'oof_predictions.json', 'selection_report.json'):
                p = old_directory(arch,f)/n; inputs[relative(p)] = sha256_file(p)
    import torch
    cache = Path(torch.hub.get_dir())/'checkpoints'
    names = {'efficientnet_b0':'efficientnet_b0_rwightman-7f5810bc.pth', 'convnext_tiny':'convnext_tiny-983f1562.pth'}
    pretrained = {a:dict(path=str(cache/n),sha256=sha256_file(cache/n)) for a,n in names.items()}
    code_names = ['five_disease_scope_trial.py','run_five_disease_scope_trial.py','train_v2.py','common.py','evaluate_evidence.py']
    code = {n:sha256_file(ROOT/'ai-service/training'/n) for n in code_names}
    protocol = dict(name=NAME, registered_date='2026-10-19', classes=FIVE, removed_classes=REMOVED,
        in_scope_images=sum(x['class'] in FIVE for x in rows), removed_images=sum(x['class'] in REMOVED for x in rows),
        original_classes=EIGHT, by_class=dict(Counter(x['class'] for x in rows)), folds=folds,
        outer_manifest_content_sha256=outer['manifest_sha256'], sources_sha256=inputs, code_sha256=code,
        initialization='Fresh torchvision ImageNet weights for every architecture/fold. No old skin-trained backbone or removed-disease images used in five-label training.',
        pretrained=pretrained, recipes=RECIPES, seed=42, epochs=24, freeze_epochs=2,
        workers=0, torch_threads=4, amp=True,
        checkpoint_selection='Inner-validation macro F1, then top3 accuracy, then lower loss; raw/epoch-EMA chosen only on inner validation.',
        training_recipe='Same architecture-specific original-eight v2 transforms/optimizer/freeze/loss/EMA recipes, filtered to five classes. Not a compute-matched training-budget study.',
        primary_method='five_classwise_inner_fitted',
        fusion_rule='Per class, ConvNeXt weight .75/.25 for advantage of at least max(3,ceil(.05*inner_support)); otherwise .5. Weights locked before outer inference.',
        comparison=['old_eight_b0_full_decision','old_eight_convnext_full_decision','old_eight_classwise_full_decision',
                    'old_eight_classwise_restricted_to_five','five_b0','five_convnext','five_equal','five_classwise_inner_fitted'],
        comparison_population='Exact same 3736 original grouped outer images with true labels in FIVE; eight-class predictions outside FIVE count as errors in full-decision baselines.',
        removed_image_policy='Only original outer fold rows of three removed diseases, never training/inner validation or threshold fitting; report forced five-class assignments and preset rejection curves.',
        preset_confidence_thresholds=THRESHOLDS, bootstrap=dict(unit='known_case_or_scene', repetitions=1000, seed=42),
        limitations=['Previously studied development images/results; scope chosen after viewing weak classes, so this is exploratory and not independent confirmation.',
            'Historical grouping does not establish independence for unknown patient identities.',
            'Five-label performance cannot be compared directly with the overall eight-label 5937-image accuracy.',
            'SCIN lacks SkinCancer; source/class sample counts must accompany all metrics.',
            'Max-softmax is an uncalibrated diagnostic for rejection, not a validated unknown-disease detector.',
            'No serving/API change; original-eight benchmark and all original data/checkpoints retained.'])
    if protocol['in_scope_images'] != 3736 or protocol['removed_images'] != 2201: raise ValueError('Unexpected scope sizes')
    destination = OUT/'protocol.json'
    if destination.exists():
        if read(destination) != protocol: raise ValueError('Frozen trial protocol/source/code changed; inspect before continuing')
    else: save_json(destination, protocol)
    return outer, inner, protocol
