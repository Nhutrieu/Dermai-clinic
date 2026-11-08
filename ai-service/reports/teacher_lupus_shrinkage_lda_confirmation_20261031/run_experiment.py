"""204: fixed shrinkage-LDA confirmation of existing paired Lupus proposals."""
from pathlib import Path
import importlib.util
import numpy as np
import sklearn
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.model_selection import StratifiedGroupKFold
from scipy.special import logsumexp
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;R=ROOT/'ai-service/reports'
PRIOR=R/'teacher_lupus_pair_cv_bagging_twofold_20261031';CAL=R/'teacher_lupus_pair_calibration_twofold_20261029'
spec=importlib.util.spec_from_file_location('paired204_reference',R/'teacher_lupus_coupled_pair_fold0_repeat_20261029/run_experiment.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
old=reference.old;base=old.base;PRIMARY='shrinkage_lda_confirmed_pairs';WEAK=[3,4,6]
SOURCES={'0':reference.OUT,'1':old.OUT};MODELS=ROOT/'ai-service/candidates'/OUT.name


def lupus_margin(scores):
    a=np.asarray(scores,float)
    if a.ndim!=2 or a.shape[1]!=3 or not np.isfinite(a).all():raise ValueError('Finite three-class discriminants in LP/Pso/Tin order required')
    return a[:,0]-logsumexp(a[:,1:],axis=1)


def route(parent,previous,margin):
    parent=np.asarray(parent);previous=np.asarray(previous);margin=np.asarray(margin,float)
    if parent.ndim!=1 or previous.shape!=parent.shape or margin.shape!=parent.shape or not np.isfinite(margin).all() or not np.isin(parent,range(8)).all() or not np.isin(previous,range(8)).all():raise ValueError('Aligned finite eight-class outputs/margins required')
    eligible=np.isin(parent,[4,6]);assert np.all((previous==parent)|(eligible&(previous==3)))
    out=parent.copy();out[eligible&(previous==3)&(margin>0)]=3
    return out


def scalerdir(fold):
    return ROOT/'ai-service/candidates'/(SOURCES[fold].name if fold=='0' else 'teacher_lupus_triad_binary_specialist_fold1_20261029')


def prepare():
    assert not (OUT/'protocol.json').exists(),'Preserve204registration'
    src=base.read(PRIOR/'protocol.json');image=base.read(CAL/'protocol.json');frozen=dict(src['frozen_sha256'])
    assert base.read(PRIOR/'completion.json')['status']=='complete_verified_pair_cv_bagging_twofold_203' and base.read(PRIOR/'independent_review.json')['status']=='PASS'
    for n in ['protocol.json','results.json','independent_review.json','completion.json','metadata_addendum.json']:
        f=PRIOR/n;frozen[f.relative_to(ROOT).as_posix()]=base.sha(f)
    for f in [Path(__file__),ROOT/'tmp/review_lupus_shrinkage_lda_20261031.py',ROOT/'ai-service/tests/test_lupus_shrinkage_lda_confirmation.py',ROOT/'tmp/review_lupus_pair_calibration_20261029.py',ROOT/'tmp/review_teacher_priorities_20261022.py']:
        frozen[f.relative_to(ROOT).as_posix()]=base.sha(f)
    for folder in SOURCES.values():
        for lock in ['training_locked.json','prediction_locked.json']:
            for f,h in base.read(folder/lock)['artifacts_sha256'].items():assert base.sha(ROOT/f)==h;frozen[f]=h
    p=dict(registered_utc=base.utc(),classes=src['classes'],roles_by_fold=src['roles_by_fold'],frozen_sha256=frozen,imagenet_path=image['imagenet_path'],imagenet_sha256=image['imagenet_sha256'],primary_formula=PRIMARY,
        scope='204 natural-prior three-class shrinkage LDA as fixed confirmation of immutable200/201 pair proposals. Same raw768 ConvNeXt ImageNet features and ownfold TRAIN. No new backbone/images/C/scaler/PCA/gate fitting or calibration.',
        training='Each ownfold: SGKF3 seed28168 onALL8 TRAIN, reuse own immutable ALL8-subtrain scalers from201/196. Fit LinearDiscriminantAnalysis(solver=lsqr,shrinkage=auto,priors=None) on true3/4/6 ONLY. All3 class covariance estimates use LedoitWolf auto on class-standardized features, rescale and pool with natural empirical priors.3CV diagnostic fits plus1final on allweak ownTRAIN using finalALL8scaler;8newLDAfits total. No hyperparameter selection, no C/threshold/seed search. CV outputs diagnostics only, not validation selection.',
        inference='Three LDA class scores in3/4/6 order; LPbinarylogodds=score3-logsumexp(score4,score6). Start175parent; accept200/201existingLPproposal ONLY if parent4/6 AND previous200/201pred3 AND LDAmarginSTRICT>0. Old parent3 preserved. Reject=>restore175parent. Not permitted to add LDA-only proposals or tune confidence/threshold/choose per-fold recipe after outcome. Preserves existing175LP, but may erase200/201gains; retention guards must detect.',
        endpoint=src['endpoint'],guards=src['guards'],inner_overlap=src['inner_overlap'],
        boundary='Freeze protocol/code/tests/reviewer/inputs before8fits. Lock8heads and2TRAINCV outputs/report BEFOREany newvalidationforward. Lock BOTHfold validation outputs before metrics. No scoreouter/global5937 or pooledhistoricalmetrics. Both historicalinner sets are already adaptive/exploratory, not blind.',
        audit='Independent formula LedoitWolf shrinkage from standardized class second/fourth moments, empirical class priors, shared covariance and Cholesky solve for all8heads; no use LDA.fit/private methods inreviewer. Compareclassmeans/covariance/coefs/intercept/KKTresidual; reconstruct SGKF/scalers/lossrows/OOFqueries; replaybothvalidationdecision scores/routes/metrics/source/cases/guards and5protectedclass masks. No independent CNNrefits.',
        references=['https://scikit-learn.org/1.3/modules/lda_qda.html#shrinkage-and-covariance-estimator','https://scikit-learn.org/1.3/modules/generated/sklearn.discriminant_analysis.LinearDiscriminantAnalysis.html'],
        sklearn_version=sklearn.__version__,new_LDA_fits=8,new_scalers=0,new_CNN_fits=0,new_PCA_fits=0,new_gate_fits=0,
        limitations=['Gaussian class-conditional/sharedcovariance assumption may be wrong for these image features. Analytic shrinkage cannot guarantee class separation or preservation of Lupus gains.',
            'Only4/9 SCIN LP TRAIN images and1/2 SCIN LP validation in prior audit; no claim source improvement from such small samples.',
            'Historicalvalidations repeatedlyexamined,74sharedimages/70groups; no independentpatients/doctorlabels or clinicalaccuracyconclusion. C of oldproposalrecipe previouslychosen onTRAIN; newLDA uses no C.',
            'Strict0.5 LP posterior within threeclasses is a technical rule, notcalibratedclinicalrisk. MainparentPso/Tin may contain truthoutsideweak; all8mainmetrics stillreported.'],
        pooled_metrics_computed=False,all_six_jobs_complete=False,selected=None,global_5937_score_changed=False,serving_changed=False,research_registry_changed=False)
    MODELS.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p);base.verify(p);return p


