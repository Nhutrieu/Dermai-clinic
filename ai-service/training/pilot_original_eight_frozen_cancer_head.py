"""Registered frozen ResNet binary/subtype heads; fixed cancer-mass fusion."""
import argparse
import json
import warnings
from collections import Counter

import numpy as np
import torch
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader

from common import CLASSES, ImageSample, ImageSampleDataset, build_model, evaluation_transform, save_json, sha256_file
from evaluate_scene_grouped_oof_ensemble import score
import pilot_original_eight_pad_addition as pad
import prepare_original_eight_pad_joint as joint

ROOT = pad.ROOT
OUT = ROOT / 'ai-service/reports/original_eight_frozen_cancer_head_fold0_seed42'
MODELS = ROOT / 'ai-service/candidates/original_eight_frozen_cancer_head_fold0_seed42'
BASE = ROOT / 'ai-service/reports/original_eight_negative_supervision_pilot_fold0_seed42_fp32'
DIAGNOSES = ('BCC', 'SCC', 'MEL', 'NEV', 'SEK')
BRANCHES = ('binary', 'subtype')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def weights(rows):
    counts = Counter((r['source_label'], r['source_patient_id']) for r in rows)
    patients = {d: {r['source_patient_id'] for r in rows if r['source_label'] == d} for d in DIAGNOSES}
    return np.array([(.5 / (3 if r['source_label'] in DIAGNOSES[:3] else 2)) /
                     len(patients[r['source_label']]) / counts[r['source_label'], r['source_patient_id']]
                    for r in rows], dtype=float) * len(rows)


def register():
    assert not (OUT / 'protocol.json').exists(), 'Preserve registered experiment'
    b = read(BASE / 'protocol.json')
    assert read(BASE / 'verification.json')['status'] == 'PASS'
    assert read(joint.OUT / 'verification.json')['status'] == 'PASS'
    rows = [json.loads(line) for file in ('positive_train.jsonl', 'negative_train.jsonl')
            for line in (joint.OUT / file).read_text(encoding='utf-8').splitlines()]
    assert len(rows) == 1169 and all(r['training_eligible'] for r in rows)
    assert {r['source_patient_id'] for r in rows}.isdisjoint(r['patient'] for r in b['pad_validation'])
    for rr in [rows, b['pad_validation'], *b['splits'].values()]:
        for r in rr:
            assert sha256_file(ROOT / r['path']) == r['sha256'], r['path']
    frozen = dict(b['sources'])
    for path in [BASE / 'protocol.json', BASE / 'verification.json',
                 joint.OUT / 'positive_train.jsonl', joint.OUT / 'negative_train.jsonl',
                 ROOT / 'ai-service/candidates/pad_cancer_probe_pilot.json',
                 ROOT / 'ai-service/candidates/pad_milk_multisource_probe.json']:
        frozen[path.relative_to(ROOT).as_posix()] = sha256_file(path)
    code = set(b['code_sha256']) | {'pilot_original_eight_frozen_cancer_head.py',
        'verify_original_eight_frozen_cancer_head.py', 'evaluate_scene_grouped_oof_classwise_fusion.py'}
    p = dict(classes=CLASSES, auxiliary_classes=DIAGNOSES, train=rows, splits=b['splits'],
        pad_validation=b['pad_validation'], sources=frozen,
        code_sha256={n: sha256_file(ROOT / 'ai-service/training' / n) for n in sorted(code)},
        initial_checkpoint=pad.prior.INITIAL.relative_to(ROOT).as_posix(),
        configuration=dict(seed=42, C=.001, solver='lbfgs', max_iter=3000, tol=1e-7,
                           feature_batch_size=16, feature_dimension=2048, cancer_mass_weight=.25),
        training='Frozen original fold0 ResNet raw epoch17, eval/FP32/no gradients. Shared train-only weighted scaler and identical rows/weights. Binary labels cancer/noncancer versus five subtype labels. Both coarse cancer/benign total weight .5; subtype then patient then photo balanced within each coarse group. Fixed C, no grid/calibration/threshold search.',
        fusion='c=.75*reference[:,5]+.25*auxiliary_cancer; other seven columns scaled by (1-c)/(1-reference[:,5]). Preserve relative odds among other classes; their argmax can still change against SkinCancer. Standalone flag uses fixed .5, not a diagnostic probability.',
        selection='Reuse original/DC validation guards plus PAD each BCC/SCC/MEL recall >=reference and ACK/NEV/SEK aggregate flag rate <=reference. Reference fallback. Rank eligible candidates using prior dual-validation rule. Lock selection/checkpoint hashes before held-role inference.',
        prior_review='Old frozen B0 binary head lost melanoma recall; PAD+MILK four-class head improved cancer flags but retained benign false flags. This changes backbone, audited train cohort, shared patient/subtype weights, five-class target and cancer-only fusion. It does not isolate backbone effect from all historical differences.',
        limits=['One previously explored fold/seed; all evaluation sources previously inspected. Selection is exploratory, no new independent test.',
                'NEV/SEK outside original eight labels, never assigned eight-way training diagnosis. ACK audit only.',
                'Published negative labels not all biopsy-confirmed; MEL validation only seven images.',
                'Frozen backbone had already used original validation for checkpoint selection.',
                'Separate PAD head may confuse other original diseases absent its training cohort. Scores are not calibrated clinical risk.',
                'No change to full 5937 OOF benchmark, original checkpoint, serving or class taxonomy.'])
    save_json(OUT / 'protocol.json', p)
    return p


