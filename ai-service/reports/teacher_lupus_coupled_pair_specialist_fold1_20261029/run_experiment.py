"""Two natural pair experts coupled into a common Lupus-vs-weak posterior."""
from pathlib import Path
import importlib.util
import numpy as np
from scipy.optimize import minimize
from sklearn.model_selection import StratifiedGroupKFold
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;R=ROOT/'ai-service/reports';SOURCE=R/'teacher_lupus_triad_binary_specialist_fold1_20261029';PREVIOUS=R/'teacher_lupus_cv_probability_fusion_fold1_20261029';MODELS=ROOT/'ai-service/candidates'/OUT.name;SOURCE_MODELS=ROOT/'ai-service/candidates'/SOURCE.name
sp=importlib.util.spec_from_file_location('pairs_control196',SOURCE/'run_experiment.py');old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old);base=old.base
CS=[.0001,.001,.01];GRID=[(a,b) for a in CS for b in CS];PAIRS={'psoriasis':4,'tinea':6};PRIMARY='coupled_pair_specialist'


def coupled_margin(psoriasis,tinea):
    a=np.asarray(psoriasis,float);b=np.asarray(tinea,float)
    if a.ndim!=1 or b.shape!=a.shape or not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError('Aligned finite pair log-odds required')
    return -np.logaddexp(-a,-b)


def choose(losses):
    a=np.asarray(losses,float)
    if a.shape!=(9,) or not np.isfinite(a).all():raise ValueError('Nine finite TRAIN CV losses required')
    return next(GRID[i] for i,v in enumerate(a) if v<=a.min()+1e-12)


def prepare():
    assert not (OUT/'protocol.json').exists(),'Preserve200registration';src=base.read(PREVIOUS/'protocol.json');base.verify(src);receipt=base.read(PREVIOUS/'completion.json');assert receipt['status']=='complete_verified_cv_probability_fusion_pilot_199' and base.read(PREVIOUS/'independent_review.json')['status']=='PASS';frozen=dict(src['frozen_sha256'])
    for lock in ['training_locked.json','prediction_locked.json']:
        for f,h in base.read(PREVIOUS/lock)['artifacts_sha256'].items():assert base.sha(ROOT/f)==h;frozen[f]=h
    for n in ['protocol.json','results.json','independent_review.json','completion.json','train_selection.json','training_locked.json','prediction_locked.json']:
        if n!='completion.json':assert base.sha(PREVIOUS/n)==receipt['artifacts_sha256'][n]
        frozen[(PREVIOUS/n).relative_to(ROOT).as_posix()]=base.sha(PREVIOUS/n)
    for f in [Path(__file__),ROOT/'ai-service/tests/test_lupus_coupled_pair_specialist.py',ROOT/'tmp/review_lupus_coupled_pair_specialist_20261029.py',ROOT/'tmp/review_teacher_priorities_20261022.py']:frozen[f.relative_to(ROOT).as_posix()]=base.sha(f)
    p=dict(registered_utc=base.utc(),classes=src['classes'],fold=1,roles=src['roles'],frozen_sha256=frozen,imagenet_path=src['imagenet_path'],imagenet_sha256=src['imagenet_sha256'],primary_formula=PRIMARY,C_grid=CS,pairs=PAIRS,
        scope='200 adaptive specialized-pair task following199selected100%RBF/no gain. Train separateLP-v-Pso andLP-v-Tin natural logisticexperts, coupletwo ratios intooneLPposterior. SameCNImageNet768,4031train,1489weak,217LP; nonewbackbone/CNN/PCA/scaler/newpatients.',
        training='Reuse196SGKF3seed28168 ALL8TRAINsplits and4immutableALL8fitStandardScalers. For pairPso fitONLYtrueLP3/Pso4 subtrain; pairTin fitONLYtrueLP3/Tin6 subtrain. NaturalSUMbinaryNLL+.5normW2/C,interceptunpenalized,zero769theta,LBFGS6000gtol1e-8ftol1e-15maxls50 success/maxgradient<1e-3. No classbalancing/hardmining/sourceweights.2pairs*(3CV*3C+1final)=20newheads.',
        coupling='Pairlogits mP=logscoreLP/Pso,mT=logscoreLP/Tin. CommonweakLP q=1/(1+exp(-mP)+exp(-mT)); stablebinaryLPlogit=-logaddexp(-mP,-mT). Normalized3waymass[1,exp(-mP),exp(-mT)] prevents simply using higher pairprior asifallweaknegativepriorunchanged. Withintercept-onlynaturalcounts yieldsNLP/(NLP+NPso+NTin). Scores stillnotclinicalcalibration, independentpairmodelsneednotperfectlycohere.',
        selection='NinefixedCcombinations(Pso,Tin) in1e-4/1e-3/1e-2. Predictall8CVheldoutrows withpairheads; evaluateCOUPLEDbinarynaturalNLL onSAMEtrueweakheldout1489. LowestpooledNLL, ties1e-12 prefer smallerCPso thenCTin. SelectpairCsjointly withinTRAIN, not by713test orindividualpairNLL. Fittwofinalheads onallowntruepairtrain using196finalscaler. No threshold/extraC/gamma/policygrid.',
        inference='Start175same196route: onlyparentPso4/Tin6 ANDcoupledLPlogitSTRICT>0 =>LP3. ExistingLP andoutside5masks exact, zeroskeep. AlwayscoupleBOTHpairheads; notchooseheadbyknowntruth/path/source orafterseeingvalidation. Endpointszero175/previous196weakfocus controls; onlycoupledpairprimary.',
        boundary='Freezecode/tests/reviewer/input/protocol beforefits. Lock20heads/CVmargins/pairCs/selection BEFORE713newoutputs; lockhardoutputs BEFOREmetrics. No newouter/global5937scoring. Historical713/hypothesesalreadyseen, adaptiveexploratoryonefold only.',guards=src['guards'],
        audit='Independently reconstructSGKF3/exactpairlossrows/scalers,20convexobjective/gradients/CVmargins; couplingreferencevia3waylogsumexp versusproductionlogaddexp; nineNLL/Ctie/finalweights;validationroutes/all8metrics/sources/cases/fullguards/masks. Inherit196/175CNNaudits, notindependentfullrefits.',
        limitations=src['limitations']+['Pairwiseprobabilitycoupling assumesusablecommonposteriorratios; discriminativepairheads maynotcohere/calibrate. SeparateboundariesmayincreaseFP evenwithpriorconsistency. Same713repeated/adaptive, no unbiasedtest or clinicalconclusion. TrainselectedCVlossoptimistic; sourceSCINLP remainsfew.'],
        new_helper_heads=20,new_kernel_bases=0,new_scalers=0,new_gate_fits=0,new_CNN_fits=0,new_PCA_fits=0,single_fold_only=True,all_six_jobs_complete=False,selected=None,global_5937_score_changed=False,serving_changed=False,research_registry_changed=False)
    MODELS.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p);base.verify(p);return p


