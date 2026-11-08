"""Matched pooled CE vs CE+CORAL heads on frozen ResNet features, fold0.

Both domains have training labels. This borrows CORAL covariance alignment,
not the original unsupervised/end-to-end Deep CORAL experiment.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

import pilot_teacher_partial_resnet as shared
import evaluate_original_eight_resnet_transfer as transfer

base=shared.fusion
ROOT=base.ROOT
NAME='teacher_coral_head_fold0_seed42_20261023'
OUT=ROOT/'ai-service/reports'/NAME
MODELS=ROOT/'ai-service/candidates'/NAME
BRANCHES=['pooled_ce','pooled_coral']
CONFIG=dict(seed=42,epochs=20,steps_per_epoch=128,per_domain_batch=16,hidden=128,
    learning_rate=.0003,weight_decay=.001,coral_lambda=100.,gradient_clip=2.,
    loss='Unweighted8labelCE on equal16original+16DermaCon train draws',
    precision='CPU FP32, two intraop threads; frozen CNN FP32 inference only',
    routing='Previous weak4/Other fixed0.8gate; exact baseline cancer mask')


def utc():return datetime.now(timezone.utc).isoformat()


class Head(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder=nn.Sequential(nn.Linear(2048,128),nn.LayerNorm(128),nn.ReLU())
        self.classifier=nn.Linear(128,8)
    def forward(self,x):
        z=self.encoder(x)
        return self.classifier(z),z


def coral(a,b):
    if a.ndim!=2 or b.ndim!=2 or a.shape[1]!=b.shape[1] or min(len(a),len(b))<2:
        raise ValueError('CORAL requires two batches of>=2rows and equal feature dimensions')
    aa=a-a.mean(0);bb=b-b.mean(0)
    ca=aa.T@aa/(len(a)-1);cb=bb.T@bb/(len(b)-1)
    return (ca-cb).square().mean()/4


def draws(n_original,n_auxiliary,epoch):
    g=torch.Generator().manual_seed(20261023+epoch)
    return (torch.randint(n_original,(128,16),generator=g),
            torch.randint(n_auxiliary,(128,16),generator=g))


def assess(predictions,truth,reference):
    scores={role:base.metrics(predictions[role],truth[role]) for role in truth}
    failed=shared.specialist.failures(scores['original_validation'],reference['original_validation'])
    clinical=scores['dermacon_validation'];old=reference['dermacon_validation']
    if clinical['macro_f1']+1e-12<old['macro_f1']:failed.append('clinical_macro_f1')
    if shared.mean_focus(clinical)+1e-12<shared.mean_focus(old):failed.append('clinical_focus_mean_f1')
    if any(abs(clinical['per_class']['SkinCancer'][key]-old['per_class']['SkinCancer'][key])>1e-12 for key in ['precision','recall']):
        failed.append('clinical_cancer_mask')
    key=[int(not failed),float(np.mean([s['macro_f1'] for s in scores.values()])),
         float(np.mean([shared.mean_focus(s) for s in scores.values()])),scores['original_validation']['accuracy']]
    return scores,failed,key


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');shared.verify(p);return p
    registry=base.read(ROOT/'ai-service/reports/active_research_track.json');assert registry['next_experiment'] is None
    parent=base.read(shared.OUT/'protocol.json');shared.verify(parent)
    historical=base.read(ROOT/'ai-service/reports/original_eight_ensemble_teacher_pilot_fold0_seed42/protocol.json')
    source_audit=base.read(transfer.OUT/'audit.json')
    canonical={r['path']:r for s in source_audit['sources'].values() for r in s['rows'] if r['included']}
    aux=[dict(path=r['path'],label=r['label'],sha256=r['sha256'],group=canonical[r['path']]['group'])
         for r in historical['supplement'] if 'dermacon' in r['path']]
    assert len(aux)==590
    roles={**parent['roles'], 'auxiliary_train':aux,
        'dermacon_validation':historical['splits']['dermacon_validation'],
        'dermacon_official_test':historical['splits']['dermacon_official_test'],
        'skindisnet_transfer':historical['splits']['skindisnet_transfer']}
    for role,rows in roles.items():
        for row in rows:assert base.sha(ROOT/row['path'])==row['sha256']
    train=roles['train']+aux
    for role in ['inner_validation','outer_holdout','dermacon_validation','dermacon_official_test','skindisnet_transfer']:
        for key in ['path','sha256']:
            assert {r[key] for r in train}.isdisjoint(r[key] for r in roles[role])
    groups={role:{canonical[r['path']]['group'] for r in rows} for role,rows in roles.items() if role.startswith('dermacon') or role=='auxiliary_train'}
    assert groups['auxiliary_train'].isdisjoint(groups['dermacon_validation']|groups['dermacon_official_test'])
    files=[ROOT/'ai-service/training/pilot_teacher_coral_head.py',ROOT/'ai-service/tests/test_teacher_coral_head.py',
        shared.OUT/'protocol.json',ROOT/'ai-service/reports/original_eight_ensemble_teacher_pilot_fold0_seed42/protocol.json',
        transfer.OUT/'protocol.json',transfer.OUT/'audit.json',transfer.OUT/'fold_0_resnet50.npz']
    cache=shared.specialist.OUT/'B_specialist/fold_0'
    files += [cache/f'{role}_features.npz' for role in ['train','inner_validation','outer_holdout']]
    sources=dict(parent['frozen_sha256']);sources.update({path.relative_to(ROOT).as_posix():base.sha(path) for path in files})
    p=dict(name=NAME,registered_utc=utc(),classes=base.CLASSES,fold=0,roles=roles,
        baseline_protected=parent['baseline_protected'],configuration=CONFIG,frozen_sha256=sources,
        architecture='Frozen original fold0ResNet2048features; train shared Linear2048to128/LayerNorm/ReLU plus Linear128to8. No dropout, no CNN updates.',
        scaling='StandardScaler fitted on4043original training features only; identical transform for every source and role.',
        isolated_change='Both heads share identical initial state, batches, original4043andDermaCon590train labels, optimizer and20epochs. Only add lambda100*CORAL covariance loss on the128hidden activations of the two training batches.',
        sampling='128steps/epoch,16original+16auxiliary replacement draws/step;4096total draws/epoch. Equal domain mass, no class reweighting, augmentation, mining or source identity at inference.',
        checkpoint='After every epoch compute fixed weak4routing on718original inner and213clinical validation; rank dualguard-pass, mean two MacroF1, mean two focus F1, original Accuracy. Earliest exact tie. Both branches complete20epochs.',
        selection='Original specialist guards on original inner; clinical MacroF1/focusMeanF1>=baseline, cancer mask unchanged. CORAL additionally mean validation MacroF1>=matchedCE and mean focusF1 strictly greater. Rank same dual metrics, baseline wins ties. Lock before held-role feature extraction/inference.',
        limits=['Onefold exploratory development on previously investigated data, not independent confirmation or new5937OOF.',
            'Original frozen CNN already trained originaltrain and used originalinner for checkpoint selection. Frozen-feature head evaluation is not fully nested CNN retraining.',
            'Target590labels are supervised and historical; original DeepCORAL paper instead studied unlabeled targets and end-to-end networks. This is a new matched feature-head experiment using its covariance idea.',
            'Clinical val has5Lupus photos; clinical test183has zeroLupus. Original inner has zeroSCINLupus. Rare classes cannot be verified stably here.',
            'Covariance alignment may mix class structure when class proportions differ; no guarantee of improvement.',
            'Equal source draws repeat known images; no new photos/patients. Scores are not calibrated clinical probabilities.',
            'Original source patient IDs missing; image/group audit does not prove cross-source patient independence.',
            'Cancer routing retains prior false negatives/positives. No API or Word changes.'],
        references=['https://arxiv.org/abs/1607.01719'],serving_changed=False)
    OUT.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p)
    base.write(OUT/'research_registry_before.json',registry)
    registry['next_experiment']=OUT.relative_to(ROOT).as_posix();registry['next_experiment_status']='registered_matched_supervised_coral_head_pilot'
    base.write(ROOT/'ai-service/reports/active_research_track.json',registry)
    base.write(OUT/'status.json',dict(state='registered',utc=utc()))
    return p


def feature_cache(p,role):
    original={'train':'train','original_validation':'inner_validation','original_outer':'outer_holdout'}
    if role in original:
        path=shared.specialist.OUT/f'B_specialist/fold_0/{original[role]}_features.npz'
        rows=p['roles'][original[role]]
        with np.load(path,allow_pickle=False) as z:
            assert z['paths'].tolist()==[r['path'] for r in rows]
            assert z['protocol_sha256'].item()==base.sha(shared.specialist.OUT/'protocol.json')
            return z['features'].copy(),rows
    rows=p['roles'][role];path=OUT/(role+'_features.npz')
    if path.exists():
        with np.load(path,allow_pickle=False) as z:
            assert z['paths'].tolist()==[r['path'] for r in rows]
            assert z['protocol_sha256'].item()==base.sha(OUT/'protocol.json')
            return z['features'].copy(),rows
    # Same FP32/cuDNN defaults as the frozen source cache, no adaptation of CNN.
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=False
    extractor=shared.specialist.Extractor(0)
    x,pp=extractor.infer(rows);extractor.close()
    with np.load(transfer.OUT/'fold_0_resnet50.npz',allow_pickle=False) as z:
        index={path:i for i,path in enumerate(z['paths'].tolist())}
        expected=z['probabilities'][[index[r['path']] for r in rows]]
    # Source rows are regrouped into role-specific batches, so validate decisions
    # and bound FP32 batch-kernel variation separately from the cached features.
    assert np.array_equal(pp.argmax(1),expected.argmax(1))
    maximum=float(np.abs(pp-expected).max())
    assert maximum<.003,maximum
    np.savez_compressed(path,paths=[r['path'] for r in rows],features=x,probabilities=pp,
        max_probability_difference_to_historical_batches=maximum,protocol_sha256=base.sha(OUT/'protocol.json'))
    return x,rows


def baseline(p,role,rows):
    if role=='original_validation':return shared.validation_context(p)[2]
    if role=='original_outer':
        old={r['path']:r for r in base.read(shared.utility.PARENT_REPORT/'test_predictions.json')}
        pp={name:np.asarray([old[r['path']]['probabilities'][name] for r in rows]) for name in ['old_classwise','resnet50']}
    else:
        values=[]
        for name in ['efficientnet_b0','convnext_tiny','resnet50']:
            with np.load(transfer.OUT/f'fold_0_{name}.npz',allow_pickle=False) as z:
                index={path:i for i,path in enumerate(z['paths'].tolist())}
                values.append(z['probabilities'][[index[r['path']] for r in rows]])
        weights=base.read(shared.utility.PARENT_REPORT/'selection_locked.json')['reference_weights']
        pp=dict(old_classwise=transfer.classwise_blend(values[0],values[1],np.asarray(weights)),resnet50=values[2])
    return base.decide(pp['old_classwise'],pp['resnet50'],p['baseline_protected'])


def probability(model,x):
    model.eval()
    with torch.inference_mode():return model(x)[0].softmax(1).numpy().astype(float)


def run(p):
    assert not (OUT/'results.json').exists(),'Preserve completed pilot'
    shared.verify(p)
    data={};raw={};truth={};reference={}
    for role in ['train','auxiliary_train','original_validation','dermacon_validation']:
        raw[role],rows=feature_cache(p,role)
        truth[role]=np.array([base.CLASSES.index(r['label']) for r in rows])
        if role.endswith('validation'):reference[role]=baseline(p,role,rows)
    scaler=StandardScaler().fit(raw['train'])
    for role,x in raw.items():data[role]=torch.from_numpy(scaler.transform(x).astype(np.float32))
    OUT.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(OUT/'scaler.npz',mean=scaler.mean_,scale=scaler.scale_)
    ys={role:torch.as_tensor(y,dtype=torch.long) for role,y in truth.items()}
    ref_scores={role:base.metrics(pred,truth[role]) for role,pred in reference.items()}
    validation={};all_histories={};initial=None
    for branch in BRANCHES:
        folder=MODELS/branch;folder.mkdir(parents=True,exist_ok=True)
        torch.manual_seed(42);model=Head()
        initial_hash=shared.state_sha(model.state_dict())
        if initial is None:initial=initial_hash
        assert initial==initial_hash
        optimizer=torch.optim.AdamW(model.parameters(),lr=CONFIG['learning_rate'],weight_decay=CONFIG['weight_decay'])
        history=[];best=None
        for epoch in range(1,21):
            base.write(OUT/'status.json',dict(state='training',branch=branch,epoch=epoch,utc=utc()))
            model.train();old_ids,aux_ids=draws(len(data['train']),len(data['auxiliary_train']),epoch)
            totals=np.zeros(3);start=time.monotonic()
            for old,aux in zip(old_ids,aux_ids):
                optimizer.zero_grad(set_to_none=True)
                logits,z=model(torch.cat([data['train'][old],data['auxiliary_train'][aux]]))
                target=torch.cat([ys['train'][old],ys['auxiliary_train'][aux]])
                ce=F.cross_entropy(logits,target);alignment=coral(z[:16],z[16:])
                loss=ce+(100*alignment if branch=='pooled_coral' else 0)
                if not torch.isfinite(loss):raise FloatingPointError('Nonfinite head loss')
                loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),2.,error_if_nonfinite=True)
                optimizer.step();totals += [float(loss.detach()),float(ce.detach()),float(alignment.detach())]
            proposed={role:shared.decision(reference[role],probability(model,data[role])) for role in reference}
            scores,failed,key=assess(proposed,{role:truth[role] for role in reference},ref_scores)
            improved=best is None or tuple(key)>tuple(best['objective'])
            if improved:
                best=dict(epoch=epoch,objective=key,scores=scores,guard_failures=failed)
                shared.utility.atomic_save(dict(model_state_dict=model.state_dict(),classes=base.CLASSES,
                    epoch=epoch,branch=branch,protocol_sha256=base.sha(OUT/'protocol.json')),folder/'best_model.pth')
            history.append(dict(epoch=epoch,actual_updates=128,loss=float(totals[0]/128),ce=float(totals[1]/128),
                coral=float(totals[2]/128),sampling_sha256=hashlib.sha256(old_ids.numpy().tobytes()+aux_ids.numpy().tobytes()).hexdigest(),
                scores=scores,guard_failures=failed,new_best=improved,best_epoch=best['epoch'],seconds=time.monotonic()-start))
            base.write(folder/'history.json',history)
            print(json.dumps(dict(branch=branch,epoch=epoch,loss=history[-1]['loss'],coral=history[-1]['coral'],best_epoch=best['epoch'])),flush=True)
        shared.utility.atomic_save(dict(model=model.state_dict(),optimizer=optimizer.state_dict(),history=history,
            initial_state_sha256=initial,protocol_sha256=base.sha(OUT/'protocol.json')),folder/'resume_state.pth')
        model.load_state_dict(torch.load(folder/'best_model.pth',weights_only=False)['model_state_dict'])
        validation[branch]={role:probability(model,data[role]) for role in reference}
        base.write(folder/'validation_probabilities.json',{role:pp.tolist() for role,pp in validation[branch].items()})
        base.write(folder/'training_report.json',dict(initial_state_sha256=initial,actual_updates=2560,epochs=20,best=best,
            protocol_sha256=base.sha(OUT/'protocol.json'),checkpoint_sha256=base.sha(folder/'best_model.pth')))
        all_histories[branch]=history
    assert [h['sampling_sha256'] for h in all_histories[BRANCHES[0]]]==[h['sampling_sha256'] for h in all_histories[BRANCHES[1]]]
    trials={'current_fusion':dict(scores=ref_scores,guard_failures=[],objective=[1,
        float(np.mean([s['macro_f1'] for s in ref_scores.values()])),float(np.mean([shared.mean_focus(s) for s in ref_scores.values()])),ref_scores['original_validation']['accuracy']])}
    for branch in BRANCHES:
        decisions={role:shared.decision(reference[role],pp) for role,pp in validation[branch].items()}
        scores,failed,key=assess(decisions,{role:truth[role] for role in reference},ref_scores)
        trials[branch]=dict(scores=scores,guard_failures=failed,objective=key)
    a,b=trials['pooled_coral'],trials['pooled_ce']
    if a['objective'][1]+1e-12<b['objective'][1]:a['guard_failures'].append('mean_macro_f1_below_matched_ce')
    if a['objective'][2]<=b['objective'][2]+1e-12:a['guard_failures'].append('no_mean_focus_f1_gain_vs_matched_ce')
    selected=max([n for n,t in trials.items() if not t['guard_failures']],key=lambda n:(*trials[n]['objective'][1:],n=='current_fusion',n=='pooled_ce'))
    base.write(OUT/'selection_locked.json',dict(locked_utc=utc(),selected=selected,trials=trials,
        checkpoints={b:base.sha(MODELS/b/'best_model.pth') for b in BRANCHES},scaler_sha256=base.sha(OUT/'scaler.npz')))
    results={};output=[];started=utc()
    for role in ['original_outer','dermacon_official_test','skindisnet_transfer']:
        x,rows=feature_cache(p,role);x=torch.from_numpy(scaler.transform(x).astype(np.float32))
        y=np.array([base.CLASSES.index(r['label']) for r in rows]);current=baseline(p,role,rows)
        decisions=dict(current_fusion=current);pp={}
        for branch in BRANCHES:
            model=Head();model.load_state_dict(torch.load(MODELS/branch/'best_model.pth',weights_only=False)['model_state_dict'])
            pp[branch]=probability(model,x);decisions[branch]=shared.decision(current,pp[branch])
        decisions['validation_selected']=decisions[selected]
        for pred in decisions.values():assert np.array_equal(pred==5,current==5)
        results[role]={name:base.metrics(pred,y) for name,pred in decisions.items()}
        output.extend(dict(**row,role=role,predictions={name:int(pred[i]) for name,pred in decisions.items()},
            probabilities={branch:values[i].tolist() for branch,values in pp.items()}) for i,row in enumerate(rows))
    base.write(OUT/'held_decisions.json',output)
    base.write(OUT/'results.json',dict(status='complete_exploratory_frozen_coral_head_onefold',selected=selected,
        validations=trials,held=results,held_started_utc=started,protocol_sha256=base.sha(OUT/'protocol.json'),
        selection_sha256=base.sha(OUT/'selection_locked.json'),global_5937_score_changed=False,serving_changed=False,limits=p['limits']))
    shared.verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),
        updates_each=2560,identical_batches=True,CNN_unchanged=True,no_held_role_alignment=True))
    base.write(OUT/'status.json',dict(state='complete',utc=utc(),selected=selected))
    print(json.dumps(dict(complete=True,selected=selected,held={role:{n:{k:s[k] for k in ['accuracy','macro_f1']} for n,s in values.items()} for role,values in results.items()})),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    torch.set_num_threads(2)
    with threadpool_limits(limits=1):
        p=prepare()
        if not args.prepare_only:run(p)


if __name__=='__main__':main()
