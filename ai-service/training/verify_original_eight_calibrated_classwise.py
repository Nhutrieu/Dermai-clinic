"""Independently reconstruct grouped calibration/fusion outputs and selection."""
import json
import numpy as np
from sklearn.metrics import confusion_matrix

from common import CLASSES, save_json, sha256_file
import pilot_original_eight_calibrated_classwise as experiment


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def independently_predict(a, b, params):
    qs = []
    for p, t in zip((a, b), params['temperatures']):
        # Power normalization, separate from experiment log-softmax implementation.
        q = np.maximum(p, 1e-12) ** (1 / t)
        qs.append(q / q.sum(1, keepdims=True))
    def mix(x, z, w):
        p = x * (1 - np.asarray(w)) + z * np.asarray(w)
        return p / np.sum(p, axis=1, keepdims=True)
    return dict(old_classwise=a, fixed25=mix(a, b, .25), calibrated25=mix(*qs, .25),
                calibrated_classwise=mix(*qs, params['adapter_weights']))


def verify_metrics(p, y, m):
    cm = confusion_matrix(y, np.argmax(p, 1), labels=np.arange(8))
    assert cm.tolist() == m['confusion_matrix']
    tp = cm.diagonal(); support = cm.sum(1); predicted = cm.sum(0)
    recall = np.divide(tp, support, out=np.zeros(8, dtype=float), where=support > 0)
    precision = np.divide(tp, predicted, out=np.zeros(8, dtype=float), where=predicted > 0)
    f1 = np.divide(2 * tp, support + predicted, out=np.zeros(8, dtype=float), where=(support + predicted) > 0)
    assert abs(float(tp.sum() / len(y)) - m['accuracy']) < 1e-12
    assert abs(float(f1.mean()) - m['macro_f1']) < 1e-12
    for k, c in enumerate(CLASSES):
        assert m['per_class'][c]['support'] == int(support[k])
        for key, expected in [('recall', recall[k]), ('precision', precision[k]), ('f1', f1[k])]:
            assert abs(m['per_class'][c][key] - expected) < 1e-12


def main():
    root, out = experiment.ROOT, experiment.OUT
    protocol = read(out / 'protocol.json'); lock = read(out / 'selection_locked.json'); results = read(out / 'results.json')
    assert protocol['classes'] == CLASSES and protocol['configuration'] == experiment.CONFIG
    for path, digest in protocol['sources'].items(): assert sha256_file(root / path) == digest, path
    for name, digest in protocol['code_sha256'].items(): assert sha256_file(root / 'ai-service/training' / name) == digest, name
    assert lock['protocol_sha256'] == results['protocol_sha256'] == sha256_file(out / 'protocol.json')
    assert results['selection_sha256'] == sha256_file(out / 'selection_locked.json')
    source_protocol = read(experiment.SOURCE / 'protocol.json')
    assert protocol['splits'] == source_protocol['splits']
    allrows = protocol['validation_rows']; folds = np.asarray(protocol['calibration_folds'])
    groups = np.asarray([r['group'] for r in allrows]); sources = np.asarray(protocol['validation_sources'])
    y = np.asarray([CLASSES.index(r['label']) for r in allrows])
    validation = [experiment.load(s, protocol) for s in experiment.previous.SPLITS[:2]]
    a, b = [np.concatenate([z[k] for z in validation]) for k in range(2)]
    expected = {n: np.empty_like(a) for n in experiment.METHODS}; covered = np.zeros(len(y), dtype=int)
    for plan, saved in zip(protocol['crossfit_plan'], lock['crossfit_parameters']):
        tr, va = np.asarray(plan['fit_indices']), np.asarray(plan['evaluate_indices'])
        assert saved['fold'] == plan['fold'] and np.all(folds[va] == plan['fold'])
        assert set(tr).isdisjoint(va) and set(tr) | set(va) == set(range(len(y)))
        assert set(groups[tr]).isdisjoint(groups[va]); covered[va] += 1
        # Refit exclusively on declared fit indices, not assessment labels.
        params = experiment.fit(a[tr], b[tr], y[tr], sources[tr])
        assert np.allclose(params['temperatures'], saved['parameters']['temperatures'], atol=1e-10, rtol=0)
        assert np.allclose(params['adapter_weights'], saved['parameters']['adapter_weights'], atol=1e-10, rtol=0)
        for n, p in independently_predict(a[va], b[va], params).items(): expected[n][va] = p
    assert np.all(covered == 1)
    params = experiment.fit(a, b, y, sources)
    assert params == lock['final_parameters'] and lock['fitting_images'] == 931
    assert lock['fitting_roles'] == list(experiment.previous.SPLITS[:2])
    trials = {t['name']: t for t in lock['trials']}
    for t in trials.values(): assert t['eligible'] == bool(experiment.previous.eligible(t, trials['old_classwise']))
    selected = sorted([t for t in trials.values() if t['eligible']], key=experiment.previous.rank)[0]['name']
    assert selected == lock['selected'] == results['selected']
    predictions = read(out / 'predictions.json'); offset = 0
    for si, split in enumerate(experiment.previous.SPLITS):
        rr = protocol['splits'][split]
        aa, bb, yy = experiment.load(split, protocol)
        pp = ({n: p[sources == si] for n, p in expected.items()} if si < 2 else independently_predict(aa, bb, params))
        pp['validation_selected'] = pp[selected]
        with np.load(out / (split + '.npz')) as z:
            assert z['paths'].tolist() == [r['path'] for r in rr] and np.array_equal(z['truth'], yy)
            for n, p in pp.items():
                assert np.isfinite(z[n]).all() and (z[n] >= 0).all() and np.allclose(z[n].sum(1), 1, atol=1e-12)
                assert np.allclose(z[n], p, atol=1e-12, rtol=0)
                verify_metrics(z[n], yy, results['results'][split][n])
                if si < 2: assert results['results'][split][n] == trials[selected if n == 'validation_selected' else n][split]
        for i, r in enumerate(rr):
            row = predictions[offset + i]
            for k, v in r.items(): assert row[k] == v
            assert row['split'] == split
            for n, p in pp.items(): assert np.allclose(row['probabilities'][n], p[i], atol=1e-12, rtol=0)
        offset += len(rr)
        assert (out / 'protocol.json').stat().st_mtime_ns <= (out / 'selection_locked.json').stat().st_mtime_ns <= (out / (split + '.npz')).stat().st_mtime_ns
    assert offset == len(predictions)
    # Audit fit objective and constraints without calling the fitting loss.
    for param in [s['parameters'] for s in lock['crossfit_parameters']] + [params]:
        assert all(.5 <= t <= 5 for t in param['temperatures'])
        assert all(0 <= w <= .75 for w in param['adapter_weights'])
        assert param['weight_fit']['success'] and param['weight_fit']['objective'] <= param['weight_fit']['initial_objective'] + 1e-8
    save_json(out / 'verification.json', dict(status='PASS', protocol_sha256=sha256_file(out / 'protocol.json'),
        results_sha256=sha256_file(out / 'results.json'), selected=selected, validation_images=931,
        disjoint_combination_fit_groups=True, independently_reconstructed_probabilities=True,
        independently_recomputed_confusion_f1_recall=True, serving_unchanged=True,
        scope='Verifies implementation/provenance, not independent clinical accuracy or unbiased checkpoint validation.'))
    print(json.dumps(read(out / 'verification.json')), flush=True)


if __name__ == '__main__': main()
