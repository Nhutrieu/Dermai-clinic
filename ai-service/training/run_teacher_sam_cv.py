"""Five-fold matched CE/SAM continuation; reuse verified fold0, train folds1..4."""
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
from threadpoolctl import threadpool_limits
import pilot_teacher_sam_cnn as pilot
import evaluate_teacher_stack_transfer as transfer
from common import ImageSampleDataset,seed_everything

ROOT,base,prior,latest,engine=pilot.ROOT,pilot.base,pilot.prior,pilot.latest,pilot.engine
OUT=ROOT/'ai-service/reports/teacher_sam_cv_seed42_20261025'
MODELS=ROOT/'ai-service/candidates'/OUT.name
ARMS=pilot.ARMS;CONFIG=dict(pilot.CONFIG)
METHODS=['current_policy','ce_control','sam_rho005','ce_validation_selected','validation_selected']
HANDLE=None


def status(state,**items):base.write(OUT/'status.json',dict(state=state,pid=os.getpid(),updated_utc=pilot.previous.utc(),**items))


def lock_process():
    global HANDLE
    import msvcrt
    OUT.mkdir(parents=True,exist_ok=True);h=(OUT/'runner.lock').open('a+b')
    if h.tell()==0:h.write(b'0');h.flush()
    h.seek(0)
    try:msvcrt.locking(h.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:h.close();raise RuntimeError('SAM CV runner already running')
    HANDLE=h


def validate_roles(roles):
    for name,rows in roles.items():
        if len(rows)!=len({r['path'] for r in rows}):raise ValueError('Repeated path in '+name)
    for a,b in [('train','inner_validation'),('train','outer_holdout'),('inner_validation','outer_holdout')]:
        for key in ['path','sha256','group']:
            if {r[key] for r in roles[a]} & {r[key] for r in roles[b]}:raise ValueError(f'Role overlap: {a}/{b}/{key}')


def control_choice(trials):
    options=[n for n in ['current_policy','ce_control'] if not trials[n]['guard_failures']]
    return max(options,key=lambda n:(trials[n]['metrics']['macro_f1'],np.mean([trials[n]['metrics']['per_class'][c]['recall'] for c in ['Lupus','Psoriasis','Tinea']]),trials[n]['metrics']['accuracy'],n=='current_policy'))


def model_folder(f,arm):return pilot.MODELS/arm if f==0 else MODELS/f'fold_{f}'/arm


def inner_context(f,spec):
    with np.load(latest.OUT/f'fold_{f}/inner_decisions.npz',allow_pickle=False) as z:
        assert z['paths'].tolist()==[r['path'] for r in spec['roles']['inner_validation']]
        return z['truth'].copy(),z[base.read(latest.OUT/f'fold_{f}/selection_locked.json')['selected']].copy()


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');prior.verify(p);return p
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    reg=base.read(ROOT/'ai-service/reports/active_research_track.json');assert reg['next_experiment'] is None
    old=base.read(pilot.OUT/'protocol.json');prior.verify(old);assert base.read(pilot.OUT/'completion.json')['status']=='complete_verified_pilot_local_selection'
    parent=base.read(ROOT/old['parent_protocol']);folds=[];files=[Path(__file__),Path(pilot.__file__),Path(transfer.__file__),ROOT/'ai-service/tests/test_teacher_sam_cv.py',
        pilot.OUT/'protocol.json',pilot.OUT/'completion.json',pilot.OUT/'independent_review.json',pilot.OUT/'results.json',pilot.OUT/'selection_locked.json',pilot.OUT/'inner_decisions.npz',
        latest.OUT/'oof_decisions.json',latest.OUT/'results.json',latest.OUT/'transfer_check/protocol.json',latest.OUT/'transfer_check/source_decisions.json',ROOT/'ai-service/app/config.py']
    images={}
    for f in range(5):
        roles={role:prior.role_rows(parent,f,role) for role in ['train','inner_validation','outer_holdout']};validate_roles(roles)
        assert sum(map(len,roles.values()))==5937
        checkpoint=prior.checkpoint(f);saved=torch.load(checkpoint,map_location='cpu',weights_only=False);assert saved['classes']==base.CLASSES and saved['architecture']=='resnet50'
        model=engine.build_model('resnet50',8,False);model.load_state_dict(saved['model_state_dict']);initial=engine.state_sha(model.state_dict());names=engine.configure(model,'layer4_finetune');frozen=engine.frozen_hash(model)
        spec=dict(fold=f,roles=roles,initial_checkpoint=checkpoint.relative_to(ROOT).as_posix(),initial_state_sha256=initial,trainable_names=names,frozen_state_sha256=frozen,
            train_images=len(roles['train']),updates_each=math.ceil(len(roles['train'])/CONFIG['batch_size'])*CONFIG['epochs'],reuse_verified_pilot=f==0)
        if f==0:assert all(spec[k]==old[k] for k in ['roles','initial_checkpoint','initial_state_sha256','trainable_names','frozen_state_sha256'])
        folds.append(spec);files += [checkpoint,latest.OUT/f'fold_{f}/inner_decisions.npz',latest.OUT/f'fold_{f}/selection_locked.json']
        for rows in roles.values():images.update({r['path']:r['sha256'] for r in rows})
        del model,saved
    source=base.read(latest.OUT/'transfer_check/protocol.json')
    assert [r['path'] for r in base.read(latest.OUT/'transfer_check/source_decisions.json')]==[r['path'] for r in source['rows']]
    images.update({r['path']:r['sha256'] for r in source['rows']})
    for path,digest in images.items():assert base.sha(ROOT/path)==digest,path
    for name in ARMS:
        files += list(model_folder(0,name).glob('*.npz'))+[model_folder(0,name)/n for n in ['best_model.pth','history.json','training_report.json','resume_state.pth']]
        files += [pilot.OUT/f'{role}_{name}_probabilities.npz' for role in ['outer_holdout','source_transfer']]
    p=dict(name=OUT.name,registered_utc=pilot.previous.utc(),classes=base.CLASSES,images=5937,folds=folds,parent_protocol=old['parent_protocol'],configuration=CONFIG,
        frozen_sha256={**old['frozen_sha256'],**{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},
        expansion='Reuse verified fold0 CE/SAM models, all6epoch evidence and probabilities unchanged. Train two continuations per fold1..4. Same optimizer/rho.05/initialfoldResNet/trainablemask/frozenBN/augmentation/6epochs/routing/guards as pilot. No additionalbackbones or post-pilot tuning.',
        budgets='Full8newCNNcontinuations: fold1/2/3 train4031/4020/4024 ->1512updates perarm; fold4train4060 ->1524perarm. Totalnew12120optimizerupdates,18180forward-backwardminibatchpasses. Reusedfold0twoarms add3036updates/4554passes to5foldtotal. Samephotos perarm,not compute-matched as SAM2passes versus CE1.',
        training=old['matched'],SAM=old['intervention'],routing=old['routing'],checkpoint_selection=old['checkpoint_selection'],
        selection='Perfold use exactly pilot.current/CE/SAM guards and ranking, includingSAMpairmeanF1>current/CE. Also record current-vs-CE-only selected control. Lock all5 bestcheckpoints andchoices before ANYnewouter/source inference. Fold0choice/predictions must match pilot. No selection using aggregateouter,source,bootstrap or favorable raw arm.',
        evaluation='Eachoriginal5937photo gets oneouterprediction. Report current/rawCE/rawSAM/CEvalidationselected/fullvalidationselected separately, perclass/source/fold/transitions and1000pairedscene-casegroup-bootstrap delta intervals seed20261022. Same1709historicalsourcephotos evaluated by5systems; per-fold summaries,not8545independentphotos or a new averagedclassifier.',
        limitations=old['limitations']+['Fold0outer is already known; remaining4folds supply additional exploratory evidence without changing recipe. Allcohort/source data historically investigated.',
            'OneCNNseed with overlappingtrainfolds,not5independentseeds or fresh patientvalidation. OriginalCNNparent and retained upstream policy used inner before; not fully nestedCNNretraining.',
            'No automatic serving/reference-policy replacement even if aggregate OOF improves. Report uncertainty and any class/source decline. Externalconfirmation remains absent.'],
        images_sha256_checked=len(images),new_CNN_continuations=8,reused_CNN_continuations=2,new_backbones=0,serving_changed=False,retained_policy_changed=False)
    base.write(OUT/'protocol.json',p);base.write(OUT/'research_registry_before.json',reg)
    reg['next_experiment']=OUT.relative_to(ROOT).as_posix();reg['next_experiment_status']='registered_matched_SAM_CNN_all5folds'
    base.write(ROOT/'ai-service/reports/active_research_track.json',reg);status('registered',new_CNN_continuations=8);return p


def train_arm(f,name,p):
    spec=p['folds'][f];folder=model_folder(f,name);folder.mkdir(parents=True,exist_ok=True)
    if (folder/'training_report.json').exists():
        report=base.read(folder/'training_report.json');assert report['protocol_sha256']==base.sha(OUT/'protocol.json') and report['checkpoint_sha256']==base.sha(folder/'best_model.pth');return
    seed_everything(42);model=pilot.previous.load_initial(spec);assert engine.state_sha(model.state_dict())==spec['initial_state_sha256'];model.cuda()
    optimizer=torch.optim.AdamW([dict(params=list(model.layer4.parameters()),lr=CONFIG['layer4_lr']),dict(params=list(model.fc.parameters()),lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=6,eta_min=1e-6);alpha=torch.tensor([1.,1.,1.,1.5,1.5,1.,1.5,1.],device='cuda')
    rows=spec['roles']['train'];inner=spec['roles']['inner_validation'];truth,current=inner_context(f,spec);baseline=base.metrics(current,truth)
    dataset=ImageSampleDataset(engine.objects(rows),engine.trainer.training_transform_v2());history=[];best=None;start=1;resume=folder/'resume_state.pth'
    if resume.exists():
        saved=torch.load(resume,map_location='cpu',weights_only=False);assert saved['protocol_sha256']==base.sha(OUT/'protocol.json')
        model.load_state_dict(saved['model']);optimizer.load_state_dict(saved['optimizer']);scheduler.load_state_dict(saved['scheduler']);history=saved['history'];best=saved['best'];start=saved['epoch']+1;del saved
    expected=math.ceil(len(rows)/CONFIG['batch_size'])
    for epoch in range(start,7):
        tick=time.monotonic();seed_everything(42+epoch);assert engine.configure(model,'layer4_finetune')==spec['trainable_names']
        order=torch.randperm(len(rows),generator=torch.Generator().manual_seed(42+epoch)).tolist();loader=engine.trainer.make_loader(engine.SeededDataset(dataset,order,epoch),16,False,0,True);assert len(loader)==expected
        params=[v for v in model.parameters() if v.requires_grad];augmentation=hashlib.sha256();labels=hashlib.sha256();updates=0;total=0.;second_total=0.;probe=None
        status('training',fold=f,arm=name,epoch=epoch,epochs_each=6,total_batches=expected)
        for batch,(x,y) in enumerate(loader):
            augmentation.update(x.numpy().tobytes());labels.update(y.numpy().tobytes());x=x.cuda();y=y.cuda();optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16):logits=model(x)
            loss=F.cross_entropy(logits.float(),y,weight=alpha)
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite first CE')
            loss.backward();details=dict(first_loss=float(loss.detach()))
            if batch==0:probe=dict(logits=logits.detach().float().cpu().numpy(),targets=y.cpu().numpy(),loss=float(loss.detach()))
            if name=='sam_rho005':
                originals,norm=pilot.perturb(params,CONFIG['rho'])
                if batch==0:details.update(first_grad_norm=norm,perturb_l2=float(torch.sqrt(sum((v.detach()-old).square().sum() for v,old in zip(params,originals)))))
                optimizer.zero_grad(set_to_none=True)
                try:
                    with torch.autocast('cuda',dtype=torch.bfloat16):perturbed_logits=model(x)
                    robust=F.cross_entropy(perturbed_logits.float(),y,weight=alpha)
                    if not torch.isfinite(robust):raise FloatingPointError('Nonfinite perturbed CE')
                    robust.backward();second_total+=float(robust.detach())
                    if batch==0:probe['perturbed_logits']=perturbed_logits.detach().float().cpu().numpy();details['perturbed_loss']=float(robust.detach())
                finally:pilot.restore(params,originals)
                if batch==0:details['restore_exact']=all(torch.equal(v.detach(),old) for v,old in zip(params,originals))
                del originals
            norm=torch.nn.utils.clip_grad_norm_(params,2,error_if_nonfinite=True);optimizer.step();updates+=1;total+=float(loss.detach())
            if batch==0:details['optimizer_grad_norm_before_clip']=float(norm);probe.update({k:np.array(v) for k,v in details.items()})
            if (batch+1)%64==0:status('training',fold=f,arm=name,epoch=epoch,batches=batch+1,total_batches=expected,seconds=time.monotonic()-tick)
        assert updates==expected and engine.frozen_hash(model)==spec['frozen_state_sha256'];state=engine.state_sha(model.state_dict())
        pp=engine.infer(model,inner);score=base.metrics(pilot.pair_route(current,pp),truth);raw=base.metrics(pp.argmax(1),truth);key=pilot.objective(score,baseline);improved=best is None or tuple(key)>tuple(best['objective'])
        if improved:
            best=dict(epoch=epoch,objective=key,routed_validation=score,raw_validation=raw,state_sha256=state)
            engine.utility.atomic_save(dict(model_state_dict=model.state_dict(),architecture='resnet50',classes=base.CLASSES,fold=f,arm=name,epoch=epoch,protocol_sha256=base.sha(OUT/'protocol.json'),research_only=True),folder/'best_model.pth')
        np.savez_compressed(folder/f'epoch_{epoch:02d}_inner.npz',paths=[r['path'] for r in inner],probabilities=pp,model_state_sha256=state);np.savez_compressed(folder/f'epoch_{epoch:02d}_loss_probe.npz',**probe);scheduler.step()
        row=dict(epoch=epoch,loss=total/updates,perturbed_loss=second_total/updates if name=='sam_rho005' else None,actual_updates=updates,images=len(rows),unique_images=len(set(order)),order_sha256=hashlib.sha256(base.json.dumps(order).encode()).hexdigest(),
            augmentation_sha256=augmentation.hexdigest(),labels_sha256=labels.hexdigest(),frozen_state_sha256=engine.frozen_hash(model),model_state_sha256=state,routed_validation=score,raw_validation=raw,new_best=improved,best_epoch=best['epoch'],seconds=time.monotonic()-tick)
        history.append(row);base.write(folder/'history.json',history);engine.utility.atomic_save(dict(protocol_sha256=base.sha(OUT/'protocol.json'),epoch=epoch,model=model.state_dict(),optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),history=history,best=best),resume)
        print(dict(fold=f,arm=name,epoch=epoch,accuracy=score['accuracy'],macro_f1=score['macro_f1'],best_epoch=best['epoch'],seconds=row['seconds']),flush=True)
    base.write(folder/'training_report.json',dict(protocol_sha256=base.sha(OUT/'protocol.json'),fold=f,arm=name,checkpoint_sha256=base.sha(folder/'best_model.pth'),best=best,epochs=6,actual_updates=spec['updates_each'],
        initial_state_sha256=spec['initial_state_sha256'],frozen_state_sha256=engine.frozen_hash(model),final_state_sha256=history[-1]['model_state_sha256'],forward_backward_passes=spec['updates_each']*(2 if name=='sam_rho005' else 1),all_batchnorm_fixed=True))
    del model,optimizer;torch.cuda.empty_cache()


def lock_fold(f,p):
    folder=OUT/f'fold_{f}';folder.mkdir(parents=True,exist_ok=True)
    if (folder/'selection_locked.json').exists():
        lock=base.read(folder/'selection_locked.json');assert lock['protocol_sha256']==base.sha(OUT/'protocol.json')
        for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
        return lock
    spec=p['folds'][f];truth,current=inner_context(f,spec);dd=dict(current_policy=current);raw={};files=[];histories={n:base.read(model_folder(f,n)/'history.json') for n in ARMS}
    for e in range(6):
        for k in ['augmentation_sha256','labels_sha256','order_sha256','images','unique_images','actual_updates']:assert histories['ce_control'][e][k]==histories['sam_rho005'][e][k]
    for name in ARMS:
        directory=model_folder(f,name);report=base.read(directory/'training_report.json');epoch=report['best']['epoch']
        with np.load(directory/f'epoch_{epoch:02d}_inner.npz',allow_pickle=False) as z:
            assert z['paths'].tolist()==[r['path'] for r in spec['roles']['inner_validation']];pp=z['probabilities'].copy()
        dd[name]=pilot.pair_route(current,pp);raw[name]=base.metrics(pp.argmax(1),truth)
        files+=list(directory.glob('*.npz'))+[directory/n for n in ['best_model.pth','history.json','training_report.json','resume_state.pth']]
    lock=pilot.choose(dd,truth);lock['control_selected']=control_choice(lock['trials'])
    if f==0:
        old=base.read(pilot.OUT/'selection_locked.json');assert lock['selected']==old['selected']
        with np.load(pilot.OUT/'inner_decisions.npz',allow_pickle=False) as z:
            for n,d in dd.items():assert np.array_equal(d,z[n])
    np.savez_compressed(folder/'inner_decisions.npz',paths=[r['path'] for r in spec['roles']['inner_validation']],truth=truth,**dd)
    lock.update(locked_utc=pilot.previous.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),raw_validation=raw,reused_pilot=f==0,artifacts_sha256={x.relative_to(ROOT).as_posix():base.sha(x) for x in files+[folder/'inner_decisions.npz']})
    base.write(folder/'selection_locked.json',lock);print(dict(fold=f,selected=lock['selected'],control_selected=lock['control_selected'],sam_failures=lock['trials']['sam_rho005']['guard_failures']),flush=True);return lock


def fit_all(p):
    for f in range(5):
        if f:
            for n in ARMS:train_arm(f,n,p)
        lock_fold(f,p)
    base.write(OUT/'all_selections_locked.json',dict(locked_utc=pilot.previous.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
        selections={str(f):base.read(OUT/f'fold_{f}/selection_locked.json')['selected'] for f in range(5)},
        sha256={str(f):base.sha(OUT/f'fold_{f}/selection_locked.json') for f in range(5)}))


def evaluate(p):
    assert not (OUT/'results.json').exists(),'Preserve completed CV'
    locks=base.read(OUT/'all_selections_locked.json');assert locks['protocol_sha256']==base.sha(OUT/'protocol.json')
    for f in range(5):
        lock=base.read(OUT/f'fold_{f}/selection_locked.json');assert locks['sha256'][str(f)]==base.sha(OUT/f'fold_{f}/selection_locked.json')
        for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
    source=base.read(latest.OUT/'transfer_check/protocol.json');started=pilot.previous.utc();original={r['path']:r for r in base.read(latest.OUT/'oof_decisions.json')};source_ref=base.read(latest.OUT/'transfer_check/source_decisions.json');output=[];sp={n:[] for n in METHODS};raw_oof={n:[] for n in ARMS};raw_sp={n:[] for n in ARMS}
    for f,spec in enumerate(p['folds']):
        probability={n:{} for n in ARMS}
        for name in ARMS:
            if f:
                model=pilot.previous.load_initial(spec);saved=torch.load(model_folder(f,name)/'best_model.pth',map_location='cpu',weights_only=False);model.load_state_dict(saved['model_state_dict']);assert engine.frozen_hash(model)==spec['frozen_state_sha256'];model.cuda()
            for role,rows in [('outer_holdout',spec['roles']['outer_holdout']),('source_transfer',source['rows'])]:
                status('evaluating',fold=f,arm=name,role=role)
                if f==0:
                    with np.load(pilot.OUT/f'{role}_{name}_probabilities.npz',allow_pickle=False) as z:assert z['paths'].tolist()==[r['path'] for r in rows];pp=z['probabilities'].copy()
                else:pp=engine.infer(model,rows)
                probability[name][role]=pp;np.savez_compressed(OUT/f'fold_{f}/{role}_{name}_probabilities.npz',paths=[r['path'] for r in rows],probabilities=pp)
            if f:del model,saved;torch.cuda.empty_cache()
        lock=base.read(OUT/f'fold_{f}/selection_locked.json')
        for role,rows in [('outer_holdout',spec['roles']['outer_holdout']),('source_transfer',source['rows'])]:
            current=np.array([original[r['path']]['predictions']['validation_selected'] for r in rows]) if role=='outer_holdout' else np.array([r['predictions']['validation_selected'][f] for r in source_ref])
            dd=dict(current_policy=current);dd.update({n:pilot.pair_route(current,probability[n][role]) for n in ARMS});dd['ce_validation_selected']=dd[lock['control_selected']];dd['validation_selected']=dd[lock['selected']]
            if role=='outer_holdout':
                rr=prior.records(rows,f,dd)
                for i,z in enumerate(rr):z['raw_CNN_predictions']={n:int(probability[n][role][i].argmax()) for n in ARMS}
                output+=rr
            else:
                for n,d in dd.items():sp[n].append(d)
                for n in ARMS:raw_sp[n].append(probability[n][role].argmax(1))
    output.sort(key=lambda z:z['path']);assert len(output)==len({z['path'] for z in output})==5937;y=np.array([base.CLASSES.index(z['label']) for z in output]);current=np.array([z['predictions']['current_policy'] for z in output]);methods={}
    for n in METHODS:
        pred=np.array([z['predictions'][n] for z in output]);s=base.metrics(pred,y);assert np.array_equal(pred==5,current==5)
        s.update(correct=int((pred==y).sum()),changed=int((pred!=current).sum()),fixed=int(((pred!=current)&(pred==y)).sum()),harmed=int(((pred!=current)&(current==y)).sum()),wrong_to_wrong=int(((pred!=current)&(current!=y)&(pred!=y)).sum()),paired_delta95=prior.paired_intervals(output,pred,current,y),
            per_source={src:base.metrics(pred[[z['source']==src for z in output]],y[[z['source']==src for z in output]]) for src in ['original_train','SCIN']});methods[n]=s
    assert methods['current_policy']['correct']==4687
    per_fold={str(f):{n:base.metrics(np.array([z['predictions'][n] for z in output if z['fold']==f]),np.array([base.CLASSES.index(z['label']) for z in output if z['fold']==f])) for n in METHODS} for f in range(5)}
    raw={n:base.metrics(np.array([z['raw_CNN_predictions'][n] for z in output]),y) for n in ARMS}
    base.write(OUT/'oof_decisions.json',output);base.write(OUT/'results.json',dict(status='complete_exploratory_matched_SAM_CV',images=5937,methods=methods,raw_CNN=raw,per_fold=per_fold,selections=locks['selections'],held_started_utc=started,completed_utc=pilot.previous.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),all_selections_sha256=base.sha(OUT/'all_selections_locked.json'),
        new_CNN_continuations=8,reused_CNN_continuations=2,new_optimizer_updates=12120,new_gradient_passes=18180,serving_changed=False,retained_policy_changed=False,limitations=p['limitations']))
    source_output=[{k:z[k] for k in ['path','sha256','label','group','source','historical_role']}|dict(predictions={n:[int(d[i]) for d in sp[n]] for n in METHODS}) for i,z in enumerate(source['rows'])];base.write(OUT/'source_decisions.json',source_output)
    ids={z['path']:i for i,z in enumerate(source_output)};ys=np.array([base.CLASSES.index(z['label']) for z in source_output]);ss={}
    for subset,paths in source['subsets'].items():
        ix=[ids[path] for path in paths];ss[subset]=dict(images=len(ix),methods={n:transfer.mean_metrics(np.array(sp[n])[:,ix],ys[ix]) for n in METHODS},raw_CNN={n:transfer.mean_metrics(np.array(raw_sp[n])[:,ix],ys[ix]) for n in ARMS})
    base.write(OUT/'source_results.json',ss);prior.verify(p);base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),source_results_sha256=base.sha(OUT/'source_results.json')))
    status('evaluation_complete_awaiting_review',selections=locks['selections']);print(dict(selections=locks['selections'],scores={n:{k:s[k] for k in ['correct','accuracy','macro_f1','fixed','harmed']} for n,s in methods.items()}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args();torch.set_num_threads(4);lock_process();p=prepare()
    if args.prepare_only:return
    assert not (OUT/'results.json').exists(),'Preserve completed CV'
    with threadpool_limits(limits=4):
        if not (OUT/'all_selections_locked.json').exists():fit_all(p)
        evaluate(p)


if __name__=='__main__':main()