def check_frozen(p):
    for path, h in p['sources'].items():
        assert sha256_file(ROOT / path) == h, path
    for name, h in p['code_sha256'].items():
        assert sha256_file(ROOT / 'ai-service/training' / name) == h, name


class Features:
    def __init__(self, p):
        self.path = ROOT / p['initial_checkpoint']
        self.before = sha256_file(self.path)
        cp = torch.load(self.path, map_location='cpu', weights_only=False)
        self.model = build_model('resnet50', 8, pretrained=False)
        self.model.load_state_dict(cp['model_state_dict'])
        self.model.cuda().eval().requires_grad_(False)
        self.slot = []
        self.hook = self.model.avgpool.register_forward_hook(lambda m, x, y: self.slot.append(y.flatten(1)))

    def infer(self, rows):
        # Dataset label here is a dummy loader target only, never used in fitting.
        samples = [ImageSample(ROOT / r['path'], 0, r['sha256'], r['group']) for r in rows]
        loader = DataLoader(ImageSampleDataset(samples, evaluation_transform()), batch_size=16,
                            shuffle=False, num_workers=2, pin_memory=True)
        xx, pp = [], []
        with torch.inference_mode():
            for x, _ in loader:
                logits = self.model(x.cuda(non_blocking=True))
                f = self.slot.pop()
                reconstructed = self.model.fc(f)
                assert torch.equal(logits, reconstructed)
                xx.append(f.cpu().numpy()); pp.append(logits.softmax(1).cpu().numpy())
        assert not self.slot and sha256_file(self.path) == self.before
        return np.concatenate(xx), np.concatenate(pp)


def fit(p, extractor):
    assert not MODELS.exists(), 'Preserve head outputs'
    MODELS.mkdir(parents=True)
    x, original = extractor.infer(p['train']); w = weights(p['train'])
    scaler = StandardScaler().fit(x, sample_weight=w)
    z = scaler.transform(x)
    np.savez_compressed(OUT / 'train_features.npz', paths=[r['path'] for r in p['train']],
                        features=x, original_resnet=original, sample_weights=w)
    heads = {}; history = {}
    for b in BRANCHES:
        y = np.array([int(r['source_label'] in DIAGNOSES[:3]) if b == 'binary'
                      else DIAGNOSES.index(r['source_label']) for r in p['train']])
        with warnings.catch_warnings():
            warnings.simplefilter('error', ConvergenceWarning)
            head = LogisticRegression(C=.001, solver='lbfgs', max_iter=3000, tol=1e-7, random_state=42).fit(z, y, sample_weight=w)
        heads[b] = (scaler, head)
        np.savez_compressed(MODELS / (b + '.npz'), mean=scaler.mean_, scale=scaler.scale_,
                            coefficients=head.coef_, intercept=head.intercept_, classes=head.classes_)
        history[b] = dict(iterations=head.n_iter_.tolist(), convergence_warning=False,
                         training_accuracy=float(np.mean(head.predict(z) == y)),
                         checkpoint_sha256=sha256_file(MODELS / (b + '.npz')))
    save_json(OUT / 'training_report.json', dict(protocol_sha256=sha256_file(OUT / 'protocol.json'),
        rows=len(x), class_counts=dict(Counter(r['source_label'] for r in p['train'])),
        weights_by_class={d: float(w[[r['source_label'] == d for r in p['train']]].sum()) for d in DIAGNOSES},
        heads=history, backbone_frozen=True))
    return heads


def head_probability(pair, x, branch):
    scaler, head = pair
    q = head.predict_proba(scaler.transform(x))
    return q[:, 1] if branch == 'binary' else q[:, :3].sum(1)


def fuse(ref, cancer):
    c = .75 * ref[:, 5] + .25 * cancer
    out = ref * ((1 - c) / np.maximum(1 - ref[:, 5], 1e-12))[:, None]
    out[:, 5] = c
    assert np.isfinite(out).all() and np.allclose(out.sum(1), 1, atol=1e-6)
    return out


