"""Matched linear/cosine eight-way frozen-feature heads, Lupus/Psoriasis pilot."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import pilot_teacher_pairwise_specialists as previous

ROOT,base,prior,latest=previous.ROOT,previous.base,previous.prior,previous.latest
OUT=ROOT/'ai-service/reports/teacher_cosine_classifier_fold0_seed42_20261025'
MODELS=ROOT/'ai-service/candidates'/OUT.name
ARMS=['linear_control','cosine_head'];METHODS=['current_policy',*ARMS]
CONFIG=dict(seed=42,steps=400,lr=.01,betas=[.9,.999],epsilon=1e-8,scale=16.,norm_epsilon=1e-12,threads=4)


def utc():return datetime.now(timezone.utc).isoformat()


def unit(x):
    x=np.asarray(x,dtype=float)
    if x.ndim!=2 or not np.isfinite(x).all() or (np.linalg.norm(x,axis=1)<=1e-12).any():raise ValueError('Finite nonzero feature rows required')
    return x/np.linalg.norm(x,axis=1,keepdims=True)


def route(current,q):
    current=np.asarray(current);q=np.asarray(q)
    if current.ndim!=1 or q.shape!=(len(current),8) or not np.isfinite(q).all() or (q<0).any() or not np.allclose(q.sum(1),1,atol=1e-8):raise ValueError('Aligned eight-way probabilities required')
    proposed=q.argmax(1);scope=np.isin(current,[0,2,3,4])&np.isin(proposed,[0,2,3,4])&(np.isin(current,[3,4])|np.isin(proposed,[3,4]))&(q.max(1)>=.8)
    result=np.where(scope,proposed,current);assert np.array_equal(result==5,current==5);return result


def focus(s):return float(np.mean([s['per_class'][c]['f1'] for c in ['Lupus','Psoriasis']]))


def choose(decisions,truth):
    scores={n:base.metrics(d,truth) for n,d in decisions.items()};trials={n:dict(metrics=s,guard_failures=prior.failures(s,scores['current_policy'])) for n,s in scores.items()}
    if scores['cosine_head']['macro_f1']+1e-12<scores['linear_control']['macro_f1']:trials['cosine_head']['guard_failures'].append('macro_f1_below_linear_control')
    for n in ['current_policy','linear_control']:
        if focus(scores['cosine_head'])<=focus(scores[n])+1e-12:trials['cosine_head']['guard_failures'].append('no_Lupus_Psoriasis_mean_f1_gain_vs_'+n)
    passing=[n for n,t in trials.items() if not t['guard_failures']]
    selected=max(passing,key=lambda n:(scores[n]['macro_f1'],np.mean([scores[n]['per_class'][c]['recall'] for c in ['Lupus','Psoriasis','Tinea']]),scores[n]['accuracy'],n=='current_policy',n=='linear_control'))
    return dict(selected=selected,trials=trials)


def prepare():
    if (OUT/'protocol.json').exists():p=base.read(OUT/'protocol.json');prior.verify(p);return p
    reg=base.read(ROOT/'ai-service/reports/active_research_track.json');assert reg['next_experiment'] is None
    parent=base.read(previous.features.OUT/'protocol.json');prior.verify(parent)
    original=base.read(ROOT/parent['parent_protocol']);roles={r:prior.role_rows(original,0,r) for r in ['train','inner_validation','outer_holdout']};source=base.read(previous.features.SOURCE/'protocol.json')
    for a,b in [('train','inner_validation'),('train','outer_holdout'),('inner_validation','outer_holdout')]:
        for key in ['path','sha256','group']:assert {z[key] for z in roles[a]}.isdisjoint({z[key] for z in roles[b]})
    files=[Path(__file__),ROOT/'ai-service/tests/test_teacher_cosine_classifier.py',ROOT/'ai-service/app/config.py',previous.features.OUT/'protocol.json',previous.features.OUT/'completion.json',
        latest.OUT/'oof_decisions.json',latest.OUT/'results.json',latest.OUT/'fold_0/inner_decisions.npz',latest.OUT/'fold_0/selection_locked.json',previous.features.SOURCE/'source_decisions.json',previous.features.SOURCE/'protocol.json']
    files += [prior.OUT/f'B_specialist/fold_0/{r}_features.npz' for r in roles]+[previous.features.SOURCE/'fold_0_resnet_features.npz']
    p=dict(name=OUT.name,registered_utc=utc(),fold=0,classes=base.CLASSES,roles=roles,source_protocol=(previous.features.SOURCE/'protocol.json').relative_to(ROOT).as_posix(),configuration=CONFIG,
        frozen_sha256={**parent['frozen_sha256'],**{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},
        representation='Reused original fold0 ResNet2048 cache, no CNN updates/forwards. StandardScaler fit only4043train rows, then exact row-L2 normalization both arms; all8classes retained. No auxiliary images, source labels or feature fitting using inner/outer.',
        comparison='Both heads8x2048,no bias. One seed42 standard-normal FP64 initialization row-normalized to unit length, identical logits at start. Linear:16*z@W.T. Cosine:16*z@(W/row_L2(W)).T with differentiable normalization. Both natural-frequency full-batch unweighted CE;400Adam updates,lr.01,betas.9/.999,eps1e-8,no decay/clipping/scheduler. Fixed final update400, no checkpoint/epoch search. Scale16 is a fixed engineering choice,not fitted calibration or the original paper scale.',
        routing='Only current/proposed in Acne,Eczema,Lupus,Psoriasis, and at least one endpoint Lupus/Psoriasis; full8top1 probability>=.8. No Acne-Eczema-only switch. Cancer/Candidiasis/Tinea/Warts exact prediction masks and P/R/F1 retained. No within-subset probability renormalization.',
        selection='Current/linear/cosine on718inner, prior strict guards Accuracy/MF and eachweakR/F1,weakPdrop<=.02,otherRdrop<=.02,CancerP/Rexact. Cosine additionally MF>=linear and Lupus/Psoriasis meanF1 strictly>current/linear. RankMF,mean3weakR,Acc,tiecurrentthenlinear. Lock final400step heads and choice before outer/source inference. No scale/step/threshold/seed scan.',
        evaluation='One exploratory fold:1176outer plus1709 historically investigated source photos, not new patienttest or a new5937OOF score. Report all3arms, raw8way heads, classes,confusion and transitions. No automatic API/reference replacement.',
        references=['https://arxiv.org/abs/1904.04232','https://arxiv.org/abs/1910.09217','https://github.com/wyharveychen/CloserLookFewShot/blob/master/backbone.py'],
        limitations=['This adapts cosine/decoupled-classifier ideas, not a reproduction of Baseline++ episodic fewshot tasks, its learnable class norms, published scales or benchmark claims.',
            'Trainfeature/parentCNN may overfit; weight normalization cannot create missing discriminative information or resolve uncertain labels. Trainnorm differences do not establish cause of validation errors.',
            'Cosine and linear have same trainable tensor count but different effective parameterization/gradient; common softmax threshold is not equally calibrated between arms.',
            'One seed/fold and repeatedly investigated cohorts; upstream policy/parentCNN previously used inner; no independent clinical confirmation.'],new_CNN_fits=0,new_backbones=0,new_heads=2,updates_each=400,global_5937_score_changed=False,serving_changed=False)
    OUT.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p);base.write(OUT/'research_registry_before.json',reg);reg['next_experiment']=OUT.relative_to(ROOT).as_posix();reg['next_experiment_status']='registered_cosine_Lupus_Psoriasis_pilot';base.write(ROOT/'ai-service/reports/active_research_track.json',reg);return p


def cached(role,rows):return previous.cached(role,rows).astype(float)


def probability(z,w,cosine):
    effective=unit(w) if cosine else w;logits=CONFIG['scale']*z@effective.T;logits-=logits.max(1,keepdims=True);q=np.exp(logits);return q/q.sum(1,keepdims=True)


def fit_and_lock(p):
    assert not (OUT/'selection_locked.json').exists();MODELS.mkdir(parents=True,exist_ok=True)
    rows=p['roles']['train'];raw=cached('train',rows);scaler=StandardScaler().fit(raw);z=unit(scaler.transform(raw));y=np.array([base.CLASSES.index(r['label']) for r in rows]);xt=torch.tensor(z,dtype=torch.float64);yt=torch.tensor(y,dtype=torch.long)
    torch.manual_seed(42);initial=F.normalize(torch.randn(8,2048,dtype=torch.float64),dim=1);np.savez_compressed(MODELS/'shared.npz',mean=scaler.mean_,scale=scaler.scale_,initial=initial.numpy())
    inner=p['roles']['inner_validation'];ix=unit(scaler.transform(cached('inner_validation',inner)))
    with np.load(latest.OUT/'fold_0/inner_decisions.npz',allow_pickle=False) as a:
        assert a['paths'].tolist()==[r['path'] for r in inner];truth=a['truth'].copy();current=a[base.read(latest.OUT/'fold_0/selection_locked.json')['selected']].copy()
    dd=dict(current_policy=current);raw_metrics={};training={}
    for name in ARMS:
        w=torch.nn.Parameter(initial.clone());opt=torch.optim.Adam([w],lr=.01,betas=(.9,.999),eps=1e-8);history=[];cosine=name=='cosine_head'
        for step in range(1,401):
            opt.zero_grad(set_to_none=True);effective=F.normalize(w,dim=1,eps=1e-12) if cosine else w;logits=16*xt@effective.T;loss=F.cross_entropy(logits,yt);assert torch.isfinite(loss);loss.backward()
            if step==1 or step%20==0:history.append(dict(step=step,loss_before_update=float(loss.detach()),gradient_norm=float(w.grad.norm()),weight_norms=w.detach().norm(dim=1).tolist()))
            opt.step()
        weight=w.detach().numpy().copy();np.savez_compressed(MODELS/f'{name}.npz',weight=weight,classes=base.CLASSES);q=probability(ix,weight,cosine);dd[name]=route(current,q);raw_metrics[name]=base.metrics(q.argmax(1),truth)
        np.savez_compressed(OUT/f'inner_{name}_probabilities.npz',paths=[r['path'] for r in inner],probabilities=q)
        trainq=probability(z,weight,cosine);training[name]=dict(steps=400,train_images=len(y),parameters=weight.size,history=history,train_raw=base.metrics(trainq.argmax(1),y),final_weight_norms=np.linalg.norm(weight,axis=1).tolist(),optimizer_steps=int(opt.state[w]['step']))
        print(dict(arm=name,steps=400,raw_inner=raw_metrics[name]['accuracy'],routed_inner=base.metrics(dd[name],truth)['macro_f1']),flush=True)
    np.savez_compressed(OUT/'inner_decisions.npz',paths=[r['path'] for r in inner],truth=truth,**dd);base.write(OUT/'training_report.json',training)
    audit={c:dict(train_images=int((y==i).sum()),feature_norm_median=float(np.median(np.linalg.norm(raw[y==i],axis=1)))) for i,c in enumerate(base.CLASSES)};base.write(OUT/'train_norm_audit.json',audit)
    files=[*MODELS.glob('*.npz'),OUT/'training_report.json',OUT/'train_norm_audit.json',OUT/'inner_decisions.npz',*[OUT/f'inner_{n}_probabilities.npz' for n in ARMS]]
    lock=choose(dd,truth);lock.update(locked_utc=utc(),protocol_sha256=base.sha(OUT/'protocol.json'),raw_validation=raw_metrics,artifacts_sha256={x.relative_to(ROOT).as_posix():base.sha(x) for x in files});base.write(OUT/'selection_locked.json',lock);print(dict(selected=lock['selected'],failures={n:v['guard_failures'] for n,v in lock['trials'].items()}),flush=True)


def evaluate(p):
    assert not (OUT/'results.json').exists();lock=base.read(OUT/'selection_locked.json');started=utc();source=base.read(ROOT/p['source_protocol']);reference={z['path']:z for z in base.read(latest.OUT/'oof_decisions.json')};external={z['path']:z for z in base.read(previous.features.SOURCE/'source_decisions.json')};held=[];results={}
    with np.load(MODELS/'shared.npz',allow_pickle=False) as a:mean,scale=a['mean'].copy(),a['scale'].copy()
    for role,rows in [('outer_holdout',p['roles']['outer_holdout']),('source_transfer',source['rows'])]:
        paths=[r['path'] for r in rows];z=unit((cached(role,rows)-mean)/scale);truth=np.array([base.CLASSES.index(r['label']) for r in rows]);current=np.array([reference[path]['predictions']['validation_selected'] if role=='outer_holdout' else external[path]['predictions']['validation_selected'][0] for path in paths]);dd=dict(current_policy=current);raw={}
        for n in ARMS:
            with np.load(MODELS/f'{n}.npz',allow_pickle=False) as a:w=a['weight'].copy()
            q=probability(z,w,n=='cosine_head');dd[n]=route(current,q);raw[n]=q.argmax(1);np.savez_compressed(OUT/f'{role}_{n}_probabilities.npz',paths=paths,probabilities=q)
        dd['validation_selected']=dd[lock['selected']]
        for i,row in enumerate(rows):held.append(dict(role=role,**row,predictions={n:int(d[i]) for n,d in dd.items()},raw_head_predictions={n:int(d[i]) for n,d in raw.items()}))
        index={path:i for i,path in enumerate(paths)};subsets={'original_outer':paths} if role=='outer_holdout' else source['subsets']
        for subset,items in subsets.items():
            ids=[index[path] for path in items];results[subset]=dict(images=len(ids),methods={n:base.metrics(d[ids],truth[ids]) for n,d in dd.items()},raw_heads={n:base.metrics(d[ids],truth[ids]) for n,d in raw.items()})
    base.write(OUT/'held_decisions.json',held);base.write(OUT/'results.json',dict(selected=lock['selected'],validation=lock['trials'],raw_validation=lock['raw_validation'],held=results,held_started_utc=started,completed_utc=utc(),protocol_sha256=base.sha(OUT/'protocol.json'),selection_sha256=base.sha(OUT/'selection_locked.json'),new_heads=2,new_CNN_fits=0,global_5937_score_changed=False,serving_changed=False));prior.verify(p);base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json')))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args();torch.set_num_threads(4);p=prepare()
    if args.prepare_only:return
    assert not (OUT/'results.json').exists(),'Preserve completed pilot'
    if not (OUT/'selection_locked.json').exists():fit_and_lock(p)
    evaluate(p)


if __name__=='__main__':
    with threadpool_limits(limits=4):main()
