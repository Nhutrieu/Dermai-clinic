"""Joint PAD historical-train patient/pixel audit for cancer and NEV/SEK contrast.

ACK participates in conflict detection but is not a negative training target.
NEV/SEK have only complementary SkinCancer supervision, never an eight-class label.
"""
import csv
import hashlib
from collections import Counter,defaultdict

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold
from common import save_json,sha256_file
from train_v2 import BkNode,UnionFind
import prepare_original_eight_pad_supplement as prior

ROOT=prior.ROOT
OUT=ROOT/'ai-service/reports/original_eight_pad_joint_audit_20261014'


def main():
    assert not (OUT/'protocol.json').exists(),'Preserve registered joint audit'
    oldsummary=prior.read(prior.OUT/'summary.json'); oldverify=prior.read(prior.OUT/'verification.json')
    assert oldverify['status']=='PASS' and oldverify['summary_sha256']==sha256_file(prior.OUT/'summary.json')
    for name,h in oldsummary['artifact_sha256'].items(): assert sha256_file(prior.OUT/name)==h
    invprotocol=prior.read(prior.INVENTORY/'protocol.json')
    for path,h in invprotocol['sources'].items(): assert sha256_file(ROOT/path)==h
    files=[prior.OUT/'protocol.json',prior.OUT/'summary.json',prior.OUT/'verification.json',prior.OUT/'protected_fingerprints.jsonl',prior.OUT/'candidate_fingerprints.jsonl',
           prior.INVENTORY/'reserved_pad_validation.json',prior.INVENTORY/'protocol.json']+[ROOT/path for path in invprotocol['sources']]
    protocol=dict(source_sha256={p.relative_to(ROOT).as_posix():sha256_file(p) for p in files},
        code_sha256={n:sha256_file(ROOT/'ai-service/training'/n) for n in ('prepare_original_eight_pad_joint.py','verify_original_eight_pad_joint.py','prepare_original_eight_pad_supplement.py','prepare_original_eight_supplement.py','common.py','train_v2.py')},
        cohort='Exact historical cleaned2150PAD ordering, SGKF5seed42first split:1703train,447reservedvalidation. Reuse17201protected fingerprints, verify current file SHA.',
        targets='BCC/SCC/MEL:original8label SkinCancer; NEV/SEK:only complementary label notSkinCancer, eight_class_label=None; ACK:conflict audit only, no train target.',
        quarantine='Join all1703historical-train images by PADpatient/canonicalpixel/candidate dHash<=3. Entire component removed for protected SHA/pixel/dHash hit or inconsistent source diagnosis on identical pixels. Deduplicate canonicalpixels in clean components.',
        limitations=['Published labels only; no new expert review.', 'PADsource and validation previously investigated; no fresh test.', 'Unknown patient identity outside PAD not solved by similarity filtering.', 'Joint retained positive subset may differ from earlier positive-only audit; reinitialize both new arms from old untouched fold0ResNet, do not inherit previously trained PADweights.'])
    save_json(OUT/'protocol.json',protocol)
    report=prior.read(ROOT/'ai-service/reports/paper_ensemble_benchmark/pad_ufes_external_evaluation.json')
    near={r['pad_img_id'] for r in report['overlap_audit']['potential_dhash_matches']}
    excluded={r['patient_id'] for r in report['predictions'] if r['img_id'] in near}|set(report['internal_duplicate_audit']['diagnosis_conflict_patients'])
    clean=[dict(img_id=r['img_id'],patient_id=r['patient_id'],diagnostic=r['diagnostic']) for r in report['predictions'] if r['patient_id'] not in excluded]
    y=np.asarray([0 if r['diagnostic'] in ('NEV','SEK') else 1 if r['diagnostic'] in ('BCC','SCC','MEL') else 2 for r in clean]); groups=np.asarray([r['patient_id'] for r in clean])
    tr,va=next(StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=42).split(np.zeros(len(clean)),y,groups))
    assert len(clean)==2150 and len(tr)==1703 and len(va)==447
    reserved=prior.read(prior.INVENTORY/'reserved_pad_validation.json')
    assert [clean[i]['img_id'] for i in va]==[r['img_id'] for r in reserved]
    with (prior.PAD/'metadata.csv').open(encoding='utf-8-sig',newline='') as f: official={r['img_id']:r for r in csv.DictReader(f)}
    index={p.name:p for p in (prior.PAD/'images').rglob('*.png')}
    cached={r['path']:r for r in prior.prior.entries(prior.OUT/'candidate_fingerprints.jsonl')}
    cc=[]
    for j,i in enumerate(tr,1):
        row=clean[i]; path=index[row['img_id']]; rel=path.relative_to(ROOT).as_posix(); m=official[row['img_id']]
        assert m['patient_id']==row['patient_id'] and m['diagnostic']==row['diagnostic']
        if rel in cached:
            old=cached[rel]; assert sha256_file(path)==old['sha256']; fp={key:old[key] for key in ('sha256','pixel_sha256','dhash64')}
        else: fp=prior.prior.fingerprints(path)
        d=row['diagnostic']; positive=d in ('BCC','SCC','MEL'); negative=d in ('NEV','SEK')
        if positive: assert m['biopsed']=='True'
        cc.append(dict(path=rel,source='PAD-UFES-20',source_label=d,source_patient_id=row['patient_id'],source_lesion_id=m['lesion_id'],
            published_biopsed=m['biopsed']=='True',label='SkinCancer' if positive else None,
            complementary_label='SkinCancer' if negative else None,role='positive' if positive else 'negative' if negative else 'audit_only',**fp))
        if j%200==0: print(dict(candidate_fingerprints=j,total=1703),flush=True)
    prior.prior.write_entries(OUT/'candidate_fingerprints.jsonl',cc)
    pp=prior.prior.entries(prior.OUT/'protected_fingerprints.jsonl')
    for r in pp: assert sha256_file(ROOT/r['path'])==r['sha256']
    values=[int(r['dhash64'],16) for r in pp]; tree=BkNode(values[0],0); bysha=defaultdict(list); bypixel=defaultdict(list)
    for j,r in enumerate(pp):
        bysha[r['sha256']].append(j); bypixel[r['pixel_sha256']].append(j)
        if j: tree.add(values[j],j)
    uf=UnionFind(len(cc)); people={}; pixels=defaultdict(list); hits={}; links=[]
    for i,r in enumerate(cc):
        pid=r['source_patient_id']
        if pid in people: uf.union(i,people[pid])
        else: people[pid]=i
        pixels[r['pixel_sha256']].append(i); near=[]; tree.query(int(r['dhash64'],16),3,near)
        exact=bysha.get(r['sha256'],[]); pixel=bypixel.get(r['pixel_sha256'],[])
        if near or exact or pixel: hits[i]=[pp[j]['path'] for j in sorted(set(near+exact+pixel))]
    conflict=set()
    for ids in pixels.values():
        for i in ids[1:]: uf.union(ids[0],i)
        if len({cc[i]['source_label'] for i in ids})>1: conflict.update(ids)
    small=BkNode(int(cc[0]['dhash64'],16),0)
    for i,r in enumerate(cc[1:],1):
        near=[]; small.query(int(r['dhash64'],16),3,near)
        for j in near: uf.union(i,j); links.append(dict(a=r['path'],b=cc[j]['path'],distance=(int(r['dhash64'],16)^int(cc[j]['dhash64'],16)).bit_count()))
        small.add(int(r['dhash64'],16),i)
    components=defaultdict(list)
    for i in range(len(cc)): components[uf.find(i)].append(i)
    kept=[]; bad=[]; duplicate=[]
    for ids in components.values():
        gid='PAD_joint_'+hashlib.sha256('\n'.join(sorted(cc[i]['path'] for i in ids)).encode()).hexdigest()[:24]
        seeds=[i for i in ids if i in hits or i in conflict]
        if seeds:
            bad.extend(dict(**cc[i],group=gid,direct_protected_matches=hits.get(i,[]),pixel_diagnosis_conflict=i in conflict,linked_seed_paths=[cc[j]['path'] for j in seeds]) for i in ids); continue
        pixelgroups=defaultdict(list)
        for i in ids: pixelgroups[cc[i]['pixel_sha256']].append(i)
        for items in pixelgroups.values():
            items.sort(key=lambda i:cc[i]['path']); row=dict(**cc[items[0]],group=gid,training_eligible=cc[items[0]]['role']!='audit_only',evaluation_eligible=False)
            kept.append(row)
            duplicate.extend(dict(**cc[i],group=gid,retained_path=row['path']) for i in items[1:])
    kept.sort(key=lambda r:r['path'])
    outputs=dict(retained_all=kept,positive_train=[r for r in kept if r['role']=='positive'],negative_train=[r for r in kept if r['role']=='negative'],audit_only=[r for r in kept if r['role']=='audit_only'],quarantined=bad,redundant=duplicate)
    for name,rows in outputs.items(): prior.prior.write_entries(OUT/(name+'.jsonl'),rows)
    save_json(OUT/'similarity_links.json',links)
    pos,neg=outputs['positive_train'],outputs['negative_train']
    summary=dict(candidate_images=1703,protected_images=len(pp),retained_images=len(kept),quarantined_images=len(bad),redundant_images=len(duplicate),
        positive_images=len(pos),positive_patients=len({r['source_patient_id'] for r in pos}),negative_images=len(neg),negative_patients=len({r['source_patient_id'] for r in neg}),
        positive_negative_shared_train_patients=len({r['source_patient_id'] for r in pos}&{r['source_patient_id'] for r in neg}),
        by_diagnosis={d:dict(images=sum(r['source_label']==d for r in kept),patients=len({r['source_patient_id'] for r in kept if r['source_label']==d})) for d in ('BCC','SCC','MEL','NEV','SEK','ACK')},
        direct_protected_hits=len(hits),protocol_sha256=sha256_file(OUT/'protocol.json'),
        artifact_sha256={name:sha256_file(OUT/name) for name in ['candidate_fingerprints.jsonl','similarity_links.json']+[n+'.jsonl' for n in outputs]},
        scope='Joint train preparation only; no labels assigned to remaining7classes, no new test.')
    assert len(kept)+len(bad)+len(duplicate)==1703
    save_json(OUT/'summary.json',summary); print(summary,flush=True)


if __name__=='__main__': main()
