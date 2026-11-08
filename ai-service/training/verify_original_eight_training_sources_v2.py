"""Verify source labels, exact replay exposure, metrics and actual frozen inference."""
from collections import Counter
import numpy as np
import torch
from PIL import Image

import audit_original_eight_training_sources as audit
from common import CLASSES, ImageSampleDataset, build_model, evaluation_transform, save_json, sha256_file
from sklearn.metrics import confusion_matrix


def main():
    root,out=audit.ROOT,audit.OUT; p=audit.read(out/'protocol.json'); meta=audit.read(out/'metadata.json'); result=audit.read(out/'results.json')
    assert p['classes']==CLASSES and len(p['rows'])==4850
    for n,h in p['source_sha256'].items(): assert sha256_file(root/n)==h,n
    for n,h in p['code_sha256'].items(): assert sha256_file(root/'ai-service/training'/n)==h,n
    assert meta['protocol_sha256']==result['protocol_sha256']==sha256_file(out/'protocol.json')
    rows=p['rows']; previous=audit.read(audit.teacher.OUT/'protocol.json'); aux=audit.entries(audit.prior.SUP/'training_candidates.jsonl')
    assert [r['path'] for r in rows]==[r['path'] for r in previous['train']+previous['supplement']]
    assert {r['path'] for r in rows}.isdisjoint(r['path'] for rr in previous['splits'].values() for r in rr)
    assert {r['sha256'] for r in rows}.isdisjoint(r['sha256'] for rr in previous['splits'].values() for r in rr)
    for r in rows:
        assert sha256_file(root/r['path'])==r['sha256']
        with Image.open(root/r['path']) as im: assert im.size==(r['width'],r['height'])
    counts=Counter(); epoch_cells=[]
    mass=torch.tensor([.9/4043]*4043+[.1/807]*807,dtype=torch.float64)
    for ep in range(1,4):
        ids=torch.multinomial(mass,4043,True,generator=torch.Generator().manual_seed(42+ep)).tolist(); counts.update(ids)
        epoch_cells.append({s:{c:sum(rows[i]['source']==s and rows[i]['label']==c for i in ids) for c in CLASSES} for s in sorted({r['source'] for r in rows})})
    assert meta['total_draws']==12129 and meta['unique_seen']==len(counts)
    for ep,saved in enumerate(meta['by_epoch']): assert saved['counts']==epoch_cells[ep]
    for cell in meta['cells']:
        ids=[i for i,r in enumerate(rows) if r['source']==cell['source'] and r['label']==cell['label']]
        assert cell['pool_images']==len(ids) and cell['sampled_draws']==sum(counts[i] for i in ids)
        seen=[i for i in ids if counts[i]>0]
        assert cell['unique_images_seen']==len(seen)
        assert cell['known_cases']==len({rows[i]['source_case_id'] for i in ids if rows[i]['source_case_id']})
        assert cell['source_labels']==dict(Counter(rows[i]['source_label'] for i in ids))
        assert cell['image_groups']==len({rows[i]['group'] for i in ids})
        assert cell['unique_groups_seen']==len({rows[i]['group'] for i in seen})
        assert cell['known_cases_seen']==len({rows[i]['source_case_id'] for i in seen if rows[i]['source_case_id']})
        assert cell['images_without_confirmed_patient_id']==sum(not rows[i]['patient_id_confirmed'] for i in ids)
    for r,a in zip(rows[4043:],aux):
        assert r['source_label']==a['source_label'] and r['source_case_id']==a['source_case_id']
        assert r['label']==a['label'] and r['sha256']==a['sha256']
    pp={}
    for m in p['members']:
        assert sha256_file(root/m['path'])==m['sha256']
        with np.load(out/(m['name']+'.npz')) as z:
            assert z['paths'].tolist()==[r['path'] for r in rows]
            assert z['protocol_sha256'].item()==sha256_file(out/'protocol.json')
            pp[m['name']]=z['probabilities']
    w=np.asarray(p['reference_weights']); ref=(1-w)*pp['efficientnet_b0']+w*pp['convnext_tiny']; pp['old_classwise']=ref/ref.sum(1,keepdims=True)
    y=np.asarray([CLASSES.index(r['label']) for r in rows])
    for source,rr in result['results'].items():
        mask=np.asarray([r['source']==source for r in rows]); yy=y[mask]
        for name,m in rr.items():
            prob=pp[name][mask]; pred=prob.argmax(1)
            assert np.isfinite(prob).all() and (prob>=0).all() and np.allclose(prob.sum(1),1,atol=1e-6)
            cm=confusion_matrix(yy,pred,labels=np.arange(8)); assert cm.tolist()==m['confusion_matrix']
            tp=cm.diagonal(); support=cm.sum(1); predicted=cm.sum(0)
            f1=np.divide(2*tp,support+predicted,out=np.zeros(8,dtype=float),where=(support+predicted)>0)
            assert abs(float(tp.sum()/len(yy))-m['accuracy'])<1e-12
            assert abs(float(f1.mean())-m['macro_f1'])<1e-12
            assert abs(float(f1.sum()/np.count_nonzero(support))-m['macro_f1_present_classes'])<1e-12
            for k,c in enumerate(CLASSES):
                assert m['per_class'][c]['support']==int(support[k])
                assert abs(m['per_class'][c]['recall']-(float(tp[k]/support[k]) if support[k] else 0))<1e-12
                assert abs(m['per_class'][c]['precision']-(float(tp[k]/predicted[k]) if predicted[k] else 0))<1e-12
                assert abs(m['per_class'][c]['f1']-f1[k])<1e-12
                assert m['false_positives'][c]==int(predicted[k]-tp[k])
    review=audit.read(out/'review_candidates.json'); bypath={r['path']:i for i,r in enumerate(rows)}
    for r in review:
        i=bypath[r['path']]; assert r['label']==rows[i]['label']
        for name,pr in r['predictions'].items():
            assert pr['label']==CLASSES[int(pp[name][i].argmax())]
            assert abs(pr['confidence']-float(pp[name][i].max()))<1e-12
        assert r['predictions']['supplement_resnet']['label']!=r['label']
    # Match original batch32and original sample positions to avoid batch-size
    # floating-point differences. No relaxed probability tolerance.
    torch.set_num_threads(4); selected=[]
    for source in sorted({r['source'] for r in rows}): selected.extend([i for i,r in enumerate(rows) if r['source']==source][:4])
    batch_starts=sorted({(i//32)*32 for i in selected})
    checked_differences={}
    for m in p['members']:
        cp=torch.load(root/m['path'],map_location='cpu',weights_only=False)
        model=build_model(m['architecture'],8,pretrained=False); model.load_state_dict(cp['model_state_dict']); del cp
        model.cuda().eval(); difference=0.
        for start in batch_starts:
            indices=list(range(start,min(start+32,len(rows))))
            dataset=ImageSampleDataset(audit.prior.samples([rows[i] for i in indices]),evaluation_transform())
            x=torch.stack([dataset[i][0] for i in range(len(dataset))]).cuda()
            with torch.inference_mode(): prob=model(x).softmax(1).cpu().numpy()
            difference=max(difference,float(np.abs(prob-pp[m['name']][indices]).max()))
            assert np.allclose(prob,pp[m['name']][indices],atol=2e-5,rtol=0),m['name']
        checked_differences[m['name']]=difference
        del model; torch.cuda.empty_cache()
    verification_protocol=audit.read(out/'verification_protocol_v2.json')
    for name,h in verification_protocol['source_sha256'].items(): assert sha256_file(root/name)==h,name
    assert sha256_file(root/'ai-service/training/verify_original_eight_training_sources_v2.py')==verification_protocol['verifier_sha256']
    save_json(out/'verification.json',dict(status='PASS',protocol_sha256=sha256_file(out/'protocol.json'),
        result_sha256=sha256_file(out/'results.json'),metadata_sha256=sha256_file(out/'metadata.json'),
        train_images=4850,train_only=True,actual_frozen_inference_checked=True,sampler_reconstructed=True,
        inference_max_abs_difference=checked_differences,matched_batch_size=32,
        verification_revision=2,verification_protocol_sha256=sha256_file(out/'verification_protocol_v2.json'),
        independently_recomputed_metrics=True,scope='Implementation/data provenance checks, not label correctness or generalization.'))
    print(audit.read(out/'verification.json'))


if __name__=='__main__': main()
