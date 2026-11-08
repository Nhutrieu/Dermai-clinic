"""Prepare exact-label corrected-source Psoriasis train candidates from cache.

Keeps original-eight scope. Does not download, copy, relabel, fit a model or use
source validation/test for training. Near matches are conservative quarantine.
"""
from __future__ import annotations

import csv
import hashlib
import json
import zlib
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image,ImageOps

from common import save_json,sha256_file
from train_v2 import BkNode,UnionFind,dhash

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'ai-service/reports/original_eight_psoriasis_supplement_20261021'
OLD=ROOT/'ai-service/reports/original_eight_supplement_audit_20261013'
META=ROOT/'SkinDisease/sources/fitzpatrick17k_corrected'
PRIOR=ROOT/'ai-service/reports/fitzpatrick_c_selected_audit_20261011'


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def entries(path):return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
def write_entries(path,rows):path.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')


def fingerprints(path):
    with Image.open(path) as image:
        image.load();rgb=ImageOps.exif_transpose(image).convert('RGB');width,height=rgb.size
        pixel=hashlib.sha256(f'{width},{height}:'.encode()+rgb.tobytes()).hexdigest()
    return dict(sha256=sha256_file(path),pixel_sha256=pixel,dhash64=f'{dhash(path):016x}',width=width,height=height)


def verify_cached(row):
    path=ROOT/row['path']
    assert path.resolve().is_relative_to(ROOT)
    assert sha256_file(path)==row['sha256'],row['path']
    return row


