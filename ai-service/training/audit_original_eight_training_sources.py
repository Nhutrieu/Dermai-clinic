"""Train-only source/label/exposure audit and frozen inference, no model fitting.

Training metrics below describe fit to seen labels. They are not validation/test
accuracy and do not verify diagnoses. Never relabel an image using a prediction.
"""
import argparse
import ast
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from common import CLASSES, ImageSampleDataset, build_model, evaluation_transform, save_json, sha256_file
from evaluate_scene_grouped_oof_classwise_fusion import classwise_blend
from evaluate_scene_grouped_oof_ensemble import score
import pilot_original_eight_supplement_adaptation as prior
import pilot_original_eight_ensemble_teacher as teacher

ROOT = prior.ROOT
OUT = ROOT / 'ai-service/reports/original_eight_training_source_audit_20261013'
SCIN_LABELS = ROOT / 'ai-service/data-sources/scin/scin_labels.csv'
ALIASES = dict(Acne={'Acne'}, Candidiasis={'Candida', 'Candida intertrigo'}, Eczema={'Eczema'},
               Lupus={'Cutaneous lupus'}, Psoriasis={'Psoriasis'}, Tinea={'Tinea'}, Warts={'Verruca vulgaris'})
METHODS = ('efficientnet_b0', 'convnext_tiny', 'baseline_resnet', 'supplement_resnet', 'distill_resnet', 'old_classwise')


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def entries(p): return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()]


def register():
    assert not (OUT / 'protocol.json').exists(), 'Preserve existing audit'
    state = read(ROOT / 'ai-service/reports/active_research_track.json')
    assert state['active_track'] == 'original_eight'
    p = read(teacher.OUT / 'protocol.json')
    assert read(teacher.OUT / 'verification.json')['status'] == 'PASS'
    aux = entries(prior.SUP / 'training_candidates.jsonl')
    assert [r['path'] for r in aux] == [r['path'] for r in p['supplement']]
    with SCIN_LABELS.open(encoding='utf-8-sig', newline='') as f:
        scin = {r['case_id']: r for r in csv.DictReader(f)}
    rows = []
    for r in p['train']:
        is_scin = '/scin-v1/' in r['path']
        item = dict(**r, source='SCIN' if is_scin else 'Original-local', role='original_train',
                    source_case_id=None, patient_id_confirmed=False,
                    label_status='folder_label_source_subtype_unavailable', source_label=r['label'])
        if is_scin:
            cid = Path(r['path']).parts[4]; s = scin[cid]
            weights = ast.literal_eval(s['weighted_skin_condition_label'])
            assert isinstance(weights, dict) and weights
            top = max(weights, key=weights.get); top_weight = float(weights[top])
            ties = sum(abs(float(w) - top_weight) < 1e-12 for w in weights.values())
            item.update(source_case_id='SCIN::' + cid, source_label=top,
                        label_status='retrospective_differential_label',
                        differential_top_weight=top_weight, top_label_tie=ties > 1,
                        published_label_map_matches=top in ALIASES.get(r['label'], set()))
        rows.append(item)
    for r, a in zip(p['supplement'], aux):
        assert r['label'] == a['label'] and r['sha256'] == a['sha256']
        rows.append(dict(**r, role='supplement_train', source_case_id=a['source_case_id'],
                         patient_id_confirmed=a['subject_id_available'], label_status=a['source_label_status'],
                         source_label=a['source_label'], diagnostic_confidence=a.get('diagnostic_confidence'),
                         pixel_sha256=a['pixel_sha256']))
    assert len(rows) == 4850 and len(set(r['path'] for r in rows)) == 4850
    protected = [r for rr in p['splits'].values() for r in rr]
    assert {r['path'] for r in rows}.isdisjoint(r['path'] for r in protected)
    assert {r['sha256'] for r in rows}.isdisjoint(r['sha256'] for r in protected)
    assert {r['group'] for r in p['train']}.isdisjoint(r['group'] for r in protected)
    dc_cases = {r['source_case_id'] for r in rows if r['source'] == 'DermaCon-IN-v1'}
    assert dc_cases.isdisjoint(r['group'] for r in protected)
    for i, r in enumerate(rows):
        assert sha256_file(ROOT / r['path']) == r['sha256']
        with Image.open(ROOT / r['path']) as im:
            im.load(); width, height = im.size
            r.update(width=width, height=height, minimum_side=min(width, height),
                     exif_orientation=int(im.getexif().get(274, 1)), mode=im.mode)
        if (i + 1) % 1000 == 0: print(json.dumps(dict(audited_images=i+1)), flush=True)
    members = [dict(name=m['architecture'], architecture=m['architecture'], path=m['path'], sha256=m['sha256']) for m in p['teachers']]
    members.append(dict(name='baseline_resnet', architecture='resnet50', path=prior.INITIAL.relative_to(ROOT).as_posix(), sha256=sha256_file(prior.INITIAL)))
    for branch, name in [('control', 'supplement_resnet'), ('distill', 'distill_resnet')]:
        cp = teacher.MODELS / branch / 'final_model.pth'
        report = read(teacher.MODELS / branch / 'training_report.json')
        assert sha256_file(cp) == report['checkpoint_sha256']
        members.append(dict(name=name, architecture='resnet50', path=cp.relative_to(ROOT).as_posix(), sha256=sha256_file(cp)))
    files = [teacher.OUT/'protocol.json', teacher.OUT/'verification.json', prior.SUP/'training_candidates.jsonl',
             prior.SUP/'verification.json', SCIN_LABELS, ROOT/'ai-service/scripts/prepare_scin.py',
             ROOT/'ai-service/training/prepare_dermacon_holdout.py',
             ROOT/state['benchmark']['report_path'], ROOT/state['serving_checkpoint']]
    for branch in ('control', 'distill'):
        files += [teacher.MODELS/branch/'history.json', teacher.MODELS/branch/'training_report.json']
    protocol = dict(classes=CLASSES, rows=rows, members=members,
        reference_weights=p['teacher_classwise_weights'],
        source_sha256={x.relative_to(ROOT).as_posix():sha256_file(x) for x in files},
        code_sha256={n:sha256_file(ROOT/'ai-service/training'/n) for n in
          ('audit_original_eight_training_sources.py', 'verify_original_eight_training_sources.py',
           'common.py', 'train_v2.py', 'pilot_original_eight_supplement_adaptation.py',
           'evaluate_scene_grouped_oof_classwise_fusion.py', 'evaluate_scene_grouped_oof_ensemble.py')},
        exposure='Reconstruct fixed supplemented90/10sampler4043replacement draws for epochs1..3, seed42+epoch. Unique seen images/cases and repeat draws separately. No changes to sampler or training.',
        inference='Five frozen fold0checkpoints, eval+no_grad, FP32, existing evaluation_transform; raw softmax matches research parent/student convention. Group by train source only. No validation/test probabilities read.',
        limits=['All4850rows are original-fold0train or audited auxiliary train; apparent fit is not generalization.',
                'Case IDs do not prove SCIN person IDs; original and atlas patient IDs missing.',
                'Source labels/subtypes differ and original-local subtype is unavailable, so semantic equivalence cannot be fully established.',
                'Prediction disagreements are review candidates, not proven errors or automatic relabel instructions.',
                'No score update for5937OOF or serving, no new model training.'])
    save_json(OUT/'protocol.json', protocol)
    return protocol


