"""Matched original-eight Psoriasis data pilot, unchanged per-epoch label counts.

Control: original train permutation. Treatment: replace exactly25% of its
Psoriasis positions with a fixed stream from321audited auxiliary photographs.
Common positions receive identical per-position augmentation seeds.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import random
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from common import CLASSES,ImageSampleDataset,evaluation_transform,seed_everything
import train_v2 as trainer
import evaluate_original_eight_cancer_locked_fusion as fusion
import pilot_original_eight_balanced_softmax as prior

ROOT=Path(__file__).resolve().parents[2]
NAME='original_eight_psoriasis_replay_pilot_fold0_seed42_20261021'
OUT=ROOT/'ai-service/reports'/NAME
MODELS=ROOT/'ai-service/candidates'/NAME
SUP=ROOT/'ai-service/reports/original_eight_psoriasis_supplement_20261021'
BRANCHES=['control','psoriasis_aux']
CONFIG=dict(seed=42,epochs=3,batch_size=16,workers=0,backbone_lr=1e-5,head_lr=5e-5,
    weight_decay=.0002,ema_decay=.5,label_smoothing=.05,effective_number_beta=.999,
    psoriasis_replacement_fraction=.25,precision='FP32',torch_threads=4)
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
        handle.close();raise RuntimeError('Another Psoriasis replay pilot is running')
    LOCK_HANDLE=handle


def draws(train,auxiliary,epoch):
    """Return equal-length streams with exactly matching labels at every position."""
    if epoch not in [1,2,3] or not auxiliary or any(row['label']!='Psoriasis' for row in auxiliary):
        raise ValueError('Expected epoch1..3 and auxiliary Psoriasis only')
    if any(row['label'] not in CLASSES for row in train):raise ValueError('Unknown original label')
    order=torch.randperm(len(train),generator=torch.Generator().manual_seed(42+epoch)).tolist()
    positions=[pos for pos,index in enumerate(order) if train[index]['label']=='Psoriasis']
    count=round(len(positions)*CONFIG['psoriasis_replacement_fraction'])
    if not count:raise ValueError('No replacement positions')
    ranked=torch.randperm(len(positions),generator=torch.Generator().manual_seed(1042+epoch)).tolist()
    replaced=sorted(positions[i] for i in ranked[:count])
    # A deterministic cycle covers every auxiliary photo before repeating it.
    required=3*count;stream=[];cycle=0
    while len(stream)<required:
        stream.extend(torch.randperm(len(auxiliary),generator=torch.Generator().manual_seed(2042+cycle)).tolist())
        cycle+=1
    selected=stream[(epoch-1)*count:epoch*count]
    treatment=order.copy()
    for position,index in zip(replaced,selected):treatment[position]=len(train)+index
    pool=train+auxiliary
    assert [pool[i]['label'] for i in order]==[pool[i]['label'] for i in treatment]
    return dict(control=order,psoriasis_aux=treatment,replaced_positions=replaced,auxiliary_indices=selected)


class SeededDrawDataset(Dataset):
    def __init__(self,base,indices,epoch):self.base=base;self.indices=indices;self.epoch=epoch
    def __len__(self):return len(self.indices)
    def __getitem__(self,position):
        # Restore caller RNG state; different image dimensions cannot shift later draws.
        python_state=random.getstate();numpy_state=np.random.get_state()
        try:
            with torch.random.fork_rng(devices=[]):
                seed=420000+self.epoch*10000+position
                random.seed(seed);np.random.seed(seed);torch.default_generator.manual_seed(seed)
                x,y=self.base[self.indices[position]]
        finally:
            random.setstate(python_state);np.random.set_state(numpy_state)
        return x,y,position


def verify_sources(protocol):
    for relative,expected in protocol['source_sha256'].items():assert fusion.sha(ROOT/relative)==expected,relative
    for name,expected in protocol['code_sha256'].items():assert fusion.sha(ROOT/'ai-service/training'/name)==expected,name


def register():
    if (OUT/'protocol.json').exists():
        protocol=fusion.read(OUT/'protocol.json');verify_sources(protocol);return protocol
    ready=fusion.read(SUP/'ready_for_training.json');review=fusion.read(SUP/'extended_review.json')
    assert review['status']=='PASS' and ready['new_psoriasis_images']==321
    source=ROOT/ready['final_manifest'];assert fusion.sha(source)==ready['final_manifest_sha256']
    auxiliary=[json.loads(line) for line in source.read_text(encoding='utf-8').splitlines()]
    assert len(auxiliary)==321 and all(row['source_partition']=='train' and row['label']=='Psoriasis' for row in auxiliary)
    assert all(row['role']=='auxiliary_train_only' and not row['evaluation_eligible'] for row in auxiliary)
    for row in auxiliary:assert fusion.sha(ROOT/row['path'])==row['sha256']
    inventory={row['path']:row for row in fusion.read(prior.AUDIT/'image_inventory.json')}
    paths=fusion.read(fusion.CV/'protocol.json')['folds'][0]['roles']
    roles={role:[dict(path=p,label=inventory[p]['label'],sha256=inventory[p]['sha256'],group=inventory[p]['group']) for p in values] for role,values in paths.items()}
    auxiliary=[dict(path=r['path'],label=r['label'],sha256=r['sha256'],group=r['image_group'],source=r['source']) for r in auxiliary]
    assert [len(roles[r]) for r in ['train','inner_validation','outer_holdout']]==[4043,718,1176]
    assert {row['path'] for row in auxiliary}.isdisjoint(inventory)
    assert {row['sha256'] for row in auxiliary}.isdisjoint(row['sha256'] for row in inventory.values())
    groups={role:{row['group'] for row in values} for role,values in roles.items()}
    groups['auxiliary']={row['group'] for row in auxiliary}
    for a,b in [('train','inner_validation'),('train','outer_holdout'),('inner_validation','outer_holdout'),('auxiliary','inner_validation'),('auxiliary','outer_holdout')]:assert groups[a].isdisjoint(groups[b])
    exposure=[draws(roles['train'],auxiliary,epoch) for epoch in range(1,4)]
    assert all(len(row['replaced_positions'])==160 for row in exposure)
    assert len({i for row in exposure for i in row['auxiliary_indices']})==321
    files=[source,SUP/'ready_for_training.json',SUP/'extended_review.json',SUP/'extended_review_protocol.json',
           SUP/'protocol.json',SUP/'training_candidates_final.jsonl',prior.PARENT,
           prior.AUDIT/'image_inventory.json',prior.PARENT_REPORT/'validation_predictions.npz',prior.PARENT_REPORT/'test_predictions.json',
           fusion.CV/'protocol.json',fusion.MANIFEST,fusion.BENCHMARK,fusion.SERVING,
           prior.CURRENT/'results.json',prior.CURRENT/'fold_0/selection_locked.json',prior.CURRENT/'independent_review.json']
    dependencies=['pilot_original_eight_psoriasis_replay.py','pilot_original_eight_balanced_softmax.py',
                  'evaluate_original_eight_cancer_locked_fusion.py','common.py','train_v2.py']
    protocol=dict(name=NAME,date='2026-10-21',classes=CLASSES,fold=0,configuration=CONFIG,roles=roles,auxiliary=auxiliary,
        source_sha256={p.relative_to(ROOT).as_posix():fusion.sha(p) for p in files},
        code_sha256={name:fusion.sha(ROOT/'ai-service/training'/name) for name in dependencies},
        source_manifest_sha256=ready['final_manifest_sha256'],auxiliary_pool_images=321,auxiliary_evaluation_eligible=False,
        sampling='Each branch4043draws/epoch and same labels per position. Control original permutation without replacement. Treatment replaces160of639Psoriasis positions per epoch with auxiliary images. Same shared3883positions;160auxiliary draws/epoch,480total,321unique auxiliary photos seen across3epochs.',
        augmentation='Each draw has seed420000+epoch*10000+position, CPU/Python/NumPy RNG restored after transformation. Verify actual shared-position augmentation hashes and all-position label hashes match.',
        optimization='Same exact original ResNet50 fold0 initialization, fresh identical AdamW, FP32, clip2finite gradients,3fixed epochs, cosine LR. Same effective-number class weights from original train4043and smoothing.05. Same per-epoch class counts, no new diagnosis labels or other807auxiliary images.',
        checkpoint_selection='Final epoch3raw/EMA chosen only by original inner MacroF1; raw wins tie. No best-epoch search.',
        fusion='Frozen75%original B0/ConvNeXt+25%branch ResNet decision fusion; learn protected masks on inner validation using existing monotone policy. SkinCancer mask unchanged.',
        guard='Compare current fusion: Accuracy/MacroF1 no decline, SkinCancer recall/precision exact, nonfocus recall loss<=.02, focus precision loss<=.02. LupusF1, PsoriasisF1, PsoriasisRecall and mean Lupus/Psoriasis/TineaF1 cannot decline.',
        data_effect='Treatment also needs MacroF1>=matched control and PsoriasisF1 strictly greater than matched control on inner validation. Otherwise cannot attribute an improvement to extra photos.',
        selection='Among passing current/control/treatment maximize MacroF1, PsoriasisF1, Accuracy, prefer current then control on exact tie. Lock before new outer inference.',
        scope='Onefold data pilot, not a fivefold experiment. Keep full5937-score78.68%/77.24%unchanged; no automatic expansion or deployment.',
        limitations=['Previously explored development fold; parents/current fusion used existing validation. Not independent clinical confirmation.',
            '321atlas photos from cached corrected source are not321new patients or newly doctor-confirmed diagnoses; patient IDs absent.',
            'Replacing25%of Psoriasis train positions controls compute and class exposure; does not test exhaustive training on the entire combined1128auxiliary pool.',
            'One seed, final3epoch continuation, train sources differ. A pilot cannot establish all8diseases improved.',
            'Do not use outer scores to reselect checkpoints, masks, replacement fraction or weights. No Word/API/checkpoint change.'])
    fusion.write(OUT/'protocol.json',protocol);status('registered',branches=BRANCHES,epochs=3,auxiliary_pool_images=321)
    return protocol


def train_branch(branch,protocol):
    directory=MODELS/branch;directory.mkdir(parents=True,exist_ok=True)
    if (directory/'training_report.json').exists():
        report=fusion.read(directory/'training_report.json')
        assert report['protocol_sha256']==fusion.sha(OUT/'protocol.json') and report['checkpoint_sha256']==fusion.sha(directory/'final_model.pth')
        return
    seed_everything(42);model=prior.load_initial();ema=copy.deepcopy(model).eval().requires_grad_(False)
    backbone,head=trainer.classifier_parameters(model)
    optimizer=torch.optim.AdamW([dict(params=backbone,lr=CONFIG['backbone_lr']),dict(params=head,lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=3,eta_min=1e-6)
    train=protocol['roles']['train'];auxiliary=protocol['auxiliary'];validation=protocol['roles']['inner_validation']
    class_weights,counts=trainer.effective_number_weights(prior.objects(train),CONFIG['effective_number_beta'],torch.device('cuda'))
    criterion=torch.nn.CrossEntropyLoss(weight=class_weights,label_smoothing=CONFIG['label_smoothing'])
    vcriterion=torch.nn.CrossEntropyLoss()
    base=ImageSampleDataset(prior.objects(train+auxiliary),trainer.training_transform_v2())
    vloader=trainer.make_loader(ImageSampleDataset(prior.objects(validation),evaluation_transform()),16,False,0,True)
    history=[];start=1;resume=directory/'resume_state.pth'
    if resume.exists():
        saved=torch.load(resume,map_location='cpu',weights_only=False);assert saved['protocol_sha256']==fusion.sha(OUT/'protocol.json')
        model.load_state_dict(saved['model']);ema.load_state_dict(saved['ema']);optimizer.load_state_dict(saved['optimizer']);scheduler.load_state_dict(saved['scheduler'])
        history=saved['history'];start=saved['epoch']+1
    for epoch in range(start,4):
        status('training',branch=branch,epoch=epoch,epochs_limit=3)
        seed_everything(42+epoch);plan=draws(train,auxiliary,epoch);indices=plan[branch];replaced=set(plan['replaced_positions'])
        loader=trainer.make_loader(SeededDrawDataset(base,indices,epoch),16,False,0,True)
        common_hash=hashlib.sha256();labels_hash=hashlib.sha256();loss_sum=0;updates=0;model.train();began=time.monotonic()
        for x,y,positions in loader:
            shared=np.array([int(p) not in replaced for p in positions])
            common_hash.update(x.numpy()[shared].tobytes());labels_hash.update(y.numpy().tobytes())
            x=x.cuda();y=y.cuda();optimizer.zero_grad(set_to_none=True)
            logits=model(x);loss=criterion(logits,y)
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),2,error_if_nonfinite=True)
            optimizer.step();updates+=1;loss_sum+=float(loss.detach())
        assert updates==len(loader)
        assert all(torch.isfinite(value).all() for value in model.state_dict().values() if value.is_floating_point())
        trainer.update_ema(ema,model,CONFIG['ema_decay'])
        raw=trainer.run_epoch(model,vloader,vcriterion,torch.device('cuda'))
        averaged=trainer.run_epoch(ema,vloader,vcriterion,torch.device('cuda'));scheduler.step()
        pool=train+auxiliary
        history.append(dict(epoch=epoch,training_loss=loss_sum/updates,actual_updates=updates,attempted_updates=len(loader),
            draws=len(indices),class_draw_counts=dict(Counter(pool[i]['label'] for i in indices)),
            shared_draws=len(indices)-len(replaced),auxiliary_draws=sum(i>=len(train) for i in indices),
            unique_main_images=len({i for i in indices if i<len(train)}),unique_auxiliary_images=len({i for i in indices if i>=len(train)}),
            auxiliary_indices=[i-len(train) for i in indices if i>=len(train)],
            draw_indices_sha256=hashlib.sha256(json.dumps(indices).encode()).hexdigest(),
            shared_augmentation_sha256=common_hash.hexdigest(),labels_sha256=labels_hash.hexdigest(),
            validation_raw=raw,validation_ema=averaged,seconds=time.monotonic()-began))
        fusion.write(directory/'history.json',history)
        prior.atomic_save(dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),epoch=epoch,model=model.state_dict(),ema=ema.state_dict(),optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),history=history),resume)
        print(json.dumps(dict(branch=branch,epoch=epoch,raw_macro_f1=raw['macro_f1'],ema_macro_f1=averaged['macro_f1'],auxiliary_draws=history[-1]['auxiliary_draws'],seconds=history[-1]['seconds'])),flush=True)
    source='ema' if history[-1]['validation_ema']['macro_f1']>history[-1]['validation_raw']['macro_f1'] else 'raw'
    chosen=ema if source=='ema' else model
    prior.atomic_save(dict(model_state_dict=chosen.state_dict(),architecture='resnet50',classes=CLASSES,protocol_sha256=fusion.sha(OUT/'protocol.json'),epoch=3,branch=branch,selected_weights=source,research_only=True),directory/'final_model.pth')
    probabilities=prior.infer(chosen,validation)
    fusion.write(directory/'inner_predictions.json',dict(paths=[r['path'] for r in validation],probabilities=probabilities.tolist()))
    fusion.write(directory/'training_report.json',dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),initial_checkpoint_sha256=fusion.sha(prior.PARENT),
        checkpoint_sha256=fusion.sha(directory/'final_model.pth'),classes=CLASSES,branch=branch,epochs=3,selected_weights=source,
        actual_updates=sum(row['actual_updates'] for row in history),attempted_updates=sum(row['attempted_updates'] for row in history),
        auxiliary_draws=sum(row['auxiliary_draws'] for row in history),unique_auxiliary_images_seen=len({i for row in history for i in row['auxiliary_indices']}),
        class_weights=class_weights.cpu().tolist(),class_counts=counts,precision='FP32',outer_used_for_selection=False))
    del model,ema,optimizer,chosen;torch.cuda.empty_cache()


def choose(validation):
    current=validation['current_fusion'];trials={}
    for name,score in validation.items():
        reasons=fusion.guard_failures(score,current)
        for label in ['Lupus','Psoriasis']:
            if score['per_class'][label]['f1']+1e-12<current['per_class'][label]['f1']:reasons.append(label+'_f1')
        if score['per_class']['Psoriasis']['recall']+1e-12<current['per_class']['Psoriasis']['recall']:reasons.append('Psoriasis_recall')
        if prior.mean_focus(score)+1e-12<prior.mean_focus(current):reasons.append('mean_focus_f1')
        if name=='psoriasis_aux':
            if score['macro_f1']+1e-12<validation['control']['macro_f1']:reasons.append('macro_f1_below_matched_control')
            if score['per_class']['Psoriasis']['f1']<=validation['control']['per_class']['Psoriasis']['f1']+1e-12:reasons.append('no_Psoriasis_f1_gain_vs_control')
        trials[name]=dict(metrics=score,guard_failures=reasons)
    eligible=[name for name in trials if not trials[name]['guard_failures']]
    selected=max(eligible,key=lambda name:(validation[name]['macro_f1'],validation[name]['per_class']['Psoriasis']['f1'],validation[name]['accuracy'],name=='current_fusion',name=='control'))
    return selected,trials


def evaluate(protocol):
    _,truth,reference,original=fusion.validation_arrays(0)
    parent_lock=fusion.read(prior.CURRENT/'fold_0/selection_locked.json')
    current_policy=parent_lock['trials'][parent_lock['selected']]['spec']['protected']
    validation={'current_fusion':fusion.metrics(fusion.decide(reference,original,current_policy),truth)}
    assert validation['current_fusion']['confusion_matrix']==parent_lock['trials'][parent_lock['selected']]['metrics']['confusion_matrix']
    policies={'current_fusion':current_policy};traces={}
    for branch in BRANCHES:
        inner=fusion.read(MODELS/branch/'inner_predictions.json');assert inner['paths']==[r['path'] for r in protocol['roles']['inner_validation']]
        probabilities=np.array(inner['probabilities']);policies[branch],traces[branch]=fusion.learn_protected(reference,probabilities,truth)
        validation[branch]=fusion.metrics(fusion.decide(reference,probabilities,policies[branch]),truth)
    selected,trials=choose(validation)
    lock=dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),selected=selected,trials=trials,protected_classes=policies,
        protection_trace=traces,checkpoint_sha256={b:fusion.sha(MODELS/b/'final_model.pth') for b in BRANCHES})
    path=OUT/'selection_locked.json'
    if path.exists():assert fusion.read(path)==lock
    else:fusion.write(path,lock)
    status('evaluating_outer',selected=selected)
    # Outer scores are read only after checkpoint/policy/branch selection is frozen.
    old=fusion.read(prior.PARENT_REPORT/'test_predictions.json');lookup={r['path']:r for r in protocol['roles']['outer_holdout']}
    assert set(lookup)=={r['path'] for r in old}
    ordered=[lookup[row['path']] for row in old];truth=np.array([CLASSES.index(row['label']) for row in ordered])
    reference=np.array([row['probabilities']['old_classwise'] for row in old]);original=np.array([row['probabilities']['resnet50'] for row in old])
    predictions={'current_fusion':fusion.decide(reference,original,policies['current_fusion'])};raw={}
    for branch in BRANCHES:
        cp=torch.load(MODELS/branch/'final_model.pth',map_location='cpu',weights_only=False)
        model=prior.build_model('resnet50',8,pretrained=False);model.load_state_dict(cp['model_state_dict']);model.cuda()
        raw[branch]=prior.infer(model,ordered);del model,cp;torch.cuda.empty_cache()
        predictions[branch]=fusion.decide(reference,raw[branch],policies[branch])
    predictions['validation_selected']=predictions[selected]
    for values in predictions.values():assert np.array_equal(values==5,predictions['current_fusion']==5)
    rows=[dict(**row,source='SCIN' if row['path'].startswith('SkinDisease/scin-v1/') else 'original_train',
        predictions={name:int(values[i]) for name,values in predictions.items()},
        raw_component_probabilities={'old_classwise':reference[i].tolist(),'original_resnet50':original[i].tolist(),**{branch:values[i].tolist() for branch,values in raw.items()}}) for i,row in enumerate(ordered)]
    result=dict(status='complete_exploratory_matched_psoriasis_data_pilot',classes=CLASSES,images=1176,fold=0,selected=selected,
        protocol_sha256=fusion.sha(OUT/'protocol.json'),selection_sha256=fusion.sha(path),
        methods={name:fusion.metrics(values,truth) for name,values in predictions.items()},
        raw_model_metrics={name:fusion.metrics(values.argmax(1),truth) for name,values in raw.items()},
        per_source={source:{name:fusion.metrics(values[np.array([r['source']==source for r in rows])],truth[np.array([r['source']==source for r in rows])]) for name,values in predictions.items()} for source in ['original_train','SCIN']},
        global_5937_score_changed=False,serving_changed=False,limitations=protocol['limitations'])
    fusion.write(OUT/'outer_decisions.json',rows);fusion.write(OUT/'results.json',result)
    return result


def run(protocol):
    assert not (OUT/'results.json').exists(),'Preserve completed pilot'
    verify_sources(protocol)
    if not (OUT/'parent_reproduction.json').exists():
        _,_,_,expected=fusion.validation_arrays(0);model=prior.load_initial()
        actual=prior.infer(model,protocol['roles']['inner_validation']);del model;torch.cuda.empty_cache()
        error=float(np.abs(actual-expected).max());assert error<2e-6 and np.array_equal(actual.argmax(1),expected.argmax(1))
        fusion.write(OUT/'parent_reproduction.json',dict(status='PASS',images=718,max_abs_difference=error))
    for branch in BRANCHES:train_branch(branch,protocol)
    history={branch:fusion.read(MODELS/branch/'history.json') for branch in BRANCHES}
    for epoch in range(3):
        for key in ['shared_augmentation_sha256','labels_sha256','class_draw_counts','actual_updates','draws','shared_draws']:
            assert history['control'][epoch][key]==history['psoriasis_aux'][epoch][key],key
        assert history['control'][epoch]['auxiliary_draws']==0
        assert history['psoriasis_aux'][epoch]['auxiliary_draws']==160
    assert len({i for row in history['psoriasis_aux'] for i in row['auxiliary_indices']})==321
    result=evaluate(protocol);verify_sources(protocol)
    fusion.write(OUT/'verification.json',dict(status='PASS',scope='Technical consistency and matched exposure; not clinical validation',
        results_sha256=fusion.sha(OUT/'results.json'),images=1176,actual_updates_each=759,
        shared_actual_augmentation_hashes_match=True,label_counts_and_positions_match=True,
        unique_auxiliary_images_seen=321,auxiliary_training_draws=480,cancer_decisions_preserved=True,global_5937_score_changed=False,serving_changed=False))
    status('complete',selected=result['selected'],images=1176)
    print(json.dumps(dict(selected=result['selected'],outer_results={name:{key:value[key] for key in ['accuracy','macro_f1']} for name,value in result['methods'].items()})),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    torch.set_num_threads(4);lock_process();protocol=register()
    if not args.prepare_only:
        assert torch.cuda.is_available();run(protocol)


if __name__=='__main__':main()
