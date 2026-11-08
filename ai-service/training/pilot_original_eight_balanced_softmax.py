"""Matched fold0 CE/Balanced Softmax continuation; retain current fusion fallback.

No labels/images edited. Three fixed epochs from the same original ResNet.
Common validation uses raw logits; Balanced Softmax adjustment is train-only.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F
from torch.utils.data import Subset

from common import CLASSES,ImageSample,ImageSampleDataset,build_model,evaluation_transform,seed_everything
import train_v2 as trainer
import evaluate_original_eight_cancer_locked_fusion as fusion

ROOT=Path(__file__).resolve().parents[2]
NAME='original_eight_balanced_softmax_pilot_fold0_seed42_20261021'
OUT=ROOT/'ai-service/reports'/NAME
MODELS=ROOT/'ai-service/candidates'/NAME
AUDIT=ROOT/'ai-service/reports/original_eight_weak_train_audit_20261021'
PARENT=ROOT/'ai-service/candidates/original_eight_resnet50_pilot_fold0_seed42/best_model.pth'
PARENT_REPORT=ROOT/'ai-service/reports/original_eight_resnet50_pilot_fold0_seed42'
CURRENT=fusion.OUT
BRANCHES=['ce','balanced_softmax']
CONFIG=dict(seed=42,epochs=3,batch_size=16,workers=0,backbone_lr=1e-5,head_lr=5e-5,
    weight_decay=.0002,ema_decay=.5,label_smoothing=0,precision='FP32',torch_threads=4)
LOCK_HANDLE=None


def status(state,**kwargs):
    fusion.write(OUT/'status.json',dict(state=state,pid=os.getpid(),updated_unix=time.time(),**kwargs))


def lock_process():
    global LOCK_HANDLE
    import msvcrt
    OUT.mkdir(parents=True,exist_ok=True)
    handle=(OUT/'runner.lock').open('a+b')
    if handle.tell()==0:handle.write(b'0');handle.flush()
    handle.seek(0)
    try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        handle.close();raise RuntimeError('Another balanced-softmax pilot is running')
    LOCK_HANDLE=handle


class BalancedSoftmax(torch.nn.Module):
    def __init__(self,counts):
        super().__init__()
        counts=torch.as_tensor(counts,dtype=torch.float32)
        if counts.shape!=(8,) or not torch.isfinite(counts).all() or (counts<=0).any():
            raise ValueError('Expected eight positive train-only counts')
        self.register_buffer('log_counts',counts.log())

    def forward(self,logits,targets):
        return F.cross_entropy(logits.float()+self.log_counts[None,:],targets)


def objects(rows):
    return [ImageSample(ROOT/r['path'],CLASSES.index(r['label']),r['sha256'],r['group']) for r in rows]


def register():
    if (OUT/'protocol.json').exists():
        protocol=fusion.read(OUT/'protocol.json');verify_sources(protocol);return protocol
    assert fusion.read(AUDIT/'verification.json')['status']=='PASS'
    assert fusion.read(CURRENT/'independent_review.json')['status']=='PASS'
    inventory={r['path']:r for r in fusion.read(AUDIT/'image_inventory.json')}
    roles=fusion.read(fusion.CV/'protocol.json')['folds'][0]['roles']
    rows={role:[dict(path=p,label=inventory[p]['label'],sha256=inventory[p]['sha256'],group=inventory[p]['group']) for p in paths] for role,paths in roles.items()}
    assert [len(rows[r]) for r in ['train','inner_validation','outer_holdout']]==[4043,718,1176]
    assert all(set(CLASSES)=={r['label'] for r in values} for values in rows.values())
    groups={role:{r['group'] for r in values} for role,values in rows.items()}
    for a,b in [('train','inner_validation'),('train','outer_holdout'),('inner_validation','outer_holdout')]:assert groups[a].isdisjoint(groups[b])
    counts=Counter(r['label'] for r in rows['train'])
    files=[PARENT,AUDIT/'summary.json',AUDIT/'verification.json',AUDIT/'image_inventory.json',AUDIT/'protocol.json',
        CURRENT/'protocol.json',CURRENT/'results.json',CURRENT/'fold_0/selection_locked.json',CURRENT/'independent_review.json',
        PARENT_REPORT/'validation_predictions.npz',PARENT_REPORT/'selection_locked.json',PARENT_REPORT/'test_predictions.json',
        fusion.MANIFEST,ROOT/'ai-service/models/best_model.pth']
    dependencies=['pilot_original_eight_balanced_softmax.py','common.py','train_v2.py','evaluate_original_eight_cancer_locked_fusion.py']
    protocol=dict(name=NAME,date='2026-10-21',classes=CLASSES,fold=0,roles=rows,configuration=CONFIG,
        train_class_counts={c:counts[c] for c in CLASSES},
        source_sha256={p.relative_to(ROOT).as_posix():fusion.sha(p) for p in files},
        code_sha256={name:fusion.sha(ROOT/'ai-service/training'/name) for name in dependencies},
        loss='CE(raw logits,y) versus CE(raw logits+log(train_counts),y), zero smoothing and no class weight in both. Original counts, no oversampling. This compares the addition of log-counts, not a complete reproduction of Balanced Meta-Softmax/meta-sampler.',
        literature=['https://arxiv.org/abs/2007.10740','https://github.com/jiawei-ren/BalancedMetaSoftmax-Classification/blob/main/loss/BalancedSoftmaxLoss.py'],
        initialization='Exact same original eight-class ResNet50 fold0 checkpoint. Fresh identical AdamW and EMA per branch.',
        exposure='Each epoch visits each train image exactly once in randperm order seeded42+epoch, no replacement. Reset Python/NumPy/Torch seeds at epoch start; save actual augmentation hashes in both branches.',
        precision='FP32 train/eval, finite loss and gradient checks, actual updates must equal batches.',
        checkpoint_selection='Fixed final epoch3. Select raw or EMA by inner-validation MacroF1, prefer raw on exact tie. No best-epoch search. Validation common plain CE; inference is raw-logit softmax, no log-count adjustment.',
        fusion='For each final branch learn protected classes using the frozen cancer-locked fusion algorithm on inner validation, then blend75% original B0/ConvNeXt reference+25% branch ResNet. The exact SkinCancer decision mask stays fixed.',
        guard='Compare inner candidate with current validation-selected fusion: Accuracy/MacroF1 must not decline, same SkinCancer precision/recall, nonfocus recall loss<=.02, target precision loss<=.02. Additionally Lupus F1 and mean F1 of Lupus/Psoriasis/Tinea cannot decline.',
        selection='Among passed current/CE/BS candidates choose MacroF1, mean targetF1, Accuracy, prefer current on tie. For Balanced Softmax to be eligible, MacroF1 and mean targetF1 must also be at least CE on validation. Lock before outer inference.',
        expansion='Onefold pilot only. No automatic fivefold expansion or change to the5937-image current score. Report both branches and fallback regardless of outcome.',
        limitations=['Exploratory existing development fold/labels; parent/current checkpoints already used inner validation.',
            'Source differential ties remain unchanged; this loss cannot confirm uncertain diagnoses or add new patients.',
            'Single seed, one fold, three-epoch continuation from a previously trained model; failure does not rule out Balanced Softmax from fresh initialization.',
            'No Word, API or serving checkpoint change. This pilot cannot replace the full fivefold78.68%/77.24% result.'])
    fusion.write(OUT/'protocol.json',protocol);status('registered',epochs=3,branches=BRANCHES)
    return protocol


def verify_sources(protocol):
    for relative,expected in protocol['source_sha256'].items():assert fusion.sha(ROOT/relative)==expected,relative
    for name,expected in protocol['code_sha256'].items():assert fusion.sha(ROOT/'ai-service/training'/name)==expected,name


def infer(model,rows):
    loader=trainer.make_loader(ImageSampleDataset(objects(rows),evaluation_transform()),16,False,0,True)
    model.eval();blocks=[]
    with torch.inference_mode():
        for x,_ in loader:blocks.append(model(x.cuda()).float().softmax(1).cpu().numpy())
    return np.concatenate(blocks).astype(float)


def load_initial():
    checkpoint=torch.load(PARENT,map_location='cpu',weights_only=False)
    assert checkpoint['classes']==CLASSES and checkpoint['architecture']=='resnet50'
    model=build_model('resnet50',8,pretrained=False)
    model.load_state_dict(checkpoint['model_state_dict']);return model.cuda()


def atomic_save(value,path):
    temporary=path.with_suffix(path.suffix+'.partial')
    torch.save(value,temporary);os.replace(temporary,path)


def train_branch(branch,protocol):
    directory=MODELS/branch;directory.mkdir(parents=True,exist_ok=True)
    if (directory/'training_report.json').exists():
        report=fusion.read(directory/'training_report.json')
        assert report['protocol_sha256']==fusion.sha(OUT/'protocol.json')
        assert report['checkpoint_sha256']==fusion.sha(directory/'final_model.pth')
        return
    seed_everything(42);model=load_initial();ema=copy.deepcopy(model).eval().requires_grad_(False)
    backbone,head=trainer.classifier_parameters(model)
    optimizer=torch.optim.AdamW([dict(params=backbone,lr=CONFIG['backbone_lr']),dict(params=head,lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=3,eta_min=1e-6)
    criterion=torch.nn.CrossEntropyLoss() if branch=='ce' else BalancedSoftmax([protocol['train_class_counts'][c] for c in CLASSES]).cuda()
    validation_criterion=torch.nn.CrossEntropyLoss()
    train=protocol['roles']['train'];validation=protocol['roles']['inner_validation']
    dataset=ImageSampleDataset(objects(train),trainer.training_transform_v2())
    vloader=trainer.make_loader(ImageSampleDataset(objects(validation),evaluation_transform()),16,False,0,True)
    history=[];start=1;resume=directory/'resume_state.pth'
    if resume.exists():
        saved=torch.load(resume,map_location='cpu',weights_only=False)
        assert saved['protocol_sha256']==fusion.sha(OUT/'protocol.json')
        model.load_state_dict(saved['model']);ema.load_state_dict(saved['ema'])
        optimizer.load_state_dict(saved['optimizer']);scheduler.load_state_dict(saved['scheduler'])
        history=saved['history'];start=saved['epoch']+1
    for epoch in range(start,4):
        status('training',branch=branch,epoch=epoch,epochs_limit=3)
        seed_everything(42+epoch)
        indices=torch.randperm(len(train),generator=torch.Generator().manual_seed(42+epoch)).tolist()
        loader=trainer.make_loader(Subset(dataset,indices),16,False,0,True)
        augmentation_hash=hashlib.sha256();label_hash=hashlib.sha256()
        model.train();began=time.monotonic();updates=0;loss_sum=0
        for x,y in loader:
            augmentation_hash.update(x.numpy().tobytes());label_hash.update(y.numpy().tobytes())
            x=x.cuda();y=y.cuda();optimizer.zero_grad(set_to_none=True)
            logits=model(x);loss=criterion(logits,y)
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite training loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),max_norm=2,error_if_nonfinite=True)
            optimizer.step();updates+=1;loss_sum+=float(loss.detach())
        assert updates==len(loader)
        assert all(torch.isfinite(value).all() for value in model.state_dict().values() if value.is_floating_point())
        trainer.update_ema(ema,model,CONFIG['ema_decay'])
        raw=trainer.run_epoch(model,vloader,validation_criterion,torch.device('cuda'))
        averaged=trainer.run_epoch(ema,vloader,validation_criterion,torch.device('cuda'))
        scheduler.step()
        history.append(dict(epoch=epoch,training_loss=loss_sum/updates,actual_updates=updates,attempted_updates=len(loader),
            images_seen=len(indices),unique_images_seen=len(set(indices)),augmentation_sha256=augmentation_hash.hexdigest(),
            labels_sha256=label_hash.hexdigest(),validation_raw=raw,validation_ema=averaged,seconds=time.monotonic()-began))
        fusion.write(directory/'history.json',history)
        atomic_save(dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),epoch=epoch,model=model.state_dict(),ema=ema.state_dict(),
                         optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),history=history),resume)
        print(json.dumps(dict(branch=branch,epoch=epoch,raw_macro_f1=raw['macro_f1'],ema_macro_f1=averaged['macro_f1'],seconds=history[-1]['seconds'])),flush=True)
    final=history[-1];source='ema' if final['validation_ema']['macro_f1']>final['validation_raw']['macro_f1'] else 'raw'
    chosen=ema if source=='ema' else model
    atomic_save(dict(model_state_dict=chosen.state_dict(),architecture='resnet50',classes=CLASSES,protocol_sha256=fusion.sha(OUT/'protocol.json'),
                     epoch=3,branch=branch,selected_weights=source,research_only=True),directory/'final_model.pth')
    probabilities=infer(chosen,validation)
    fusion.write(directory/'inner_predictions.json',dict(paths=[r['path'] for r in validation],probabilities=probabilities.tolist()))
    fusion.write(directory/'training_report.json',dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),checkpoint_sha256=fusion.sha(directory/'final_model.pth'),
        classes=CLASSES,branch=branch,epochs=3,selected_weights=source,actual_updates=sum(row['actual_updates'] for row in history),
        attempted_updates=sum(row['attempted_updates'] for row in history),precision='FP32',outer_used_for_selection=False))
    del model,ema,optimizer,chosen;torch.cuda.empty_cache()


def mean_focus(score):return float(np.mean([score['per_class'][label]['f1'] for label in ['Lupus','Psoriasis','Tinea']]))


def choose(validation):
    reference=validation['current_fusion'];trials={}
    for name,score in validation.items():
        reasons=fusion.guard_failures(score,reference)
        if score['per_class']['Lupus']['f1']+1e-12<reference['per_class']['Lupus']['f1']:reasons.append('Lupus_f1')
        if mean_focus(score)+1e-12<mean_focus(reference):reasons.append('mean_focus_f1')
        if name=='balanced_softmax':
            if score['macro_f1']+1e-12<validation['ce']['macro_f1']:reasons.append('macro_f1_below_matched_CE')
            if mean_focus(score)+1e-12<mean_focus(validation['ce']):reasons.append('focus_f1_below_matched_CE')
        trials[name]=dict(metrics=score,guard_failures=reasons)
    eligible=[name for name in trials if not trials[name]['guard_failures']]
    selected=max(eligible,key=lambda name:(validation[name]['macro_f1'],mean_focus(validation[name]),validation[name]['accuracy'],name=='current_fusion'))
    return selected,trials


def run(protocol):
    verify_sources(protocol)
    if (OUT/'results.json').exists():raise FileExistsError('Preserve completed pilot')
    _,truth,reference,original=fusion.validation_arrays(0)
    if not (OUT/'parent_reproduction.json').exists():
        model=load_initial();actual=infer(model,protocol['roles']['inner_validation']);del model;torch.cuda.empty_cache()
        difference=float(np.abs(actual-original).max())
        assert difference<2e-6 and np.array_equal(actual.argmax(1),original.argmax(1))
        fusion.write(OUT/'parent_reproduction.json',dict(status='PASS',max_abs_difference=difference,images=718))
    for branch in BRANCHES:train_branch(branch,protocol)
    histories={branch:fusion.read(MODELS/branch/'history.json') for branch in BRANCHES}
    for epoch in range(3):
        for key in ['augmentation_sha256','labels_sha256','actual_updates','images_seen','unique_images_seen']:
            assert histories['ce'][epoch][key]==histories['balanced_softmax'][epoch][key],key
    parent_lock=fusion.read(CURRENT/'fold_0/selection_locked.json')
    current_protected=parent_lock['trials'][parent_lock['selected']]['spec']['protected']
    current_decisions=fusion.decide(reference,original,current_protected)
    validation={'current_fusion':fusion.metrics(current_decisions,truth)}
    assert validation['current_fusion']['confusion_matrix']==parent_lock['trials'][parent_lock['selected']]['metrics']['confusion_matrix']
    policies={'current_fusion':current_protected};trace={}
    for branch in BRANCHES:
        inner=fusion.read(MODELS/branch/'inner_predictions.json')
        assert inner['paths']==[r['path'] for r in protocol['roles']['inner_validation']]
        probabilities=np.array(inner['probabilities'])
        policies[branch],trace[branch]=fusion.learn_protected(reference,probabilities,truth)
        validation[branch]=fusion.metrics(fusion.decide(reference,probabilities,policies[branch]),truth)
    selected,trials=choose(validation)
    lock=dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),selected=selected,trials=trials,protected_classes=policies,
              protection_trace=trace,checkpoint_sha256={branch:fusion.sha(MODELS/branch/'final_model.pth') for branch in BRANCHES})
    path=OUT/'selection_locked.json'
    if path.exists():assert fusion.read(path)==lock
    else:fusion.write(path,lock)
    # First outer arrays/inference of this pilot follow the frozen decision.
    status('evaluating_outer',selected=selected)
    old=fusion.read(PARENT_REPORT/'test_predictions.json');expected={r['path']:r for r in protocol['roles']['outer_holdout']}
    assert set(expected)=={r['path'] for r in old}
    ordered=[expected[row['path']] for row in old]
    truth=np.array([CLASSES.index(row['label']) for row in old])
    outer_reference=np.array([row['probabilities']['old_classwise'] for row in old])
    outer_original=np.array([row['probabilities']['resnet50'] for row in old])
    predictions={'current_fusion':fusion.decide(outer_reference,outer_original,policies['current_fusion'])}
    raw_probabilities={}
    for branch in BRANCHES:
        checkpoint=torch.load(MODELS/branch/'final_model.pth',map_location='cpu',weights_only=False)
        model=build_model('resnet50',8,pretrained=False);model.load_state_dict(checkpoint['model_state_dict']);model.cuda()
        probabilities=infer(model,ordered);del model,checkpoint;torch.cuda.empty_cache()
        raw_probabilities[branch]=probabilities
        predictions[branch]=fusion.decide(outer_reference,probabilities,policies[branch])
    predictions['validation_selected']=predictions[selected]
    for values in predictions.values():assert np.array_equal(values==5,predictions['current_fusion']==5)
    rows=[dict(**row,fold=0,source='SCIN' if row['path'].startswith('SkinDisease/scin-v1/') else 'original_train',
        predictions={name:int(values[i]) for name,values in predictions.items()},
        raw_component_probabilities={'old_classwise':outer_reference[i].tolist(),'original_resnet50':outer_original[i].tolist(),
                                    **{branch:values[i].tolist() for branch,values in raw_probabilities.items()}}) for i,row in enumerate(ordered)]
    result=dict(status='complete_exploratory_onefold_pilot',classes=CLASSES,images=1176,fold=0,selected=selected,
        protocol_sha256=fusion.sha(OUT/'protocol.json'),selection_sha256=fusion.sha(path),
        methods={name:fusion.metrics(values,truth) for name,values in predictions.items()},
        raw_model_metrics={branch:fusion.metrics(probabilities.argmax(1),truth) for branch,probabilities in raw_probabilities.items()},
        per_source={source:{name:fusion.metrics(values[np.array([row['source']==source for row in rows])],truth[np.array([row['source']==source for row in rows])]) for name,values in predictions.items()} for source in ['original_train','SCIN']},
        global_5937_score_changed=False,serving_changed=False,limitations=protocol['limitations'])
    fusion.write(OUT/'outer_decisions.json',rows);fusion.write(OUT/'results.json',result)
    verify_sources(protocol)
    fusion.write(OUT/'verification.json',dict(status='PASS',scope='Technical consistency of matched exposure and frozen selection; not clinical validation',
        results_sha256=fusion.sha(OUT/'results.json'),images=1176,actual_updates_per_branch=[sum(row['actual_updates'] for row in histories[branch]) for branch in BRANCHES],
        matching_actual_augmentation_hashes=True,cancer_masks_preserved=True,global_5937_score_changed=False,serving_changed=False))
    status('complete',selected=selected,images=1176)
    print(json.dumps(dict(selected=selected,outer_results={name:{key:score[key] for key in ['accuracy','macro_f1']} for name,score in result['methods'].items()})),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    torch.set_num_threads(4)
    lock_process();protocol=register()
    if not args.prepare_only:
        assert torch.cuda.is_available();run(protocol)


if __name__=='__main__':main()
