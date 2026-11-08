"""Fixed stacking transfer check on previously investigated source images.

No fitting, new routing policy, source-based selection or deployment. Each of
five original fold-specific pairs evaluates the SAME source images. Means over
the five paired evaluations are not a new five-fold source split or classifier.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

import run_teacher_logprob_stacking as stack
import evaluate_original_eight_resnet_transfer as transfer

base=stack.base
ROOT=base.ROOT
NAME='teacher_stack_transfer_seed42_20261023'
OUT=ROOT/'ai-service/reports'/NAME
METHODS=['current_fusion','logprob_stack','validation_selected']
HISTORY=ROOT/'ai-service/reports/original_eight_ensemble_teacher_pilot_fold0_seed42/protocol.json'


def utc():return datetime.now(timezone.utc).isoformat()


def aligned(paths,values,expected):
    paths,expected=list(paths),list(expected)
    values=np.asarray(values)
    if len(paths)!=len(set(paths)) or len(expected)!=len(set(expected)):
        raise ValueError('Duplicate image paths')
    if values.shape!=(len(paths),8) or set(paths)!=set(expected):
        raise ValueError('Cache images do not match source manifest')
    index={path:i for i,path in enumerate(paths)}
    values=values[[index[path] for path in expected]]
    if (not np.isfinite(values).all() or (values<0).any()
            or (values>1).any() or not np.allclose(values.sum(1),1,atol=1e-6)):
        raise ValueError('Invalid parent probabilities')
    return values


def mean_metrics(predictions,truth):
    predictions=np.asarray(predictions)
    if predictions.shape!=(5,len(truth)) or len(truth)==0:
        raise ValueError('Five paired evaluations of a nonempty source required')
    scores=[base.metrics(pred,truth) for pred in predictions]
    present=[label for label in base.CLASSES if scores[0]['per_class'][label]['support']>0]
    for score in scores:
        score['macro_f1_present_classes']=float(np.mean([score['per_class'][label]['f1'] for label in present]))
    keys=['accuracy','macro_f1','macro_recall','macro_f1_present_classes']
    return dict(per_fold=scores,mean={key:float(np.mean([s[key] for s in scores])) for key in keys},
        minimum={key:min(s[key] for s in scores) for key in keys},
        maximum={key:max(s[key] for s in scores) for key in keys},
        per_class={label:dict(support=scores[0]['per_class'][label]['support'],
            **{key:float(np.mean([s['per_class'][label][key] for s in scores])) for key in ['precision','recall','f1']}) for label in base.CLASSES},
        mean_cancer_flag_rate=float((predictions==base.CANCER).mean()),present_classes=present)


def paired_intervals(rows,baseline,candidate,truth):
    _,inverse=np.unique([r['group'] for r in rows],return_inverse=True)
    n_groups=int(inverse.max())+1
    counts=[]
    for predictions in [baseline,candidate]:
        cm=np.zeros((5,n_groups,64))
        for f in range(5):np.add.at(cm[f],(inverse,truth*8+predictions[f]),1)
        counts.append(cm)
    rng=np.random.default_rng(20261023)
    differences=[]
    for _ in range(10):
        draw=rng.multinomial(n_groups,np.full(n_groups,1/n_groups),size=100)
        scores=[]
        for count in counts:
            cm=np.einsum('bg,fgk->bfk',draw,count,optimize=True).reshape(100,5,8,8)
            tp=np.diagonal(cm,axis1=2,axis2=3)
            denominator=cm.sum(2)+cm.sum(3)
            f1=np.divide(2*tp,denominator,out=np.zeros_like(tp),where=denominator>0).mean(2).mean(1)
            accuracy=(tp.sum(2)/cm.sum((2,3))).mean(1)
            scores.append(np.column_stack([accuracy,f1]))
        differences.extend(scores[1]-scores[0])
    return {key:np.quantile(np.asarray(differences)[:,i],[.025,.975]).tolist()
            for i,key in enumerate(['accuracy','macro_f1'])}


def verify(p):
    for path,expected in p['frozen_sha256'].items():assert base.sha(ROOT/path)==expected,path


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');verify(p);return p
    registry=base.read(ROOT/'ai-service/reports/active_research_track.json')
    assert registry['active_track']=='original_eight' and registry['next_experiment'] is None
    sp=base.read(stack.OUT/'protocol.json');stack.previous.verify(sp)
    parent=base.read(ROOT/sp['parent_protocol']);stack.previous.verify(parent)
    assert base.read(stack.OUT/'independent_review.json')['status']=='PASS'
    tp=base.read(transfer.OUT/'protocol.json');audit=base.read(transfer.OUT/'audit.json')
    receipt=base.read(transfer.OUT/'verification.json')
    assert receipt['status']=='PASS' and receipt['protocol_sha256']==base.sha(transfer.OUT/'protocol.json')
    assert receipt['results_sha256']==base.sha(transfer.OUT/'results.json')
    assert receipt['predictions_sha256']==base.sha(transfer.OUT/'predictions.json')
    assert tp['audit_sha256']==base.sha(transfer.OUT/'audit.json')
    assert tp['classes']==base.CLASSES
    for member in tp['members']:assert base.sha(ROOT/member['path'])==member['sha256']
    fingerprint=base.read(OUT/'cache_forward_check.json')
    assert fingerprint['status']=='PASS' and fingerprint['checkpoints']==15
    assert fingerprint['old_protocol_sha256']==base.sha(transfer.OUT/'protocol.json')
    for check in fingerprint['checks']:
        assert base.sha(ROOT/check['cache'])==check['cache_sha256']
        assert base.sha(ROOT/check['checkpoint'])==check['checkpoint_sha256']
    history=base.read(HISTORY)
    role_by_path={}
    for role,items in [('historical_aux_train',[r for r in history['supplement'] if 'dermacon' in r['path']]),
                       ('historical_validation',history['splits']['dermacon_validation']),
                       ('historical_official_test',history['splits']['dermacon_official_test'])]:
        for item in items:
            assert item['path'] not in role_by_path
            role_by_path[item['path']]=(role,item)
    rows=[]
    for source,d in audit['sources'].items():
        for row in d['rows']:
            if not row['included']:continue
            if source=='dermacon_in':
                role,item=role_by_path[row['path']]
                assert (item['sha256'],item['label'])==(row['sha256'],row['label'])
            else:role='historical_transfer'
            rows.append(dict(path=row['path'],sha256=row['sha256'],label=row['label'],group=row['group'],
                             source=source,historical_role=role))
    assert len(rows)==len({r['path'] for r in rows})==1709
    original=list(parent['manifest'].values())
    assert {r['path'] for r in rows}.isdisjoint(r['path'] for r in original)
    assert {r['sha256'] for r in rows}.isdisjoint(r['sha256'] for r in original)
    for row in rows:assert base.sha(ROOT/row['path'])==row['sha256']
    subsets={
        'dermacon_all':[r['path'] for r in rows if r['source']=='dermacon_in'],
        **{f'dermacon_{role}':[r['path'] for r in rows if r['source']=='dermacon_in' and r['historical_role']==role]
           for role in ['historical_aux_train','historical_validation','historical_official_test']},
        'skindisnet_transfer':[r['path'] for r in rows if r['source']=='skindisnet_v2']}
    assert [len(paths) for paths in subsets.values()]==[986,590,213,183,723]
    split_groups={role:{r['group'] for r in rows if r['source']=='dermacon_in' and r['historical_role']==role}
                  for role in ['historical_aux_train','historical_validation','historical_official_test']}
    overlap={f'{a}__{b}':len(split_groups[a]&split_groups[b]) for a in split_groups for b in split_groups if a<b}
    assert not any(overlap.values())
    sources=[Path(__file__),Path(stack.__file__),Path(transfer.__file__),Path(base.__file__),
        ROOT/'ai-service/tests/test_teacher_stack_transfer.py',stack.OUT/'protocol.json',stack.OUT/'results.json',
        stack.OUT/'independent_review.json',ROOT/sp['parent_protocol'],HISTORY,base.SERVING,
        transfer.OUT/'protocol.json',transfer.OUT/'audit.json',transfer.OUT/'verification.json',
        transfer.OUT/'results.json',transfer.OUT/'predictions.json',OUT/'cache_forward_check.json']
    folds=[]
    for f in range(5):
        lock=base.read(stack.OUT/f'fold_{f}/selection_locked.json')
        assert lock['protocol_sha256']==base.sha(stack.OUT/'protocol.json')
        for path,expected in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==expected,path
        folds.append(dict(fold=f,baseline_protected=parent['folds'][f]['baseline_protected'],
            validation_selected=lock['selected'],reference_weights=tp['reference_weights'][f]))
        sources += [stack.OUT/f'fold_{f}/selection_locked.json',stack.MODELS/f'fold_{f}/stack.npz']
        sources += [transfer.OUT/f'fold_{f}_{architecture}.npz' for architecture in stack.PARENTS]
    p=dict(name=NAME,registered_utc=utc(),classes=base.CLASSES,unique_images=1709,rows=rows,subsets=subsets,folds=folds,
        frozen_sha256={path.relative_to(ROOT).as_posix():base.sha(path) for path in sources},
        model_checkpoint_sha256={member['path']:member['sha256'] for member in tp['members']},
        original_cohort=5937,source_patient_group_overlap_historical_roles=overlap,
        inference='Reuse immutable cached FP32 predictions for the exact same15 original CNN checkpoints and1709source images. Per fold reconstruct locked B0/ConvNeXt reference, current cancer-locked fusion and unchanged logprob stack head.',
        methods=METHODS,selection='No fitting, source thresholds, model/epoch/weight selection or adoption. Reuse the previously locked per-fold validation choice, which is baseline for all5.',
        summary='Report each paired fold-specific evaluation and arithmetic mean/min/max of its metrics on the SAME source images. Not a newly bagged classifier, five source folds or five independent seeds. Never pool1709x5 rows as independent images.',
        primary_slice='dermacon_historical_official_test:183 previously inspected source test-role images, seven supported classes, no Lupus. Not an independent new test.',
        secondary_slices=list(subsets),bootstrap='1000 paired resamples of canonical source groups, seed20261023. Each sampled group shared across both methods AND all5fold pairs; CI of mean-over-fold Accuracy/MacroF1 deltas, not clinical/multiple-testing adjusted.',
        duplicate_audit='Reuse frozen completed dHash<=3/SHA audit against5937 development images; verify source image bytes unchanged. No excluded rows reinstated.',
        limitations=['Both sources previously investigated and informed research; not fresh independent confirmation.',
            '590 DermaCon images trained other historical pilot candidates,213 selected prior candidates,183 source test role previously examined. The15specific parent CNNs and5stack heads in this check did not train on these1709images.',
            'Current parent checkpoint and stack metadata are from one training seed; overlapping CNN train folds are not independent replications.',
            'Original-cohort patient identifiers unavailable. Image duplicate audit cannot prove patient independence across sources.',
            'DermaCon all has11Lupus images/four source groups and17SkinCancer images/11groups. Its183source test-role slice has no Lupus and6SkinCancer images.',
            'SkinDisNet source supports only Eczema/Tinea; keep eight-way predictions. Report fixed8class MacroF1 AND mean F1 over supported truth classes with explicit names; neither is full8class clinical accuracy.',
            'Preserving every baseline cancer call also preserves existing cancer errors.',
            'Subsets overlap: all986 includes590/213/183. Do not sum subset counts or pool cross-source accuracy.'],
        references=['https://papers.nips.cc/paper_files/paper/2025/file/a2c548b2ed3141400d86a235eaa6fad0-Paper-Datasets_and_Benchmarks_Track.pdf'],
        serving_changed=False,baseline_changed=False)
    base.write(OUT/'protocol.json',p);base.write(OUT/'research_registry_before.json',registry)
    base.write(OUT/'status.json',dict(state='registered',utc=utc()))
    registry['next_experiment']=OUT.relative_to(ROOT).as_posix()
    registry['next_experiment_status']='registered_frozen_stacking_source_transfer_check'
    base.write(ROOT/'ai-service/reports/active_research_track.json',registry)
    print(json.dumps(dict(registered=True,images=len(rows),subsets={k:len(v) for k,v in subsets.items()})),flush=True)
    return p


def run(p):
    assert not (OUT/'results.json').exists(),'Preserve completed transfer check'
    verify(p)
    for path,expected in p['model_checkpoint_sha256'].items():assert base.sha(ROOT/path)==expected
    base.write(OUT/'status.json',dict(state='evaluating_locked_models',utc=utc()))
    paths=[r['path'] for r in p['rows']]
    raw={};decisions={name:[] for name in METHODS};all_old=[]
    for f,spec in enumerate(p['folds']):
        pp=[]
        for architecture in stack.PARENTS:
            with np.load(transfer.OUT/f'fold_{f}_{architecture}.npz',allow_pickle=False) as cached:
                assert cached['protocol_sha256'].item()==base.sha(transfer.OUT/'protocol.json')
                pp.append(aligned(cached['paths'].tolist(),cached['probabilities'],paths))
            raw[(f,architecture)]=pp[-1]
        reference=transfer.classwise_blend(pp[0],pp[1],np.asarray(spec['reference_weights']))
        all_old.append(reference)
        current=base.decide(reference,pp[2],spec['baseline_protected'])
        head_probability=stack.saved_probability(stack.MODELS/f'fold_{f}/stack.npz',stack.features(pp))
        proposed=stack.route(current,head_probability)
        values=dict(current_fusion=current,logprob_stack=proposed)
        values['validation_selected']=values[spec['validation_selected']]
        for name,pred in values.items():
            assert np.array_equal(pred==base.CANCER,current==base.CANCER)
            decisions[name].append(pred)
    # Reproduce the old transfer's probability averages as an input-cache check.
    old_rows=base.read(transfer.OUT/'predictions.json')
    assert [r['path'] for r in old_rows]==paths
    aggregate=transfer.aggregate(raw,[s['reference_weights'] for s in p['folds']])
    for method,pp in aggregate.items():
        assert np.allclose(pp,np.asarray([row['probabilities'][method] for row in old_rows]),atol=1e-12,rtol=0),method
    decisions={name:np.asarray(pred) for name,pred in decisions.items()}
    index={path:i for i,path in enumerate(paths)}
    results={}
    for subset,items in p['subsets'].items():
        ids=np.asarray([index[path] for path in items])
        rows=[p['rows'][i] for i in ids]
        truth=np.asarray([base.CLASSES.index(row['label']) for row in rows])
        methods={}
        for name,pred in decisions.items():
            methods[name]=mean_metrics(pred[:,ids],truth)
            methods[name]['paired_delta_95pct']=paired_intervals(rows,decisions['current_fusion'][:,ids],pred[:,ids],truth)
            methods[name]['corrected_per_fold']=[int(((decisions['current_fusion'][f,ids]!=truth)&(pred[f,ids]==truth)).sum()) for f in range(5)]
            methods[name]['broken_per_fold']=[int(((decisions['current_fusion'][f,ids]==truth)&(pred[f,ids]!=truth)).sum()) for f in range(5)]
        results[subset]=dict(images=len(rows),source_groups=len({r['group'] for r in rows}),
            class_groups={label:len({r['group'] for r in rows if r['label']==label}) for label in base.CLASSES},methods=methods)
    output=[dict(**row,predictions={name:pred[:,i].tolist() for name,pred in decisions.items()}) for i,row in enumerate(p['rows'])]
    base.write(OUT/'source_decisions.json',output)
    result=dict(status='complete_exploratory_frozen_transfer',unique_images=1709,paired_model_evaluations=5,
        subsets=results,protocol_sha256=base.sha(OUT/'protocol.json'),completed_utc=utc(),
        global_5937_score_changed=False,serving_changed=False,limitations=p['limitations'])
    base.write(OUT/'results.json',result);verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),
        decisions_sha256=base.sha(OUT/'source_decisions.json'),previous_cache_aggregates_reproduced=True,
        baseline_cancer_masks_preserved=True,no_training_or_source_selection=True,
        scope='Calculation/provenance only, not clinical validation'))
    base.write(OUT/'status.json',dict(state='complete',utc=utc()))
    print(json.dumps({subset:{name:score['mean'] for name,score in values['methods'].items()}
        for subset,values in results.items()}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    with threadpool_limits(limits=1):
        p=prepare()
        if not args.prepare_only:run(p)


if __name__=='__main__':main()