def main():
    assert not (OUT/'summary.json').exists(),'Preserve completed supplement preparation'
    assert read(ROOT/'ai-service/reports/active_research_track.json')['active_track']=='original_eight'
    assert read(OLD/'summary.json')['retained_images']==807
    metadata_path=META/'Fitzpatrick17k-C.csv'
    assert hashlib.md5(metadata_path.read_bytes()).hexdigest()=='028e4fc67f64526b264a92d5b0e57909'
    with metadata_path.open(encoding='utf-8-sig',newline='') as stream:metadata=list(csv.DictReader(stream))
    source_rows=[row for row in metadata if row['label']=='psoriasis']
    selected=[row for row in source_rows if row['partition']=='train']
    nontrain=[row for row in source_rows if row['partition']!='train']
    assert len(selected)==374 and len(nontrain)==160
    prior={row['source_md5']:row for row in entries(PRIOR/'verified_images.jsonl') if row['source_label']=='psoriasis'}
    assert len(prior)==534
    files=[metadata_path,META/'archive_directory.json',PRIOR/'verified_images.jsonl',
           OLD/'summary.json',OLD/'protocol.json',OLD/'protected_fingerprints.jsonl',OLD/'candidate_fingerprints.jsonl',OLD/'training_candidates.jsonl',
           ROOT/'ai-service/reports/original_eight_weak_train_audit_20261021/summary.json',
           ROOT/'ai-service/reports/scene_grouped_oof_folds_seed42.json',ROOT/'ai-service/models/best_model.pth']
    protocol=dict(date='2026-10-21',source_record='https://zenodo.org/records/11101338',
        author_project='https://derm.cs.sfu.ca/critique/',license='CC BY-NC 4.0 as stated by versioned author record',
        original_label='Psoriasis',source_label='psoriasis',source_partition='train',candidate_images=374,
        nontrain_source_images_protected=160,newly_downloaded_images=0,
        acquisition='Existing cached atlas images and original versioned metadata only; not a newly collected patient cohort. Original eight-class preparation, no inactive-task artifacts or weights restored.',
        source_sha256={p.relative_to(ROOT).as_posix():sha256_file(p) for p in files},
        code_sha256={name:sha256_file(ROOT/'ai-service/training'/name) for name in ['prepare_original_eight_psoriasis_supplement.py','common.py','train_v2.py']},
        integrity='Metadata MD5+ZIP-directory size/CRC per image, Pillow decode, SHA256; no claim to full ZIP checksum without full archive validation.',
        protection='All prior protected7926 and previous821supplement candidates, plus160source Psoriasis val/test. Verify current SHA of cached fingerprints. Exact byte/canonical pixel or original right>left dHash<=3 hit quarantines entire linked candidate component.',
        quality='Source qc beginning4or5 flagged for metadata review and quarantined with their candidate component. Blank qc is unknown, not diagnosis confirmation.',
        deduplication='Group all candidate dHash<=3 links and exact pixels. In safe components retain one representative per canonical pixel; retain scene grouping.',
        limits=['No patient IDs. Source partition and similarity filters do not establish independent patients.',
                'Atlas labels have not been newly verified by a clinician. Selection does not prove diagnosis correctness.',
                'No change to5937OOF score, original Word, or API. Candidates are auxiliary train-only, not new independent test.',
                'Tinea and Lupus are not added by this preparation. Do not reinterpret other source conditions as Tinea.'])
    save_json(OUT/'protocol.json',protocol)
    archive={row['member']:row for row in read(META/'archive_directory.json')}
    rows=[]
    for source in source_rows:
        previous=prior[source['md5hash']];path=ROOT/previous['local_path']
        data=path.read_bytes();entry=archive['Categorized_AbbrvName/'+source['filepath']]
        assert hashlib.md5(data).hexdigest()==source['md5hash']
        assert len(data)==entry['uncompressed_bytes'] and zlib.crc32(data)==entry['crc32']
        fp=fingerprints(path);assert fp['sha256']==previous['sha256'] and fp['pixel_sha256']==previous['pixel_sha256']
        rows.append(dict(path=previous['local_path'],label='Psoriasis',source='Fitzpatrick17k-C',source_label='psoriasis',
            source_partition=source['partition'],source_md5=source['md5hash'],source_case_id=None,subject_id_available=False,
            evaluation_eligible=False,source_label_status='published_corrected_atlas_label_not_newly_confirmed',
            source_qc=source['qc'],source_qc_review_flag=source['qc'].strip().startswith(('4','5')),**fp))
    candidates=[row for row in rows if row['source_partition']=='train']
    protected_by_path={row['path']:row for name in ['protected_fingerprints.jsonl','candidate_fingerprints.jsonl'] for row in entries(OLD/name)}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for index,_ in enumerate(pool.map(verify_cached,list(protected_by_path.values())),1):
            if index%2000==0:print(json.dumps(dict(protected_hashes_checked=index)),flush=True)
    protected=list(protected_by_path.values())
    for row in rows:
        if row['source_partition']!='train':protected.append(dict(**row,role='source_psoriasis_'+row['source_partition']))
    write_entries(OUT/'protected_fingerprints.jsonl',protected)
    protected_sha=defaultdict(list);protected_pixel=defaultdict(list)
    tree=None
    for i,row in enumerate(protected):
        protected_sha[row['sha256']].append(i);protected_pixel[row['pixel_sha256']].append(i)
        if tree is None:tree=BkNode(int(row['dhash64'],16),i)
        else:tree.add(int(row['dhash64'],16),i)
    hits={};uf=UnionFind(len(candidates));pixels=defaultdict(list)
    for i,row in enumerate(candidates):
        near=[];tree.query(int(row['dhash64'],16),3,near)
        sha=protected_sha.get(row['sha256'],[]);pixel=protected_pixel.get(row['pixel_sha256'],[])
        if sha or pixel or near:
            hits[i]=dict(exact_sha=bool(sha),same_pixel=bool(pixel),near_dhash=bool(near),
                protected_examples=[protected[j]['path'] for j in sorted(set(sha+pixel+near))[:8]])
        pixels[row['pixel_sha256']].append(i)
    links=[];small=None
    for i,row in enumerate(candidates):
        value=int(row['dhash64'],16)
        if small is None:small=BkNode(value,i)
        else:
            matches=[];small.query(value,3,matches)
            for j in matches:
                uf.union(i,j);links.append(dict(a=row['path'],b=candidates[j]['path'],dhash_distance=(value^int(candidates[j]['dhash64'],16)).bit_count()))
            small.add(value,i)
    for members in pixels.values():
        for i in members[1:]:uf.union(members[0],i)
    components=defaultdict(list)
    for i in range(len(candidates)):components[uf.find(i)].append(i)
    retained=[];quarantined=[];redundant=[]
    for members in components.values():
        group='psoriasis_aux_'+hashlib.sha256('\n'.join(sorted(candidates[i]['sha256'] for i in members)).encode()).hexdigest()[:24]
        bad=[i for i in members if i in hits or candidates[i]['source_qc_review_flag']]
        if bad:
            for i in members:
                quarantined.append(dict(**candidates[i],image_group=group,direct_protected_match=hits.get(i),
                    linked_review_paths=[candidates[j]['path'] for j in bad],role='quarantined_not_train'))
            continue
        by_pixel=defaultdict(list)
        for i in members:by_pixel[candidates[i]['pixel_sha256']].append(i)
        for indices in by_pixel.values():
            indices.sort(key=lambda i:candidates[i]['path'])
            retained.append(dict(**candidates[indices[0]],image_group=group,role='auxiliary_train_only'))
            for i in indices[1:]:redundant.append(dict(**candidates[i],image_group=group,retained_path=candidates[indices[0]]['path']))
    retained.sort(key=lambda row:row['path'])
    assert len(retained)+len(quarantined)+len(redundant)==374
    old_train=entries(OLD/'training_candidates.jsonl');combined=sorted(old_train+retained,key=lambda row:row['path'])
    assert len(combined)==len({row['path'] for row in combined})==807+len(retained)
    assert len(combined)==len({row['sha256'] for row in combined})
    write_entries(OUT/'training_candidates.jsonl',retained)
    write_entries(OUT/'combined_auxiliary_train.jsonl',combined)
    write_entries(OUT/'quarantined.jsonl',quarantined)
    write_entries(OUT/'redundant.jsonl',redundant)
    write_entries(OUT/'candidate_fingerprints.jsonl',candidates)
    save_json(OUT/'similarity_links.json',links)
    summary=dict(status='auxiliary_psoriasis_candidates_prepared_not_trained',input_candidates=374,source_partition='train',
        retained_images=len(retained),retained_scene_groups=len({row['image_group'] for row in retained}),
        quarantined_images=len(quarantined),redundant_images=len(redundant),direct_protected_match_images=len(hits),
        direct_exact_sha_hits=sum(hit['exact_sha'] for hit in hits.values()),direct_canonical_pixel_hits=sum(hit['same_pixel'] for hit in hits.values()),
        source_qc_flag_images=sum(row['source_qc_review_flag'] for row in candidates),
        protected_images=len(protected),source_val_test_protected=160,
        previous_auxiliary_train_images=807,combined_auxiliary_train_images=len(combined),
        combined_by_class=dict(Counter(row['label'] for row in combined)),newly_downloaded_images=0,
        main_development_images=5937,main_development_unchanged=True,source_patient_ids_available=False,
        newly_doctor_verified_images=0,evaluation_eligible=False,not_trained=True,serving_changed=False,
        protocol_sha256=sha256_file(OUT/'protocol.json'),training_manifest_sha256=sha256_file(OUT/'training_candidates.jsonl'))
    save_json(OUT/'summary.json',summary)
    for relative,expected in protocol['source_sha256'].items():assert sha256_file(ROOT/relative)==expected,relative
    save_json(OUT/'verification.json',dict(status='PASS',scope='Source integrity, train partition, deterministic similarity quarantine; not diagnosis confirmation',
        summary_sha256=sha256_file(OUT/'summary.json'),protocol_sha256=sha256_file(OUT/'protocol.json'),
        images_changed=0,newly_downloaded_images=0,serving_changed=False))
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
