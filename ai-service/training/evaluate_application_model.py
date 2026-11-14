"""Evaluate the frozen serving API, preserving abstentions and audit provenance.

prepare -> run -> score -> verify. Historical holdouts are retrospective,
not a new independent clinical test. No training or threshold selection.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
import mimetypes
import os
from pathlib import Path
import platform
import sys
import time

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / 'ai-service'
REPORT = AI / 'reports/application_evaluation_20261110'
PACKAGE = AI / 'models/research_pipeline'
CLASSES = ['Acne', 'Candidiasis', 'Eczema', 'Lupus', 'Psoriasis', 'SkinCancer', 'Tinea', 'Warts']
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def rel(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def fingerprint(path):
    data = Path(path).read_bytes()
    with Image.open(io.BytesIO(data)) as image:
        rgb = image.convert('RGB'); w, h = rgb.size
        pixels = hashlib.sha256(f'{w}x{h}:RGB:'.encode() + rgb.tobytes()).hexdigest()
        a = np.asarray(rgb.convert('L').resize((9, 8), Image.Resampling.LANCZOS), dtype=np.int16)
        value = 0
        for bit in (a[:, 1:] > a[:, :-1]).flat:
            value = (value << 1) | int(bit)
    return dict(path=rel(path), sha256=hashlib.sha256(data).hexdigest(),
                pixel_sha256=pixels, dhash64=f'{value:016x}', width=w, height=h)


class HammingTree:
    def __init__(self, values):
        self.nodes = []
        for index, value in enumerate(values):
            if not self.nodes:
                self.nodes.append([value, [index], {}]); continue
            node = 0
            while True:
                v, ids, edges = self.nodes[node]; distance = (value ^ v).bit_count()
                if distance == 0:
                    ids.append(index); break
                if distance not in edges:
                    edges[distance] = len(self.nodes)
                    self.nodes.append([value, [index], {}]); break
                node = edges[distance]

    def query(self, value, radius=3):
        found, todo = [], ([0] if self.nodes else [])
        while todo:
            v, indices, edges = self.nodes[todo.pop()]; d = (value ^ v).bit_count()
            if d <= radius:
                found.extend(indices)
            todo.extend(n for edge, n in edges.items() if d - radius <= edge <= d + radius)
        return found


def scin_case(path):
    parts = Path(path).parts
    if 'scin-v1' not in parts:
        return None
    i = parts.index('scin-v1')
    return parts[i + 3] if len(parts) > i + 4 else None


def leakage_reasons(row, byte_set, pixel_set, cases, reviewed, tree):
    reasons = []
    if row['sha256'] in byte_set:
        reasons.append('same_bytes_as_protected')
    if row['pixel_sha256'] in pixel_set:
        reasons.append('same_RGB_pixels_as_protected')
    case = scin_case(row['path'])
    if case is not None and case in cases:
        reasons.append('same_SCIN_case_as_protected')
    if row['sha256'] in reviewed:
        reasons.append('historically_reviewed_same_scene')
    near = tree.query(int(row['dhash64'], 16))
    if near:
        reasons.append('conservative_dhash_distance_le3')
    return reasons, near


def metrics(records):
    """Fixed eight labels; the ninth prediction column is an API abstention."""
    cm = np.zeros((8, 9), dtype=np.int64)
    for row in records:
        y = CLASSES.index(row['label'])
        d = CLASSES.index(row['disease']) if row['http_status'] == 200 else 8
        cm[y, d] += 1
    total = int(cm.sum()); returned = int(cm[:, :8].sum()); correct = int(cm[:, :8].diagonal().sum())
    support = cm.sum(1); predicted = cm[:, :8].sum(0); tp = cm[:, :8].diagonal()
    f1 = np.divide(2 * tp, support + predicted, out=np.zeros(8, float), where=support + predicted > 0)
    accepted_support = cm[:, :8].sum(1)
    accepted_f1 = np.divide(2 * tp, accepted_support + predicted, out=np.zeros(8, float), where=accepted_support + predicted > 0)
    per_class = {}
    for i, name in enumerate(CLASSES):
        per_class[name] = dict(support=int(support[i]), returned=int(accepted_support[i]),
            rejected=int(cm[i, 8]), correct=int(tp[i]),
            precision=float(tp[i] / predicted[i]) if predicted[i] else 0.,
            recall=float(tp[i] / support[i]) if support[i] else None,
            f1=float(f1[i]),
            recall_on_returned=float(tp[i] / accepted_support[i]) if accepted_support[i] else None)
    return dict(input_images=total, returned_predictions=returned, rejected_images=total-returned,
        correct_returned=correct, coverage=returned/total if total else None,
        accuracy_on_returned=correct/returned if returned else None,
        correct_return_rate=correct/total if total else None,
        macro_f1_8class_with_abstentions=float(f1.mean()) if total else None,
        macro_f1_present_classes_with_abstentions=float(f1[support > 0].mean()) if total else None,
        macro_f1_8class_on_returned=float(accepted_f1.mean()) if returned else None,
        all_8_classes_present=bool((support > 0).all()),
        uncertain_returned=sum(row['http_status'] == 200 and row['uncertain'] for row in records),
        per_class=per_class, confusion_matrix_8x9=cm.tolist(),
        true_labels=CLASSES, predicted_labels=CLASSES+['API_rejected'],
        rejection_reasons=dict(Counter(row.get('detail', '') for row in records if row['http_status'] != 200)))


def bootstrap(records, repetitions=1000):
    groups = defaultdict(list)
    for row in records:
        groups[row['group']].append(row)
    names = sorted(groups); rng = np.random.default_rng(42)
    keys = ['coverage', 'accuracy_on_returned', 'correct_return_rate', 'macro_f1_8class_with_abstentions']
    values = {k:[] for k in keys}
    for _ in range(repetitions):
        rows = [v for i in rng.integers(0, len(names), size=len(names)) for v in groups[names[i]]]
        result = metrics(rows)
        for k in keys:
            if result[k] is not None:
                values[k].append(result[k])
    return dict(groups=len(names), repetitions=repetitions, seed=42,
        limitations='SCIN uses source case IDs; original-source groups use dHash connected components, not verified patient IDs. Intervals do not account for adaptive historical research exposure.',
        percentile_95={k:np.quantile(v, [.025, .975]).tolist() if v else None for k,v in values.items()})


def verify_frozen(p):
    for path, expected in p['frozen_sha256'].items():
        if sha(ROOT / path) != expected:
            raise ValueError(f'Frozen source or package changed: {path}')


def prepare(out, device):
    if (out / 'protocol.json').exists():
        raise FileExistsError('Preserve registered evaluation; choose a new output for a new protocol')
    out.mkdir(parents=True, exist_ok=True)
    classes = set(CLASSES)
    protected_paths = sorted({p.resolve() for base in [ROOT/'SkinDisease/train', ROOT/'SkinDisease/scin-v1/train']
        for p in base.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS
        and p.relative_to(base).parts[0] in classes})
    cohort_file = AI/'reports/scene_grouped_oof_folds_seed42.json'
    cohort = read(cohort_file)['images']
    if not {str(ROOT/r['path']) for r in cohort} <= {str(p) for p in protected_paths}:
        raise ValueError('Protected raw training roots do not cover all 5937 CNN/meta development images')
    candidate_paths = sorted(p.resolve() for base in [ROOT/'SkinDisease/test', ROOT/'SkinDisease/scin-v1/external_test']
        for p in base.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS
        and p.relative_to(base).parts[0] in classes)
    all_paths = protected_paths + candidate_paths
    print(f'Fingerprinting {len(protected_paths)} protected and {len(candidate_paths)} candidate files', flush=True)
    fingers = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i, row in enumerate(pool.map(fingerprint, all_paths), 1):
            fingers.append(row)
            if i % 1000 == 0:
                print(f'Fingerprint progress {i}/{len(all_paths)}', flush=True)
    protected = fingers[:len(protected_paths)]; candidates = fingers[len(protected_paths):]
    by_path = {r['path']:r for r in protected}
    for row in cohort:
        if by_path[row['path']]['sha256'] != row['sha256']:
            raise ValueError('Current training image differs from frozen cohort: '+row['path'])
    source_files = [cohort_file]
    expected = {}
    for name, dataset in [('fixed_test_predictions.json', 'historical_fixed_test'),
                          ('scin_external_test_predictions.json', 'SCIN_case_holdout')]:
        path = AI/'reports/ai_evidence'/name;source_files.append(path)
        for row in read(path)['predictions']:
            expected[(dataset, row['sample_id'].removeprefix('sha256:'))] = row['true_label']
    tree = HammingTree([int(v['dhash64'],16) for v in protected])
    byte_set = {v['sha256'] for v in protected}; pixel_set = {v['pixel_sha256'] for v in protected}
    cases = {v for r in protected if (v := scin_case(r['path'])) is not None}
    review_file = AI/'reports/historical_same_scene_review.json'; source_files.append(review_file)
    reviewed = set()
    for pair in read(review_file)['pairs']:
        if pair['decision'].startswith('same_scene'):
            reviewed.add(pair['test_sha256'])
    audit, eligible = [], []
    for row in candidates:
        parts = Path(row['path']).parts
        dataset = 'SCIN_case_holdout' if 'scin-v1' in parts else 'historical_fixed_test'
        label = parts[parts.index('external_test')+1] if dataset=='SCIN_case_holdout' else parts[parts.index('test')+1]
        row.update(dataset=dataset, label=label,
            label_status='Existing source/dataset label; no new project clinical confirmation',
            prior_research_exposure=True)
        reasons, near = leakage_reasons(row, byte_set, pixel_set, cases, reviewed, tree)
        if (dataset,row['sha256']) not in expected:
            reasons.append('not_in_historical_label_cleaned_reference_set')
        elif expected[(dataset,row['sha256'])] != label:
            reasons.append('historical_reference_label_conflict')
        row['exclusion_reasons'] = reasons
        row['near_protected_examples'] = [protected[j]['path'] for j in near[:3]]
        audit.append(row)
    # Reject conflicting byte/pixel labels; keep a fixed canonical copy of exact duplicates.
    for key in ['sha256', 'pixel_sha256']:
        grouped = defaultdict(list)
        for row in audit:
            grouped[row[key]].append(row)
        for rr in grouped.values():
            if len({r['label'] for r in rr}) > 1:
                for r in rr:
                    r['exclusion_reasons'].append('candidate_label_conflict_'+key)
    seen_bytes, seen_pixels = set(), set()
    for row in sorted(audit, key=lambda r:(r['dataset'],r['path'])):
        if not row['exclusion_reasons']:
            if row['sha256'] in seen_bytes or row['pixel_sha256'] in seen_pixels:
                row['exclusion_reasons'].append('candidate_exact_duplicate')
            else:
                seen_bytes.add(row['sha256']);seen_pixels.add(row['pixel_sha256']);eligible.append(dict(row))
    # Fixed group proxies for uncertainty estimates, constructed before inference.
    for dataset in ['historical_fixed_test','SCIN_case_holdout']:
        rows = [r for r in eligible if r['dataset']==dataset]
        parent = list(range(len(rows)))
        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]; i = parent[i]
            return i
        local = HammingTree([int(r['dhash64'],16) for r in rows])
        case_first = {}
        for i,row in enumerate(rows):
            linked = local.query(int(row['dhash64'],16))
            case = scin_case(row['path'])
            if case is not None:
                linked.append(case_first.setdefault(case,i))
            for j in linked:
                a,b=find(i),find(j)
                if a != b:parent[max(a,b)] = min(a,b)
        for i,row in enumerate(rows):
            row['group'] = f'{dataset}:proxy:{find(i)}'
    if not eligible:
        raise ValueError('No eligible retrospective holdout images after leakage audit')
    summary = {}
    for dataset in ['historical_fixed_test','SCIN_case_holdout']:
        rr = [r for r in audit if r['dataset']==dataset]; kept = [r for r in eligible if r['dataset']==dataset]
        summary[dataset] = dict(candidates=len(rr), eligible=len(kept), excluded=len(rr)-len(kept),
            class_counts={c:sum(r['label']==c for r in kept) for c in CLASSES},
            exclusion_reasons=dict(Counter(reason for r in rr for reason in r['exclusion_reasons'])),
            prior_research_exposure=True, blind_independent_test=False)
    write(out/'audit.json',dict(protected_images=len(protected), source_summary=summary, candidates=audit))
    write(out/'protected_fingerprints.json',protected)
    write(out/'evaluation_manifest.json',eligible)
    source_files += [Path(__file__),AI/'tests/test_application_evaluation.py',out/'audit.json',out/'protected_fingerprints.json',out/'evaluation_manifest.json']
    source_files += list((AI/'app').glob('*.py'))
    manifest_file = PACKAGE/'manifest.json'; m = read(manifest_file); source_files.append(manifest_file)
    for entry in m['assets'].values():
        f = PACKAGE/entry['path']
        if sha(f) != entry['sha256']:raise ValueError('Package hash mismatch')
        source_files.append(f)
    for row in protected+candidates:
        source_files.append(ROOT/row['path'])
    for f in (AI/'rag-data').glob('*'):
        if f.is_file():source_files.append(f)
    sys.path.insert(0,str(AI))
    from app.config import settings
    api_settings={k:getattr(settings,k) for k in ['max_upload_bytes','confidence_threshold',
        'confidence_margin_threshold','normalized_entropy_threshold','allowed_mime','inference_threads']}
    p = dict(registered_utc=utc(), name='application_evaluation_20261110', version=m['name'], classes=CLASSES,
        api_settings=api_settings,
        device=device, engine='FastAPI TestClient /predict with frozen package; no mock predictions',
        evaluation_type='retrospective leakage-screened historical holdouts, NOT a new blind independent clinical test',
        primary_dataset='historical_fixed_test', secondary_dataset='SCIN_case_holdout',
        data_admission='Source-defined prior label-cleaned test membership; byte/RGB/dHash<=3/source-case/reviewed-scene exclusions before any new model scoring. Raw 8-class training roots conservatively protect all known CNN/inner/head/gate/legacy OOD training inputs. dHash exclusions are conservative flags, not patient identity proof.',
        protected_images=len(protected), source_summary=summary,
        workflow='POST original bytes and original MIME to actual app /predict, PATIENT role. Keep original upload limit, quality/OOD rejection, preprocessing, 5 folds, routing, voting, score thresholds, Grad-CAM and RAG. Uncertain returned labels remain in metrics.',
        metrics='Report coverage; accuracy conditional on HTTP200; correct-return/all-input rate; fixed8 macroF1 with abstentions as a 9th predicted column; accepted-only F1; per-class P/R/F1/support/rejected; SkinCancer recall null when absent. Never report conditional accuracy without coverage. No pooled primary score across the two sources.',
        confidence_intervals='1000 deterministic seed42 percentile group bootstraps; SCIN case and dHash components are proxies, not verified independent patient IDs.',
        selection_policy='Freeze all images/code/package/settings before inference. Lock all predictions before metrics. No training, new weights, threshold changes, reclassification or favorable subset selection.',
        independent_test=False, clinical_label_review_performed=False, model_changed=False,
        limitations=['Both holdouts were inspected in historical research, so adaptive study exposure is not erased by deduplication.',
          'SCIN holdout has no SkinCancer and very few Lupus/Candidiasis examples; no full8 generalization claim.',
          'Clinical/dataset labels are not newly confirmed by project clinicians; patient independence is not fully established.',
          'OOD and quality rejections are API abstentions, not eight-class diagnoses; report them separately.',
          'No current claim about prospective patients, Vietnamese clinics, or clinical diagnostic accuracy.'],
        frozen_sha256={rel(f):sha(f) for f in sorted(set(source_files))})
    write(out/'protocol.json',p);write(out/'status.json',dict(state='registered',updated_utc=utc()))
    print(json.dumps(summary,indent=2),flush=True)


def run(out):
    p = read(out/'protocol.json');verify_frozen(p)
    if (out/'predictions_locked.json').exists():
        raise FileExistsError('Predictions already locked; use score or verify')
    if p['device']=='cpu':os.environ['CUDA_VISIBLE_DEVICES']='-1'
    os.environ['RESEARCH_MANIFEST_PATH']=str(PACKAGE/'manifest.json')
    os.environ['RAG_INDEX_PATH']=str(AI/'rag-data')
    sys.path.insert(0,str(AI))
    import torch
    import torchvision
    from fastapi.testclient import TestClient
    from app.main import app, settings
    for key,value in p.get('api_settings',{}).items():
        observed=getattr(settings,key)
        if (list(observed) if isinstance(observed,tuple) else observed) != value:raise ValueError('API setting changed: '+key)
    rows=read(out/'evaluation_manifest.json'); file=out/'predictions.jsonl';done=[]
    if file.exists():
        done=[json.loads(s) for s in file.read_text(encoding='utf-8').splitlines() if s]
        for expected,observed in zip(rows,done):
            if any(expected[k]!=observed[k] for k in ['path','sha256','label','dataset','group']):raise ValueError('Resume prefix differs')
        if len(done)>len(rows):raise ValueError('Extra predictions in resume file')
    with TestClient(app) as client, file.open('a',encoding='utf-8') as log:
        health=client.get('/health').json()
        if not health.get('modelReady') or health.get('modelVersion')!=p['version']:raise ValueError('Wrong serving model')
        write(out/'environment.json',dict(python=platform.python_version(),torch=torch.__version__,torchvision=torchvision.__version__,numpy=np.__version__,device=p['device'],health=health))
        for i,row in enumerate(rows[len(done):],len(done)):
            image=ROOT/row['path']
            if sha(image)!=row['sha256']:raise ValueError('Evaluation image changed')
            started=time.perf_counter();mime=mimetypes.guess_type(image.name)[0] or 'image/jpeg'
            response=client.post('/predict',headers={'X-User-Role':'PATIENT'},files={'image':(image.name,image.read_bytes(),mime)})
            if response.status_code not in [200,413,415,422]:
                write(out/'error.json',dict(index=i,status=response.status_code,detail=response.text[:500]));raise RuntimeError('Unexpected API failure; no score produced')
            payload=response.json();record={k:row[k] for k in ['path','sha256','label','dataset','group']}
            record.update(http_status=response.status_code,seconds=time.perf_counter()-started)
            if response.status_code==200:
                if payload['model_version']!=p['version'] or payload['score_type']!='fold_vote_fraction':raise ValueError('Runtime prediction identity changed')
                for key in ['disease','confidence','top3','uncertain','model_version','score_type','confidence_is_calibrated','decision_policy_applied','fold_decisions']:
                    record[key]=payload[key]
                record.update(gradcam_present=bool(payload['gradcam_image']),guidance_present=bool(payload.get('guidance')))
            else:record.update(disease=None,uncertain=None,detail=payload.get('detail',''))
            log.write(json.dumps(record,ensure_ascii=False)+'\n');log.flush();done.append(record)
            if (i+1)%25==0 or i+1==len(rows):
                write(out/'status.json',dict(state='predicting',completed=i+1,total=len(rows),updated_utc=utc()))
                print(f'API predictions {i+1}/{len(rows)}',flush=True)
    verify_frozen(p)
    write(out/'predictions_locked.json',dict(locked_utc=utc(),images=len(rows),predictions_sha256=sha(file),protocol_sha256=sha(out/'protocol.json')))


def score(out):
    p=read(out/'protocol.json');verify_frozen(p);lock=read(out/'predictions_locked.json')
    if sha(out/'predictions.jsonl')!=lock['predictions_sha256']:raise ValueError('Locked predictions changed')
    rows=[json.loads(x) for x in (out/'predictions.jsonl').read_text(encoding='utf-8').splitlines()]
    datasets={}
    for dataset in p['source_summary']:
        rr=[r for r in rows if r['dataset']==dataset]
        if rr:datasets[dataset]=dict(metrics=metrics(rr),bootstrap_95=bootstrap(rr))
    write(out/'results.json',dict(completed_utc=utc(),version=p['version'],evaluation_type=p['evaluation_type'],
        primary_dataset=p['primary_dataset'],datasets=datasets,independent_test=False,model_changed=False,
        protocol_sha256=sha(out/'protocol.json'),predictions_sha256=sha(out/'predictions.jsonl')))
    print(json.dumps({k:v['metrics'] for k,v in datasets.items()},indent=2),flush=True)


def verify(out):
    from sklearn.metrics import confusion_matrix, f1_score, accuracy_score
    p=read(out/'protocol.json');verify_frozen(p);results=read(out/'results.json');lock=read(out/'predictions_locked.json')
    assert lock['predictions_sha256']==sha(out/'predictions.jsonl')==results['predictions_sha256']
    rows=[json.loads(x) for x in (out/'predictions.jsonl').read_text(encoding='utf-8').splitlines()]
    expected=read(out/'evaluation_manifest.json');assert len(rows)==len(expected)==lock['images']
    for a,b in zip(rows,expected):
        assert all(a[k]==b[k] for k in ['path','sha256','label','dataset','group'])
        if a['http_status']==200:
            assert a['disease']==a['top3'][0]['label'] and a['gradcam_present']
            assert len(a['fold_decisions'])==5
            assert abs(a['confidence']-a['fold_decisions'].count(a['disease'])/5)<1e-6
    for dataset,result in results['datasets'].items():
        rr=[r for r in rows if r['dataset']==dataset];y=[CLASSES.index(r['label']) for r in rr]
        d=[CLASSES.index(r['disease']) if r['http_status']==200 else 8 for r in rr];m=result['metrics']
        cm=confusion_matrix(y,d,labels=list(range(9)))[:8,:]
        np.testing.assert_array_equal(cm,m['confusion_matrix_8x9'])
        assert abs(accuracy_score(y,d)-m['correct_return_rate'])<1e-12
        assert abs(f1_score(y,d,labels=list(range(8)),average='macro',zero_division=0)-m['macro_f1_8class_with_abstentions'])<1e-12
        accepted=[i for i,r in enumerate(rr) if r['http_status']==200]
        if accepted:
            assert abs(accuracy_score(np.array(y)[accepted],np.array(d)[accepted])-m['accuracy_on_returned'])<1e-12
    write(out/'verification.json',dict(status='PASS',checked_utc=utc(),images=len(rows),
        exact_manifest_alignment=True,sklearn_metrics_and_8x9_confusion_match=True,all_frozen_hashes_match=True,
        API_vote_scores_match=True,independent_test=False,results_sha256=sha(out/'results.json')))
    write(out/'status.json',dict(state='complete_verified_retrospective_application_evaluation',updated_utc=utc()))
    print('PASS: frozen serving API, audited inputs, abstention-aware metrics and sklearn verification')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','run','score','verify'])
    parser.add_argument('--output',type=Path,default=REPORT)
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    args=parser.parse_args();out=args.output.resolve()
    if args.phase=='prepare':prepare(out,args.device)
    else:globals()[args.phase](out)


if __name__=='__main__':main()
