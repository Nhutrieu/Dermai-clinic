"""Group-cross-fitted calibration/classwise fusion of frozen original-eight models.

All combination fitting uses the two validation roles only. These roles previously
selected parent checkpoints, so this is exploratory combination validation, not
nested model validation or a new independent test. Never retrain image models.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from sklearn.model_selection import StratifiedGroupKFold

from common import CLASSES, save_json, sha256_file
from evaluate_scene_grouped_oof_ensemble import score
import pilot_original_eight_supplement_adaptation as previous

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'ai-service/reports/original_eight_ensemble_teacher_pilot_fold0_seed42'
OUT = ROOT / 'ai-service/reports/original_eight_calibrated_classwise_fold0_seed42'
METHODS = ('old_classwise', 'fixed25', 'calibrated25', 'calibrated_classwise')
CONFIG = dict(seed=42, folds=3, temperature_bounds=[.5, 5.],
              adapter_weight_bounds=[0., .75], initial_adapter_weight=.25,
              weight_regularization=.1, source_mass=[.5, .5],
              optimizer_maxiter=300, epsilon=1e-12)


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def load(split, protocol):
    rr = protocol['splits'][split]
    with np.load(SOURCE / (split + '.npz')) as z:
        assert z['paths'].tolist() == [r['path'] for r in rr]
        y = np.asarray([CLASSES.index(r['label']) for r in rr])
        assert np.array_equal(z['truth'], y)
        # The CE-only supplemented control is fixed before this experiment.
        # No branch or weight choice uses held-role outcomes.
        a, b = z['old_classwise'].astype(float), z['control_resnet'].astype(float)
    for p in (a, b):
        assert p.shape == (len(y), 8) and np.isfinite(p).all() and (p >= 0).all()
        assert np.allclose(p.sum(1), 1, atol=1e-6)
    return a, b, y


def source_weights(sources):
    assert set(sources.tolist()) == {0, 1}
    return np.asarray([.5 / np.count_nonzero(sources == s) for s in sources])


def scale(p, temperature):
    z = np.log(np.maximum(p, CONFIG['epsilon'])) / temperature
    z -= z.max(1, keepdims=True)
    q = np.exp(z)
    return q / q.sum(1, keepdims=True)


def blend(a, b, weights):
    p = (1 - np.asarray(weights)) * a + np.asarray(weights) * b
    return p / p.sum(1, keepdims=True)


def nll(p, y, mass):
    return float(-np.sum(mass * np.log(np.maximum(p[np.arange(len(y)), y], CONFIG['epsilon']))))


def fit(a, b, y, sources):
    mass = source_weights(sources)
    temperatures = []
    temperatures_audit = []
    for p in (a, b):
        opt = minimize_scalar(lambda t: nll(scale(p, t), y, mass),
                              bounds=CONFIG['temperature_bounds'], method='bounded',
                              options={'maxiter': CONFIG['optimizer_maxiter'], 'xatol': 1e-8})
        assert opt.success and np.isfinite(opt.fun)
        temperatures.append(float(opt.x))
        temperatures_audit.append(dict(success=bool(opt.success), nfev=int(opt.nfev),
                                       uncalibrated_nll=nll(p, y, mass), calibrated_nll=float(opt.fun)))
    aa, bb = scale(a, temperatures[0]), scale(b, temperatures[1])
    def loss(w):
        return nll(blend(aa, bb, w), y, mass) + CONFIG['weight_regularization'] * float(np.mean((w - .25) ** 2))
    opt = minimize(loss, np.full(8, .25), method='L-BFGS-B',
                   bounds=[CONFIG['adapter_weight_bounds']] * 8,
                   options={'maxiter': CONFIG['optimizer_maxiter'], 'ftol': 1e-12, 'gtol': 1e-7})
    assert opt.success and np.isfinite(opt.fun)
    return dict(temperatures=temperatures, adapter_weights=opt.x.tolist(),
                temperature_fit=temperatures_audit,
                weight_fit=dict(success=bool(opt.success), iterations=int(opt.nit),
                    nfev=int(opt.nfev), objective=float(opt.fun),
                    initial_objective=loss(np.full(8, .25)),
                    gradient_inf_norm=float(np.max(np.abs(opt.jac)))))


def predict(a, b, params):
    aa, bb = scale(a, params['temperatures'][0]), scale(b, params['temperatures'][1])
    return dict(old_classwise=a, fixed25=blend(a, b, .25),
                calibrated25=blend(aa, bb, .25),
                calibrated_classwise=blend(aa, bb, params['adapter_weights']))


def register():
    state = read(ROOT / 'ai-service/reports/active_research_track.json')
    assert state['active_track'] == 'original_eight' and state['classes'] == CLASSES
    source = read(SOURCE / 'protocol.json')
    assert read(SOURCE / 'verification.json')['status'] == 'PASS'
    rr = []; sources = []
    for i, split in enumerate(previous.SPLITS[:2]):
        rr.extend(dict(**r, split=split) for r in source['splits'][split])
        sources.extend([i] * len(source['splits'][split]))
    groups = np.asarray([r['group'] for r in rr])
    strata = np.asarray([str(s) + ':' + r['label'] for s, r in zip(sources, rr)])
    folds = np.full(len(rr), -1)
    plan = []
    splitter = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42)
    for f, (tr, va) in enumerate(splitter.split(np.zeros(len(rr)), strata, groups)):
        assert set(groups[tr]).isdisjoint(groups[va])
        assert set(np.asarray(sources)[tr]) == {0, 1}
        folds[va] = f
        plan.append(dict(fold=f, fit_indices=tr.tolist(), evaluate_indices=va.tolist()))
    assert (folds >= 0).all() and len(set(r['path'] for r in rr)) == len(rr)
    paths = [SOURCE / 'protocol.json', SOURCE / 'selection_locked.json', SOURCE / 'verification.json']
    paths += [SOURCE / (s + '.npz') for s in previous.SPLITS]
    paths += [ROOT / 'ai-service/models/best_model.pth',
              ROOT / 'ai-service/reports/scene_grouped_oof_classwise_fusion_seed42.json']
    code = [Path(__file__), Path(previous.__file__),
            ROOT / 'ai-service/training/evaluate_scene_grouped_oof_ensemble.py',
            ROOT / 'ai-service/training/pilot_original_eight_resnet50.py',
            ROOT / 'ai-service/training/common.py',
            ROOT / 'ai-service/training/verify_original_eight_calibrated_classwise.py']
    p = dict(classes=CLASSES, configuration=CONFIG, methods=METHODS, validation_rows=rr,
        validation_sources=sources, calibration_folds=folds.tolist(), crossfit_plan=plan,
        splits=source['splits'],
        sources={x.relative_to(ROOT).as_posix(): sha256_file(x) for x in paths},
        code_sha256={x.name: sha256_file(x) for x in code},
        component='Frozen old-fold0 B0/ConvNeXt reference and CE-only supplemented ResNet (ensemble-teacher control). Distill branch is diagnostic only, never candidate.',
        fitting='Per-component scalar temperature [.5,5] minimizes equal-source NLL; then eight classwise convex weights [0,.75] minimize equal-source NLL plus .1 mean((weight-.25)^2), one initialization .25. Three grouped crossfits; no held-role fitting or hyperparameter grid.',
        selection='Score cross-fitted predictions separately on718original and213clinical validation photos; apply unchanged dual guard/rank. Reference fallback. Lock method and final parameters fitted on all931validation images before opening any held-role probability arrays.',
        limits=['Combination crossfitting does not undo parent checkpoint selection on the original validation role.',
                'One previously investigated fold and sources. All later held-role results descriptive and previously inspected, not new independent evidence.',
                'Fixed two source masses; no source detector or true-label-dependent routing at inference.',
                'Eight classwise weights concern the supplemented ResNet versus the existing two-model reference; three architectures total.',
                'No model retraining, new-eight inputs, serving changes or replacement of5937benchmark.'],
        reference='Guo et al., ICML2017, https://arxiv.org/abs/1706.04599 ; temperature scaling reference, classwise fusion is project-specific.')
    assert not (OUT / 'protocol.json').exists(), 'Preserve registered protocol'
    save_json(OUT / 'protocol.json', p)
    return p


def diagnosis(protocol):
    out = {}
    for split in previous.SPLITS[:2]:
        with np.load(SOURCE / (split + '.npz')) as z:
            y = z['truth']; ref = z['old_classwise']; a = ref.argmax(1)
            out[split] = {}
            for name in ('control_resnet', 'distill_resnet'):
                p = z[name]; h = p.argmax(1); mixed = blend(ref, p, .25).argmax(1)
                per_class = {}
                for k, c in enumerate(CLASSES):
                    m = y == k
                    per_class[c] = dict(support=int(m.sum()), reference_correct=int(((a == y) & m).sum()),
                        adapter_correct=int(((h == y) & m).sum()), mixed_correct=int(((mixed == y) & m).sum()),
                        unique_correct=int(((a != y) & (h == y) & m).sum()),
                        mean_true_class_probability=float(p[m, k].mean()))
                out[split][name] = dict(adapter_correct=int((h == y).sum()),
                    unique_correct=int(((a != y) & (h == y)).sum()),
                    rescued=int(((a != y) & (mixed == y)).sum()),
                    harmed=int(((a == y) & (mixed != y)).sum()),
                    metrics=score(p, y), per_class=per_class)
    save_json(OUT / 'validation_diagnosis.json', dict(protocol_sha256=sha256_file(OUT / 'protocol.json'),
        results=out, interpretation='Validation shows lower adapter confidence and fewer unique corrections after KD. Raw accuracy alone does not establish stronger fusion; fixed25fusion underuses clinical Candidiasis/Tinea. This observation motivates calibration/classwise fusion, not a causal proof of training drift.'))


def evaluate(protocol):
    original = [load(s, protocol) for s in previous.SPLITS[:2]]
    a, b, y = [np.concatenate([z[k] for z in original]) for k in range(3)]
    sources = np.asarray(protocol['validation_sources'])
    cross = {n: np.empty_like(a) for n in METHODS}; fits = []
    for plan in protocol['crossfit_plan']:
        tr, va = np.asarray(plan['fit_indices']), np.asarray(plan['evaluate_indices'])
        parameters = fit(a[tr], b[tr], y[tr], sources[tr])
        fits.append(dict(fold=plan['fold'], parameters=parameters))
        for n, p in predict(a[va], b[va], parameters).items(): cross[n][va] = p
    trials = {n: dict(name=n) for n in METHODS}
    results = {}; payloads = []
    for s, split in enumerate(previous.SPLITS[:2]):
        mask = sources == s
        for n in METHODS: trials[n][split] = score(cross[n][mask], y[mask])
    for t in trials.values(): t['eligible'] = bool(previous.eligible(t, trials['old_classwise']))
    selected = sorted([t for t in trials.values() if t['eligible']], key=previous.rank)[0]['name']
    final = fit(a, b, y, sources)
    lock = dict(protocol_sha256=sha256_file(OUT / 'protocol.json'), selected=selected,
                trials=list(trials.values()), crossfit_parameters=fits, final_parameters=final,
                fitting_images=len(y), fitting_roles=list(previous.SPLITS[:2]))
    save_json(OUT / 'selection_locked.json', lock)
    for s, split in enumerate(previous.SPLITS[:2]):
        mask = sources == s; values = {n: p[mask] for n, p in cross.items()}
        values['validation_selected'] = values[selected]
        results[split] = {n: score(p, y[mask]) for n, p in values.items()}
        np.savez_compressed(OUT / (split + '.npz'), paths=[r['path'] for r in protocol['splits'][split]],
                            truth=y[mask], **values)
        payloads.extend(dict(**r, split=split, probabilities={n: p[i].tolist() for n, p in values.items()})
                        for i, r in enumerate(protocol['splits'][split]))
    # The lock exists before any held-role probabilities are loaded.
    for split in previous.SPLITS[2:]:
        aa, bb, yy = load(split, protocol); values = predict(aa, bb, final)
        values['validation_selected'] = values[selected]
        results[split] = {n: score(p, yy) for n, p in values.items()}
        np.savez_compressed(OUT / (split + '.npz'), paths=[r['path'] for r in protocol['splits'][split]], truth=yy, **values)
        payloads.extend(dict(**r, split=split, probabilities={n: p[i].tolist() for n, p in values.items()})
                        for i, r in enumerate(protocol['splits'][split]))
    save_json(OUT / 'predictions.json', payloads)
    save_json(OUT / 'results.json', dict(protocol_sha256=sha256_file(OUT / 'protocol.json'),
        selection_sha256=sha256_file(OUT / 'selection_locked.json'), selected=selected, results=results,
        scope='Onefold exploratory combination crossfit; parent validation reused; previously inspected held roles, no independent confirmation.'))
    print(json.dumps(dict(selected=selected, weights=final['adapter_weights'], temperatures=final['temperatures'],
        results={s: {n: {k: v[k] for k in ('accuracy', 'macro_f1')} for n, v in rr.items()} for s, rr in results.items()})), flush=True)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--prepare-only', action='store_true'); args = parser.parse_args()
    protocol = register(); diagnosis(protocol)
    if args.prepare_only: print('Registered; validation diagnosis saved.'); return
    evaluate(protocol)


if __name__ == '__main__': main()
