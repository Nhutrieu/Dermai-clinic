"""Descriptive train/validation audit, no fitting and no held-role score access."""
import argparse
import json
from collections import Counter

import numpy as np
import torch
from scipy.special import expit, softmax

from common import CLASSES, save_json, sha256_file
from evaluate_scene_grouped_oof_classwise_fusion import classwise_blend
from evaluate_scene_grouped_oof_ensemble import score
import pilot_original_eight_frozen_cancer_head as head

ROOT = head.ROOT
OUT = ROOT / 'ai-service/reports/original_eight_cancer_head_disagreement_audit_20261014'
TRAIN = ROOT / 'ai-service/reports/original_eight_training_source_audit_20261013'
SPLITS = ('original_train', 'supplement_train', 'original_validation', 'dermacon_validation', 'pad_validation')
METHODS = ('old_classwise', 'binary_cancer25', 'subtype_cancer25')


def register():
    assert not (OUT/'protocol.json').exists(), 'Preserve registered audit'
    h = head.read(head.OUT/'protocol.json'); head.check_frozen(h)
    assert head.read(head.OUT/'verification.json')['status'] == 'PASS'
    t = head.read(TRAIN/'protocol.json'); v = head.read(TRAIN/'verification.json')
    assert v['status'] == 'PASS' and v['protocol_sha256'] == sha256_file(TRAIN/'protocol.json')
    rows = t['rows']; assert len(rows) == 4850
    old = head.read(head.BASE/'protocol.json')
    assert [r['path'] for r in rows] == [r['path'] for r in old['train']+old['supplement']]
    splits = dict(original_train=rows[:4043], supplement_train=rows[4043:])
    for s in ('original_validation', 'dermacon_validation'):
        splits[s] = [dict(r, source='SCIN' if '/scin-v1/' in r['path'] else
                         ('DermaCon-IN-v1' if s=='dermacon_validation' else 'Original-local')) for r in h['splits'][s]]
    splits['pad_validation'] = [dict(r,source='PAD-UFES-20',label=r['diagnostic']) for r in h['pad_validation']]
    paths = [head.OUT/'protocol.json',head.OUT/'verification.json',TRAIN/'protocol.json',TRAIN/'verification.json',
             TRAIN/'efficientnet_b0.npz',TRAIN/'convnext_tiny.npz',
             head.MODELS/'binary.npz',head.MODELS/'subtype.npz']
    paths += [head.OUT/(s+'.npz') for s in ('original_validation','dermacon_validation','pad_validation')]
    frozen = dict(h['sources'])
    frozen.update({p.relative_to(ROOT).as_posix():sha256_file(p) for p in paths})
    frozen_code = dict(h['code_sha256'])
    for n in ('audit_original_eight_cancer_head_disagreements.py','verify_original_eight_cancer_head_disagreements.py'):
        frozen_code[n] = sha256_file(ROOT/'ai-service/training'/n)
    p = dict(classes=CLASSES, splits=splits, reference_weights=t['reference_weights'],
        initial_checkpoint=h['initial_checkpoint'], sources=frozen, code_sha256=frozen_code,
        roles=SPLITS, training=False, relabeling=False,
        scope='Post-hoc descriptive train/validation-only disagreement audit. No held-role NPZ or result scores loaded. No threshold/weight fit or diagnosis verification.',
        decision_rule='Freeze old reference and both existing heads, shared cancer-mass weight .25 and standalone .5 threshold. Count correct-to-wrong/wrong-to-correct and cancer false flags by true label/source. Train fit is not generalization.',
        limits=['SCIN labels are retrospective differential annotations, not expert-confirmed diagnoses.',
                'Original-local source labels and patient IDs have limited provenance; group IDs do not guarantee patient IDs.',
                'Validation/checkpoint and sources have already been investigated; audit cannot validate a new model.',
                'NEV/SEK/ACK do not map to original eight diagnoses. PAD metrics are flags, not eight-way accuracy.'])
    save_json(OUT/'protocol.json',p)
    return p


def head_scores(x):
    values={}
    for branch in head.BRANCHES:
        with np.load(head.MODELS/(branch+'.npz')) as z:
            logits=((x.astype(float)-z['mean'])/z['scale'])@z['coefficients'].T+z['intercept']
            values[branch]=expit(logits[:,0]) if branch=='binary' else softmax(logits,axis=1)[:,:3].sum(1)
    return values


