"""Replay the packaged per-fold rules on saved held-out scores, not a new test."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parent
sys.path.insert(0, str(AI))
from app.research_runtime import checked_path, route_fold


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify(package=None):
    package = package or AI / 'models/research_pipeline'
    manifest = read(package / 'manifest.json')
    for entry in manifest['assets'].values():
        checked_path(package, entry)
    def arrays(key):
        with np.load(package / manifest['assets'][key]['path'], allow_pickle=False) as a:
            return {k:a[k].copy() for k in a.files}
    rows = read(AI / 'reports/teacher_dropout_specialist_seed42_20261023/oof_decisions.json')
    def vector(value):
        return [value[c] for c in manifest['classes']] if isinstance(value, dict) else value
    records = []
    for f in manifest['folds']:
        fold = f['fold']; held = [r for r in rows if r['fold'] == fold]
        paths = [r['path'] for r in held]
        parents = []
        for architecture in ['b0', 'convnext']:
            payload = read(AI / f'candidates/oof_{architecture}_fold{fold}_seed42/oof_predictions.json')
            mapped = {r['path']:r['probabilities'] for r in payload['rows']}
            parents.append(np.array([vector(mapped[p]) for p in paths], dtype=np.float64))
        rdir = AI / ('reports/original_eight_resnet50_pilot_fold0_seed42' if fold == 0 else f'reports/original_eight_resnet50_cv_seed42/fold_{fold}')
        mapped = {r['path']:r['probabilities']['resnet50'] for r in read(rdir / 'test_predictions.json')}
        parents.append(np.array([vector(mapped[p]) for p in paths], dtype=np.float64))
        sp = None
        if 'specialist' in f:
            with np.load(AI / f'reports/teacher_dropout_specialist_seed42_20261023/fold_{fold}/outer_probabilities.npz') as a:
                index = {str(p):i for i,p in enumerate(a['paths'])}
                sp = a['dropout_specialist_probability'][[index[p] for p in paths]]
        decision, ref, _, ensemble = route_fold(parents, f['convnext_weights'], f['protected'],
              arrays(f['stack']) if 'stack' in f else None, arrays(f['gate']) if 'gate' in f else None, sp)
        np.testing.assert_array_equal(ensemble, [r['predictions']['original_fusion'] for r in held])
        np.testing.assert_array_equal(decision, [r['predictions']['validation_selected'] for r in held])
        np.testing.assert_array_equal(decision == 5, ref == 5)
        records.append(dict(fold=fold, images=len(held), exact_E=True, exact_final=True, cancer_mask_exact=True))
    result = dict(status='PASS', scope='Serving branch implementation replays the 5937 historical OOF decisions exactly; this does NOT evaluate the five-branch serving vote.',
                  images=sum(r['images'] for r in records), folds=records,
                  manifest_sha256=hashlib.sha256((package / 'manifest.json').read_bytes()).hexdigest(),
                  serving_accuracy=None, independent_test=False)
    destination = AI / 'reports/research_runtime_integration_20261108'
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'branch_parity.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    verify()
