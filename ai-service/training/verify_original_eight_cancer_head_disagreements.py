"""Independent aggregate audit of frozen head train/validation disagreements."""
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.special import expit,softmax
from sklearn.metrics import accuracy_score,confusion_matrix,f1_score

from common import CLASSES,save_json,sha256_file
import audit_original_eight_cancer_head_disagreements as audit


def main():
    p=audit.head.read(audit.OUT/'protocol.json');audit.head.check_frozen(p)
    r=audit.head.read(audit.OUT/'results.json')
    assert r['protocol_sha256']==sha256_file(audit.OUT/'protocol.json')
    assert not r['fitting'] and r['no_held_score_access'] and r['diagnoses_not_verified']
    assert set(r['results'])==set(audit.SPLITS)
    candidates=[json.loads(line) for line in (audit.OUT/'prediction_disagreements.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(candidates)==r['review_images'] and sha256_file(audit.OUT/'prediction_disagreements.jsonl')==r['disagreements_sha256']
    lookup={(x['role'],x['path']):x for x in candidates};assert len(lookup)==len(candidates)
    expected_review=set();maxerr=0.;flags={}
    for split in audit.SPLITS:
        rows=p['splits'][split];m=r['results'][split];is_pad=split=='pad_validation'
        for row in rows:assert sha256_file(audit.ROOT/row['path'])==row['sha256']
        with np.load(audit.OUT/(split+'.npz')) as z:
            assert z['paths'].tolist()==[x['path'] for x in rows]
            ref=z['old_classwise'];yp=ref.argmax(1)
            truth=None if is_pad else np.array([CLASSES.index(x['label']) for x in rows])
            for b in audit.head.BRANCHES:
                c=z[b+'_cancer'];q=z[b+'_cancer25'];pred=q.argmax(1)
                expected=np.zeros_like(ref);expected[:,5]=.75*ref[:,5]+.25*c
                for k in range(8):
                    if k!=5:expected[:,k]=ref[:,k]*(1-expected[:,5])/(1-ref[:,5])
                delta=float(np.abs(expected-q).max());maxerr=max(maxerr,delta);assert delta<1e-6
                assert np.allclose(q.sum(1),1,atol=1e-6)
                if split.endswith('_train'):
                    with np.load(audit.head.MODELS/(b+'.npz')) as h:
                        logits=((z['features'].astype(float)-h['mean'])/h['scale'])@h['coefficients'].T+h['intercept']
                        cancer=expit(logits[:,0]) if b=='binary' else softmax(logits,axis=1)[:,:3].sum(1)
                    assert np.allclose(c,cancer,atol=1e-7)
                if not is_pad:
                    metrics=m['metrics'][b+'_cancer25']
                    assert abs(metrics['accuracy']-accuracy_score(truth,pred))<1e-12
                    assert abs(metrics['macro_f1']-f1_score(truth,pred,labels=np.arange(8),average='macro',zero_division=0))<1e-12
                    assert np.array_equal(metrics['confusion_matrix'],confusion_matrix(truth,pred,labels=np.arange(8)))
                for cell in m['cells']+[dict(source=None,label=None,**m['total'])]:
                    ids=np.array([i for i,row in enumerate(rows) if cell['source'] is None or
                                  (row['source'],row['label'])==(cell['source'],cell['label'])])
                    assert len(ids)==cell['images'] and len({rows[i]['group'] for i in ids})==cell['groups']
                    assert cell['raw_auxiliary_flags'][b]==int((c[ids]>=.5).sum())
                    assert np.allclose(cell['auxiliary_probability_quantiles'][b],np.quantile(c[ids],[0,.25,.5,.75,1]))
                    assert cell['cancer_flags'][b+'_cancer25']==int((pred[ids]==5).sum())
                    assert cell['cancer_flags']['old_classwise']==int((yp[ids]==5).sum())
                    counts=Counter()
                    for i in ids:
                        if yp[i]!=pred[i]:counts['changed']+=1
                        if yp[i]!=5 and pred[i]==5:counts['newly_flagged_cancer']+=1
                        if yp[i]==5 and pred[i]!=5:counts['removed_cancer_flag']+=1
                        if not is_pad:
                            if yp[i]==truth[i] and pred[i]!=truth[i]:counts['correct_to_wrong']+=1
                            if yp[i]!=truth[i] and pred[i]==truth[i]:counts['wrong_to_correct']+=1
                            if yp[i]!=truth[i] and pred[i]!=truth[i] and yp[i]!=pred[i]:counts['wrong_to_other_wrong']+=1
                    stored=cell['transitions'][b+'_cancer25']
                    assert all(stored[k]==counts[k] for k in stored)
                if b=='subtype' and not is_pad:
                    for i in np.flatnonzero(yp!=pred):
                        key=(split,rows[i]['path']);expected_review.add(key);item=lookup[key]
                        assert not item['diagnosis_verified'] and not item['automatic_relabel']
                        category='correct_to_wrong' if yp[i]==truth[i] else ('wrong_to_correct' if pred[i]==truth[i] else 'other_change')
                        assert item['transition']==category and item['old_prediction']==CLASSES[yp[i]] and item['fused_prediction']==CLASSES[pred[i]]
            flags[split]={n:m['total']['cancer_flags'][n] for n in audit.METHODS}
    assert expected_review==set(lookup)
    # Actual batch forward from original train matches stored new feature cache.
    extractor=audit.head.Features(p);features,raw=extractor.infer(p['splits']['original_train'][:16])
    with np.load(audit.OUT/'original_train.npz') as z:
        assert np.allclose(features,z['features'][:16],atol=1e-6,rtol=1e-6)
        assert np.allclose(raw,z['original_resnet'][:16],atol=1e-7)
    verification=dict(status='PASS',protocol_sha256=sha256_file(audit.OUT/'protocol.json'),
        results_sha256=sha256_file(audit.OUT/'results.json'),verifier_sha256=sha256_file(Path(__file__)),
        review_rows=len(candidates),source_label_aggregate_counts_verified=True,
        unchanged_model_and_source_hashes=True,actual_batch_reinference=True,
        maximum_fusion_error=maxerr,role_cancer_flags=flags,no_fitting=True,
        scope='Descriptive audit implementation only; diagnoses and generalization not verified.')
    save_json(audit.OUT/'verification.json',verification);print(json.dumps(verification),flush=True)


if __name__=='__main__':main()
