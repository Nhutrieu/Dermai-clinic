"""Matched fold0pilot: replace5%old replay slots with audited PAD train cancer.

Same init, steps, original loss weights and per-slot augmentations. PAD is
subtype/patient balanced; existing807auxiliary draws remain unchanged. No
changes to source labels, SCIN supervision, architecture, KL or fusion weights.
"""
import argparse
import hashlib
import json
import math
import time
from collections import Counter

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from sklearn.metrics import accuracy_score, f1_score

from common import CLASSES, ImageSampleDataset, build_model, evaluation_transform, save_json, sha256_file, seed_everything
import pilot_original_eight_supplement_adaptation as prior
import prepare_original_eight_pad_supplement as audit
from evaluate_scene_grouped_oof_ensemble import score

ROOT=prior.ROOT
OUT=ROOT/'ai-service/reports/original_eight_pad_addition_pilot_fold0_seed42'
MODELS=ROOT/'ai-service/candidates/original_eight_pad_addition_pilot_fold0_seed42'
CONFIG=dict(prior.CONFIG,pad_replacement_slots=202,augmentation_seed_base=840000,
            pad_sampling='Equal BCC/SCC/MEL mass, equal patients within subtype, equal images within patient/subtype.')
BRANCHES=('control','pad')
METHODS=('old_classwise','control_resnet','control_mix25','pad_resnet','pad_mix25')


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def pad_weights(rr):
    patients={d:{r['source_patient_id'] for r in rr if r['source_label']==d} for d in ('BCC','SCC','MEL')}
    assert all(patients.values())
    count=Counter((r['source_label'],r['source_patient_id']) for r in rr)
    return torch.tensor([1/3/len(patients[r['source_label']])/count[r['source_label'],r['source_patient_id']] for r in rr],dtype=torch.float64)


def paired_draws(protocol,epoch):
    control=prior.draws('supplement',epoch)
    oldpositions=[i for i,j in enumerate(control) if j<4043]
    generator=torch.Generator().manual_seed(424200+epoch)
    order=torch.randperm(len(oldpositions),generator=generator).tolist()
    slots=sorted(oldpositions[i] for i in order[:202])
    selected=torch.multinomial(pad_weights(protocol['pad']),202,True,generator=torch.Generator().manual_seed(5000+epoch)).tolist()
    intervention=control.copy()
    for slot,index in zip(slots,selected): intervention[slot]=4850+index
    return control,intervention,slots


class PairedDataset(Dataset):
    def __init__(self,rr,ids,epoch,slots):
        self.base=ImageSampleDataset(prior.samples(rr),prior.trainer.training_transform_v2())
        self.ids=ids; self.epoch=epoch; self.slots=set(slots)
    def __len__(self): return len(self.ids)
    def __getitem__(self,position):
        # Isolate torchvision random draws per attempted sample; changing PAD
        # image dimensions cannot shift augmentation RNG for later replay slots.
        with torch.random.fork_rng(devices=[]):
            torch.random.default_generator.manual_seed(840000+self.epoch*100000+position)
            x,y=self.base[self.ids[position]]
        return x,y,position not in self.slots


