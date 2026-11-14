"""Verify the restored API against eight frozen historical voter responses."""
import hashlib
import json
from pathlib import Path

import httpx

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parent


def main():
    path = AI / 'models/research_pipeline/manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == '60c4927e479b2bb88c7778070715fba8876ac65420be1ff2affbd8c53fb89fed'
    assert manifest['aggregation'] == 'protected_fold_vote_v1'
    samples = {}
    source = AI / 'reports/application_evaluation_20261110/predictions.jsonl'
    for line in source.read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row['http_status'] == 200:
            samples.setdefault(row['label'], row)
    assert set(samples) == set(manifest['classes'])
    fields = ['disease', 'confidence', 'top3', 'uncertain', 'model_version', 'score_type',
              'confidence_is_calibrated', 'decision_policy_applied', 'fold_decisions']
    with httpx.Client(base_url='http://localhost:8000', timeout=45) as client:
        health = client.get('/health').raise_for_status().json()
        assert health['modelVersion'] == manifest['name']
        assert health['aggregation'] == manifest['aggregation'] and health['servingFold'] is None
        for label in manifest['classes']:
            row = samples[label]
            sample = ROOT / row['path']
            content = sample.read_bytes()
            assert hashlib.sha256(content).hexdigest() == row['sha256']
            mime = 'image/png' if sample.suffix.lower() == '.png' else 'image/jpeg'
            response = client.post('/predict', headers={'X-User-Role': 'PATIENT'},
                                   files={'image': (sample.name, content, mime)})
            response.raise_for_status()
            result = response.json()
            for field in fields:
                assert result[field] == row[field], f'Historical response mismatch: {field}'
            assert len(result['fold_decisions']) == 5
            assert result['gradcam_method'] == 'illustrative_b0_fold0'
            assert result['gradcam_image'].startswith('data:image/png;base64,')
            print('Historical voter response matched', flush=True)
    destination = AI / 'reports/restored_fold_vote_20261111'
    destination.mkdir(parents=True, exist_ok=True)
    report = dict(status='PASS', requests=8, exact_historical_response_fields=fields,
                  health=health, manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  scope='Functional restoration check on eight previously accepted examples, not a new accuracy study.')
    (destination / 'docker_smoke.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
