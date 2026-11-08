"""Independent brute force matching and component reconstruction for PAD pool."""
from collections import defaultdict
import numpy as np
from common import save_json,sha256_file
import prepare_original_eight_pad_supplement as a


def main():
    p=a.read(a.OUT/'protocol.json'); s=a.read(a.OUT/'summary.json')
    for name,h in p['source_sha256'].items(): assert sha256_file(a.ROOT/name)==h,name
    for name,h in p['code_sha256'].items(): assert sha256_file(a.ROOT/'ai-service/training'/name)==h,name
    for name,h in s['artifact_sha256'].items(): assert sha256_file(a.OUT/name)==h,name
    assert s['protocol_sha256']==sha256_file(a.OUT/'protocol.json') and s['manifest_sha256']==sha256_file(a.OUT/'training_candidates.jsonl')
    pp=a.prior.entries(a.OUT/'protected_fingerprints.jsonl'); cc=a.prior.entries(a.OUT/'candidate_fingerprints.jsonl')
    kept=a.prior.entries(a.OUT/'training_candidates.jsonl'); bad=a.prior.entries(a.OUT/'quarantined.jsonl'); duplicate=a.prior.entries(a.OUT/'redundant.jsonl')
    assert len(cc)==821 and len(pp)==s['protected_images']
    assert len({r['path'] for r in cc})==821
    allrows=kept+bad+duplicate; assert {r['path'] for r in allrows}=={r['path'] for r in cc} and len(allrows)==821
    # Verify cached image identities plus recompute fingerprints for all new PAD rows.
    for r in pp: assert sha256_file(a.ROOT/r['path'])==r['sha256']
    for r in cc:
        fp=a.prior.fingerprints(a.ROOT/r['path'])
        for key,value in fp.items(): assert r[key]==value
    values=np.asarray([int(r['dhash64'],16) for r in pp],dtype=np.uint64)
    bits=np.arange(64,dtype=np.uint64); sha={r['sha256'] for r in pp}; pix={r['pixel_sha256'] for r in pp}
    directly_bad=set(); protected_matches={}
    # Vectorized Hamming popcount independent of BK-tree matching.
    for i,r in enumerate(cc):
        xor=values^np.uint64(int(r['dhash64'],16))
        distance=np.zeros(len(pp),dtype=np.uint8)
        for bit in bits: distance+=((xor>>bit)&np.uint64(1)).astype(np.uint8)
        match={pp[j]['path'] for j in np.flatnonzero(distance<=3)}|{x['path'] for x in pp if x['sha256']==r['sha256'] or x['pixel_sha256']==r['pixel_sha256']}
        if match: directly_bad.add(i); protected_matches[i]=match
    # Graph connectivity by known patient, identical pixels, or <=3candidate dHash.
    adjacency=[set() for _ in cc]
    for i,r in enumerate(cc):
        for j in range(i):
            z=cc[j]
            if r['source_patient_id']==z['source_patient_id'] or r['pixel_sha256']==z['pixel_sha256'] or (int(r['dhash64'],16)^int(z['dhash64'],16)).bit_count()<=3:
                adjacency[i].add(j); adjacency[j].add(i)
    pixelclasses=defaultdict(set)
    for r in cc: pixelclasses[r['pixel_sha256']].add(r['source_label'])
    directly_bad|={i for i,r in enumerate(cc) if len(pixelclasses[r['pixel_sha256']])>1}
    seen=set(); expected_bad=set(); expected_kept=set(); expected_duplicate=set()
    for i in range(len(cc)):
        if i in seen: continue
        component=set(); todo=[i]
        while todo:
            j=todo.pop()
            if j in component: continue
            component.add(j); todo.extend(adjacency[j]-component)
        seen|=component
        if component & directly_bad: expected_bad|={cc[j]['path'] for j in component}
        else:
            groups=defaultdict(list)
            for j in component: groups[cc[j]['pixel_sha256']].append(cc[j]['path'])
            for paths in groups.values():
                paths.sort(); expected_kept.add(paths[0]); expected_duplicate.update(paths[1:])
    assert expected_bad=={r['path'] for r in bad}
    assert expected_kept=={r['path'] for r in kept}
    assert expected_duplicate=={r['path'] for r in duplicate}
    reserved=a.read(a.INVENTORY/'reserved_pad_validation.json')
    assert {r['source_patient_id'] for r in kept}.isdisjoint(r['patient_id'] for r in reserved)
    assert len(kept)==s['retained_images'] and len(bad)==s['quarantined_images'] and len(duplicate)==s['redundant_images']
    assert len({r['source_patient_id'] for r in kept})==s['retained_patients']
    for d,counts in s['by_diagnosis'].items():
        assert counts['images']==sum(r['source_label']==d for r in kept)
        assert counts['patients']==len({r['source_patient_id'] for r in kept if r['source_label']==d})
    save_json(a.OUT/'verification.json',dict(status='PASS',summary_sha256=sha256_file(a.OUT/'summary.json'),
        protocol_sha256=sha256_file(a.OUT/'protocol.json'),retained_images=len(kept),
        independent_hamming_matching=True,independent_patient_component_reconstruction=True,
        preserved_pad_validation_patients=True,scope='Train preparation; similarity filtering is not proof of unknown patient independence or diagnosis correctness.'))
    print(a.read(a.OUT/'verification.json'),flush=True)


if __name__=='__main__': main()
