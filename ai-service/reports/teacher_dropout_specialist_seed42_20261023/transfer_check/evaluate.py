"""Read-only source application of already locked hidden-dropout specialists.

Five paired original-fold systems evaluate the SAME 1709 historically studied
photos. This is neither five new source splits nor an averaged classifier.
"""
from datetime import datetime, timezone
from pathlib import Path
import sys

import numpy as np
import torch
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'ai-service/training'))
import run_teacher_dropout_specialist as new
import run_teacher_priorities_ensemble_specialist as features
import evaluate_teacher_stack_transfer as source

base = new.base
PRIOR = ROOT/'ai-service/reports/teacher_macro_f1_gate_seed42_20261023/transfer_check'
METHODS = ['original_fusion', 'current_gate', 'dropout_control',
           'dropout_specialist', 'validation_selected']


def utc():
    return datetime.now(timezone.utc).isoformat()


def verify(p):
    for path, expected in p['frozen_sha256'].items():
        assert base.sha(ROOT/path) == expected, path
    for row in p['rows']:
        assert base.sha(ROOT/row['path']) == row['sha256'], row['path']


def prepare():
    if (HERE/'protocol.json').exists():
        p = base.read(HERE/'protocol.json'); verify(p); return p
    main = base.read(new.OUT/'protocol.json'); new.prior.verify(main)
    result = base.read(new.OUT/'results.json')
    receipt = base.read(new.OUT/'verification.json')
    assert receipt['status'] == 'PASS'
    assert receipt['results_sha256'] == base.sha(new.OUT/'results.json')
    prior = base.read(PRIOR/'protocol.json')
    for receipt_name in ['verification.json','independent_review.json']:
        r = base.read(PRIOR/receipt_name)
        assert r['status'] == 'PASS'
        assert r['results_sha256'] == base.sha(PRIOR/'results.json')
    assert base.read(PRIOR/'verification.json')['decisions_sha256'] == base.sha(PRIOR/'source_decisions.json')
    locks = base.read(new.OUT/'all_selections_locked.json')
    assert locks['locked_utc'] <= result['outer_started_utc']
    extra = [Path(__file__), Path(new.__file__), Path(new.previous.__file__),
             Path(features.__file__), ROOT/'ai-service/training/common.py', Path(source.__file__),
             new.OUT/'protocol.json', new.OUT/'results.json', new.OUT/'verification.json',
             new.OUT/'all_selections_locked.json', PRIOR/'protocol.json', PRIOR/'results.json',
             PRIOR/'verification.json', PRIOR/'independent_review.json', PRIOR/'source_decisions.json']
    folds = []
    frozen = {**prior['frozen_sha256'], **main['frozen_sha256']}
    for f in range(5):
        lock_path = new.OUT/f'fold_{f}/selection_locked.json'
        assert locks['selections_sha256'][str(f)] == base.sha(lock_path)
        lock = base.read(lock_path)
        assert lock['selected'] in ['current_gate', *new.ARMS]
        assert lock['selected'] == result['per_fold'][f]['selected']
        for path, expected in lock['artifacts_sha256'].items():
            assert base.sha(ROOT/path) == expected, path
        cp = features.checkpoint(f)
        old_cache = source.transfer.OUT/f'fold_{f}_resnet50.npz'
        extra += [lock_path, cp, old_cache, new.OUT/f'fold_{f}/scaler.npz',
                  *[new.MODELS/f'fold_{f}/{arm}/best_model.pth' for arm in new.ARMS]]
        folds.append(dict(fold=f, validation_selected=lock['selected'],
                          checkpoint=cp.relative_to(ROOT).as_posix(),
                          reference_probability_cache=old_cache.relative_to(ROOT).as_posix()))
    assert [s['fold'] for s in folds if s['validation_selected']=='dropout_specialist'] == [1,2]
    frozen.update({p.relative_to(ROOT).as_posix():base.sha(p) for p in extra})
    p = dict(name='locked_dropout_specialist_source_transfer_check', registered_utc=utc(),
        parent_experiment=new.OUT.relative_to(ROOT).as_posix(), classes=base.CLASSES,
        rows=prior['rows'], subsets=prior['subsets'], unique_images=1709,
        methods=METHODS, folds=folds, frozen_sha256=frozen,
        inference='Extract original fold ResNet50 eval FP32 frozen 2048 avgpool features, batch16, original evaluation_transform. Compare all original 8-class probabilities against frozen prior cache, absolute tolerance 2e-6. Apply fixed original-train scaler and chosen best five-way head in eval mode (dropout disabled). Route only pre-existing specialist scope at unchanged >=0.8 confidence. Keep exact Cancer prediction mask.',
        feature_cache='New fold_{f}_resnet_features.npz stores all1709 paths/features/original8probabilities and this protocol SHA. No cache changes after verification.',
        summary='Each SAME source photo is evaluated by five existing fold-specific systems. Report per-fold and arithmetic mean/min/max metrics, not five new source folds, independent seeds,8545 independent photos or a new bagged classifier.',
        controls='Original fusion and current_gate predictions and all corresponding source confusion matrices must exactly match preceding Macro-F1 source check. Locked source application does not select checkpoints, folds, thresholds, dropout or calibration.',
        uncertainty='No confidence intervals or significance claim. These historically studied sources are not a new independent clinical test.',
        no_training=True, no_calibration=True, no_source_selection=True,
        no_threshold_change=True, serving_changed=False, registry_changed=False,
        limitations=prior['limitations']+[
            'DermaCon986 includes590 historical auxiliary train photos,213 historical validation photos,183 official test photos. Those historical roles refer to previous work, not training this current head.',
            'Current original-train-only specialists and their ResNet backbones do not fit these source photos; historical project exposure still prevents a fresh confirmatory test claim.',
            'SkinDisNet723 contains Eczema/Tinea only; official DermaCon183 contains no Lupus and only6 SkinCancer. Report fixed8 and truth-supported class MacroF1 explicitly.',
            'Single frozen CNN seed, incomplete patient IDs and repeated source exploration remain. No source result changes main5937OOF policy.'])
    verify(p); base.write(HERE/'protocol.json', p)
    return p


