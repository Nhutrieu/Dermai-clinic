"""Inventory only the historical patient-split PAD cancer training role.

No predictions or fitting. Candidates remain ineligible until a fresh overlap
audit protects the current original-eight and source held roles.
"""
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from common import save_json, sha256_file

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'ai-service/reports/original_eight_pad_train_inventory_20261013'
DATA=ROOT/'SkinDisease/sources/pad_ufes20/extracted'
REPORT=ROOT/'ai-service/reports/paper_ensemble_benchmark/pad_ufes_external_evaluation.json'
HISTORY=ROOT/'ai-service/candidates/pad_cancer_probe_pilot.json'
SOURCE=ROOT/'ai-service/reports/paper_ensemble_benchmark/pad_ufes_source_manifest.json'


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def main():
    assert not (OUT/'summary.json').exists(),'Preserve completed inventory'
    source=read(SOURCE); assert source['license']=='CC BY 4.0'
    assert sha256_file(DATA/'metadata.csv')==source['metadata_sha256']
    with (DATA/'metadata.csv').open(encoding='utf-8-sig',newline='') as f: meta={r['img_id']:r for r in csv.DictReader(f)}
    prior=read(REPORT)
    near_ids={r['pad_img_id'] for r in prior['overlap_audit']['potential_dhash_matches']}
    excluded={r['patient_id'] for r in prior['predictions'] if r['img_id'] in near_ids}|set(prior['internal_duplicate_audit']['diagnosis_conflict_patients'])
    # Extract identities/metadata only, never use old probability/flag columns.
    rows=[dict(img_id=r['img_id'],patient_id=r['patient_id'],diagnostic=r['diagnostic']) for r in prior['predictions'] if r['patient_id'] not in excluded]
    assert len(rows)==2150
    y=np.asarray([0 if r['diagnostic'] in {'NEV','SEK'} else 1 if r['diagnostic'] in {'BCC','SCC','MEL'} else 2 for r in rows])
    groups=np.asarray([r['patient_id'] for r in rows])
    tr,va=next(StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=42).split(np.zeros(len(rows)),y,groups))
    assert len(tr)==1703 and len(va)==447 and set(groups[tr]).isdisjoint(groups[va])
    history=read(HISTORY)['split']
    assert history['train_diagnosis_counts']==dict(Counter(rows[i]['diagnostic'] for i in tr))
    assert history['validation_diagnosis_counts']==dict(Counter(rows[i]['diagnostic'] for i in va))
    candidates=[i for i in tr if rows[i]['diagnostic'] in {'BCC','SCC','MEL'}]
    assert len(candidates)==821
    fileindex={p.name:p for p in (DATA/'images').rglob('*.png')}
    assert len(fileindex)==2298
    protocol=dict(source_url=source['source_url'],license=source['license'],classes_kept={'BCC':'SkinCancer','SCC':'SkinCancer','MEL':'SkinCancer'},
        sources={p.relative_to(ROOT).as_posix():sha256_file(p) for p in [REPORT,HISTORY,SOURCE,DATA/'metadata.csv']},
        code_sha256=sha256_file(Path(__file__)),
        original_patient_split='Exact historical cleaned2150row ordering; StratifiedGroupKFold5seed42first split, binary category strata as original PAD probe. All447validation rows/patients stay reserved.',
        selection='Original train only, BCC/SCC/MEL with biopsed=True; ACK/NEV/SEK have no valid mapping to remaining original8labels and are not relabelled.',
        role='Candidate auxiliary train only, no fitting and not yet eligible. Complete current exact/pixel/near-image audit before use.',
        limits=['Prior PAD results already inspected; source cannot become fresh independent test.',
                'Historical PAD split reserved; consuming only its train role invalidates any later whole-PAD holdout claim.',
                '821is pre-current-audit candidate count, not newly acquired photos or accepted training count.',
                'Biopsy field verifies published metadata, not new clinical review by this project.'])
    save_json(OUT/'protocol.json',protocol)
    result=[]
    for i in candidates:
        r=rows[i]; m=meta[r['img_id']]; path=fileindex[r['img_id']]
        assert m['patient_id']==r['patient_id'] and m['diagnostic']==r['diagnostic'] and m['biopsed']=='True'
        result.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha256_file(path),label='SkinCancer',
            source='PAD-UFES-20',source_label=r['diagnostic'],source_patient_id=r['patient_id'],source_lesion_id=m['lesion_id'],
            biopsy_confirmed_in_published_metadata=True,source_partition='historical_development_train',
            role='candidate_auxiliary_train_only',training_eligible=False,evaluation_eligible=False,
            pending='Current exact SHA/canonical pixel/dHash overlap quarantine including protected source roles and patient groups.'))
    (OUT/'training_candidates.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in result),encoding='utf-8')
    reserved=[dict(**rows[i],role='preserved_historical_validation') for i in va]
    save_json(OUT/'reserved_pad_validation.json',reserved)
    bydiag={d:dict(images=sum(r['source_label']==d for r in result),patients=len({r['source_patient_id'] for r in result if r['source_label']==d})) for d in ('BCC','SCC','MEL')}
    # Independently match saved candidate/reserved identities to official metadata.
    assert set(r['source_patient_id'] for r in result).isdisjoint(r['patient_id'] for r in reserved)
    assert len({r['path'] for r in result})==821
    save_json(OUT/'summary.json',dict(status='inventory_verified_overlap_audit_pending_not_trained',
        candidate_images=821,candidate_patients=len({r['source_patient_id'] for r in result}),by_diagnosis=bydiag,
        reserved_pad_images=447,reserved_pad_patients=len({r['patient_id'] for r in reserved}),
        training_eligible_images=0,new_downloads=0,protocol_sha256=sha256_file(OUT/'protocol.json'),
        manifest_sha256=sha256_file(OUT/'training_candidates.jsonl'),reserved_sha256=sha256_file(OUT/'reserved_pad_validation.json')))
    save_json(OUT/'verification.json',dict(status='PASS_INVENTORY_ONLY',summary_sha256=sha256_file(OUT/'summary.json'),
        historical_split_counts_match=True,reserved_patient_overlap=0,published_metadata_biopsy_fields_match=True,
        all_candidate_file_sha256_recorded=True,overlap_audit_complete=False,training_not_started=True))
    print(json.dumps(read(OUT/'summary.json')),flush=True)


if __name__=='__main__': main()
