"""Audit supplemental old-eight training data against protected images.

Reuses the590-image published-case DermaCon development train split and newly
acquired corrected Fitz-C train-only Lupus atlas photos. No model fitting or
change to the5937image OOF benchmark. Case/similarity-linked quarantine.
"""
import csv
import hashlib
import json
from collections import Counter,defaultdict
from pathlib import Path

import numpy as np
from PIL import Image,ImageOps

from common import CLASSES,IMAGE_EXTENSIONS,save_json,sha256_file
from train_v2 import BkNode,UnionFind,dhash
from evaluate_new_ensemble_holdout import read_new_samples

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'ai-service/reports/original_eight_supplement_audit_20261013'
RAW_REPORT=ROOT/'ai-service/reports/original_eight_lupus_source_20261013'
DC=ROOT/'SkinDisease/sources/dermacon_in/holdout'
SPLIT=ROOT/'SkinDisease/sources/dermacon_in/adaptation'
SD=ROOT/'SkinDisease/sources/skindisnet_v2/holdout'
OUTER=ROOT/'ai-service/reports/scene_grouped_oof_folds_seed42.json'


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def fingerprints(path):
    with Image.open(path) as im:
        im.load(); rgb=ImageOps.exif_transpose(im).convert('RGB'); w,h=rgb.size
        pixel=hashlib.sha256(f'{w},{h}:'.encode()+rgb.tobytes()).hexdigest()
    # Same right>left dHash implementation as the original training audit.
    return dict(sha256=sha256_file(path),pixel_sha256=pixel,dhash64=f'{dhash(path):016x}')