def feature_cache(p, f):
    path = HERE/f'fold_{f}_resnet_features.npz'
    rows = p['rows']; paths = [r['path'] for r in rows]
    if not path.exists():
        assert torch.cuda.is_available(), 'Frozen feature extractor requires CUDA'
        started = utc()
        extractor = features.Extractor(f)
        try:
            x, probability = extractor.infer(rows)
        finally:
            extractor.close()
        np.savez_compressed(path, paths=paths, features=x, probabilities=probability,
                            protocol_sha256=base.sha(HERE/'protocol.json'), started_utc=started)
    with np.load(path, allow_pickle=False) as z:
        assert z['paths'].tolist() == paths
        assert z['protocol_sha256'].item() == base.sha(HERE/'protocol.json')
        assert p['registered_utc'] <= str(z['started_utc'].item())
        x, probability = z['features'].copy(), z['probabilities'].copy()
    assert x.shape == (1709,2048) and x.dtype == np.float32 and np.isfinite(x).all()
    spec = p['folds'][f]
    with np.load(ROOT/spec['reference_probability_cache'], allow_pickle=False) as z:
        reference = source.aligned(z['paths'].tolist(), z['probabilities'], paths)
    error = float(np.max(np.abs(probability-reference)))
    assert error <= 2e-6, (f,error)
    receipt = dict(fold=f, images=len(paths), checkpoint=spec['checkpoint'],
        checkpoint_sha256=base.sha(ROOT/spec['checkpoint']), cache=path.relative_to(ROOT).as_posix(),
        cache_sha256=base.sha(path), original_probability_cache=spec['reference_probability_cache'],
        original_probability_max_absolute_error=error, tolerance=2e-6,
        precision='eval FP32', new_image_forwards=1709, protocol_before_forward=True)
    print(dict(fold=f, feature_images=1709, original_probability_error=error), flush=True)
    return x, receipt


