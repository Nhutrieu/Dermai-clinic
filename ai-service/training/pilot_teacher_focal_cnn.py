"""Matched CE versus focal-loss layer4+fc CNN continuation, fold0 only."""
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

from common import ImageSampleDataset,seed_everything
import pilot_teacher_partial_resnet as engine
import pilot_teacher_spatial_multicrop as previous

ROOT,base,prior,latest=previous.ROOT,previous.base,previous.prior,previous.latest
OUT=ROOT/'ai-service/reports/teacher_focal_cnn_fold0_seed42_20261024'
MODELS=ROOT/'ai-service/candidates'/OUT.name
ARMS=['ce_control','focal_gamma2']
CONFIG={**engine.CONFIG,'gamma':2.,'torch_threads':4}
HANDLE=None


def focal_loss(logits,labels,weights,gamma):
    if not math.isfinite(gamma) or gamma<0:raise ValueError('Finite nonnegative gamma required')
    logp=F.log_softmax(logits.float(),dim=1).gather(1,labels[:,None]).squeeze(1)
    alpha=weights[labels]
    modulator=(-torch.expm1(logp)).pow(gamma)
    return (-alpha*modulator*logp).sum()/alpha.sum()


def utc():return previous.features.utc()


def status(state,**items):
    base.write(OUT/'status.json',dict(state=state,pid=os.getpid(),updated_utc=utc(),**items))


