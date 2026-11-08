"""Matched head-only versus layer4+head ResNet specialization, fold0 pilot."""
from __future__ import annotations

import argparse
import hashlib
import os
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from common import ImageSample,ImageSampleDataset,build_model,evaluation_transform,seed_everything
import train_v2 as trainer
import evaluate_original_eight_cancer_locked_fusion as fusion
import pilot_original_eight_balanced_softmax as utility
from pilot_original_eight_imagenet_mixup import SeededDataset,state_sha
import run_teacher_priorities_ensemble_specialist as specialist

ROOT=fusion.ROOT
NAME='teacher_partial_resnet_fold0_seed42_20261023'
OUT=ROOT/'ai-service/reports'/NAME
MODELS=ROOT/'ai-service/candidates'/NAME
PARENT=utility.PARENT
BRANCHES=['head_only','layer4_finetune']
CONFIG=dict(seed=42,epochs=6,batch_size=16,workers=0,head_lr=5e-5,layer4_lr=1e-5,
            weight_decay=.0002,gradient_clip=2.,label_smoothing=0.,specialist_threshold=.8,
            weak_loss_multiplier=1.5,precision='BF16 forward; FP32 loss/parameters/optimizer; no GradScaler',
            batchnorm='All running statistics fixed in eval mode; affine params follow branch trainable mask',ema=False)
HANDLE=None


def configure(model,branch):
    if branch not in BRANCHES:raise ValueError('Unknown branch')
    for name,parameter in model.named_parameters():
        parameter.requires_grad_(name.startswith('fc.') or (branch=='layer4_finetune' and name.startswith('layer4.')))
    # eval() keeps BatchNorm buffers fixed; it does not disable gradients.
    model.eval()
    return [name for name,parameter in model.named_parameters() if parameter.requires_grad]


def frozen_hash(model):
    trainable={name for name,p in model.named_parameters() if p.requires_grad}
    return state_sha({name:value for name,value in model.state_dict().items() if name not in trainable})


def collapse(probability):
    probability=np.asarray(probability)
    if (probability.ndim!=2 or probability.shape[1]!=8 or not np.isfinite(probability).all()
        or (probability<0).any() or not np.allclose(probability.sum(1),1,atol=1e-6)):
        raise ValueError('Expected Nx8 probabilities')
    remaining=[i for i in range(8) if i not in specialist.SPECIAL]
    return np.column_stack([probability[:,i] for i in specialist.SPECIAL]+[probability[:,remaining].sum(1)])


def decision(current,probability):
    return specialist.route(current,collapse(probability))


def mean_focus(score):
    return float(np.mean([score['per_class'][fusion.CLASSES[i]]['f1'] for i in specialist.FOCUS]))


def choose(scores):
    baseline=scores['current_fusion'];trials={}
    for name,score in scores.items():
        reasons=specialist.failures(score,baseline)
        if name=='layer4_finetune':
            if score['macro_f1']+1e-12<scores['head_only']['macro_f1']:
                reasons.append('macro_f1_below_matched_head_only')
            if mean_focus(score)<=mean_focus(scores['head_only'])+1e-12:
                reasons.append('no_focus_mean_f1_gain_vs_matched_head_only')
        trials[name]=dict(metrics=score,guard_failures=reasons)
    passing=[n for n,t in trials.items() if not t['guard_failures']]
    selected=max(passing,key=lambda n:(scores[n]['macro_f1'],mean_focus(scores[n]),scores[n]['accuracy'],
                                      n=='current_fusion',n=='head_only'))
    return selected,trials


def checkpoint_key(score,baseline):
    return [int(not specialist.failures(score,baseline)),score['macro_f1'],mean_focus(score),score['accuracy']]


def status(state,**details):
    fusion.write(OUT/'status.json',dict(state=state,pid=os.getpid(),updated_unix=time.time(),**details))


def lock():
    global HANDLE
    import msvcrt
    OUT.mkdir(parents=True,exist_ok=True)
    handle=(OUT/'runner.lock').open('a+b')
    if handle.tell()==0:handle.write(b'0');handle.flush()
    handle.seek(0)
    try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        handle.close();raise RuntimeError('Partial ResNet pilot already running')
    HANDLE=handle