def run(p):
    assert not (HERE/'results.json').exists(), 'Preserve completed source check'
    verify(p); started = utc()
    old_decisions = {r['path']:r for r in base.read(PRIOR/'source_decisions.json')}
    expected_results = base.read(PRIOR/'results.json')
    paths = [r['path'] for r in p['rows']]
    decisions = {name:[] for name in METHODS}; probabilities = {a:[] for a in new.ARMS}
    checks = []
    for f, spec in enumerate(p['folds']):
        raw, receipt = feature_cache(p, f); checks.append(receipt)
        with np.load(new.OUT/f'fold_{f}/scaler.npz', allow_pickle=False) as z:
            x = torch.from_numpy(((raw-z['mean'])/z['scale']).astype(np.float32))
        current = np.array([old_decisions[path]['predictions']['validation_selected'][f] for path in paths])
        methods = dict(original_fusion=np.array([old_decisions[path]['predictions']['current_fusion'][f] for path in paths]),
                       current_gate=current)
        for arm in new.ARMS:
            model = new.Head(0. if arm=='dropout_control' else .5)
            checkpoint = torch.load(new.MODELS/f'fold_{f}/{arm}/best_model.pth', map_location='cpu', weights_only=False)
            assert checkpoint['protocol_sha256'] == base.sha(new.OUT/'protocol.json')
            model.load_state_dict(checkpoint['model_state_dict']); model.eval()
            q = new.probability(model,x)
            assert q.shape == (1709,5) and np.allclose(q.sum(1),1,atol=1e-6)
            assert not model.training and not model.dropout.training
            methods[arm] = new.previous.route(current,q); probabilities[arm].append(q)
        methods['validation_selected'] = methods[spec['validation_selected']]
        for name, pred in methods.items():
            assert np.array_equal(pred==base.CANCER,current==base.CANCER)
            decisions[name].append(pred)
    decisions = {k:np.asarray(v) for k,v in decisions.items()}
    probabilities = {k:np.asarray(v) for k,v in probabilities.items()}
    index = {path:i for i,path in enumerate(paths)}; subsets = {}; matched=0
    for subset, items in p['subsets'].items():
        ids = np.array([index[path] for path in items]); rows=[p['rows'][i] for i in ids]
        truth = np.array([base.CLASSES.index(row['label']) for row in rows])
        current = decisions['current_gate'][:,ids]; methods={}
        for name, values in decisions.items():
            pred = values[:,ids]; score=source.mean_metrics(pred,truth)
            score['corrected_per_fold']=[int(((current[f]!=truth)&(pred[f]==truth)).sum()) for f in range(5)]
            score['broken_per_fold']=[int(((current[f]==truth)&(pred[f]!=truth)).sum()) for f in range(5)]
            score['changed_per_fold']=[int((current[f]!=pred[f]).sum()) for f in range(5)]
            score['wrong_to_wrong_per_fold']=[int(((current[f]!=truth)&(pred[f]!=truth)&(pred[f]!=current[f])).sum()) for f in range(5)]
            for f in range(5):
                assert score['changed_per_fold'][f] == sum(score[k][f] for k in ['corrected_per_fold','broken_per_fold','wrong_to_wrong_per_fold'])
                if name in ['original_fusion','current_gate']:
                    previous_name = 'current_fusion' if name=='original_fusion' else 'validation_selected'
                    assert score['per_fold'][f]['confusion_matrix'] == expected_results['subsets'][subset]['methods'][previous_name]['per_fold'][f]['confusion_matrix']
                    matched+=1
            methods[name]=score
        subsets[subset]=dict(images=len(rows),source_groups=len({r['group'] for r in rows}),
            class_groups={label:len({r['group'] for r in rows if r['label']==label}) for label in base.CLASSES}, methods=methods)
    output = [dict(**row,predictions={name:values[:,i].tolist() for name,values in decisions.items()},
                   head_probabilities={arm:values[:,i].tolist() for arm,values in probabilities.items()})
              for i,row in enumerate(p['rows'])]
    base.write(HERE/'source_decisions.json',output)
    result=dict(status='complete_readonly_locked_dropout_specialist_transfer',unique_images=1709,
        paired_model_evaluations=5,subsets=subsets,protocol_sha256=base.sha(HERE/'protocol.json'),
        inference_started_utc=started,completed_utc=utc(),confidence_intervals_computed=False,
        uncertainty=p['uncertainty'],no_training=True,no_source_selection=True,
        serving_changed=False,registry_changed=False,global_5937_score_changed=False,limitations=p['limitations'])
    base.write(HERE/'results.json',result); verify(p)
    assert matched==50
    base.write(HERE/'verification.json',dict(status='PASS',results_sha256=base.sha(HERE/'results.json'),
        decisions_sha256=base.sha(HERE/'source_decisions.json'),protocol_sha256=base.sha(HERE/'protocol.json'),
        all_input_sha_verified=True,source_image_sha_verified=1709,new_image_forwards=8545,
        new_frozen_resnet_feature_caches=5,feature_cache_checks=checks,
        original_and_current_confusion_matrices_matched=matched,exact_cancer_masks=True,
        all_five_selections_locked_before_source_forward=True,no_training_or_source_selection=True,
        no_new_confidence_intervals=True,scope='Calculation and provenance consistency, not independent clinical validation'))
    for subset,values in subsets.items():
        print(subset,{n:{k:round(s['mean'][k]*100,4) for k in ['accuracy','macro_f1','macro_f1_present_classes']}
                      for n,s in values['methods'].items()},flush=True)


if __name__=='__main__':
    torch.set_num_threads(2)
    with threadpool_limits(limits=2):
        run(prepare())