def lock_process():
    global HANDLE
    import msvcrt
    OUT.mkdir(parents=True,exist_ok=True);h=(OUT/'runner.lock').open('a+b')
    if h.tell()==0:h.write(b'0');h.flush()
    h.seek(0)
    try:msvcrt.locking(h.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:h.close();raise RuntimeError('Focal CNN pilot already running')
    HANDLE=h


def load_initial(p):
    saved=torch.load(ROOT/p['initial_checkpoint'],map_location='cpu',weights_only=False)
    model=engine.build_model('resnet50',8,False);model.load_state_dict(saved['model_state_dict'])
    engine.configure(model,'layer4_finetune');return model


def inner_context(p):
    with np.load(latest.OUT/'fold_0/inner_decisions.npz',allow_pickle=False) as z:
        assert z['paths'].tolist()==[r['path'] for r in p['roles']['inner_validation']]
        choice=base.read(latest.OUT/'fold_0/selection_locked.json')['selected']
        return z['truth'].copy(),z[choice].copy()


def objective(score,current):
    return [int(not prior.failures(score,current)),score['macro_f1'],engine.mean_focus(score),score['accuracy']]


def choose(decisions,truth):
    scores={n:base.metrics(d,truth) for n,d in decisions.items()}
    trials={n:dict(metrics=s,guard_failures=prior.failures(s,scores['current_policy'])) for n,s in scores.items()}
    focal=scores['focal_gamma2']
    if focal['macro_f1']+1e-12<scores['ce_control']['macro_f1']:
        trials['focal_gamma2']['guard_failures'].append('macro_f1_below_ce_control')
    for name in ['current_policy','ce_control']:
        if engine.mean_focus(focal)<=engine.mean_focus(scores[name])+1e-12:
            trials['focal_gamma2']['guard_failures'].append('no_weak_mean_f1_gain_vs_'+name)
    passing=[n for n,t in trials.items() if not t['guard_failures']]
    selected=max(passing,key=lambda n:(scores[n]['macro_f1'],latest.previous.mean_focus(scores[n],'recall'),
        scores[n]['accuracy'],n=='current_policy',n=='ce_control'))
    return dict(selected=selected,trials=trials)


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');prior.verify(p);return p
    reg=base.read(ROOT/'ai-service/reports/active_research_track.json');assert reg['next_experiment'] is None
    old=base.read(previous.OUT/'protocol.json');prior.verify(old)
    assert base.read(previous.OUT/'completion.json')['status']=='complete_verified_pilot_not_selected'
    original=base.read(ROOT/old['parent_protocol']);roles={r:prior.role_rows(original,0,r) for r in ['train','inner_validation','outer_holdout']}
    checkpoint=prior.checkpoint(0);saved=torch.load(checkpoint,map_location='cpu',weights_only=False)
    assert saved['architecture']=='resnet50' and saved['classes']==base.CLASSES
    model=engine.build_model('resnet50',8,False);model.load_state_dict(saved['model_state_dict'])
    initial=engine.state_sha(model.state_dict());names=engine.configure(model,'layer4_finetune');frozen=engine.frozen_hash(model)
    files=[Path(__file__),ROOT/'ai-service/tests/test_teacher_focal_cnn.py',checkpoint,
        previous.OUT/'protocol.json',previous.OUT/'completion.json',previous.OUT/'independent_review.json',
        engine.OUT/'protocol.json',engine.OUT/'verification.json',
        ROOT/'ai-service/training/pilot_teacher_partial_resnet.py',ROOT/'ai-service/training/pilot_teacher_spatial_multicrop.py',
        ROOT/'ai-service/training/pilot_original_eight_imagenet_mixup.py',ROOT/'ai-service/training/train_v2.py',ROOT/'ai-service/training/common.py']
    p=dict(name=OUT.name,registered_utc=utc(),fold=0,classes=base.CLASSES,roles=roles,
        parent_protocol=old['parent_protocol'],initial_checkpoint=checkpoint.relative_to(ROOT).as_posix(),
        initial_state_sha256=initial,trainable_names=names,frozen_state_sha256=frozen,configuration=CONFIG,
        frozen_sha256={**old['frozen_sha256'],**{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},
        intervention='Only loss changes in an actual CNN continuation: weightedCE versus softmax multiclass focal gamma2. Both train original ResNet layer4+fc, all earlier parameters and all BatchNorm running statistics fixed.',
        loss='For target probability pt from8way softmax, focal = sum(alpha_y*(1-pt)^2*(-logpt))/sum(alpha_y). Same alpha weak3=1.5/others1 in both arms; no additional balance. CE is torch weighted cross_entropy. Gamma0 equals weightedCE; fixed gamma2 before running, no search.',
        training='Two independent starts from same original checkpoint. Six fixed epochs each,4043original train photos once/epoch; batch16,last shorter,253updates/epoch. Same position-seeded V2augmentation/order/labels,AdamW layer4lr1e-5/fclr5e-5,weight_decay.0002,cosine6eta_min1e-6,gradient_clip2. BF16forward/FP32loss+params+optimizer,noGradScaler,noEMA,nooversampling,noextraimages. Keep exact class labels.',
        selection='After each epoch infer718inner in evalFP32/batch16. Rank best checkpoint by passing current strictguards,MacroF1,meanweakF1,Accuracy; earliest exact tie. Train all6epochs. Final current/CE/focal comparison strict existing perweakRecall/F1,totalAccuracy/MacroF1,weakPrecision/otherRecall,Cancerexact. Focal additionally MF>=CE and meanweakF1 strictly above current andCE; rank MF,meanweakRecall,Accuracy,ties current thenCE. Lock both chosen checkpoints and choice before any outer/source inference.',
        routing='Collapse8way probabilities to Lupus/Psoriasis/Tinea/Eczema/Other(sum remaining4); fixed>=.8 route changes only currentweak4 calls; Other abstains. Preserve exact existingCancer mask.',
        logging='Save each epoch inner probabilities,first-minibatch FP32logits/targets/lossprobe,augmentation/order/labelSHA,model/frozenSHA,updates/loss/bestselection. Save bestfull checkpoint and resumable final model/optimizer/scheduler. Technicalaudit does not imply independent CNN retraining.',
        scope='Onefold pilot4043train/718inner/1176outer;1709known-source descriptive slices. No new5937global score unless a separately registered fullCV confirmation succeeds.',
        limitations=old['limitations']+[
            'This updates layer4+fc CNN parameters; the crop-view and pairwise interventions are not used in this experiment.',
            'The modulator changes total gradient magnitude as well as hard-example emphasis. Same learning rates do not isolate these effects.',
            'Hard examples can include label errors. Focal weighting is not label verification or correction; no medical relabeling is performed.',
            'Lin2017 studies dense object detection/RetinaNet; this is a custom softmax8class adaptation with existing classweights, not a RetinaNet reproduction.',
            'One seed/fold and historically inspected cohorts; frozen parents used inner for initial checkpoint choice. No fresh independent patient test.'],
        references=['https://arxiv.org/abs/1708.02002','https://arxiv.org/pdf/1708.02002'],
        runtime=dict(torch=torch.__version__,gpu=torch.cuda.get_device_name(0)),
        new_CNN_continuations=2,new_backbones=0,global_5937_score_changed=False,serving_changed=False)
    base.write(OUT/'protocol.json',p);base.write(OUT/'research_registry_before.json',reg)
    reg['next_experiment']=OUT.relative_to(ROOT).as_posix();reg['next_experiment_status']='registered_matched_ce_focal_cnn_fold0'
    base.write(ROOT/'ai-service/reports/active_research_track.json',reg);status('registered',epochs_each=6)
    return p


def train_arm(name,p):
    folder=MODELS/name;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'training_report.json').exists():
        report=base.read(folder/'training_report.json')
        assert report['protocol_sha256']==base.sha(OUT/'protocol.json') and report['checkpoint_sha256']==base.sha(folder/'best_model.pth')
        return
    seed_everything(42);model=load_initial(p);assert engine.state_sha(model.state_dict())==p['initial_state_sha256']
    assert engine.frozen_hash(model)==p['frozen_state_sha256'];model.cuda()
    optimizer=torch.optim.AdamW([dict(params=list(model.layer4.parameters()),lr=CONFIG['layer4_lr']),dict(params=list(model.fc.parameters()),lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=6,eta_min=1e-6)
    alpha=torch.tensor([1.,1.,1.,1.5,1.5,1.,1.5,1.],device='cuda')
    rows=p['roles']['train'];inner=p['roles']['inner_validation'];truth,current=inner_context(p);baseline=base.metrics(current,truth)
    dataset=ImageSampleDataset(engine.objects(rows),engine.trainer.training_transform_v2())
    history=[];best=None;start=1;resume=folder/'resume_state.pth'
    if resume.exists():
        saved=torch.load(resume,map_location='cpu',weights_only=False);assert saved['protocol_sha256']==base.sha(OUT/'protocol.json')
        model.load_state_dict(saved['model']);optimizer.load_state_dict(saved['optimizer']);scheduler.load_state_dict(saved['scheduler'])
        history=saved['history'];best=saved['best'];start=saved['epoch']+1;del saved
    for epoch in range(start,7):
        tick=time.monotonic();seed_everything(42+epoch)
        assert engine.configure(model,'layer4_finetune')==p['trainable_names']
        indices=torch.randperm(len(rows),generator=torch.Generator().manual_seed(42+epoch)).tolist()
        loader=engine.trainer.make_loader(engine.SeededDataset(dataset,indices,epoch),16,False,0,True)
        augmentation=hashlib.sha256();labels_hash=hashlib.sha256();updates=0;total_loss=0.;probe=None
        status('training',arm=name,epoch=epoch,epochs_each=6)
        for batch,(images,targets) in enumerate(loader):
            augmentation.update(images.numpy().tobytes());labels_hash.update(targets.numpy().tobytes())
            images=images.cuda();targets=targets.cuda();optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16):logits=model(images)
            loss=F.cross_entropy(logits.float(),targets,weight=alpha) if name=='ce_control' else focal_loss(logits,targets,alpha,CONFIG['gamma'])
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite CNN training loss')
            if batch==0:probe=dict(logits=logits.detach().float().cpu().numpy(),targets=targets.cpu().numpy(),loss=float(loss.detach()))
            loss.backward();torch.nn.utils.clip_grad_norm_([v for v in model.parameters() if v.requires_grad],2,error_if_nonfinite=True)
            optimizer.step();updates+=1;total_loss+=float(loss.detach())
            if (batch+1)%64==0:status('training',arm=name,epoch=epoch,batches=batch+1,total_batches=len(loader),seconds=time.monotonic()-tick)
        assert updates==253 and engine.frozen_hash(model)==p['frozen_state_sha256']
        state_hash=engine.state_sha(model.state_dict());assert state_hash!=p['initial_state_sha256']
        pp=engine.infer(model,inner);decision=engine.decision(current,pp);score=base.metrics(decision,truth)
        raw=base.metrics(pp.argmax(1),truth);key=objective(score,baseline)
        improved=best is None or tuple(key)>tuple(best['objective'])
        if improved:
            best=dict(epoch=epoch,objective=key,routed_validation=score,raw_validation=raw,state_sha256=state_hash)
            engine.utility.atomic_save(dict(model_state_dict=model.state_dict(),architecture='resnet50',classes=base.CLASSES,arm=name,
                epoch=epoch,protocol_sha256=base.sha(OUT/'protocol.json'),research_only=True),folder/'best_model.pth')
        np.savez_compressed(folder/f'epoch_{epoch:02d}_inner.npz',paths=[r['path'] for r in inner],probabilities=pp,model_state_sha256=state_hash)
        np.savez_compressed(folder/f'epoch_{epoch:02d}_loss_probe.npz',**probe)
        scheduler.step()
        row=dict(epoch=epoch,loss=total_loss/updates,actual_updates=updates,images=len(indices),unique_images=len(set(indices)),
            order_sha256=hashlib.sha256(base.json.dumps(indices).encode()).hexdigest(),augmentation_sha256=augmentation.hexdigest(),labels_sha256=labels_hash.hexdigest(),
            frozen_state_sha256=engine.frozen_hash(model),model_state_sha256=state_hash,routed_validation=score,raw_validation=raw,
            new_best=improved,best_epoch=best['epoch'],seconds=time.monotonic()-tick)
        history.append(row);base.write(folder/'history.json',history)
        engine.utility.atomic_save(dict(protocol_sha256=base.sha(OUT/'protocol.json'),epoch=epoch,model=model.state_dict(),optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),history=history,best=best),resume)
        print(dict(arm=name,epoch=epoch,accuracy=score['accuracy'],macro_f1=score['macro_f1'],best_epoch=best['epoch'],seconds=row['seconds']),flush=True)
    base.write(folder/'training_report.json',dict(protocol_sha256=base.sha(OUT/'protocol.json'),arm=name,
        checkpoint_sha256=base.sha(folder/'best_model.pth'),initial_state_sha256=p['initial_state_sha256'],epochs=6,actual_updates=1518,skipped_updates=0,
        best=best,frozen_state_sha256=engine.frozen_hash(model),all_batchnorm_fixed=True,final_state_sha256=history[-1]['model_state_sha256']))
    del model,optimizer;torch.cuda.empty_cache()


def select_and_lock(p):
    truth,current=inner_context(p);dd=dict(current_policy=current);raw={};files=[]
    histories={name:base.read(MODELS/name/'history.json') for name in ARMS}
    for e in range(6):
        for k in ['augmentation_sha256','labels_sha256','order_sha256','images','unique_images','actual_updates']:
            assert histories['ce_control'][e][k]==histories['focal_gamma2'][e][k],(e,k)
    for name in ARMS:
        folder=MODELS/name;report=base.read(folder/'training_report.json');epoch=report['best']['epoch']
        with np.load(folder/f'epoch_{epoch:02d}_inner.npz',allow_pickle=False) as z:
            assert z['paths'].tolist()==[r['path'] for r in p['roles']['inner_validation']];pp=z['probabilities'].copy()
        dd[name]=engine.decision(current,pp);raw[name]=base.metrics(pp.argmax(1),truth)
        files+=list(folder.glob('*.npz'))+[folder/'best_model.pth',folder/'training_report.json',folder/'history.json',folder/'resume_state.pth']
    lock=choose(dd,truth)
    np.savez_compressed(OUT/'inner_decisions.npz',paths=[r['path'] for r in p['roles']['inner_validation']],truth=truth,**dd)
    lock.update(locked_utc=utc(),protocol_sha256=base.sha(OUT/'protocol.json'),raw_validation=raw,
        artifacts_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in files+[OUT/'inner_decisions.npz']})
    base.write(OUT/'selection_locked.json',lock);print(dict(selected=lock['selected'],failures={n:t['guard_failures'] for n,t in lock['trials'].items()}),flush=True)


