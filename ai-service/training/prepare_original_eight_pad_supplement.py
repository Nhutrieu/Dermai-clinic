"""Patient/component quarantine of historical PAD train cancer candidates."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from common import save_json, sha256_file
from train_v2 import BkNode, UnionFind
import prepare_original_eight_supplement as prior

ROOT=prior.ROOT
OUT=ROOT/'ai-service/reports/original_eight_pad_supplement_audit_20261014'
INVENTORY=ROOT/'ai-service/reports/original_eight_pad_train_inventory_20261013'
PAD=ROOT/'SkinDisease/sources/pad_ufes20/extracted'
EXTRAS=[ROOT/'SkinDisease/sources'/s/p for s,p in [
    ('hiba_2023','holdout/locked_manifest.csv'),('dermatonet_2026','holdout/locked_manifest.csv'),
    ('med_node_2015','holdout/locked_manifest.csv'),('milk10k_2025','clinical_pool/locked_split.csv'),
    ('slice3d_permissive_2024','patient_holdout/locked_manifest.csv')]]


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def register():
    assert not (OUT/'protocol.json').exists(),'Preserve registered audit'
    inv=read(INVENTORY/'summary.json'); verification=read(INVENTORY/'verification.json')
    assert verification['status']=='PASS_INVENTORY_ONLY' and inv['candidate_images']==821
    assert verification['summary_sha256']==sha256_file(INVENTORY/'summary.json')
    assert inv['manifest_sha256']==sha256_file(INVENTORY/'training_candidates.jsonl')
    sup=read(prior.OUT/'summary.json'); assert read(prior.OUT/'verification.json')['status']=='PASS'
    for name,h in sup['artifact_sha256'].items(): assert sha256_file(prior.OUT/name)==h
    files=[INVENTORY/'protocol.json',INVENTORY/'summary.json',INVENTORY/'training_candidates.jsonl',
        INVENTORY/'reserved_pad_validation.json',prior.OUT/'summary.json',prior.OUT/'verification.json',
        prior.OUT/'protected_fingerprints.jsonl',prior.OUT/'candidate_fingerprints.jsonl',
        PAD/'metadata.csv',ROOT/'ai-service/reports/paper_ensemble_benchmark/pad_ufes_external_evaluation.json',*EXTRAS]
    p=dict(source_sha256={x.relative_to(ROOT).as_posix():sha256_file(x) for x in files},
        code_sha256={n:sha256_file(ROOT/'ai-service/training'/n) for n in
            ('prepare_original_eight_pad_supplement.py','verify_original_eight_pad_supplement.py','prepare_original_eight_supplement.py','common.py','train_v2.py')},
        candidates='821PAD historical development-train BCC/SCC/MEL images; published biopsy=True; source patient split unchanged.',
        protected='All prior7926protected original/source roles, all821prior supplemental candidate photos (including quarantined ones), complete locked HIBA/DermaNet/MEDNODE/MILKpool/SLICEholdout images, PAD447reservedvalidation plus prior excluded-patient images.',
        matching='Exact SHA256, EXIF-canonical RGB pixel hash, or original right>left dHash<=3. Union candidates by PADpatient, samepixel and candidate dHash<=3; quarantine whole connected component on any protected hit or conflicting source diagnosis on identical pixels.',
        deduplication='Within clean components retain one row per canonical pixel hash, preserve all affected patient/diagnosis identities in duplicate metadata.',
        role='Auxiliary train only; does not create new independent test or change5937benchmark. Never map ACK/NEV/SEK to another original class.')
    save_json(OUT/'protocol.json',p); return p


def main():
    protocol=register()
    protected={}
    for filename,role in [('protected_fingerprints.jsonl',None),('candidate_fingerprints.jsonl','prior_auxiliary_candidate')]:
        for r in prior.entries(prior.OUT/filename):
            assert sha256_file(ROOT/r['path'])==r['sha256']
            protected[r['path']]=dict(path=r['path'],role=role or r['role'],sha256=r['sha256'],pixel_sha256=r['pixel_sha256'],dhash64=r['dhash64'])
    extra=[]
    for manifest in EXTRAS:
        with manifest.open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                path=(manifest.parent/r['image_path']).resolve(strict=True)
                assert path.is_relative_to(manifest.parent.resolve())
                assert sha256_file(path)==r['sha256']
                extra.append((path,manifest.parent.parent.name+':protected_locked_source'))
    with (PAD/'metadata.csv').open(encoding='utf-8-sig',newline='') as f: padmeta={r['img_id']:r for r in csv.DictReader(f)}
    index={p.name:p for p in (PAD/'images').rglob('*.png')}; assert len(index)==2298
    for r in read(INVENTORY/'reserved_pad_validation.json'): extra.append((index[r['img_id']],'PAD_reserved_validation'))
    old=read(ROOT/'ai-service/reports/paper_ensemble_benchmark/pad_ufes_external_evaluation.json')
    nearids={r['pad_img_id'] for r in old['overlap_audit']['potential_dhash_matches']}
    excluded={r['patient_id'] for r in old['predictions'] if r['img_id'] in nearids}|set(old['internal_duplicate_audit']['diagnosis_conflict_patients'])
    for r in old['predictions']:
        if r['patient_id'] in excluded: extra.append((index[r['img_id']],'PAD_previously_quarantined_patient'))
    for j,(path,role) in enumerate(extra,1):
        rel=path.relative_to(ROOT).as_posix()
        if rel not in protected: protected[rel]=dict(path=rel,role=role,**prior.fingerprints(path))
        if j%1000==0: print(json.dumps(dict(extra_fingerprints=j,total=len(extra))),flush=True)
    pp=sorted(protected.values(),key=lambda r:r['path']); prior.write_entries(OUT/'protected_fingerprints.jsonl',pp)
    candidates=[]
    for r in prior.entries(INVENTORY/'training_candidates.jsonl'):
        path=ROOT/r['path']; fp=prior.fingerprints(path); assert fp['sha256']==r['sha256']
        official=padmeta[path.name]
        assert official['biopsed']=='True' and official['patient_id']==r['source_patient_id'] and official['diagnostic']==r['source_label']
        candidates.append(dict(**r,pixel_sha256=fp['pixel_sha256'],dhash64=fp['dhash64']))
    prior.write_entries(OUT/'candidate_fingerprints.jsonl',candidates)
    values=[int(r['dhash64'],16) for r in pp]; tree=BkNode(values[0],0)
    bysha=defaultdict(list); bypixel=defaultdict(list)
    for j,r in enumerate(pp):
        bysha[r['sha256']].append(j); bypixel[r['pixel_sha256']].append(j)
        if j: tree.add(values[j],j)
    uf=UnionFind(len(candidates)); patients={}; pixels=defaultdict(list); hits={}; links=[]
    for i,r in enumerate(candidates):
        pid=r['source_patient_id']
        if pid in patients: uf.union(i,patients[pid])
        else: patients[pid]=i
        pixels[r['pixel_sha256']].append(i)
        near=[]; tree.query(int(r['dhash64'],16),3,near)
        exact=bysha.get(r['sha256'],[]); pixel=bypixel.get(r['pixel_sha256'],[])
        if exact or pixel or near: hits[i]=dict(exact_sha=bool(exact),same_pixel=bool(pixel),near_dhash=bool(near),protected_matches=[pp[j]['path'] for j in sorted(set(exact+pixel+near))])
    conflicts=set()
    for ids in pixels.values():
        for i in ids[1:]: uf.union(ids[0],i)
        if len({candidates[i]['source_label'] for i in ids})>1: conflicts.update(ids)
    small=BkNode(int(candidates[0]['dhash64'],16),0)
    for i,r in enumerate(candidates[1:],1):
        near=[]; small.query(int(r['dhash64'],16),3,near)
        for j in near:
            uf.union(i,j); links.append(dict(a=candidates[i]['path'],b=candidates[j]['path'],distance=(int(r['dhash64'],16)^int(candidates[j]['dhash64'],16)).bit_count()))
        small.add(int(r['dhash64'],16),i)
    components=defaultdict(list)
    for i in range(len(candidates)): components[uf.find(i)].append(i)
    retained=[]; quarantined=[]; redundant=[]
    import hashlib
    for ids in components.values():
        gid='PAD_component_'+hashlib.sha256('\n'.join(sorted(candidates[i]['path'] for i in ids)).encode()).hexdigest()[:24]
        bad=[i for i in ids if i in hits or i in conflicts]
        if bad:
            for i in ids: quarantined.append(dict(**candidates[i],group=gid,direct_match=hits.get(i),pixel_diagnosis_conflict=i in conflicts,linked_hit_paths=[candidates[j]['path'] for j in bad]))
            continue
        local=defaultdict(list)
        for i in ids: local[candidates[i]['pixel_sha256']].append(i)
        for group in local.values():
            group.sort(key=lambda i:candidates[i]['path']); i=group[0]
            r=dict(candidates[i]); r.update(group=gid,role='auxiliary_train_only',training_eligible=True)
            retained.append(r)
            for j in group[1:]: redundant.append(dict(**candidates[j],group=gid,retained_path=r['path']))
    retained.sort(key=lambda r:r['path'])
    for name,rows in [('training_candidates.jsonl',retained),('quarantined.jsonl',quarantined),('redundant.jsonl',redundant)]: prior.write_entries(OUT/name,rows)
    save_json(OUT/'similarity_links.json',links)
    summary=dict(status='verified_overlap_preparation_pending_verifier',candidate_images=821,protected_images=len(pp),protected_by_role=dict(Counter(r['role'] for r in pp)),
        retained_images=len(retained),retained_patients=len({r['source_patient_id'] for r in retained}),quarantined_images=len(quarantined),redundant_images=len(redundant),direct_match_images=len(hits),
        by_diagnosis={d:dict(images=sum(r['source_label']==d for r in retained),patients=len({r['source_patient_id'] for r in retained if r['source_label']==d})) for d in ('BCC','SCC','MEL')},
        protocol_sha256=sha256_file(OUT/'protocol.json'),manifest_sha256=sha256_file(OUT/'training_candidates.jsonl'),
        artifact_sha256={name:sha256_file(OUT/name) for name in ('protected_fingerprints.jsonl','candidate_fingerprints.jsonl','quarantined.jsonl','redundant.jsonl','similarity_links.json')})
    assert len(retained)+len(quarantined)+len(redundant)==821
    save_json(OUT/'summary.json',summary); print(json.dumps(summary),flush=True)


if __name__=='__main__': main()
