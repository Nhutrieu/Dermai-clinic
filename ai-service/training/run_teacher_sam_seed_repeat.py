"""Precommitted seed43 continuation replication of matched CE/SAM across5folds.

Same original seed42-trained parent CNN weights; only data streams are repeated.
No search among seeds and no mixing seed43 predictions into seed42 policy.
"""
from __future__ import annotations
import argparse
import hashlib
import math
import os
from pathlib import Path
import random
import time
import numpy as np
import torch
from torch.nn import functional as F
from threadpoolctl import threadpool_limits
import run_teacher_sam_cv as parent
from common import ImageSampleDataset,seed_everything

ROOT,base,prior,latest,engine=parent.ROOT,parent.base,parent.prior,parent.latest,parent.engine
OUT=ROOT/'ai-service/reports/teacher_sam_cv_seed43_20261025'
MODELS=ROOT/'ai-service/candidates'/OUT.name
SEED=43
CONFIG={**parent.CONFIG,'seed':SEED,'stream_domain_stride':100_000_000}
ARMS=parent.ARMS;METHODS=parent.METHODS;HANDLE=None


def order_seed(seed,epoch):
    if seed<42 or epoch<1:raise ValueError('Seed>=42 and epoch>=1 required')
    return 42+epoch+(seed-42)*100_000_000


def augmentation_seed(seed,epoch,position):
    if seed<42 or epoch<1 or position<0 or position>=10000:raise ValueError('Invalid positional seed coordinates')
    return 420000+epoch*10000+position+(seed-42)*100_000_000


class SeededDataset(torch.utils.data.Dataset):
    def __init__(self,dataset,order,epoch,seed):self.dataset=dataset;self.order=order;self.epoch=epoch;self.seed=seed
    def __len__(self):return len(self.order)
    def __getitem__(self,position):
        python_state=random.getstate();numpy_state=np.random.get_state()
        try:
            with torch.random.fork_rng(devices=[]):
                seed=augmentation_seed(self.seed,self.epoch,position);random.seed(seed);np.random.seed(seed);torch.default_generator.manual_seed(seed)
                return self.dataset[self.order[position]]
        finally:random.setstate(python_state);np.random.set_state(numpy_state)


def status(state,**items):base.write(OUT/'status.json',dict(state=state,pid=os.getpid(),updated_utc=parent.pilot.previous.utc(),**items))


