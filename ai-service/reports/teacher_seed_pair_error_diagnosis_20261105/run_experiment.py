"""293: frozen-cache seed-pair error diagnosis; no new predictions selected or models fit."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
REPORTS = OUT.parent
LATEST = REPORTS / 'teacher_classbalanced_seed43_repeat_20261105'
CB42 = REPORTS / 'teacher_classbalanced_eight_20261105'
BASE = REPORTS / 'teacher_fine_eight_oof_hierarchy_20261104'
OLD = REPORTS / 'teacher_lupus_consensus_addon_20261105'
CLASSES = ['Acne', 'Candidiasis', 'Eczema', 'Lupus', 'Psoriasis', 'SkinCancer', 'Tinea', 'Warts']
MAP = np.array([3, 4, 6, 0, 2, 1, 5, 7])
INV = np.argsort(MAP)
WEAK = [3, 4, 6]
MODEL_NAMES = ['parent288', 'ce42', 'cb42', 'ce43', 'cb43', 'confirmed42', 'confirmed43']
STAGES = ['weak_change', 'CE_CB_disagreement', 'Cancer_and_positive_margin',
          'margin_gain_above_ln2', 'only_Lupus', 'CNN6_confirmation']
ENDPOINTS = ['accuracy', 'macro_f1'] + [CLASSES[c] + '_' + k for c in WEAK for k in ['precision', 'recall', 'f1']] + ['SkinCancer_recall']
PAIRS = [('CB_minus_CE_seed42', 2, 1), ('CB_minus_CE_seed43', 4, 3),
         ('confirmed42_minus_parent288', 5, 0), ('confirmed43_minus_parent288', 6, 0)]
REASONS = ['CB_not_correct', 'CE_CB_agree_on_correct_label', 'Cancer_parent_protected',
           'new_margin_not_positive', 'margin_gain_not_above_ln2', 'only_Lupus_policy',
           'CNN6_rejects_Lupus', 'accepted_correct']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    with np.load(path, allow_pickle=False) as a:
        return dict(a)


def status(state, **extra):
    obj = dict(state=state, pid=os.getpid(), updated_utc=utc(),
               report=OUT.relative_to(ROOT).as_posix(), selected=None, query_evaluated=False, **extra)
    write(OUT / 'status.json', obj)
    write(REPORTS / 'source_aware_training_status.json', obj)


def funnel(parent, ce, cb, six):
    """Truth-free, weak-destination funnel; last mask reproduces fixed 290 addon."""
    parent = np.asarray(parent)
    ce, cb, six = np.asarray(ce, float), np.asarray(cb, float), np.asarray(six, float)
    n = len(parent)
    if parent.shape != (n,) or not n or not np.issubdtype(parent.dtype, np.integer) or not np.isin(parent, range(8)).all():
        raise ValueError('Canonical nonempty parent labels required')
    if ce.shape != (n, 8) or cb.shape != ce.shape or six.shape != (n, 6) or not all(np.isfinite(x).all() for x in [ce, cb, six]):
        raise ValueError('Aligned finite logits required')
    ca = cb.argmax(1)
    candidate, natural = MAP[ca], MAP[ce.argmax(1)]
    ix, old = np.arange(n), INV[parent]
    new_margin = cb[ix, ca] - cb[ix, old]
    old_margin = ce[ix, ca] - ce[ix, old]
    m0 = (candidate != parent) & np.isin(candidate, WEAK)
    m1 = m0 & (candidate != natural)
    m2 = m1 & (parent != 5) & (new_margin > 0)
    m3 = m2 & ((new_margin - old_margin) > np.log(2.))
    m4 = m3 & (candidate == 3) & (parent != 3)
    m5 = m4 & (six[:, 0] > six[:, 1:].max(1))
    masks = np.stack([m0, m1, m2, m3, m4, m5], axis=1)
    assert not np.any(masks[:, 1:] & ~masks[:, :-1])
    pred = np.where(m5, 3, parent)
    assert np.array_equal(pred == 5, parent == 5)
    return candidate, natural, masks, new_margin, new_margin - old_margin, pred


def reason(truth, parent, candidate, natural, new_margin, gain, mask):
    """Post-lock explanation ONLY, never a routing function."""
    if candidate != truth:
        return REASONS[0]
    if candidate == natural:
        return REASONS[1]
    if parent == 5:
        return REASONS[2]
    if new_margin <= 0:
        return REASONS[3]
    if gain <= np.log(2.):
        return REASONS[4]
    if candidate != 3:
        return REASONS[5]
    if not mask[-1]:
        return REASONS[6]
    return REASONS[7]


def metric_vector(cm):
    cm = np.asarray(cm, float)
    d, row, col = np.diag(cm), cm.sum(1), cm.sum(0)
    precision = np.divide(d, col, out=np.zeros(8), where=col > 0)
    recall = np.divide(d, row, out=np.zeros(8), where=row > 0)
    f1 = np.divide(2 * d, row + col, out=np.zeros(8), where=row + col > 0)
    return np.array([d.sum() / cm.sum(), f1.mean()] + [v[c] for c in WEAK for v in [precision, recall, f1]] + [recall[5]])


def row_weights(draw, inverse, groups):
    draw, inverse = np.asarray(draw), np.asarray(inverse)
    if draw.ndim != 1 or len(draw) != groups or not np.isin(draw, range(groups)).all():
        raise ValueError('Exactly G sampled group IDs required')
    return np.bincount(draw, minlength=groups)[inverse]


def prepare():
    assert not (OUT / 'protocol.json').exists(), 'Preserve293 protocol'
    p, c, v = [read(LATEST / n) for n in ['protocol.json', 'completion.json', 'independent_review.json']]
    assert c['visual_qa']['status'] == v['status'] == c['final_integrity_check']['status'] == 'PASS'
    assert not c['directional_repeat_across42and43'] and not c['query_evaluated']
    frozen = dict(p['frozen_sha256'])
    for name, digest in c['artifacts_sha256'].items():
        frozen[(LATEST / name).relative_to(ROOT).as_posix()] = digest
    for f in [LATEST / 'completion.json', ROOT / c['final_integrity_check']['script'], Path(__file__),
              OUT / 'unit_checks.json', ROOT / 'ai-service/tests/test_seed_pair_error_diagnosis.py',
              ROOT / 'tmp/review_seed_pair_error_diagnosis_20261105.py', ROOT / 'tmp/finish_seed_pair_error_diagnosis_20261105.py']:
        frozen[f.relative_to(ROOT).as_posix()] = sha(f)
    q = {k: p[k] for k in ['classes', 'fit_rows', 'query_rows', 'roles', 'meta_splits', 'image_manifest']}
    q.update(registered_utc=utc(), frozen_sha256=frozen, diagnostic_only=True,
             analysis='After292 failed seed repeat, decompose errors for ALL three weak labels. No threshold/ensemble/seed selection or new model/prediction promotion. Reconstruct cached native heldgroup CE42/CB42/CE43/CB43 and CNN6. Funnel weak destinations through unchanged290 gates and reproduce290/292 labels exactly. Attribute each baseline weak false negative to first failed condition; labels used only for descriptive counts after frozen routing.',
             oracle='For each baseline weak FN, check whether ANY top1 of CE42,CB42,CE43,CB43,or nativeCNN6 is correct. CNN6 only maps its first3 outputs to LP/Pso/Tin; no mapping OtherRest to eight diseases. Oracle uses true labels, is NOT a selectable ensemble, score estimate, feasible gain, specialist or clinical guarantee. Correlated samearchitecture models are not independent experts.',
             bootstrap='2000 paired group draws, seed29342, sorted unique group IDs; each draw rng.integers(0,G,size=G,dtype=int64), image multiplicity equals sampled group multiplicity. Same draw for all7 fixed predictors; preserve all images within each drawn group. Recompute8x8confusion and12 endpoints, report percentile2.5/97.5 with numpylinear quantiles for CB-CE42/43,confirmed42/43-parent, and difference of CB effects. No pvalue, multiple-testing claim, admission or seed-population uncertainty. Fixed adaptive historical predictions, no retraining within bootstrap; not nested CV or new validation.',
             scope='Same2699historical adaptive ownfit with2407available groups andfixed3folds; NOT testblind/newpatients/global5937/API. Only1SCINLP, no newimages/doctorlabels. Group IDs are available image/case clusters, not verified independent patient identifiers. Sources/query1332/otherownpools/validation not newly evaluated. Two optimization seeds with fixed288/CNN6 cannot establish fullpipeline stability.',
             model_names=MODEL_NAMES, stages=STAGES, endpoints=ENDPOINTS, pairs=[list(x) for x in PAIRS], reasons=REASONS,
             bootstrap_draws=2000, bootstrap_seed=29342, CNN_fits=0, CNN_updates=0, fusion_fits=0,
             new_oof_image_forwards=0, new_query_image_forwards=0, selected=None,
             promotion_eligible=False, query_evaluated=False, serving_changed=False,
             research_registry_changed=False, global_5937_score_changed=False, all_three_evaluated=False)
    for rel, digest in frozen.items():
        assert sha(ROOT / rel) == digest, rel
    write(OUT / 'protocol.json', q)
    status('seed_pair_diagnosis293_registered')
    return q


def reconstruct(p):
    a, b, old, base = [load(d / f) for d, f in [(LATEST, 'predictions.npz'), (CB42, 'predictions.npz'), (OLD, 'predictions.npz'), (BASE, 'oof_predictions.npz')]]
    paths = [r['path'] for r in p['fit_rows']]
    for x in [a, b, old, base]:
        assert x['paths'].tolist() == paths
        np.testing.assert_array_equal(x['truth'], a['truth'])
        np.testing.assert_array_equal(x['fold_ids'], a['fold_ids'])
    pairs = [(b['natural8_logits'], b['balanced8_logits']), (a['ce43_logits'], a['cb43_logits'])]
    pred = np.stack([a['current288'], MAP[pairs[0][0].argmax(1)], MAP[pairs[0][1].argmax(1)],
                     MAP[pairs[1][0].argmax(1)], MAP[pairs[1][1].argmax(1)],
                     old['cnn6_confirmed_lupus_addon'], a['seed43_confirmed_addon']], axis=1)
    arrays = dict(paths=a['paths'], truth=a['truth'], fold_ids=a['fold_ids'], predictions=pred, six_logits=base['six_logits'])
    for seed, (ce, cb) in zip([42, 43], pairs):
        cand, natural, masks, margin, gain, final = funnel(pred[:, 0], ce, cb, base['six_logits'])
        np.testing.assert_array_equal(final, pred[:, 5 if seed == 42 else 6])
        identity = funnel(pred[:, 0], ce, ce, base['six_logits'])[-1]
        np.testing.assert_array_equal(identity, pred[:, 0])
        arrays.update({f'candidate{seed}': cand, f'natural{seed}': natural, f'masks{seed}': masks,
                       f'margin{seed}': margin, f'gain{seed}': gain, f'ce_logits{seed}': ce, f'cb_logits{seed}': cb})
    groups, inverse = np.unique([r['group'] for r in p['fit_rows']], return_inverse=True)
    assert len(groups) == 2407 and len(paths) == 2699
    arrays.update(groups=groups, group_inverse=inverse)
    np.savez_compressed(OUT / 'analysis_inputs.npz', **arrays)
    write(OUT / 'analysis_inputs_locked.json', dict(locked_utc=utc(), protocol_sha256=sha(OUT / 'protocol.json'),
          labels_used_for_routing=False, new_predictions_selected=False, metrics_started=False,
          artifacts_sha256={(OUT / 'analysis_inputs.npz').relative_to(ROOT).as_posix(): sha(OUT / 'analysis_inputs.npz')}))


def analyze(p):
    a = load(OUT / 'analysis_inputs.npz')
    truth, pred, parent, n = a['truth'], a['predictions'], a['predictions'][:, 0], len(a['truth'])
    point = np.stack([metric_vector(np.bincount(truth * 8 + x, minlength=64).reshape(8, 8)) for x in pred.T])
    six_top = a['six_logits'].argmax(1)
    correct = (pred[:, 1:5] == truth[:, None])
    all_correct = np.column_stack([correct, (six_top < 3) & (np.array([3, 4, 6, -1, -1, -1])[six_top] == truth)])
    coverage, funnels, cases = {}, {}, []
    for c in WEAK:
        ix = (truth == c) & (parent != c)
        by_source = {}
        for source in sorted({r['source'] for r in p['fit_rows']}):
            sr = np.array([r['source'] == source for r in p['fit_rows']]); z = ix & sr
            by_source[source] = dict(errors=int(z.sum()), any_top1_correct=int((z & all_correct.any(1)).sum()), none_top1_correct=int((z & ~all_correct.any(1)).sum()))
        coverage[CLASSES[c]] = dict(support=int((truth == c).sum()), parent_correct=int(((truth == c) & (parent == c)).sum()),
              parent_errors=int(ix.sum()), any_top1_correct=int((ix & all_correct.any(1)).sum()), none_top1_correct=int((ix & ~all_correct.any(1)).sum()),
              per_expert_correct={name: int((ix & all_correct[:, j]).sum()) for j, name in enumerate(['ce42', 'cb42', 'ce43', 'cb43', 'CNN6'])},
              both_CB_correct=int((ix & correct[:, 1] & correct[:, 3]).sum()),
              either_CB_correct=int((ix & (correct[:, 1] | correct[:, 3])).sum()), by_source=by_source)
    for seed in [42, 43]:
        cand, masks = a[f'candidate{seed}'], a[f'masks{seed}']
        stages = {}
        for j, name in enumerate(STAGES):
            m = masks[:, j]
            stages[name] = dict(proposals=int(m.sum()), repairs=int((m & (cand == truth) & (parent != truth)).sum()),
                 harms=int((m & (cand != truth) & (parent == truth)).sum()), neutral=int((m & (cand != truth) & (parent != truth)).sum()),
                 repairs_by_class={CLASSES[c]: int((m & (cand == c) & (truth == c) & (parent != c)).sum()) for c in WEAK})
        reasons = {CLASSES[c]: {key: 0 for key in REASONS} for c in WEAK}
        for i in np.flatnonzero(np.isin(truth, WEAK) & (parent != truth)):
            key = reason(int(truth[i]), int(parent[i]), int(cand[i]), int(a[f'natural{seed}'][i]), float(a[f'margin{seed}'][i]), float(a[f'gain{seed}'][i]), masks[i])
            reasons[CLASSES[int(truth[i])]][key] += 1
        funnels[str(seed)] = dict(stages=stages, first_failure_by_class=reasons)
    for i in np.flatnonzero(np.isin(truth, WEAK) & (parent != truth)):
        row = p['fit_rows'][i]
        cases.append(dict(index=int(i), path=row['path'], group=row['group'], source=row['source'], dataset_label=CLASSES[int(truth[i])],
              parent_label=CLASSES[int(parent[i])], top1_correct_experts=[name for j, name in enumerate(['ce42', 'cb42', 'ce43', 'cb43', 'CNN6']) if all_correct[i, j]],
              reasons={str(seed): reason(int(truth[i]), int(parent[i]), int(a[f'candidate{seed}'][i]), int(a[f'natural{seed}'][i]), float(a[f'margin{seed}'][i]), float(a[f'gain{seed}'][i]), a[f'masks{seed}'][i]) for seed in [42, 43]}))
    rng, g = np.random.default_rng(p['bootstrap_seed']), len(a['groups'])
    boot = np.zeros((p['bootstrap_draws'], len(MODEL_NAMES), len(ENDPOINTS)))
    sample_sha = hashlib.sha256()
    for b in range(p['bootstrap_draws']):
        draw = rng.integers(0, g, size=g, dtype=np.int64); sample_sha.update(draw.astype('<i8').tobytes())
        w = row_weights(draw, a['group_inverse'], g)
        for j in range(len(MODEL_NAMES)):
            boot[b, j] = metric_vector(np.bincount(truth * 8 + pred[:, j], weights=w, minlength=64).reshape(8, 8))
    comparisons = {}
    for name, new, old in PAIRS:
        delta = boot[:, new] - boot[:, old]; ci = np.quantile(delta, [.025, .975], axis=0, method='linear')
        comparisons[name] = {key: dict(point=float(point[new, j] - point[old, j]), lower=float(ci[0, j]), upper=float(ci[1, j])) for j, key in enumerate(ENDPOINTS)}
    diff = (boot[:, 4] - boot[:, 3]) - (boot[:, 2] - boot[:, 1]); ci = np.quantile(diff, [.025, .975], axis=0, method='linear')
    comparisons['CB_effect43_minus_effect42'] = {key: dict(point=float((point[4, j] - point[3, j]) - (point[2, j] - point[1, j])), lower=float(ci[0, j]), upper=float(ci[1, j])) for j, key in enumerate(ENDPOINTS)}
    np.savez_compressed(OUT / 'bootstrap_metrics.npz', point=point, bootstrap=boot)
    write(OUT / 'error_cases.json', dict(labels_used_only_for_explanation=True, cases=cases))
    results = dict(completed_utc=utc(), protocol_sha256=sha(OUT / 'protocol.json'), rows=n, groups=g,
                   model_metrics={name: dict(zip(ENDPOINTS, point[j].tolist())) for j, name in enumerate(MODEL_NAMES)},
                   coverage=coverage, funnels=funnels, comparisons=comparisons,
                   bootstrap_draws=p['bootstrap_draws'], bootstrap_group_draws_sha256=sample_sha.hexdigest(),
                   weak_error_cases=len(cases), diagnostic_only=True, oracle_is_not_ensemble=True,
                   labels_used_for_routing=False, new_predictions_selected=False,
                   **{k: p[k] for k in ['CNN_fits', 'CNN_updates', 'fusion_fits', 'new_oof_image_forwards', 'new_query_image_forwards',
                        'selected', 'promotion_eligible', 'query_evaluated', 'serving_changed', 'research_registry_changed', 'global_5937_score_changed', 'all_three_evaluated']})
    write(OUT / 'results.json', results)
    for rel, digest in p['frozen_sha256'].items():
        assert sha(ROOT / rel) == digest, rel
    status('seed_pair_diagnosis293_awaiting_review')
    print(dict(coverage=coverage, weak_error_cases=len(cases), selected=None), flush=True)


if __name__ == '__main__':
    protocol = prepare()
    reconstruct(protocol)
    analyze(protocol)
