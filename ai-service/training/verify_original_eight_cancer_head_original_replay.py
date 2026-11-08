"""Verify original binary targets, source weights, frozen scaler and fusion."""
from collections import Counter
from pathlib import Path
import json

import numpy as np
from scipy.special import expit
from sklearn.metrics import accuracy_score,confusion_matrix,f1_score,precision_recall_fscore_support

from common import CLASSES,save_json,sha256_file
from verify_original_eight_frozen_cancer_head import guard
import pilot_original_eight_cancer_head_original_replay as pilot


def main():
    p=pilot.prior.read(pilot.OUT/'protocol.json');pilot.prior.check_frozen(p)
    results=pilot.prior.read(pilot.OUT/'results.json');lock=pilot.prior.read(pilot.OUT/'selection_locked.json')
    assert results['protocol_sha256']==lock['protocol_sha256']==sha256_file(pilot.OUT/'protocol.json')
    assert results['selection_sha256']==sha256_file(pilot.OUT/'selection_locked.json')
    rr=p['original_train'];pad=p['pad_train']
    groups={c:len({r['group'] for r in rr if r['label']==c}) for c in CLASSES}
    count=Counter((r['label'],r['group']) for r in rr)
    mass=np.array([(.5 if r['label']=='SkinCancer' else .5/7)/groups[r['label']]/count[r['label'],r['group']]*1169*.25 for r in rr])
    original_y=np.array([r['label']=='SkinCancer' for r in rr],dtype=int)
    pad_y=np.array([r['source_label'] in ('BCC','SCC','MEL') for r in pad],dtype=int)
    with np.load(pilot.prior.OUT/'train_features.npz') as z:padw=z['sample_weights'].copy()
    heads={}
    for branch in pilot.BRANCHES:
        with np.load(pilot.OUT/(branch+'_training_targets.npz')) as z:
            expected_y=pad_y if branch=='control' else np.concatenate([pad_y,original_y])
            expected_w=padw if branch=='control' else np.concatenate([.75*padw,mass])
            assert np.array_equal(expected_y,z['truth']) and np.allclose(expected_w,z['sample_weights'],atol=1e-12)
            assert np.isclose(z['sample_weights'].sum(),1169) and np.isclose(z['sample_weights'][z['truth']==1].sum(),584.5)
        assert sha256_file(pilot.MODELS/(branch+'.npz'))==lock['checkpoints'][branch]
        with np.load(pilot.MODELS/(branch+'.npz')) as z:heads[branch]={k:z[k].copy() for k in z.files}
    with np.load(pilot.prior.MODELS/'binary.npz') as z:
        for branch in pilot.BRANCHES:
            for key in ('mean','scale'):assert np.array_equal(heads[branch][key],z[key])
        for key in ('coefficients','intercept'):assert np.allclose(heads['control'][key],z[key],atol=1e-7)
    maxerr=0.
    for split in (*pilot.prior.pad.prior.SPLITS,'pad_validation'):
        rr=p['pad_validation'] if split=='pad_validation' else p['splits'][split]
        with np.load(pilot.prior.OUT/(split+'.npz')) as parent, np.load(pilot.OUT/(split+'.npz')) as z:
            assert z['paths'].tolist()==parent['paths'].tolist()==[r['path'] for r in rr]
            ref=z['old_classwise'];assert np.array_equal(ref,parent['old_classwise'])
            for branch in pilot.BRANCHES:
                h=heads[branch];logits=((parent['features'].astype(float)-h['mean'])/h['scale'])@h['coefficients'].T+h['intercept']
                c=expit(logits[:,0]);delta=float(np.abs(c-z[branch+'_cancer']).max());maxerr=max(maxerr,delta);assert delta<1e-6
                q=np.empty_like(ref);q[:,5]=.75*ref[:,5]+.25*c
                other=[k for k in range(8) if k!=5]
                q[:,other]=ref[:,other]/(1-ref[:,5])[:,None]*(1-q[:,5])[:,None]
                assert np.allclose(q,z[branch+'_cancer25'],atol=1e-6) and np.allclose(q.sum(1),1,atol=1e-6)
            for name in pilot.METHODS:
                pred=z[name].argmax(1)
                if split=='pad_validation':
                    m=results['pad_validation'][name];neg=np.array([r['diagnostic'] in ('ACK','NEV','SEK') for r in rr])
                    assert m['non_cancer_flagged']==int(((pred==5)&neg).sum())
                    for diagnosis in ('BCC','SCC','MEL','ACK','NEV','SEK'):
                        mask=np.array([r['diagnostic']==diagnosis for r in rr]);d=m['by_diagnosis'][diagnosis]
                        assert int(((pred==5)&mask).sum())==d['flagged'] and mask.sum()==d['images']
                else:
                    y=np.array([CLASSES.index(r['label']) for r in rr]);assert np.array_equal(y,z['truth'])
                    m=results['results'][split][name]
                    assert abs(m['accuracy']-accuracy_score(y,pred))<1e-12
                    assert abs(m['macro_f1']-f1_score(y,pred,labels=np.arange(8),average='macro',zero_division=0))<1e-12
                    assert np.array_equal(m['confusion_matrix'],confusion_matrix(y,pred,labels=np.arange(8)))
                    prec,rec,f1,support=precision_recall_fscore_support(y,pred,labels=np.arange(8),zero_division=0)
                    for k,cname in enumerate(CLASSES):
                        for field,value in [('precision',prec[k]),('recall',rec[k]),('f1',f1[k]),('support',support[k])]:assert abs(m['per_class'][cname][field]-value)<1e-12
    failures={};t=lock['trials'];ref=t['old_classwise'];pm=results['pad_validation']
    for name,m in t.items():
        failures[name]=guard(m['original_validation'],m['dermacon_validation'],ref['original_validation'],ref['dermacon_validation'],pm[name],pm['old_classwise'])
        assert m['eligible']==(not failures[name])
    eligible=[v for n,v in t.items() if not failures[n]]
    assert sorted(eligible,key=pilot.prior.pad.prior.rank)[0]['name']==lock['selected']==results['selected']
    v=dict(status='PASS',protocol_sha256=sha256_file(pilot.OUT/'protocol.json'),results_sha256=sha256_file(pilot.OUT/'results.json'),
        verifier_sha256=sha256_file(Path(__file__)),original_targets_verified=True,original_rows=4043,pad_rows=1169,
        total_training_mass_both=1169,unchanged_scaler_and_backbone=True,control_reproduced_prior=True,
        maximum_probability_reconstruction_error=maxerr,guard_failures=failures,selected=lock['selected'],
        scope='Exploratory source-replay pilot implementation verified, not clinical accuracy or fresh independent validation.')
    save_json(pilot.OUT/'verification.json',v);print(json.dumps(v),flush=True)


if __name__=='__main__':main()