def verify(p):
    for relative,h in p['frozen_sha256'].items():
        assert fusion.sha(ROOT/relative)==h,relative


def objects(rows):
    return [ImageSample(ROOT/r['path'],fusion.CLASSES.index(r['label']),r['sha256'],r['group']) for r in rows]


def validation_context(p):
    paths,truth,ref,resnet=fusion.validation_arrays(0)
    assert paths==[r['path'] for r in p['roles']['inner_validation']]
    return paths,truth,fusion.decide(ref,resnet,p['baseline_protected'])


def prepare():
    if (OUT/'protocol.json').exists():
        p=fusion.read(OUT/'protocol.json');verify(p);return p
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    registry=fusion.read(ROOT/'ai-service/reports/active_research_track.json')
    assert registry['next_experiment'] is None
    parent=fusion.read(specialist.OUT/'protocol.json');specialist.verify(parent)
    assert fusion.read(specialist.OUT/'independent_review.json')['status']=='PASS'
    roles={role:[dict(path=path,label=parent['manifest'][path]['class'],sha256=parent['manifest'][path]['sha256'],
                      group=parent['manifest'][path]['scene_or_case_group']) for path in paths]
           for role,paths in parent['folds'][0]['roles'].items()}
    assert [len(roles[r]) for r in ['train','inner_validation','outer_holdout']]==[4043,718,1176]
    for a,b in [('train','inner_validation'),('train','outer_holdout'),('inner_validation','outer_holdout')]:
        for key in ['path','sha256','group']:
            assert {r[key] for r in roles[a]}.isdisjoint(r[key] for r in roles[b])
    for rows in roles.values():
        for row in rows:assert fusion.sha(ROOT/row['path'])==row['sha256']
    saved=torch.load(PARENT,map_location='cpu',weights_only=False)
    assert saved['classes']==fusion.CLASSES and saved['architecture']=='resnet50'
    model=build_model('resnet50',8,pretrained=False);model.load_state_dict(saved['model_state_dict'])
    initial_hash=state_sha(model.state_dict());trainables={};frozen={}
    for branch in BRANCHES:
        trainables[branch]=configure(model,branch);frozen[branch]=frozen_hash(model)
    sources=dict(parent['frozen_sha256'])
    files=[PARENT,specialist.OUT/'protocol.json',specialist.OUT/'independent_review.json',
           fusion.OUT/'fold_0/selection_locked.json',ROOT/'ai-service/tests/test_teacher_partial_resnet.py']
    for name in ['pilot_teacher_partial_resnet.py','pilot_original_eight_imagenet_mixup.py',
                 'pilot_original_eight_balanced_softmax.py','run_teacher_priorities_ensemble_specialist.py','train_v2.py','common.py']:
        files.append(ROOT/'ai-service/training'/name)
    sources.update({path.relative_to(ROOT).as_posix():fusion.sha(path) for path in files})
    p=dict(name=NAME,date='2026-10-23',classes=fusion.CLASSES,fold=0,roles=roles,configuration=CONFIG,
        initial_checkpoint=PARENT.relative_to(ROOT).as_posix(),initial_state_sha256=initial_hash,
        frozen_sha256=sources,trainable_names=trainables,frozen_state_sha256=frozen,
        baseline_protected=parent['folds'][0]['baseline_protected'],
        training='Six fixed epochs each branch; same existing8-way ResNet parent, train image order and position-seeded V2 augmentation; each image once/epoch. Identical AdamW, cosine6 eta_min1e-6, weak3 CE weights1.5/others1, zero smoothing; no EMA or mining.',
        isolated_change='head_only trains fc; layer4_finetune trains layer4+fc. All BatchNorm buffers fixed in eval mode in both; no earlier parameters updated. Both retain the original8-class fc.',
        prediction='FP32 inference. Collapse8 probabilities to Lupus/Psoriasis/Tinea/Eczema/Other(sum remaining4) only for specialist routing; no relabeling training targets. Only change baseline calls in those4classes at score>=.8. Other abstains; cancer decision mask unchanged.',
        checkpoint_selection='After each epoch route predictions on718inner. Rank checkpoints by passing original specialist baseline guards first, then routed8-class MacroF1, mean focus F1, Accuracy. Earliest wins exact tie. Both branches get full6epochs; no checkpoint selection by outer.',
        final_selection='Baseline/head_only/layer4 candidate on718inner; prior specialist guards. Layer4 also MacroF1>=matched head_only and mean focus F1 strictly greater. Rank MacroF1/mean focus F1/Accuracy, prefer baseline then head_only on tie. Lock before1176outer inference.',
        expansion='Onefold pilot only in this run. Do not replace full5937 OOF score or extrapolate a onefold gain to five folds. A promising validation choice needs a separately registered confirmation.',
        runtime=dict(torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0)),
        limitations=parent['limitations']+[
            'Onefold six-epoch continuation, one matched seed. No new patient test; prior inner/outer have historical exposure.',
            'This compares layer4 unfreezing within a common weak-weighted CE recipe, not the isolated effect of CE class weighting or a complete paper reproduction.',
            'Fixed0.8 specialist threshold and summed Other scores are not calibrated clinical probabilities.'],
        references=['https://docs.pytorch.org/tutorials/beginner/transfer_learning_tutorial.html'],serving_changed=False)
    fusion.write(OUT/'protocol.json',p);status('registered',branches=BRANCHES,epochs_each=6)
    fusion.write(OUT/'research_registry_before.json',registry)
    registry['next_experiment']=OUT.relative_to(ROOT).as_posix()
    registry['next_experiment_status']='registered_partial_resnet_fold0_matched_pilot'
    fusion.write(ROOT/'ai-service/reports/active_research_track.json',registry)
    return p


