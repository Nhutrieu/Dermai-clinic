"""Frozen 15-checkpoint transfer comparison on previously inspected sources.

No training, temperature fit, threshold fit, weight search or deployment.
Average the five per-fold classwise references, then fixed 75:25 with ResNet.
These are previously inspected source slices, not a fresh independent test.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch

from common import CLASSES,ImageSample,ImageSampleDataset,build_model,evaluation_transform,save_json,sha256_file
from train_v2 import BkNode,dhash,make_loader
from evaluate_new_ensemble_holdout import read_new_samples
from evaluate_scene_grouped_oof_classwise_fusion import classwise_blend
from evaluate_scene_grouped_oof_ensemble import score

ROOT=Path(__file__).resolve().parents[2]
CV=ROOT/'ai-service/reports/original_eight_resnet50_cv_seed42'
F0=ROOT/'ai-service/reports/original_eight_resnet50_pilot_fold0_seed42'
OUT=ROOT/'ai-service/reports/original_eight_resnet_transfer_seed42'
OUTER=ROOT/'ai-service/reports/scene_grouped_oof_folds_seed42.json'
SOURCES={
 'dermacon_in':('SkinDisease/sources/dermacon_in/holdout',986,'cb0c4f2720bfdaa04f13da2dfd159c940c5ae3efb7be6577ee307c63828bb907'),
 'skindisnet_v2':('SkinDisease/sources/skindisnet_v2/holdout',723,'8ec63991effc440b66fb791a852713ade3e4d560c10e0caff3fc52eb63756088'),
}
ARCHS=('efficientnet_b0','convnext_tiny','resnet50')
METHODS=ARCHS+('old_classwise','reference_resnet_w0.25')


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def checkpoint(f,arch):
    if arch=='resnet50':
        stem='original_eight_resnet50_pilot_fold0_seed42' if f==0 else f'original_eight_resnet50_cv_fold{f}_seed42'
    else: stem=f"oof_{'b0' if arch=='efficientnet_b0' else 'convnext'}_fold{f}_seed42"
    return ROOT/'ai-service/candidates'/stem/'best_model.pth'


def register():
    state=read(ROOT/'ai-service/reports/active_research_track.json')
    assert state['active_track']=='original_eight' and state['classes']==CLASSES
    cvp=read(CV/'protocol.json'); cvv=read(CV/'verification.json')
    assert cvv['status']=='PASS' and cvv['protocol_sha256']==sha256_file(CV/'protocol.json')
    assert cvv['results_sha256']==sha256_file(CV/'results.json')
    members=[]; weights=[]; upstream={}
    for f in range(5):
        lockpath=(F0 if f==0 else CV/f'fold_{f}')/'selection_locked.json'; lock=read(lockpath)
        weights.append(lock['reference_weights']); upstream[str(lockpath.relative_to(ROOT))]=sha256_file(lockpath)
        for arch in ARCHS:
            cp=checkpoint(f,arch); selection=cp.parent/'selection_report.json'
            expected=lock['checkpoint_sha256'] if arch=='resnet50' else cvp['sources'][str(cp.relative_to(ROOT))]
            assert sha256_file(cp)==expected
            upstream[str(selection.relative_to(ROOT))]=sha256_file(selection)
            members.append(dict(fold=f,architecture=arch,path=cp.relative_to(ROOT).as_posix(),sha256=expected))
    code=('evaluate_original_eight_resnet_transfer.py','common.py','train_v2.py',
          'evaluate_new_ensemble_holdout.py','evaluate_scene_grouped_oof_classwise_fusion.py','evaluate_scene_grouped_oof_ensemble.py')
    base=dict(classes=CLASSES,cv_protocol_sha256=sha256_file(CV/'protocol.json'),cv_verification_sha256=sha256_file(CV/'verification.json'),
              outer_manifest_sha256=sha256_file(OUTER),members=members,reference_weights=weights,upstream=upstream,
              code_sha256={n:sha256_file(ROOT/'ai-service/training'/n) for n in code},
              methods=list(METHODS),inference='Resize256/CenterCrop224/ImageNet normalization; FP32 eval/inference_mode, GPU softmax, batch16/workers2. Temperature1, no calibration fitting.',
              aggregation='For each fold reconstruct original classwise B0/ConvNeXt reference using locked inner weights and row normalization. Average five reference probability arrays equally; average five ResNet arrays equally; fixed .75 reference+.25 ResNet, row normalize. Single architectures also averaged over their five folds.',
              audit_rule='Before inference, quarantine exact SHA256 matches or dHash64 distance<=3 against any of the5937 original development images. Conservative suspected-duplicate exclusion, not proof of duplication. Original source labels unchanged.',
              sources={k:dict(root=v[0],input_images=v[1],labels_sha256=v[2]) for k,v in SOURCES.items()},
              limitations=['Both sources have already been inspected and informed prior research; descriptive transfer only, not fresh independent confirmation.',
                            'Patient independence against the original pool cannot be fully verified because original patient IDs are missing.',
                            'DermaCon Lupus/SkinCancer have few cases; SkinDisNet covers only Eczema/Tinea with eight-way predictions.',
                            'Five-model bagging per architecture differs from single-outer-fold OOF inference; do not compare its source score directly with5937OOF.',
                            'No source-based tuning, training, new-eight model use, serving changes or pooled cross-source accuracy.'])
    if (OUT/'protocol.json').exists():
        registered=read(OUT/'protocol.json')
        assert all(registered[k]==v for k,v in base.items()),'Registered transfer changed'
        assert sha256_file(OUT/'audit.json')==registered['audit_sha256']
        audit=read(OUT/'audit.json')
    else:
        outer=read(OUTER); known=outer['images']; assert len(known)==5937
        hashes=[]
        for r in known:
            p=ROOT/r['path']; assert sha256_file(p)==r['sha256']; hashes.append(dhash(p))
        tree=BkNode(hashes[0],0)
        for j,h in enumerate(hashes[1:],1): tree.add(h,j)
        digest_paths={r['sha256']:r['path'] for r in known}; audit=dict(radius=3,reference_images=5937,sources={})
        for source,(directory,count,labelsha) in SOURCES.items():
            root=ROOT/directory; labels=root/'labels_no_near.csv'; assert sha256_file(labels)==labelsha
            samples,meta=read_new_samples(root,labels); assert len(samples)==count
            rows=[]; excluded=[]
            for s in samples:
                dh=dhash(s.path); hits=[]; tree.query(dh,3,hits)
                row=dict(path=s.path.relative_to(ROOT).as_posix(),label=CLASSES[s.label],sha256=s.digest,group=s.group_id,dhash64=f'{dh:016x}')
                row['included']=s.digest not in digest_paths and not hits
                if not row['included']:
                    matches=[known[j]['path'] for j in sorted(hits,key=lambda j:(dh^hashes[j]).bit_count())[:5]]
                    excluded.append(dict(**row,exact_match=digest_paths.get(s.digest),near_examples=matches))
                rows.append(row)
            included=[r for r in rows if r['included']]; assert included
            audit['sources'][source]=dict(metadata=meta,input_images=count,images=len(included),cases=len({r['group'] for r in included}),
                 support=dict(Counter(r['label'] for r in included)),rows=rows,excluded=excluded)
            print(json.dumps(dict(audit_source=source,input_images=count,retained=len(included),excluded=len(excluded))),flush=True)
        save_json(OUT/'audit.json',audit)
        registered=dict(base,audit_sha256=sha256_file(OUT/'audit.json')); save_json(OUT/'protocol.json',registered)
    # Re-check frozen label CSVs and all retained/excluded source images on resume.
    for source,d in audit['sources'].items():
        root=ROOT/SOURCES[source][0]; assert sha256_file(root/'labels_no_near.csv')==SOURCES[source][2]
        samples,meta=read_new_samples(root,root/'labels_no_near.csv')
        assert meta==d['metadata'] and [(s.path.relative_to(ROOT).as_posix(),s.digest,CLASSES[s.label],s.group_id) for s in samples]==[(r['path'],r['sha256'],r['label'],r['group']) for r in d['rows']]
    return registered,audit


def infer_member(member,rows):
    path=ROOT/member['path']; assert sha256_file(path)==member['sha256']
    cp=torch.load(path,map_location='cpu',weights_only=False)
    assert cp['classes']==CLASSES and cp['architecture']==member['architecture']
    model=build_model(member['architecture'],8,pretrained=False)
    model.load_state_dict(cp['model_state_dict']); del cp; model.cuda().eval()
    samples=[ImageSample(ROOT/r['path'],CLASSES.index(r['label']),r['sha256'],r['group']) for r in rows]
    loader=make_loader(ImageSampleDataset(samples,evaluation_transform()),16,False,2,True); values=[]
    with torch.inference_mode():
        for x,_ in loader: values.append(model(x.cuda(non_blocking=True)).softmax(1).cpu().numpy())
    p=np.concatenate(values).astype(float); del model,loader; torch.cuda.empty_cache(); return p


def aggregate(raw,weights):
    p={arch:np.mean([raw[(f,arch)] for f in range(5)],axis=0) for arch in ARCHS}
    p['old_classwise']=np.mean([classwise_blend(raw[(f,ARCHS[0])],raw[(f,ARCHS[1])],np.asarray(weights[f])) for f in range(5)],axis=0)
    p['reference_resnet_w0.25']=.75*p['old_classwise']+.25*p['resnet50']
    p['reference_resnet_w0.25']/=p['reference_resnet_w0.25'].sum(1,keepdims=True)
    return p


def source_metrics(p,y):
    m=score(p,y); present=[c for c in CLASSES if m['per_class'][c]['support']>0]
    m['present_classes']=present; m['macro_f1_present_classes']=float(np.mean([m['per_class'][c]['f1'] for c in present]))
    m['correct']=int((p.argmax(1)==y).sum()); return m


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--prepare-only',action='store_true'); args=parser.parse_args()
    torch.set_num_threads(4); protocol,audit=register()
    if args.prepare_only: print(json.dumps(dict(registered=True,sources={s:d['images'] for s,d in audit['sources'].items()})),flush=True); return
    assert torch.cuda.is_available() and not (OUT/'results.json').exists(),'Preserve completed transfer evaluation'
    rows_by_source={s:[r for r in d['rows'] if r['included']] for s,d in audit['sources'].items()}
    rows=[r for rr in rows_by_source.values() for r in rr]; paths=np.asarray([r['path'] for r in rows]); raw={}; upstream_sha=sha256_file(OUT/'protocol.json')
    for member in protocol['members']:
        f,arch=member['fold'],member['architecture']; path=OUT/f'fold_{f}_{arch}.npz'
        if path.exists():
            with np.load(path) as cached:
                assert cached['protocol_sha256'].item()==upstream_sha and np.array_equal(cached['paths'],paths)
                raw[(f,arch)]=cached['probabilities']
        else:
            raw[(f,arch)]=infer_member(member,rows)
            np.savez_compressed(path,paths=paths,probabilities=raw[(f,arch)],protocol_sha256=upstream_sha)
        print(json.dumps(dict(completed_member=f'{arch}_fold{f}',images=len(rows))),flush=True)
    combined=aggregate(raw,protocol['reference_weights']); predictions=[]; sources={}; start=0
    for source,rr in rows_by_source.items():
        end=start+len(rr); truth=np.asarray([CLASSES.index(r['label']) for r in rr])
        sources[source]=dict(images=len(rr),cases=audit['sources'][source]['cases'],excluded=len(audit['sources'][source]['excluded']),
                            results={k:source_metrics(v[start:end],truth) for k,v in combined.items()})
        predictions.extend(dict(**r,source=source,probabilities={k:v[start+j].tolist() for k,v in combined.items()}) for j,r in enumerate(rr))
        start=end
    save_json(OUT/'predictions.json',predictions)
    save_json(OUT/'results.json',dict(scope='Descriptive fixed transfer on previously inspected source slices; not independent confirmation.',
              protocol_sha256=upstream_sha,images=len(rows),sources=sources))
    print(json.dumps(dict(complete=True,sources={s:{k:{f:v[f] for f in ('accuracy','macro_f1','macro_f1_present_classes')} for k,v in d['results'].items()} for s,d in sources.items()})),flush=True)


if __name__=='__main__': main()