def register():
    assert not (OUT/'protocol.json').exists(),'Preserve registered pilot'
    state=read(ROOT/'ai-service/reports/active_research_track.json'); assert state['active_track']=='original_eight'
    v=read(audit.OUT/'verification.json'); s=read(audit.OUT/'summary.json')
    assert v['status']=='PASS' and v['summary_sha256']==sha256_file(audit.OUT/'summary.json')
    assert sha256_file(audit.OUT/'training_candidates.jsonl')==s['manifest_sha256']
    pads=audit.prior.entries(audit.OUT/'training_candidates.jsonl')
    assert pads and all(r['training_eligible'] and r['label']=='SkinCancer' for r in pads)
    old=read(prior.OUT/'protocol.json')
    rr=[dict(path=r['path'],label=r['label'],sha256=r['sha256'],group=r['group'],source='PAD-UFES-20',source_patient_id=r['source_patient_id'],source_label=r['source_label']) for r in pads]
    with (audit.PAD/'metadata.csv').open(encoding='utf-8-sig',newline='') as f:
        import csv
        metadata={r['img_id']:r for r in csv.DictReader(f)}
    index={p.name:p for p in (audit.PAD/'images').rglob('*.png')}
    padval=[]
    for r in read(audit.INVENTORY/'reserved_pad_validation.json'):
        path=index[r['img_id']]; m=metadata[r['img_id']]
        assert m['diagnostic']==r['diagnostic'] and m['patient_id']==r['patient_id']
        padval.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha256_file(path),diagnostic=r['diagnostic'],patient=r['patient_id'],label='SkinCancer' if r['diagnostic'] in ('BCC','SCC','MEL') else None,group='PAD::'+r['patient_id']))
    assert len(padval)==447 and {r['source_patient_id'] for r in rr}.isdisjoint(r['patient'] for r in padval)
    for r in old['train']+old['supplement']+rr+padval: assert sha256_file(ROOT/r['path'])==r['sha256']
    paths=[audit.OUT/'protocol.json',audit.OUT/'summary.json',audit.OUT/'verification.json',audit.OUT/'training_candidates.jsonl',
        audit.INVENTORY/'reserved_pad_validation.json',prior.OUT/'protocol.json',prior.INITIAL,
        ROOT/state['benchmark']['report_path'],ROOT/state['serving_checkpoint']]
    parents=read(ROOT/'ai-service/reports/original_eight_ensemble_teacher_pilot_fold0_seed42/protocol.json')['teachers']
    frozen={**old['sources'],**{p.relative_to(ROOT).as_posix():sha256_file(p) for p in paths},**{m['path']:m['sha256'] for m in parents}}
    for path,h in frozen.items(): assert sha256_file(ROOT/path)==h,path
    protocol=dict(classes=CLASSES,configuration=CONFIG,train=old['train'],supplement=old['supplement'],pad=rr,
        splits=old['splits'],pad_validation=padval,initial_checkpoint_sha256=sha256_file(prior.INITIAL),
        reference_weights=read(prior.BASE/'selection_locked.json')['reference_weights'],
        parent_members=parents,
        sources=frozen,
        code_sha256={n:sha256_file(ROOT/'ai-service/training'/n) for n in ('pilot_original_eight_pad_addition.py','verify_original_eight_pad_addition.py','pilot_original_eight_supplement_adaptation.py','pilot_original_eight_resnet50.py','common.py','train_v2.py','evaluate_scene_grouped_oof_ensemble.py')},
        training='Same old-fold0raw17init, seed42, fresh AdamW/AMP, fixed3epochs759attempted updates; original4043effective-number CEweights/.05smoothing, same fixed LR/clip2/noEMA. Control original90%/existing807aux10%. Intervention replaces exactly202original-only positions/epoch with PAD, preserves all existingaux and other old identities.',
        augmentation='Same deterministic per-position seed840000+epoch*100000+position, forked CPUtorchRNG. Both arms retain identical augmented x/y bytes on nonreplacement slots; shared stream hash recorded per epoch. This stream differs from earlier worker-seed pilots, which are not reused as matched control.',
        family='Old reference and fixed75%reference/25%control or PADResNet; raw models descriptive. No new temperature/weights or selection on held scores.',
        selection='Apply original/DermaCon dual validation guard/rank from prior pilot, and each BCC/SCC/MEL PADvalidation recall >= reference, plus combined NEV/SEK/ACK SkinCancer false-positive rate <= reference. Reference fallback. Lock method and final3epoch checkpoints before any new held-role inference.',
        limitations=['One previously investigated fold/seed and previously viewed sources; no new independent confirmation.',
            'PAD validation reuses historical roles and has few melanoma images; no eight-class labels for ACK/NEV/SEK, report SkinCancer flag by subtype only.',
            'Data addition includes predefined subtype/patient sampling; cannot isolate unweighted image addition separately.',
            'Original/SCIN/atlas patient identity and label certainty remain limited. No source relabelling or serving changes.',
            'Control and intervention differ in202data slots, shared budget not additional updates.'])
    save_json(OUT/'protocol.json',protocol); return protocol