def infer(model,rows):
    loader=trainer.make_loader(ImageSampleDataset(objects(rows),evaluation_transform()),16,False,0,True)
    model.eval();blocks=[]
    with torch.inference_mode():
        for x,_ in loader:blocks.append(model(x.cuda()).float().softmax(1).cpu().numpy())
    return np.concatenate(blocks).astype(float)


def load_parent():
    saved=torch.load(PARENT,map_location='cpu',weights_only=False)
    model=build_model('resnet50',8,pretrained=False);model.load_state_dict(saved['model_state_dict'])
    return model


def train_branch(branch,p):
    folder=MODELS/branch;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'training_report.json').exists():
        r=fusion.read(folder/'training_report.json')
        assert r['protocol_sha256']==fusion.sha(OUT/'protocol.json') and r['checkpoint_sha256']==fusion.sha(folder/'best_model.pth')
        return
    seed_everything(42);model=load_parent()
    assert state_sha(model.state_dict())==p['initial_state_sha256']
    assert configure(model,branch)==p['trainable_names'][branch]
    assert frozen_hash(model)==p['frozen_state_sha256'][branch]
    model.cuda()
    optimizer=torch.optim.AdamW([dict(params=list(model.layer4.parameters()),lr=CONFIG['layer4_lr']),
                                dict(params=list(model.fc.parameters()),lr=CONFIG['head_lr'])],weight_decay=CONFIG['weight_decay'])
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=6,eta_min=1e-6)
    loss_weights=torch.tensor([1.,1.,1.,1.5,1.5,1.,1.5,1.],device='cuda')
    train=p['roles']['train'];inner=p['roles']['inner_validation']
    dataset=ImageSampleDataset(objects(train),trainer.training_transform_v2())
    _,truth,current=validation_context(p);baseline=fusion.metrics(current,truth)
    resume=folder/'resume_state.pth';history=[];best=None;start=1
    if resume.exists():
        saved=torch.load(resume,map_location='cpu',weights_only=False)
        assert saved['protocol_sha256']==fusion.sha(OUT/'protocol.json')
        model.load_state_dict(saved['model']);optimizer.load_state_dict(saved['optimizer']);scheduler.load_state_dict(saved['scheduler'])
        history=saved['history'];best=saved['best'];start=saved['epoch']+1;del saved
    for epoch in range(start,7):
        status('training',branch=branch,epoch=epoch,epochs_limit=6)
        seed_everything(42+epoch);configure(model,branch)
        indices=torch.randperm(len(train),generator=torch.Generator().manual_seed(42+epoch)).tolist()
        loader=trainer.make_loader(SeededDataset(dataset,indices,epoch),16,False,0,True)
        ah=hashlib.sha256();lh=hashlib.sha256();updates=0;loss_sum=0.;began=time.monotonic()
        for x,y in loader:
            ah.update(x.numpy().tobytes());lh.update(y.numpy().tobytes())
            x=x.cuda();y=y.cuda();optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16):logits=model(x)
            loss=F.cross_entropy(logits.float(),y,weight=loss_weights)
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite partial-finetune loss')
            loss.backward();torch.nn.utils.clip_grad_norm_([v for v in model.parameters() if v.requires_grad],2,error_if_nonfinite=True)
            optimizer.step();updates+=1;loss_sum+=float(loss.detach())
        assert updates==253 and frozen_hash(model)==p['frozen_state_sha256'][branch]
        probability=infer(model,inner)
        routed=decision(current,probability)
        score=fusion.metrics(routed,truth);raw=fusion.metrics(probability.argmax(1),truth)
        key=checkpoint_key(score,baseline)
        improved=best is None or tuple(key)>tuple(best['objective'])
        if improved:
            best=dict(epoch=epoch,objective=key,routed_validation=score,raw_validation=raw)
            utility.atomic_save(dict(model_state_dict=model.state_dict(),architecture='resnet50',classes=fusion.CLASSES,
                branch=branch,epoch=epoch,protocol_sha256=fusion.sha(OUT/'protocol.json'),research_only=True),folder/'best_model.pth')
        scheduler.step()
        record=dict(epoch=epoch,loss=loss_sum/updates,actual_updates=updates,images=len(indices),unique_images=len(set(indices)),
            order_sha256=hashlib.sha256(fusion.json.dumps(indices).encode()).hexdigest(),augmentation_sha256=ah.hexdigest(),
            labels_sha256=lh.hexdigest(),frozen_state_sha256=frozen_hash(model),routed_validation=score,raw_validation=raw,
            new_best=improved,best_epoch=best['epoch'],seconds=time.monotonic()-began)
        history.append(record);fusion.write(folder/'history.json',history)
        utility.atomic_save(dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),epoch=epoch,model=model.state_dict(),
                                 optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),history=history,best=best),resume)
        print(fusion.json.dumps(dict(branch=branch,epoch=epoch,routed_accuracy=score['accuracy'],routed_macro_f1=score['macro_f1'],
                  best_epoch=best['epoch'],actual_updates=updates,seconds=record['seconds'])),flush=True)
    del model,optimizer;torch.cuda.empty_cache()
    model=load_parent();configure(model,branch)
    saved=torch.load(folder/'best_model.pth',map_location='cpu',weights_only=False);model.load_state_dict(saved['model_state_dict']);model.cuda()
    probability=infer(model,inner)
    fusion.write(folder/'inner_predictions.json',dict(paths=[r['path'] for r in inner],probabilities=probability.tolist()))
    assert frozen_hash(model)==p['frozen_state_sha256'][branch]
    fusion.write(folder/'training_report.json',dict(protocol_sha256=fusion.sha(OUT/'protocol.json'),branch=branch,
        checkpoint_sha256=fusion.sha(folder/'best_model.pth'),initial_checkpoint_sha256=fusion.sha(PARENT),
        initial_state_sha256=p['initial_state_sha256'],trainable_names=p['trainable_names'][branch],
        epochs=6,actual_updates=sum(r['actual_updates'] for r in history),skipped_updates=0,best=best,
        frozen_state_sha256=frozen_hash(model),all_batchnorm_buffers_fixed=True,outer_used_for_selection=False))
    del model,saved;torch.cuda.empty_cache()


