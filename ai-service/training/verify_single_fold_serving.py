"""Check fixed branch parity on saved scores; this is not an accuracy study."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI))
from app.research_runtime import checked_path, route_fold, serving_scores
from training.select_single_fold_serving import choose


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    package = AI / 'models/research_pipeline'
    manifest_path = package / 'serving_single_fold.json'
    m = read(manifest_path)
    assert m['aggregation'] == 'single_fold_v1' and len(m['folds']) == 1
    for entry in m['assets'].values():
        checked_path(package, entry)
    selection = read(package / m['assets']['serving_selection']['path'])
    for row in selection['candidates']:
        path = AI / row['source']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['source_sha256']
        lock = read(path)
        metrics = lock['trials'][lock['selected']]['metrics']
        assert metrics['macro_f1'] == row['macro_f1'] and metrics['accuracy'] == row['accuracy']
    assert choose(selection['candidates']) == m['serving_fold'] == 4
    f = m['folds'][0]
    assert not any(k in f for k in ['stack', 'gate', 'specialist'])
    rows = [r for r in read(AI / 'reports/teacher_dropout_specialist_seed42_20261023/oof_decisions.json') if r['fold'] == 4]
    paths = [r['path'] for r in rows]
    parents = []
    for architecture in ['b0', 'convnext']:
        payload = read(AI / f'candidates/oof_{architecture}_fold4_seed42/oof_predictions.json')
        mapped = {r['path']: r['probabilities'] for r in payload['rows']}
        values = [mapped[p] for p in paths]
        parents.append(np.array([[v[c] for c in m['classes']] if isinstance(v, dict) else v for v in values]))
    payload = read(AI / 'reports/original_eight_resnet50_cv_seed42/fold_4/test_predictions.json')
    mapped = {r['path']: r['probabilities']['resnet50'] for r in payload}
    values = [mapped[p] for p in paths]
    parents.append(np.array([[v[c] for c in m['classes']] if isinstance(v, dict) else v for v in values]))
    decision, ref, bc, ensemble = route_fold(parents, f['convnext_weights'], f['protected'])
    np.testing.assert_array_equal(decision, [r['predictions']['validation_selected'] for r in rows])
    np.testing.assert_array_equal(ensemble, [r['predictions']['original_fusion'] for r in rows])
    np.testing.assert_array_equal(decision == 5, ref == 5)
    for i, winner in enumerate(decision):
        pp = [p[i:i+1] for p in parents]
        order, scores, _, _ = serving_scores(pp, bc[i:i+1], int(ref[i]), f['protected'], int(winner))
        assert order[0] == winner and np.isclose(scores.sum(), 1)
        expected = bc[i] if ref[i] in f['protected'] else .75 * bc[i] + .25 * parents[2][i]
        np.testing.assert_array_equal(scores, expected)
    result = dict(status='PASS', serving_fold=4, images=len(rows), exact_retained_branch=True,
                  exact_cancer_mask=True, unmodified_scores=True, voting=False,
                  manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                  scope='Implementation parity on existing held-out fold-4 scores only; not a new test or full API accuracy evaluation.')
    destination = AI / 'reports/single_fold_serving_20261111'
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'branch_parity.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
