"""All-fold train metadata audit and exact decoded-pixel integrity inventory.

Does not read prediction scores, change labels, or remove images. Pixel/role
checks inspect development inventory; train summaries are separate per fold.
"""
import ast
import csv
import hashlib
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'ai-service/reports/original_eight_weak_train_audit_20261021'
MANIFEST=ROOT/'ai-service/reports/scene_grouped_oof_folds_seed42.json'
CV_PROTOCOL=ROOT/'ai-service/reports/original_eight_resnet50_cv_seed42/protocol.json'
LABELS=ROOT/'ai-service/data-sources/scin/scin_labels.csv'
ALIASES={'Acne':{'Acne'},'Candidiasis':{'Candida','Candida intertrigo'},'Eczema':{'Eczema'},
         'Lupus':{'Cutaneous lupus'},'Psoriasis':{'Psoriasis'},'Tinea':{'Tinea'},'Warts':{'Verruca vulgaris'}}
FOCUS={'Lupus','Psoriasis','Tinea'}


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):result.update(block)
    return result.hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def image_inventory(row):
    path=ROOT/row['path']
    assert path.resolve().is_relative_to(ROOT)
    assert sha(path)==row['sha256'],row['path']
    with Image.open(path) as image:
        image.load()
        rgb=image.convert('RGB')
        width,height=rgb.size
        digest=hashlib.sha256(f'{width}x{height}:RGB:'.encode()+rgb.tobytes()).hexdigest()
        gray=np.asarray(rgb.resize((128,128)).convert('L'),dtype=float)
        return dict(path=row['path'],width=width,height=height,minimum_side=min(width,height),
            pixel_sha256=digest,exif_orientation=int(image.getexif().get(274,1)),
            grayscale_mean=float(gray.mean()),grayscale_std=float(gray.std()))


def annotate(row,labels):
    item=dict(path=row['path'],label=row['class'],sha256=row['sha256'],group=row['scene_or_case_group'],
              source='SCIN' if row['path'].startswith('SkinDisease/scin-v1/') else 'original_train',
              source_case_id=None,confirmed_patient_id_available=False,flags=[])
    if item['source']=='SCIN':
        case_id=Path(row['path']).parts[4]
        weighted=ast.literal_eval(labels[case_id]['weighted_skin_condition_label'])
        assert isinstance(weighted,dict) and weighted
        weighted={str(k):float(v) for k,v in weighted.items()}
        assert all(np.isfinite(v) and v>=0 for v in weighted.values())
        top=max(weighted,key=weighted.get)
        maximum=weighted[top]
        tied=[label for label,value in weighted.items() if abs(value-maximum)<1e-12]
        if top not in ALIASES.get(row['class'],set()):item['flags'].append('source_mapping_mismatch')
        if len(tied)>1:item['flags'].append('tied_top_differential_labels')
        if maximum<.75:item['flags'].append('top_annotation_weight_below075')
        if len(tied)>1 and row['class'] in FOCUS and 'Eczema' in tied:item['flags'].append('weak_class_and_eczema_tied')
        item.update(source_case_id='SCIN::'+case_id,source_label_status='retrospective_differential_not_confirmed_diagnosis',
                    top_source_label=top,top_annotation_weight=maximum,tied_top_labels=tied,
                    weighted_source_labels=weighted)
    else:
        item.update(source_label_status='folder_label_original_diagnostic_evidence_unavailable')
    return item


def cell(rows):
    return dict(images=len(rows),groups=len({row['group'] for row in rows}),
        known_source_cases=len({row['source_case_id'] for row in rows if row['source_case_id']}),
        source_mapping_mismatches=sum('source_mapping_mismatch' in row['flags'] for row in rows),
        top_tied_images=sum('tied_top_differential_labels' in row['flags'] for row in rows),
        top_tied_cases=len({row['source_case_id'] for row in rows if 'tied_top_differential_labels' in row['flags']}),
        top_weight_below075_images=sum('top_annotation_weight_below075' in row['flags'] for row in rows),
        weak_eczema_tie_images=sum('weak_class_and_eczema_tied' in row['flags'] for row in rows),
        minimum_side_below128=sum(row['minimum_side']<128 for row in rows),
        nondefault_orientation_images=sum(row['exif_orientation'] not in (0,1) for row in rows),
        source_label_status=dict(Counter(row['source_label_status'] for row in rows)))


