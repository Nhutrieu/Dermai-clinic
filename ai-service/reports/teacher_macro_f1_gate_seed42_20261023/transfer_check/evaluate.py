"""Apply the locked matched gate objectives to previously investigated sources.

No fitting, source selection, threshold tuning or new GPU inference. The same
1709 images are evaluated by five paired fold-specific systems, not five new
source folds, independent seeds or a new probability-averaged classifier.
"""
from datetime import datetime, timezone
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'ai-service/training'))
import run_teacher_macro_f1_gate as new
import evaluate_teacher_stack_transfer as source

old = new.old
base = new.base
OLD_CHILD = old.OUT/'transfer_check'
METHODS = ['current_fusion', 'conservative_control', 'macro_f1_gate',
           'prior_validation_selected', 'validation_selected']
PRIOR_NAMES = dict(current_fusion='current_fusion',
                   conservative_control='conservative_gate',
                   prior_validation_selected='validation_selected')


def utc():
    return datetime.now(timezone.utc).isoformat()


def verify(p):
    for path, expected in p['frozen_sha256'].items():
        assert base.sha(ROOT/path) == expected, path
    for row in p['rows']:
        assert base.sha(ROOT/row['path']) == row['sha256'], row['path']


def prepare():
    if (HERE/'protocol.json').exists():
        p = base.read(HERE/'protocol.json')
        verify(p)
        return p
    spath = source.OUT/'protocol.json'
    sp = base.read(spath)
    source.verify(sp)
    assert base.read(source.OUT/'independent_review.json')['status'] == 'PASS'
    main = base.read(new.OUT/'protocol.json')
    new.original.verify(main)
    results = base.read(new.OUT/'results.json')
    receipt = base.read(new.OUT/'verification.json')
    review = base.read(new.OUT/'independent_review.json')
    assert receipt['status'] == review['status'] == 'PASS'
    assert receipt['results_sha256'] == review['results_sha256'] == base.sha(new.OUT/'results.json')
    assert receipt['decisions_sha256'] == base.sha(new.OUT/'oof_decisions.json')
    assert results['protocol_sha256'] == base.sha(new.OUT/'protocol.json')
    assert review['gate_fit_calls'] == 40
    prior_receipt = base.read(OLD_CHILD/'verification.json')
    prior_review = base.read(OLD_CHILD/'independent_review.json')
    assert prior_receipt['status'] == prior_review['status'] == 'PASS'
    assert prior_receipt['results_sha256'] == prior_review['results_sha256'] == base.sha(OLD_CHILD/'results.json')
    assert prior_receipt['decisions_sha256'] == base.sha(OLD_CHILD/'source_decisions.json')
    prior_child = base.read(OLD_CHILD/'protocol.json')
    for path, expected in prior_child['frozen_sha256'].items():
        assert base.sha(ROOT/path) == expected, path
    fingerprint_path = source.OUT/'cache_forward_check.json'
    fingerprint = base.read(fingerprint_path)
    assert fingerprint['status'] == 'PASS'
    assert fingerprint['checkpoints'] == 15 and fingerprint['image_forwards'] == 240
    assert len(fingerprint['checks']) == 15
    extra = [Path(__file__), Path(new.__file__), Path(old.__file__), Path(old.stack.__file__),
        Path(source.__file__), Path(source.transfer.__file__), Path(base.__file__), spath,
        source.OUT/'results.json', source.OUT/'verification.json', source.OUT/'independent_review.json',
        fingerprint_path, new.OUT/'protocol.json', new.OUT/'results.json', new.OUT/'verification.json',
        new.OUT/'independent_review.json', new.OUT/'all_selections_locked.json',
        old.OUT/'protocol.json', old.OUT/'results.json', old.OUT/'independent_review.json',
        old.OUT/'all_selections_locked.json', OLD_CHILD/'protocol.json', OLD_CHILD/'results.json',
        OLD_CHILD/'verification.json', OLD_CHILD/'independent_review.json', OLD_CHILD/'source_decisions.json']
    frozen = {**sp['frozen_sha256'], **sp['model_checkpoint_sha256'],
              **main['frozen_sha256'], **prior_child['frozen_sha256']}
    boundary = base.read(new.OUT/'all_selections_locked.json')
    old_boundary = base.read(old.OUT/'all_selections_locked.json')
    assert boundary['locked_utc'] <= results['outer_started_utc']
    folds = []
    for f, spec in enumerate(sp['folds']):
        lock_path = new.OUT/f'fold_{f}/selection_locked.json'
        lock = base.read(lock_path)
        prior_lock_path = old.OUT/f'fold_{f}/selection_locked.json'
        prior_lock = base.read(prior_lock_path)
        assert boundary['selections_sha256'][str(f)] == base.sha(lock_path)
        assert old_boundary['selections_sha256'][str(f)] == base.sha(prior_lock_path)
        assert lock['protocol_sha256'] == base.sha(new.OUT/'protocol.json')
        assert lock['selected'] == results['per_fold'][f]['selected']
        assert lock['selected'] in ['current_fusion', *new.ARMS]
        assert prior_lock['selected'] in ['current_fusion', 'conservative_gate']
        for path, expected in lock['artifacts_sha256'].items():
            assert base.sha(ROOT/path) == expected, path
        folds.append(dict(fold=f, baseline_protected=spec['baseline_protected'],
            reference_weights=spec['reference_weights'], validation_selected=lock['selected'],
            prior_validation_selected='conservative_control' if prior_lock['selected']=='conservative_gate' else 'current_fusion'))
        extra += [lock_path, prior_lock_path, old.MODELS/f'fold_{f}/stack.npz',
            old.MODELS/f'fold_{f}/gate.npz',
            *[new.MODELS/f'fold_{f}/{arm}.npz' for arm in new.ARMS]]
    for check in fingerprint['checks']:
        assert base.sha(ROOT/check['cache']) == check['cache_sha256']
        assert base.sha(ROOT/check['checkpoint']) == check['checkpoint_sha256']
        frozen[check['cache']] = check['cache_sha256']
        frozen[check['checkpoint']] = check['checkpoint_sha256']
    frozen.update({path.relative_to(ROOT).as_posix(): base.sha(path) for path in extra})
    p = dict(name='locked_macro_f1_gate_source_transfer_check', registered_utc=utc(),
        parent_experiment=new.OUT.relative_to(ROOT).as_posix(), source_protocol=spath.relative_to(ROOT).as_posix(),
        classes=base.CLASSES, unique_images=1709, rows=sp['rows'], subsets=sp['subsets'],
        folds=folds, methods=METHODS, frozen_sha256=frozen, threshold=new.old.THRESHOLD,
        inference='Reuse same15 frozen original CNN probability caches on same1709images. Apply priorfixedstack and newlocked20fitcontrol/20fitutility gates, unchanged22runtimefeatures and strictscore>2/3. Final10gateheads alone used at inference. Read both oldandnew inner-selected foldlocks.',
        summary='Report paired per-fold evaluations and arithmetic mean/min/max of metrics on SAMEimages; not5sourcefolds, independentseeds,1709x5independentimages or a newbagged classifier.',
        controls='Every source subset/fold baseline,conservative_control andprior_validation_selected CM must match old conservativegate childresults. Every method preserves exactCancer binary predictionmask.',
        reused_forward_receipt=dict(path=fingerprint_path.relative_to(ROOT).as_posix(), sha256=base.sha(fingerprint_path),
            checkpoints=15, image_forwards=240, distinct_images=fingerprint['distinct_images'], new_gpu_forwards=0),
        uncertainty='No newconfidenceintervals computed; no significance or clinical improvementclaim.',
        no_training=True, no_calibration=True, no_source_selection=True, no_threshold_change=True,
        registry_changed=False, global_5937_score_changed=False, serving_changed=False,
        limitations=sp['limitations']+[
            'Read-only source application of alreadylocked matchedgates; not a fresh independent clinical test.',
            'Finalgate losses used originalinner labels only. Source outcomes do not select objective,checkpoint,threshold,fold or calibration.',
            'Report fixed8class MacroF1 and supported-truthclass MacroF1 with explicit support denominators.'])
    assert p['threshold'] == 2/3
    verify(p)
    base.write(HERE/'protocol.json', p)
    return p


