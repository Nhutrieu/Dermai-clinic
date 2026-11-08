"""Independent schedules/loss-gradient/fusion/metrics checks for negative pilot."""
import hashlib
import json
from collections import Counter

import numpy as np
import torch
from common import CLASSES,ImageSampleDataset,build_model,evaluation_transform,save_json,sha256_file
from verify_original_eight_pad_addition import independent_cancer,verify_score
import pilot_original_eight_negative_supervision_fp32 as e


def loss_check():
    z=np.asarray([[.2,-.1,.5,-.2,.8,.3,-.7,.6],[-.3,.1,-.5,.4,-.8,100.,.2,.6]],dtype=float)
    def lse(a):
        m=a.max(1); return m+np.log(np.exp(a-m[:,None]).sum(1))
    other=np.delete(z,5,axis=1); expected=lse(z)-lse(other)
    tensor=torch.tensor(z,dtype=torch.float32,requires_grad=True)
    loss=e.complementary_loss(tensor); assert np.allclose(loss.detach().numpy(),expected,atol=1e-5,rtol=0)
    loss.sum().backward()
    p=np.exp(z-lse(z)[:,None]); q=np.exp(other-lse(other)[:,None]); gradient=p.copy(); gradient[:,:5]-=q[:,:5]; gradient[:,6:]-=q[:,5:]
    assert np.allclose(tensor.grad.numpy(),gradient,atol=1e-6,rtol=0)
    assert np.isfinite(loss.detach().numpy()).all() and (tensor.grad[:,5]>0).all()


