"""Independent NumPy head/fusion reconstruction, labels, metrics and guard audit."""
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.special import expit, softmax
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support

from common import CLASSES, save_json, sha256_file
import pilot_original_eight_frozen_cancer_head as pilot


def guard(a, c, refa, refc, pm, refpm):
    failures = []
    if a['macro_f1'] < refa['macro_f1'] - 1e-12: failures.append('original_macro_f1')
    if a['accuracy'] < refa['accuracy'] - .005 - 1e-12: failures.append('original_accuracy')
    if a['per_class']['SkinCancer']['recall'] < refa['per_class']['SkinCancer']['recall'] - 1e-12: failures.append('original_skin_recall')
    for name in CLASSES:
        if name not in ('Lupus', 'Psoriasis') and a['per_class'][name]['recall'] < refa['per_class'][name]['recall'] - .02 - 1e-12:
            failures.append('original_recall_' + name)
    for name in ('Lupus', 'Psoriasis'):
        if a['per_class'][name]['precision'] < refa['per_class'][name]['precision'] - .02 - 1e-12:
            failures.append('original_precision_' + name)
    if c['macro_f1'] < refc['macro_f1'] - 1e-12: failures.append('clinical_macro_f1')
    if c['per_class']['SkinCancer']['recall'] < refc['per_class']['SkinCancer']['recall'] - 1e-12: failures.append('clinical_skin_recall')
    targets = ('Candidiasis', 'Lupus', 'Tinea')
    if sum(c['per_class'][n]['recall'] for n in targets) < sum(refc['per_class'][n]['recall'] for n in targets) - 1e-12:
        failures.append('clinical_target_mean_recall')
    if pm['non_cancer_flag_rate'] > refpm['non_cancer_flag_rate'] + 1e-12: failures.append('pad_other_flags')
    for name in ('BCC', 'SCC', 'MEL'):
        if pm['by_diagnosis'][name]['flag_rate'] < refpm['by_diagnosis'][name]['flag_rate'] - 1e-12:
            failures.append('pad_recall_' + name)
    return failures


