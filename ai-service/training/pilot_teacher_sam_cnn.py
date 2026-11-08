"""Matched AdamW CE versus SAM-AdamW CNN continuation for Tinea/Eczema."""
from __future__ import annotations
import argparse
import hashlib
import math
import os
from pathlib import Path
import time
import numpy as np
import torch
from torch.nn import functional as F

import pilot_teacher_focal_cnn as previous
from common import ImageSampleDataset,seed_everything

ROOT,base,prior,latest,engine=previous.ROOT,previous.base,previous.prior,previous.latest,previous.engine
OUT=ROOT/'ai-service/reports/teacher_sam_cnn_fold0_seed42_20261025'
MODELS=ROOT/'ai-service/candidates'/OUT.name
ARMS=['ce_control','sam_rho005'];CONFIG={**previous.CONFIG,'rho':.05};CONFIG.pop('gamma',None)
HANDLE=None


def perturb(parameters,rho):
    """Global L2 SAM ascent; snapshots allow exact restoration before AdamW."""
    parameters=list(parameters)
    if not math.isfinite(rho) or rho<0:raise ValueError('Finite nonnegative SAM radius required')
    if not parameters or any(p.grad is None or not torch.isfinite(p.grad).all() for p in parameters):raise ValueError('Finite gradients required for every trainable parameter')
    saved=[p.detach().clone() for p in parameters]
    norm=torch.linalg.vector_norm(torch.stack([torch.linalg.vector_norm(p.grad.detach().float()) for p in parameters]))
    factor=rho/(norm+1e-12)
    with torch.no_grad():
        for p in parameters:p.add_(p.grad,alpha=float(factor))
    return saved,float(norm)


def restore(parameters,saved):
    if len(parameters)!=len(saved):raise ValueError('Snapshots must match the trainable parameter list')
    with torch.no_grad():
        for p,value in zip(parameters,saved):p.copy_(value)


def pair_route(current,probabilities):
    pp=np.asarray(probabilities);current=np.asarray(current)
    if pp.shape!=(len(current),8) or not np.isfinite(pp).all() or (pp<0).any() or not np.allclose(pp.sum(1),1,atol=1e-6):raise ValueError('Aligned normalized eight-way scores required')
    top=pp.argmax(1);mask=np.isin(current,[2,6])&np.isin(top,[2,6])&(pp.max(1)>=.8)
    result=current.copy();result[mask]=top[mask]
    return result


def pair_f1(s):return float(np.mean([s['per_class'][c]['f1'] for c in ['Tinea','Eczema']]))


def objective(score,current):return [int(not prior.failures(score,current)),score['macro_f1'],pair_f1(score),score['accuracy']]


def choose(decisions,truth):
    scores={n:base.metrics(d,truth) for n,d in decisions.items()};trials={n:dict(metrics=s,guard_failures=prior.failures(s,scores['current_policy'])) for n,s in scores.items()}
    sam=scores['sam_rho005'];ce=scores['ce_control']
    if sam['macro_f1']+1e-12<ce['macro_f1']:trials['sam_rho005']['guard_failures'].append('macro_f1_below_ce')
    for n in ['current_policy','ce_control']:
        if pair_f1(sam)<=pair_f1(scores[n])+1e-12:trials['sam_rho005']['guard_failures'].append('no_pair_mean_f1_gain_vs_'+n)
    passing=[n for n,v in trials.items() if not v['guard_failures']]
    selected=max(passing,key=lambda n:(scores[n]['macro_f1'],np.mean([scores[n]['per_class'][c]['recall'] for c in ['Lupus','Psoriasis','Tinea']]),scores[n]['accuracy'],n=='current_policy',n=='ce_control'))
    return dict(selected=selected,trials=trials)


def status(state,**items):base.write(OUT/'status.json',dict(state=state,pid=os.getpid(),updated_utc=previous.utc(),**items))


