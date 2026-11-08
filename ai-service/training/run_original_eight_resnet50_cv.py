"""Complete original-eight ResNet CV without changing the pilot's selection rule.

Fold0 reuses the verified pilot; four additional ImageNet-initialized models.
Report guarded validation selection, fixed secondary recipes, and fold1-4
replication separately. Never replace a choice using its outer test scores.
"""
import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import torch

import pilot_original_eight_resnet50 as pilot
from common import CLASSES,save_json,sha256_file
from prepare_scene_grouped_oof_inner_splits import checked_outer_rows,OUTPUT as INNER
from prepare_scene_grouped_oof_folds import OUTPUT as OUTER
from evaluate_scene_grouped_oof_ensemble import ARCHITECTURES,RUN_ROOT,read_probabilities,score
from evaluate_scene_grouped_oof_classwise_fusion import aligned_inner_predictions,choose_class_weights,classwise_blend

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'ai-service/reports/original_eight_resnet50_cv_seed42'
F0=ROOT/'ai-service/reports/original_eight_resnet50_pilot_fold0_seed42'
F0MODEL=ROOT/'ai-service/candidates/original_eight_resnet50_pilot_fold0_seed42'
PARENTS=pilot.PARENTS; NEW=pilot.NEW; REFERENCE=pilot.REFERENCE


def read(path): return json.loads(path.read_text(encoding='utf-8'))


def register():
    state=read(ROOT/'ai-service/reports/active_research_track.json')
    assert state['active_track']=='original_eight' and state['classes']==CLASSES
    assert read(F0/'verification.json')['status']=='PASS'
    outer,samples,_=checked_outer_rows(); inner=read(INNER); by_path={r['path']:r for r in outer['images']}
    folds=[]; roles_by_fold={}
    for f,plan in enumerate(inner['folds']):
        assert plan['outer_fold']==f
        validation=set(plan['inner_validation_paths']); roles={r:[] for r in ('train','inner_validation','outer_holdout')}
        for sample in samples:
            path=sample.path.relative_to(ROOT).as_posix(); row=by_path[path]
            role='outer_holdout' if row['fold']==f else ('inner_validation' if path in validation else 'train')
            roles[role].append(sample)
        for role,items in roles.items(): assert len(items)==plan[role+'_images']
        groups={r:{s.group_id or s.digest for s in items} for r,items in roles.items()}
        for a,b in [('train','inner_validation'),('train','outer_holdout'),('inner_validation','outer_holdout')]: assert groups[a].isdisjoint(groups[b])
        paths={r:[s.path.relative_to(ROOT).as_posix() for s in items] for r,items in roles.items()}
        assert paths['inner_validation']==plan['inner_validation_paths']
        roles_by_fold[f]=roles; folds.append(dict(fold=f,roles=paths))
    assert folds[0]['roles']==read(F0/'protocol.json')['roles']
    sources={}
    for f in range(5):
        for m in PARENTS:
            directory=RUN_ROOT/ARCHITECTURES[m].format(fold=f)
            for n in ('best_model.pth','inner_predictions.json','oof_predictions.json','selection_report.json','dataset_summary.json'):
                p=directory/n; sources[str(p.relative_to(ROOT))]=sha256_file(p)
    for p in [F0/n for n in ('protocol.json','selection_locked.json','validation_predictions.npz','test_predictions.json','results.json','verification.json')]+[
              F0MODEL/n for n in ('best_model.pth','selection_report.json','history.json')]: sources[str(p.relative_to(ROOT))]=sha256_file(p)
    parent=ROOT/'ai-service/reports/scene_grouped_oof_classwise_fusion_seed42.json'
    dependencies=('run_original_eight_resnet50_cv.py','pilot_original_eight_resnet50.py','common.py','train_v2.py',
                  'prepare_scene_grouped_oof_inner_splits.py','evaluate_scene_grouped_oof_ensemble.py','evaluate_scene_grouped_oof_classwise_fusion.py')
    protocol=dict(status='registered_original_eight_three_architecture_cv_internal_research',classes=CLASSES,folds=folds,configuration=pilot.CONFIG,
        outer_manifest_sha256=sha256_file(OUTER),inner_plan_sha256=sha256_file(INNER),manifest_content_sha256=outer['manifest_sha256'],
        benchmark_sha256=sha256_file(parent),pretrained_sha256=read(F0/'protocol.json')['pretrained_sha256'],sources=sources,
        code_sha256={n:sha256_file(ROOT/'ai-service/training'/n) for n in dependencies},
        initialization='Each new fold ResNet starts from torchvision ImageNetV2 seed42; no skin-trained weights shared across folds. Fold0 is exact verified reuse.',
        checkpoint_selection=read(F0/'protocol.json')['checkpoint_selection'],family=read(F0/'protocol.json')['family'],
        guard=read(F0/'protocol.json')['guard'],fusion_selection=read(F0/'protocol.json')['fusion_selection'],
        primary='Same guarded validation selector as pilot, compared with original B0/ConvNeXt classwise reference on5937unique clinical+SCIN development photos.',
        secondary='All nine preset recipes; fixed75% original reference+25% ResNet is a replication hypothesis after observing fold0. Report full5fold and folds1-4 excluding hypothesis-generation fold0. Never call test-best recipe validation-selected.',
        warning_handling='Suppress only optimizer-step-wrapper scheduler bookkeeping warning; optimizer updates/AMP skips remain recorded. Mathematical training recipe unchanged.',
        limitations=['All original development data/parent results have been studied; no independent external test.',
                      'Fold0 ResNet outcomes informed this follow-up. Fold1-4 new ResNet outcomes are unseen at registration.',
                      'One seed; case/scene groups do not establish unknown patient independence.',
                      'No new-eight datasets/models, relabeling, serving changes or retrospective weight-grid expansion.'])
    if (OUT/'protocol.json').exists(): assert read(OUT/'protocol.json')==protocol,'Preserve registered CV'
    else: save_json(OUT/'protocol.json',protocol)
    return outer,inner,roles_by_fold,protocol


