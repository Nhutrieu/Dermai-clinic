"""Matched ensemble-teacher retention pilot on original-eight fold0.

Same supplemented draws/augmentations/teacher compute in both arms; only
KL weight differs0/.5. Fixed3epochs, teacher on original train images only.
"""
import argparse
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader,Subset,Dataset
from sklearn.metrics import classification_report

from common import CLASSES,ImageSampleDataset,build_model,evaluation_transform,save_json,sha256_file,seed_everything
import train_v2 as trainer
import pilot_original_eight_supplement_adaptation as previous

ROOT=Path(__file__).resolve().parents[2]
PRIOR=previous.OUT
OUT=ROOT/'ai-service/reports/original_eight_ensemble_teacher_pilot_fold0_seed42'
MODELS=ROOT/'ai-service/candidates/original_eight_ensemble_teacher_pilot_fold0_seed42'
BRANCHES=('control','distill')
CONFIG=dict(previous.CONFIG,temperature=2.,distillation_weights=dict(control=0.,distill=.5))
METHODS=('old_classwise','baseline_resnet','baseline_mix25','control_resnet','control_mix25','distill_resnet','distill_mix25','validation_selected')


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def tensor_state_hash(model):
    h=hashlib.sha256()
    for k,v in model.state_dict().items():
        h.update(k.encode());h.update(str(v.dtype).encode());h.update(str(tuple(v.shape)).encode());h.update(v.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def register():
    state=read(ROOT/'ai-service/reports/active_research_track.json'); assert state['active_track']=='original_eight' and state['classes']==CLASSES
    prior=read(PRIOR/'protocol.json'); v=read(PRIOR/'verification.json')
    assert v['status']=='PASS' and v['protocol_sha256']==sha256_file(PRIOR/'protocol.json')
    assert v['result_sha256']==sha256_file(PRIOR/'results.json')
    for name,h in prior['sources'].items(): assert sha256_file(ROOT/name)==h
    for rr in [prior['train'],prior['supplement'],*prior['splits'].values()]:
        for r in rr: assert sha256_file(ROOT/r['path'])==r['sha256']
    members=read(previous.TRANSFER/'protocol.json')['members']
    teachers=[m for m in members if m['fold']==0 and m['architecture'] in ('efficientnet_b0','convnext_tiny')]
    assert len(teachers)==2
    for m in teachers: assert sha256_file(ROOT/m['path'])==m['sha256']
    weights=read(previous.BASE/'selection_locked.json')['reference_weights']
    dependencies=('pilot_original_eight_ensemble_teacher.py','pilot_original_eight_supplement_adaptation.py',
        'pilot_original_eight_resnet50.py','common.py','train_v2.py','evaluate_scene_grouped_oof_classwise_fusion.py',
        'evaluate_scene_grouped_oof_ensemble.py','evaluate_new_ensemble_holdout.py')
    files=[PRIOR/'protocol.json',PRIOR/'verification.json',PRIOR/'results.json',previous.INITIAL,
        ROOT/'ai-service/reports/dermacon_distillation_matched_control.json',ROOT/'docs/48-giao-thuc-thich-nghi-co-distillation.md']
    sources=dict(prior['sources']);sources.update({p.relative_to(ROOT).as_posix():sha256_file(p) for p in files})
    sources.update({m['path']:m['sha256'] for m in teachers})
    p=dict(classes=CLASSES,configuration=CONFIG,train=prior['train'],supplement=prior['supplement'],splits=prior['splits'],
        initial_checkpoint_sha256=prior['initial_checkpoint_sha256'],teachers=teachers,teacher_classwise_weights=weights,
        sources=sources,code_sha256={n:sha256_file(ROOT/'ai-service/training'/n) for n in dependencies},
        training='Both fresh ResNet students load exact same original fold0 raw epoch17 checkpoint. Same supplemented90/10draws4043/epoch, augmentation stream seed1000+epoch, AdamW/loss weights/AMP/clip2/fixed3epochs as prior pilot. Both execute frozen teacher forwards and KL; only coefficient0/.5differs. No EMA/scheduler/early-stop or checkpoint choice.',
        teacher='Two frozen original fold0 B0/ConvNeXt checkpoints in eval+no_grad FP32; same augmented original image input as student. Classwise mix of untempered parent softmax probabilities using locked old inner weights, row normalize, then q^(1/T)renormalize atT2. T^2KL(q_T||student_softmax(z/T)), old images only. No teacher targets on clinical/atlas supplement.',
        loss='Weighted smoothed CE on whole batch +lambda*KD mean over original-image subset, lambda0or.5; no teacher labels on807auxiliary photos.',
        comparison='Matched control/teacher, including entire augmentation-input stream hashes per epoch and frozen teacher state hashes before/after. This is distinct from prior B0self-teacher/15%clinical/old892validation trial: ensemble teacher, ResNet student,10%807clinical+Lupusatlas, original grouped fold0.',
        family='Old classwise reference, fixed25%control or25%distilled ResNet. Raw student and initial25%reference formula descriptive only; no extra weight grid.',
        selection=prior['selection'],primary='Distillation effect versus matched zero-KL supplemented control on separate old/clinical validations. Only validation selects; exploratory one-fold held-role reporting follows selection lock.',
        literature=['https://arxiv.org/abs/1503.02531','https://arxiv.org/abs/1606.09282'],
        limitations=prior['limits']+['Ensemble-probability softening is a project variant, not an exact reproduction of either paper.',
          'Learning without Forgetting originally uses only new-task data; this pilot uses old-data replay and teacher on old data.',
          'Teacher can be wrong; retention does not certify clinical safety or improvement. No parameter adjustment after held-role outcomes.'])
    if (OUT/'protocol.json').exists(): assert read(OUT/'protocol.json')==p,'Preserve registered teacher pilot'
    else: save_json(OUT/'protocol.json',p)
    return p


class TaggedDataset(Dataset):
    def __init__(self,rr,n_old): self.base=ImageSampleDataset(previous.samples(rr),trainer.training_transform_v2());self.n_old=n_old
    def __len__(self): return len(self.base)
    def __getitem__(self,i):
        x,y=self.base[i];return x,y,i<self.n_old


def load_teacher(member):
    cp=torch.load(ROOT/member['path'],map_location='cpu',weights_only=False)
    assert cp['classes']==CLASSES and cp['architecture']==member['architecture']
    model=build_model(member['architecture'],8,pretrained=False);model.load_state_dict(cp['model_state_dict']);del cp
    return model.cuda().eval().requires_grad_(False)


def teacher_target(teachers,x,weights,temperature=2.):
    with torch.no_grad(),torch.autocast('cuda',enabled=False):
        a,b=[m(x.float()).softmax(1) for m in teachers]
        q=(1-weights)*a+weights*b;q=q/q.sum(1,keepdim=True)
        q=q.clamp_min(1e-12).pow(1/temperature);return q/q.sum(1,keepdim=True)


def train_branch(branch,p):
    directory=MODELS/branch
    if (directory/'training_report.json').exists():
        r=read(directory/'training_report.json');assert r['protocol_sha256']==sha256_file(OUT/'protocol.json') and r['checkpoint_sha256']==sha256_file(directory/'final_model.pth');return
    assert not directory.exists(),'Inspect partial branch; do not overwrite'
    directory.mkdir(parents=True);seed_everything(42)
    cp=torch.load(previous.INITIAL,map_location='cpu',weights_only=False)
    student=build_model('resnet50',8,pretrained=False);student.load_state_dict(cp['model_state_dict']);del cp;student.cuda()
    teachers=[load_teacher(m) for m in p['teachers']]
    assert [m['architecture'] for m in p['teachers']]==['efficientnet_b0','convnext_tiny']
    teacher_before=[tensor_state_hash(m) for m in teachers];backbone,head=trainer.classifier_parameters(student)
    optimizer=torch.optim.AdamW([dict(params=backbone,lr=CONFIG['backbone_lr']),dict(params=head,lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    weights,counts=trainer.effective_number_weights(previous.samples(p['train']),CONFIG['beta'],torch.device('cuda'))
    criterion=nn.CrossEntropyLoss(weight=weights,label_smoothing=CONFIG['label_smoothing']);scaler=torch.amp.GradScaler('cuda')
    update={'count':0};original_step=optimizer.step
    def counted_step(*args,**kwargs):
        result=original_step(*args,**kwargs);update['count']+=1;return result
    optimizer.step=counted_step; rr=p['train']+p['supplement'];dataset=TaggedDataset(rr,4043)
    blend_weights=torch.tensor(p['teacher_classwise_weights'],device='cuda',dtype=torch.float32);history=[];coefficient=CONFIG['distillation_weights'][branch]
    for epoch in range(1,4):
        ids=previous.draws('supplement',epoch);loader=DataLoader(Subset(dataset,ids),batch_size=16,shuffle=False,num_workers=2,pin_memory=True,generator=torch.Generator().manual_seed(1000+epoch))
        student.train();input_hash=hashlib.sha256();before=update['count'];began=time.monotonic();ce_losses=[];kd_losses=[];total_losses=[];targets=[];predicted=[];core_count=0
        for x,y,is_old in loader:
            input_hash.update(x.numpy().tobytes());input_hash.update(y.numpy().tobytes());input_hash.update(is_old.numpy().tobytes())
            x=x.cuda(non_blocking=True);y=y.cuda(non_blocking=True);is_old=is_old.cuda(non_blocking=True);optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',enabled=scaler.is_enabled()):
                logits=student(x);ce=criterion(logits,y)
            if bool(is_old.any()):
                q=teacher_target(teachers,x[is_old],blend_weights,CONFIG['temperature'])
                kd=F.kl_div(F.log_softmax(logits[is_old].float()/CONFIG['temperature'],dim=1),q,reduction='batchmean')*CONFIG['temperature']**2
            else: kd=logits.float().sum()*0
            loss=ce+coefficient*kd;scaler.scale(loss).backward();scaler.unscale_(optimizer);torch.nn.utils.clip_grad_norm_(student.parameters(),2.);scaler.step(optimizer);scaler.update()
            ce_losses.append(float(ce.detach()));kd_losses.append(float(kd.detach()));total_losses.append(float(loss.detach()));core_count+=int(is_old.sum())
            targets.extend(y.cpu().tolist());predicted.extend(logits.argmax(1).detach().cpu().tolist())
        metrics=classification_report(targets,predicted,labels=list(range(8)),target_names=CLASSES,output_dict=True,zero_division=0)
        h=dict(epoch=epoch,loss=float(np.mean(total_losses)),cross_entropy=float(np.mean(ce_losses)),distillation=float(np.mean(kd_losses)),
            accuracy=metrics['accuracy'],macro_f1=metrics['macro avg']['f1-score'],attempted_updates=len(loader),actual_updates=update['count']-before,
            source_draws=dict(Counter(rr[j].get('source','original') for j in ids)),teacher_images=core_count,
            sample_indices_sha256=hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest(),augmentation_stream_sha256=input_hash.hexdigest(),seconds=time.monotonic()-began)
        history.append(h);save_json(directory/'history.json',history);print(json.dumps(dict(branch=branch,**h)),flush=True);del loader
    teacher_after=[tensor_state_hash(m) for m in teachers];assert teacher_before==teacher_after and all(not m.training and all(not q.requires_grad for q in m.parameters()) for m in teachers)
    torch.save(dict(model_state_dict=student.state_dict(),architecture='resnet50',classes=CLASSES,epoch=3,branch=branch,protocol_sha256=sha256_file(OUT/'protocol.json'),initial_checkpoint_sha256=p['initial_checkpoint_sha256'],research_only=True),directory/'final_model.pth')
    save_json(directory/'training_report.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),initial_checkpoint_sha256=p['initial_checkpoint_sha256'],branch=branch,configuration=CONFIG,coefficient=coefficient,epochs=3,
        actual_updates=update['count'],attempted_updates=759,class_counts=counts,class_weights=weights.cpu().tolist(),checkpoint_sha256=sha256_file(directory/'final_model.pth'),teacher_state_before=teacher_before,teacher_state_after=teacher_after,teacher_frozen=True))
    del student,teachers,optimizer;torch.cuda.empty_cache()


def infer(branch,rr):
    cp=torch.load(MODELS/branch/'final_model.pth',map_location='cpu',weights_only=False);assert cp['classes']==CLASSES and cp['protocol_sha256']==sha256_file(OUT/'protocol.json')
    m=build_model('resnet50',8,pretrained=False);m.load_state_dict(cp['model_state_dict']);m.cuda().eval()
    loader=trainer.make_loader(ImageSampleDataset(previous.samples(rr),evaluation_transform()),16,False,2,True);values=[]
    with torch.inference_mode():
        for x,_ in loader:values.append(m(x.cuda(non_blocking=True)).softmax(1).cpu().numpy())
    del m,cp,loader;torch.cuda.empty_cache();return np.concatenate(values).astype(float)


def evaluate(p):
    validation={};trials={n:dict(name=n) for n in ('old_classwise','control_mix25','distill_mix25')}
    for name in previous.SPLITS[:2]:
        rr=p['splits'][name];base=previous.baseline(name,rr);ref=base['old_classwise'];values=dict(old_classwise=ref,baseline_resnet=base['resnet50'],baseline_mix25=previous.combine(ref,base['resnet50']))
        for b in BRANCHES:values[b+'_resnet']=infer(b,rr);values[b+'_mix25']=previous.combine(ref,values[b+'_resnet'])
        y=np.asarray([CLASSES.index(r['label']) for r in rr])
        for k,t in trials.items():t[name]=previous.score(values[k],y)
        np.savez_compressed(OUT/f'{name}.npz',paths=[r['path'] for r in rr],truth=y,**values);validation[name]=values
    for t in trials.values():t['eligible']=bool(previous.eligible(t,trials['old_classwise']))
    selected=sorted([t for t in trials.values() if t['eligible']],key=previous.rank)[0]['name']
    lock=dict(protocol_sha256=sha256_file(OUT/'protocol.json'),selected=selected,trials=list(trials.values()),checkpoint_sha256={b:read(MODELS/b/'training_report.json')['checkpoint_sha256'] for b in BRANCHES})
    if (OUT/'selection_locked.json').exists():assert read(OUT/'selection_locked.json')==lock
    else:save_json(OUT/'selection_locked.json',lock)
    results={};predictions=[]
    for name in previous.SPLITS:
        rr=p['splits'][name];y=np.asarray([CLASSES.index(r['label']) for r in rr])
        if name in validation:values=validation[name]
        else:
            base=previous.baseline(name,rr);ref=base['old_classwise'];values=dict(old_classwise=ref,baseline_resnet=base['resnet50'],baseline_mix25=previous.combine(ref,base['resnet50']))
            for b in BRANCHES:values[b+'_resnet']=infer(b,rr);values[b+'_mix25']=previous.combine(ref,values[b+'_resnet'])
            np.savez_compressed(OUT/f'{name}.npz',paths=[r['path'] for r in rr],truth=y,**values)
        values['validation_selected']=values[selected];results[name]={k:previous.score(v,y) for k,v in values.items()}
        predictions.extend(dict(**r,split=name,probabilities={k:v[j].tolist() for k,v in values.items()}) for j,r in enumerate(rr))
    save_json(OUT/'predictions.json',predictions);save_json(OUT/'results.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),selection_sha256=sha256_file(OUT/'selection_locked.json'),selected=selected,results=results,scope='Matched ensemble-teacher exploratory original fold0, retained previously-inspected source roles; not full5fold/independent confirmation.'))
    print(json.dumps(dict(complete=True,selected=selected,results={s:{k:{f:v[f] for f in ('accuracy','macro_f1')} for k,v in mm.items()} for s,mm in results.items()})),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args();torch.set_num_threads(4);p=register()
    if args.prepare_only:print(json.dumps(dict(registered=True,configuration=CONFIG,teachers=[m['architecture'] for m in p['teachers']])),flush=True);return
    assert torch.cuda.is_available() and not (OUT/'results.json').exists(),'Preserve completed teacher pilot'
    for b in BRANCHES:train_branch(b,p)
    evaluate(p)


if __name__=='__main__':main()
