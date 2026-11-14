"""API wiring check on eight previously accepted examples; no accuracy claim."""
import hashlib
import json
from pathlib import Path

import httpx

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parent


def main():
    package = AI / 'models/research_pipeline'
    manifest_path = package / 'serving_single_fold.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    # First historical accepted example for each input class, in locked file order.
    # This selects usable plumbing samples, not a representative accuracy cohort.
    samples = {}
    source = AI / 'reports/application_evaluation_20261110/predictions.jsonl'
    for line in source.read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        if r['http_status'] == 200:
            samples.setdefault(r['label'], r)
    assert set(samples) == set(manifest['classes'])
    with httpx.Client(base_url='http://localhost:8000', timeout=45) as client:
        health = client.get('/health').raise_for_status().json()
        assert health['modelVersion'] == manifest['name'] and health['servingFold'] == 4
        assert health['aggregation'] == 'single_fold_v1'
        for label in manifest['classes']:
            row = samples[label]
            path = ROOT / row['path']
            content = path.read_bytes()
            assert hashlib.sha256(content).hexdigest() == row['sha256']
            response = client.post('/predict', headers={'X-User-Role': 'PATIENT'},
                                   files={'image': (path.name, content, 'image/png' if path.suffix.lower() == '.png' else 'image/jpeg')})
            response.raise_for_status()
            result = response.json()
            assert result['model_version'] == manifest['name']
            assert result['score_type'] == 'ensemble_evidence' and result['serving_fold'] == 4
            assert not result.get('fold_decisions') and not result['confidence_is_calibrated']
            assert result['top3'][0]['label'] == result['disease']
            assert result['confidence'] == result['top3'][0]['probability']
            assert result['gradcam_method'] == 'illustrative_b0_fold4'
            assert result['gradcam_image'].startswith('data:image/png;base64,')
            print(f'API wiring: {len(result["top3"])} scores, single fold, CAM present', flush=True)
    report = dict(status='PASS', requests=8, health=health, voting=False,
                  score_type='ensemble_evidence', gradcam_method='illustrative_b0_fold4',
                  manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                  scope='Functional smoke only, selected from historical accepted images. No accuracy metrics or independent-test claim.')
    destination = AI / 'reports/single_fold_serving_20261111'
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'docker_smoke.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
