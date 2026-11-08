"""Independently verify old-eight supplement identity, quarantine and roles."""
import csv
import hashlib
import json
import zlib
from collections import Counter,defaultdict
from pathlib import Path

import numpy as np
from PIL import Image,ImageOps
from common import CLASSES,save_json,sha256_file
from prepare_original_eight_supplement import ROOT,OUT,RAW_REPORT,OUTER,SPLIT,DC,read,entries
from evaluate_new_ensemble_holdout import read_new_samples


def actual_fingerprints(path):
    data=path.read_bytes()
    with Image.open(path) as im:
        im.load(); rgb=ImageOps.exif_transpose(im).convert('RGB'); w,h=rgb.size
        pixel=hashlib.sha256(f'{w},{h}:'.encode()+rgb.tobytes()).hexdigest()
        gray=np.asarray(im.convert('L').resize((9,8),Image.Resampling.LANCZOS))
        bits=(gray[:,1:]>gray[:,:-1]).ravel(); value=0
        for bit in bits: value=(value<<1)|int(bit)
    return hashlib.sha256(data).hexdigest(),pixel,f'{value:016x}'


def main():
    protocol=read(OUT/'protocol.json'); summary=read(OUT/'summary.json')
    assert protocol['classes']==summary['classes']==CLASSES and summary['protocol_sha256']==sha256_file(OUT/'protocol.json')
    for path,h in protocol['sources'].items(): assert sha256_file(ROOT/path)==h
    for path,h in protocol['code_sha256'].items(): assert sha256_file(ROOT/'ai-service/training'/path)==h
    for name,h in summary['artifact_sha256'].items(): assert sha256_file(OUT/name)==h
    assert summary['training_manifest_sha256']==sha256_file(OUT/'training_candidates.jsonl')
    acquisition=read(RAW_REPORT/'protocol.json'); raw_summary=read(RAW_REPORT/'summary.json')
    assert raw_summary['protocol_sha256']==sha256_file(RAW_REPORT/'protocol.json')
    for name,h in acquisition['code_sha256'].items(): assert sha256_file(ROOT/'ai-service/training'/name)==h
    source=ROOT/'SkinDisease/sources/fitzpatrick17k_corrected'; record=read(RAW_REPORT/'zenodo_record.json')
    assert acquisition['source_record_sha256']==sha256_file(RAW_REPORT/'zenodo_record.json') and record['id']==11101338 and record['metadata']['license']['id']=='cc-by-nc-4.0'
    assert acquisition['metadata_sha256']==sha256_file(source/'Fitzpatrick17k-C.csv') and acquisition['archive_directory_sha256']==sha256_file(source/'archive_directory.json')
    with (source/'Fitzpatrick17k-C.csv').open(encoding='utf-8-sig',newline='') as f: metadata=list(csv.DictReader(f))
    selected={r['new_img_name']:r for r in metadata if r['label'] in acquisition['label_mapping'] and r['partition']=='train'}
    directory={r['member']:r for r in read(source/'archive_directory.json')}
    acquired=entries(RAW_REPORT/'verified_images.jsonl'); assert len(acquired)==len(selected)==231
    assert {Path(r['local_path']).name for r in acquired}==set(selected)
    for r in acquired:
        p=ROOT/r['local_path']; meta=selected[p.name]; entry=directory['Categorized_AbbrvName/'+meta['filepath']]; data=p.read_bytes()
        assert hashlib.md5(data).hexdigest()==meta['md5hash']==r['source_md5'] and len(data)==entry['uncompressed_bytes'] and zlib.crc32(data)==entry['crc32']
        assert r['source_label']==meta['label'] and r['source_partition']=='train' and r['label']=='Lupus' and not r['evaluation_eligible']
    candidates=entries(OUT/'candidate_fingerprints.jsonl'); protected=entries(OUT/'protected_fingerprints.jsonl')
    kept=entries(OUT/'training_candidates.jsonl'); quarantined=entries(OUT/'quarantined.jsonl'); redundant=entries(OUT/'redundant.jsonl')
    candidate_by_path={r['path']:r for r in candidates}
    for r in [*kept,*quarantined,*redundant]:
        assert all(r[k]==v for k,v in candidate_by_path[r['path']].items())
    assert len(candidates)==summary['input_candidates']==821 and len(protected)==summary['protected_images']==7926
    assert len({r['path'] for r in candidates})==821 and len({r['path'] for r in protected})==7926
    expected_old={r['path']:r['sha256'] for r in read(OUTER)['images']}
    assert {r['path']:r['sha256'] for r in protected if r['role']=='original_development'}==expected_old
    for r in [*candidates,*protected]:
        assert sha256_file(ROOT/r['path'])==r['sha256']
    for r in candidates:
        assert actual_fingerprints(ROOT/r['path'])==(r['sha256'],r['pixel_sha256'],r['dhash64'])
        assert r['label'] in CLASSES and not r['evaluation_eligible']
    assert sum(r['source']=='Fitzpatrick17k-C' for r in candidates)==231
    for r in candidates:
        if r['source']=='Fitzpatrick17k-C': assert r['source_partition']=='train' and r['source_case_id'] is None and not r['subject_id_available']
    role_samples={k:read_new_samples(DC,SPLIT/f'{k}.csv')[0] for k in ('train','validation','official_test')}
    case_sets={k:{s.group_id for s in v} for k,v in role_samples.items()}
    for a,b in [('train','validation'),('train','official_test'),('validation','official_test')]: assert case_sets[a].isdisjoint(case_sets[b])
    train_expected={s.path.relative_to(ROOT).as_posix():(CLASSES[s.label],s.group_id) for s in role_samples['train']}
    assert {r['path']:(r['label'],r['source_case_id']) for r in candidates if r['source']=='DermaCon-IN-v1'}==train_expected
    assert all((OUT/'protocol.json').stat().st_mtime_ns<(OUT/n).stat().st_mtime_ns for n in ('candidate_fingerprints.jsonl','training_candidates.jsonl'))
    # Independent exhaustive comparisons and components, rather than BK-tree queries.
    parents=list(range(len(candidates)))
    def find(i):
        while parents[i]!=i: i=parents[i]
        return i
    def join(i,j): parents[find(i)]=find(j)
    people={}; pixels=defaultdict(list); hits=set(); conflicts=set(); links=[]
    for i,r in enumerate(candidates):
        if r['source_case_id']:
            key=r['source'],r['source_case_id']
            if key in people: join(i,people[key])
            else: people[key]=i
        pixels[r['pixel_sha256']].append(i)
        value=int(r['dhash64'],16)
        if any(r['sha256']==p['sha256'] or r['pixel_sha256']==p['pixel_sha256'] or (value^int(p['dhash64'],16)).bit_count()<=3 for p in protected): hits.add(i)
        for j in range(i):
            distance=(value^int(candidates[j]['dhash64'],16)).bit_count()
            if distance<=3:
                join(i,j); links.append(dict(a=r['path'],b=candidates[j]['path'],distance=distance))
    for ids in pixels.values():
        for i in ids[1:]: join(ids[0],i)
        if len({candidates[i]['label'] for i in ids})>1: conflicts.update(ids)
    assert {tuple(sorted(r.items())) for r in links}=={tuple(sorted(r.items())) for r in read(OUT/'similarity_links.json')}
    components=defaultdict(list)
    for i in range(len(candidates)): components[find(i)].append(i)
    expected_kept={}; expected_quarantine={}; expected_redundant={}
    for ids in components.values():
        gid='supplement_'+hashlib.sha256('\n'.join(sorted(candidates[i]['sha256'] for i in ids)).encode()).hexdigest()[:24]
        if any(i in hits or i in conflicts for i in ids):
            expected_quarantine.update({candidates[i]['path']:gid for i in ids}); continue
        pp=defaultdict(list)
        for i in ids: pp[candidates[i]['pixel_sha256']].append(i)
        for values in pp.values():
            values.sort(key=lambda i:(candidates[i]['source']!='DermaCon-IN-v1',candidates[i]['path']))
            expected_kept[candidates[values[0]]['path']]=gid
            expected_redundant.update({candidates[i]['path']:(gid,candidates[values[0]]['path']) for i in values[1:]})
    assert {r['path']:r['image_group'] for r in kept}==expected_kept
    assert {r['path']:r['image_group'] for r in quarantined}==expected_quarantine
    assert {r['path']:(r['image_group'],r['retained_path']) for r in redundant}==expected_redundant
    assert len(kept)+len(quarantined)+len(redundant)==821 and summary['direct_protected_match_images']==len(hits)
    for name,rows in [('retained_images',kept),('quarantined_images',quarantined),('redundant_images',redundant)]: assert summary[name]==len(rows)
    assert len({r['pixel_sha256'] for r in kept})==len(kept)
    assert all(r['role']=='auxiliary_train_only' for r in kept) and summary['training_not_started']
    for c in CLASSES:
        rr=[r for r in kept if r['label']==c]
        assert summary['by_class'][c]==dict(retained=len(rr),by_source=dict(Counter(r['source'] for r in rr)))
    state=read(ROOT/'ai-service/reports/active_research_track.json')
    assert state['active_track']=='original_eight' and state['classes']==CLASSES and sha256_file(ROOT/state['serving_checkpoint'])==state['serving_checkpoint_sha256']
    assert sha256_file(ROOT/state['benchmark']['report_path'])==state['benchmark']['report_sha256']
    save_json(OUT/'verification.json',dict(status='PASS',verifier_code_sha256=sha256_file(Path(__file__)),summary_sha256=sha256_file(OUT/'summary.json'),
        acquisition_images=231,retained_images=len(kept),protocol_sha256=sha256_file(OUT/'protocol.json'),
        checks=['Original eight class taxonomy and source/code hashes','All231 images MD5, ZIP CRC/size and corrected train metadata',
                'Current source SHA and all candidate canonical pixel/dHash fingerprints','7926protected images, including original5937and held source roles',
                'DermaCon case-disjoint roles and original590train identities','Exhaustive independent protected/candidate similarity comparisons',
                'Independent case/similarity components, quarantine and representative reconstruction','Exact image accounting and manifest role flags',
                'Original benchmark and serving checkpoint unchanged; no training or accuracy claim']))
    lines=['# Dữ liệu bổ sung cho bộ tám bệnh cũ','',
        '**Chuẩn bị xong, kiểm chứng PASS; chưa train và chưa có điểm accuracy mới.**','',
        'Đã tải và xác minh231ảnh Lupus thuộc partition train của Fitzpatrick17k-C. Tái sử dụng590ảnh train phát triển DermaCon; đây là ảnh đã có và từng dùng nghiên cứu, không phải590ảnh mới tải. Giữ nguyên tám nhãn cũ.','',
        f"Đối chiếu{len(protected)}ảnh được bảo vệ bằng SHA-256, pixel RGB chuẩn hóa EXIF và dHash≤3; giữ{len(kept)}ảnh, để riêng{len(quarantined)}ảnh theo nhóm, loại{len(redundant)}bản pixel lặp trong các nhóm được giữ.",'',
        '| Bệnh | DermaCon giữ lại | Lupus atlas giữ lại | Tổng bổ sung |','|---|---:|---:|---:|']
    for c in CLASSES:
        by=summary['by_class'][c]['by_source']; lines.append(f"| {c} | {by.get('DermaCon-IN-v1',0)} | {by.get('Fitzpatrick17k-C',0)} | {summary['by_class'][c]['retained']} |")
    lines+=['',f"Ảnh atlas còn giữ nhưng thiếu mã bệnh nhân: {summary['atlas_images_without_subject_id']}; chỉ dùng làm dữ liệu train phụ, không dùng làm test độc lập theo người.",
        '- Manifest bổ sung để riêng; bộ OOF5937ảnh, điểm78,07%/76,82% và điểm công thức thử79,06%/77,98% không thay đổi.',
        '- Sau khi thêm DermaCon train vào một model, toàn bộ986ảnh DermaCon không còn là holdout của model đó. Dùng đúng validation213/test183đã tách ca; các phần này cũng đã được xem trước đây.',
        '- Tập nguồn có nhãn công bố; kiểm chứng dữ liệu không xác nhận lại chẩn đoán của bác sĩ.',
        '- DHash chỉ chỉ ra ảnh nghi giống; cách để riêng cả nhóm là lựa chọn bảo thủ, không kết luận ảnh thật sự trùng hoặc nhãn sai.',
        '', 'Nguồn: [dự án phân tích chất lượng dữ liệu](https://derm.cs.sfu.ca/critique/), [bản Zenodo11101338](https://zenodo.org/records/11101338), giấy phép nghiên cứu CC BY-NC4.0 và giữ ghi công/điều kiện nguồn gốc.',
        '', '[Manifest train phụ](training_candidates.jsonl), [ảnh để riêng](quarantined.jsonl), [số liệu](summary.json), [xác minh](verification.json), [giao thức](protocol.json).','']
    (OUT/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(verification='PASS',acquired_images=231,retained_images=len(kept),by_source=summary['by_source'],by_class=summary['by_class'])),flush=True)


if __name__=='__main__': main()
