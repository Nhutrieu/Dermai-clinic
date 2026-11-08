"""Matched auxiliary not-SkinCancer supervision on jointly audited PAD NEV/SEK.

Both arms share every main/negative image and augmented input; only lambda0/1
differs. Negative loss is summed and divided by main batch size. Negative eval
forwards keep BN/dropout statistics fixed while allowing gradients.
"""
import argparse
import hashlib
import json
import time
from collections import Counter

import numpy as np
import torch
from torch.nn import functional as F
from torch.utils.data import DataLoader,Dataset
from PIL import Image
from sklearn.metrics import accuracy_score,f1_score

from common import CLASSES,ImageSampleDataset,save_json,sha256_file,build_model,seed_everything
import pilot_original_eight_pad_addition as previous
import prepare_original_eight_pad_joint as joint

ROOT=previous.ROOT
OUT=ROOT/'ai-service/reports/original_eight_negative_supervision_pilot_fold0_seed42_fp32'
MODELS=ROOT/'ai-service/candidates/original_eight_negative_supervision_pilot_fold0_seed42_fp32'
CONFIG=dict(previous.CONFIG,negative_slots_per_epoch=202,negative_coefficients=dict(control=0.,negative=1.),negative_seed_base=1840000,precision='float32')
BRANCHES=('control','negative')
METHODS=('old_classwise','control_resnet','control_mix25','negative_resnet','negative_mix25')


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def negative_weights(rr):
    patients={d:{r['source_patient_id'] for r in rr if r['source_label']==d} for d in ('NEV','SEK')}
    assert all(patients.values())
    count=Counter((r['source_label'],r['source_patient_id']) for r in rr)
    return torch.tensor([1/(2*len(patients[r['source_label']])*count[r['source_label'],r['source_patient_id']]) for r in rr],dtype=torch.float64)


def schedules(p,epoch):
    _,main,slots=previous.paired_draws(p,epoch)
    neg=torch.multinomial(negative_weights(p['negative']),202,True,generator=torch.Generator().manual_seed(6000+epoch)).tolist()
    return main,dict(zip(slots,neg))


class ContrastDataset(Dataset):
    def __init__(self,p,ids,negmap,epoch):
        self.main=ImageSampleDataset(previous.prior.samples(p['train']+p['supplement']+p['pad']),previous.prior.trainer.training_transform_v2())
        self.negative=p['negative']; self.transform=previous.prior.trainer.training_transform_v2()
        self.ids=ids; self.negmap=negmap; self.epoch=epoch
    def __len__(self): return len(self.ids)
    def __getitem__(self,position):
        with torch.random.fork_rng(devices=[]):
            torch.random.default_generator.manual_seed(840000+self.epoch*100000+position)
            x,y=self.main[self.ids[position]]
        isnegative=position in self.negmap
        if isnegative:
            with Image.open(ROOT/self.negative[self.negmap[position]]['path']) as im: image=im.convert('RGB')
            with torch.random.fork_rng(devices=[]):
                torch.random.default_generator.manual_seed(1840000+self.epoch*100000+position)
                nx=self.transform(image)
        else: nx=torch.zeros_like(x)
        return x,y,nx,isnegative


def complementary_loss(logits):
    z=logits.float(); other=torch.cat([z[:,:5],z[:,6:]],dim=1)
    # -log(1-softmax(z)[SkinCancer]), stable for probabilities near1.
    return F.softplus(z[:,5]-torch.logsumexp(other,dim=1))