def evaluate(p):
    assert not (OUT/'results.json').exists(),'Preserve completed evaluation'
    lock=base.read(OUT/'selection_locked.json');assert lock['protocol_sha256']==base.sha(OUT/'protocol.json')
    for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
    source=base.read(latest.OUT/'transfer_check/protocol.json');started=utc();probs={}
    for name in ARMS:
        model=load_initial(p);saved=torch.load(MODELS/name/'best_model.pth',map_location='cpu',weights_only=False)
        model.load_state_dict(saved['model_state_dict']);assert engine.frozen_hash(model)==p['frozen_state_sha256'];model.cuda()
        probs[name]={}
        for role,rows in [('outer_holdout',p['roles']['outer_holdout']),('source_transfer',source['rows'])]:
            status('evaluating',arm=name,role=role);pp=engine.infer(model,rows);probs[name][role]=pp
            np.savez_compressed(OUT/f'{role}_{name}_probabilities.npz',paths=[r['path'] for r in rows],probabilities=pp)
        del model,saved;torch.cuda.empty_cache()
    old={r['path']:r for r in base.read(latest.OUT/'oof_decisions.json')};external={r['path']:r for r in base.read(latest.OUT/'transfer_check/source_decisions.json')}
    scores={};output=[]
    for role,rows in [('outer_holdout',p['roles']['outer_holdout']),('source_transfer',source['rows'])]:
        truth=np.array([base.CLASSES.index(r['label']) for r in rows]);current=np.array([old[r['path']]['predictions']['validation_selected'] if role=='outer_holdout' else external[r['path']]['predictions']['validation_selected'][0] for r in rows])
        dd=dict(current_policy=current);dd.update({name:engine.decision(current,probs[name][role]) for name in ARMS});dd['validation_selected']=dd[lock['selected']]
        idx={r['path']:i for i,r in enumerate(rows)};slices={'original_outer':list(idx)} if role=='outer_holdout' else source['subsets']
        for subset,paths in slices.items():
            ids=[idx[path] for path in paths]
            scores[subset]=dict(images=len(ids),methods={name:base.metrics(d[ids],truth[ids]) for name,d in dd.items()},
                raw_CNN={name:base.metrics(probs[name][role][ids].argmax(1),truth[ids]) for name in ARMS})
        output.extend(dict(**r,role=role,predictions={name:int(d[i]) for name,d in dd.items()}) for i,r in enumerate(rows))
    base.write(OUT/'held_decisions.json',output)
    result=dict(status='complete_exploratory_focal_cnn_pilot',fold=0,selected=lock['selected'],validation=lock['trials'],raw_validation=lock['raw_validation'],held=scores,
        protocol_sha256=base.sha(OUT/'protocol.json'),selection_sha256=base.sha(OUT/'selection_locked.json'),held_started_utc=started,completed_utc=utc(),
        new_CNN_continuations=2,epochs_each=6,optimizer_updates=3036,new_backbones=0,global_5937_score_changed=False,serving_changed=False,limitations=p['limitations'])
    base.write(OUT/'results.json',result);prior.verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),matched_exposure_and_augmentation=True,
        initial_weights_identical=True,frozen_parameters_and_BN_unchanged=True,actual_updates_each=1518,skipped_updates=0))
    status('evaluation_complete_awaiting_independent_review',selected=lock['selected'])
    print(dict(selected=lock['selected'],outer={name:{k:s[k] for k in ['accuracy','macro_f1']} for name,s in scores['original_outer']['methods'].items()}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    torch.set_num_threads(4);lock_process();p=prepare()
    if args.prepare_only:return
    assert not (OUT/'results.json').exists(),'Preserve completed pilot'
    if not (OUT/'selection_locked.json').exists():
        for name in ARMS:train_arm(name,p)
        select_and_lock(p)
    evaluate(p)


if __name__=='__main__':main()