def exposure(protocol):
    draws = []; counts = Counter(); by_epoch = []
    for ep in range(1, 4):
        ids = prior.draws('supplement', ep); counts.update(ids); draws.extend(ids)
        by_epoch.append(dict(epoch=ep, draws=len(ids), counts={s:{c:sum(protocol['rows'][i]['source']==s and protocol['rows'][i]['label']==c for i in ids) for c in CLASSES} for s in sorted({r['source'] for r in protocol['rows']})}))
    return counts, by_epoch


def metadata_report(protocol):
    rows = protocol['rows']; counts, by_epoch = exposure(protocol); cells = []
    for source in sorted({r['source'] for r in rows}):
        for label in CLASSES:
            ids = [i for i,r in enumerate(rows) if r['source']==source and r['label']==label]
            if not ids: continue
            rr = [rows[i] for i in ids]; seen = [i for i in ids if counts[i]>0]
            cells.append(dict(source=source, label=label, pool_images=len(ids),
                image_groups=len({r['group'] for r in rr}), known_cases=len({r['source_case_id'] for r in rr if r['source_case_id']}),
                images_without_confirmed_patient_id=sum(not r['patient_id_confirmed'] for r in rr),
                source_labels=dict(Counter(r['source_label'] for r in rr)),
                sampled_draws=sum(counts[i] for i in ids), unique_images_seen=len(seen),
                unique_groups_seen=len({rows[i]['group'] for i in seen}),
                known_cases_seen=len({rows[i]['source_case_id'] for i in seen if rows[i]['source_case_id']}),
                minimum_side_quantiles=np.quantile([r['minimum_side'] for r in rr],[0,.25,.5,.75,1]).tolist(),
                images_min_side_below128=sum(r['minimum_side']<128 for r in rr),
                nondefault_exif=sum(r['exif_orientation'] not in (0,1) for r in rr),
                scin_top_ties=sum(r.get('top_label_tie',False) for r in rr),
                scin_top_weight_below075=sum(r.get('differential_top_weight',1)<.75 for r in rr),
                label_mapping_mismatches=sum(r.get('published_label_map_matches',True) is False for r in rr)))
    save_json(OUT/'metadata.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),
        pool_images=len(rows), total_draws=sum(counts.values()), unique_seen=len(counts),
        cells=cells, by_epoch=by_epoch,
        observation='Oversampling repeats known photos and cannot create new labelled cases; SCIN weights are differential annotation weights, not calibrated diagnostic probabilities.'))


