"""Repeat the frozen200 training procedure on ownfold0 and report each historical fold."""
from pathlib import Path
import importlib.util
import numpy as np
from scipy.optimize import minimize
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;R=ROOT/'ai-service/reports';SOURCE=R/'teacher_lupus_coupled_pair_specialist_fold1_20261029';PARENT=R/'teacher_lupus_monotone_extension_20261028';PLAN=R/'teacher_parent_crossfit_preflight_20261028';MODELS=ROOT/'ai-service/candidates'/OUT.name
sp=importlib.util.spec_from_file_location('retained_pairs200',SOURCE/'run_experiment.py');old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old);base=old.base;PRIMARY=old.PRIMARY


def fit_scaler(x,indices):
    sc=StandardScaler().fit(np.asarray(x,float)[indices]);return sc.mean_,sc.scale_


def bind_parent(rows,predictions):
    expected=[a['path'] for a in rows];labels=np.array([base.CLASSES.index(a['label']) for a in rows])
    if list(predictions['paths'])!=expected or not np.array_equal(predictions['truth'],labels):raise ValueError('Parent paths/order/truth must bind to exact ownfold validation roles')


def prepare():
    assert not (OUT/'protocol.json').exists(),'Preserve201registration';src=base.read(SOURCE/'protocol.json');base.verify(src);receipt=base.read(SOURCE/'completion.json');assert receipt['status']=='complete_verified_coupled_pair_specialist_pilot_200' and receipt['primary_guard_pass'] and base.read(SOURCE/'independent_review.json')['status']=='PASS';frozen=dict(src['frozen_sha256'])
    for lock in ['training_locked.json','prediction_locked.json']:
        for f,h in base.read(SOURCE/lock)['artifacts_sha256'].items():assert base.sha(ROOT/f)==h;frozen[f]=h
    for n in ['protocol.json','results.json','independent_review.json','completion.json','selection.json','training_locked.json','prediction_locked.json','validation_predictions.npz']:
        if n!='completion.json':assert base.sha(SOURCE/n)==receipt['artifacts_sha256'][n]
        frozen[(SOURCE/n).relative_to(ROOT).as_posix()]=base.sha(SOURCE/n)
    parent=base.read(PARENT/'protocol.json');roles=parent['folds']['0']['roles'];assert roles==base.read(PLAN/'protocol.json')['folds']['0']['roles'];base.assert_roles(roles);assert {k:len(v) for k,v in roles.items()}==dict(train=4043,inner_validation=718,outer_holdout=1176)
    assert base.read(PARENT/'independent_review.json')['status']=='PASS'
    for f,h in base.read(PARENT/'prediction_lock.json')['artifacts_sha256'].items():assert base.sha(ROOT/f)==h;frozen[f]=h
    for rr in roles.values():
        for row in rr:assert base.sha(ROOT/row['path'])==row['sha256']
    a,b=roles['inner_validation'],src['roles']['inner_validation'];overlap={k:len({x[k] for x in a}&{x[k] for x in b}) for k in ['path','sha256','group']};assert overlap==dict(path=74,sha256=74,group=70)
    for f in [Path(__file__),ROOT/'ai-service/tests/test_lupus_coupled_pair_fold0_repeat.py',ROOT/'tmp/review_lupus_coupled_pair_fold0_repeat_20261029.py',ROOT/'tmp/review_teacher_priorities_20261022.py',PLAN/'protocol.json',*[PARENT/n for n in ['protocol.json','completion.json','independent_review.json','prediction_lock.json','fold_0_decisions.npz']]]:frozen[f.relative_to(ROOT).as_posix()]=base.sha(f)
    p=dict(registered_utc=base.utc(),classes=src['classes'],fold=0,roles=roles,frozen_sha256=frozen,imagenet_path=src['imagenet_path'],imagenet_sha256=src['imagenet_sha256'],primary_formula=PRIMARY,C_grid=src['C_grid'],pairs=src['pairs'],
        scope='201 repeat training PROCEDURE200 on ownfold0 only; preserve fold1successful20heads/metrics. New20pairheads and4scalers; sameCNImageNet768/no newCNN/PCA/pixelsforward. No newarchitecture/loss/router/threshold/grid/seed choices. Historicalfold0inner alreadyusedbefore; overlaps fold1inner74photos70groups => NOT blind or independenttwo-validationconfirmation, neverpoolscore.',
        recipe='Reuse200coupled_margin/choose and196naturalobjective/rawfeatures/route as frozenfunctions. SGKF3seed28168 ALL8ownfold0TRAIN4043. FreshStandardScaler onALL8subtrain andfinal4043, identical fittingdefinition to196scalers reusedby200. Two naturalbinaryLP/Pso andLP/Tin lossrows, Cgrid1e-4/1e-3/1e-2; jointlychoose9Ccombinations bycoupledLPbinaryNLL ontrueweakheldoutTRAINonly; ties1e-12 smallerPsoC thenTinC. Zero769theta/LBFGS6000gtol1e-8ftol1e-15maxls50 success/maxgradient<1e-3.18CV+2finalheads. CvaluesselectedanewwithownTRAIN, notcopiedbyfold1outcome.',
        validation='Reuse immutable175full-ownfold0parent718 labels. OnlyparentPso/Tin andcoupledLPlogit>0=>LP;existingLP/outside5masks exact. Parentoldpipeline NOT retrained here; no claim original185other3fold0parentcrossfitjobs completed. No TRAINparent predictions used tofit/filter/tuneexperts. Replay200fold1 old713outputs onlyforcomparison, no newfold1fit orchangedscore.',
        endpoint='Primary BOTHfolds pass SAME200guards separately:Acc>=ownparent,MFstrictgain,ALL8P/R/F1>=ownparent andoneweakRecallstrictgain. Reporteachfold/per-source/newTP/FP andcompleteguards; no averaging/pooling1431entrieswithoverlap. Bothfoldpass stillonlyhistoricalrecipefollowup, notclinicalgeneralization/globalOOFpromotion.',
        boundary='Freeze201code/tests/reviewer/inputs/protocol BEFORE newscalers/fits. Lock20heads/4scalers/CV/Cchoices BEFOREnew718inference. Lockfold0newoutputs andfold1historicalreplay BEFOREmetrics. No newouter/global5937scoring; neverchangeendpointafterfold0outcome.',guards=src['guards'],
        limitations=src['limitations']+['74sharedvalidationphotos/70groups; hypothesisdevelopedafterfold1outcomes andbothhistoricalcohortsseenpreviously. No independentclinicaltest or wholepipelinebootstrap. Existing175parents differ acrossfolds butsame175formula/provenance frozen. This repeat onlychanges ownTRAINdata/scalers/Cselection throughsame recipe, notbaselineCNNpipeline.'],
        inner_overlap=overlap,new_helper_heads=20,new_scalers=4,new_CNN_fits=0,new_PCA_fits=0,new_gate_fits=0,fold1_reused=True,single_fold_only=False,two_historical_folds_evaluated=True,all_six_jobs_complete=False,selected=None,global_5937_score_changed=False,serving_changed=False,research_registry_changed=False)
    MODELS.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p);base.verify(p);return p


