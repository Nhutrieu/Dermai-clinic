"""Freeze one serving branch using existing INNER validation only; no test reads."""
import copy
import hashlib
import json
from pathlib import Path

AI = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def choose(rows):
    # Fixed ordering: higher inner Macro F1, then Accuracy, then lower fold ID.
    return max(rows, key=lambda r: (r['macro_f1'], r['accuracy'], -r['fold']))['fold']


def main():
    package = AI / 'models/research_pipeline'
    destination = package / 'serving_single_fold.json'
    selection_path = package / 'single_fold_selection_20261111.json'
    if destination.exists() or selection_path.exists():
        raise FileExistsError('Refusing to overwrite frozen serving selection')
    source = package / 'manifest.json'
    old = json.loads(source.read_text(encoding='utf-8'))
    rows = []
    for fold in range(5):
        path = AI / f'reports/teacher_dropout_specialist_seed42_20261023/fold_{fold}/selection_locked.json'
        lock = json.loads(path.read_text(encoding='utf-8'))
        metrics = lock['trials'][lock['selected']]['metrics']
        rows.append(dict(fold=fold, selected=lock['selected'], accuracy=metrics['accuracy'],
                         macro_f1=metrics['macro_f1'], source=str(path.relative_to(AI)).replace('\\', '/'),
                         source_sha256=digest(path)))
    selected = choose(rows)
    branch = copy.deepcopy(old['folds'][selected])
    selection = dict(schema_version=1, date='2026-11-11', selected_fold=selected,
                     criterion='max INNER Macro F1; tie: INNER Accuracy; tie: lower fold ID',
                     candidates=rows, source_manifest_sha256=digest(source),
                     test_used_for_selection=False,
                     caveat='Inner sets differ across folds. This is a serving choice, not a new OOF result or a claim of external superiority.')
    selection_path.write_text(json.dumps(selection, indent=2) + '\n', encoding='utf-8')
    keys = {'ood_model', 'ood_profile', 'provenance', *branch['members']}
    keys.update(branch[k] for k in ['stack', 'gate', 'specialist', 'scaler'] if k in branch)
    assets = {k: v for k, v in old['assets'].items() if k in keys}
    assets['serving_selection'] = dict(path=selection_path.name, sha256=digest(selection_path))
    manifest = dict(schema_version=2, name=f'dermai-eight-single-fold{selected}-v1-20261111',
                    classes=old['classes'], aggregation='single_fold_v1', serving_fold=selected,
                    assets=assets, folds=[branch], score_type='ensemble_evidence',
                    confidence_is_calibrated=False,
                    historical_research_OOF=old['research_OOF'],
                    serving_evaluation=dict(accuracy=None, macro_f1=None, independent_test=False,
                        note='Historical pooled OOF and the retired voter evaluation are not scores of this fixed serving branch.'),
                    gradcam_method=f'illustrative_b0_fold{selected}')
    destination.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(manifest=str(destination), selected_fold=selected,
                         inner_macro_f1=rows[selected]['macro_f1'], assets=len(assets))))


if __name__ == '__main__':
    main()
