"""Apply locked keep/stack gates to previously investigated source caches.

This child check performs no fitting or source selection and writes only here.
Five fold-specific systems evaluate the same 1709 images; mean metrics are not
a new bagged classifier, source cross-validation or independent clinical test.
"""
from datetime import datetime, timezone
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'ai-service/training'))
import run_teacher_conservative_gate as gate
import evaluate_teacher_stack_transfer as prior

base = gate.base
METHODS = ['current_fusion', 'raw_stack', 'conservative_gate', 'validation_selected']


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
    source_path = prior.OUT/'protocol.json'
    source = base.read(source_path)
    prior.verify(source)
    assert base.read(prior.OUT/'independent_review.json')['status'] == 'PASS'
    main_p = base.read(gate.OUT/'protocol.json')
    gate.original.verify(main_p)
    main_result = base.read(gate.OUT/'results.json')
    main_receipt = base.read(gate.OUT/'verification.json')
    assert base.read(gate.OUT/'independent_review.json')['status'] == 'PASS'
    assert main_receipt['results_sha256'] == base.sha(gate.OUT/'results.json')
    assert main_receipt['decisions_sha256'] == base.sha(gate.OUT/'oof_decisions.json')
    assert main_result['protocol_sha256'] == base.sha(gate.OUT/'protocol.json')
    fingerprint_path = prior.OUT/'cache_forward_check.json'
    fingerprint = base.read(fingerprint_path)
    assert fingerprint['status'] == 'PASS'
    assert fingerprint['checkpoints'] == 15 and fingerprint['image_forwards'] == 240
    assert len(fingerprint['checks']) == 15
    extra = [Path(__file__), Path(prior.__file__), Path(gate.__file__), Path(gate.stack.__file__),
        Path(base.__file__), Path(prior.transfer.__file__), source_path, prior.OUT/'results.json',
        prior.OUT/'verification.json', prior.OUT/'independent_review.json', fingerprint_path,
        gate.OUT/'protocol.json', gate.OUT/'results.json', gate.OUT/'verification.json',
        gate.OUT/'independent_review.json', gate.OUT/'all_selections_locked.json']
    frozen = {**source['frozen_sha256'], **source['model_checkpoint_sha256'], **main_p['frozen_sha256']}
    folds = []
    boundary = base.read(gate.OUT/'all_selections_locked.json')
    assert boundary['locked_utc'] <= main_result['outer_started_utc']
    for f, old in enumerate(source['folds']):
        lock_path = gate.OUT/f'fold_{f}/selection_locked.json'
        lock = base.read(lock_path)
        assert boundary['selections_sha256'][str(f)] == base.sha(lock_path)
        assert lock['protocol_sha256'] == base.sha(gate.OUT/'protocol.json')
        assert lock['selected'] == main_result['per_fold'][f]['selected']
        assert lock['selected'] in ['current_fusion', 'conservative_gate']
        folds.append(dict(fold=f, baseline_protected=old['baseline_protected'],
            reference_weights=old['reference_weights'], validation_selected=lock['selected']))
        extra += [lock_path, gate.MODELS/f'fold_{f}/stack.npz', gate.MODELS/f'fold_{f}/gate.npz']
    for check in fingerprint['checks']:
        assert base.sha(ROOT/check['cache']) == check['cache_sha256']
        assert base.sha(ROOT/check['checkpoint']) == check['checkpoint_sha256']
        frozen[check['cache']] = check['cache_sha256']
        frozen[check['checkpoint']] = check['checkpoint_sha256']
    frozen.update({path.relative_to(ROOT).as_posix(): base.sha(path) for path in extra})
    p = dict(name='locked_conservative_gate_source_transfer_check', registered_utc=utc(),
        parent_experiment=gate.OUT.relative_to(ROOT).as_posix(),
        source_protocol=source_path.relative_to(ROOT).as_posix(),
        classes=base.CLASSES, unique_images=1709, rows=source['rows'], subsets=source['subsets'],
        folds=folds, methods=METHODS, frozen_sha256=frozen,
        inference='Reuse the same15 frozen original CNN probability caches on the same1709 source images. Apply locked fresh stack and gate per fold, unchanged22features and strictscore>2/3. Use mainexperiment inner-validation-selected gate only where already locked; no source selection.',
        summary='Report each of5 fold-specific evaluations and arithmetic mean/min/max on the SAME images. Not5 source folds, independent seeds,1709x5 independent images or a new probability-averaged classifier.',
        reused_forward_receipt=dict(path=fingerprint_path.relative_to(ROOT).as_posix(),
            sha256=base.sha(fingerprint_path), checkpoints=15, image_forwards=240,
            distinct_images=fingerprint['distinct_images'], new_gpu_forwards=0),
        uncertainty='No new confidence intervals computed in this child check; no significance or clinical improvement claim.',
        controls='Every subset/fold baseline CM and raw stack CM must match the prior locked stack source-check results. Exact Cancer binary prediction mask retained for allmethods.',
        no_training=True, no_calibration=True, no_source_selection=True, no_threshold_change=True,
        registry_changed=False, global_5937_score_changed=False, serving_changed=False,
        limitations=source['limitations']+[
            'This is a read-only source application of the already-locked conservative gate, not a fresh independent clinical test or a new training experiment.',
            'The final gate was trained on original inner-validation cross-predictions, not source labels; source outcomes never choose gate/threshold/fold.',
            'No confidence intervals added here. Report fixed8class MacroF1 and support-class MacroF1 with their denominators.'])
    verify(p)
    base.write(HERE/'protocol.json',p)
    return p