def train(p):
    files=[];fits={};diagnostics={}
    for fold in SOURCES:
        rows=p['roles_by_fold'][fold]['train'];xx=old.old.raw(rows);labels=np.array([p['classes'].index(a['label']) for a in rows]);weak=np.isin(labels,WEAK)
        splits=list(StratifiedGroupKFold(3,shuffle=True,random_state=28168).split(np.zeros(len(rows)),labels,[a['group'] for a in rows]));scores=np.full((len(rows),3),np.nan)
        for name,tr,ho in [(f'cv{k}',tr,ho) for k,(tr,ho) in enumerate(splits)]+[('final',np.arange(len(rows)),None)]:
            sc=old.old.arrays(scalerdir(fold)/(name+'_scaler.npz'))
            if ho is not None:
                assert np.array_equal(sc['train_indices'],tr) and np.array_equal(sc['holdout_indices'],ho)
                for key in ['path','sha256','group']:assert {rows[i][key] for i in tr}.isdisjoint({rows[i][key] for i in ho})
            ix=tr[np.isin(labels[tr],WEAK)];x=(xx[ix]-sc['mean'])/sc['scale']
            model=LinearDiscriminantAnalysis(solver='lsqr',shrinkage='auto',priors=None).fit(x,labels[ix]);assert model.classes_.tolist()==WEAK
            for value in [model.coef_,model.intercept_,model.covariance_,model.means_,model.priors_]:assert np.isfinite(value).all()
            residual=float(np.max(abs(model.covariance_@model.coef_.T-model.means_.T)));assert residual<1e-8
            f=MODELS/f'fold{fold}_{name}.npz';np.savez_compressed(f,classes=model.classes_,coef=model.coef_,intercept=model.intercept_,means=model.means_,priors=model.priors_,covariance=model.covariance_,fit_indices=ix);files.append(f)
            fits[f'fold{fold}_{name}']=dict(fit_rows=len(ix),class_counts={str(c):int(sum(labels[ix]==c)) for c in WEAK},linear_system_max_residual=residual)
            if ho is not None:
                query=(xx[ho]-sc['mean'])/sc['scale'];scores[ho]=query@model.coef_.T+model.intercept_
        assert np.isfinite(scores).all();target=np.searchsorted(WEAK,labels[weak]);weakscore=scores[weak]
        diag=dict(weak_rows=int(sum(weak)),three_class_oof_nll=float(np.mean(logsumexp(weakscore,axis=1)-weakscore[np.arange(sum(weak)),target])),three_class_oof_accuracy=float(np.mean(np.array(WEAK)[weakscore.argmax(1)]==labels[weak])),no_hyperparameter_selection=True)
        diagnostics[fold]=diag;f=OUT/f'fold_{fold}_train_cv.npz';np.savez_compressed(f,paths=[a['path'] for a in rows],labels=labels,scores=scores,weak=weak);files.append(f)
        print(dict(fold=fold,completed_LDA_fits=4,train_cv_diagnostics=diag),flush=True)
    f=OUT/'training_report.json';base.write(f,dict(fits=fits,train_cv_diagnostics=diagnostics,new_LDA_fits=8,new_scalers=0));files.append(f)
    base.write(OUT/'training_locked.json',dict(locked_utc=base.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),new_validation_outputs_started=False,artifacts_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in files}))