def run_fold(outer,inner,roles,protocol,f):
    directory=OUT/f'fold_{f}'
    if f==0:
        save_json(directory/'reuse.json',dict(source=str(F0.relative_to(ROOT)),protocol_sha256=sha256_file(OUT/'protocol.json'),
                                           source_verification_sha256=sha256_file(F0/'verification.json')))
        return
    if (directory/'results.json').exists():
        assert read(directory/'results.json')['protocol_sha256']==sha256_file(OUT/'protocol.json'); print(f'Fold{f} already complete',flush=True); return
    pilot.OUT=directory; pilot.MODEL=ROOT/f'ai-service/candidates/original_eight_resnet50_cv_fold{f}_seed42'
    fold_protocol=dict(benchmark_protocol_sha256=sha256_file(OUT/'protocol.json'),fold=f,classes=CLASSES,configuration=pilot.CONFIG,roles=protocol['folds'][f]['roles'])
    if (directory/'protocol.json').exists(): assert read(directory/'protocol.json')==fold_protocol
    else: save_json(directory/'protocol.json',fold_protocol)
    if not (pilot.MODEL/'selection_report.json').exists():
        assert not pilot.MODEL.exists(),'Inspect partial training; never overwrite an incomplete run'
        print(json.dumps(dict(start_fold=f,role_counts={r:len(v) for r,v in roles.items()})),flush=True)
        pilot.train(roles,fold_protocol)
    selected=read(pilot.MODEL/'selection_report.json')
    assert selected['protocol_sha256']==sha256_file(directory/'protocol.json') and selected['checkpoint_sha256']==sha256_file(pilot.MODEL/'best_model.pth')
    vp={}; vy=None
    for m in PARENTS: vp[m],vy=aligned_inner_predictions(m,f,outer,inner)
    paths=fold_protocol['roles']['inner_validation']; by_path={s.path.relative_to(ROOT).as_posix():s for s in roles['inner_validation']}
    vp[NEW]=pilot.infer([by_path[p] for p in paths])
    assert score(vp[NEW],vy)['macro_f1']==selected['best']['validation']['macro_f1']
    w,details=choose_class_weights(vp[PARENTS[0]],vp[PARENTS[1]],vy); vp[REFERENCE]=classwise_blend(vp[PARENTS[0]],vp[PARENTS[1]],w)
    np.savez_compressed(directory/'validation_predictions.npz',paths=paths,truth=vy,**vp)
    specs=pilot.candidates(vp,vy); reference=score(vp[REFERENCE],vy)
    trials=[dict(spec=s,validation=score(pilot.combine(s,vp),vy)) for s in specs]
    for t in trials: t['passes_validation_guard']=pilot.passes(t['validation'],reference)
    winner=sorted([t for t in trials if t['passes_validation_guard']],key=pilot.ranking)[0]['spec']
    lock=dict(protocol_sha256=sha256_file(OUT/'protocol.json'),fold_protocol_sha256=sha256_file(directory/'protocol.json'),fold=f,
              checkpoint_sha256=selected['checkpoint_sha256'],reference_weights=w.tolist(),reference_details=details,selected=winner,trials=trials)
    if (directory/'selection_locked.json').exists(): assert read(directory/'selection_locked.json')==lock
    else: save_json(directory/'selection_locked.json',lock)
    # First outer probability access and new inference follow validation lock.
    expected={r['path']:r for r in outer['images'] if r['fold']==f}; order=sorted(expected)
    tp={m:np.stack([v[p] for p in order]) for m in PARENTS for v in [read_probabilities(m,f,outer,expected)]}
    by_path={s.path.relative_to(ROOT).as_posix():s for s in roles['outer_holdout']}; tp[NEW]=pilot.infer([by_path[p] for p in order])
    tp[REFERENCE]=classwise_blend(tp[PARENTS[0]],tp[PARENTS[1]],w); y=np.asarray([CLASSES.index(expected[p]['class']) for p in order])
    probabilities={s['name']:pilot.combine(s,tp) for s in specs}; probabilities['validation_selected']=pilot.combine(winner,tp)
    pred=[dict(path=p,sha256=expected[p]['sha256'],label=expected[p]['class'],group=expected[p]['scene_or_case_group'],
               probabilities={k:a[j].tolist() for k,a in probabilities.items()}) for j,p in enumerate(order)]
    save_json(directory/'test_predictions.json',pred)
    result=dict(protocol_sha256=sha256_file(OUT/'protocol.json'),selection_sha256=sha256_file(directory/'selection_locked.json'),fold=f,selected_method=winner['name'],
                results={k:score(a,y) for k,a in probabilities.items()})
    save_json(directory/'results.json',result)
    print(json.dumps(dict(complete_fold=f,selected=winner['name'],selected_metrics={k:result['results']['validation_selected'][k] for k in ('accuracy','macro_f1')},
                         reference_metrics={k:result['results'][REFERENCE][k] for k in ('accuracy','macro_f1')})),flush=True)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--prepare-only',action='store_true'); args=parser.parse_args()
    torch.set_num_threads(4); warnings.filterwarnings('ignore',message=r'Seems like.*optimizer.step',category=UserWarning)
    outer,inner,roles,protocol=register()
    if args.prepare_only: print(json.dumps(dict(registered=str(OUT/'protocol.json'),folds={f:{r:len(v) for r,v in roles[f].items()} for f in roles})),flush=True); return
    assert torch.cuda.is_available() and not (OUT/'results.json').exists(),'Preserve completed CV'
    for f in range(5): run_fold(outer,inner,roles[f],protocol,f)
    predictions=[]; per_fold=[]
    for f in range(5):
        directory=F0 if f==0 else OUT/f'fold_{f}'
        predictions.extend(dict(r,fold=f) for r in read(directory/'test_predictions.json'))
        d=read(directory/'results.json'); per_fold.append(dict(fold=f,selected_method=d['selected_method'],results=d['results']))
    predictions.sort(key=lambda r:r['path']); assert len(predictions)==len({r['path'] for r in predictions})==5937
    y=np.asarray([CLASSES.index(r['label']) for r in predictions]); names=list(predictions[0]['probabilities'])
    subset=[r for r in predictions if r['fold']!=0]; sy=np.asarray([CLASSES.index(r['label']) for r in subset])
    result=dict(status='original_eight_three_architecture_cv_complete_internal_research',classes=CLASSES,images=5937,protocol_sha256=sha256_file(OUT/'protocol.json'),
                results={k:score(np.asarray([r['probabilities'][k] for r in predictions]),y) for k in names},per_fold=per_fold,
                fold1_4_replication=dict(images=len(subset),results={k:score(np.asarray([r['probabilities'][k] for r in subset]),sy) for k in names}))
    save_json(OUT/'oof_predictions.json',predictions); save_json(OUT/'results.json',result)
    print(json.dumps(dict(complete=True,images=5937,results={k:{n:v[n] for n in ('accuracy','macro_f1')} for k,v in result['results'].items()})),flush=True)


if __name__=='__main__': main()