def main():
    assert not (OUT/'summary.json').exists(),'Preserve completed audit'
    source_paths=[MANIFEST,CV_PROTOCOL,LABELS,ROOT/'ai-service/scripts/prepare_scin.py',ROOT/'ai-service/models/best_model.pth']
    protocol=dict(date='2026-10-21',purpose='Train metadata audit in all5 original folds; global exact-pixel split integrity only',
        source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in source_paths},code_sha256=sha(Path(__file__)),
        scope='No prediction arrays, no automatic diagnostic relabeling, no image removals or serving changes. Annotation weights are not diagnosis probabilities.',
        alias_map={key:sorted(value) for key,value in ALIASES.items()},
        quality='Decode Pillow RGB; hash dimensions and RGB bytes; metadata min side<128 and nondefault EXIF are review flags, not automatic exclusions.')
    save(OUT/'protocol.json',protocol)
    manifest=read(MANIFEST)['images'];cv=read(CV_PROTOCOL)
    with LABELS.open(encoding='utf-8-sig',newline='') as stream:labels={row['case_id']:row for row in csv.DictReader(stream)}
    items={row['path']:annotate(row,labels) for row in manifest}
    with ThreadPoolExecutor(max_workers=4) as executor:
        for index,quality in enumerate(executor.map(image_inventory,manifest),1):
            items[quality['path']].update(quality)
            if index%500==0:print(json.dumps(dict(images_checked=index)),flush=True)
    digest_groups=defaultdict(list)
    for item in items.values():digest_groups[item['pixel_sha256']].append(item)
    repeated=[members for members in digest_groups.values() if len(members)>1]
    folds=[];review_queue=[]
    for fold in range(5):
        roles=cv['folds'][fold]['roles'];train=[items[path] for path in roles['train']]
        role_lookup={path:role for role,paths in roles.items() for path in paths}
        assert len(role_lookup)==len(items)==5937
        cross_pixels=[]
        for members in repeated:
            roles_seen={role_lookup[row['path']] for row in members}
            if len(roles_seen)>1:cross_pixels.append(dict(roles=sorted(roles_seen),paths=[row['path'] for row in members]))
        cases=defaultdict(set);groups=defaultdict(set)
        for path,role in role_lookup.items():
            item=items[path]
            if item['source_case_id']:cases[item['source_case_id']].add(role)
            groups[item['group']].add(role)
        cross_cases=[case for case,roles_seen in cases.items() if len(roles_seen)>1]
        cross_groups=[group for group,roles_seen in groups.items() if len(roles_seen)>1]
        cells=[]
        for source in ['original_train','SCIN']:
            for label in cv['classes']:
                rows=[item for item in train if item['source']==source and item['label']==label]
                if rows:cells.append(dict(source=source,label=label,**cell(rows)))
        folds.append(dict(fold=fold,train_images=len(train),train_class_counts=dict(Counter(row['label'] for row in train)),
            cells=cells,cross_role_decoded_pixel_groups=cross_pixels,cross_role_known_cases=cross_cases,cross_role_scene_groups=cross_groups))
        for item in train:
            reasons=[flag for flag in item['flags'] if flag in ['source_mapping_mismatch','tied_top_differential_labels','weak_class_and_eczema_tied']]
            if item['minimum_side']<128:reasons.append('minimum_side_below128')
            if item['exif_orientation'] not in (0,1):reasons.append('nondefault_orientation')
            if item['label'] in FOCUS and reasons:
                review_queue.append(dict(fold=fold,role='train',review_reasons=reasons,diagnostic_error_confirmed=False,**item))
    summary=dict(images_in_development_inventory=len(items),folds=folds,
        unique_decoded_pixel_duplicate_groups=len(repeated),
        source_mapping_mismatches=sum('source_mapping_mismatch' in row['flags'] for row in items.values()),
        cross_role_pixel_groups=sum(len(f['cross_role_decoded_pixel_groups']) for f in folds),
        cross_role_known_cases=sum(len(f['cross_role_known_cases']) for f in folds),
        cross_role_scene_groups=sum(len(f['cross_role_scene_groups']) for f in folds),
        unique_focus_review_images=len({row['path'] for row in review_queue}),review_rows_per_fold=len(review_queue),
        labels_changed=0,images_removed=0,serving_changed=False,
        interpretation='Differential ties and small images are metadata review flags, not proof of incorrect diagnosis. Original folder-label validity remains unknown.')
    save(OUT/'image_inventory.json',list(items.values()))
    with (OUT/'focus_train_review.jsonl').open('w',encoding='utf-8') as stream:
        for row in review_queue:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    save(OUT/'summary.json',summary)
    for path,expected in protocol['source_sha256'].items():assert sha(ROOT/path)==expected
    technical_ok=summary['source_mapping_mismatches']==summary['cross_role_pixel_groups']==summary['cross_role_known_cases']==summary['cross_role_scene_groups']==0
    save(OUT/'verification.json',dict(status='PASS' if technical_ok else 'REVIEW_REQUIRED',
        scope='Metadata/image integrity and known-case separation; not diagnosis verification',
        images_sha256_checked=5937,decoded_images=5937,protocol_sha256=sha(OUT/'protocol.json'),summary_sha256=sha(OUT/'summary.json'),
        labels_changed=0,images_removed=0,serving_changed=False))
    print(json.dumps({key:value for key,value in summary.items() if key!='folds'}),flush=True)
    print('technical_status='+('PASS' if technical_ok else 'REVIEW_REQUIRED'),flush=True)


if __name__=='__main__':main()