def predictions(p):
    files=[]
    for fold,folder in SOURCES.items():
        source=old.old.arrays(folder/('fold_0_predictions.npz' if fold=='0' else 'validation_predictions.npz'));rows=p['roles_by_fold'][fold]['inner_validation'];reference.bind_parent(rows,source)
        sc=old.old.arrays(scalerdir(fold)/'final_scaler.npz');head=old.old.arrays(MODELS/f'fold{fold}_final.npz');x=(old.old.raw(rows)-sc['mean'])/sc['scale'];scores=x@head['coef'].T+head['intercept'];margin=lupus_margin(scores)
        f=OUT/f'fold_{fold}_predictions.npz';np.savez_compressed(f,paths=source['paths'],truth=source['truth'],parent=source['parent'],zero_step175=source['parent'],uncalibrated_pairs=source[old.PRIMARY],lda_scores=scores,lda_lupus_margin=margin,**{PRIMARY:route(source['parent'],source[old.PRIMARY],margin)});files.append(f)
    base.write(OUT/'prediction_locked.json',dict(locked_utc=base.utc(),metrics_started=False,artifacts_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in files}))


def score(p):
    spec=importlib.util.spec_from_file_location('retention202',CAL/'run_experiment.py');cal=importlib.util.module_from_spec(spec);spec.loader.exec_module(cal)
    folds={};changes={}
    for fold in SOURCES:
        z=old.old.arrays(OUT/f'fold_{fold}_predictions.npz');rows=p['roles_by_fold'][fold]['inner_validation'];parent=z['parent'];truth=z['truth']
        ps=base.metrics_base.metrics(parent,truth);uncal=base.metrics_base.metrics(z['uncalibrated_pairs'],truth);trials={}
        for name in ['zero_step175','uncalibrated_pairs',PRIMARY]:
            d=z[name];s=base.metrics_base.metrics(d,truth);ff=old.old.failures(s,ps);rf=cal.retention(s,uncal,fold)
            trials[name]=dict(metrics=s,base_guard_failures=ff,retention_failures=rf,guard_failures=ff+rf,guard_pass=not(ff+rf),changed=int(sum(d!=parent)),fixed=int(sum((d==truth)&(parent!=truth))),harmed=int(sum((d!=truth)&(parent==truth))),new_Lupus_true=int(sum((parent!=3)&(d==3)&(truth==3))),new_Lupus_false=int(sum((parent!=3)&(d==3)&(truth!=3))),per_source={source:base.metrics_base.metrics(d[ix],truth[ix]) for source in ['SCIN','original_train'] for ix in [np.array([a['source']==source for a in rows])]})
            changes['fold'+fold+'__'+name]=[dict(path=str(z['paths'][i]),truth=p['classes'][int(truth[i])],before=p['classes'][int(parent[i])],after=p['classes'][int(d[i])],source=rows[i]['source']) for i in np.flatnonzero(d!=parent)]
        folds[fold]=dict(validation_images=len(rows),parent=ps,trials=trials)
    base.write(OUT/'changed_cases.json',changes)
    r=dict(completed_utc=base.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),primary_formula=PRIMARY,folds=folds,primary_both_fold_pass=all(d['trials'][PRIMARY]['guard_pass'] for d in folds.values()),new_LDA_fits=8,new_scalers=0,new_CNN_fits=0,new_PCA_fits=0,new_gate_fits=0,inner_overlap=p['inner_overlap'],pooled_metrics_computed=False,all_six_jobs_complete=False,selected=None,global_5937_score_changed=False,serving_changed=False,research_registry_changed=False)
    base.write(OUT/'results.json',r);base.verify(p);base.status('shrinkage_lda_confirmation_twofold_204_awaiting_review',selected=None)
    print(dict(fold_pass={f:d['trials'][PRIMARY]['guard_pass'] for f,d in folds.items()},both_fold_pass=r['primary_both_fold_pass'],new_LDA_fits=8))


if __name__=='__main__':
    base.OUT=OUT;base.process_lock()
    with threadpool_limits(limits=4):p=prepare();train(p);predictions(p);score(p)