def evaluate(p):
    paths,y,current=validation_context(p)
    values={'current_fusion':current};raw_validation={}
    for branch in BRANCHES:
        v=fusion.read(MODELS/branch/'inner_predictions.json');assert v['paths']==paths
        probability=np.array(v['probabilities']);values[branch]=decision(current,probability)
        raw_validation[branch]=fusion.metrics(probability.argmax(1),y)
    scores={n:fusion.metrics(pred,y) for n,pred in values.items()};selected,trials=choose(scores)
    fusion.write(OUT/'selection_locked.json',dict(selected=selected,trials=trials,raw_validation=raw_validation,
        protocol_sha256=fusion.sha(OUT/'protocol.json'),checkpoints={b:fusion.sha(MODELS/b/'best_model.pth') for b in BRANCHES}))
    status('evaluating_outer',selected=selected);print(fusion.json.dumps(dict(selection_locked=selected)),flush=True)
    old=fusion.read(utility.PARENT_REPORT/'test_predictions.json');lookup={r['path']:r for r in p['roles']['outer_holdout']}
    assert set(lookup)=={r['path'] for r in old};rows=[lookup[r['path']] for r in old]
    y=np.array([fusion.CLASSES.index(r['label']) for r in rows])
    ref=np.array([r['probabilities']['old_classwise'] for r in old]);resnet=np.array([r['probabilities']['resnet50'] for r in old])
    current=fusion.decide(ref,resnet,p['baseline_protected']);values={'current_fusion':current};raw={}
    for branch in BRANCHES:
        model=load_parent();saved=torch.load(MODELS/branch/'best_model.pth',map_location='cpu',weights_only=False)
        model.load_state_dict(saved['model_state_dict']);model.cuda()
        raw[branch]=infer(model,rows);values[branch]=decision(current,raw[branch])
        del model,saved;torch.cuda.empty_cache()
    values['validation_selected']=values[selected]
    for pred in values.values():assert np.array_equal(pred==5,current==5)
    output=[dict(**r,source='SCIN' if r['path'].startswith('SkinDisease/scin-v1/') else 'original_train',
        predictions={n:int(pred[i]) for n,pred in values.items()},probabilities={b:raw[b][i].tolist() for b in BRANCHES}) for i,r in enumerate(rows)]
    fusion.write(OUT/'outer_decisions.json',output)
    result=dict(status='complete_exploratory_partial_resnet_onefold',fold=0,classes=fusion.CLASSES,images=1176,
        selected=selected,validation=scores,methods={n:fusion.metrics(pred,y) for n,pred in values.items()},
        raw_outer={b:fusion.metrics(raw[b].argmax(1),y) for b in BRANCHES},
        per_source={s:{n:fusion.metrics(pred[np.array([r['source']==s for r in output])],y[np.array([r['source']==s for r in output])]) for n,pred in values.items()} for s in ['original_train','SCIN']},
        protocol_sha256=fusion.sha(OUT/'protocol.json'),selection_sha256=fusion.sha(OUT/'selection_locked.json'),
        global_5937_score_changed=False,serving_changed=False,limitations=p['limitations'])
    fusion.write(OUT/'results.json',result);return result


def run(p):
    assert not (OUT/'results.json').exists(),'Preserve completed experiment';verify(p)
    for branch in BRANCHES:train_branch(branch,p)
    histories={b:fusion.read(MODELS/b/'history.json') for b in BRANCHES}
    assert all(len(h)==6 for h in histories.values())
    for epoch in range(6):
        for key in ['augmentation_sha256','labels_sha256','order_sha256','images','unique_images','actual_updates']:
            assert histories['head_only'][epoch][key]==histories['layer4_finetune'][epoch][key],(epoch,key)
    result=evaluate(p);verify(p)
    fusion.write(OUT/'verification.json',dict(status='PASS',actual_updates_each=1518,
        matched_augmentation_and_exposure=True,initial_state_identical=True,frozen_parameters_and_batchnorm_unchanged=True,
        results_sha256=fusion.sha(OUT/'results.json'),scope='Technical consistency, not clinical validation'))
    status('complete',selected=result['selected'])
    print(fusion.json.dumps(dict(complete=True,selected=result['selected'],outer={n:{k:s[k] for k in ['accuracy','macro_f1']} for n,s in result['methods'].items()})),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    torch.set_num_threads(4);lock();p=prepare()
    if not args.prepare_only:run(p)


if __name__=='__main__':main()