def process_lock():
    global HANDLE
    import msvcrt
    OUT.mkdir(parents=True,exist_ok=True);h=(OUT/'runner.lock').open('a+b')
    if h.tell()==0:h.write(b'0');h.flush()
    h.seek(0)
    try:msvcrt.locking(h.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:h.close();raise RuntimeError('Seed repetition already running')
    HANDLE=h


def folder(f,n):return MODELS/f'fold_{f}'/n


def prepare():
    if (OUT/'protocol.json').exists():p=base.read(OUT/'protocol.json');prior.verify(p);return p
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported();reg=base.read(ROOT/'ai-service/reports/active_research_track.json');assert reg['next_experiment'] is None
    old=base.read(parent.OUT/'protocol.json');prior.verify(old);assert base.read(parent.OUT/'completion.json')['status']=='complete_verified_not_promoted';folds=[dict(spec,reuse_verified_pilot=False,continuation_seed=SEED) for spec in old['folds']]
    files=[Path(__file__),ROOT/'ai-service/tests/test_teacher_sam_seed_repeat.py',parent.OUT/'protocol.json',parent.OUT/'results.json',parent.OUT/'source_results.json',parent.OUT/'completion.json',parent.OUT/'independent_review.json',parent.OUT/'oof_decisions.json',parent.OUT/'source_decisions.json',parent.OUT/'all_selections_locked.json',ROOT/'ai-service/app/config.py'];images={}
    for f,spec in enumerate(folds):
        parent.validate_roles(spec['roles']);assert spec['updates_each']==6*math.ceil(len(spec['roles']['train'])/16)
        files += [parent.OUT/f'fold_{f}/selection_locked.json',parent.OUT/f'fold_{f}/inner_decisions.npz']
        for n in ARMS:files += [parent.model_folder(f,n)/'history.json',parent.model_folder(f,n)/'training_report.json']
        for rows in spec['roles'].values():images.update({r['path']:r['sha256'] for r in rows})
    source=base.read(latest.OUT/'transfer_check/protocol.json');images.update({r['path']:r['sha256'] for r in source['rows']})
    for path,digest in images.items():assert base.sha(ROOT/path)==digest,path
    p=dict(name=OUT.name,registered_utc=parent.pilot.previous.utc(),classes=base.CLASSES,folds=folds,parent_protocol=old['parent_protocol'],seed42_protocol=(parent.OUT/'protocol.json').relative_to(ROOT).as_posix(),configuration=CONFIG,
        frozen_sha256={**old['frozen_sha256'],**{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},
        purpose='Precommit all5folds/10CE-SAM continuations with a new data-order/augmentation stream, irrespective fold0 success/failure. Replication not seedsearch; no choosebest seed42/43, no averaging/mixing seeds, no automatic policy promotion.',
        seed_scope='Original fold-specific ResNet checkpoints are exactly those trained/selected before at seed42; no independent end-to-end retraining/initialization/split. Only continuation stream isseed43. Order seed42+epoch+(seed-42)*100000000; positionalaugmentation420000+epoch*10000+position+(seed-42)*100000000. For42 reproduces original map,43 has a separate domain and does not merely shift epochs. Global seed43+epoch; bothCE/SAM same realized tensors.',
        training=old['training'],SAM=old['SAM'],routing=old['routing'],checkpoint_selection=old['checkpoint_selection'],selection=old['selection'].replace('Fold0choice/predictions must match pilot.','All5folds are newly trained; no fold0 reuse.'),
        matched='Same initialweights,data roles,trainablemask,allBNstatsfixed,augmentationoperators,6epochs,batch16,weightedCE,AdamWLR/decay/cosine/clip/BF16-FP32,rho.05. Exactly matched withinseed CE/SAM. Seed42reused for comparison,not retrained here; only order/augmentation seedstreams change betweencontinuations.',
        budget='10newCNNcontinuations:fold0updates1518perarm,fold1/2/3each1512perarm,fold4each1524perarm. Total15156committedoptimizerupdates/22734forward-backwardminibatchpasses,6epochsallarms. SAM2passes versusCE1,notcompute-matched. 0newbackbones.',
        evaluation='Same5937outer predictions once each and1709historicalsource photos across5systems. Freeze ALL5innerchoices before newouter/source forwards. Same guards/rank asseed42 against retainedDropout current_policy; no seed42-selected fallback added to selection. Report rawCE/SAM,CE-onlyselected/fullselected andseed42comparison separately. Paired1000scene-groupbootstrap vsretained andseed42-selected,seed20261022; not independent clinical confirmation.',
        logging='Epochmodel/frozen/order/augmentation/labelSHA,raw/routedinner,checkpointobjective,firstbatch CE/SAMlogit/loss/norm/restoreprobes,optimizer/scheduler resumable final states. Verify pairedhashes match withinseed and differ fromseed42; do not alter old logs.',
        limitations=old['limitations']+['Only a second continuationdata stream with same pretrained parentweights,split,cohort; not2independent from-scratch CNNseeds or freshpatients.','One selected extra seed fixedbeforeoutcomes, no sweep. Repeated use of outer/source remains exploratory; no conditional fullCV expansion or reselection of favorable seed.'],images_sha256_checked=len(images),new_CNN_continuations=10,new_backbones=0,serving_changed=False,retained_policy_changed=False,seed42_candidate_changed=False)
    base.write(OUT/'protocol.json',p);base.write(OUT/'research_registry_before.json',reg);reg['next_experiment']=OUT.relative_to(ROOT).as_posix();reg['next_experiment_status']='registered_full5fold_seed43_CE_SAM_replication';base.write(ROOT/'ai-service/reports/active_research_track.json',reg);status('registered',new_CNN_continuations=10);return p


def train(f,name,p):
    spec=p['folds'][f];directory=folder(f,name);directory.mkdir(parents=True,exist_ok=True)
    if (directory/'training_report.json').exists():
        r=base.read(directory/'training_report.json');assert r['protocol_sha256']==base.sha(OUT/'protocol.json') and r['checkpoint_sha256']==base.sha(directory/'best_model.pth');return
    seed_everything(SEED);model=parent.pilot.previous.load_initial(spec);assert engine.state_sha(model.state_dict())==spec['initial_state_sha256'];model.cuda();opt=torch.optim.AdamW([dict(params=list(model.layer4.parameters()),lr=CONFIG['layer4_lr']),dict(params=list(model.fc.parameters()),lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay']);scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(opt,T_max=6,eta_min=1e-6);alpha=torch.tensor([1.,1.,1.,1.5,1.5,1.,1.5,1.],device='cuda')
    rows=spec['roles']['train'];inner=spec['roles']['inner_validation'];truth,current=parent.inner_context(f,spec);baseline=base.metrics(current,truth);dataset=ImageSampleDataset(engine.objects(rows),engine.trainer.training_transform_v2());history=[];best=None;start=1;resume=directory/'resume_state.pth';expected=math.ceil(len(rows)/16)
    if resume.exists():
        saved=torch.load(resume,map_location='cpu',weights_only=False);assert saved['protocol_sha256']==base.sha(OUT/'protocol.json');model.load_state_dict(saved['model']);opt.load_state_dict(saved['optimizer']);scheduler.load_state_dict(saved['scheduler']);history=saved['history'];best=saved['best'];start=saved['epoch']+1;del saved
    for epoch in range(start,7):
        tick=time.monotonic();seed_everything(SEED+epoch);assert engine.configure(model,'layer4_finetune')==spec['trainable_names'];order=torch.randperm(len(rows),generator=torch.Generator().manual_seed(order_seed(SEED,epoch))).tolist();loader=engine.trainer.make_loader(SeededDataset(dataset,order,epoch,SEED),16,False,0,True);assert len(loader)==expected
        params=[v for v in model.parameters() if v.requires_grad];augmentation=hashlib.sha256();labels=hashlib.sha256();updates=0;total=0.;second_total=0.;probe=None;status('training',fold=f,arm=name,epoch=epoch,epochs_each=6,total_batches=expected)
        for batch,(x,y) in enumerate(loader):
            augmentation.update(x.numpy().tobytes());labels.update(y.numpy().tobytes());x=x.cuda();y=y.cuda();opt.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16):logits=model(x)
            loss=F.cross_entropy(logits.float(),y,weight=alpha)
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite firstCE')
            loss.backward();details=dict(first_loss=float(loss.detach()))
            if batch==0:probe=dict(logits=logits.detach().float().cpu().numpy(),targets=y.cpu().numpy(),loss=float(loss.detach()))
            if name=='sam_rho005':
                originals,norm=parent.pilot.perturb(params,.05)
                if batch==0:details.update(first_grad_norm=norm,perturb_l2=float(torch.sqrt(sum((v.detach()-old).square().sum() for v,old in zip(params,originals)))))
                opt.zero_grad(set_to_none=True)
                try:
                    with torch.autocast('cuda',dtype=torch.bfloat16):second_logits=model(x)
                    robust=F.cross_entropy(second_logits.float(),y,weight=alpha)
                    if not torch.isfinite(robust):raise FloatingPointError('Nonfinite perturbedCE')
                    robust.backward();second_total+=float(robust.detach())
                    if batch==0:probe['perturbed_logits']=second_logits.detach().float().cpu().numpy();details['perturbed_loss']=float(robust.detach())
                finally:parent.pilot.restore(params,originals)
                if batch==0:details['restore_exact']=all(torch.equal(v.detach(),old) for v,old in zip(params,originals))
                del originals
            norm=torch.nn.utils.clip_grad_norm_(params,2,error_if_nonfinite=True);opt.step();updates+=1;total+=float(loss.detach())
            if batch==0:details['optimizer_grad_norm_before_clip']=float(norm);probe.update({k:np.array(v) for k,v in details.items()})
            if (batch+1)%64==0:status('training',fold=f,arm=name,epoch=epoch,batches=batch+1,total_batches=expected,seconds=time.monotonic()-tick)
        assert updates==expected and engine.frozen_hash(model)==spec['frozen_state_sha256'];state=engine.state_sha(model.state_dict());q=engine.infer(model,inner);score=base.metrics(parent.pilot.pair_route(current,q),truth);raw=base.metrics(q.argmax(1),truth);key=parent.pilot.objective(score,baseline);improved=best is None or tuple(key)>tuple(best['objective'])
        if improved:
            best=dict(epoch=epoch,objective=key,routed_validation=score,raw_validation=raw,state_sha256=state);engine.utility.atomic_save(dict(model_state_dict=model.state_dict(),architecture='resnet50',classes=base.CLASSES,fold=f,arm=name,epoch=epoch,continuation_seed=SEED,protocol_sha256=base.sha(OUT/'protocol.json'),research_only=True),directory/'best_model.pth')
        np.savez_compressed(directory/f'epoch_{epoch:02d}_inner.npz',paths=[r['path'] for r in inner],probabilities=q,model_state_sha256=state);np.savez_compressed(directory/f'epoch_{epoch:02d}_loss_probe.npz',**probe);scheduler.step();row=dict(epoch=epoch,loss=total/updates,perturbed_loss=second_total/updates if name=='sam_rho005' else None,actual_updates=updates,images=len(rows),unique_images=len(set(order)),order_sha256=hashlib.sha256(base.json.dumps(order).encode()).hexdigest(),augmentation_sha256=augmentation.hexdigest(),labels_sha256=labels.hexdigest(),frozen_state_sha256=engine.frozen_hash(model),model_state_sha256=state,routed_validation=score,raw_validation=raw,new_best=improved,best_epoch=best['epoch'],seconds=time.monotonic()-tick);history.append(row);base.write(directory/'history.json',history);engine.utility.atomic_save(dict(protocol_sha256=base.sha(OUT/'protocol.json'),epoch=epoch,model=model.state_dict(),optimizer=opt.state_dict(),scheduler=scheduler.state_dict(),history=history,best=best),resume);print(dict(fold=f,arm=name,epoch=epoch,accuracy=score['accuracy'],macro_f1=score['macro_f1'],best_epoch=best['epoch'],seconds=row['seconds']),flush=True)
    base.write(directory/'training_report.json',dict(protocol_sha256=base.sha(OUT/'protocol.json'),fold=f,arm=name,continuation_seed=SEED,checkpoint_sha256=base.sha(directory/'best_model.pth'),best=best,epochs=6,actual_updates=spec['updates_each'],initial_state_sha256=spec['initial_state_sha256'],frozen_state_sha256=engine.frozen_hash(model),final_state_sha256=history[-1]['model_state_sha256'],forward_backward_passes=spec['updates_each']*(2 if name=='sam_rho005' else 1),all_batchnorm_running_statistics_fixed=True));del model,opt;torch.cuda.empty_cache()


def lock_fold(f,p):
    directory=OUT/f'fold_{f}';directory.mkdir(parents=True,exist_ok=True)
    if (directory/'selection_locked.json').exists():
        lock=base.read(directory/'selection_locked.json')
        for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
        return
    spec=p['folds'][f];truth,current=parent.inner_context(f,spec);dd=dict(current_policy=current);raw={};hist={n:base.read(folder(f,n)/'history.json') for n in ARMS};old={n:base.read(parent.model_folder(f,n)/'history.json') for n in ARMS};differences={n:[] for n in ARMS};files=[]
    for epoch in range(6):
        for key in ['augmentation_sha256','labels_sha256','order_sha256','images','unique_images','actual_updates']:assert hist[ARMS[0]][epoch][key]==hist[ARMS[1]][epoch][key]
        for n in ARMS:
            changed={key:hist[n][epoch][key]!=old[n][epoch][key] for key in ['augmentation_sha256','labels_sha256','order_sha256']};assert all(changed.values());differences[n].append(changed)
    for n in ARMS:
        report=base.read(folder(f,n)/'training_report.json');epoch=report['best']['epoch']
        with np.load(folder(f,n)/f'epoch_{epoch:02d}_inner.npz',allow_pickle=False) as z:assert z['paths'].tolist()==[r['path'] for r in spec['roles']['inner_validation']];q=z['probabilities'].copy()
        dd[n]=parent.pilot.pair_route(current,q);raw[n]=base.metrics(q.argmax(1),truth);files+=list(folder(f,n).glob('*.npz'))+[folder(f,n)/name for name in ['best_model.pth','history.json','training_report.json','resume_state.pth']]
    lock=parent.pilot.choose(dd,truth);np.savez_compressed(directory/'inner_decisions.npz',paths=[r['path'] for r in spec['roles']['inner_validation']],truth=truth,**dd);lock.update(control_selected=parent.control_choice(lock['trials']),locked_utc=parent.pilot.previous.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),raw_validation=raw,stream_differences_vs_seed42=differences,artifacts_sha256={x.relative_to(ROOT).as_posix():base.sha(x) for x in files+[directory/'inner_decisions.npz']});base.write(directory/'selection_locked.json',lock);print(dict(fold=f,selected=lock['selected'],control_selected=lock['control_selected'],sam_failures=lock['trials']['sam_rho005']['guard_failures']),flush=True)


def fit_all(p):
    for f in range(5):
        for n in ARMS:train(f,n,p)
        lock_fold(f,p)
    base.write(OUT/'all_selections_locked.json',dict(locked_utc=parent.pilot.previous.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),selections={str(f):base.read(OUT/f'fold_{f}/selection_locked.json')['selected'] for f in range(5)},sha256={str(f):base.sha(OUT/f'fold_{f}/selection_locked.json') for f in range(5)}))


def evaluate(p):
    assert not (OUT/'results.json').exists();locks=base.read(OUT/'all_selections_locked.json');started=parent.pilot.previous.utc();source=base.read(latest.OUT/'transfer_check/protocol.json');original={r['path']:r for r in base.read(latest.OUT/'oof_decisions.json')};old42={r['path']:r for r in base.read(parent.OUT/'oof_decisions.json')};source_ref=base.read(latest.OUT/'transfer_check/source_decisions.json');output=[];sp={n:[] for n in METHODS};raw_sp={n:[] for n in ARMS}
    for f,spec in enumerate(p['folds']):
        lock=base.read(OUT/f'fold_{f}/selection_locked.json');assert locks['sha256'][str(f)]==base.sha(OUT/f'fold_{f}/selection_locked.json')
        for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
        probability={n:{} for n in ARMS}
        for n in ARMS:
            model=parent.pilot.previous.load_initial(spec);saved=torch.load(folder(f,n)/'best_model.pth',map_location='cpu',weights_only=False);model.load_state_dict(saved['model_state_dict']);assert engine.frozen_hash(model)==spec['frozen_state_sha256'];model.cuda()
            for role,rows in [('outer_holdout',spec['roles']['outer_holdout']),('source_transfer',source['rows'])]:
                status('evaluating',fold=f,arm=n,role=role);q=engine.infer(model,rows);probability[n][role]=q;np.savez_compressed(OUT/f'fold_{f}/{role}_{n}_probabilities.npz',paths=[r['path'] for r in rows],probabilities=q)
            del model,saved;torch.cuda.empty_cache()
        for role,rows in [('outer_holdout',spec['roles']['outer_holdout']),('source_transfer',source['rows'])]:
            current=np.array([original[r['path']]['predictions']['validation_selected'] for r in rows]) if role=='outer_holdout' else np.array([r['predictions']['validation_selected'][f] for r in source_ref]);dd=dict(current_policy=current);dd.update({n:parent.pilot.pair_route(current,probability[n][role]) for n in ARMS});dd['ce_validation_selected']=dd[lock['control_selected']];dd['validation_selected']=dd[lock['selected']]
            if role=='outer_holdout':
                rr=prior.records(rows,f,dd)
                for i,z in enumerate(rr):z['raw_CNN_predictions']={n:int(probability[n][role][i].argmax()) for n in ARMS};z['seed42_selected_prediction']=old42[z['path']]['predictions']['validation_selected']
                output+=rr
            else:
                for n,d in dd.items():sp[n].append(d)
                for n in ARMS:raw_sp[n].append(probability[n][role].argmax(1))
    output.sort(key=lambda z:z['path']);assert len(output)==len({z['path'] for z in output})==5937;y=np.array([base.CLASSES.index(z['label']) for z in output]);current=np.array([z['predictions']['current_policy'] for z in output]);seed42=np.array([z['seed42_selected_prediction'] for z in output]);methods={}
    for n in METHODS:
        d=np.array([z['predictions'][n] for z in output]);s=base.metrics(d,y);changed=d!=current;assert np.array_equal(d==5,current==5);s.update(correct=int((d==y).sum()),changed=int(changed.sum()),fixed=int((changed&(d==y)).sum()),harmed=int((changed&(current==y)).sum()),wrong_to_wrong=int((changed&(current!=y)&(d!=y)).sum()),paired_delta95=prior.paired_intervals(output,d,current,y),paired_delta95_vs_seed42=prior.paired_intervals(output,d,seed42,y),per_source={src:base.metrics(d[[z['source']==src for z in output]],y[[z['source']==src for z in output]]) for src in ['original_train','SCIN']});methods[n]=s
    assert methods['current_policy']['correct']==4687 and (seed42==y).sum()==4688
    per_fold={str(f):{n:base.metrics(np.array([z['predictions'][n] for z in output if z['fold']==f]),np.array([base.CLASSES.index(z['label']) for z in output if z['fold']==f])) for n in METHODS} for f in range(5)};raw={n:base.metrics(np.array([z['raw_CNN_predictions'][n] for z in output]),y) for n in ARMS};base.write(OUT/'oof_decisions.json',output);base.write(OUT/'results.json',dict(status='complete_exploratory_seed43_data_stream_replication',images=5937,continuation_seed=SEED,methods=methods,raw_CNN=raw,per_fold=per_fold,selections=locks['selections'],seed42_selected_reference=base.metrics(seed42,y),held_started_utc=started,completed_utc=parent.pilot.previous.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),all_selections_sha256=base.sha(OUT/'all_selections_locked.json'),new_CNN_continuations=10,optimizer_updates=15156,gradient_passes=22734,retained_policy_changed=False,seed42_candidate_changed=False,serving_changed=False,limitations=p['limitations']))
    sout=[{k:z[k] for k in ['path','sha256','label','group','source','historical_role']}|dict(predictions={n:[int(d[i]) for d in sp[n]] for n in METHODS}) for i,z in enumerate(source['rows'])];base.write(OUT/'source_decisions.json',sout);ids={z['path']:i for i,z in enumerate(sout)};ys=np.array([base.CLASSES.index(z['label']) for z in sout]);ss={}
    for subset,paths in source['subsets'].items():
        ix=[ids[path] for path in paths];ss[subset]=dict(images=len(ix),methods={n:parent.transfer.mean_metrics(np.array(sp[n])[:,ix],ys[ix]) for n in METHODS},raw_CNN={n:parent.transfer.mean_metrics(np.array(raw_sp[n])[:,ix],ys[ix]) for n in ARMS})
    base.write(OUT/'source_results.json',ss);prior.verify(p);base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),source_results_sha256=base.sha(OUT/'source_results.json')));status('evaluation_complete_awaiting_review');print(dict(selections=locks['selections'],scores={n:{k:s[k] for k in ['correct','accuracy','macro_f1','fixed','harmed']} for n,s in methods.items()}),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args();torch.set_num_threads(4);process_lock();p=prepare()
    if args.prepare_only:return
    assert not (OUT/'results.json').exists(),'Preserve completed replication'
    with threadpool_limits(limits=4):
        if not (OUT/'all_selections_locked.json').exists():fit_all(p)
        evaluate(p)


if __name__=='__main__':main()