def entries(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def write_entries(path,rows):
    path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')


def main():
    assert not (OUT/'summary.json').exists(),'Preserve completed supplemental audit'
    state=read(ROOT/'ai-service/reports/active_research_track.json'); assert state['active_track']=='original_eight' and state['classes']==CLASSES
    raw_summary=read(RAW_REPORT/'summary.json'); assert raw_summary['images']==231 and raw_summary['manifest_sha256']==sha256_file(RAW_REPORT/'verified_images.jsonl')
    sources=[OUTER,RAW_REPORT/'protocol.json',RAW_REPORT/'summary.json',RAW_REPORT/'verified_images.jsonl',
             SPLIT/'train.csv',SPLIT/'validation.csv',SPLIT/'official_test.csv',SPLIT/'split_audit.json',DC/'labels_no_near.csv',SD/'labels_no_near.csv']
    protocol=dict(classes=CLASSES,focus_classes=['Candidiasis','Lupus','Tinea'],sources={p.relative_to(ROOT).as_posix():sha256_file(p) for p in sources},
        code_sha256={n:sha256_file(ROOT/'ai-service/training'/n) for n in ('prepare_original_eight_supplement.py','common.py','train_v2.py','evaluate_new_ensemble_holdout.py')},
        candidates='590 original-label DermaCon development-train photos +231 corrected-source-train Lupus atlas photos; no inactive new-eight manifest/checkpoint.',
        reference='5937 original development photos, all original fixed/SCIN historical test photos, DermaCon validation213/official_test183, SkinDisNet723.',
        quarantine='Exact SHA256, canonical EXIF-transposed RGB pixels, or original right>left dHash<=3 against any protected image. Join known source cases and all candidate exact/pixel/dHash links; quarantine entire candidate component if any member hits protected data or pixel-label conflict.',
        deduplication='Within unquarantined components retain one representative per canonical pixel hash; prefer published clinical DermaCon over atlas. Case and similarity group IDs retained.',
        limits=['Train-preparation only; no new accuracy result or serving change.',
                'Fitz-C source partition=train only, missing subject IDs, auxiliary train-only; neither published split nor dHash proves independent patients.',
                'DermaCon source previously inspected and used in development; future evaluation must use held roles, not its full986photos containing train.',
                'Clinical/atlas source labels retained; no claim of new diagnosis verification.',
                'DHash quarantine is conservative similarity filtering, not proof of duplicate or label error.'])
    if (OUT/'protocol.json').exists(): assert read(OUT/'protocol.json')==protocol,'Registered data audit changed'
    else: save_json(OUT/'protocol.json',protocol)
    roles={}; metadata={}
    for role,count in [('train',590),('validation',213),('official_test',183)]:
        samples,meta=read_new_samples(DC,SPLIT/f'{role}.csv'); assert len(samples)==count
        roles[role]=samples; metadata[role]=meta
    groups={k:{s.group_id for s in v} for k,v in roles.items()}
    for a,b in [('train','validation'),('train','official_test'),('validation','official_test')]: assert groups[a].isdisjoint(groups[b])
    source_audit=read(SPLIT/'split_audit.json'); assert source_audit['all_splits_patient_disjoint'] and source_audit['input_manifest_sha256']==sha256_file(DC/'labels_no_near.csv')
    old=read(OUTER)['images']; reference={ROOT/r['path']:dict(role='original_development',label=r['class'],expected_sha256=r['sha256']) for r in old}
    for directory,role in [(ROOT/'SkinDisease/test','historical_fixed_test'),(ROOT/'SkinDisease/scin-v1/external_test','historical_scin_test')]:
        for p in sorted(directory.rglob('*')):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS: reference[p]=dict(role=role,label=p.relative_to(directory).parts[0])
    for role in ('validation','official_test'):
        for s in roles[role]: reference[s.path]=dict(role='dermacon_'+role,label=CLASSES[s.label],expected_sha256=s.digest)
    sd,sdmeta=read_new_samples(SD,SD/'labels_no_near.csv'); assert len(sd)==723
    for s in sd: reference[s.path]=dict(role='skindisnet_prior_transfer',label=CLASSES[s.label],expected_sha256=s.digest)
    protected=[]
    for i,(path,info) in enumerate(reference.items(),1):
        fp=fingerprints(path)
        if 'expected_sha256' in info: assert fp['sha256']==info['expected_sha256']
        protected.append(dict(path=path.relative_to(ROOT).as_posix(),**info,**fp))
        if i%1000==0: print(json.dumps(dict(protected_fingerprints=i,total=len(reference))),flush=True)
    write_entries(OUT/'protected_fingerprints.jsonl',protected)
    candidates=[]
    with (SPLIT/'train.csv').open(encoding='utf-8-sig',newline='') as f:
        dc_annotations={r['image_path']:r for r in csv.DictReader(f)}
    for s in roles['train']:
        annotation=dc_annotations[s.path.relative_to(DC).as_posix()]
        candidates.append(dict(path=s.path.relative_to(ROOT).as_posix(),label=CLASSES[s.label],source='DermaCon-IN-v1',
          source_case_id=s.group_id,subject_id_available=True,source_partition='development_train',evaluation_eligible=False,
          source_label=annotation['source_disease_label'],diagnostic_confidence=annotation['diagnostic_confidence'],
          source_label_status='published_dermatologist_annotation_previously_inspected',**fingerprints(s.path)))
    for r in entries(RAW_REPORT/'verified_images.jsonl'):
        p=ROOT/r['local_path']; fp=fingerprints(p); assert fp['sha256']==r['sha256'] and fp['pixel_sha256']==r['pixel_sha256']
        assert hashlib.md5(p.read_bytes()).hexdigest()==r['source_md5'] and r['source_partition']=='train' and r['label']=='Lupus'
        candidates.append(dict(path=r['local_path'],label='Lupus',source='Fitzpatrick17k-C',source_case_id=None,
          subject_id_available=False,source_label=r['source_label'],source_partition='train',source_md5=r['source_md5'],
          evaluation_eligible=False,source_label_status='published_atlas_label_not_newly_confirmed',**fp))
    assert len(candidates)==821
    protected_sha=defaultdict(list); protected_pixel=defaultdict(list); values=[int(r['dhash64'],16) for r in protected]
    tree=BkNode(values[0],0)
    for j,r in enumerate(protected):
        protected_sha[r['sha256']].append(j); protected_pixel[r['pixel_sha256']].append(j)
        if j: tree.add(values[j],j)
    uf=UnionFind(len(candidates)); people={}; pixels=defaultdict(list); links=[]; hits={}
    for i,r in enumerate(candidates):
        if r['source_case_id']:
            key=r['source'],r['source_case_id']
            if key in people: uf.union(i,people[key])
            else: people[key]=i
        pixels[r['pixel_sha256']].append(i)
        near=[]; value=int(r['dhash64'],16); tree.query(value,3,near)
        sha=protected_sha.get(r['sha256'],[]); pixel=protected_pixel.get(r['pixel_sha256'],[])
        if sha or pixel or near:
            hits[i]=dict(exact_sha=bool(sha),same_pixel=bool(pixel),near_dhash=bool(near),
                         examples=[protected[j]['path'] for j in sorted(set(sha+pixel+near))[:6]])
    conflicts=set()
    for indices in pixels.values():
        for i in indices[1:]: uf.union(indices[0],i)
        if len({candidates[i]['label'] for i in indices})>1: conflicts.update(indices)
    small_tree=BkNode(int(candidates[0]['dhash64'],16),0)
    for i,r in enumerate(candidates[1:],1):
        near=[]; value=int(r['dhash64'],16); small_tree.query(value,3,near)
        for j in near:
            uf.union(i,j); links.append(dict(a=candidates[i]['path'],b=candidates[j]['path'],distance=(value^int(candidates[j]['dhash64'],16)).bit_count()))
        small_tree.add(value,i)
    components=defaultdict(list)
    for i in range(len(candidates)): components[uf.find(i)].append(i)
    kept=[]; excluded=[]; redundant=[]
    for indices in components.values():
        gid='supplement_'+hashlib.sha256('\n'.join(sorted(candidates[i]['sha256'] for i in indices)).encode()).hexdigest()[:24]
        bad=[i for i in indices if i in hits or i in conflicts]
        if bad:
            for i in indices: excluded.append(dict(**candidates[i],image_group=gid,linked_hit_paths=[candidates[j]['path'] for j in bad],direct_match=hits.get(i),pixel_label_conflict=i in conflicts))
            continue
        reps=defaultdict(list)
        for i in indices: reps[candidates[i]['pixel_sha256']].append(i)
        for pp in reps.values():
            pp.sort(key=lambda i:(candidates[i]['source']!='DermaCon-IN-v1',candidates[i]['path']))
            kept.append(dict(**candidates[pp[0]],image_group=gid,role='auxiliary_train_only'))
            for i in pp[1:]: redundant.append(dict(**candidates[i],image_group=gid,retained_path=candidates[pp[0]]['path']))
    kept.sort(key=lambda r:r['path']); write_entries(OUT/'training_candidates.jsonl',kept)
    write_entries(OUT/'quarantined.jsonl',excluded); write_entries(OUT/'redundant.jsonl',redundant); write_entries(OUT/'candidate_fingerprints.jsonl',candidates)
    save_json(OUT/'similarity_links.json',links)
    summary=dict(status='supplement_prepared_train_only_not_trained',classes=CLASSES,input_candidates=821,
      protected_images=len(protected),protected_by_role=dict(Counter(r['role'] for r in protected)),
      retained_images=len(kept),quarantined_images=len(excluded),redundant_images=len(redundant),direct_protected_match_images=len(hits),
      by_class={c:dict(retained=sum(r['label']==c for r in kept),by_source=dict(Counter(r['source'] for r in kept if r['label']==c))) for c in CLASSES},
      by_source=dict(Counter(r['source'] for r in kept)),candidate_image_groups=len({r['image_group'] for r in kept}),
      known_dermacon_cases=len({r['source_case_id'] for r in kept if r['subject_id_available']}),
      atlas_images_without_subject_id=sum(not r['subject_id_available'] for r in kept),
      protocol_sha256=sha256_file(OUT/'protocol.json'),training_manifest_sha256=sha256_file(OUT/'training_candidates.jsonl'),
      artifact_sha256={n:sha256_file(OUT/n) for n in ('protected_fingerprints.jsonl','candidate_fingerprints.jsonl','quarantined.jsonl','redundant.jsonl','similarity_links.json')},
      derma_split_metadata=metadata,skindisnet_metadata=sdmeta,
      original_benchmark_images=5937,original_benchmark_unchanged=True,training_not_started=True,
      note='Supplement is separate from original5937benchmark. Future adapted models cannot be evaluated as held-out on all986DermaCon images because some are supplemental train. Partition train and dHash groups do not certify atlas patient independence.')
    assert len(kept)+len(excluded)+len(redundant)==821
    save_json(OUT/'summary.json',summary)
    print(json.dumps({k:summary[k] for k in ('retained_images','quarantined_images','redundant_images','by_class','by_source')}),flush=True)


if __name__=='__main__': main()