def main():
    root,out=e.ROOT,e.OUT; p=e.read(out/'protocol.json'); lock=e.read(out/'selection_locked.json'); result=e.read(out/'results.json')
    for n,h in p['sources'].items(): assert sha256_file(root/n)==h,n
    for n,h in p['code_sha256'].items(): assert sha256_file(root/'ai-service/training'/n)==h,n
    assert lock['protocol_sha256']==result['protocol_sha256']==sha256_file(out/'protocol.json')
    assert result['selection_sha256']==sha256_file(out/'selection_locked.json')
    assert p['configuration']['precision']=='float32'
    base=e.read(e.previous.OUT/'protocol.json'); assert p['splits']==base['splits'] and p['pad_validation']==base['pad_validation']
    rr=p['train']+p['supplement']+p['pad']; negative=p['negative']
    assert all(r['label'] is None and r['complementary_label']=='SkinCancer' for r in negative)
    allpaths={r['path'] for r in rr+negative}; allsha={r['sha256'] for r in rr+negative}
    for rows in [*p['splits'].values(),p['pad_validation']]:
        assert allpaths.isdisjoint(r['path'] for r in rows) and allsha.isdisjoint(r['sha256'] for r in rows)
    assert {r['source_patient_id'] for r in p['pad']+negative}.isdisjoint(r['patient'] for r in p['pad_validation'])
    for r in rr+negative: assert sha256_file(root/r['path'])==r['sha256']
    reports={b:e.read(e.MODELS/b/'training_report.json') for b in e.BRANCHES}; history={b:e.read(e.MODELS/b/'history.json') for b in e.BRANCHES}
    counters=Counter(r['label'] for r in p['train']); counts=np.asarray([counters[c] for c in CLASSES]); weights=(1-.999)/(1-.999**counts); weights/=weights.mean()
    poscounts=Counter((r['source_label'],r['source_patient_id']) for r in p['pad']); pospeople={d:{r['source_patient_id'] for r in p['pad'] if r['source_label']==d} for d in ('BCC','SCC','MEL')}
    posmass=torch.tensor([1/(3*len(pospeople[r['source_label']])*poscounts[r['source_label'],r['source_patient_id']]) for r in p['pad']],dtype=torch.float64)
    negcounts=Counter((r['source_label'],r['source_patient_id']) for r in negative); negpeople={d:{r['source_patient_id'] for r in negative if r['source_label']==d} for d in ('NEV','SEK')}
    negmass=torch.tensor([1/(2*len(negpeople[r['source_label']])*negcounts[r['source_label'],r['source_patient_id']]) for r in negative],dtype=torch.float64)
    assert np.allclose(negmass.numpy(),e.negative_weights(negative).numpy(),atol=1e-15,rtol=0)
    for epoch in range(1,4):
        old=torch.multinomial(torch.tensor([.9/4043]*4043+[.1/807]*807,dtype=torch.float64),4043,True,generator=torch.Generator().manual_seed(42+epoch)).tolist()
        positions=[i for i,j in enumerate(old) if j<4043]; order=torch.randperm(len(positions),generator=torch.Generator().manual_seed(424200+epoch)).tolist(); slots=sorted(positions[i] for i in order[:202])
        selected=torch.multinomial(posmass,202,True,generator=torch.Generator().manual_seed(5000+epoch)).tolist(); ids=old.copy()
        for slot,j in zip(slots,selected): ids[slot]=4850+j
        negids=torch.multinomial(negmass,202,True,generator=torch.Generator().manual_seed(6000+epoch)).tolist(); mapping=dict(zip(slots,negids))
        assert e.schedules(p,epoch)==(ids,mapping)
        for b in e.BRANCHES:
            saved=history[b][epoch-1]
            assert saved['coefficient']==(0 if b=='control' else 1)
            assert saved['main_indices_sha256']==hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()
            assert saved['negative_mapping_sha256']==hashlib.sha256(json.dumps(mapping,separators=(',',':')).encode()).hexdigest()
            assert saved['main_source_draws']==dict(Counter(rr[i].get('source','original') for i in ids))
            assert saved['positive_subtype_draws']==dict(Counter(rr[i]['source_label'] for i in ids if i>=4850))
            assert saved['negative_subtype_draws']==dict(Counter(negative[i]['source_label'] for i in mapping.values()))
            assert saved['negative_images_forwarded']==202 and saved['negative_bn_unchanged']
            assert saved['actual_updates']==saved['attempted_updates']==253
        for key in ('main_augmented_stream_sha256','negative_augmented_stream_sha256'):
            assert history['control'][epoch-1][key]==history['negative'][epoch-1][key]
        # Deterministic inputs and absence of8class supervision for negatives.
        ds=e.ContrastDataset(p,ids,mapping,epoch); x=ds[slots[0]]; z=ds[slots[0]]
        assert torch.equal(x[0],z[0]) and torch.equal(x[2],z[2]) and x[1]==z[1] and x[3] is True
    loss_check()
    for b,report in reports.items():
        assert report['epochs']==3 and report['actual_updates']==759 and report['coefficient']==(0 if b=='control' else 1)
        assert report['class_counts']==counts.astype(int).tolist() and np.allclose(report['class_weights'],weights,atol=2e-7,rtol=0)
        assert report['initial_checkpoint_sha256']==p['initial_checkpoint_sha256']
        assert report['checkpoint_sha256']==lock['checkpoint_sha256'][b]==sha256_file(e.MODELS/b/'final_model.pth')
    trials={t['name']:t for t in lock['trials']}
    for split in e.previous.prior.SPLITS:
        rows=p['splits'][split]; y=np.asarray([CLASSES.index(r['label']) for r in rows])
        with np.load(out/(split+'.npz')) as z:
            assert z['paths'].tolist()==[r['path'] for r in rows] and np.array_equal(z['truth'],y)
            ref=e.previous.prior.baseline(split,rows)['old_classwise']; assert np.allclose(ref,z['old_classwise'],atol=1e-12,rtol=0)
            for b in e.BRANCHES:
                fusion=.75*ref+.25*z[b+'_resnet']; fusion/=fusion.sum(1,keepdims=True)
                assert np.allclose(fusion,z[b+'_mix25'],atol=1e-12,rtol=0)
            for name in e.METHODS:
                assert np.isfinite(z[name]).all() and (z[name]>=0).all() and np.allclose(z[name].sum(1),1,atol=1e-6)
                verify_score(z[name],y,result['results'][split][name])
            assert result['results'][split]['validation_selected']==result['results'][split][lock['selected']]
            if split in e.previous.prior.SPLITS[:2]:
                for n,t in trials.items(): assert t[split]==result['results'][split][n]
            else: assert (out/'selection_locked.json').stat().st_mtime_ns<(out/(split+'.npz')).stat().st_mtime_ns
    with np.load(out/'pad_validation.npz') as z,np.load(e.previous.OUT/'pad_validation.npz') as old:
        assert z['paths'].tolist()==old['paths'].tolist()==[r['path'] for r in p['pad_validation']]
        for n in ('efficientnet_b0','convnext_tiny','old_classwise'): assert np.array_equal(z[n],old[n])
        for b in e.BRANCHES:
            prob=.75*z['old_classwise']+.25*z[b+'_resnet']; prob/=prob.sum(1,keepdims=True)
            assert np.allclose(prob,z[b+'_mix25'],atol=1e-12,rtol=0)
        pm={n:independent_cancer(z[n],p['pad_validation']) for n in e.METHODS}
        for n,m in pm.items(): assert m==result['pad_validation'][n]
    for n,t in trials.items():
        assert t['pad_validation']==pm[n]
        ref,item=pm['old_classwise'],pm[n]
        eligible=e.previous.prior.eligible(t,trials['old_classwise']) and item['non_cancer_flag_rate']<=ref['non_cancer_flag_rate']+1e-12 and all(item['by_diagnosis'][d]['flag_rate']>=ref['by_diagnosis'][d]['flag_rate']-1e-12 for d in ('BCC','SCC','MEL'))
        assert t['eligible']==bool(eligible)
    selected=sorted([t for t in trials.values() if t['eligible']],key=e.previous.prior.rank)[0]['name']; assert selected==lock['selected']==result['selected']
    # Batch16matched actual inference and real negative gradient/BN check.
    torch.set_num_threads(4)
    for b in e.BRANCHES:
        cp=torch.load(e.MODELS/b/'final_model.pth',map_location='cpu',weights_only=False); model=build_model('resnet50',8,pretrained=False); model.load_state_dict(cp['model_state_dict']); del cp; model.cuda().eval()
        for split in ('original_validation','pad_validation'):
            rows=p['pad_validation'] if split=='pad_validation' else p['splits'][split]
            ds=ImageSampleDataset(e.previous.prior.samples([dict(r,label=r.get('label') or 'SkinCancer') for r in rows[:16]]),evaluation_transform())
            x=torch.stack([ds[i][0] for i in range(16)]).cuda()
            with torch.inference_mode(): prob=model(x).softmax(1).cpu().numpy()
            with np.load(out/(split+'.npz')) as z: assert np.allclose(prob,z[b+'_resnet'][:16],atol=2e-5,rtol=0)
        if b=='negative':
            nx=[]
            for r in negative[:2]:
                with e.Image.open(root/r['path']) as image: nx.append(evaluation_transform()(image.convert('RGB')))
            before=e.bn_state_hash(model); loss=e.complementary_loss(model(torch.stack(nx).cuda())).mean(); loss.backward()
            assert e.bn_state_hash(model)==before and torch.isfinite(model.fc.weight.grad).all() and float(model.fc.weight.grad.norm())>0
        del model; torch.cuda.empty_cache()
    # Optional exact reproduction evidence; not a gate for matched negative effect.
    oldpaths=[r['path'] for r in base['pad']]; repeated=[r['path'] for r in p['pad']]==oldpaths
    exact=False
    if repeated:
        old=torch.load(e.previous.MODELS/'pad/final_model.pth',map_location='cpu',weights_only=False)['model_state_dict']
        new=torch.load(e.MODELS/'control/final_model.pth',map_location='cpu',weights_only=False)['model_state_dict']
        exact=all(torch.equal(new[k],old[k]) for k in old)
    save_json(out/'verification.json',dict(status='PASS',protocol_sha256=sha256_file(out/'protocol.json'),results_sha256=sha256_file(out/'results.json'),
        actual_updates={b:reports[b]['actual_updates'] for b in e.BRANCHES},main_negative_streams_match=True,negative_bn_frozen=True,
        independent_schedule_metrics_fusion=True,loss_and_gradient_checked=True,actual_inference_checked=True,
        control_exact_tensor_reproduction_of_previous_pad=exact,selected=selected,scope='Implementation/provenance check; no independent clinical confirmation.'))
    print(e.read(out/'verification.json'),flush=True)


if __name__=='__main__': main()
