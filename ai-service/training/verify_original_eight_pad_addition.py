"""Verify matched PAD sampling, shared augmentation, roles, fusion and inference."""
import hashlib
import json
from collections import Counter

import numpy as np
import torch
from sklearn.metrics import confusion_matrix

from common import CLASSES,ImageSampleDataset,build_model,evaluation_transform,save_json,sha256_file
import pilot_original_eight_pad_addition as e


def independent_cancer(p,rr):
    flag=p.argmax(1)==5; result={}
    for d in ('BCC','SCC','MEL','ACK','NEV','SEK'):
        ids=[i for i,r in enumerate(rr) if r['diagnostic']==d]
        result[d]=dict(images=len(ids),flagged=int(flag[ids].sum()),flag_rate=float(flag[ids].mean()) if ids else None)
    ids=[i for i,r in enumerate(rr) if r['diagnostic'] in ('ACK','NEV','SEK')]
    return dict(by_diagnosis=result,non_cancer_flag_rate=float(flag[ids].mean()),non_cancer_images=len(ids),non_cancer_flagged=int(flag[ids].sum()),scope='Argmax SkinCancer flag, not eight-class accuracy or fresh external validation.')


def verify_score(prob,y,record):
    cm=confusion_matrix(y,prob.argmax(1),labels=np.arange(8)); assert record['confusion_matrix']==cm.tolist()
    tp=cm.diagonal(); support=cm.sum(1); pred=cm.sum(0)
    f1=np.divide(2*tp,support+pred,out=np.zeros(8,dtype=float),where=(support+pred)>0)
    assert abs(float(tp.sum()/len(y))-record['accuracy'])<1e-12
    assert abs(float(f1.mean())-record['macro_f1'])<1e-12
    for k,c in enumerate(CLASSES):
        m=record['per_class'][c]
        assert m['support']==int(support[k])
        assert abs(m['recall']-(tp[k]/support[k] if support[k] else 0))<1e-12
        assert abs(m['precision']-(tp[k]/pred[k] if pred[k] else 0))<1e-12
        assert abs(m['f1']-f1[k])<1e-12