def infer(member, protocol):
    path = OUT/(member['name']+'.npz')
    if path.exists():
        with np.load(path) as z:
            assert z['protocol_sha256'].item()==sha256_file(OUT/'protocol.json')
            assert z['paths'].tolist()==[r['path'] for r in protocol['rows']]
            return z['probabilities'].astype(float)
    assert sha256_file(ROOT/member['path'])==member['sha256']
    cp = torch.load(ROOT/member['path'],map_location='cpu',weights_only=False)
    assert cp['classes']==CLASSES and cp['architecture']==member['architecture']
    model=build_model(member['architecture'],8,pretrained=False)
    model.load_state_dict(cp['model_state_dict']); del cp
    model.cuda().eval().requires_grad_(False)
    loader=prior.trainer.make_loader(ImageSampleDataset(prior.samples(protocol['rows']),evaluation_transform()),32,False,2,True)
    blocks=[]
    with torch.inference_mode():
        for x,_ in loader: blocks.append(model(x.cuda(non_blocking=True)).softmax(1).cpu().numpy())
    pp=np.concatenate(blocks).astype(float)
    np.savez_compressed(path,paths=[r['path'] for r in protocol['rows']],probabilities=pp,
                        protocol_sha256=sha256_file(OUT/'protocol.json'))
    del model,loader; torch.cuda.empty_cache()
    print(json.dumps(dict(inferred=member['name'],train_images=len(pp))),flush=True)
    return pp


def run(protocol):
    assert not (OUT/'results.json').exists(),'Preserve completed audit'
    torch.set_num_threads(4); assert torch.cuda.is_available()
    metadata_report(protocol)
    pp={m['name']:infer(m,protocol) for m in protocol['members']}
    pp['old_classwise']=classwise_blend(pp['efficientnet_b0'],pp['convnext_tiny'],np.asarray(protocol['reference_weights']))
    rows=protocol['rows']; y=np.asarray([CLASSES.index(r['label']) for r in rows]); result={}; review=[]
    for source in sorted({r['source'] for r in rows}):
        mask=np.asarray([r['source']==source for r in rows]); result[source]={}
        for name,p in pp.items():
            m=score(p[mask],y[mask]); present=sum(m['per_class'][c]['support']>0 for c in CLASSES)
            m['macro_f1_present_classes']=m['macro_f1']*8/present
            m['false_positives']={c:int(((p.argmax(1)==k)&(y!=k)&mask).sum()) for k,c in enumerate(CLASSES)}
            result[source][name]=m
        for c in ('Candidiasis','Lupus','Psoriasis','SkinCancer','Tinea'):
            k=CLASSES.index(c)
            ids=[i for i,r in enumerate(rows) if mask[i] and y[i]==k and pp['supplement_resnet'][i].argmax()!=k]
            ids.sort(key=lambda i:(-float(pp['supplement_resnet'][i].max()),rows[i]['path']))
            for i in ids[:10]:
                review.append(dict(**rows[i],reason='supplemented_train_prediction_disagreement_not_confirmed_label_error',
                    predictions={n:dict(label=CLASSES[int(p[i].argmax())],confidence=float(p[i].max()),true_label_probability=float(p[i,k])) for n,p in pp.items()}))
    save_json(OUT/'review_candidates.json',review)
    save_json(OUT/'results.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),
        train_only=True, no_fitting=True, results=result,
        scope='Descriptive fit on seen train labels; not test accuracy, clinical diagnosis verification, or a selection experiment.'))
    print(json.dumps(dict(complete=True,source_metrics={s:{n:dict(accuracy=m['accuracy'],macro_f1_present=m['macro_f1_present_classes']) for n,m in rr.items()} for s,rr in result.items()})),flush=True)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--prepare-only',action='store_true'); parser.add_argument('--resume',action='store_true'); args=parser.parse_args()
    p=read(OUT/'protocol.json') if args.resume else register()
    for name,h in p['code_sha256'].items(): assert sha256_file(ROOT/'ai-service/training'/name)==h
    if args.prepare_only: metadata_report(p); print('Registered train-only audit.'); return
    run(p)


if __name__=='__main__': main()
