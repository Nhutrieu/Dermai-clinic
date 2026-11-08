"""Fresh ImageNet V2 ResNet50: matched plain versus MixUp, one frozen fold."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torchvision
from torch.nn import functional as F

from common import CLASSES,ImageSampleDataset,evaluation_transform,seed_everything
import train_v2 as trainer
import evaluate_original_eight_cancer_locked_fusion as fusion
import pilot_original_eight_balanced_softmax as prior

ROOT=prior.ROOT
NAME='original_eight_imagenet_mixup_fold0_seed42_20261021'
OUT=ROOT/'ai-service/reports'/NAME
MODELS=ROOT/'ai-service/candidates'/NAME
INITIAL=MODELS/'shared_imagenet_initial.pth'
BRANCHES=['plain_control','mixup']
CONFIG=dict(seed=42,epochs=24,freeze_epochs=2,batch_size=16,workers=0,
    backbone_lr=5e-5,head_lr=2e-4,weight_decay=.0002,effective_number_beta=.999,
    label_smoothing=.05,mixup_alpha=.2,ema_decay=.995,ema_update='each_optimizer_step',
    precision='CUDA BF16 autocast; FP32 parameters, loss and optimizer; no GradScaler',torch_threads=4)
HANDLE=None


def mix_plan(epoch,batch,size):
    if epoch<1 or batch<0 or size<1:raise ValueError('Invalid draw coordinates')
    generator=np.random.default_rng(42000000+epoch*10000+batch)
    coefficient=float(generator.beta(CONFIG['mixup_alpha'],CONFIG['mixup_alpha'])) if epoch>CONFIG['freeze_epochs'] else 1.
    return coefficient,generator.permutation(size).astype(np.int64)


def mix_loss(logits,labels,partner,coefficient,weights):
    if not 0<=coefficient<=1:raise ValueError('MixUp coefficient outside[0,1]')
    a=F.cross_entropy(logits.float(),labels,weight=weights,label_smoothing=CONFIG['label_smoothing'],reduction='none')
    b=F.cross_entropy(logits.float(),labels[partner],weight=weights,label_smoothing=CONFIG['label_smoothing'],reduction='none')
    # The partner is a permutation, so both hard-label weight sums match.
    return (coefficient*a+(1-coefficient)*b).sum()/weights[labels].sum()


def state_sha(state):
    digest=hashlib.sha256()
    for key,value in sorted(state.items()):
        data=value.detach().cpu().contiguous()
        digest.update(key.encode());digest.update(str(data.dtype).encode());digest.update(str(tuple(data.shape)).encode());digest.update(data.numpy().tobytes())
    return digest.hexdigest()


class SeededDataset(torch.utils.data.Dataset):
    def __init__(self,base,order,epoch):self.base=base;self.order=order;self.epoch=epoch
    def __len__(self):return len(self.order)
    def __getitem__(self,position):
        # Isolate transforms from loader/model RNG and later draw dimensions.
        import random
        python_state=random.getstate();numpy_state=np.random.get_state()
        try:
            with torch.random.fork_rng(devices=[]):
                seed=420000+self.epoch*10000+position
                random.seed(seed);np.random.seed(seed);torch.default_generator.manual_seed(seed)
                x,y=self.base[self.order[position]]
        finally:random.setstate(python_state);np.random.set_state(numpy_state)
        return x,y


def guards(scores):
    baseline=scores['current_fusion'];trials={}
    for name,value in scores.items():
        reasons=fusion.guard_failures(value,baseline)
        for label in ['Lupus','Psoriasis','Tinea']:
            for key in ['f1','recall']:
                if value['per_class'][label][key]+1e-12<baseline['per_class'][label][key]:reasons.append(label+'_'+key)
        if name=='mixup':
            if value['macro_f1']+1e-12<scores['plain_control']['macro_f1']:reasons.append('macro_f1_below_matched_control')
            if prior.mean_focus(value)<=prior.mean_focus(scores['plain_control'])+1e-12:reasons.append('no_mean_focus_f1_gain_vs_control')
        trials[name]=dict(metrics=value,guard_failures=reasons)
    eligible=[name for name in trials if not trials[name]['guard_failures']]
    selected=max(eligible,key=lambda name:(scores[name]['macro_f1'],prior.mean_focus(scores[name]),scores[name]['accuracy'],name=='current_fusion',name=='plain_control'))
    return selected,trials


def status(state,**kwargs):
    fusion.write(OUT/'status.json',dict(state=state,pid=os.getpid(),updated_unix=time.time(),**kwargs))


def lock_process():
    global HANDLE
    import msvcrt
    OUT.mkdir(parents=True,exist_ok=True);handle=(OUT/'runner.lock').open('a+b')
    if handle.tell()==0:handle.write(b'0');handle.flush()
    handle.seek(0)
    try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        handle.close();raise RuntimeError('ImageNet MixUp pilot already running')
    HANDLE=handle


def verify(p):
    for path,h in p['frozen_sha256'].items():assert fusion.sha(ROOT/path)==h,path
    assert fusion.sha(Path(p['imagenet_cache_path']))==p['imagenet_cache_sha256']


def fresh_initial(cache):
    seed_everything(42);model=prior.build_model('resnet50',8,pretrained=False)
    source=torch.load(cache,map_location='cpu',weights_only=True)
    source.pop('fc.weight');source.pop('fc.bias')
    result=model.load_state_dict(source,strict=False)
    assert sorted(result.missing_keys)==['fc.bias','fc.weight'] and not result.unexpected_keys
    for key,value in source.items():assert torch.equal(model.state_dict()[key],value),key
    return model


def prepare():
    if (OUT/'protocol.json').exists():
        p=fusion.read(OUT/'protocol.json');verify(p);return p
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    cache=Path(torch.hub.get_dir())/'checkpoints/resnet50-11ad3fa6.pth'
    old=fusion.read(prior.PARENT_REPORT/'protocol.json');assert fusion.sha(cache)==old['pretrained_sha256']
    inventory={row['path']:row for row in fusion.read(prior.AUDIT/'image_inventory.json')}
    role_paths=fusion.read(fusion.CV/'protocol.json')['folds'][0]['roles']
    roles={name:[{key:inventory[path][key] for key in ['path','label','sha256','group']} for path in paths] for name,paths in role_paths.items()}
    assert [len(roles[name]) for name in ['train','inner_validation','outer_holdout']]==[4043,718,1176]
    for a,b in [('train','inner_validation'),('train','outer_holdout'),('inner_validation','outer_holdout')]:
        for key in ['path','sha256','group']:assert {r[key] for r in roles[a]}.isdisjoint(r[key] for r in roles[b])
    for rows in roles.values():
        for row in rows:assert fusion.sha(ROOT/row['path'])==row['sha256']
    initial=fresh_initial(cache);initial_hash=state_sha(initial.state_dict())
    MODELS.mkdir(parents=True,exist_ok=True)
    if INITIAL.exists():assert state_sha(torch.load(INITIAL,map_location='cpu',weights_only=False)['model_state_dict'])==initial_hash
    else:prior.atomic_save(dict(model_state_dict=initial.state_dict(),architecture='resnet50',classes=CLASSES,
        provenance='Only ImageNetV2 backbone plus seed42fresh8-way fc',state_sha256=initial_hash,research_only=True),INITIAL)
    del initial
    files=[INITIAL,prior.AUDIT/'image_inventory.json',fusion.CV/'protocol.json',prior.PARENT_REPORT/'protocol.json',
        prior.PARENT_REPORT/'validation_predictions.npz',prior.PARENT_REPORT/'test_predictions.json',
        prior.CURRENT/'results.json',prior.CURRENT/'fold_0/selection_locked.json',prior.CURRENT/'independent_review.json',
        fusion.SERVING,fusion.BENCHMARK,ROOT/'ai-service/tests/test_imagenet_mixup_pilot.py']
    files += [ROOT/'ai-service/training'/name for name in ['pilot_original_eight_imagenet_mixup.py','pilot_original_eight_balanced_softmax.py',
        'evaluate_original_eight_cancer_locked_fusion.py','common.py','train_v2.py']]
    p=dict(name=NAME,date='2026-10-21',classes=CLASSES,roles=roles,configuration=CONFIG,
        frozen_sha256={path.relative_to(ROOT).as_posix():fusion.sha(path) for path in files},
        imagenet_cache_path=str(cache),imagenet_cache_sha256=fusion.sha(cache),shared_initial_state_sha256=initial_hash,
        runtime=dict(torch=torch.__version__,torchvision=torchvision.__version__,cuda=torch.version.cuda,numpy=np.__version__,gpu=torch.cuda.get_device_name(0)),
        initialization='Fresh deterministic8-way fc and ImageNetV2 backbone only; exact shared artifact, never initialize from a skin-trained checkpoint.',
        training='Exactly24epochs/branch, first2backbone parameters frozen but BN stats update in train mode; remaining22 full fine-tuning. AdamW backbone5e-5/head2e-4, wd.0002, cosine22eta_min1e-6 after warmup. BF16 autocast FP32logits/loss/parameters/optimizer, no GradScaler or skipped steps. Clip2; EMA.995after EVERY optimizer step.',
        matched='Same4043images and original hard labels, every image once/epoch, same per-position transforms, order, initial state, class weights, optimizer budget and precision. No auxiliary or soft-source labels. Track actual augmentation/label/order and planned pair/coefficient hashes. Both warmup trajectories must match exactly.',
        mixup='From epoch3 only: lambda~Beta(.2,.2), within-batch permutation from independent numpy RNG seed42000000+epoch*10000+batch. Mixed input=lambda*x+(1-lambda)*x[permutation]. Loss=lambda*weighted smoothed CE(y)+(1-lambda)*weighted smoothed CE(y[permutation]), normalize shared sum of hard-label weights. Control receives original input and lambda1; computes same random plan only for audit. No mixup at validation/inference.',
        checkpoint_selection='Best inner MacroF1, then Top3, then lower smoothed weighted CE across24epochs and raw/EMA; prefer raw on exact tie. No early stopping; both branches get same full budget. All checkpoint selection uses718inner only.',
        fusion='Same frozen75%original B0/Conv reference+25%branch ResNet. Learn monotone protected class masks on inner with existing procedure. Preserve complete SkinCancer decision mask.',
        selection='Accuracy and MacroF1>=current; prior class guards and exact cancer recall/precision; Lupus/Psoriasis/Tinea recall andF1>=current. MixUp also MacroF1>=plain and mean weak3F1 strictly greater than plain. Rank MacroF1, mean weak3F1, Accuracy; prefer current then plain on tie. Lock before1176outer access/inference.',
        paper='https://arxiv.org/abs/1710.09412',
        limitations=['Onefold/seed development experiment; historical inner/outer repeatedly viewed. No new independent test created by fresh initialization.',
            'Source labels and original patient identity limitations unchanged; no new expert diagnosis.',
            'BF16 and per-step EMA are common to both new branches but differ from original older AMP/per-epoch EMA recipe. Plain control isolates MixUp within this new recipe, not each historical difference.',
            'No automatic fivefold expansion, serving checkpoint swap, Word update or change to5937global score. No guaranteed gain from MixUp.'])
    fusion.write(OUT/'protocol.json',p);status('registered',epochs_limit=24,branches=BRANCHES)
    registry_path=ROOT/'ai-service/reports/active_research_track.json';registry=fusion.read(registry_path)
    registry['next_experiment']=OUT.relative_to(ROOT).as_posix();registry['next_experiment_status']='registered_fresh_imagenet_mixup'
    registry['next_step']='Run registered fresh ImageNet plain/MixUp onefold comparison, lock selection before outer, preserve full benchmark and serving.'
    fusion.write(registry_path,registry);return p


def train_branch(branch,p):
    folder=MODELS/branch;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'training_report.json').exists():
        r=fusion.read(folder/'training_report.json');assert r['protocol_sha256']==fusion.sha(OUT/'protocol.json')
        assert r['checkpoint_sha256']==fusion.sha(folder/'best_model.pth');return
    seed_everything(42);model=prior.build_model('resnet50',8,pretrained=False)
    checkpoint=torch.load(INITIAL,map_location='cpu',weights_only=False);model.load_state_dict(checkpoint['model_state_dict'])
    assert state_sha(model.state_dict())==p['shared_initial_state_sha256'];del checkpoint
    model.cuda();ema=copy.deepcopy(model).eval().requires_grad_(False)
    backbone,head=trainer.classifier_parameters(model)
    optimizer=torch.optim.AdamW([dict(params=backbone,lr=CONFIG['backbone_lr']),dict(params=head,lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=22,eta_min=1e-6)
    train=p['roles']['train'];inner=p['roles']['inner_validation']
    weights,counts=trainer.effective_number_weights(prior.objects(train),.999,torch.device('cuda'))
    criterion=torch.nn.CrossEntropyLoss(weight=weights,label_smoothing=.05)
    base=ImageSampleDataset(prior.objects(train),trainer.training_transform_v2())
    vloader=trainer.make_loader(ImageSampleDataset(prior.objects(inner),evaluation_transform()),16,False,0,True)
    history=[];start=1;best=None;resume=folder/'resume_state.pth'
    if resume.exists():
        saved=torch.load(resume,map_location='cpu',weights_only=False);assert saved['protocol_sha256']==fusion.sha(OUT/'protocol.json')
        model.load_state_dict(saved['model']);ema.load_state_dict(saved['ema']);optimizer.load_state_dict(saved['optimizer']);scheduler.load_state_dict(saved['scheduler'])
        history=saved['history'];best=saved['best'];start=saved['epoch']+1;del saved
    for epoch in range(start,25):
        status('training',branch=branch,epoch=epoch,epochs_limit=24,best_epoch=None if best is None else best['epoch'])
        for parameter in backbone:parameter.requires_grad_(epoch>2)
        seed_everything(42+epoch)
        indices=torch.randperm(len(train),generator=torch.Generator().manual_seed(42+epoch)).tolist()
        loader=trainer.make_loader(SeededDataset(base,indices,epoch),16,False,0,True)
        augmentation_hash=hashlib.sha256();labels_hash=hashlib.sha256();plan_hash=hashlib.sha256();actual_plan_hash=hashlib.sha256()
        updates=0;loss_sum=0;began=time.monotonic();model.train()
        for batch,(x,y) in enumerate(loader):
            augmentation_hash.update(x.numpy().tobytes());labels_hash.update(y.numpy().tobytes())
            coefficient,permutation=mix_plan(epoch,batch,len(y))
            plan_hash.update(np.array([coefficient],dtype=np.float64).tobytes());plan_hash.update(permutation.tobytes())
            actual=coefficient if branch=='mixup' else 1.
            actual_plan_hash.update(np.array([actual],dtype=np.float64).tobytes());actual_plan_hash.update(permutation.tobytes())
            x=x.cuda();y=y.cuda();partner=torch.tensor(permutation,device='cuda')
            if actual!=1:x=actual*x+(1-actual)*x[partner]
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16):logits=model(x)
            loss=mix_loss(logits,y,partner,actual,weights)
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),2,error_if_nonfinite=True);optimizer.step()
            trainer.update_ema(ema,model,.995);updates+=1;loss_sum+=float(loss.detach())
        assert updates==253
        assert all(torch.isfinite(value).all() for value in model.state_dict().values() if value.is_floating_point())
        raw=trainer.run_epoch(model,vloader,criterion,torch.device('cuda'));averaged=trainer.run_epoch(ema,vloader,criterion,torch.device('cuda'))
        source=max(['raw','ema'],key=lambda n:((raw if n=='raw' else averaged)['macro_f1'],(raw if n=='raw' else averaged)['top3_accuracy'],-(raw if n=='raw' else averaged)['loss'],n=='raw'))
        metrics=raw if source=='raw' else averaged;key=[metrics['macro_f1'],metrics['top3_accuracy'],-metrics['loss']]
        improved=best is None or tuple(key)>tuple(best['objective'])
        if improved:
            best=dict(epoch=epoch,source=source,objective=key,validation=metrics)
            prior.atomic_save(dict(model_state_dict=(model if source=='raw' else ema).state_dict(),architecture='resnet50',classes=CLASSES,
                protocol_sha256=fusion.sha(OUT/'protocol.json'),epoch=epoch,branch=branch,selected_weights=source,research_only=True),folder/'best_model.pth')
        if epoch>2:scheduler.step()
        record=dict(epoch=epoch,training_loss=loss_sum/updates,actual_updates=updates,attempted_updates=len(loader),draws=len(indices),unique_images=len(set(indices)),
            augmentation_sha256=augmentation_hash.hexdigest(),labels_sha256=labels_hash.hexdigest(),planned_mix_sha256=plan_hash.hexdigest(),actual_mix_sha256=actual_plan_hash.hexdigest(),
            draw_indices_sha256=hashlib.sha256(json.dumps(indices).encode()).hexdigest(),class_draw_counts=dict(Counter(train[i]['label'] for i in indices)),
            backbone_frozen=epoch<=2,validation_raw=raw,validation_ema=averaged,selected_new_best=improved,best_epoch=best['epoch'],seconds=time.monotonic()-began)
        if epoch<=2:record.update(warmup_model_state_sha256=state_sha(model.state_dict()),warmup_ema_state_sha256=state_sha(ema.state_dict()))
        history.append(record);fusion.write(folder/'history.json',history)
        prior.atomic_save(dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),epoch=epoch,model=model.state_dict(),ema=ema.state_dict(),optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),history=history,best=best),resume)
        print(json.dumps(dict(branch=branch,epoch=epoch,raw_macro_f1=raw['macro_f1'],ema_macro_f1=averaged['macro_f1'],best_epoch=best['epoch'],actual_updates=updates,seconds=record['seconds'])),flush=True)
    del model,ema,optimizer;torch.cuda.empty_cache()
    saved=torch.load(folder/'best_model.pth',map_location='cpu',weights_only=False);chosen=prior.build_model('resnet50',8,pretrained=False);chosen.load_state_dict(saved['model_state_dict']);chosen.cuda()
    probabilities=prior.infer(chosen,inner)
    fusion.write(folder/'inner_predictions.json',dict(paths=[row['path'] for row in inner],probabilities=probabilities.tolist()))
    fusion.write(folder/'training_report.json',dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),checkpoint_sha256=fusion.sha(folder/'best_model.pth'),
        initial_checkpoint_sha256=fusion.sha(INITIAL),initial_state_sha256=p['shared_initial_state_sha256'],branch=branch,classes=CLASSES,epochs=24,
        best=best,actual_updates=sum(row['actual_updates'] for row in history),class_counts=counts,class_weights=weights.cpu().tolist(),precision=CONFIG['precision'],
        outer_used_for_selection=False,skipped_updates=0))
    del chosen,saved;torch.cuda.empty_cache()


def evaluate(p):
    paths,y,ref,original=fusion.validation_arrays(0);parent=fusion.read(prior.CURRENT/'fold_0/selection_locked.json')
    protected=parent['trials'][parent['selected']]['spec']['protected'];policies={'current_fusion':protected};traces={};raw_validation={}
    values={'current_fusion':fusion.decide(ref,original,protected)}
    for branch in BRANCHES:
        inner=fusion.read(MODELS/branch/'inner_predictions.json');assert inner['paths']==paths
        raw=np.array(inner['probabilities']);policies[branch],traces[branch]=fusion.learn_protected(ref,raw,y)
        values[branch]=fusion.decide(ref,raw,policies[branch]);raw_validation[branch]=fusion.metrics(raw.argmax(1),y)
    validation={name:fusion.metrics(pred,y) for name,pred in values.items()};selected,trials=guards(validation)
    fusion.write(OUT/'selection_locked.json',dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),selected=selected,trials=trials,protected=policies,
        protection_trace=traces,raw_validation=raw_validation,checkpoints={b:fusion.sha(MODELS/b/'best_model.pth') for b in BRANCHES}))
    status('evaluating_outer',selected=selected);print(json.dumps(dict(selection_locked=selected)),flush=True)
    old=fusion.read(prior.PARENT_REPORT/'test_predictions.json');lookup={row['path']:row for row in p['roles']['outer_holdout']}
    assert set(lookup)=={row['path'] for row in old};rows=[lookup[row['path']] for row in old]
    y=np.array([CLASSES.index(row['label']) for row in rows]);ref=np.array([row['probabilities']['old_classwise'] for row in old]);original=np.array([row['probabilities']['resnet50'] for row in old])
    raw={};values={'current_fusion':fusion.decide(ref,original,policies['current_fusion'])}
    for branch in BRANCHES:
        checkpoint=torch.load(MODELS/branch/'best_model.pth',map_location='cpu',weights_only=False)
        model=prior.build_model('resnet50',8,pretrained=False);model.load_state_dict(checkpoint['model_state_dict']);model.cuda()
        raw[branch]=prior.infer(model,rows);values[branch]=fusion.decide(ref,raw[branch],policies[branch]);del model,checkpoint;torch.cuda.empty_cache()
    values['validation_selected']=values[selected]
    for value in values.values():assert np.array_equal(value==5,values['current_fusion']==5)
    output=[dict(**row,source='SCIN' if row['path'].startswith('SkinDisease/scin-v1/') else 'original_train',
        predictions={name:int(value[i]) for name,value in values.items()},
        raw_component_probabilities={'old_classwise':ref[i].tolist(),'original_resnet50':original[i].tolist(),**{b:prob[i].tolist() for b,prob in raw.items()}}) for i,row in enumerate(rows)]
    fusion.write(OUT/'outer_decisions.json',output)
    result=dict(status='complete_exploratory_fresh_imagenet_mixup',classes=CLASSES,images=1176,selected=selected,validation=validation,
        methods={name:fusion.metrics(value,y) for name,value in values.items()},raw_outer={b:fusion.metrics(prob.argmax(1),y) for b,prob in raw.items()},
        protocol_sha256=fusion.sha(OUT/'protocol.json'),selection_sha256=fusion.sha(OUT/'selection_locked.json'),
        per_source={source:{name:fusion.metrics(value[np.array([r['source']==source for r in output])],y[np.array([r['source']==source for r in output])]) for name,value in values.items()} for source in ['original_train','SCIN']},
        global_5937_score_changed=False,serving_changed=False,labels_changed=0,limitations=p['limitations'])
    fusion.write(OUT/'results.json',result);return result


def run(p):
    assert not (OUT/'results.json').exists(),'Preserve completed experiment';verify(p)
    for branch in BRANCHES:train_branch(branch,p)
    histories={b:fusion.read(MODELS/b/'history.json') for b in BRANCHES}
    for epoch in range(24):
        keys=['augmentation_sha256','labels_sha256','planned_mix_sha256','draw_indices_sha256','class_draw_counts','actual_updates','draws','unique_images']
        if epoch<2:keys+=['actual_mix_sha256','warmup_model_state_sha256','warmup_ema_state_sha256']
        for key in keys:assert histories['plain_control'][epoch][key]==histories['mixup'][epoch][key],(epoch+1,key)
    result=evaluate(p);verify(p)
    fusion.write(OUT/'verification.json',dict(status='PASS',scope='Technical consistency, not clinical validation',actual_updates_each=6072,
        matched_actual_augmentation_and_exposure=True,identical_initial_and_warmup_states=True,skipped_updates=0,
        results_sha256=fusion.sha(OUT/'results.json'),serving_changed=False))
    status('complete',selected=result['selected'])
    print(json.dumps(dict(complete=True,selected=result['selected'],outer={n:{k:s[k] for k in ['accuracy','macro_f1']} for n,s in result['methods'].items()})),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    torch.set_num_threads(4);lock_process();p=prepare()
    if not args.prepare_only:run(p)


if __name__=='__main__':main()