def run(p):
    assert not (HERE/'results.json').exists(), 'Preserve completed transfer results'
    verify(p)
    paths = [row['path'] for row in p['rows']]
    old_results = base.read(prior.OUT/'results.json')
    decisions = {name: [] for name in METHODS}
    all_scores = []
    started = utc()
    assert p['registered_utc'] <= started
    for f, spec in enumerate(p['folds']):
        parents = []
        for architecture in gate.stack.PARENTS:
            cache = prior.transfer.OUT/f'fold_{f}_{architecture}.npz'
            with np.load(cache, allow_pickle=False) as values:
                assert values['protocol_sha256'].item() == base.sha(prior.transfer.OUT/'protocol.json')
                parents.append(prior.aligned(values['paths'].tolist(),values['probabilities'],paths))
        reference = prior.transfer.classwise_blend(parents[0],parents[1],np.asarray(spec['reference_weights']))
        current = base.decide(reference,parents[2],spec['baseline_protected'])
        stack_model = gate.load(gate.MODELS/f'fold_{f}/stack.npz')
        q = gate.candidate_probability(stack_model,gate.stack.features(parents))
        features,raw = gate.gate_features(parents,q,current)
        score = gate.gate_probability(gate.load(gate.MODELS/f'fold_{f}/gate.npz'),features)
        gated = gate.route(current,raw,score)
        methods = dict(current_fusion=current,raw_stack=raw,conservative_gate=gated)
        methods['validation_selected'] = methods[spec['validation_selected']]
        for name, pred in methods.items():
            assert np.array_equal(pred==base.CANCER,current==base.CANCER)
            decisions[name].append(pred)
        all_scores.append(score)
    decisions = {name:np.asarray(predictions) for name,predictions in decisions.items()}
    all_scores = np.asarray(all_scores)
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
            score = prior.mean_metrics(pred,truth)
            score['corrected_per_fold'] = [int(((current[f]!=truth)&(pred[f]==truth)).sum()) for f in range(5)]
            score['broken_per_fold'] = [int(((current[f]==truth)&(pred[f]!=truth)).sum()) for f in range(5)]
            score['changed_per_fold'] = [int((current[f]!=pred[f]).sum()) for f in range(5)]
            score['wrong_to_wrong_per_fold'] = [int(((current[f]!=truth)&(pred[f]!=truth)&(pred[f]!=current[f])).sum()) for f in range(5)]
            for f in range(5):
                assert score['changed_per_fold'][f] == score['corrected_per_fold'][f]+score['broken_per_fold'][f]+score['wrong_to_wrong_per_fold'][f]
                if name in ['current_fusion','raw_stack']:
                    prior_name = 'logprob_stack' if name=='raw_stack' else name
                    expected = old_results['subsets'][subset]['methods'][prior_name]['per_fold'][f]['confusion_matrix']
                    assert score['per_fold'][f]['confusion_matrix'] == expected, (subset,f,name)
                    checks += 1
            methods[name] = score
        subsets[subset] = dict(images=len(rows), source_groups=len({row['group'] for row in rows}),
            class_groups={label:len({row['group'] for row in rows if row['label']==label}) for label in base.CLASSES}, methods=methods)
    output = [dict(**row,predictions={name:values[:,i].tolist() for name,values in decisions.items()},
        gate_score=all_scores[:,i].tolist(),candidate_pred=decisions['raw_stack'][:,i].tolist()) for i,row in enumerate(p['rows'])]
    base.write(HERE/'source_decisions.json',output)
    result = dict(status='complete_readonly_locked_gate_transfer',unique_images=1709,
        paired_model_evaluations=5,subsets=subsets,protocol_sha256=base.sha(HERE/'protocol.json'),
        inference_started_utc=started,completed_utc=utc(),confidence_intervals_computed=False,
        uncertainty=p['uncertainty'],no_training=True,no_source_selection=True,
        global_5937_score_changed=False,serving_changed=False,registry_changed=False,limitations=p['limitations'])
    base.write(HERE/'results.json',result)
    verify(p)
    verification = dict(status='PASS',results_sha256=base.sha(HERE/'results.json'),
        decisions_sha256=base.sha(HERE/'source_decisions.json'),protocol_sha256=base.sha(HERE/'protocol.json'),
        all_input_sha_verified=True,source_image_sha_verified=1709,cache_count=15,
        reused_previous_gpu_fingerprint_forwards=240,new_gpu_forwards=0,
        prior_baseline_and_stack_confusion_matrices_matched=checks,
        exact_cancer_masks=True,locked_main_choices_unchanged=True,no_training_or_source_selection=True,
        no_new_confidence_intervals=True,scope='Calculation/provenance consistency; not independent clinical validation')
    base.write(HERE/'verification.json',verification)
    for subset, values in subsets.items():
        print(subset,{name:{key:round(score['mean'][key]*100,4) for key in ['accuracy','macro_f1','macro_f1_present_classes']}
            for name,score in values['methods'].items()},flush=True)
    print(verification,flush=True)


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        run(prepare())
