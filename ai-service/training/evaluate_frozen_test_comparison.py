"""Matched, frozen classifier evaluation on audited historical test manifests.

No training, source-based tuning, API configuration changes or patient claims.
Single-architecture comparators average their five checkpoint probabilities.
E variants reuse the exact frozen fold policies and protected five-fold vote.
All methods label every admitted image, without API quality/OOD abstention.
"""
from __future__ import annotations

import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import sys
import time

import numpy as np
from PIL import Image
import torch
from sklearn.metrics import confusion_matrix, f1_score, accuracy_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ai-service'))
from app.model import CLASSES, PREPROCESS, load_bundle
from app.research_runtime import route_fold, aggregate, Specialist

OUT = ROOT / 'ai-service/reports/frozen_test_comparison_20261113'
PACKAGE = ROOT / 'ai-service/models/research_pipeline'
DATA = ROOT / 'ai-service/reports/application_evaluation_20261110/evaluation_manifest.json'
METHODS = ['efficientnet_b0', 'convnext_tiny', 'resnet50', 'E', 'E_S', 'E_G', 'E_G_S']
ARCHS = METHODS[:3]
DATASETS = ['historical_fixed_test', 'SCIN_case_holdout']

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def rel(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()

def prepare():
    rows = read(DATA)
    assert len(rows) == len({r['path'] for r in rows}) == 723
    assert Counter(r['dataset'] for r in rows) == dict(historical_fixed_test=486, SCIN_case_holdout=237)
    manifest = read(PACKAGE / 'manifest.json')
    assert manifest['classes'] == CLASSES
    assert manifest['aggregation'] == 'protected_fold_vote_v1'
    paths = [Path(__file__), DATA, PACKAGE / 'manifest.json',
             ROOT / 'ai-service/app/model.py', ROOT / 'ai-service/app/research_runtime.py',
             ROOT / 'ai-service/reports/application_evaluation_20261110/audit.json',
             ROOT / 'ai-service/reports/application_evaluation_20261110/predictions.jsonl']
    for entry in manifest['assets'].values():
        p = (PACKAGE / entry['path']).resolve()
        assert p.is_relative_to(PACKAGE.resolve()) and sha(p) == entry['sha256']
        paths.append(p)
    for row in rows:
        p = (ROOT / row['path']).resolve()
        assert p.is_relative_to(ROOT) and sha(p) == row['sha256'], row['path']
    design = dict(
        classes=CLASSES, rows=rows, images=723, primary_dataset=DATASETS[0],
        datasets=dict(historical_fixed_test=486, SCIN_case_holdout=237),
        model_manifest_sha256=sha(PACKAGE / 'manifest.json'), methods=METHODS,
        preprocessing='Exact app PREPROCESS: RGB, Resize256, CenterCrop224, ImageNet normalization.',
        inference='Native CUDA, FP32, eval and inference_mode, batch16, deterministic cuDNN, no TF32.',
        single_architecture_aggregation='Arithmetic mean of five probability vectors per architecture, then argmax. Each row is one architecture with five pretrained/fine-tuned checkpoints, NOT one checkpoint.',
        combined_aggregation='Each frozen fold routes E/E+S/E+G/E+G+S with its existing validation-selected assets; apply unchanged app.aggregate protected five-fold plurality vote to each variant. No new gate, specialist, thresholds or weights.',
        paired_fold_analysis='Additionally report each architecture and variant separately in each original fold and arithmetic means of those metrics on the SAME test images. These folds are not independent seeds or five disjoint test subsets.',
        missing_components='S enabled only where retained (fold1/2), G only fold0/3; fold4 E only. Ablation removes existing components without refitting.',
        admission='All723 images in already-audited immutable test manifest. No further sample removal or favorable subset after prediction. All methods must return a class on every image.',
        api_abstention='No quality/OOD rejection, Grad-CAM, RAG or HTTP in this CLASSIFIER-ONLY test. It is not an API accuracy or speed comparison.',
        score='Fixed8 Accuracy/MacroF1, per-class P/R/F1/support, 8x8 confusion, paired group-proxy bootstrap1000 seed42 of EGS-minus-comparator deltas; report SCIN class absence and present-class F1 separately.',
        selection='No model, threshold, weight, seed or dataset selection from new scores. No adoption or application changes. Lock every prediction before scoring.',
        limitations=['Previously investigated historical test sources, not blind independent patient data.',
                     'Image/scene and SCIN case proxy groups do not verify all patient identities.',
                     'SCIN lacks SkinCancer and contains only four Lupus images.',
                     'One training seed; original training folds overlap. Bootstrap covers image-group sampling only.',
                     'No training, clinical review or new source intake; no clinical or universal-superiority claim.'],
        frozen_sha256={rel(p): sha(p) for p in paths})
    path = OUT / 'protocol.json'
    if path.exists():
        p = read(path)
        assert all(p[k] == v for k, v in design.items()), 'Registered design changed'
    else:
        p = dict(registered_utc=datetime.now(timezone.utc).isoformat(), **design)
        write(path, p)
    return p, manifest

def verify(p):
    for path, digest in p['frozen_sha256'].items():
        assert sha(ROOT / path) == digest, path

def forward(p, manifest):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    torch.set_num_threads(4)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(42)
    rows = p['rows']
    tensors = []
    for row in rows:
        with Image.open(ROOT / row['path']) as image:
            tensors.append(PREPROCESS(image.convert('RGB')))
    x = torch.stack(tensors)
    del tensors
    protocol_sha = sha(OUT / 'protocol.json')
    assets = manifest['assets']
    parent = []
    specialists = []
    for cfg in manifest['folds']:
        f = cfg['fold']
        cached = OUT / f'fold_{f}_probabilities.npz'
        if cached.exists():
            with np.load(cached, allow_pickle=False) as z:
                assert str(z['protocol_sha256']) == protocol_sha
                pp = z['probabilities'].copy()
                sp = z['specialist'].copy() if z['specialist'].shape[1] else None
        else:
            pp = []
            res_features = None
            for index, key in enumerate(cfg['members']):
                start = time.monotonic()
                bundle = load_bundle(PACKAGE / assets[key]['path'])
                assert bundle.classes == CLASSES and bundle.temperature == 1
                bundle.model.to(device).eval()
                captured = []
                handle = None
                if index == 2 and cfg.get('specialist'):
                    handle = bundle.model.avgpool.register_forward_hook(lambda _m, _a, y: captured.append(y.flatten(1).detach().cpu()))
                values = []
                with torch.inference_mode():
                    for first in range(0, len(x), 16):
                        values.append(bundle.model(x[first:first + 16].to(device)).softmax(1).cpu().numpy())
                pp.append(np.concatenate(values).astype(np.float64))
                if handle:
                    handle.remove()
                    res_features = torch.cat(captured).numpy()
                del bundle
                torch.cuda.empty_cache()
                print(json.dumps(dict(fold=f, architecture=ARCHS[index], images=len(x), seconds=round(time.monotonic()-start, 2))), flush=True)
            pp = np.stack(pp)
            sp = None
            if cfg.get('specialist'):
                with np.load(PACKAGE / assets[cfg['scaler']]['path'], allow_pickle=False) as z:
                    scaled = ((res_features - z['mean']) / z['scale']).astype(np.float32)
                head = Specialist().to(device).eval()
                head.load_state_dict(torch.load(PACKAGE / assets[cfg['specialist']]['path'], map_location=device, weights_only=True)['model_state_dict'])
                with torch.inference_mode():
                    sp = head(torch.from_numpy(scaled).to(device)).softmax(1).cpu().numpy()
                del head
            np.savez_compressed(cached, probabilities=pp,
                                specialist=sp if sp is not None else np.empty((len(x), 0)),
                                protocol_sha256=np.array(protocol_sha))
        assert pp.shape == (3, 723, 8) and np.isfinite(pp).all()
        assert np.allclose(pp.sum(-1), 1, atol=1e-6)
        parent.append(pp)
        specialists.append(sp)
    parent = np.stack(parent)
    by_fold = np.zeros((5, len(METHODS), len(rows)), dtype=np.int64)
    bcs = np.zeros((5, len(rows), 8))
    refs = np.zeros((5, len(rows)), dtype=np.int64)
    for f, cfg in enumerate(manifest['folds']):
        def arrays(key):
            if not cfg.get(key):
                return None
            with np.load(PACKAGE / assets[cfg[key]]['path'], allow_pickle=False) as z:
                return {k: z[k].copy() for k in z.files}
        stack, gate = arrays('stack'), arrays('gate')
        by_fold[f, :3] = parent[f].argmax(2)
        for method, use_g, use_s in [('E', False, False), ('E_S', False, True), ('E_G', True, False), ('E_G_S', True, True)]:
            d, ref, bc, _ = route_fold(list(parent[f]), cfg['convnext_weights'], cfg['protected'],
                                      stack if use_g else None, gate if use_g else None,
                                      specialists[f] if use_s else None)
            assert np.array_equal(d == 5, ref == 5)
            by_fold[f, METHODS.index(method)] = d
            bcs[f] = bc
            refs[f] = ref
    predictions = np.zeros((len(METHODS), len(rows)), dtype=np.int64)
    predictions[:3] = parent.mean(0).argmax(2)
    for mi in range(3, len(METHODS)):
        for i in range(len(rows)):
            predictions[mi, i] = aggregate(by_fold[:, mi, i], refs[:, i], bcs[:, i])[0]
    np.savez_compressed(OUT / 'predictions_locked.npz', predictions=predictions,
                        by_fold=by_fold, paths=np.array([r['path'] for r in rows]),
                        protocol_sha256=np.array(protocol_sha))
    write(OUT / 'prediction_lock.json', dict(protocol_sha256=protocol_sha,
          predictions_sha256=sha(OUT / 'predictions_locked.npz'), images=723,
          methods=METHODS, locked_before_scoring=True, device=str(device),
          architecture=torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU'))
    verify(p)
    return predictions, by_fold

def metrics(pred, truth):
    cm = np.zeros((8, 8), dtype=np.int64)
    np.add.at(cm, (truth, pred), 1)
    tp = cm.diagonal(); support = cm.sum(1); called = cm.sum(0)
    precision = np.divide(tp, called, out=np.zeros(8), where=called>0)
    recall = np.divide(tp, support, out=np.zeros(8), where=support>0)
    f1 = np.divide(2*tp, support+called, out=np.zeros(8), where=support+called>0)
    result = dict(images=len(truth), correct=int(tp.sum()), accuracy=float(tp.sum()/len(truth)),
                  macro_f1=float(f1.mean()), macro_f1_present_classes=float(f1[support>0].mean()),
                  per_class={c:dict(support=int(support[i]), precision=float(precision[i]),
                     recall=float(recall[i]) if support[i] else None, f1=float(f1[i])) for i,c in enumerate(CLASSES)},
                  confusion_matrix=cm.tolist())
    assert np.array_equal(cm, confusion_matrix(truth, pred, labels=np.arange(8)))
    assert abs(result['accuracy']-accuracy_score(truth,pred)) < 1e-12
    assert abs(result['macro_f1']-f1_score(truth,pred,labels=np.arange(8),average='macro',zero_division=0)) < 1e-12
    return result

def paired_intervals(rows, truth, predictions):
    groups, inverse = np.unique([r['group'] for r in rows], return_inverse=True)
    g = len(groups)
    cm = np.zeros((len(METHODS),g,8,8), dtype=np.int64)
    for mi, pred in enumerate(predictions):
        np.add.at(cm[mi], (inverse,truth,pred), 1)
    draw = np.random.default_rng(42).multinomial(g,np.full(g,1/g),size=1000)
    boot = np.einsum('bg,mgij->bmij',draw,cm,optimize=True)
    tp = np.diagonal(boot,axis1=2,axis2=3)
    acc = tp.sum(2)/boot.sum((2,3))
    den = boot.sum(2)+boot.sum(3)
    mf = np.divide(2*tp,den,out=np.zeros_like(tp,dtype=float),where=den>0).mean(2)
    out = {}
    for comparator in ARCHS+['E','E_G']:
        ci = METHODS.index(comparator); fi = METHODS.index('E_G_S')
        out[comparator] = {k:np.quantile(values[:,fi]-values[:,ci],[.025,.975]).tolist()
                           for k,values in [('accuracy',acc),('macro_f1',mf)]}
    return dict(repetitions=1000, seed=42, proxy_groups=g, deltas_EGS_minus=out,
                limitation='Proxy-group bootstrap of fixed predictions only; not new patients, training seeds, adaptive-selection adjustment or clinical evidence.')

def score(p, pred, by_fold):
    assert read(OUT/'prediction_lock.json')['predictions_sha256']==sha(OUT/'predictions_locked.npz')
    results = {}
    for dataset in DATASETS:
        take = np.array([i for i,r in enumerate(p['rows']) if r['dataset']==dataset])
        rows = [p['rows'][i] for i in take]
        truth = np.array([CLASSES.index(r['label']) for r in rows])
        methods = {m:metrics(pred[mi,take],truth) for mi,m in enumerate(METHODS)}
        fold_scores = {m:[metrics(by_fold[f,mi,take],truth) for f in range(5)] for mi,m in enumerate(METHODS)}
        means = {m:{k:float(np.mean([v[k] for v in values])) for k in ['accuracy','macro_f1']}
                 for m,values in fold_scores.items()}
        results[dataset] = dict(images=len(rows), methods=methods, per_fold=fold_scores,
                               mean_paired_fold_metrics=means,
                               paired_bootstrap=paired_intervals(rows,truth,pred[:,take]))
        print(json.dumps(dict(dataset=dataset, results={m:{k:methods[m][k] for k in ['correct','accuracy','macro_f1']} for m in METHODS})),flush=True)
    # This only checks a known frozen pipeline; it never selects a policy.
    old = [json.loads(s) for s in (ROOT/'ai-service/reports/application_evaluation_20261110/predictions.jsonl').read_text(encoding='utf-8').splitlines()]
    index = {r['path']:i for i,r in enumerate(p['rows'])}
    mismatch = []
    checked = 0
    for row in old:
        if row['http_status']!=200:
            continue
        checked += 1
        winner = CLASSES[pred[METHODS.index('E_G_S'),index[row['path']]]]
        if winner != row['disease']:
            mismatch.append(dict(path=row['path'], classifier=winner, previous_api=row['disease']))
    value = dict(scope='Frozen classifier-only matched comparison on historically inspected held test images',
                 independent_blind_test=False, protocol_sha256=sha(OUT/'protocol.json'),
                 prediction_sha256=sha(OUT/'predictions_locked.npz'),classes=CLASSES,
                 aggregation={k:p[k] for k in ['single_architecture_aggregation','combined_aggregation','paired_fold_analysis','api_abstention']},
                 datasets=results, current_api_changed=False, training_performed=False,
                 historical_api_label_crosscheck=dict(returned_checked=checked,mismatches=mismatch))
    write(OUT/'results.json',value)
    verify(p)
    write(OUT/'verification.json',dict(status='PASS', results_sha256=sha(OUT/'results.json'),
          protocol_sha256=sha(OUT/'protocol.json'), predictions_sha256=sha(OUT/'predictions_locked.npz'),
          source_and_checkpoints_unchanged=True, samples=723,sklearn_metric_check=True,
          label_lookup_only_in_scoring=True, historical_api_label_crosscheck_mismatches=len(mismatch)))

if __name__ == '__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    protocol, manifest = prepare()
    print(json.dumps(dict(registered_protocol=sha(OUT/'protocol.json'), images=723, model_selection='none')),flush=True)
    predictions, folds = forward(protocol, manifest)
    score(protocol, predictions, folds)