def evaluate(p, extractor, heads):
    trial = {n: dict(name=n) for n in ('old_classwise', 'binary_cancer25', 'subtype_cancer25')}
    results = {}; values_by_split = {}
    for split in pad.prior.SPLITS[:2]:
        rr = p['splits'][split]; x, raw = extractor.infer(rr)
        ref = pad.prior.baseline(split, rr)['old_classwise']
        values = dict(old_classwise=ref)
        aux = {}
        for b in BRANCHES:
            aux[b] = head_probability(heads[b], x, b)
            values[b + '_cancer25'] = fuse(ref, aux[b])
        y = np.array([CLASSES.index(r['label']) for r in rr])
        for n, q in values.items(): trial[n][split] = score(q, y)
        results[split] = {n: score(q, y) for n, q in values.items()}
        values_by_split[split] = values
        np.savez_compressed(OUT / (split + '.npz'), paths=[r['path'] for r in rr], truth=y,
                            features=x, original_resnet=raw, **values, **{b + '_cancer': q for b, q in aux.items()})
    rr = p['pad_validation']; x, raw = extractor.infer(rr)
    with np.load(pad.OUT / 'pad_validation.npz') as z:
        assert z['paths'].tolist() == [r['path'] for r in rr]
        ref = z['old_classwise'].copy()
    pv = dict(old_classwise=ref); aux = {}
    for b in BRANCHES:
        aux[b] = head_probability(heads[b], x, b); pv[b + '_cancer25'] = fuse(ref, aux[b])
    pm = {n: pad.cancer_score(q, rr) for n, q in pv.items()}
    standalone = {b: {d: dict(flagged=int(((aux[b] >= .5) & np.array([r['diagnostic'] == d for r in rr])).sum()),
                             support=sum(r['diagnostic'] == d for r in rr))
                      for d in ('BCC', 'SCC', 'MEL', 'NEV', 'SEK', 'ACK')} for b in BRANCHES}
    np.savez_compressed(OUT / 'pad_validation.npz', paths=[r['path'] for r in rr], features=x,
                        original_resnet=raw, **pv, **{b + '_cancer': q for b, q in aux.items()})
    for n, t in trial.items():
        t['pad_validation'] = pm[n]
        t['eligible'] = bool(pad.prior.eligible(t, trial['old_classwise']) and
            pm[n]['non_cancer_flag_rate'] <= pm['old_classwise']['non_cancer_flag_rate'] + 1e-12 and
            all(pm[n]['by_diagnosis'][d]['flag_rate'] >= pm['old_classwise']['by_diagnosis'][d]['flag_rate'] - 1e-12 for d in DIAGNOSES[:3]))
    selected = sorted([t for t in trial.values() if t['eligible']], key=pad.prior.rank)[0]['name']
    save_json(OUT / 'selection_locked.json', dict(protocol_sha256=sha256_file(OUT / 'protocol.json'),
        selected=selected, trials=trial, checkpoints={b: sha256_file(MODELS / (b + '.npz')) for b in BRANCHES}))
    print(json.dumps(dict(selection_locked=selected, eligibility={n:t['eligible'] for n,t in trial.items()})), flush=True)
    for split in pad.prior.SPLITS[2:]:
        rr = p['splits'][split]; x, raw = extractor.infer(rr)
        ref = pad.prior.baseline(split, rr)['old_classwise']; values = dict(old_classwise=ref); aux = {}
        for b in BRANCHES:
            aux[b] = head_probability(heads[b], x, b); values[b + '_cancer25'] = fuse(ref, aux[b])
        y = np.array([CLASSES.index(r['label']) for r in rr])
        results[split] = {n: score(q, y) for n, q in values.items()}
        np.savez_compressed(OUT / (split + '.npz'), paths=[r['path'] for r in rr], truth=y,
                            features=x, original_resnet=raw, **values, **{b + '_cancer': q for b, q in aux.items()})
        print(json.dumps(dict(evaluated=split)), flush=True)
    check_frozen(p)
    save_json(OUT / 'results.json', dict(protocol_sha256=sha256_file(OUT / 'protocol.json'),
        selection_sha256=sha256_file(OUT / 'selection_locked.json'), selected=selected,
        results=results, pad_validation=pm, standalone_pad_flags=standalone))
    print(json.dumps(dict(complete=True, selected=selected)), flush=True)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--prepare-only', action='store_true'); parser.add_argument('--resume', action='store_true'); args = parser.parse_args()
    p = read(OUT / 'protocol.json') if args.resume else register()
    check_frozen(p)
    if args.prepare_only: print('Registered frozen cancer-head comparison.'); return
    assert not (OUT / 'results.json').exists()
    torch.set_num_threads(4)
    extractor = Features(p); heads = fit(p, extractor); evaluate(p, extractor, heads)


if __name__ == '__main__': main()
