"""Acquire only corrected train-partition Lupus atlas images for old labels.

Reuses the unchanged ZIP range/CRC/MD5 reader, with a separate raw image/cache
directory. This does not use new-eight images, manifests or model checkpoints.
No subject IDs: auxiliary training candidates, not independent evaluation.
"""
import argparse
import hashlib
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

import download_fitzpatrick_c_supplement as fetcher
from common import save_json,sha256_file

ROOT=Path(__file__).resolve().parents[2]
META=ROOT/'SkinDisease/sources/fitzpatrick17k_corrected'
RAW=ROOT/'SkinDisease/sources/original_eight_lupus_fitzc_20261013'
OUT=ROOT/'ai-service/reports/original_eight_lupus_source_20261013'
LABELS={'lupus erythematosus':'Lupus','lupus subacute':'Lupus'}


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--prepare-only',action='store_true'); args=parser.parse_args()
    state=read(ROOT/'ai-service/reports/active_research_track.json'); assert state['active_track']=='original_eight'
    record=read(OUT/'zenodo_record.json'); files={r['key']:r for r in record['files']}
    assert record['id']==11101338 and record['metadata']['license']['id']=='cc-by-nc-4.0'
    metadata_path=META/'Fitzpatrick17k-C.csv'; metadata=fetcher.read_csv(metadata_path)
    assert hashlib.md5(metadata_path.read_bytes()).hexdigest()==files['Fitzpatrick17k-C.csv']['checksum'].split(':')[1]
    all_lupus=[r for r in metadata if r['label'] in LABELS]; selected=[r for r in all_lupus if r['partition']=='train']
    assert len(all_lupus)==330 and len(selected)==231 and len({r['md5hash'] for r in selected})==231
    archive=files['Fitzpatrick17k_CategorizedAbbrvs.zip']; assert archive['size']==fetcher.SIZE
    index={r['member']:r for r in read(META/'archive_directory.json')}
    jobs=[(r,index['Categorized_AbbrvName/'+r['filepath']]) for r in selected]
    protocol=dict(status='original_eight_lupus_auxiliary_acquisition_registered',source_record='https://zenodo.org/records/11101338',
        author_project='https://derm.cs.sfu.ca/critique/',license=record['metadata']['license'],
        source_record_sha256=sha256_file(OUT/'zenodo_record.json'),metadata_sha256=sha256_file(metadata_path),
        archive_directory_sha256=sha256_file(META/'archive_directory.json'),archive_published_md5=archive['checksum'],
        archive_size=archive['size'],label_mapping=LABELS,selected_images=231,
        selection='Exact two published source labels in corrected subset, partition=train only; no val/test rows downloaded.',
        source_partition_counts=dict(Counter(r['partition'] for r in all_lupus)),
        raw_root=RAW.relative_to(ROOT).as_posix(),
        code_sha256={n:sha256_file(ROOT/'ai-service/training'/n) for n in ('download_original_eight_lupus_supplement.py','download_fitzpatrick_c_supplement.py','common.py')},
        limits=['Atlas/source labels, not newly doctor-confirmed patient selfies.',
                'No subject IDs: auxiliary train candidates only, not independent patient evaluation.',
                'Integrity is per-image metadata MD5 and ZIP CRC/size; fullZIP checksum cannot be claimed without full download.',
                'Must audit exact/pixel/near matches against development and held images before assigning training roles.',
                'Existing source val/test metadata rows are not counted as downloaded photographs.'])
    if (OUT/'protocol.json').exists(): assert read(OUT/'protocol.json')==protocol,'Preserve registered acquisition'
    else: save_json(OUT/'protocol.json',protocol)
    if args.prepare_only: print(json.dumps(dict(registered=True,train_images=231,labels=LABELS)),flush=True); return
    assert not (OUT/'verified_images.jsonl').exists(),'Preserve completed acquisition'
    RAW.mkdir(exist_ok=True); (RAW/'images').mkdir(exist_ok=True)
    fetcher.SOURCE=RAW; fetcher.LABELS=LABELS; fetcher.RANGES=[]
    downloaded=fetcher.prepare_range_cache(jobs); verified=[]; failures=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks={pool.submit(fetcher.process,r,e):r for r,e in jobs}
        for i,t in enumerate(as_completed(tasks),1):
            try:
                row=t.result(); row['use_status']='original_eight_auxiliary_train_candidate_pending_duplicate_audit'; verified.append(row)
            except Exception as exc: failures.append(dict(image=tasks[t]['new_img_name'],error=str(exc)))
            if i%50==0 or i==len(jobs): print(json.dumps(dict(verified=len(verified),failures=len(failures),completed=i,total=len(jobs))),flush=True)
    if failures:
        save_json(OUT/'partial_failures.json',failures); raise RuntimeError('Preserve cache and retry unresolved images; no final manifest written')
    verified.sort(key=lambda r:r['local_path']); assert len(verified)==231
    manifest=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in verified)
    (OUT/'verified_images.jsonl').write_text(manifest,encoding='utf-8')
    save_json(OUT/'summary.json',dict(status='all_selected_lupus_images_integrity_verified_pending_pool_audit',
        images=231,protocol_sha256=sha256_file(OUT/'protocol.json'),manifest_sha256=sha256_file(OUT/'verified_images.jsonl'),
        by_source_label=dict(Counter(r['source_label'] for r in verified)),downloaded_range_bytes=downloaded,
        ranges=[dict(start=r['start'],end=r['end'],sha256=r['sha256'],local_path=r['local_path'].relative_to(ROOT).as_posix()) for r in fetcher.RANGES],
        source_partition='train',labels=['Lupus'],patient_ids_available=False,evaluation_eligible=False,not_trained=True))
    print(json.dumps(dict(completed=True,verified_images=231,source_labels=dict(Counter(r['source_label'] for r in verified)))),flush=True)


if __name__=='__main__': main()
