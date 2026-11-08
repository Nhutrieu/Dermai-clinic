"""Matched gate objective: accuracy outcomes versus local Macro-F1 utility.

Reuse frozen nested candidate predictions; fit no CNN or candidate stack.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from pathlib import Path
import warnings
import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits
import run_teacher_conservative_gate as old

base=old.base
original=old.original
ROOT=old.ROOT
NAME='teacher_macro_f1_gate_seed42_20261023'
OUT=ROOT/'ai-service/reports'/NAME
MODELS=ROOT/'ai-service/candidates'/NAME
ARMS=['conservative_control','macro_f1_gate']
TOL=1e-12


def utc():return datetime.now(timezone.utc).isoformat()


def utility_targets(current,candidate,truth):
    current=np.asarray(current,dtype=int);candidate=np.asarray(candidate,dtype=int);truth=np.asarray(truth,dtype=int)
    if current.shape!=candidate.shape or current.shape!=truth.shape or current.ndim!=1 or any(np.any((a<0)|(a>7)) for a in [current,candidate,truth]):
        raise ValueError('Aligned class indices 0..7 required')
    cm=np.bincount(8*truth+current,minlength=64).reshape(8,8)
    tp=cm.diagonal();den=cm.sum(0)+cm.sum(1)
    f1=np.divide(2*tp,den,out=np.zeros(8),where=den>0)
    delta=np.zeros(len(truth));eligible=(current!=5)&(candidate!=5)&(current!=candidate)
    def f(t,d):return 2*t/d if d else 0.
    for i in np.flatnonzero(eligible):
        b,c,y=int(current[i]),int(candidate[i]),int(truth[i])
        delta[i]=(f(tp[b]-(y==b),den[b]-1)-f1[b]+f(tp[c]+(y==c),den[c]+1)-f1[c])/8
    target=np.full(len(truth),-1,dtype=int);target[eligible&(delta>TOL)]=1;target[eligible&(delta<-TOL)]=0
    decisive=old.gate_targets(current,candidate,truth);mass=int((decisive>=0).sum())
    weights=np.zeros(len(truth));mask=target>=0
    if mask.any() and mass>0:weights[mask]=np.abs(delta[mask])*mass/np.abs(delta[mask]).sum()
    return target,weights,delta,cm


def fit_pair(x,current,candidate,truth):
    control_target=old.gate_targets(current,candidate,truth)
    control,control_report=old.fit_gate(x,control_target)
    target,weights,delta,cm=utility_targets(current,candidate,truth)
    mask=target>=0;mass=int((control_target>=0).sum())
    report=dict(input_rows=len(x),fit_rows=int(mask.sum()),target_counts=np.bincount(target[mask],minlength=2).tolist(),
        control_decisive_rows=mass,weight_sum=float(weights.sum()),mean_weight=float(weights[mask].mean()) if mask.any() else 0.,
        min_weight=float(weights[mask].min()) if mask.any() else 0.,max_weight=float(weights[mask].max()) if mask.any() else 0.,
        included_wrong_to_wrong=int((mask&(current!=truth)&(candidate!=truth)).sum()),
        delta_tolerance=TOL,baseline_confusion_matrix=cm.tolist())
    if control['kind']=='always_keep' or np.unique(target[mask]).tolist()!=[0,1]:
        model=dict(kind='always_keep',mean=control['mean'].copy(),scale=control['scale'].copy(),
            coef=np.zeros((0,22)),intercept=np.zeros(0),classes=np.array([0,1]))
        report.update(kind='always_keep',iterations=[])
    else:
        assert abs(weights.sum()-mass)<1e-10
        z=(x[mask]-control['mean'])/control['scale']
        with warnings.catch_warnings():
            warnings.simplefilter('error',ConvergenceWarning)
            head=LogisticRegression(C=.1,penalty='l2',solver='lbfgs',class_weight=None,
                max_iter=3000,tol=1e-7,random_state=42).fit(z,target[mask],sample_weight=weights[mask])
        model=dict(kind='logistic',mean=control['mean'].copy(),scale=control['scale'].copy(),
            coef=head.coef_,intercept=head.intercept_,classes=head.classes_)
        report.update(kind='logistic',iterations=head.n_iter_.tolist())
    return dict(conservative_control=control,macro_f1_gate=model),dict(conservative_control=control_report,macro_f1_gate=report),dict(
        control_target=control_target,utility_target=target,utility_weights=weights,utility_delta=delta,baseline_confusion_matrix=cm)


def fit_meta(source,truth,current):
    fit=source['fit_indices'];hold=source['hold_indices']
    candidate=old.stack.route(current[fit],source['nested_probability'])
    models,reports,trace=fit_pair(source['gate_features'],current[fit],candidate,truth[fit])
    scores={arm:old.gate_probability(model,source['held_gate_features']) for arm,model in models.items()}
    decisions={arm:old.route(current[hold],source['held_candidate'],score) for arm,score in scores.items()}
    return models,reports,trace,scores,decisions


def choose(decisions,truth):
    scores={name:base.metrics(pred,truth) for name,pred in decisions.items()}
    trials={name:dict(metrics=s,guard_failures=original.failures(s,scores['current_fusion'])) for name,s in scores.items()}
    new=scores['macro_f1_gate'];control=scores['conservative_control']
    for key in ['accuracy','macro_f1']:
        if new[key]+TOL<control[key]:trials['macro_f1_gate']['guard_failures'].append(key+'_below_control')
    focus=lambda s:float(np.mean([s['per_class'][c]['f1'] for c in ['Lupus','Psoriasis','Tinea']]))
    if focus(new)+TOL<focus(control):trials['macro_f1_gate']['guard_failures'].append('mean_focus_f1_below_control')
    passing=[name for name,t in trials.items() if not t['guard_failures']]
    selected=max(passing,key=lambda name:(scores[name]['macro_f1'],
        np.mean([scores[name]['per_class'][c]['recall'] for c in ['Lupus','Psoriasis','Tinea']]),
        scores[name]['accuracy'],name=='current_fusion',name=='conservative_control'))
    return dict(selected=selected,trials=trials)


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');original.verify(p);return p
    prior=base.read(old.OUT/'protocol.json');original.verify(prior)
    review=base.read(old.OUT/'independent_review.json');assert review['status']=='PASS' and review['maximum_model_refit_abs_error']==0
    registry=base.read(ROOT/'ai-service/reports/active_research_track.json');assert registry['next_experiment'] is None
    files=[Path(__file__),ROOT/'ai-service/tests/test_teacher_macro_f1_gate.py',Path(old.__file__),old.OUT/'protocol.json',
        old.OUT/'results.json',old.OUT/'completion.json',old.OUT/'independent_review.json',old.OUT/'all_selections_locked.json']
    for f in range(5):
        lock=base.read(old.OUT/f'fold_{f}/selection_locked.json')
        files+=[ROOT/path for path in lock['artifacts_sha256']]
        files+=[old.OUT/f'fold_{f}/selection_locked.json',base.fold_dir(f)/'validation_predictions.npz',base.fold_dir(f)/'test_predictions.json']
    frozen={**prior['frozen_sha256'],**{path.relative_to(ROOT).as_posix():base.sha(path) for path in files}}
    p=dict(name=NAME,registered_utc=utc(),classes=base.CLASSES,images=5937,folds=5,
        parent_protocol=prior['parent_protocol'],prior_gate_protocol=(old.OUT/'protocol.json').relative_to(ROOT).as_posix(),
        frozen_sha256=frozen,
        intervention='Only change learned gate utility/loss: oldbinaryAccuracy decisivefix/harm vs signandmagnitude of exactone-row MacroF1 switchdelta. Utility arm includes informative wrong-to-wrong switches.',
        utilities='Build baseline8x8CM from ONLY currentgatefitrole T labels. For each nonCancerdisagreement subtract1at[y,baseline],add1at[y,candidate]; fixed8label MacroF1delta. Delta>1e-12target1,delta<-1e-12target0; othersexcluded.',
        matched='Botharms use same frozen22runtimefeatures,nestedcandidatepredictions,sourceindices,thresholdstrict>2/3,L2C=.1. Shared scaler fitted ONLY originaldecisive T rows, reproduced from priorcontrol. Utility absdelta weights sum=numberoriginaldecisive T rows to match total lossmass atfixedC. Not meanweight1 when rowscountdiffers.',
        fallback='If control lacks eitherbinaryclass, bothalwayskeep. If utility lacks either signclass, utilityalwayskeep. No fakeclasses/rows.',
        fitting='Reuse independently verified immutable3meta-part/2nested-part candidate caches. Refit20control+20utilitygates; nocandidate/CNNfits. Final utilityCM only wholeinner labels; final features use only candidatecross-predictions, nofullinner in-sample candidate outputs.',
        selection='On same meta-held inner predictions compare baseline/control/utility. Original strictbaselineguards. Utility additionally Accuracy,MacroF1 and meanweakF1>=control. Rank originalMacroF1/meanweakRecall/Accuracy, baselinewinstie thencontrol. All5choices locked before outer inference. No outer threshold/weight/search.',
        threshold=2/3,C=.1,delta_tolerance=TOL,
        references=['https://proceedings.neurips.cc/paper_files/paper/2014/hash/5c0314ec1b57fcd36bbb013f3f025868-Abstract.html',
            'https://proceedings.mlr.press/v37/narasimhanb15.html'],
        limitations=prior['limitations']+[
            'This is an original localutility heuristic inspired by cost-sensitive Fmeasure literature, not a reproduction or globally optimalF1algorithm.',
            'Single-switch deltas about originalCM are not additive when multiple switches occur; optimizing weighted loss does not guarantee globalMacroF1 or weakF1 improvement.',
            'Utility targets include training labels and CM only inside fitrole. Runtime uses modeloutputs only. Weighted gate scores are not diseaseprobabilities.',
            'Fixedthreshold2/3 enforces conservative weighted odds; it was not tuned. Different utility signs/rowpopulation are part of the objectivechange, while scaler/totalweightmass are heldfixed.',
            'Prior validation-selected gate improved development aggregates slightly but decreased someweakF1/sourceMF. Newresults remain exploratory on repeatedly studied images.'],
        new_candidate_fits=0,new_CNN_fits=0,serving_changed=False)
    OUT.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p);base.write(OUT/'research_registry_before.json',registry)
    registry['next_experiment']=OUT.relative_to(ROOT).as_posix();registry['next_experiment_status']='registered_matched_macro_f1_utility_gate'
    base.write(ROOT/'ai-service/reports/active_research_track.json',registry)
    return p


def match(model,path):
    prior=old.load(path)
    assert str(model['kind'])==str(prior['kind'])
    for key in ['mean','scale','coef','intercept','classes']:assert np.allclose(model[key],prior[key],atol=1e-10,rtol=0),key


def fit_all(p):
    assert not (OUT/'all_selections_locked.json').exists(),'Preserve completed fits'
    parent=base.read(ROOT/p['parent_protocol']);counts={arm:0 for arm in ARMS};fallbacks={arm:0 for arm in ARMS}
    for f in range(5):
        paths,y,_,_,current=original.validation(parent,f);folder=OUT/f'fold_{f}';folder.mkdir(parents=True,exist_ok=True)
        scores={arm:np.full(len(y),np.nan) for arm in ARMS};decisions={arm:np.full(len(y),-1) for arm in ARMS};reports=[]
        for part in range(3):
            source=old.load(old.OUT/f'fold_{f}/meta_{part}_training.npz')
            models,report,trace,ss,dd=fit_meta(source,y,current);hold=source['hold_indices']
            for arm,model in models.items():
                old.save(MODELS/f'fold_{f}/meta_{part}/{arm}.npz',model)
                scores[arm][hold]=ss[arm];decisions[arm][hold]=dd[arm]
                counts[arm]+=model['kind']=='logistic';fallbacks[arm]+=model['kind']=='always_keep'
            match(models['conservative_control'],old.MODELS/f'fold_{f}/meta_{part}/gate.npz')
            assert np.allclose(ss['conservative_control'],source['held_gate_score'],atol=1e-12,rtol=0)
            np.savez_compressed(folder/f'meta_{part}_training.npz',fit_indices=source['fit_indices'],hold_indices=hold,
                **trace,control_score=ss['conservative_control'],utility_score=ss['macro_f1_gate'])
            reports.append(dict(part=part,**report))
        prior=old.load(old.OUT/f'fold_{f}/inner_crossfit.npz')
        assert prior['paths'].tolist()==paths and np.array_equal(prior['current'],current)
        assert np.array_equal(decisions['conservative_control'],prior['gate_decision'])
        lock=choose(dict(current_fusion=current,**decisions),y)
        models,final,trace=fit_pair(prior['final_gate_features'],current,prior['raw_stack'],y)
        for arm,model in models.items():
            old.save(MODELS/f'fold_{f}/{arm}.npz',model)
            counts[arm]+=model['kind']=='logistic';fallbacks[arm]+=model['kind']=='always_keep'
        match(models['conservative_control'],old.MODELS/f'fold_{f}/gate.npz')
        np.savez_compressed(folder/'inner_crossfit.npz',paths=paths,truth=y,current=current,
            control_score=scores['conservative_control'],utility_score=scores['macro_f1_gate'],
            control_decision=decisions['conservative_control'],utility_decision=decisions['macro_f1_gate'],
            **trace,protocol_sha256=base.sha(OUT/'protocol.json'))
        base.write(folder/'training_report.json',dict(fold=f,inner_images=len(y),meta_parts=reports,final=final,
            original_control_reproduced=True,candidate_cache_reused=True,new_candidate_fits=0,new_CNN_fits=0))
        artifacts=[*folder.glob('*.npz'),folder/'training_report.json',*(MODELS/f'fold_{f}').rglob('*.npz')]
        lock.update(locked_utc=utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
            artifacts_sha256={path.relative_to(ROOT).as_posix():base.sha(path) for path in artifacts})
        base.write(folder/'selection_locked.json',lock)
        print(dict(fold=f,selected=lock['selected'],utility_failures=lock['trials']['macro_f1_gate']['guard_failures'],final=final['macro_f1_gate']),flush=True)
    base.write(OUT/'all_selections_locked.json',dict(locked_utc=utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
        selections_sha256={str(f):base.sha(OUT/f'fold_{f}/selection_locked.json') for f in range(5)},actual_gate_fits=counts,fallbacks=fallbacks))
    original.verify(p)


def evaluate(p):
    assert not (OUT/'results.json').exists(),'Preserve completed evaluation'
    locks=base.read(OUT/'all_selections_locked.json');parent=base.read(ROOT/p['parent_protocol']);rows=[];started=utc()
    assert locks['selections_sha256']=={str(f):base.sha(OUT/f'fold_{f}/selection_locked.json') for f in range(5)}
    for f in range(5):
        records,_,_,current=original.outer_rows(parent,f);lock=base.read(OUT/f'fold_{f}/selection_locked.json')
        for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
        pp=[np.asarray([r['probabilities'][k] for r in records]) for k in old.stack.PARENTS]
        q=old.candidate_probability(old.load(old.MODELS/f'fold_{f}/stack.npz'),old.stack.features(pp))
        x,candidate=old.gate_features(pp,q,current);scores={};decisions=dict(current_fusion=current)
        for arm in ARMS:
            scores[arm]=old.gate_probability(old.load(MODELS/f'fold_{f}/{arm}.npz'),x)
            decisions[arm]=old.route(current,candidate,scores[arm])
        prior_choice=base.read(old.OUT/f'fold_{f}/selection_locked.json')['selected']
        decisions['prior_validation_selected']=decisions['conservative_control'] if prior_choice=='conservative_gate' else current
        decisions['validation_selected']=decisions[lock['selected']]
        rr=original.records(records,f,decisions)
        for i,row in enumerate(rr):row.update(control_score=float(scores['conservative_control'][i]),utility_score=float(scores['macro_f1_gate'][i]),candidate_pred=int(candidate[i]))
        rows+=rr
    rows.sort(key=lambda r:r['path']);assert len(rows)==len({r['path'] for r in rows})==5937
    y=np.array([base.CLASSES.index(r['label']) for r in rows]);current=np.array([r['predictions']['current_fusion'] for r in rows]);prior_pred=np.array([r['predictions']['prior_validation_selected'] for r in rows])
    prior_rows={r['path']:r for r in base.read(old.OUT/'oof_decisions.json')}
    for row in rows:
        previous=prior_rows[row['path']]['predictions']
        assert row['predictions']['current_fusion']==previous['current_fusion']
        assert row['predictions']['conservative_control']==previous['conservative_gate']
        assert row['predictions']['prior_validation_selected']==previous['validation_selected']
    methods={}
    for name in rows[0]['predictions']:
        pred=np.array([r['predictions'][name] for r in rows]);assert np.array_equal(pred==5,current==5)
        score=base.metrics(pred,y)
        score.update(correct=int((pred==y).sum()),changed=int((pred!=current).sum()),
            corrected=int(((current!=y)&(pred==y)).sum()),broken=int(((current==y)&(pred!=y)).sum()),
            wrong_to_wrong=int(((current!=pred)&(current!=y)&(pred!=y)).sum()),
            paired_delta_95pct=original.paired_intervals(rows,pred,current,y),
            paired_delta_vs_prior_gate_95pct=original.paired_intervals(rows,pred,prior_pred,y))
        score['per_source']={}
        for source in ['original_train','SCIN']:
            mask=np.array([r['source']==source for r in rows]);score['per_source'][source]=dict(images=int(mask.sum()),**base.metrics(pred[mask],y[mask]))
        methods[name]=score
    prior=base.read(old.OUT/'results.json')
    for name,prior_name in [('current_fusion','current_fusion'),('conservative_control','conservative_gate'),('prior_validation_selected','validation_selected')]:
        assert methods[name]['confusion_matrix']==prior['methods'][prior_name]['confusion_matrix']
    per_fold=[]
    for f in range(5):
        rr=[r for r in rows if r['fold']==f];yy=np.array([base.CLASSES.index(r['label']) for r in rr])
        per_fold.append(dict(fold=f,selected=base.read(OUT/f'fold_{f}/selection_locked.json')['selected'],
            methods={n:base.metrics(np.array([r['predictions'][n] for r in rr]),yy) for n in methods}))
    r=dict(status='complete_exploratory_matched_macro_f1_gate',images=5937,methods=methods,per_fold=per_fold,
        actual_gate_fits=locks['actual_gate_fits'],fallbacks=locks['fallbacks'],new_candidate_fits=0,new_CNN_fits=0,
        outer_started_utc=started,completed_utc=utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
        all_selections_sha256=base.sha(OUT/'all_selections_locked.json'),reference_baseline_changed=False,serving_changed=False,limitations=p['limitations'])
    base.write(OUT/'oof_decisions.json',rows);base.write(OUT/'results.json',r);original.verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),
        decisions_sha256=base.sha(OUT/'oof_decisions.json'),all_five_choices_locked_before_outer=True,
        original_gate_control_reproduced=True,cancer_mask_unchanged=True,scope='Technical consistency, not clinical validation'))
    base.write(OUT/'status.json',dict(state='complete',utc=utc()))
    print({n:{k:s[k] for k in ['accuracy','macro_f1','correct','changed']} for n,s in methods.items()},flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--register-only',action='store_true');args=parser.parse_args()
    with threadpool_limits(limits=1):
        p=prepare()
        if not args.register_only:fit_all(p);evaluate(p)


if __name__=='__main__':main()
