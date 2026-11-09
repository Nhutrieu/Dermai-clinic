"""Package the retained E/G/S artifacts without training or changing old files."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import torch

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / 'ai-service'
R = AI / 'reports'
C = AI / 'candidates'
CLASSES = ['Acne', 'Candidiasis', 'Eczema', 'Lupus', 'Psoriasis', 'SkinCancer', 'Tinea', 'Warts']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def export(output):
    if (output / 'manifest.json').exists():
        raise ValueError('Package exists; verify it or choose a new output directory')
    source = R / 'teacher_dropout_specialist_seed42_20261023'
    gsource = R / 'teacher_macro_f1_gate_seed42_20261023'
    esource = R / 'original_eight_cancer_locked_resnet_fusion_seed42_20261021'
    explanations = R / 'teacher_pipeline_explanation_20261108'
    expected = {}
    provenance = {}
    for directory in [source, gsource, esource]:
        protocol = read(directory / 'protocol.json')
        expected.update(protocol.get('frozen_sha256', {}))
        expected.update(protocol.get('source_sha256', {}))
        provenance[(directory / 'protocol.json').relative_to(ROOT).as_posix()] = sha(directory / 'protocol.json')
        for fold in range(5):
            lock = directory / f'fold_{fold}/selection_locked.json'
            expected.update(read(lock).get('artifacts_sha256', {}))
            provenance[lock.relative_to(ROOT).as_posix()] = sha(lock)
    ablation = read(explanations / 'results.json')
    assert ablation['status'] == 'PASS'
    assert read(source / 'verification.json')['status'] == 'PASS'
    provenance[(explanations / 'results.json').relative_to(ROOT).as_posix()] = sha(explanations / 'results.json')
    assets, folds = {}, []
    output.mkdir(parents=True, exist_ok=True)

    def copy_asset(key, path, target, expected_hash=None):
        relative = path.relative_to(ROOT).as_posix()
        digest = sha(path)
        bound = expected_hash or expected.get(relative)
        if bound is None or digest != bound:
            raise ValueError(f'Unbound or changed source artifact: {relative}')
        provenance[relative] = digest
        dest = output / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        assert sha(dest) == digest
        assets[key] = dict(path=target, sha256=digest)
        return key

    # Preserve the existing OOD feature space/model version exactly.
    old = AI / 'models/best_model.pth'
    profile = AI / 'models/ood_profile.json'
    assert sha(old) == '975e4852023ebb9d3af544b819bec0b887cf75b1467447c87c40591da90b7a17'
    copy_asset('ood_model', old, 'ood/model.pth', sha(old))
    copy_asset('ood_profile', profile, 'ood/profile.json', sha(profile))
    for fold in range(5):
        names = [f'oof_b0_fold{fold}_seed42', f'oof_convnext_fold{fold}_seed42',
                 'original_eight_resnet50_pilot_fold0_seed42' if fold == 0 else f'original_eight_resnet50_cv_fold{fold}_seed42']
        members = []
        for arch, name in zip(['efficientnet_b0', 'convnext_tiny', 'resnet50'], names):
            path = C / name / 'best_model.pth'
            bound = None
            if arch != 'resnet50':
                prediction_file = C / name / 'inner_predictions.json'
                pred = read(prediction_file)
                assert pred['architecture'] == arch and pred['outer_fold'] == fold and pred['classes'] == CLASSES
                bound = pred['checkpoint_sha256']
                provenance[prediction_file.relative_to(ROOT).as_posix()] = sha(prediction_file)
            ck = torch.load(path, map_location='cpu', weights_only=True)
            assert ck['architecture'] == arch and ck['classes'] == CLASSES and ck.get('temperature', 1) == 1
            members.append(copy_asset(f'fold{fold}_{arch}', path, f'fold_{fold}/{arch}.pth', bound))
        elock = read(esource / f'fold_{fold}/selection_locked.json')
        glock = read(gsource / f'fold_{fold}/selection_locked.json')
        slock = read(source / f'fold_{fold}/selection_locked.json')
        spec = elock['trials'][elock['selected']]['spec']
        f = dict(fold=fold, members=members,
                 convnext_weights=[ablation['convnext_weights'][str(fold)][c] for c in CLASSES],
                 protected=spec['protected'])
        assert glock['selected'] == ('macro_f1_gate' if fold in [0, 3] else 'current_fusion')
        assert slock['selected'] == ('dropout_specialist' if fold in [1, 2] else 'current_gate')
        if fold in [0, 3]:
            f['stack'] = copy_asset(f'fold{fold}_stack', C / f'teacher_conservative_gate_seed42_20261023/fold_{fold}/stack.npz', f'fold_{fold}/stack.npz')
            f['gate'] = copy_asset(f'fold{fold}_gate', C / f'teacher_macro_f1_gate_seed42_20261023/fold_{fold}/macro_f1_gate.npz', f'fold_{fold}/gate.npz')
        if fold in [1, 2]:
            f['specialist'] = copy_asset(f'fold{fold}_specialist', C / f'teacher_dropout_specialist_seed42_20261023/fold_{fold}/dropout_specialist/best_model.pth', f'fold_{fold}/specialist.pth')
            f['scaler'] = copy_asset(f'fold{fold}_scaler', source / f'fold_{fold}/scaler.npz', f'fold_{fold}/scaler.npz')
        folds.append(f)
    provenance_path = output / 'provenance.json'
    provenance_path.write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    assets['provenance'] = dict(path='provenance.json', sha256=sha(provenance_path))
    m = dict(schema_version=1, name='dermai-eight-esg-v1-20261108', classes=CLASSES,
             aggregation='protected_fold_vote_v1', assets=assets, folds=folds,
             score_type='fold_vote_fraction', confidence_is_calibrated=False,
             research_OOF=dict(images=5937, correct=4687,
                 accuracy=ablation['methods']['ensemble_gate_specialist']['accuracy'],
                 macro_f1=ablation['methods']['ensemble_gate_specialist']['macro_f1'], SkinCancer_recall=596/677),
             serving_evaluation=dict(accuracy=None, macro_f1=None, independent_test=False,
                 note='OOF evaluates one held-out branch per image, not five-branch serving votes. Do not assign OOF metrics to the deployed committee.'),
             gradcam_method='illustrative_b0_fold0')
    (output / 'manifest.json').write_text(json.dumps(m, indent=2), encoding='utf-8')
    print(f'Exported {len(assets)} assets, 15 parent CNNs, 2 gates, 2 specialists: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=AI / 'models/research_pipeline')
    export(parser.parse_args().output.resolve())