def bn_state_hash(model):
    digest=hashlib.sha256()
    for name,x in model.named_buffers():
        if 'running_' in name or 'num_batches_tracked' in name:
            digest.update(name.encode()); digest.update(x.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def register():
    assert not (OUT/'protocol.json').exists(),'Preserve registered experiment'
    state=read(ROOT/'ai-service/reports/active_research_track.json'); assert state['active_track']=='original_eight'
    s=read(joint.OUT/'summary.json'); v=read(joint.OUT/'verification.json')
    assert v['status']=='PASS' and v['summary_sha256']==sha256_file(joint.OUT/'summary.json')
    base=read(previous.OUT/'protocol.json')
    assert read(previous.OUT/'verification.json')['status']=='PASS'
    pos=joint.prior.prior.entries(joint.OUT/'positive_train.jsonl'); neg=joint.prior.prior.entries(joint.OUT/'negative_train.jsonl')
    for r in pos+neg: assert sha256_file(ROOT/r['path'])==r['sha256'] and r['training_eligible']
    assert all(r['label'] is None and r['complementary_label']=='SkinCancer' and r['source_label'] in ('NEV','SEK') for r in neg)
    assert all(r['label']=='SkinCancer' and r['published_biopsed'] for r in pos)
    pad=[{k:r[k] for k in ('path','label','sha256','group','source','source_patient_id','source_label')} for r in pos]
    negative=[{k:r[k] for k in ('path','label','complementary_label','sha256','group','source','source_patient_id','source_label','published_biopsed')} for r in neg]
    assert {r['source_patient_id'] for r in pos+neg}.isdisjoint(r['patient'] for r in base['pad_validation'])
    paths=[joint.OUT/'protocol.json',joint.OUT/'summary.json',joint.OUT/'verification.json',joint.OUT/'positive_train.jsonl',joint.OUT/'negative_train.jsonl',
        previous.OUT/'protocol.json',previous.OUT/'verification.json',previous.OUT/'pad_validation.npz',OUT/'numerical_repair.json']
    frozen={**base['sources'],**{x.relative_to(ROOT).as_posix():sha256_file(x) for x in paths}}
    for path,h in frozen.items(): assert sha256_file(ROOT/path)==h,path
    p=dict(classes=CLASSES,configuration=CONFIG,train=base['train'],supplement=base['supplement'],pad=pad,negative=negative,
        splits=base['splits'],pad_validation=base['pad_validation'],parent_members=base['parent_members'],reference_weights=base['reference_weights'],
        initial_checkpoint_sha256=base['initial_checkpoint_sha256'],sources=frozen,numerical_repair='Preliminary AMPpilot had758vs759actual steps. FP32repair locked solely from update counters before reading scores; no recipe/weight/selection change.',
        code_sha256={n:sha256_file(ROOT/'ai-service/training'/n) for n in ('pilot_original_eight_negative_supervision_fp32.py','verify_original_eight_negative_supervision_fp32.py',
            'pilot_original_eight_pad_addition.py','verify_original_eight_pad_addition.py','pilot_original_eight_supplement_adaptation.py','pilot_original_eight_resnet50.py','common.py','train_v2.py','evaluate_scene_grouped_oof_ensemble.py')},
        training='Both reinitialize old fold0ResNet raw17, same seed42/AdamW/weights/AMP/clip2/fixed3epochs759steps, fullFP32/noGradScaler/noEMA/earlystop; finite gradient gate. Both same main4043replay draws with202balanced PADpositive replacements as previous. Both202balanced NEV/SEKnegative forwards/epoch. Only coefficient0or1differs.',
        loss='Original weighted smoothed CE on main batch plus lambda*sum(-log(1-pSkinCancer(negative)))/main_batch_size. Negative rows never have an8class CEtarget. Fixed coefficient1, no search. This redistributes mass away from SkinCancer; it is not an OODrejector or correct diagnosis for NEV/SEK.',
        negative_forward='Model.eval() during negative forward, gradients enabled; main forward in train(). BNstate hash before/after checked on first negative batch per epoch; dropout/BN disabled on all negative forwards in both arms. Control computes same negative graph/loss with lambda0.',
        augmentation='Full main x/y and real-negative augmented stream hashes equal between arms. Main seed840000+epoch*100000+position; negative1840000+epoch*100000+position, forked CPUtorchRNG.',
        family='Reference plus same fixed75%reference/25%ResNet mix for control/negative. No new ensemble weight/temperature and no label revisions.',
        selection=base['selection'],
        literature='https://arxiv.org/abs/1908.07387 ; equation2negative-loss idea only. NLNL uses random complementary labels to handle noisy closed-set labels; this project uses known fixed noncancer annotations from out-of-8scope images. No SelNL/SelPL or claim of full replication.',
        limits=base['limitations']+['NEV/SEKpublished labels are not all biopsy-confirmed; no new expert review.',
            'ACK omitted from negative loss, assessed separately. Parent checkpoint original validation was previously used for selection.',
            'Shared train patients across positive/negative lesions allowed, held patients remain disjoint.',
            'One tested loss variant; lack of independent confirmation persists.'])
    save_json(OUT/'protocol.json',p); return p


def train(branch,p):
    folder=MODELS/branch; assert not folder.exists(),'Preserve model outputs'; folder.mkdir(parents=True)
    seed_everything(42); cp=torch.load(previous.prior.INITIAL,map_location='cpu',weights_only=False)
    model=build_model('resnet50',8,pretrained=False); model.load_state_dict(cp['model_state_dict']); del cp; model.cuda()
    backbone,head=previous.prior.trainer.classifier_parameters(model)
    optimizer=torch.optim.AdamW([dict(params=backbone,lr=CONFIG['backbone_lr']),dict(params=head,lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    weights,counts=previous.prior.trainer.effective_number_weights(previous.prior.samples(p['train']),.999,torch.device('cuda'))
    criterion=torch.nn.CrossEntropyLoss(weight=weights,label_smoothing=.05); scaler=torch.amp.GradScaler('cuda',enabled=False)
    updates={'count':0}; step=optimizer.step
    def counted(*args,**kwargs):
        result=step(*args,**kwargs); updates['count']+=1; return result
    optimizer.step=counted; history=[]; coefficient=CONFIG['negative_coefficients'][branch]
    rr=p['train']+p['supplement']+p['pad']
    for epoch in range(1,4):
        ids,negmap=schedules(p,epoch)
        loader=DataLoader(ContrastDataset(p,ids,negmap,epoch),batch_size=16,shuffle=False,num_workers=2,pin_memory=True,generator=torch.Generator().manual_seed(1000+epoch))
        mainhash=hashlib.sha256(); neghash=hashlib.sha256(); before=updates['count']; started=time.monotonic(); targets=[]; predicted=[]; ces=[]; nls=[]; negative_count=0; checked=False
        model.train()
        for x,y,nx,mask in loader:
            mainhash.update(x.numpy().tobytes()); mainhash.update(y.numpy().tobytes()); neghash.update(nx[mask].numpy().tobytes())
            count=int(mask.sum()); negative_count+=count; optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',enabled=False): logits=model(x.cuda(non_blocking=True)); ce=criterion(logits,y.cuda(non_blocking=True))
            if count:
                model.eval(); before_bn=bn_state_hash(model) if not checked else None
                with torch.autocast('cuda',enabled=False): nz=model(nx[mask].cuda(non_blocking=True))
                nl=complementary_loss(nz).sum()/len(y)
                if not checked: assert before_bn==bn_state_hash(model); checked=True
                model.train()
            else: nl=torch.zeros((),device='cuda')
            loss=ce+coefficient*nl; scaler.scale(loss).backward(); scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(),2,error_if_nonfinite=True); scaler.step(optimizer); scaler.update()
            ces.extend([float(ce.detach())]*len(y)); nls.extend([float(nl.detach())]*len(y)); targets.extend(y.tolist()); predicted.extend(logits.detach().argmax(1).cpu().tolist())
        history.append(dict(epoch=epoch,coefficient=coefficient,ce=float(np.mean(ces)),complement_normalized_loss=float(np.mean(nls)),
            accuracy=float(accuracy_score(targets,predicted)),macro_f1=float(f1_score(targets,predicted,labels=np.arange(8),average='macro',zero_division=0)),
            attempted_updates=len(loader),actual_updates=updates['count']-before,negative_images_forwarded=negative_count,negative_bn_unchanged=checked,
            main_augmented_stream_sha256=mainhash.hexdigest(),negative_augmented_stream_sha256=neghash.hexdigest(),
            main_indices_sha256=hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest(),
            negative_mapping_sha256=hashlib.sha256(json.dumps(negmap,separators=(',',':')).encode()).hexdigest(),
            main_source_draws=dict(Counter(rr[i].get('source','original') for i in ids)),
            positive_subtype_draws=dict(Counter(rr[i]['source_label'] for i in ids if i>=4850)),
            negative_subtype_draws=dict(Counter(p['negative'][i]['source_label'] for i in negmap.values())),seconds=time.monotonic()-started))
        save_json(folder/'history.json',history)
        print(json.dumps({k:value for k,value in dict(branch=branch,**history[-1]).items() if 'sha256' not in k}),flush=True)
    checkpoint=folder/'final_model.pth'; torch.save(dict(model_state_dict=model.state_dict(),classes=CLASSES,architecture='resnet50',branch=branch,epoch=3,
        protocol_sha256=sha256_file(OUT/'protocol.json'),research_only=True),checkpoint)
    save_json(folder/'training_report.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),checkpoint_sha256=sha256_file(checkpoint),initial_checkpoint_sha256=p['initial_checkpoint_sha256'],
        epochs=3,coefficient=coefficient,actual_updates=updates['count'],class_counts=counts,class_weights=weights.cpu().tolist()))
    del model,optimizer,loader; torch.cuda.empty_cache()


def evaluate(p):
    from evaluate_scene_grouped_oof_ensemble import score
    vals={}; trials={n:dict(name=n) for n in ('old_classwise','control_mix25','negative_mix25')}
    for split in previous.prior.SPLITS[:2]:
        rr=p['splits'][split]; ref=previous.prior.baseline(split,rr)['old_classwise']; values=dict(old_classwise=ref)
        for b in BRANCHES:
            values[b+'_resnet']=previous.infer(MODELS/b/'final_model.pth','resnet50',rr); values[b+'_mix25']=previous.prior.combine(ref,values[b+'_resnet'])
        y=np.asarray([CLASSES.index(r['label']) for r in rr]); vals[split]=values
        for n,t in trials.items(): t[split]=score(values[n],y)
        np.savez_compressed(OUT/(split+'.npz'),paths=[r['path'] for r in rr],truth=y,**values)
    with np.load(previous.OUT/'pad_validation.npz') as z:
        assert z['paths'].tolist()==[r['path'] for r in p['pad_validation']]
        parents={n:z[n].copy() for n in ('efficientnet_b0','convnext_tiny')}; ref=z['old_classwise'].copy()
    pv=dict(old_classwise=ref)
    for b in BRANCHES:
        pv[b+'_resnet']=previous.infer(MODELS/b/'final_model.pth','resnet50',p['pad_validation']); pv[b+'_mix25']=previous.prior.combine(ref,pv[b+'_resnet'])
    padmetrics={n:previous.cancer_score(z,p['pad_validation']) for n,z in pv.items()}
    np.savez_compressed(OUT/'pad_validation.npz',paths=[r['path'] for r in p['pad_validation']],**parents,**pv)
    for n,t in trials.items():
        t['pad_validation']=padmetrics[n]; base=padmetrics['old_classwise']; item=padmetrics[n]
        t['eligible']=bool(previous.prior.eligible(t,trials['old_classwise']) and item['non_cancer_flag_rate']<=base['non_cancer_flag_rate']+1e-12
            and all(item['by_diagnosis'][d]['flag_rate']>=base['by_diagnosis'][d]['flag_rate']-1e-12 for d in ('BCC','SCC','MEL')))
    selected=sorted([t for t in trials.values() if t['eligible']],key=previous.prior.rank)[0]['name']
    save_json(OUT/'selection_locked.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),selected=selected,trials=list(trials.values()),checkpoint_sha256={b:sha256_file(MODELS/b/'final_model.pth') for b in BRANCHES}))
    results={}
    for split in previous.prior.SPLITS:
        rr=p['splits'][split]; y=np.asarray([CLASSES.index(r['label']) for r in rr])
        if split in vals: values=vals[split]
        else:
            values=dict(old_classwise=previous.prior.baseline(split,rr)['old_classwise'])
            for b in BRANCHES:
                values[b+'_resnet']=previous.infer(MODELS/b/'final_model.pth','resnet50',rr); values[b+'_mix25']=previous.prior.combine(values['old_classwise'],values[b+'_resnet'])
            np.savez_compressed(OUT/(split+'.npz'),paths=[r['path'] for r in rr],truth=y,**values)
        values['validation_selected']=values[selected]; results[split]={n:score(z,y) for n,z in values.items()}
    padmetrics['validation_selected']=padmetrics[selected]
    save_json(OUT/'results.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),selection_sha256=sha256_file(OUT/'selection_locked.json'),selected=selected,
        results=results,pad_validation=padmetrics,scope='Matched onefold/seed complementary-supervision pilot; previously investigated sources and validation, no new independent test.'))
    print(json.dumps(dict(complete=True,selected=selected,results={s:{n:{k:m[k] for k in ('accuracy','macro_f1')} for n,m in rr.items()} for s,rr in results.items()},pad_validation=padmetrics)),flush=True)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--prepare-only',action='store_true'); parser.add_argument('--resume',action='store_true'); args=parser.parse_args()
    p=read(OUT/'protocol.json') if args.resume else register()
    for n,h in p['code_sha256'].items(): assert sha256_file(ROOT/'ai-service/training'/n)==h
    torch.set_num_threads(4)
    if args.prepare_only: print('Registered matched complementary-supervision pilot.'); return
    assert torch.cuda.is_available() and not (OUT/'results.json').exists()
    for b in BRANCHES: train(b,p)
    evaluate(p)


if __name__=='__main__': main()
