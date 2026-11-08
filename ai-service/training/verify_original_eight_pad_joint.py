"""Independent Hamming lookup and graph check for the joint PAD train audit."""
from collections import defaultdict
import numpy as np
from common import save_json,sha256_file
import prepare_original_eight_pad_joint as a


def main():
    root,out=a.ROOT,a.OUT; p=a.prior.read(out/'protocol.json'); s=a.prior.read(out/'summary.json')
    for name,h in p['source_sha256'].items(): assert sha256_file(root/name)==h,name
    for name,h in p['code_sha256'].items(): assert sha256_file(root/'ai-service/training'/name)==h,name
    for name,h in s['artifact_sha256'].items(): assert sha256_file(out/name)==h,name
    assert s['protocol_sha256']==sha256_file(out/'protocol.json')
    cc=a.prior.prior.entries(out/'candidate_fingerprints.jsonl'); pp=a.prior.prior.entries(a.prior.OUT/'protected_fingerprints.jsonl')
    kept=a.prior.prior.entries(out/'retained_all.jsonl'); bad=a.prior.prior.entries(out/'quarantined.jsonl'); duplicate=a.prior.prior.entries(out/'redundant.jsonl')
    assert len(cc)==1703 and len(pp)==17201 and len(kept)+len(bad)+len(duplicate)==1703
    assert {r['path'] for r in kept+bad+duplicate}=={r['path'] for r in cc}
    for r in pp: assert sha256_file(root/r['path'])==r['sha256']
    for i,r in enumerate(cc):
        fp=a.prior.prior.fingerprints(root/r['path'])
        assert all(r[k]==value for k,value in fp.items())
        if (i+1)%400==0: print(dict(verified_candidate_fingerprints=i+1),flush=True)
    values=np.asarray([int(r['dhash64'],16) for r in pp],dtype=np.uint64)
    lookup=np.asarray([i.bit_count() for i in range(256)],dtype=np.uint8)
    protected_sha={r['sha256'] for r in pp}; protected_pixel={r['pixel_sha256'] for r in pp}; seeds=set()
    pixels=defaultdict(set)
    for r in cc: pixels[r['pixel_sha256']].add(r['source_label'])
    for i,r in enumerate(cc):
        xor=values^np.uint64(int(r['dhash64'],16)); distance=lookup[xor.view(np.uint8).reshape(-1,8)].sum(1)
        if (distance<=3).any() or r['sha256'] in protected_sha or r['pixel_sha256'] in protected_pixel or len(pixels[r['pixel_sha256']])>1: seeds.add(i)
    adjacency=[set() for _ in cc]; dh=[int(r['dhash64'],16) for r in cc]
    for i,r in enumerate(cc):
        for j in range(i):
            if r['source_patient_id']==cc[j]['source_patient_id'] or r['pixel_sha256']==cc[j]['pixel_sha256'] or (dh[i]^dh[j]).bit_count()<=3: adjacency[i].add(j); adjacency[j].add(i)
    seen=set(); expected_kept=set(); expected_bad=set(); expected_duplicates=set()
    for i in range(len(cc)):
        if i in seen: continue
        component=set(); todo=[i]
        while todo:
            j=todo.pop()
            if j in component: continue
            component.add(j); todo.extend(adjacency[j]-component)
        seen|=component
        if component & seeds: expected_bad|={cc[j]['path'] for j in component}; continue
        groups=defaultdict(list)
        for j in component: groups[cc[j]['pixel_sha256']].append(cc[j]['path'])
        for paths in groups.values(): paths.sort(); expected_kept.add(paths[0]); expected_duplicates.update(paths[1:])
    assert expected_kept=={r['path'] for r in kept} and expected_bad=={r['path'] for r in bad} and expected_duplicates=={r['path'] for r in duplicate}
    reserved=a.prior.read(a.prior.INVENTORY/'reserved_pad_validation.json'); assert {r['source_patient_id'] for r in kept}.isdisjoint(r['patient_id'] for r in reserved)
    for role,name in [('positive','positive_train'),('negative','negative_train'),('audit_only','audit_only')]:
        rr=a.prior.prior.entries(out/(name+'.jsonl')); assert rr==[r for r in kept if r['role']==role]
        for r in rr:
            if role=='positive': assert r['label']=='SkinCancer' and r['complementary_label'] is None and r['published_biopsed']
            elif role=='negative': assert r['label'] is None and r['complementary_label']=='SkinCancer' and r['source_label'] in ('NEV','SEK')
            else: assert r['label'] is None and r['complementary_label'] is None and r['training_eligible'] is False
    assert len(kept)==s['retained_images'] and len(bad)==s['quarantined_images'] and len(duplicate)==s['redundant_images']
    for d,c in s['by_diagnosis'].items():
        assert c['images']==sum(r['source_label']==d for r in kept) and c['patients']==len({r['source_patient_id'] for r in kept if r['source_label']==d})
    save_json(out/'verification.json',dict(status='PASS',summary_sha256=sha256_file(out/'summary.json'),protocol_sha256=sha256_file(out/'protocol.json'),
        independent_hamming_lookup=True,independent_patient_graph=True,complementary_targets_only=True,reserved_pad_patients_unchanged=True,
        scope='Checks preparation/provenance, not new clinical labels or independent patient generalization.'))
    print(a.prior.read(out/'verification.json'),flush=True)


if __name__=='__main__': main()