def train(p):
    rows=p['roles']['train'];xx=old.old.raw(rows);labels=np.array([p['classes'].index(a['label']) for a in rows]);y=(labels==3).astype(int);weak=np.isin(labels,[3,4,6]);groups=[a['group'] for a in rows];splits=list(StratifiedGroupKFold(3,shuffle=True,random_state=28168).split(np.zeros(len(rows)),labels,groups));cv={a:np.full((3,len(rows)),np.nan) for a in old.PAIRS};files=[];fits={}
    def save(name,**values):
        f=MODELS/name;np.savez_compressed(f,**values);files.append(f)
    def fit(name,x,target,c):
        op=minimize(old.old.objective,np.zeros(769),args=(x,target,c),jac=True,method='L-BFGS-B',options=dict(maxiter=6000,gtol=1e-8,ftol=1e-15,maxls=50));value,g=old.old.objective(op.x,x,target,c);assert op.success and max(abs(g))<1e-3,(name,op.message,float(max(abs(g))));save(name+'.npz',theta=op.x,c=c);fits[name]=dict(rows=len(target),positives=int(sum(target)),negatives=int(sum(target==0)),c=c,objective=value,gradient_max_abs=float(max(abs(g))),iterations=int(op.nit),success=True);return op.x
    for k,(tr,va) in enumerate(splits):
        for key in ['path','sha256','group']:assert {rows[i][key] for i in tr}.isdisjoint({rows[i][key] for i in va})
        mean,scale=fit_scaler(xx,tr);save(f'cv{k}_scaler.npz',train_indices=tr,holdout_indices=va,mean=mean,scale=scale);query=(xx[va]-mean)/scale
        for pair,cid in old.PAIRS.items():
            ix=tr[np.isin(labels[tr],[3,cid])];x=(xx[ix]-mean)/scale
            for ci,c in enumerate(old.CS):t=fit(f'{pair}_cv{k}_c{ci}',x,y[ix],c);cv[pair][ci,va]=query@t[:-1]+t[-1]
        print(dict(fold=0,CV=k+1,heads=len(fits)),flush=True)
    assert all(np.isfinite(a).all() for a in cv.values());losses=[]
    for cp,ct in old.GRID:
        margin=old.coupled_margin(cv['psoriasis'][old.CS.index(cp)],cv['tinea'][old.CS.index(ct)]);losses.append(float(np.mean(np.logaddexp(0,margin[weak])-y[weak]*margin[weak])))
    cp,ct=old.choose(losses);mean,scale=fit_scaler(xx,np.arange(len(rows)));save('final_scaler.npz',mean=mean,scale=scale)
    for pair,c in [('psoriasis',cp),('tinea',ct)]:
        ix=np.flatnonzero(np.isin(labels,[3,old.PAIRS[pair]]));fit(pair+'_final',(xx[ix]-mean)/scale,y[ix],c)
    assert len(fits)==20;save('train_CV_predictions.npz',paths=[a['path'] for a in rows],labels=labels,truth=y,weak=weak,**cv)
    for n,value in [('selection.json',dict(psoriasis_C=cp,tinea_C=ct,selection_images=int(sum(weak)),scores=[dict(psoriasis_C=a,tinea_C=b,nll=v) for (a,b),v in zip(old.GRID,losses)])),('training_report.json',dict(fits=fits,heads=20,scalers=4,train_images=len(rows),weak_images=int(sum(weak)),Lupus_images=int(sum(y)),pair_counts={pair:int(sum(np.isin(labels,[3,cid]))) for pair,cid in old.PAIRS.items()}))]:base.write(OUT/n,value);files.append(OUT/n)
    base.write(OUT/'training_locked.json',dict(locked_utc=base.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),new_validation_outputs_started=False,artifacts_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in files}))