def lock_process():
    global HANDLE
    import msvcrt
    OUT.mkdir(parents=True,exist_ok=True);h=(OUT/'runner.lock').open('a+b')
    if h.tell()==0:h.write(b'0');h.flush()
    h.seek(0)
    try:msvcrt.locking(h.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:h.close();raise RuntimeError('SAM pilot already running')
    HANDLE=h


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');prior.verify(p);return p
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    reg=base.read(ROOT/'ai-service/reports/active_research_track.json');assert reg['next_experiment'] is None
    old=base.read(previous.OUT/'protocol.json');prior.verify(old);assert base.read(previous.OUT/'completion.json')['status']=='complete_verified_pilot_not_selected'
    initial=previous.load_initial(old);assert engine.state_sha(initial.state_dict())==old['initial_state_sha256']
    roles=old['roles'];train=roles['train'];truth=np.array([base.CLASSES.index(r['label']) for r in train]);audit={};files=[]
    for arch in ['efficientnet_b0','convnext_tiny','resnet50']:
        path=prior.OUT/'B_specialist/fold_0/train_features.npz' if arch=='resnet50' else ROOT/f'ai-service/reports/teacher_multifeature_specialist_fold0_seed42_20261024/train_{arch}_features.npz'
        with np.load(path,allow_pickle=False) as z:
            lookup={p:i for i,p in enumerate(z['paths'].tolist())};pp=z['probabilities'][[lookup[r['path']] for r in train]]
        pred=pp.argmax(1);audit[arch]=dict(train_correct=int((pred==truth).sum()),train_images=len(train),classes={c:dict(images=int((truth==base.CLASSES.index(c)).sum()),correct=int(((truth==base.CLASSES.index(c))&(pred==truth)).sum())) for c in ['Eczema','Tinea']});files.append(path)
    files += [Path(__file__),Path(previous.__file__),ROOT/'ai-service/tests/test_teacher_sam_cnn.py',previous.OUT/'protocol.json',previous.OUT/'completion.json',previous.OUT/'independent_review.json',
        ROOT/'ai-service/reports/teacher_soft_pool_selection_audit_20261025/protocol.json',ROOT/'ai-service/reports/teacher_soft_pool_selection_audit_20261025/completion.json']
    files += [previous.MODELS/'ce_control/history.json']
    p=dict(name=OUT.name,registered_utc=previous.utc(),fold=0,classes=base.CLASSES,parent_protocol=old['parent_protocol'],roles=roles,
        initial_checkpoint=old['initial_checkpoint'],initial_state_sha256=old['initial_state_sha256'],trainable_names=old['trainable_names'],frozen_state_sha256=old['frozen_state_sha256'],configuration=CONFIG,
        frozen_sha256={**old['frozen_sha256'],**{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},train_fit_audit=audit,
        hypothesis='Frozen heads/decision gates had small unstable gains. Change actual CNN optimization to seek locally flatter loss, not another routing threshold. Training-fit audit is descriptive, not proof of memorization or causal diagnosis error.',
        intervention='AdamW weightedCE control versus SAM-AdamW with fixed globalL2rho.05 over layer4+fc trainableparams. First CE gradient un-clipped determines epsilon=rho*g/(||g||2+1e-12); second CE on same actual augmentedimages at perturbedweights. Copy originalFP32weights back exactly before clipping secondgradient at2 and one AdamWupdate. No adaptiveSAM, rho search, extra loss or newbackbone.',
        matched='Both same initialResNet,4043photos once/epoch,6epochs,253updates/epoch,batch16,lastshorter, same seeds/order/actual V2augmentation/CEweak3weights1.5others1,LRlayer4=1e-5/fc5e-5,wd.0002,cosine6eta1e-6. Earlierweights and allBNstats frozen. BF16forward/FP32loss/params/optimizer,noGradScaler/EMA. SAM has two forwards/backwards perbatch versus one inCE; same data and updates, not compute-matched.',
        routing='CNNs still train8originallabels; inference changes only currentTinea/Eczema to eight-wayCNNtop1 inthatpair at full8waymax>=.8. Outsidepair calls and their perclassP/R/F1 fixed, including SkinCancer. No renormalized pair or soft-pool gates.',
        checkpoint_selection='After each epoch evalFP32 on718inner; rank passing strictcurrentguards,MacroF1,pairmeanF1,Accuracy,earliesttie. Train all6epochs botharms. Final current/CE/SAM strictguards;SAM alsoMF>=CE and pairmeanF1 strictlyabove current andCE. Rank MF,meanweakRecall,Accuracy,tiescurrentthenCE. Lock bothcheckpoints and selection before outer/source inference.',
        logging='Everyepoch innerprobabilities,raw/routedmetrics,augmentation/order/labelSHA,model/frozenSHA,optimizersteps; firstbatch base/perturbedCElogits,gradnorm,actualepsilonL2,restoreexactflag and secondgradientstats. Bestcheckpoint and resumable finaloptimizer/scheduler states. Compare actualCE exposure/order/augmentation to completed matchedCE run, but do not assume independently retrained SAM.',
        scope='Onefold4043train/718inner/1176outer/1709historicalsource. No new5937score or APIchange. A promising inner choice requires separately registered confirmation.',
        limitations=['Samehistorically inspected cohort/oneCNNseed, parent checkpoint originally selected byinner; not fresh patienttest or fully nestedCNNtraining.',
            'Continuation layer4+fc with fixedBN may not repair feature gaps established by earlierlayers. SAM success on otherbenchmarks is not a guarantee here.',
            'Local SAM implementation uses AdamW,BF16 and fixedBN, not direct reproduction of authors JAX/SGDbenchmarks. More gradientcompute is intrinsic to intervention.',
            'No automatic diagnostic label correction, image removal, backbone addition, Word edits or serving replacement. FP32snapshotrestore avoids rounding drift from subtracting epsilon.'],
        references=['https://arxiv.org/abs/2010.01412','https://github.com/google-research/sam'],runtime=dict(torch=torch.__version__,gpu=torch.cuda.get_device_name(0)),
        new_CNN_continuations=2,new_backbones=0,global_5937_score_changed=False,serving_changed=False)
    base.write(OUT/'protocol.json',p);base.write(OUT/'train_fit_audit.json',audit);base.write(OUT/'research_registry_before.json',reg)
    reg['next_experiment']=OUT.relative_to(ROOT).as_posix();reg['next_experiment_status']='registered_matched_CE_SAM_CNN_pair'
    base.write(ROOT/'ai-service/reports/active_research_track.json',reg);status('registered',epochs_each=6);return p


def train_arm(name,p):
    folder=MODELS/name;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'training_report.json').exists():
        report=base.read(folder/'training_report.json');assert report['protocol_sha256']==base.sha(OUT/'protocol.json') and report['checkpoint_sha256']==base.sha(folder/'best_model.pth');return
    seed_everything(42);model=previous.load_initial(p);assert engine.state_sha(model.state_dict())==p['initial_state_sha256'];model.cuda()
    optimizer=torch.optim.AdamW([dict(params=list(model.layer4.parameters()),lr=CONFIG['layer4_lr']),dict(params=list(model.fc.parameters()),lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=6,eta_min=1e-6);alpha=torch.tensor([1.,1.,1.,1.5,1.5,1.,1.5,1.],device='cuda')
    rows=p['roles']['train'];inner=p['roles']['inner_validation'];truth,current=previous.inner_context(p);baseline=base.metrics(current,truth)
    dataset=ImageSampleDataset(engine.objects(rows),engine.trainer.training_transform_v2());history=[];best=None;start=1;resume=folder/'resume_state.pth'
    if resume.exists():
        saved=torch.load(resume,map_location='cpu',weights_only=False);assert saved['protocol_sha256']==base.sha(OUT/'protocol.json')
        model.load_state_dict(saved['model']);optimizer.load_state_dict(saved['optimizer']);scheduler.load_state_dict(saved['scheduler']);history=saved['history'];best=saved['best'];start=saved['epoch']+1;del saved
    for epoch in range(start,7):
        tick=time.monotonic();seed_everything(42+epoch);assert engine.configure(model,'layer4_finetune')==p['trainable_names']
        indices=torch.randperm(len(rows),generator=torch.Generator().manual_seed(42+epoch)).tolist();loader=engine.trainer.make_loader(engine.SeededDataset(dataset,indices,epoch),16,False,0,True)
        params=[v for v in model.parameters() if v.requires_grad];augmentation=hashlib.sha256();labels_hash=hashlib.sha256();updates=0;total_loss=0.;second_loss=0.;probe=None
        status('training',arm=name,epoch=epoch,epochs_each=6)
        for batch,(images,targets) in enumerate(loader):
            augmentation.update(images.numpy().tobytes());labels_hash.update(targets.numpy().tobytes());images=images.cuda();targets=targets.cuda();optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16):logits=model(images)
            loss=F.cross_entropy(logits.float(),targets,weight=alpha)
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite first CE loss')
            loss.backward();details=dict(first_loss=float(loss.detach()))
            if batch==0:probe=dict(logits=logits.detach().float().cpu().numpy(),targets=targets.cpu().numpy(),loss=float(loss.detach()))
            if name=='sam_rho005':
                saved,gradnorm=perturb(params,CONFIG['rho'])
                if batch==0:
                    delta=torch.sqrt(sum((v.detach()-s).square().sum() for v,s in zip(params,saved)));details.update(first_grad_norm=gradnorm,perturb_l2=float(delta))
                optimizer.zero_grad(set_to_none=True)
                try:
                    with torch.autocast('cuda',dtype=torch.bfloat16):perturbed_logits=model(images)
                    robust_loss=F.cross_entropy(perturbed_logits.float(),targets,weight=alpha)
                    if not torch.isfinite(robust_loss):raise FloatingPointError('Nonfinite perturbed CE loss')
                    robust_loss.backward()
                    if batch==0:probe['perturbed_logits']=perturbed_logits.detach().float().cpu().numpy();details['perturbed_loss']=float(robust_loss.detach())
                    second_loss+=float(robust_loss.detach())
                finally:restore(params,saved)
                if batch==0:details['restore_exact']=all(torch.equal(v.detach(),s) for v,s in zip(params,saved))
                del saved
            gradclip=torch.nn.utils.clip_grad_norm_(params,2,error_if_nonfinite=True);optimizer.step();updates+=1;total_loss+=float(loss.detach())
            if batch==0:
                details['optimizer_grad_norm_before_clip']=float(gradclip);probe.update({k:np.array(v) for k,v in details.items()})
            if (batch+1)%64==0:status('training',arm=name,epoch=epoch,batches=batch+1,total_batches=len(loader),seconds=time.monotonic()-tick)
        assert updates==253 and engine.frozen_hash(model)==p['frozen_state_sha256'];state_hash=engine.state_sha(model.state_dict())
        pp=engine.infer(model,inner);score=base.metrics(pair_route(current,pp),truth);raw=base.metrics(pp.argmax(1),truth);key=objective(score,baseline);improved=best is None or tuple(key)>tuple(best['objective'])
        if improved:
            best=dict(epoch=epoch,objective=key,routed_validation=score,raw_validation=raw,state_sha256=state_hash)
            engine.utility.atomic_save(dict(model_state_dict=model.state_dict(),architecture='resnet50',classes=base.CLASSES,arm=name,epoch=epoch,protocol_sha256=base.sha(OUT/'protocol.json'),research_only=True),folder/'best_model.pth')
        np.savez_compressed(folder/f'epoch_{epoch:02d}_inner.npz',paths=[r['path'] for r in inner],probabilities=pp,model_state_sha256=state_hash)
        np.savez_compressed(folder/f'epoch_{epoch:02d}_loss_probe.npz',**probe);scheduler.step()
        row=dict(epoch=epoch,loss=total_loss/updates,perturbed_loss=second_loss/updates if name=='sam_rho005' else None,actual_updates=updates,images=len(indices),unique_images=len(set(indices)),
            order_sha256=hashlib.sha256(base.json.dumps(indices).encode()).hexdigest(),augmentation_sha256=augmentation.hexdigest(),labels_sha256=labels_hash.hexdigest(),
            frozen_state_sha256=engine.frozen_hash(model),model_state_sha256=state_hash,routed_validation=score,raw_validation=raw,new_best=improved,best_epoch=best['epoch'],seconds=time.monotonic()-tick)
        history.append(row);base.write(folder/'history.json',history)
        engine.utility.atomic_save(dict(protocol_sha256=base.sha(OUT/'protocol.json'),epoch=epoch,model=model.state_dict(),optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),history=history,best=best),resume)
        print(dict(arm=name,epoch=epoch,accuracy=score['accuracy'],macro_f1=score['macro_f1'],best_epoch=best['epoch'],seconds=row['seconds']),flush=True)
    base.write(folder/'training_report.json',dict(protocol_sha256=base.sha(OUT/'protocol.json'),arm=name,checkpoint_sha256=base.sha(folder/'best_model.pth'),best=best,epochs=6,actual_updates=1518,
        initial_state_sha256=p['initial_state_sha256'],frozen_state_sha256=engine.frozen_hash(model),final_state_sha256=history[-1]['model_state_sha256'],forward_backward_passes=3036 if name=='sam_rho005' else 1518,all_batchnorm_fixed=True))
    del model,optimizer;torch.cuda.empty_cache()


def select_and_lock(p):
    truth,current=previous.inner_context(p);dd=dict(current_policy=current);raw={};files=[];histories={name:base.read(MODELS/name/'history.json') for name in ARMS};oldce=base.read(previous.MODELS/'ce_control/history.json')
    ce_hash_matches=[]
    for e in range(6):
        for k in ['augmentation_sha256','labels_sha256','order_sha256','images','unique_images','actual_updates']:
            assert histories['ce_control'][e][k]==histories['sam_rho005'][e][k]==oldce[e][k],(e,k)
        ce_hash_matches.append(histories['ce_control'][e]['model_state_sha256']==oldce[e]['model_state_sha256'])
    for name in ARMS:
        folder=MODELS/name;report=base.read(folder/'training_report.json');epoch=report['best']['epoch']
        with np.load(folder/f'epoch_{epoch:02d}_inner.npz',allow_pickle=False) as z:assert z['paths'].tolist()==[r['path'] for r in p['roles']['inner_validation']];pp=z['probabilities'].copy()
        dd[name]=pair_route(current,pp);raw[name]=base.metrics(pp.argmax(1),truth)
        files+=list(folder.glob('*.npz'))+[folder/'best_model.pth',folder/'training_report.json',folder/'history.json',folder/'resume_state.pth']
    lock=choose(dd,truth);np.savez_compressed(OUT/'inner_decisions.npz',paths=[r['path'] for r in p['roles']['inner_validation']],truth=truth,**dd)
    lock.update(locked_utc=previous.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),raw_validation=raw,prior_CE_epoch_state_matches=ce_hash_matches,artifacts_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in files+[OUT/'inner_decisions.npz']})
    base.write(OUT/'selection_locked.json',lock);print(dict(selected=lock['selected'],failures={n:v['guard_failures'] for n,v in lock['trials'].items()}),flush=True)