def train(branch,p):
    folder=MODELS/branch; assert not folder.exists(),'Preserve partial/completed model'
    folder.mkdir(parents=True); seed_everything(42)
    cp=torch.load(prior.INITIAL,map_location='cpu',weights_only=False)
    model=build_model('resnet50',8,pretrained=False); model.load_state_dict(cp['model_state_dict']); del cp; model.cuda()
    backbone,head=prior.trainer.classifier_parameters(model)
    optimizer=torch.optim.AdamW([dict(params=backbone,lr=CONFIG['backbone_lr']),dict(params=head,lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    weights,counts=prior.trainer.effective_number_weights(prior.samples(p['train']),.999,torch.device('cuda'))
    criterion=torch.nn.CrossEntropyLoss(weight=weights,label_smoothing=.05); scaler=torch.amp.GradScaler('cuda')
    actual={'count':0}; step=optimizer.step
    def counted(*args,**kwargs):
        z=step(*args,**kwargs); actual['count']+=1; return z
    optimizer.step=counted; rr=p['train']+p['supplement']+p['pad']; history=[]
    for ep in range(1,4):
        control,intervention,slots=paired_draws(p,ep); ids=control if branch=='control' else intervention
        loader=DataLoader(PairedDataset(rr,ids,ep,slots),batch_size=16,shuffle=False,num_workers=2,pin_memory=True,generator=torch.Generator().manual_seed(1000+ep))
        model.train(); digest=hashlib.sha256(); before=actual['count']; losses=[]; targets=[]; preds=[]; started=time.monotonic()
        for x,y,shared in loader:
            digest.update(x[shared].numpy().tobytes()); digest.update(y[shared].numpy().tobytes())
            x=x.cuda(non_blocking=True); y=y.cuda(non_blocking=True); optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',enabled=True): logits=model(x); loss=criterion(logits,y)
            scaler.scale(loss).backward(); scaler.unscale_(optimizer); torch.nn.utils.clip_grad_norm_(model.parameters(),2)
            scaler.step(optimizer); scaler.update(); losses.extend([float(loss.detach())]*len(y)); targets.extend(y.cpu().tolist()); preds.extend(logits.detach().argmax(1).cpu().tolist())
        history.append(dict(epoch=ep,loss=float(np.mean(losses)),accuracy=float(accuracy_score(targets,preds)),macro_f1=float(f1_score(targets,preds,labels=np.arange(8),average='macro',zero_division=0)),
            actual_updates=actual['count']-before,attempted_updates=len(loader),shared_augmented_stream_sha256=digest.hexdigest(),
            indices_sha256=hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest(),
            replaced_positions=slots,source_draws=dict(Counter(rr[i].get('source','original') for i in ids)),
            pad_subtype_draws=dict(Counter(rr[i]['source_label'] for i in ids if i>=4850)),seconds=time.monotonic()-started))
        save_json(folder/'history.json',history); print(json.dumps(dict(branch=branch,**history[-1])),flush=True)
    cp=folder/'final_model.pth'; torch.save(dict(model_state_dict=model.state_dict(),classes=CLASSES,architecture='resnet50',epoch=3,
        branch=branch,protocol_sha256=sha256_file(OUT/'protocol.json'),research_only=True),cp)
    save_json(folder/'training_report.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),checkpoint_sha256=sha256_file(cp),initial_checkpoint_sha256=p['initial_checkpoint_sha256'],
        actual_updates=actual['count'],class_weights=weights.cpu().tolist(),class_counts=counts,epochs=3))
    del model,optimizer,loader; torch.cuda.empty_cache()


def infer(checkpoint,architecture,rr):
    cp=torch.load(checkpoint,map_location='cpu',weights_only=False)
    model=build_model(architecture,8,pretrained=False); model.load_state_dict(cp['model_state_dict']); del cp; model.cuda().eval()
    samples=prior.samples([dict(r,label=r.get('label') or 'SkinCancer') for r in rr])
    loader=prior.trainer.make_loader(ImageSampleDataset(samples,evaluation_transform()),16,False,2,True); pp=[]
    with torch.inference_mode():
        for x,_ in loader: pp.append(model(x.cuda(non_blocking=True)).softmax(1).cpu().numpy())
    del model,loader; torch.cuda.empty_cache(); return np.concatenate(pp).astype(float)


def cancer_score(p,rr):
    flag=p.argmax(1)==CLASSES.index('SkinCancer'); by={}
    for d in ('BCC','SCC','MEL','ACK','NEV','SEK'):
        mask=np.asarray([r['diagnostic']==d for r in rr]); n=int(mask.sum())
        by[d]=dict(images=n,flagged=int(flag[mask].sum()),flag_rate=float(flag[mask].mean()) if n else None)
    neg=np.asarray([r['diagnostic'] in ('ACK','NEV','SEK') for r in rr])
    return dict(by_diagnosis=by,non_cancer_flag_rate=float(flag[neg].mean()),non_cancer_images=int(neg.sum()),non_cancer_flagged=int(flag[neg].sum()),
        scope='Argmax SkinCancer flag, not eight-class accuracy or fresh external validation.')


def evaluate(p):
    vals={}; trials={n:dict(name=n) for n in ('old_classwise','control_mix25','pad_mix25')}
    for split in prior.SPLITS[:2]:
        rr=p['splits'][split]; ref=prior.baseline(split,rr)['old_classwise']; values=dict(old_classwise=ref)
        for branch in BRANCHES:
            values[branch+'_resnet']=infer(MODELS/branch/'final_model.pth','resnet50',rr)
            values[branch+'_mix25']=prior.combine(ref,values[branch+'_resnet'])
        y=np.asarray([CLASSES.index(r['label']) for r in rr]); vals[split]=values
        for n,t in trials.items(): t[split]=score(values[n],y)
        np.savez_compressed(OUT/(split+'.npz'),paths=[r['path'] for r in rr],truth=y,**values)
    rr=p['pad_validation']; parents=[infer(ROOT/m['path'],m['architecture'],rr) for m in p['parent_members']]
    from evaluate_scene_grouped_oof_classwise_fusion import classwise_blend
    ref=classwise_blend(*parents,np.asarray(p['reference_weights'])); pv=dict(old_classwise=ref)
    for branch in BRANCHES:
        pv[branch+'_resnet']=infer(MODELS/branch/'final_model.pth','resnet50',rr)
        pv[branch+'_mix25']=prior.combine(ref,pv[branch+'_resnet'])
    padmetrics={n:cancer_score(z,rr) for n,z in pv.items()}
    np.savez_compressed(OUT/'pad_validation.npz',paths=[r['path'] for r in rr],efficientnet_b0=parents[0],convnext_tiny=parents[1],**pv)
    for n,t in trials.items():
        t['pad_validation']=padmetrics[n]
        ref=padmetrics['old_classwise']; item=padmetrics[n]
        t['eligible']=bool(prior.eligible(t,trials['old_classwise']) and item['non_cancer_flag_rate']<=ref['non_cancer_flag_rate']+1e-12
            and all(item['by_diagnosis'][d]['flag_rate']>=ref['by_diagnosis'][d]['flag_rate']-1e-12 for d in ('BCC','SCC','MEL')))
    selected=sorted([t for t in trials.values() if t['eligible']],key=prior.rank)[0]['name']
    save_json(OUT/'selection_locked.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),selected=selected,trials=list(trials.values()),
        checkpoint_sha256={b:sha256_file(MODELS/b/'final_model.pth') for b in BRANCHES}))
    results={}
    for split in prior.SPLITS:
        rr=p['splits'][split]; y=np.asarray([CLASSES.index(r['label']) for r in rr])
        if split in vals: values=vals[split]
        else:
            values=dict(old_classwise=prior.baseline(split,rr)['old_classwise'])
            for branch in BRANCHES:
                values[branch+'_resnet']=infer(MODELS/branch/'final_model.pth','resnet50',rr)
                values[branch+'_mix25']=prior.combine(values['old_classwise'],values[branch+'_resnet'])
            np.savez_compressed(OUT/(split+'.npz'),paths=[r['path'] for r in rr],truth=y,**values)
        values['validation_selected']=values[selected]; results[split]={n:score(z,y) for n,z in values.items()}
    padmetrics['validation_selected']=padmetrics[selected]
    save_json(OUT/'results.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),selection_sha256=sha256_file(OUT/'selection_locked.json'),selected=selected,
        results=results,pad_validation=padmetrics,scope='Matched onefold/seed data-addition pilot, previously viewed roles; no independent confirmation or deployment.'))
    print(json.dumps(dict(complete=True,selected=selected,results={s:{n:dict(accuracy=m['accuracy'],macro_f1=m['macro_f1']) for n,m in rr.items()} for s,rr in results.items()},pad_validation=padmetrics)),flush=True)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--prepare-only',action='store_true'); parser.add_argument('--resume',action='store_true'); args=parser.parse_args()
    p=read(OUT/'protocol.json') if args.resume else register()
    for n,h in p['code_sha256'].items(): assert sha256_file(ROOT/'ai-service/training'/n)==h
    torch.set_num_threads(4)
    if args.prepare_only: print('Registered matched PADaddition pilot.'); return
    assert torch.cuda.is_available() and not (OUT/'results.json').exists()
    for branch in BRANCHES: train(branch,p)
    evaluate(p)


if __name__=='__main__': main()