def main():
    root,out=e.ROOT,e.OUT; p=e.read(out/'protocol.json'); lock=e.read(out/'selection_locked.json'); result=e.read(out/'results.json')
    for n,h in p['sources'].items(): assert sha256_file(root/n)==h,n
    for n,h in p['code_sha256'].items(): assert sha256_file(root/'ai-service/training'/n)==h,n
    assert lock['protocol_sha256']==result['protocol_sha256']==sha256_file(out/'protocol.json')
    assert result['selection_sha256']==sha256_file(out/'selection_locked.json')
    rr=p['train']+p['supplement']+p['pad']
    paths={r['path'] for r in rr}; digests={r['sha256'] for r in rr}
    for rows in [*p['splits'].values(),p['pad_validation']]:
        assert paths.isdisjoint(r['path'] for r in rows) and digests.isdisjoint(r['sha256'] for r in rows)
    assert {r['source_patient_id'] for r in p['pad']}.isdisjoint(r['patient'] for r in p['pad_validation'])
    for r in rr: assert sha256_file(root/r['path'])==r['sha256']
    history={b:e.read(e.MODELS/b/'history.json') for b in e.BRANCHES}
    original_counts=Counter(CLASSES.index(r['label']) for r in p['train']); count=np.asarray([original_counts[k] for k in range(8)])
    expected=(1-.999)/(1-.999**count); expected/=expected.mean()
    reports={b:e.read(e.MODELS/b/'training_report.json') for b in e.BRANCHES}
    # Independent closed-form subtype/patient probabilities.
    subgroup=Counter((r['source_label'],r['source_patient_id']) for r in p['pad'])
    people={d:{r['source_patient_id'] for r in p['pad'] if r['source_label']==d} for d in ('BCC','SCC','MEL')}
    mass=torch.tensor([1/(3*len(people[r['source_label']])*subgroup[r['source_label'],r['source_patient_id']]) for r in p['pad']],dtype=torch.float64)
    assert np.allclose(mass.numpy(),e.pad_weights(p).numpy(),atol=1e-15,rtol=0)
    for d in people: assert abs(float(mass[[r['source_label']==d for r in p['pad']]].sum())-1/3)<1e-12
    for epoch in range(1,4):
        control=torch.multinomial(torch.tensor([.9/4043]*4043+[.1/807]*807,dtype=torch.float64),4043,True,generator=torch.Generator().manual_seed(42+epoch)).tolist()
        positions=[i for i,j in enumerate(control) if j<4043]
        order=torch.randperm(len(positions),generator=torch.Generator().manual_seed(424200+epoch)).tolist()
        slots=sorted(positions[i] for i in order[:202])
        padids=torch.multinomial(mass,202,True,generator=torch.Generator().manual_seed(5000+epoch)).tolist()
        pad=control.copy()
        for position,i in zip(slots,padids): pad[position]=4850+i
        assert len(slots)==202 and sum(i>=4850 for i in pad)==202
        assert all(control[j]==pad[j] for j in range(4043) if j not in slots)
        for b,ids in [('control',control),('pad',pad)]:
            saved=history[b][epoch-1]
            assert saved['replaced_positions']==slots
            assert saved['indices_sha256']==hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()
            assert saved['source_draws']==dict(Counter(rr[i].get('source','original') for i in ids))
            assert saved['pad_subtype_draws']==dict(Counter(rr[i]['source_label'] for i in ids if i>=4850))
            assert saved['actual_updates']==saved['attempted_updates']==253
        assert history['control'][epoch-1]['shared_augmented_stream_sha256']==history['pad'][epoch-1]['shared_augmented_stream_sha256']
        # Directly check augmentation of a shared sample on both datasets.
        position=next(j for j in range(4043) if j not in slots)
        ca=e.PairedDataset(rr,control,epoch,slots)[position]; cb=e.PairedDataset(rr,pad,epoch,slots)[position]
        assert torch.equal(ca[0],cb[0]) and ca[1:]==cb[1:]
    for b,report in reports.items():
        assert report['actual_updates']==759 and report['epochs']==3
        assert report['initial_checkpoint_sha256']==p['initial_checkpoint_sha256']
        assert np.allclose(report['class_weights'],expected,atol=2e-7,rtol=0)
        assert report['class_counts']==count.astype(int).tolist()
        assert report['checkpoint_sha256']==lock['checkpoint_sha256'][b]==sha256_file(e.MODELS/b/'final_model.pth')
    trials={r['name']:r for r in lock['trials']}
    for split in e.prior.SPLITS:
        rows=p['splits'][split]; y=np.asarray([CLASSES.index(r['label']) for r in rows])
        with np.load(out/(split+'.npz')) as z:
            assert z['paths'].tolist()==[r['path'] for r in rows] and np.array_equal(z['truth'],y)
            ref=e.prior.baseline(split,rows)['old_classwise']; assert np.allclose(z['old_classwise'],ref,atol=1e-12,rtol=0)
            for b in e.BRANCHES:
                prob=.75*ref+.25*z[b+'_resnet']; prob/=prob.sum(1,keepdims=True)
                assert np.allclose(prob,z[b+'_mix25'],atol=1e-12,rtol=0)
            for name in e.METHODS:
                assert np.isfinite(z[name]).all() and (z[name]>=0).all() and np.allclose(z[name].sum(1),1,atol=1e-6)
                verify_score(z[name],y,result['results'][split][name])
            assert result['results'][split]['validation_selected']==result['results'][split][lock['selected']]
            if split in e.prior.SPLITS[:2]:
                for name,t in trials.items(): assert t[split]==result['results'][split][name]
            else: assert (out/'selection_locked.json').stat().st_mtime_ns<(out/(split+'.npz')).stat().st_mtime_ns
    with np.load(out/'pad_validation.npz') as z:
        assert z['paths'].tolist()==[r['path'] for r in p['pad_validation']]
        w=np.asarray(p['reference_weights']); ref=(1-w)*z['efficientnet_b0']+w*z['convnext_tiny']; ref/=ref.sum(1,keepdims=True)
        assert np.allclose(ref,z['old_classwise'],atol=1e-12,rtol=0)
        for b in e.BRANCHES:
            q=.75*ref+.25*z[b+'_resnet']; q/=q.sum(1,keepdims=True)
            assert np.allclose(q,z[b+'_mix25'],atol=1e-12,rtol=0)
        padmetrics={n:independent_cancer(z[n],p['pad_validation']) for n in e.METHODS}
        for n,m in padmetrics.items(): assert m==result['pad_validation'][n]
    for n,t in trials.items():
        assert t['pad_validation']==padmetrics[n]
        base=padmetrics['old_classwise']; item=padmetrics[n]
        eligible=e.prior.eligible(t,trials['old_classwise']) and item['non_cancer_flag_rate']<=base['non_cancer_flag_rate']+1e-12 and all(item['by_diagnosis'][d]['flag_rate']>=base['by_diagnosis'][d]['flag_rate']-1e-12 for d in ('BCC','SCC','MEL'))
        assert t['eligible']==bool(eligible)
    selected=sorted([t for t in trials.values() if t['eligible']],key=e.prior.rank)[0]['name']
    assert selected==lock['selected']==result['selected']
    # Actual student/parent inference at identical batch16positions.
    torch.set_num_threads(4)
    members=[dict(path=e.MODELS/b/'final_model.pth',architecture='resnet50',name=b+'_resnet') for b in e.BRANCHES]
    members+=[dict(path=root/m['path'],architecture=m['architecture'],name=m['architecture']) for m in p['parent_members']]
    for split in ['original_validation','pad_validation']:
        rows=p['pad_validation'] if split=='pad_validation' else p['splits'][split]
        normalized=[dict(r,label=r.get('label') or 'SkinCancer') for r in rows[:16]]
        ds=ImageSampleDataset(e.prior.samples(normalized),evaluation_transform()); x=torch.stack([ds[i][0] for i in range(16)]).cuda()
        for member in members:
            if split=='original_validation' and member['name'] not in ('control_resnet','pad_resnet'): continue
            cp=torch.load(member['path'],map_location='cpu',weights_only=False); model=build_model(member['architecture'],8,pretrained=False); model.load_state_dict(cp['model_state_dict']); del cp; model.cuda().eval()
            with torch.inference_mode(): prob=model(x).softmax(1).cpu().numpy()
            with np.load(out/(split+'.npz')) as z: assert np.allclose(prob,z[member['name']][:16],atol=2e-5,rtol=0),member['name']
            del model; torch.cuda.empty_cache()
    save_json(out/'verification.json',dict(status='PASS',protocol_sha256=sha256_file(out/'protocol.json'),results_sha256=sha256_file(out/'results.json'),
        actual_updates={b:reports[b]['actual_updates'] for b in e.BRANCHES},shared_augmentation_matches=True,
        independent_paired_sampler=True,independent_metrics_fusion=True,actual_inference_checked=True,selected=selected,
        scope='Verifies matched implementation/provenance, not independent clinical improvement.'))
    print(e.read(out/'verification.json'),flush=True)


if __name__=='__main__': main()