def train(p):
    rows=p['roles']['train'];xx=old.raw(rows);labels=np.array([p['classes'].index(a['label']) for a in rows]);target=(labels==3).astype(int);weak=np.isin(labels,[3,4,6]);groups=[a['group'] for a in rows];splits=list(StratifiedGroupKFold(3,shuffle=True,random_state=28168).split(np.zeros(len(rows)),labels,groups));cv={a:np.full((3,len(rows)),np.nan) for a in PAIRS};files=[];fits={}
    def save(name,**values):
        f=MODELS/name;np.savez_compressed(f,**values);files.append(f)
    def fit(name,x,y,c):
        op=minimize(old.objective,np.zeros(769),args=(x,y,c),jac=True,method='L-BFGS-B',options=dict(maxiter=6000,gtol=1e-8,ftol=1e-15,maxls=50));value,g=old.objective(op.x,x,y,c);assert op.success and max(abs(g))<1e-3,(name,op.message,float(max(abs(g))));save(name+'.npz',theta=op.x,c=c);fits[name]=dict(rows=len(y),positives=int(sum(y)),negatives=int(sum(y==0)),c=c,objective=value,gradient_max_abs=float(max(abs(g))),iterations=int(op.nit),success=True);return op.x
    for k,(tr,va) in enumerate(splits):
        sc=old.arrays(SOURCE_MODELS/f'cv{k}_scaler.npz');assert np.array_equal(sc['train_indices'],tr) and np.array_equal(sc['holdout_indices'],va)
        for key in ['path','sha256','group']:assert {rows[i][key] for i in tr}.isdisjoint({rows[i][key] for i in va})
        xv=(xx[va]-sc['mean'])/sc['scale']
        for pair,cid in PAIRS.items():
            ix=tr[np.isin(labels[tr],[3,cid])];x=(xx[ix]-sc['mean'])/sc['scale']
            for ci,c in enumerate(CS):t=fit(f'{pair}_cv{k}_c{ci}',x,target[ix],c);cv[pair][ci,va]=xv@t[:-1]+t[-1]
        print(dict(CV=k+1,new_pair_heads=len(fits)),flush=True)
    assert all(np.isfinite(a).all() for a in cv.values());losses=[]
    for cp,ct in GRID:
        margin=coupled_margin(cv['psoriasis'][CS.index(cp)],cv['tinea'][CS.index(ct)]);losses.append(float(np.mean(np.logaddexp(0,margin[weak])-target[weak]*margin[weak])))
    cp,ct=choose(losses);selection=dict(psoriasis_C=cp,tinea_C=ct,selection_images=int(sum(weak)),scores=[dict(psoriasis_C=a,tinea_C=b,nll=v) for (a,b),v in zip(GRID,losses)]);sc=old.arrays(SOURCE_MODELS/'final_scaler.npz')
    for pair,c in [('psoriasis',cp),('tinea',ct)]:
        ix=np.flatnonzero(np.isin(labels,[3,PAIRS[pair]]));fit(pair+'_final',(xx[ix]-sc['mean'])/sc['scale'],target[ix],c)
    assert len(fits)==20;save('train_CV_predictions.npz',paths=[a['path'] for a in rows],labels=labels,truth=target,weak=weak,**cv)
    for name,value in [('training_report.json',dict(fits=fits,heads=20,reused_scalers=4,train_images=4031,weak_images=int(sum(weak)),Lupus_images=int(sum(target)),pair_counts={pair:int(sum(np.isin(labels,[3,cid]))) for pair,cid in PAIRS.items()})),('selection.json',selection)]:base.write(OUT/name,value);files.append(OUT/name)
    base.write(OUT/'training_locked.json',dict(locked_utc=base.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),new_validation_outputs_started=False,artifacts_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in files}))


