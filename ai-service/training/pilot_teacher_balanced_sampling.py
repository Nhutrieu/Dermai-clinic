"""Matched uniform versus class-balanced image sampling, original eight labels.

Fold0 only. Both branches fine-tune layer4+fc with the same unweighted CE;
only the training image index generator differs. Never tune from outer errors.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import os
import time

import numpy as np
import torch
from torch.nn import functional as F
from torch.utils.data import WeightedRandomSampler

import pilot_teacher_partial_resnet as shared

base = shared.fusion
ROOT = base.ROOT
NAME = 'teacher_balanced_sampling_fold0_seed42_20261023'
OUT = ROOT/'ai-service/reports'/NAME
MODELS = ROOT/'ai-service/candidates'/NAME
BRANCHES = ['uniform', 'balanced_sampling']
CONFIG = dict(seed=42, epochs=6, batch_size=16, workers=0, layer4_lr=1e-5, head_lr=5e-5,
    weight_decay=.0002, gradient_clip=2., label_smoothing=0., loss='unweighted eight-label CE',
    batchnorm='all running buffers fixed in eval; layer4 affine trainable',
    precision='BF16 forward, FP32 loss/parameters/optimizer; no GradScaler', ema=False,
    routing_threshold=.8, images_per_epoch=4043)
HANDLE = None


def utc():
    return datetime.now(timezone.utc).isoformat()


def sampling_weights(labels):
    labels = np.asarray(labels)
    if (labels.ndim != 1 or not np.issubdtype(labels.dtype, np.integer)
            or np.unique(labels).tolist() != list(range(8))):
        raise ValueError('Sampling weights require training labels for all8classes')
    counts = np.bincount(labels,minlength=8)
    return 1. / counts[labels]


def sample_indices(labels, branch, epoch):
    if branch not in BRANCHES or epoch < 1:
        raise ValueError('Invalid branch or epoch')
    weights = sampling_weights(labels)
    generator = torch.Generator().manual_seed(42+epoch)
    if branch == 'uniform':
        return torch.randperm(len(labels),generator=generator).tolist()
    return list(WeightedRandomSampler(torch.as_tensor(weights,dtype=torch.double),len(labels),
                                     replacement=True,generator=generator))


def choose(scores):
    trials = {}
    baseline = scores['current_fusion']
    for name,score in scores.items():
        failed = shared.specialist.failures(score,baseline)
        if name == 'balanced_sampling':
            if score['macro_f1']+1e-12 < scores['uniform']['macro_f1']:
                failed.append('macro_f1_below_matched_uniform')
            if shared.mean_focus(score) <= shared.mean_focus(scores['uniform'])+1e-12:
                failed.append('no_focus_mean_f1_gain_vs_matched_uniform')
        trials[name] = dict(metrics=score,guard_failures=failed)
    passing = [name for name,t in trials.items() if not t['guard_failures']]
    selected = max(passing,key=lambda name:(scores[name]['macro_f1'],shared.mean_focus(scores[name]),
        scores[name]['accuracy'],name == 'current_fusion',name == 'uniform'))
    return selected,trials


def status(state,**details):
    base.write(OUT/'status.json',dict(state=state,pid=os.getpid(),utc=utc(),**details))


def lock():
    global HANDLE
    import msvcrt
    OUT.mkdir(parents=True,exist_ok=True)
    handle = (OUT/'runner.lock').open('a+b')
    if handle.tell() == 0:
        handle.write(b'0');handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        handle.close()
        raise RuntimeError('Balanced sampling pilot already running')
    HANDLE = handle


def prepare():
    if (OUT/'protocol.json').exists():
        p = base.read(OUT/'protocol.json');shared.verify(p)
        return p
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    registry = base.read(ROOT/'ai-service/reports/active_research_track.json')
    assert registry['next_experiment'] is None
    old = base.read(shared.OUT/'protocol.json');shared.verify(old)
    assert base.read(shared.OUT/'independent_review.json')['status'] == 'PASS'
    model = shared.load_parent()
    names = shared.configure(model,'layer4_finetune')
    frozen = shared.frozen_hash(model)
    initial = shared.state_sha(model.state_dict())
    sources = dict(old['frozen_sha256'])
    for path in [shared.OUT/'protocol.json',shared.OUT/'independent_review.json',
                 ROOT/'ai-service/training/pilot_teacher_balanced_sampling.py',
                 ROOT/'ai-service/tests/test_teacher_balanced_sampling.py']:
        sources[path.relative_to(ROOT).as_posix()] = base.sha(path)
    for rows in old['roles'].values():
        for row in rows:
            assert base.sha(ROOT/row['path']) == row['sha256']
    labels = np.asarray([base.CLASSES.index(r['label']) for r in old['roles']['train']])
    w = sampling_weights(labels)
    p = dict(name=NAME,date='2026-10-23',registered_utc=utc(),classes=base.CLASSES,fold=0,
        roles=old['roles'],baseline_protected=old['baseline_protected'],configuration=CONFIG,
        initial_checkpoint=old['initial_checkpoint'],initial_state_sha256=initial,
        trainable_names=names,frozen_state_sha256=frozen,frozen_sha256=sources,
        class_counts=np.bincount(labels,minlength=8).tolist(),
        balanced_weight_mass=[float(w[labels == i].sum()) for i in range(8)],
        isolated_change='Training index generator only: uniform random permutation vs inverse training-class frequency WeightedRandomSampler with replacement, N=4043 draws/epoch. Expected equal8class exposure, not guaranteed exact counts.',
        matched='Same original8class ResNet50 checkpoint; layer4+fc trainable, earlier tensors and all BN running buffers fixed. Unweighted CE in BOTH branches, same AdamW/cosine6/FP32 optimizer/BF16 forward and position-seeded V2 augmentation. Six full epochs each, no mining/auxiliary images/teacher or additional class loss weights.',
        augmentation='Same augmentation random seed for each epoch/position in both branches; different images and labels mean augmented tensors are NOT expected identical.',
        checkpoint_selection='Each epoch use718inner only; rank guard-pass first, routed MacroF1, mean focus F1, Accuracy; earliest wins exact tie. No epoch selection from outer.',
        final_selection='Same baseline guards as previous specialist. Balanced branch additionally needs MacroF1>=matched uniform and mean focus F1 strictly greater. Rank MacroF1/mean focus F1/Accuracy, baseline then uniform on exact tie. Lock selection before1176outer inference.',
        prediction='Original8labels retained. Collapse probabilities to Lupus/Psoriasis/Tinea/Eczema/Other(sum remaining4) for previous fixed.8 specialist gate. Only those4 baseline labels may change; Other abstains; exact cancer mask.',
        expansion='Onefold pilot only, not a new5937 score. Do not expand unless separately registered; raw and selected scores always both reported.',
        limitations=old['limitations']+[
            'Balanced sampling increases repeats of rare-class photos; it creates no new independent images or patient cases.',
            'No weak-class loss weighting in either branch; comparison isolates sampling within this common unweighted CE recipe.',
            'Fold0 inner has zero SCIN Lupus images. Cannot select for source-specific SCIN Lupus improvement here.'],
        references=['https://docs.pytorch.org/docs/2.5/data.html#torch.utils.data.WeightedRandomSampler'],
        runtime=dict(torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0)),
        serving_changed=False)
    base.write(OUT/'protocol.json',p)
    base.write(OUT/'research_registry_before.json',registry)
    registry['next_experiment'] = OUT.relative_to(ROOT).as_posix()
    registry['next_experiment_status'] = 'registered_balanced_sampling_fold0_matched_pilot'
    base.write(ROOT/'ai-service/reports/active_research_track.json',registry)
    status('registered',epochs_each=6,branches=BRANCHES)
    return p


def train_branch(branch,p):
    folder = MODELS/branch;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'training_report.json').exists():
        report = base.read(folder/'training_report.json')
        assert report['protocol_sha256'] == base.sha(OUT/'protocol.json')
        assert report['checkpoint_sha256'] == base.sha(folder/'best_model.pth')
        return
    shared.seed_everything(42)
    model = shared.load_parent()
    assert shared.state_sha(model.state_dict()) == p['initial_state_sha256']
    assert shared.configure(model,'layer4_finetune') == p['trainable_names']
    assert shared.frozen_hash(model) == p['frozen_state_sha256']
    model.cuda()
    optimizer = torch.optim.AdamW([dict(params=list(model.layer4.parameters()),lr=CONFIG['layer4_lr']),
        dict(params=list(model.fc.parameters()),lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=6,eta_min=1e-6)
    train,inner = p['roles']['train'],p['roles']['inner_validation']
    labels = np.asarray([base.CLASSES.index(r['label']) for r in train])
    dataset = shared.ImageSampleDataset(shared.objects(train),shared.trainer.training_transform_v2())
    _,truth,current = shared.validation_context(p)
    baseline = base.metrics(current,truth)
    resume = folder/'resume_state.pth';history=[];best=None;start=1
    if resume.exists():
        saved = torch.load(resume,map_location='cpu',weights_only=False)
        assert saved['protocol_sha256'] == base.sha(OUT/'protocol.json')
        model.load_state_dict(saved['model']);optimizer.load_state_dict(saved['optimizer'])
        scheduler.load_state_dict(saved['scheduler'])
        history,best,start = saved['history'],saved['best'],saved['epoch']+1
        del saved
    for epoch in range(start,7):
        status('training',branch=branch,epoch=epoch,epochs_limit=6)
        shared.seed_everything(42+epoch);shared.configure(model,'layer4_finetune')
        indices = sample_indices(labels,branch,epoch)
        loader = shared.trainer.make_loader(shared.SeededDataset(dataset,indices,epoch),16,False,0,True)
        ah=hashlib.sha256();lh=hashlib.sha256();updates=0;loss_sum=0.;started=time.monotonic()
        for x,y in loader:
            ah.update(x.numpy().tobytes());lh.update(y.numpy().tobytes())
            x=x.cuda();y=y.cuda();optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16):
                logits=model(x)
            loss=F.cross_entropy(logits.float(),y)
            if not torch.isfinite(loss):
                raise FloatingPointError('Nonfinite sampling pilot loss')
            loss.backward()
            torch.nn.utils.clip_grad_norm_([v for v in model.parameters() if v.requires_grad],2.,error_if_nonfinite=True)
            optimizer.step();updates+=1;loss_sum+=float(loss.detach())
        assert updates == 253 and shared.frozen_hash(model) == p['frozen_state_sha256']
        probability = shared.infer(model,inner)
        score = base.metrics(shared.decision(current,probability),truth)
        raw = base.metrics(probability.argmax(1),truth)
        key = shared.checkpoint_key(score,baseline)
        improved = best is None or tuple(key)>tuple(best['objective'])
        if improved:
            best = dict(epoch=epoch,objective=key,routed_validation=score,raw_validation=raw)
            shared.utility.atomic_save(dict(model_state_dict=model.state_dict(),architecture='resnet50',
                classes=base.CLASSES,branch=branch,epoch=epoch,protocol_sha256=base.sha(OUT/'protocol.json'),research_only=True),folder/'best_model.pth')
        scheduler.step()
        exposure = np.bincount(labels[indices],minlength=8)
        record = dict(epoch=epoch,loss=loss_sum/updates,actual_updates=updates,images=len(indices),
            unique_images=len(set(indices)),class_exposure=exposure.tolist(),
            unique_class_exposure=np.bincount(labels[sorted(set(indices))],minlength=8).tolist(),
            order_sha256=hashlib.sha256(base.json.dumps(indices).encode()).hexdigest(),
            augmentation_sha256=ah.hexdigest(),labels_sha256=lh.hexdigest(),
            frozen_state_sha256=shared.frozen_hash(model),routed_validation=score,raw_validation=raw,
            new_best=improved,best_epoch=best['epoch'],seconds=time.monotonic()-started)
        history.append(record);base.write(folder/'history.json',history)
        shared.utility.atomic_save(dict(protocol_sha256=base.sha(OUT/'protocol.json'),epoch=epoch,
            model=model.state_dict(),optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),history=history,best=best),resume)
        print(base.json.dumps(dict(branch=branch,epoch=epoch,routed_accuracy=score['accuracy'],
            routed_macro_f1=score['macro_f1'],best_epoch=best['epoch'],actual_updates=updates,
            class_exposure=exposure.tolist(),unique_images=record['unique_images'],seconds=record['seconds'])),flush=True)
    del model,optimizer;torch.cuda.empty_cache()
    model=shared.load_parent();shared.configure(model,'layer4_finetune')
    saved=torch.load(folder/'best_model.pth',map_location='cpu',weights_only=False)
    model.load_state_dict(saved['model_state_dict']);model.cuda()
    probability=shared.infer(model,inner)
    base.write(folder/'inner_predictions.json',dict(paths=[r['path'] for r in inner],probabilities=probability.tolist()))
    assert shared.frozen_hash(model) == p['frozen_state_sha256']
    base.write(folder/'training_report.json',dict(protocol_sha256=base.sha(OUT/'protocol.json'),branch=branch,
        checkpoint_sha256=base.sha(folder/'best_model.pth'),initial_checkpoint_sha256=base.sha(ROOT/p['initial_checkpoint']),
        epochs=6,actual_updates=sum(r['actual_updates'] for r in history),skipped_updates=0,best=best,
        trainable_names=p['trainable_names'],initial_state_sha256=p['initial_state_sha256'],
        frozen_state_sha256=shared.frozen_hash(model),all_batchnorm_buffers_fixed=True,outer_used_for_selection=False))
    del model,saved;torch.cuda.empty_cache()


def evaluate(p):
    paths,truth,current=shared.validation_context(p)
    values=dict(current_fusion=current);raw_validation={}
    for branch in BRANCHES:
        v=base.read(MODELS/branch/'inner_predictions.json');assert v['paths']==paths
        probability=np.asarray(v['probabilities'])
        values[branch]=shared.decision(current,probability)
        raw_validation[branch]=base.metrics(probability.argmax(1),truth)
    scores={name:base.metrics(pred,truth) for name,pred in values.items()}
    selected,trials=choose(scores)
    assert not (OUT/'selection_locked.json').exists(),'Preserve existing selection; inspect interrupted evaluation'
    base.write(OUT/'selection_locked.json',dict(locked_utc=utc(),selected=selected,trials=trials,
        raw_validation=raw_validation,protocol_sha256=base.sha(OUT/'protocol.json'),
        checkpoints={b:base.sha(MODELS/b/'best_model.pth') for b in BRANCHES}))
    status('evaluating_outer',selected=selected)
    started=utc()
    old=base.read(shared.utility.PARENT_REPORT/'test_predictions.json')
    lookup={r['path']:r for r in p['roles']['outer_holdout']}
    assert set(lookup)=={r['path'] for r in old}
    rows=[lookup[r['path']] for r in old]
    truth=np.asarray([base.CLASSES.index(r['label']) for r in rows])
    ref=np.asarray([r['probabilities']['old_classwise'] for r in old])
    resnet=np.asarray([r['probabilities']['resnet50'] for r in old])
    current=base.decide(ref,resnet,p['baseline_protected'])
    values=dict(current_fusion=current);raw={}
    for branch in BRANCHES:
        model=shared.load_parent()
        saved=torch.load(MODELS/branch/'best_model.pth',map_location='cpu',weights_only=False)
        model.load_state_dict(saved['model_state_dict']);model.cuda()
        raw[branch]=shared.infer(model,rows)
        values[branch]=shared.decision(current,raw[branch])
        del model,saved;torch.cuda.empty_cache()
    values['validation_selected']=values[selected]
    for pred in values.values():
        assert np.array_equal(pred==5,current==5)
    output=[dict(**row,source='SCIN' if row['path'].startswith('SkinDisease/scin-v1/') else 'original_train',
        predictions={name:int(pred[i]) for name,pred in values.items()},
        probabilities={branch:raw[branch][i].tolist() for branch in BRANCHES}) for i,row in enumerate(rows)]
    base.write(OUT/'outer_decisions.json',output)
    result=dict(status='complete_exploratory_sampling_onefold',fold=0,classes=base.CLASSES,images=1176,
        selected=selected,validation=scores,methods={name:base.metrics(pred,truth) for name,pred in values.items()},
        raw_outer={branch:base.metrics(raw[branch].argmax(1),truth) for branch in BRANCHES},
        per_source={source:{name:base.metrics(pred[mask],truth[mask]) for name,pred in values.items()}
            for source in ['original_train','SCIN'] if (mask:=np.asarray([r['source']==source for r in output])).any()},
        protocol_sha256=base.sha(OUT/'protocol.json'),selection_sha256=base.sha(OUT/'selection_locked.json'),
        outer_started_utc=started,global_5937_score_changed=False,serving_changed=False,limitations=p['limitations'])
    base.write(OUT/'results.json',result)
    return result


def run(p):
    assert not (OUT/'results.json').exists(),'Preserve completed experiment'
    shared.verify(p)
    for branch in BRANCHES:
        train_branch(branch,p)
    histories={branch:base.read(MODELS/branch/'history.json') for branch in BRANCHES}
    assert all(len(h)==6 and sum(r['actual_updates'] for r in h)==1518 for h in histories.values())
    assert all(r['unique_images']==4043 for r in histories['uniform'])
    result=evaluate(p);shared.verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',actual_updates_each=1518,
        initial_state_identical=True,epoch_draw_counts_identical=True,frozen_parameters_and_batchnorm_fixed=True,
        results_sha256=base.sha(OUT/'results.json'),scope='Technical consistency, not clinical validation'))
    status('complete',selected=result['selected'])
    print(base.json.dumps(dict(complete=True,selected=result['selected'],outer={name:{k:s[k] for k in ['accuracy','macro_f1']} for name,s in result['methods'].items()})),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    torch.set_num_threads(4);lock();p=prepare()
    if not args.prepare_only:
        run(p)


if __name__=='__main__':
    main()