def main():
    p = pilot.read(pilot.OUT / 'protocol.json'); pilot.check_frozen(p)
    result = pilot.read(pilot.OUT / 'results.json'); lock = pilot.read(pilot.OUT / 'selection_locked.json')
    assert result['protocol_sha256'] == lock['protocol_sha256'] == sha256_file(pilot.OUT / 'protocol.json')
    assert result['selection_sha256'] == sha256_file(pilot.OUT / 'selection_locked.json')
    rr = p['train']; assert len(rr) == 1169 and all(r['training_eligible'] for r in rr)
    assert {r['source_patient_id'] for r in rr}.isdisjoint(r['patient'] for r in p['pad_validation'])
    for group in [rr, p['pad_validation'], *p['splits'].values()]:
        for r in group: assert sha256_file(pilot.ROOT / r['path']) == r['sha256']
    with np.load(pilot.OUT / 'train_features.npz') as z:
        assert z['paths'].tolist() == [r['path'] for r in rr]
        w = z['sample_weights']; x = z['features'].astype(float)
    counts = Counter((r['source_label'], r['source_patient_id']) for r in rr)
    patients = {d: len({r['source_patient_id'] for r in rr if r['source_label'] == d}) for d in pilot.DIAGNOSES}
    expected = np.array([len(rr) * .5 / (3 if r['source_label'] in pilot.DIAGNOSES[:3] else 2) /
                         patients[r['source_label']] / counts[r['source_label'], r['source_patient_id']] for r in rr])
    assert np.allclose(w, expected, atol=1e-12)
    heads = {}
    for b in pilot.BRANCHES:
        assert lock['checkpoints'][b] == sha256_file(pilot.MODELS / (b + '.npz'))
        with np.load(pilot.MODELS / (b + '.npz')) as z: heads[b] = {k: z[k].copy() for k in z.files}
        h = heads[b]
        assert np.allclose(h['mean'], np.average(x, axis=0, weights=w), atol=1e-9)
        variance = np.average((x-h['mean'])**2, axis=0, weights=w)
        expected_scale = np.sqrt(variance); expected_scale[expected_scale == 0] = 1
        assert np.allclose(h['scale'], expected_scale, atol=1e-8)
    assert np.array_equal(heads['binary']['mean'], heads['subtype']['mean'])
    maxima = {}; methods = ('old_classwise', 'binary_cancer25', 'subtype_cancer25')
    for split in [*pilot.pad.prior.SPLITS, 'pad_validation']:
        rows = p['pad_validation'] if split == 'pad_validation' else p['splits'][split]
        with np.load(pilot.OUT / (split + '.npz')) as z:
            assert z['paths'].tolist() == [r['path'] for r in rows]
            ref = z['old_classwise']; feat = z['features'].astype(float)
            for b in pilot.BRANCHES:
                h = heads[b]; logits = ((feat-h['mean'])/h['scale']) @ h['coefficients'].T + h['intercept']
                c = expit(logits[:, 0]) if b == 'binary' else softmax(logits, axis=1)[:, :3].sum(1)
                delta = float(np.abs(c-z[b+'_cancer']).max()); assert delta < 1e-6
                maxima[split + '/' + b] = delta
                q = np.empty_like(ref, dtype=float); q[:, 5] = .75 * ref[:, 5] + .25 * c
                keep = [0,1,2,3,4,6,7]
                q[:, keep] = ref[:, keep] / (1-ref[:, 5])[:, None] * (1-q[:, 5])[:, None]
                assert np.allclose(q, z[b+'_cancer25'], atol=1e-6)
                assert np.allclose(q.sum(1), 1, atol=1e-6) and (q >= 0).all()
                assert np.array_equal(q[:,keep].argmax(1), ref[:,keep].argmax(1))
            for name in methods:
                q = z[name]; pred = q.argmax(1)
                if split != 'pad_validation':
                    y = np.array([CLASSES.index(r['label']) for r in rows]); assert np.array_equal(y,z['truth'])
                    m = result['results'][split][name]
                    assert abs(accuracy_score(y,pred)-m['accuracy']) < 1e-12
                    assert abs(f1_score(y,pred,labels=np.arange(8),average='macro',zero_division=0)-m['macro_f1']) < 1e-12
                    assert np.array_equal(confusion_matrix(y,pred,labels=np.arange(8)),m['confusion_matrix'])
                    prec, rec, f1, support = precision_recall_fscore_support(y,pred,labels=np.arange(8),zero_division=0)
                    for k,cname in enumerate(CLASSES):
                        for field,value in [('precision',prec[k]),('recall',rec[k]),('f1',f1[k]),('support',support[k])]:
                            assert abs(m['per_class'][cname][field]-value) < 1e-12
                else:
                    m = result['pad_validation'][name]
                    for d in ('BCC','SCC','MEL','ACK','NEV','SEK'):
                        mask = np.array([r['diagnostic']==d for r in rows]); flagged = int(((pred==5)&mask).sum())
                        assert flagged == m['by_diagnosis'][d]['flagged']
    # Re-extract an actual full batch, independently confirm hook does not change logits.
    f = pilot.Features(p); sample = p['splits']['original_validation'][:16]; xcheck, raw = f.infer(sample)
    with np.load(pilot.OUT / 'original_validation.npz') as z:
        assert np.allclose(xcheck,z['features'][:16],atol=1e-6,rtol=1e-6)
        assert np.allclose(raw,z['original_resnet'][:16],atol=1e-7)
    failures = {}; trials = lock['trials']
    for name,t in trials.items():
        ref = trials['old_classwise']
        failures[name] = guard(t['original_validation'],t['dermacon_validation'],ref['original_validation'],ref['dermacon_validation'],
                               result['pad_validation'][name],result['pad_validation']['old_classwise'])
        assert bool(t['eligible']) == (not failures[name])
    candidates = [t for t in trials.values() if not failures[t['name']]]
    assert sorted(candidates,key=pilot.pad.prior.rank)[0]['name'] == lock['selected'] == result['selected']
    verification = dict(status='PASS', protocol_sha256=sha256_file(pilot.OUT/'protocol.json'),
        results_sha256=sha256_file(pilot.OUT/'results.json'), verifier_sha256=sha256_file(Path(__file__)),
        train_rows=len(rr), feature_dimension=2048, shared_scaler_and_weights=True,
        independent_head_probability_max_errors=maxima, actual_batch_reinference=True,
        unchanged_other_class_order=True, all_source_and_checkpoint_hashes_verified=True,
        guard_failures=failures, selected=lock['selected'], scope='Implementation and exploratory metrics verification; no clinical certification or new test.')
    save_json(pilot.OUT/'verification.json',verification)
    print(json.dumps(verification),flush=True)


if __name__ == '__main__': main()