def evaluate(p):
    previous=old.arrays(SOURCE/'validation_predictions.npz');rows=p['roles']['inner_validation'];assert previous['paths'].tolist()==[a['path'] for a in rows];parent=previous['parent'];truth=previous['truth'];sc=old.arrays(SOURCE_MODELS/'final_scaler.npz');x=(old.raw(rows)-sc['mean'])/sc['scale'];margins={}
    for pair in PAIRS:
        t=old.arrays(MODELS/(pair+'_final.npz'))['theta'];margins[pair+'_margin']=x@t[:-1]+t[-1]
    margin=coupled_margin(margins['psoriasis_margin'],margins['tinea_margin']);outputs=dict(zero_step175=parent,previous196_weak_focus=previous['weak_focus'],coupled_pair_specialist=old.route(parent,margin));f=OUT/'validation_predictions.npz';np.savez_compressed(f,paths=previous['paths'],truth=truth,parent=parent,coupled_margin=margin,**margins,**outputs);base.write(OUT/'prediction_locked.json',dict(locked_utc=base.utc(),metrics_started=False,artifacts_sha256={f.relative_to(ROOT).as_posix():base.sha(f)}));ps=base.metrics_base.metrics(parent,truth);trials={};changes={}
    for name,d in outputs.items():
        s=base.metrics_base.metrics(d,truth);ff=old.failures(s,ps);trials[name]=dict(metrics=s,guard_failures=ff,guard_pass=not ff,changed=int(sum(d!=parent)),fixed=int(sum((d==truth)&(parent!=truth))),harmed=int(sum((d!=truth)&(parent==truth))),new_Lupus_true=int(sum((parent!=3)&(d==3)&(truth==3))),new_Lupus_false=int(sum((parent!=3)&(d==3)&(truth!=3))),per_source={source:base.metrics_base.metrics(d[ix],truth[ix]) for source in ['SCIN','original_train'] for ix in [np.array([a['source']==source for a in rows])]});changes[name]=[dict(path=str(previous['paths'][i]),truth=p['classes'][int(truth[i])],before=p['classes'][int(parent[i])],after=p['classes'][int(d[i])]) for i in np.flatnonzero(d!=parent)]
    base.write(OUT/'changed_cases.json',changes);base.write(OUT/'results.json',dict(completed_utc=base.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),parent=ps,trials=trials,primary_formula=PRIMARY,primary_guard_pass=trials[PRIMARY]['guard_pass'],new_gate_fits=0,new_helper_heads=20,new_kernel_bases=0,new_CNN_fits=0,single_fold_only=True,all_six_jobs_complete=False,selected=None,global_5937_score_changed=False,serving_changed=False,research_registry_changed=False));base.verify(p);base.status('lupus_coupled_pair_complete_awaiting_review',selected=None)


if __name__=='__main__':
    base.OUT=OUT;base.process_lock();p=prepare()
    with threadpool_limits(limits=4):train(p);evaluate(p)
