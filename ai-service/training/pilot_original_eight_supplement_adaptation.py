"""Matched fixed-three-epoch fold0 ResNet adaptation, original-eight classes.

Control replay vs90% original replay/10% audited supplement. Fixed checkpoints,
fixed25% ResNet fusion; dual validation guard locks before new holdout inference.
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
from torch.utils.data import DataLoader,Subset

from common import CLASSES,ImageSample,ImageSampleDataset,build_model,evaluation_transform,save_json,sha256_file,seed_everything
import train_v2 as trainer
import pilot_original_eight_resnet50 as old
from evaluate_new_ensemble_holdout import read_new_samples
from evaluate_scene_grouped_oof_classwise_fusion import classwise_blend
from evaluate_scene_grouped_oof_ensemble import score
from prepare_scene_grouped_oof_inner_splits import checked_outer_rows,OUTPUT as INNER
from prepare_scene_grouped_oof_folds import OUTPUT as OUTER

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'ai-service/reports/original_eight_supplement_adaptation_pilot_fold0_seed42'
MODELS=ROOT/'ai-service/candidates/original_eight_supplement_adaptation_pilot_fold0_seed42'
SUP=ROOT/'ai-service/reports/original_eight_supplement_audit_20261013'
TRANSFER=ROOT/'ai-service/reports/original_eight_resnet_transfer_seed42'
BASE=ROOT/'ai-service/reports/original_eight_resnet50_pilot_fold0_seed42'
INITIAL=ROOT/'ai-service/candidates/original_eight_resnet50_pilot_fold0_seed42/best_model.pth'
DC=ROOT/'SkinDisease/sources/dermacon_in/holdout'
DC_SPLIT=ROOT/'SkinDisease/sources/dermacon_in/adaptation'
SD=ROOT/'SkinDisease/sources/skindisnet_v2/holdout'
CONFIG=dict(seed=42,epochs=3,batch_size=16,workers=2,backbone_lr=.00001,head_lr=.00005,
            weight_decay=.01,label_smoothing=.05,beta=.999,draws_per_epoch=4043,supplement_mass=.10)
SPLITS=('original_validation','dermacon_validation','original_outer','dermacon_official_test','skindisnet_transfer')
METHODS=('old_classwise','baseline_resnet','baseline_mix25','control_resnet','control_mix25','supplement_resnet','supplement_mix25','validation_selected')


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def rows(samples):
    return [dict(path=s.path.relative_to(ROOT).as_posix(),label=CLASSES[s.label],sha256=s.digest,group=s.group_id) for s in samples]


def samples(rr): return [ImageSample(ROOT/r['path'],CLASSES.index(r['label']),r['sha256'],r['group']) for r in rr]


def draws(branch,epoch,n_old=4043,n_aux=807):
    mass=0 if branch=='control' else CONFIG['supplement_mass']
    weights=torch.tensor([1/n_old]*n_old if not mass else [(1-mass)/n_old]*n_old+[mass/n_aux]*n_aux,dtype=torch.float64)
    return torch.multinomial(weights,CONFIG['draws_per_epoch'],replacement=True,generator=torch.Generator().manual_seed(42+epoch)).tolist()


def register():
    state=read(ROOT/'ai-service/reports/active_research_track.json'); assert state['active_track']=='original_eight' and state['classes']==CLASSES
    audit=read(SUP/'summary.json'); verification=read(SUP/'verification.json')
    assert verification['status']=='PASS' and verification['summary_sha256']==sha256_file(SUP/'summary.json') and audit['retained_images']==807
    rr=[json.loads(x) for x in (SUP/'training_candidates.jsonl').read_text(encoding='utf-8').splitlines()]
    assert sha256_file(SUP/'training_candidates.jsonl')==audit['training_manifest_sha256']
    aux=[dict(path=r['path'],label=r['label'],sha256=r['sha256'],group=r['image_group'],source=r['source']) for r in rr]
    for r in aux: assert sha256_file(ROOT/r['path'])==r['sha256'] and r['label'] in CLASSES
    outer,original,_=checked_outer_rows(); plan=read(INNER)['folds'][0]; initial_roles=read(BASE/'protocol.json')['roles']
    original_by_path={s.path.relative_to(ROOT).as_posix():s for s in original}
    train=rows([original_by_path[p] for p in initial_roles['train']]); split={
      'original_validation':rows([original_by_path[p] for p in plan['inner_validation_paths']]),
      'original_outer':rows([original_by_path[p] for p in sorted(initial_roles['outer_holdout'])])}
    for name,file in [('dermacon_validation','validation'),('dermacon_official_test','official_test')]: split[name]=rows(read_new_samples(DC,DC_SPLIT/f'{file}.csv')[0])
    split['skindisnet_transfer']=rows(read_new_samples(SD,SD/'labels_no_near.csv')[0])
    assert [len(train),len(aux)]+[len(split[k]) for k in SPLITS]==[4043,807,718,213,1176,183,723]
    train_paths={r['path'] for r in train+aux}; train_sha={r['sha256'] for r in train+aux}
    for rr in split.values(): assert train_paths.isdisjoint(r['path'] for r in rr) and train_sha.isdisjoint(r['sha256'] for r in rr)
    assert sha256_file(INITIAL)==read(BASE/'selection_locked.json')['checkpoint_sha256']
    assert read(TRANSFER/'verification.json')['status']=='PASS'
    frozen=[INITIAL,BASE/'protocol.json',BASE/'selection_locked.json',BASE/'validation_predictions.npz',BASE/'test_predictions.json',
            SUP/'summary.json',SUP/'verification.json',SUP/'training_candidates.jsonl',SUP/'protocol.json',
            TRANSFER/'protocol.json',TRANSFER/'verification.json',DC_SPLIT/'train.csv',DC_SPLIT/'validation.csv',DC_SPLIT/'official_test.csv',SD/'labels_no_near.csv',OUTER,INNER]
    frozen += [TRANSFER/f'fold_0_{a}.npz' for a in ('efficientnet_b0','convnext_tiny','resnet50')]
    dependencies=('pilot_original_eight_supplement_adaptation.py','pilot_original_eight_resnet50.py','common.py','train_v2.py',
        'evaluate_new_ensemble_holdout.py','evaluate_scene_grouped_oof_classwise_fusion.py','evaluate_scene_grouped_oof_ensemble.py','prepare_scene_grouped_oof_inner_splits.py')
    protocol=dict(classes=CLASSES,configuration=CONFIG,initial_checkpoint_sha256=sha256_file(INITIAL),train=train,supplement=aux,splits=split,
        sources={p.relative_to(ROOT).as_posix():sha256_file(p) for p in frozen},code_sha256={n:sha256_file(ROOT/'ai-service/training'/n) for n in dependencies},
        training='Both branches load exact same old-fold0 ResNet raw epoch17 state, seed42; fresh AdamW/scaler, full fine-tune3epochs, fixed LR, no EMA/scheduler/early-stop or checkpoint selection. Original train_v2 augmentation/clip2/AMP. Fixed original4043effective-number loss weights for both.',
        sampling='Replacement draws4043/epoch. Control original only; intervention probability mass90%original/10%807supplement. Torch float64 multinomial seed42+epoch; augmentation worker generator1000+epoch. Same attempted update budget253/epoch.',
        family='Original classwise reference plus fixed75%reference/25%control ResNet or supplemented ResNet; report raw initial/control/intervention and unchanged initial25%mix separately.',
        selection='Final epoch3 checkpoints. Eligible ensemble candidates must pass original pilot guard on original validation, and not decrease clinical validation MacroF1/SkinCancer recall/mean Candidiasis-Lupus-Tinea recall relative to original classwise reference. Reference fallback. Among eligible maximize average MacroF1 across two validations, mean clinical target recall, original mean Lupus/PsoriasisF1, then lower complexity/name. Lock before new holdout inference.',
        primary='Effect of supplemental data versus matched replay control on separate validations; selected original1176outer and183official clinical held-role measurements exploratory, not independent confirmation.',
        limits=['One previously explored fold, one seed, source/OOF outcomes already inspected.',
                'Published-case clinical held roles protected; atlas train photos lack patient IDs.',
                'DermaCon full986contains590supplemental train images and is not a holdout after adaptation.',
                'Official clinical test183has no Lupus and few SkinCancer cases; SkinDisNet only2classes.',
                'No redefinition of5937fullOOF, weight search on test, new-eight inputs or serving changes.'])
    if (OUT/'protocol.json').exists(): assert read(OUT/'protocol.json')==protocol,'Preserve registered pilot'
    else: save_json(OUT/'protocol.json',protocol)
    return protocol


def train_branch(branch,protocol):
    directory=MODELS/branch
    if (directory/'training_report.json').exists():
        d=read(directory/'training_report.json'); assert d['protocol_sha256']==sha256_file(OUT/'protocol.json') and d['checkpoint_sha256']==sha256_file(directory/'final_model.pth'); return
    assert not directory.exists(),'Inspect partial training; no automatic overwrite'
    directory.mkdir(parents=True); seed_everything(42)
    cp=torch.load(INITIAL,map_location='cpu',weights_only=False); assert cp['classes']==CLASSES and cp['architecture']=='resnet50'
    model=build_model('resnet50',8,pretrained=False); model.load_state_dict(cp['model_state_dict']); del cp; model.cuda()
    backbone,head=trainer.classifier_parameters(model)
    optimizer=torch.optim.AdamW([dict(params=backbone,lr=CONFIG['backbone_lr']),dict(params=head,lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    weights,counts=trainer.effective_number_weights(samples(protocol['train']),CONFIG['beta'],torch.device('cuda'))
    criterion=torch.nn.CrossEntropyLoss(weight=weights,label_smoothing=CONFIG['label_smoothing']); scaler=torch.amp.GradScaler('cuda')
    updates={'count':0}; step=optimizer.step
    def counted_step(*args,**kwargs):
        r=step(*args,**kwargs); updates['count']+=1; return r
    optimizer.step=counted_step
    rr=protocol['train']+(protocol['supplement'] if branch=='supplement' else [])
    dataset=ImageSampleDataset(samples(rr),trainer.training_transform_v2()); history=[]
    for epoch in range(1,4):
        ids=draws(branch,epoch); before=updates['count']; started=time.monotonic()
        loader=DataLoader(Subset(dataset,ids),batch_size=16,shuffle=False,num_workers=2,pin_memory=True,
                          generator=torch.Generator().manual_seed(1000+epoch))
        metrics=trainer.run_epoch(model,loader,criterion,torch.device('cuda'),optimizer,scaler)
        history.append(dict(epoch=epoch,train=metrics,attempted_updates=len(loader),actual_updates=updates['count']-before,
            source_draws=dict(Counter(rr[j].get('source','original') for j in ids)),
            sample_indices_sha256=hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest(),seconds=time.monotonic()-started))
        save_json(directory/'history.json',history); print(json.dumps(dict(branch=branch,**history[-1])),flush=True); del loader
    torch.save(dict(model_state_dict=model.state_dict(),classes=CLASSES,architecture='resnet50',epoch=3,branch=branch,
          protocol_sha256=sha256_file(OUT/'protocol.json'),initial_checkpoint_sha256=protocol['initial_checkpoint_sha256'],research_only=True),directory/'final_model.pth')
    save_json(directory/'training_report.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),initial_checkpoint_sha256=protocol['initial_checkpoint_sha256'],
        branch=branch,epochs=3,actual_updates=updates['count'],attempted_updates=3*math.ceil(4043/16),class_counts=counts,class_weights=weights.cpu().tolist(),
        checkpoint_sha256=sha256_file(directory/'final_model.pth'),configuration=CONFIG))
    del model,optimizer; torch.cuda.empty_cache()


def infer(branch,rr):
    cp=torch.load(MODELS/branch/'final_model.pth',map_location='cpu',weights_only=False)
    assert cp['classes']==CLASSES and cp['protocol_sha256']==sha256_file(OUT/'protocol.json')
    model=build_model('resnet50',8,pretrained=False); model.load_state_dict(cp['model_state_dict']); model.cuda().eval()
    loader=trainer.make_loader(ImageSampleDataset(samples(rr),evaluation_transform()),16,False,2,True); pp=[]
    with torch.inference_mode():
        for x,_ in loader: pp.append(model(x.cuda(non_blocking=True)).softmax(1).cpu().numpy())
    del model,cp,loader; torch.cuda.empty_cache(); return np.concatenate(pp).astype(float)


def baseline(split,rr):
    names=('efficientnet_b0','convnext_tiny','resnet50'); out={}
    if split=='original_validation':
        with np.load(BASE/'validation_predictions.npz') as p:
            assert p['paths'].tolist()==[r['path'] for r in rr]
            for n in names: out[n]=p[n]
    elif split=='original_outer':
        pp=read(BASE/'test_predictions.json'); assert [r['path'] for r in pp]==[r['path'] for r in rr]
        out={n:np.asarray([r['probabilities'][n] for r in pp]) for n in names}
    else:
        for n in names:
            with np.load(TRANSFER/f'fold_0_{n}.npz') as p:
                index={path:i for i,path in enumerate(p['paths'].tolist())}; out[n]=p['probabilities'][[index[r['path']] for r in rr]]
    out['old_classwise']=classwise_blend(out[names[0]],out[names[1]],np.asarray(read(BASE/'selection_locked.json')['reference_weights']))
    return out


def combine(reference,resnet):
    p=.75*reference+.25*resnet; return p/p.sum(1,keepdims=True)


def rank(trial):
    a,b=trial['original_validation'],trial['dermacon_validation']
    return (-(a['macro_f1']+b['macro_f1'])/2,-np.mean([b['per_class'][c]['recall'] for c in ('Candidiasis','Lupus','Tinea')]),
            -np.mean([a['per_class'][c]['f1'] for c in ('Lupus','Psoriasis')]),0 if trial['name']=='old_classwise' else 1,trial['name'])


def eligible(trial,reference):
    a,b=trial['original_validation'],trial['dermacon_validation']; clinical=reference['dermacon_validation']
    return (old.passes(a,reference['original_validation']) and b['macro_f1']>=clinical['macro_f1']-1e-12
            and b['per_class']['SkinCancer']['recall']>=clinical['per_class']['SkinCancer']['recall']-1e-12
            and np.mean([b['per_class'][c]['recall'] for c in ('Candidiasis','Lupus','Tinea')])>=np.mean([clinical['per_class'][c]['recall'] for c in ('Candidiasis','Lupus','Tinea')])-1e-12)


def evaluate(protocol):
    validations={}; trial_scores={n:dict(name=n) for n in ('old_classwise','control_mix25','supplement_mix25')}
    for split in SPLITS[:2]:
        rr=protocol['splits'][split]; p=baseline(split,rr); ref=p['old_classwise']
        values=dict(old_classwise=ref,baseline_resnet=p['resnet50'],baseline_mix25=combine(ref,p['resnet50']))
        for branch in ('control','supplement'):
            values[branch+'_resnet']=infer(branch,rr); values[branch+'_mix25']=combine(ref,values[branch+'_resnet'])
        y=np.asarray([CLASSES.index(r['label']) for r in rr])
        for n,t in trial_scores.items(): t[split]=score(values[n],y)
        np.savez_compressed(OUT/f'{split}.npz',paths=[r['path'] for r in rr],truth=y,**values); validations[split]=values
    for t in trial_scores.values(): t['eligible']=bool(eligible(t,trial_scores['old_classwise']))
    selected=sorted([t for t in trial_scores.values() if t['eligible']],key=rank)[0]['name']
    lock=dict(protocol_sha256=sha256_file(OUT/'protocol.json'),selected=selected,trials=list(trial_scores.values()),
              checkpoint_sha256={b:read(MODELS/b/'training_report.json')['checkpoint_sha256'] for b in ('control','supplement')})
    if (OUT/'selection_locked.json').exists(): assert read(OUT/'selection_locked.json')==lock
    else: save_json(OUT/'selection_locked.json',lock)
    results={}; predictions=[]
    for split in SPLITS:
        rr=protocol['splits'][split]; y=np.asarray([CLASSES.index(r['label']) for r in rr])
        if split in validations: values=validations[split]
        else:
            p=baseline(split,rr); ref=p['old_classwise']; values=dict(old_classwise=ref,baseline_resnet=p['resnet50'],baseline_mix25=combine(ref,p['resnet50']))
            for b in ('control','supplement'):
                values[b+'_resnet']=infer(b,rr); values[b+'_mix25']=combine(ref,values[b+'_resnet'])
            np.savez_compressed(OUT/f'{split}.npz',paths=[r['path'] for r in rr],truth=y,**values)
        values['validation_selected']=values[selected]
        results[split]={k:score(v,y) for k,v in values.items()}
        predictions.extend(dict(**r,split=split,probabilities={k:v[i].tolist() for k,v in values.items()}) for i,r in enumerate(rr))
    save_json(OUT/'predictions.json',predictions); save_json(OUT/'results.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),
          selection_sha256=sha256_file(OUT/'selection_locked.json'),selected=selected,results=results,scope='Matched exploratory original fold0 and already-inspected source held roles; not5fold or fresh external confirmation.'))
    print(json.dumps(dict(complete=True,selected=selected,results={s:{n:{k:m[k] for k in ('accuracy','macro_f1')} for n,m in v.items()} for s,v in results.items()})),flush=True)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--prepare-only',action='store_true'); args=parser.parse_args()
    torch.set_num_threads(4); protocol=register()
    if args.prepare_only: print(json.dumps(dict(registered=True,train=4043,supplement=807,configuration=CONFIG)),flush=True); return
    assert torch.cuda.is_available() and not (OUT/'results.json').exists(),'Preserve completed pilot'
    for b in ('control','supplement'): train_branch(b,protocol)
    evaluate(protocol)


if __name__=='__main__': main()