def run(p):
    assert not (HERE/'results.json').exists(), 'Preserve completed source check'
    verify(p)
    paths = [row['path'] for row in p['rows']]
    expected_results = base.read(OLD_CHILD/'results.json')
    expected_decisions = {row['path']:row for row in base.read(OLD_CHILD/'source_decisions.json')}
    decisions = {name:[] for name in METHODS}
    all_scores = {arm:[] for arm in new.ARMS}
    candidates = []
    started = utc()
    assert p['registered_utc'] <= started
    for f, spec in enumerate(p['folds']):
        parents = []
        for architecture in old.stack.PARENTS:
            with np.load(source.transfer.OUT/f'fold_{f}_{architecture}.npz', allow_pickle=False) as cache:
                assert cache['protocol_sha256'].item() == base.sha(source.transfer.OUT/'protocol.json')
                parents.append(source.aligned(cache['paths'].tolist(), cache['probabilities'], paths))
        reference = source.transfer.classwise_blend(parents[0], parents[1], np.asarray(spec['reference_weights']))
        current = base.decide(reference, parents[2], spec['baseline_protected'])
        q = old.candidate_probability(old.load(old.MODELS/f'fold_{f}/stack.npz'), old.stack.features(parents))
        x, candidate = old.gate_features(parents, q, current)
        assert x.shape == (1709,22)
        methods = dict(current_fusion=current)
        for arm in new.ARMS:
            scores = old.gate_probability(old.load(new.MODELS/f'fold_{f}/{arm}.npz'), x)
            methods[arm] = old.route(current, candidate, scores)
            all_scores[arm].append(scores)
        methods['prior_validation_selected'] = methods[spec['prior_validation_selected']]
        methods['validation_selected'] = methods[spec['validation_selected']]
        for name, pred in methods.items():
            assert np.array_equal(pred==base.CANCER, current==base.CANCER)
            if name in PRIOR_NAMES:
                assert all(int(pred[i])==expected_decisions[path]['predictions'][PRIOR_NAMES[name]][f] for i,path in enumerate(paths))
            decisions[name].append(pred)
        candidates.append(candidate)
    decisions = {name:np.asarray(values) for name,values in decisions.items()}
    all_scores = {arm:np.asarray(values) for arm,values in all_scores.items()}
    candidates = np.asarray(candidates)
    index = {path:i for i,path in enumerate(paths)}
    subsets = {}
    checks = 0
    for subset, items in p['subsets'].items():
        ids = np.asarray([index[path] for path in items])
        rows = [p['rows'][i] for i in ids]
        truth = np.asarray([base.CLASSES.index(row['label']) for row in rows])
        current = decisions['current_fusion'][:,ids]
        methods = {}
        for name, values in decisions.items():
            pred = values[:,ids]
            score = source.mean_metrics(pred, truth)
            score['corrected_per_fold'] = [int(((current[f]!=truth)&(pred[f]==truth)).sum()) for f in range(5)]
            score['broken_per_fold'] = [int(((current[f]==truth)&(pred[f]!=truth)).sum()) for f in range(5)]
            score['changed_per_fold'] = [int((current[f]!=pred[f]).sum()) for f in range(5)]
            score['wrong_to_wrong_per_fold'] = [int(((current[f]!=truth)&(pred[f]!=truth)&(pred[f]!=current[f])).sum()) for f in range(5)]
            for f in range(5):
                assert score['changed_per_fold'][f] == score['corrected_per_fold'][f]+score['broken_per_fold'][f]+score['wrong_to_wrong_per_fold'][f]
                if name in PRIOR_NAMES:
                    expected = expected_results['subsets'][subset]['methods'][PRIOR_NAMES[name]]['per_fold'][f]['confusion_matrix']
                    assert score['per_fold'][f]['confusion_matrix'] == expected, (subset,f,name)
                    checks += 1
            methods[name] = score
        subsets[subset] = dict(images=len(rows), source_groups=len({row['group'] for row in rows}),
            class_groups={label:len({row['group'] for row in rows if row['label']==label}) for label in base.CLASSES}, methods=methods)
    output = [dict(**row, predictions={name:values[:,i].tolist() for name,values in decisions.items()},
        gate_scores={arm:values[:,i].tolist() for arm,values in all_scores.items()},
        candidate_pred=candidates[:,i].tolist()) for i,row in enumerate(p['rows'])]
    base.write(HERE/'source_decisions.json', output)
    result = dict(status='complete_readonly_locked_matched_gate_transfer', unique_images=1709,
        paired_model_evaluations=5, subsets=subsets, protocol_sha256=base.sha(HERE/'protocol.json'),
        inference_started_utc=started, completed_utc=utc(), confidence_intervals_computed=False,
        uncertainty=p['uncertainty'], no_training=True, no_source_selection=True,
        global_5937_score_changed=False, serving_changed=False, registry_changed=False, limitations=p['limitations'])
    base.write(HERE/'results.json', result)
    verify(p)
    verification = dict(status='PASS', results_sha256=base.sha(HERE/'results.json'),
        decisions_sha256=base.sha(HERE/'source_decisions.json'), protocol_sha256=base.sha(HERE/'protocol.json'),
        all_input_sha_verified=True, source_image_sha_verified=1709, cache_count=15,
        reused_previous_gpu_fingerprint_forwards=240, new_gpu_forwards=0,
        prior_baseline_control_and_selected_confusion_matrices_matched=checks,
        all_prior_source_decisions_reproduced=True, exact_cancer_masks=True,
        locked_main_choices_unchanged=True, no_training_or_source_selection=True,
        no_new_confidence_intervals=True, scope='Calculation/provenance consistency; not independent clinical validation')
    assert checks == 75
    base.write(HERE/'verification.json', verification)
    for subset, values in subsets.items():
        print(subset, {name:{key:round(score['mean'][key]*100,4)
            for key in ['accuracy','macro_f1','macro_f1_present_classes']}
            for name,score in values['methods'].items()}, flush=True)
    print(verification, flush=True)


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        run(prepare())