def evaluate(p):
    assert not (OUT/'results.json').exists(),'Preserve completed pilot'
    lock=base.read(OUT/'selection_locked.json');assert lock['protocol_sha256']==base.sha(OUT/'protocol.json')
    for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
    source=base.read(latest.OUT/'transfer_check/protocol.json');started=previous.utc();probs={}
    for name in ARMS:
        model=previous.load_initial(p);saved=torch.load(MODELS/name/'best_model.pth',map_location='cpu',weights_only=False);model.load_state_dict(saved['model_state_dict']);assert engine.frozen_hash(model)==p['frozen_state_sha256'];model.cuda();probs[name]={}
        for role,rows in [('outer_holdout',p['roles']['outer_holdout']),('source_transfer',source['rows'])]:
            status('evaluating',arm=name,role=role);pp=engine.infer(model,rows);probs[name][role]=pp;np.savez_compressed(OUT/f'{role}_{name}_probabilities.npz',paths=[r['path'] for r in rows],probabilities=pp)
        del model,saved;torch.cuda.empty_cache()
    old={r['path']:r for r in base.read(latest.OUT/'oof_decisions.json')};external={r['path']:r for r in base.read(latest.OUT/'transfer_check/source_decisions.json')};scores={};output=[]
    for role,rows in [('outer_holdout',p['roles']['outer_holdout']),('source_transfer',source['rows'])]:
        truth=np.array([base.CLASSES.index(r['label']) for r in rows]);current=np.array([old[r['path']]['predictions']['validation_selected'] if role=='outer_holdout' else external[r['path']]['predictions']['validation_selected'][0] for r in rows])
        dd=dict(current_policy=current);dd.update({n:pair_route(current,probs[n][role]) for n in ARMS});dd['validation_selected']=dd[lock['selected']]
        idx={r['path']:i for i,r in enumerate(rows)};slices={'original_outer':list(idx)} if role=='outer_holdout' else source['subsets']
        for subset,paths in slices.items():
            ids=[idx[path] for path in paths];scores[subset]=dict(images=len(ids),methods={n:base.metrics(d[ids],truth[ids]) for n,d in dd.items()},raw_CNN={n:base.metrics(probs[n][role][ids].argmax(1),truth[ids]) for n in ARMS})
        output.extend(dict(**r,role=role,predictions={n:int(d[i]) for n,d in dd.items()}) for i,r in enumerate(rows))
    base.write(OUT/'held_decisions.json',output)
    result=dict(status='complete_exploratory_SAM_CNN_pair',fold=0,selected=lock['selected'],validation=lock['trials'],raw_validation=lock['raw_validation'],held=scores,protocol_sha256=base.sha(OUT/'protocol.json'),selection_sha256=base.sha(OUT/'selection_locked.json'),held_started_utc=started,completed_utc=previous.utc(),
        new_CNN_continuations=2,epochs_each=6,optimizer_updates=3036,gradient_passes=4554,new_backbones=0,global_5937_score_changed=False,serving_changed=False,limitations=p['limitations'])
    base.write(OUT/'results.json',result);prior.verify(p);base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),matched_exposure=True,frozen_parameters_and_BN_unchanged=True))
    status('evaluation_complete_awaiting_independent_review',selected=lock['selected']);print(dict(selected=lock['selected'],outer={n:{k:s[k] for k in ['accuracy','macro_f1']} for n,s in scores['original_outer']['methods'].items()}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args();torch.set_num_threads(4);lock_process();p=prepare()
    if args.prepare_only:return
    assert not (OUT/'results.json').exists(),'Preserve completed pilot'
    if not (OUT/'selection_locked.json').exists():
        for name in ARMS:train_arm(name,p)
        select_and_lock(p)
    evaluate(p)


if __name__=='__main__':main()
