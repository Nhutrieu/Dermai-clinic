"""Five-fold validation-selected Tinea/Eczema assistance from frozen-feature DRO."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import pilot_teacher_dro_pair_gate as pilot

ROOT,base,prior,latest,latent=pilot.ROOT,pilot.base,pilot.prior,pilot.latest,pilot.latent
dro=pilot.previous
OUT=ROOT/'ai-service/reports/teacher_dro_pair_cv_seed42_20261024'
MODELS=ROOT/'ai-service/candidates'/OUT.name


def route(current,q):
    candidate,mask=pilot.proposals(current,q);result=current.copy();change=mask&(q.max(1)>=.8);result[change]=candidate[change]
    return result


def choose(current,candidate,truth):
    scores={n:base.metrics(d,truth) for n,d in [('current_policy',current),('dro_pair',candidate)]}
    trials={n:dict(metrics=s,guard_failures=prior.failures(s,scores['current_policy'])) for n,s in scores.items()}
    passing=[n for n,t in trials.items() if not t['guard_failures']]
    selected=max(passing,key=lambda n:(scores[n]['macro_f1'],latest.previous.mean_focus(scores[n],'recall'),scores[n]['accuracy'],n=='current_policy'))
    return dict(selected=selected,trials=trials)


def cached(f,role,paths):
    path=latent.SOURCE/f'fold_{f}_resnet_features.npz' if role=='source_transfer' else prior.OUT/f'B_specialist/fold_{f}/{role}_features.npz'
    with np.load(path,allow_pickle=False) as z:
        index={p:i for i,p in enumerate(z['paths'].tolist())};x=z['features'][[index[p] for p in paths]].copy()
    assert x.shape==(len(paths),2048) and np.isfinite(x).all();return x


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');prior.verify(p);return p
    old=base.read(pilot.OUT/'protocol.json');prior.verify(old)
    assert base.read(pilot.OUT/'completion.json')['status']=='complete_verified_pilot_local_selection'
    reg=base.read(ROOT/'ai-service/reports/active_research_track.json');assert reg['next_experiment'] is None
    files=[Path(__file__),Path(pilot.__file__),ROOT/'ai-service/tests/test_teacher_dro_pair_cv.py',
        pilot.OUT/'protocol.json',pilot.OUT/'results.json',pilot.OUT/'selection_locked.json',pilot.OUT/'completion.json',pilot.OUT/'independent_review.json']
    for f in range(5):
        files += [prior.OUT/f'B_specialist/fold_{f}/{role}_features.npz' for role in ['train','inner_validation','outer_holdout']]
        files += [latent.SOURCE/f'fold_{f}_resnet_features.npz',latest.OUT/f'fold_{f}/inner_decisions.npz',latest.OUT/f'fold_{f}/selection_locked.json']
    p=dict(name=OUT.name,registered_utc=latent.utc(),classes=base.CLASSES,folds=5,images=5937,parent_protocol=old['parent_protocol'],
        frozen_sha256={**old['frozen_sha256'],**{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},
        rationale='Pair-confined fixed>=.8 policy passed all fold0inner guards, while learned gate failed. Expand the validation-passing fixed policy unchanged, assess all outer folds without selecting on aggregate. Fold0outer previously known to decline one correct, not used to change recipe.',
        training='Reuse verified fold0GroupDRO checkpoint exactly. Fit original fiveway head once for eachfold1..4, originalfold-specific frozenResNet2048cache, train-onlyStandardScaler, samecase-averaged class-source groupDRO CONFIG400fullbatchCPUfloat64 Adam.01 dual.01,C.001,L2=1/(Ntrain*C),zeroinit42. No head/scaler fit on inner or source.',
        configuration=dro.CONFIG,
        routing='Only current Tinea/Eczema calls may flip to other pair member if frozen DRO full5way argmax is that member and full5way max>=.8. No conditional pair renormalization, learned gate, thresholds/weights search or source labels at inference. ExactCancer mask preserved.',
        selection='On eachfoldinner compare current versus pairedcandidate using unchanged strict Accuracy/MacroF1, eachweakRecall/F1, weakPrecision<=2pp, otherRecall<=2pp, exactCancerP/R. Rank MF,meanweakRecall,Accuracy,tiescurrent. Lock all5choices before new outer/source application. Fold0predictions/choice must reproduce pilot.',
        evaluation='Every original5937photo gets one outer prediction, report rawcandidate and validation-selected policy separately with perclass,source,fold,fix/harm and1000pairedscene-group bootstrap95% delta intervals seed20261022. Same1709known-sourcephotos evaluated byfivefoldsystems; separate historicalsubsets and per-fold means, never pooled as8545independentphotos or averaged into a new classifier.',
        limitations=old['limitations']+[
            'This is an additional adaptation of a previously inspected cohort, with one CNN seed, not a fresh clinical/patient test or fully nestedCNNtraining.',
            'Positive full-cohort aggregates cannot alone prove stable gains if weak-class scores, source generalization or paired intervals disagree. Do not silently replace retained policy from exploratory results.',
            'Only four new linear heads are trained; original15CNNcheckpoints unchanged. Five source scores evaluate samephotos, not newfolds/independent seeds.'],
        new_head_fits=4,reused_head_fits=1,new_CNN_fits=0,serving_changed=False)
    OUT.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p);base.write(OUT/'research_registry_before.json',reg)
    reg['next_experiment']=OUT.relative_to(ROOT).as_posix();reg['next_experiment_status']='registered_fixed_dro_pair_all5folds'
    base.write(ROOT/'ai-service/reports/active_research_track.json',reg);return p


def fit_and_lock(p):
    parent=base.read(ROOT/p['parent_protocol']);selections={}
    for f in range(5):
        folder=OUT/f'fold_{f}';directory=MODELS/f'fold_{f}';folder.mkdir(parents=True,exist_ok=True);directory.mkdir(parents=True,exist_ok=True)
        if f==0:
            with np.load(dro.MODELS/'group_dro.npz',allow_pickle=False) as z:model={k:z[k].copy() for k in ['coef','intercept','q','mean','scale']}
            report=dict(reused_checkpoint=(dro.MODELS/'group_dro.npz').relative_to(ROOT).as_posix(),reused_sha256=base.sha(dro.MODELS/'group_dro.npz'),new_head_fit=False)
        else:
            rows=prior.role_rows(parent,f,'train');paths=[r['path'] for r in rows];x=cached(f,'train',paths);scaler=StandardScaler().fit(x)
            y=latest.fiveway(np.array([base.CLASSES.index(r['label']) for r in rows]));matrix,counts=dro.group_matrix(rows)
            model,history=dro.fit(scaler.transform(x.astype(float)),y,matrix,True,p['configuration']);model.update(mean=scaler.mean_,scale=scaler.scale_)
            report=dict(new_head_fit=True,images=len(rows),groups=counts,history=history)
        np.savez_compressed(directory/'dro_head.npz',**model);base.write(folder/'training_report.json',report)
        rows=prior.role_rows(parent,f,'inner_validation');paths=[r['path'] for r in rows];truth=np.array([base.CLASSES.index(r['label']) for r in rows])
        with np.load(latest.OUT/f'fold_{f}/inner_decisions.npz',allow_pickle=False) as z:
            assert z['paths'].tolist()==paths;current=z[base.read(latest.OUT/f'fold_{f}/selection_locked.json')['selected']].copy()
        q=dro.probabilities(cached(f,'inner_validation',paths),model);candidate=route(current,q);lock=choose(current,candidate,truth)
        if f==0:
            with np.load(pilot.OUT/'inner_crossfit.npz',allow_pickle=False) as z:
                assert z['paths'].tolist()==paths and np.array_equal(candidate,z['fixed_pair_control'])
            assert lock['selected']=='dro_pair'
        np.savez_compressed(folder/'inner_decisions.npz',paths=paths,truth=truth,current_policy=current,dro_pair=candidate,dro_q=q)
        lock.update(locked_utc=latent.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),artifacts_sha256={x.relative_to(ROOT).as_posix():base.sha(x) for x in [directory/'dro_head.npz',folder/'training_report.json',folder/'inner_decisions.npz']})
        base.write(folder/'selection_locked.json',lock);selections[str(f)]=lock['selected']
        print(dict(fold=f,selected=lock['selected'],failures=lock['trials']['dro_pair']['guard_failures']),flush=True)
    base.write(OUT/'all_selections_locked.json',dict(locked_utc=latent.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
        selections=selections,selections_sha256={str(f):base.sha(OUT/f'fold_{f}/selection_locked.json') for f in range(5)}))


def load_model(f):
    with np.load(MODELS/f'fold_{f}/dro_head.npz',allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}


def evaluate(p):
    assert not (OUT/'results.json').exists(),'Preserve completed evaluation'
    locks=base.read(OUT/'all_selections_locked.json');assert locks['protocol_sha256']==base.sha(OUT/'protocol.json')
    for f in range(5):
        lock=base.read(OUT/f'fold_{f}/selection_locked.json');assert locks['selections_sha256'][str(f)]==base.sha(OUT/f'fold_{f}/selection_locked.json')
        for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
    started=latent.utc();parent=base.read(ROOT/p['parent_protocol']);reference={r['path']:r for r in base.read(latest.OUT/'oof_decisions.json')};rows=[]
    for f in range(5):
        meta=prior.role_rows(parent,f,'outer_holdout');paths=[r['path'] for r in meta];current=np.array([reference[path]['predictions']['validation_selected'] for path in paths])
        q=dro.probabilities(cached(f,'outer_holdout',paths),load_model(f));candidate=route(current,q)
        dd=dict(current_policy=current,dro_pair=candidate);dd['validation_selected']=dd[locks['selections'][str(f)]]
        np.savez_compressed(OUT/f'fold_{f}/outer_probabilities.npz',paths=paths,dro_q=q)
        rows+=prior.records(meta,f,dd)
    rows.sort(key=lambda r:r['path']);assert len(rows)==len({r['path'] for r in rows})==5937
    truth=np.array([base.CLASSES.index(r['label']) for r in rows]);current=np.array([r['predictions']['current_policy'] for r in rows]);methods={}
    for n in ['current_policy','dro_pair','validation_selected']:
        pred=np.array([r['predictions'][n] for r in rows]);assert np.array_equal(pred==5,current==5)
        s=base.metrics(pred,truth);s.update(correct=int((pred==truth).sum()),changed=int((pred!=current).sum()),
            corrected=int(((pred!=current)&(pred==truth)).sum()),broken=int(((pred!=current)&(current==truth)).sum()),
            wrong_to_wrong=int(((pred!=current)&(current!=truth)&(pred!=truth)).sum()),paired_delta95=prior.paired_intervals(rows,pred,current,truth))
        s['per_source']={src:base.metrics(pred[[r['source']==src for r in rows]],truth[[r['source']==src for r in rows]]) for src in ['original_train','SCIN']};methods[n]=s
    assert methods['current_policy']['correct']==4687
    per_fold={str(f):{n:base.metrics(np.array([r['predictions'][n] for r in rows if r['fold']==f]),np.array([base.CLASSES.index(r['label']) for r in rows if r['fold']==f])) for n in methods} for f in range(5)}
    base.write(OUT/'oof_decisions.json',rows)
    base.write(OUT/'results.json',dict(status='complete_exploratory_fixed_pair_CV',images=5937,methods=methods,per_fold=per_fold,
        selections=locks['selections'],held_started_utc=started,completed_utc=latent.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
        all_selections_sha256=base.sha(OUT/'all_selections_locked.json'),new_head_fits=4,reused_heads=1,new_CNN_fits=0,retained_policy_changed=False,serving_changed=False,limitations=p['limitations']))
    source=base.read(latent.SOURCE/'protocol.json');source_rows=base.read(latent.SOURCE/'source_decisions.json');ps=[r['path'] for r in source_rows];source_output=[];ss={}
    for f in range(5):
        current=np.array([r['predictions']['validation_selected'][f] for r in source_rows]);q=dro.probabilities(cached(f,'source_transfer',ps),load_model(f));candidate=route(current,q)
        dd=dict(current_policy=current,dro_pair=candidate);dd['validation_selected']=dd[locks['selections'][str(f)]];ss[f]=dd
        np.savez_compressed(OUT/f'fold_{f}/source_probabilities.npz',paths=ps,dro_q=q)
    for i,row in enumerate(source_rows):source_output.append({k:row[k] for k in ['path','sha256','group','source','historical_role','label']}|dict(predictions={n:[int(ss[f][n][i]) for f in range(5)] for n in methods}))
    lookup={path:i for i,path in enumerate(ps)};source_metrics={};ys=np.array([base.CLASSES.index(r['label']) for r in source_rows])
    for subset,paths in source['subsets'].items():
        ids=[lookup[path] for path in paths];source_metrics[subset]=dict(unique_images=len(ids),methods={})
        for n in methods:
            fold_scores={str(f):base.metrics(ss[f][n][ids],ys[ids]) for f in range(5)}
            means={k:dict(mean=float(np.mean([s[k] for s in fold_scores.values()])),min=float(min(s[k] for s in fold_scores.values())),max=float(max(s[k] for s in fold_scores.values()))) for k in ['accuracy','macro_f1']}
            source_metrics[subset]['methods'][n]=dict(per_fold=fold_scores,summary=means)
    base.write(OUT/'source_decisions.json',source_output);base.write(OUT/'source_results.json',source_metrics)
    prior.verify(p);base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),source_results_sha256=base.sha(OUT/'source_results.json')))
    print(dict(selected_folds=locks['selections'],scores={n:{k:s[k] for k in ['accuracy','macro_f1','correct','corrected','broken']} for n,s in methods.items()}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    with threadpool_limits(limits=2):
        p=prepare()
        if args.prepare_only:return
        assert not (OUT/'results.json').exists(),'Preserve completed CV'
        if not (OUT/'all_selections_locked.json').exists():fit_and_lock(p)
        evaluate(p)


if __name__=='__main__':main()