def flags_and_changes(rows,ref,values,aux,ids):
    ids=np.asarray(ids,dtype=int); truth=np.array([r['label'] for r in rows]); rp=ref.argmax(1)
    is_pad=rows[0]['source']=='PAD-UFES-20'
    d=dict(images=len(ids),groups=len({rows[i]['group'] for i in ids}),
           raw_auxiliary_flags={b: int((a[ids]>=.5).sum()) for b,a in aux.items()},
           auxiliary_probability_quantiles={b:np.quantile(a[ids],[0,.25,.5,.75,1]).tolist() for b,a in aux.items()},
           cancer_flags={},transitions={})
    for name,q in values.items():
        pred=q.argmax(1); d['cancer_flags'][name]=int((pred[ids]==5).sum())
        if not is_pad:
            y=np.array([CLASSES.index(rows[i]['label']) for i in ids]); a=rp[ids]; b=pred[ids]
            d['transitions'][name]=dict(changed=int((a!=b).sum()),
                correct_to_wrong=int(((a==y)&(b!=y)).sum()),wrong_to_correct=int(((a!=y)&(b==y)).sum()),
                wrong_to_other_wrong=int(((a!=y)&(b!=y)&(a!=b)).sum()),
                newly_flagged_cancer=int(((a!=5)&(b==5)).sum()),removed_cancer_flag=int(((a==5)&(b!=5)).sum()))
        else:
            a=rp[ids]; b=pred[ids]
            d['transitions'][name]=dict(changed=int((a!=b).sum()),
                newly_flagged_cancer=int(((a!=5)&(b==5)).sum()),removed_cancer_flag=int(((a==5)&(b!=5)).sum()))
    return d


def analyze_split(split,rows,ref,aux,features=None,original_resnet=None):
    values=dict(old_classwise=ref)
    for b,c in aux.items(): values[b+'_cancer25']=head.fuse(ref,c)
    cells=[]
    for source,label in sorted({(r['source'],r['label']) for r in rows}):
        ids=[i for i,r in enumerate(rows) if (r['source'],r['label'])==(source,label)]
        cells.append(dict(source=source,label=label,**flags_and_changes(rows,ref,values,aux,ids)))
    total=flags_and_changes(rows,ref,values,aux,range(len(rows)))
    metrics={} if split=='pad_validation' else {n:score(q,np.array([CLASSES.index(r['label']) for r in rows])) for n,q in values.items()}
    report=dict(images=len(rows),scope='PAD flags only' if split=='pad_validation' else
                ('Apparent train fit only' if split.endswith('_train') else 'Previously used validation'),
                total=total,cells=cells,metrics=metrics)
    arrays=dict(paths=[r['path'] for r in rows],**values,**{b+'_cancer':c for b,c in aux.items()})
    if features is not None: arrays.update(features=features,original_resnet=original_resnet)
    np.savez_compressed(OUT/(split+'.npz'),**arrays)
    rp=ref.argmax(1); review=[]
    if split!='pad_validation':
        y=np.array([CLASSES.index(r['label']) for r in rows]); fp=values['subtype_cancer25'].argmax(1)
        for category,mask in [('correct_to_wrong',(rp==y)&(fp!=y)),('wrong_to_correct',(rp!=y)&(fp==y)),
                              ('other_change',(rp!=y)&(fp!=y)&(fp!=rp))]:
            for i in np.flatnonzero(mask):
                item=dict(rows[i]);item.update(role=split,transition=category,
                    old_prediction=CLASSES[int(rp[i])],fused_prediction=CLASSES[int(fp[i])],
                    old_cancer_probability=float(ref[i,5]),auxiliary_cancer_probability=float(aux['subtype'][i]),
                    fused_cancer_probability=float(values['subtype_cancer25'][i,5]),
                    diagnosis_verified=False,automatic_relabel=False)
                review.append(item)
    return report,review


def run(p):
    assert not (OUT/'results.json').exists(),'Preserve completed audit'
    head.check_frozen(p); torch.set_num_threads(4)
    rr=p['splits']['original_train']+p['splits']['supplement_train']
    extractor=head.Features(p); x,raw=extractor.infer(rr)
    aux=head_scores(x); parents=[]
    for name in ('efficientnet_b0','convnext_tiny'):
        with np.load(TRAIN/(name+'.npz')) as z:
            assert z['paths'].tolist()==[r['path'] for r in rr]
            parents.append(z['probabilities'])
    ref=classwise_blend(*parents,np.array(p['reference_weights']))
    reports={}; review=[]
    for split,lo,hi in [('original_train',0,4043),('supplement_train',4043,4850)]:
        reports[split],candidates=analyze_split(split,p['splits'][split],ref[lo:hi],
            {b:a[lo:hi] for b,a in aux.items()},x[lo:hi],raw[lo:hi]); review.extend(candidates)
        print(json.dumps(dict(audited=split,images=hi-lo)),flush=True)
    del extractor; torch.cuda.empty_cache()
    for split in ('original_validation','dermacon_validation','pad_validation'):
        with np.load(head.OUT/(split+'.npz')) as z:
            assert z['paths'].tolist()==[r['path'] for r in p['splits'][split]]
            reports[split],candidates=analyze_split(split,p['splits'][split],z['old_classwise'],
                {b:z[b+'_cancer'] for b in head.BRANCHES}); review.extend(candidates)
    with (OUT/'prediction_disagreements.jsonl').open('w',encoding='utf-8') as f:
        for r in review: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    head.check_frozen(p)
    save_json(OUT/'results.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),results=reports,
        fitting=False,no_held_score_access=True,diagnoses_not_verified=True,
        review_images=len(review),disagreements_sha256=sha256_file(OUT/'prediction_disagreements.jsonl')))
    print(json.dumps(dict(complete=True,review_candidates=len(review))),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    p=head.read(OUT/'protocol.json') if args.resume else register()
    head.check_frozen(p)
    if args.prepare_only: print('Registered train/validation audit.');return
    run(p)


if __name__=='__main__':main()
