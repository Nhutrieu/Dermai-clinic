"""Nested group-crossfit keep/stack gate; no CNN updates or threshold search."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from pathlib import Path
import warnings
import numpy as np
from scipy.special import expit
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import run_teacher_logprob_stacking as stack

original=stack.previous
base=stack.base
ROOT=stack.ROOT
NAME='teacher_conservative_gate_seed42_20261023'
OUT=ROOT/'ai-service/reports'/NAME
MODELS=ROOT/'ai-service/candidates'/NAME
THRESHOLD=2/3
EPS=1e-7


def utc():return datetime.now(timezone.utc).isoformat()


def gate_features(parents,probability,current):
    """22 runtime-only features, never accepting labels or source identities."""
    stack.features(parents)  # Validate aligned parent distributions.
    probability=np.asarray(probability,dtype=float);current=np.asarray(current,dtype=int)
    candidate=stack.route(current,probability)
    n=len(current);idx=np.arange(n)
    if n!=len(parents[0]) or np.any((current<0)|(current>7)):raise ValueError('Invalid baseline indices')
    logp=[np.log(np.clip(np.asarray(p),EPS,1)) for p in parents]
    columns=[p[idx,candidate]-p[idx,current] for p in logp]
    lp=np.log(np.clip(probability,EPS,1));columns.append(lp[idx,candidate]-lp[idx,current])
    votes=np.stack([np.asarray(p).argmax(1) for p in parents],1)
    columns.append(((votes==candidate[:,None]).sum(1)-(votes==current[:,None]).sum(1))/3)
    entropy=np.mean([-np.sum(np.asarray(p)*lp,axis=1)/np.log(8) for p,lp in zip(parents,logp)],axis=0)
    columns.append(entropy)
    result=np.column_stack([*columns,np.eye(8)[current],np.eye(8)[candidate]])
    assert result.shape==(n,22) and np.isfinite(result).all()
    return result,candidate


def gate_targets(current,candidate,truth):
    current=np.asarray(current);candidate=np.asarray(candidate);truth=np.asarray(truth)
    if current.shape!=candidate.shape or current.shape!=truth.shape:raise ValueError('Unaligned labels')
    eligible=(current!=5)&(candidate!=5)&(candidate!=current)
    fixed=(candidate==truth)&(current!=truth)&eligible
    harmed=(current==truth)&(candidate!=truth)&eligible
    target=np.full(len(truth),-1,dtype=int);target[fixed]=1;target[harmed]=0
    return target


def fit_gate(x,target):
    target=np.asarray(target);mask=target>=0
    report=dict(input_rows=len(x),fit_rows=int(mask.sum()),target_counts=np.bincount(target[mask],minlength=2).tolist())
    if np.unique(target[mask]).tolist()!=[0,1]:
        return dict(kind='always_keep',mean=np.zeros(22),scale=np.ones(22),coef=np.zeros((0,22)),
            intercept=np.zeros(0),classes=np.array([0,1])),{**report,'kind':'always_keep','iterations':[]}
    scaler=StandardScaler().fit(x[mask])
    with warnings.catch_warnings():
        warnings.simplefilter('error',ConvergenceWarning)
        head=LogisticRegression(C=.1,penalty='l2',solver='lbfgs',class_weight=None,
            max_iter=3000,tol=1e-7,random_state=42).fit(scaler.transform(x[mask]),target[mask])
    assert head.classes_.tolist()==[0,1]
    model=dict(kind='logistic',mean=scaler.mean_,scale=scaler.scale_,coef=head.coef_,intercept=head.intercept_,classes=head.classes_)
    return model,{**report,'kind':'logistic','iterations':head.n_iter_.tolist()}


def gate_probability(model,x):
    if str(model['kind'])=='always_keep':return np.zeros(len(x))
    assert str(model['kind'])=='logistic' and np.asarray(model['classes']).tolist()==[0,1]
    return expit(((x-model['mean'])/model['scale'])@np.asarray(model['coef'])[0]+np.asarray(model['intercept'])[0])


def route(current,candidate,score):
    current=np.asarray(current,dtype=int);candidate=np.asarray(candidate,dtype=int);score=np.asarray(score)
    if current.shape!=candidate.shape or score.shape!=current.shape or not np.isfinite(score).all() or np.any((score<0)|(score>1)):
        raise ValueError('Aligned decisions and probabilities required')
    allowed=(current!=5)&(candidate!=5)&(candidate!=current)&(score>THRESHOLD)
    result=np.where(allowed,candidate,current)
    assert np.array_equal(result==5,current==5)
    return result


def candidate_model(x,y):
    scaler,head=stack.fit(x,y)
    return dict(kind='stack',mean=scaler.mean_,scale=scaler.scale_,coef=head.coef_,intercept=head.intercept_,classes=head.classes_)


def candidate_probability(model,x):
    assert np.asarray(model['classes']).tolist()==list(range(8))
    z=((x-model['mean'])/model['scale'])@model['coef'].T+model['intercept'];z-=z.max(1,keepdims=True)
    v=np.exp(z);return v/v.sum(1,keepdims=True)


def save(path,model):
    path.parent.mkdir(parents=True,exist_ok=True)
    assert not path.exists(),'Do not overwrite a trained artifact'
    np.savez_compressed(path,**model)


def load(path):
    with np.load(path,allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}


def nested_parts(truth,groups):
    parts=np.full(len(truth),-1,dtype=int)
    for part,(fit,hold) in enumerate(StratifiedGroupKFold(n_splits=2,shuffle=True,random_state=42).split(np.zeros(len(truth)),truth,groups)):
        assert set(groups[fit]).isdisjoint(groups[hold])
        assert np.unique(truth[fit]).tolist()==list(range(8))
        parts[hold]=part
    assert (parts>=0).all()
    return parts


def fit_part(parents,current,truth,groups,parts,part,model_dir=None,trace_path=None):
    """No held-meta labels enter either nested candidate fits or gate fit."""
    x=stack.features(parents);fit=np.flatnonzero(parts!=part);hold=np.flatnonzero(parts==part)
    assert set(groups[fit]).isdisjoint(groups[hold])
    nested=nested_parts(truth[fit],groups[fit]);q=np.full((len(fit),8),np.nan)
    audit=[]
    for sub in range(2):
        train=fit[nested!=sub];test=fit[nested==sub]
        model=candidate_model(x[train],truth[train]);q[nested==sub]=candidate_probability(model,x[test])
        if model_dir is not None:save(model_dir/f'candidate_nested_{sub}.npz',model)
        audit.append(dict(part=sub,fit_indices=train.tolist(),hold_indices=test.tolist()))
    assert np.isfinite(q).all()
    gate_x,candidate=gate_features([p[fit] for p in parents],q,current[fit])
    target=gate_targets(current[fit],candidate,truth[fit])
    gate,report=fit_gate(gate_x,target)
    model=candidate_model(x[fit],truth[fit]);held_probability=candidate_probability(model,x[hold])
    held_x,held_candidate=gate_features([p[hold] for p in parents],held_probability,current[hold])
    score=gate_probability(gate,held_x);decision=route(current[hold],held_candidate,score)
    if model_dir is not None:
        save(model_dir/'candidate_fit.npz',model);save(model_dir/'gate.npz',gate)
    if trace_path is not None:
        trace_path.parent.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(trace_path,fit_indices=fit,hold_indices=hold,nested_parts=nested,
            nested_probability=q,gate_features=gate_x,gate_target=target,
            gate_decisive_indices=fit[target>=0],held_probability=held_probability,
            held_gate_features=held_x,held_gate_score=score,held_candidate=held_candidate,held_decision=decision)
    report={**report,'part':part,'fit_indices':fit.tolist(),'hold_indices':hold.tolist(),'nested':audit,
        'nested_only_fit_groups':True,'candidate_fits':3,
        'excluded_both_wrong_disagreements':int(((candidate!=current[fit])&(current[fit]!=5)&(candidate!=truth[fit])&(current[fit]!=truth[fit])).sum())}
    return hold,held_probability,score,decision,report


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');original.verify(p);return p
    parent_path=original.OUT/'protocol.json';parent=base.read(parent_path);original.verify(parent)
    registry=base.read(ROOT/'ai-service/reports/active_research_track.json');assert registry['next_experiment'] is None
    files=[Path(__file__),Path(stack.__file__),ROOT/'ai-service/tests/test_teacher_conservative_gate.py',
        parent_path,stack.OUT/'protocol.json',stack.OUT/'results.json',stack.OUT/'independent_review.json',
        base.OUT/'oof_decisions.json',base.SERVING,
        ROOT/'ai-service/reports/teacher_complementarity_routing_audit_20261023/results.json']
    for f in range(5):files += [base.fold_dir(f)/'validation_predictions.npz',base.fold_dir(f)/'test_predictions.json',
        stack.MODELS/f'fold_{f}/stack.npz',stack.OUT/f'fold_{f}/inner_crossfit.npz']
    frozen={**parent['frozen_sha256'],**{f.relative_to(ROOT).as_posix():base.sha(f) for f in files}}
    p=dict(name=NAME,registered_utc=utc(),classes=base.CLASSES,parent_protocol=parent_path.relative_to(ROOT).as_posix(),
        frozen_sha256=frozen,images=5937,folds=5,
        candidate='Same24logparent feature stack, unweighted multiclass L2logistic C=.1; refit fresh. Exact Cancer mask from baseline. Raw stack control, not new CNN.',
        features='22: three parent logp(candidate)-logp(baseline), stack logp(candidate)-logp(baseline), (parent votes candidate-baseline)/3, mean parent entropy/log8, baseline onehot8, candidate onehot8. Clip log at1e-7.',
        gate=dict(head='Unweighted binary L2logistic',C=.1,solver='lbfgs',max_iter=3000,tol=1e-7,seed=42,
            scaler='StandardScaler fit on all22features of decisive fit rows only',threshold=THRESHOLD,
            routing='Strict score>2/3; exacttie keeps baseline. Only nonCancer baseline/stack disagreements. No threshold or feature sweep.',
            target='1=stackcorrect/baselinewrong,0=baselinecorrect/stackwrong. Bothwrong and agreement rows excluded from gate fit; all rows evaluated. Missing either class alwayskeeps baseline.'),
        nested='For each targetCNNfold,3SGKF inner meta-parts seed42. Within each two-thirds fit subset,2SGKF seed42 produce held stack probabilities for gate training. Fit gate on those decisive rows; fit stack on alltwo-thirds to predict outermeta-heldthird. No held-meta groups used by candidate/gate/scalers.',
        final='Final gate fitted from3fold inner OOF candidate probabilities only. Then fit final stack onfullinner. Never use stack in-sample probabilities to fit finalgate. New50candidatefits +up to20gates; no backbonefit.',
        selection='Original strictguards and ranking on nestedheld inner decisions. Baseline vsconservative_gate eligible; rawstack control reported only. Lock all5 choices before outer inference; no selection from finalgate in-sample or outer results.',
        reporting='Full rawstack,rawgate,validationselected vsbaseline; all8labels/weakdiseases/source/fold, fixes/harms/wrongtowrong, fixed1000groupbootstrap.',
        limitations=['Exploratory development: allouter/inner previously studied, not a fresh independent clinical test.',
            'CNN parent checkpoints and baseline weights previously used fullinner for selection; nested meta-fitting does not undo inherited exposure or makeCNNvalidation fully nested.',
            'Gate labels/probabilities conditional on decisive disagreements, not clinically calibrated disease probabilities.',
            'Bothwrong rows carry zero relativeAccuracy benefit but changingwronglabels can alter MacroF1/precision; heldguards evaluate allrows.',
            'Few decisive examples and shift from nestedhalf-fit stack to2/3fit and finalfullinner stack confidence. OneCNNseed; groups not verifiedpatients.',
            'Cancer mask preserves existing false positives and negatives. No new data, relabeling, API or Word change.',
            'Borrow gating/stacking ideas only; not a reproduction of jointlytrained mixturesofexperts. Fixedthreshold2/3 is an engineering prior, not selected using outcomes.'],
        references=['https://www.cs.toronto.edu/~hinton/absps/jjnh91.pdf',
            'https://scikit-learn.org/1.3/modules/generated/sklearn.ensemble.StackingClassifier.html'],serving_changed=False)
    OUT.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p);base.write(OUT/'research_registry_before.json',registry)
    registry['next_experiment']=OUT.relative_to(ROOT).as_posix();registry['next_experiment_status']='registered_nested_conservative_keep_stack_gate'
    base.write(ROOT/'ai-service/reports/active_research_track.json',registry)
    return p


def fit_all(p):
    assert not (OUT/'all_selections_locked.json').exists(),'Preserve completed fits'
    parent=base.read(ROOT/p['parent_protocol']);counts=dict(candidate_fits=0,gate_fits=0,always_keep_fallbacks=0)
    for f in range(5):
        paths,y,_,_,current=original.validation(parent,f)
        with np.load(base.fold_dir(f)/'validation_predictions.npz',allow_pickle=False) as z:parents=[z[k].copy() for k in stack.PARENTS]
        x=stack.features(parents);groups=np.array([parent['manifest'][path]['scene_or_case_group'] for path in paths])
        parts=stack.assignments(y,groups);q=np.full((len(y),8),np.nan);scores=np.full(len(y),np.nan);gated=np.full(len(y),-1)
        model_dir=MODELS/f'fold_{f}';folder=OUT/f'fold_{f}';folder.mkdir(parents=True,exist_ok=True);audit=[]
        for part in range(3):
            hold,pp,s,decision,report=fit_part(parents,current,y,groups,parts,part,
                model_dir/f'meta_{part}',folder/f'meta_{part}_training.npz')
            q[hold]=pp;scores[hold]=s;gated[hold]=decision;audit.append(report)
            counts['candidate_fits']+=3;counts['gate_fits']+=report['kind']=='logistic';counts['always_keep_fallbacks']+=report['kind']=='always_keep'
        with np.load(stack.OUT/f'fold_{f}/inner_crossfit.npz',allow_pickle=False) as z:
            assert z['paths'].tolist()==paths and np.array_equal(z['parts'],parts)
            assert np.allclose(q,z['probability'],atol=1e-12,rtol=0),'Fresh stack differs from previous control'
        raw=stack.route(current,q)
        lock=original.choose(dict(current_fusion=current,conservative_gate=gated),y)
        lock['raw_stack_control']=dict(metrics=base.metrics(raw,y),guard_failures=original.failures(base.metrics(raw,y),base.metrics(current,y)))
        # Final gate uses only candidate cross-predictions, before final candidate is fit.
        gx,_=gate_features(parents,q,current);target=gate_targets(current,raw,y)
        gate,gate_report=fit_gate(gx,target);save(model_dir/'gate.npz',gate)
        counts['gate_fits']+=gate_report['kind']=='logistic';counts['always_keep_fallbacks']+=gate_report['kind']=='always_keep'
        final=candidate_model(x,y);save(model_dir/'stack.npz',final);counts['candidate_fits']+=1
        with np.load(stack.MODELS/f'fold_{f}/stack.npz',allow_pickle=False) as z:
            for key in ['mean','scale','coef','intercept']:assert np.allclose(final[key],z[key],atol=1e-10,rtol=0),key
        np.savez_compressed(folder/'inner_crossfit.npz',paths=paths,truth=y,groups=groups,parts=parts,
            current=current,candidate_probability=q,raw_stack=raw,gate_score=scores,gate_decision=gated,
            final_gate_features=gx,final_gate_target=target,protocol_sha256=base.sha(OUT/'protocol.json'))
        base.write(folder/'training_report.json',dict(fold=f,inner_images=len(y),inner_groups=len(set(groups)),
            meta_parts=audit,final_gate=gate_report,candidate_fits=10,gate_fit_calls=4,
            actual_gate_fits=sum(a['kind']=='logistic' for a in audit)+(gate_report['kind']=='logistic'),
            original_stack_reproduced=True,CNN_updated=False,final_stack_in_sample_not_used_for_gate=True))
        artifacts=[*model_dir.rglob('*.npz'),*folder.glob('*.npz'),folder/'training_report.json']
        lock.update(locked_utc=utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
            artifacts_sha256={a.relative_to(ROOT).as_posix():base.sha(a) for a in artifacts})
        base.write(folder/'selection_locked.json',lock)
        print(dict(fold=f,selected=lock['selected'],gate_guard_failures=lock['trials']['conservative_gate']['guard_failures'],final_gate=gate_report),flush=True)
    base.write(OUT/'all_selections_locked.json',dict(locked_utc=utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
        selections_sha256={str(f):base.sha(OUT/f'fold_{f}/selection_locked.json') for f in range(5)},fits=counts))
    original.verify(p)


def evaluate(p):
    assert not (OUT/'results.json').exists(),'Preserve completed evaluation'
    locks=base.read(OUT/'all_selections_locked.json');parent=base.read(ROOT/p['parent_protocol'])
    assert locks['selections_sha256']=={str(f):base.sha(OUT/f'fold_{f}/selection_locked.json') for f in range(5)}
    rows=[];started=utc()
    for f in range(5):
        records,_,_,current=original.outer_rows(parent,f);lock=base.read(OUT/f'fold_{f}/selection_locked.json')
        for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
        parents=[np.asarray([r['probabilities'][k] for r in records]) for k in stack.PARENTS]
        q=candidate_probability(load(MODELS/f'fold_{f}/stack.npz'),stack.features(parents))
        gx,raw=gate_features(parents,q,current);score=gate_probability(load(MODELS/f'fold_{f}/gate.npz'),gx)
        gated=route(current,raw,score);decisions=dict(current_fusion=current,raw_stack=raw,conservative_gate=gated)
        decisions['validation_selected']=decisions[lock['selected']]
        output=original.records(records,f,decisions)
        for i,row in enumerate(output):row.update(gate_score=float(score[i]),candidate_pred=int(raw[i]))
        rows+=output
    rows.sort(key=lambda r:r['path']);assert len(rows)==len({r['path'] for r in rows})==5937
    y=np.array([base.CLASSES.index(r['label']) for r in rows]);current=np.array([r['predictions']['current_fusion'] for r in rows])
    reference={r['path']:r['predictions'][base.SELECTED] for r in base.read(base.OUT/'oof_decisions.json')}
    assert current.tolist()==[reference[r['path']] for r in rows]
    methods={}
    for name in rows[0]['predictions']:
        pred=np.array([r['predictions'][name] for r in rows]);assert np.array_equal(pred==5,current==5)
        score=base.metrics(pred,y);score.update(correct=int((pred==y).sum()),changed=int((pred!=current).sum()),
            corrected=int(((current!=y)&(pred==y)).sum()),broken=int(((current==y)&(pred!=y)).sum()),
            wrong_to_wrong=int(((pred!=current)&(current!=y)&(pred!=y)).sum()),
            paired_delta_95pct=original.paired_intervals(rows,pred,current,y))
        score['per_source']={}
        for source in ['original_train','SCIN']:
            mask=np.array([r['source']==source for r in rows]);score['per_source'][source]=dict(images=int(mask.sum()),**base.metrics(pred[mask],y[mask]))
        methods[name]=score
    assert methods['raw_stack']['confusion_matrix']==base.read(stack.OUT/'results.json')['methods']['logprob_stack']['confusion_matrix']
    per_fold=[]
    for f in range(5):
        rr=[r for r in rows if r['fold']==f];yy=np.array([base.CLASSES.index(r['label']) for r in rr])
        per_fold.append(dict(fold=f,selected=base.read(OUT/f'fold_{f}/selection_locked.json')['selected'],
            methods={n:base.metrics(np.array([r['predictions'][n] for r in rr]),yy) for n in methods}))
    result=dict(status='complete_exploratory_nested_gate_fivefold',images=5937,methods=methods,per_fold=per_fold,
        actual_fits=locks['fits'],outer_started_utc=started,completed_utc=utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
        all_selections_sha256=base.sha(OUT/'all_selections_locked.json'),baseline_changed=False,serving_changed=False,
        limitations=p['limitations'])
    base.write(OUT/'oof_decisions.json',rows);base.write(OUT/'results.json',result);original.verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),
        decisions_sha256=base.sha(OUT/'oof_decisions.json'),all_five_choices_locked_before_outer=True,
        original_stack_reproduced=True,cancer_mask_unchanged=True,scope='Technical consistency, not clinical validation'))
    base.write(OUT/'status.json',dict(state='complete',utc=utc()))
    print({n:{k:s[k] for k in ['accuracy','macro_f1','correct','changed','corrected','broken']} for n,s in methods.items()},flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--register-only',action='store_true');args=parser.parse_args()
    with threadpool_limits(limits=1):
        p=prepare()
        if not args.register_only:fit_all(p);evaluate(p)


if __name__=='__main__':main()