def predictions(p):
    source=old.old.arrays(PARENT/'fold_0_decisions.npz');rows=p['roles']['inner_validation'];bind_parent(rows,source);sc=old.old.arrays(MODELS/'final_scaler.npz');x=(old.old.raw(rows)-sc['mean'])/sc['scale'];margins={}
    for pair in old.PAIRS:
        t=old.old.arrays(MODELS/(pair+'_final.npz'))['theta'];margins[pair+'_margin']=x@t[:-1]+t[-1]
    margin=old.coupled_margin(margins['psoriasis_margin'],margins['tinea_margin']);parent=source['monotone_additive'];d=old.old.route(parent,margin);f=OUT/'fold_0_predictions.npz';np.savez_compressed(f,paths=source['paths'],truth=source['truth'],parent=parent,zero_step175=parent,coupled_pair_specialist=d,coupled_margin=margin,**margins);files=[f];z=old.old.arrays(SOURCE/'validation_predictions.npz');f=OUT/'fold_1_replay.npz';np.savez_compressed(f,paths=z['paths'],truth=z['truth'],parent=z['parent'],zero_step175=z['parent'],coupled_pair_specialist=z[PRIMARY]);files.append(f);base.write(OUT/'prediction_locked.json',dict(locked_utc=base.utc(),metrics_started=False,fold1_reused_not_refit=True,artifacts_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in files}))


def score(p):
    folds={};changes={};source_p=base.read(SOURCE/'protocol.json')
    for fold,file,roles in [('0','fold_0_predictions.npz',p['roles']),('1','fold_1_replay.npz',source_p['roles'])]:
        z=old.old.arrays(OUT/file);rows=roles['inner_validation'];bind_parent(rows,z);parent=z['parent'];truth=z['truth'];ps=base.metrics_base.metrics(parent,truth);trials={}
        for name in ['zero_step175',PRIMARY]:
            d=z[name];s=base.metrics_base.metrics(d,truth);ff=old.old.failures(s,ps);trials[name]=dict(metrics=s,guard_failures=ff,guard_pass=not ff,changed=int(sum(d!=parent)),fixed=int(sum((d==truth)&(parent!=truth))),harmed=int(sum((d!=truth)&(parent==truth))),new_Lupus_true=int(sum((parent!=3)&(d==3)&(truth==3))),new_Lupus_false=int(sum((parent!=3)&(d==3)&(truth!=3))),per_source={source:base.metrics_base.metrics(d[ix],truth[ix]) for source in ['SCIN','original_train'] for ix in [np.array([a['source']==source for a in rows])]});changes['fold'+fold+'__'+name]=[dict(path=str(z['paths'][i]),truth=p['classes'][int(truth[i])],before=p['classes'][int(parent[i])],after=p['classes'][int(d[i])],source=rows[i]['source']) for i in np.flatnonzero(d!=parent)]
        folds[fold]=dict(validation_images=len(rows),reused=fold=='1',parent=ps,trials=trials)
    both=all(a['trials'][PRIMARY]['guard_pass'] for a in folds.values());base.write(OUT/'changed_cases.json',changes);base.write(OUT/'results.json',dict(completed_utc=base.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),folds=folds,primary_formula=PRIMARY,primary_both_fold_pass=both,inner_overlap=p['inner_overlap'],pooled_metrics_computed=False,new_helper_heads=20,new_scalers=4,new_CNN_fits=0,new_gate_fits=0,fold1_reused=True,single_fold_only=False,two_historical_folds_evaluated=True,all_six_jobs_complete=False,selected=None,global_5937_score_changed=False,serving_changed=False,research_registry_changed=False));base.verify(p);base.status('coupled_pair_fold0_repeat_complete_awaiting_review',selected=None)


if __name__=='__main__':
    base.OUT=OUT;base.process_lock();p=prepare()
    with threadpool_limits(limits=4):train(p);predictions(p);score(p)
