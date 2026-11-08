"""255 training-only metadata review and representation readiness for the current three pools."""
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict,Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib,json
from PIL import Image

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;R=OUT.parent
SPLITS=R/'teacher_ept_two_pool_repeat_20261103/protocol.json';INVENTORY=R/'original_eight_weak_train_audit_20261021/image_inventory.json';LEGACY=INVENTORY.parent;LATEST=R/'teacher_six_cnn_two_stages_20261103'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();utc=lambda:datetime.now(timezone.utc).isoformat()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def lines(p,rows):Path(p).write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in rows),encoding='utf-8')
FOCUS=['Lupus','Psoriasis','Tinea','Eczema']


def pixel(row):
    f=ROOT/row['path'];assert sha(f)==row['sha256'],f
    with Image.open(f) as im:
        rgb=im.convert('RGB');w,h=rgb.size;digest=hashlib.sha256(f'{w}x{h}:RGB:'.encode()+rgb.tobytes()).hexdigest()
    assert (w,h,digest)==(row['width'],row['height'],row['pixel_sha256']),row['path']
    return dict(path=row['path'],sha256=row['sha256'],pixel_sha256=digest,width=w,height=h)


def clusters(rows,key,metadata):
    groups=defaultdict(list)
    for row in rows:
        value=metadata[row['path']].get(key) if key in ['source_case_id','pixel_sha256'] else row.get(key)
        if value:groups[value].append(row)
    return [dict(key=key,value=value,labels=sorted({v['label'] for v in members}),paths=sorted(v['path'] for v in members)) for value,members in sorted(groups.items()) if len({v['label'] for v in members})>1]


def main():
    assert not (OUT/'protocol.json').exists(),'Preserve255 audit registration'
    inputs=[SPLITS,INVENTORY,LEGACY/'protocol.json',LEGACY/'verification.json',Path(__file__),ROOT/'tmp/review_weak_data_readiness_20261103.py',ROOT/'tmp/finish_weak_data_readiness_20261103.py',LATEST/'completion.json',LATEST/'status.json']
    assert read(LEGACY/'verification.json')['status']=='PASS' and read(LATEST/'completion.json')['status']=='complete_verified_six_cnn_two_stages_254' and read(LATEST/'status.json')['pid'] is None
    sp=read(SPLITS);metadata={v['path']:v for v in read(INVENTORY)};jobs=sp['jobs'];rows={}
    for name,j in jobs.items():
        for row in j['fit_rows']+j['rows']:
            m=metadata[row['path']]
            for key in ['path','label','sha256','source','group']:assert row[key]==m[key],(name,key,row['path'])
            if row['path'] in rows:assert rows[row['path']]==m
            rows[row['path']]=m
    p=dict(registered_utc=utc(),scope='Current three historical TRAIN pools only; metadata/data-readiness audit, no training or diagnostic label correction.',sources_sha256={f.relative_to(ROOT).as_posix():sha(f) for f in inputs},
        design='Reuse frozen5937legacy metadata, STRICTbind path/label/SHA/source/group tocurrent250roles. RecheckdecodedRGB andbytes ofcurrent4031unique images. Per-poolflags generatedONLYfromOWNfit rows. Query usedONLYforrole-separation, neverforreviewpriority. No predictions/errors/loss read.',
        review_rules='FocusLupus/Psoriasis/Tinea/Eczema. Flag multipleequal-topsourceannotations, or own-fit SHA/pixel/group/knowncase containingmultiple datasetlabels. Co-scene/case multi-label is a review signal, not proof wronglabel. Reuseweightbelow075 flag onlyfor descriptivecounts, not clinicalconfidence/exclusion. No sourceannotations inoriginal_train => unknown, notzeroquality.',
        endpoint='Reportperpoolfit coverage byfocusdisease/source, image/group/knowncase counts, metadata ambiguity, clinicalconfirmation unknown. ExportSEPARATE ownFITonly reviewqueue withreviewer/confirmed_label/evidence null. MissingSCINcells explicitlyzero; nojudgment ofadequacynumericthreshold. No labels changed, filesdeleted, modelsselected orscoresupdated.',
        limitations=['KnowncaseIDs/scenehash groups are not always verifiedpatientIDs.','Legacy source annotations are retrospective differential labels, not confirmedclinicaldiagnoses.','Trainingsets overlap:8062memberships are4031uniqueimages, notnewimages.','Nonewexpert/clinicalreview or independenttest; modelqualitymetrics notcomputed.'],selected=None,labels_changed=0,images_removed=0,new_CNN_fits=0,new_metrics_computed=False,global_5937_score_changed=False,serving_changed=False,research_registry_changed=False)
    write(OUT/'protocol.json',p)
    with ThreadPoolExecutor(max_workers=4) as executor:inventory=list(executor.map(pixel,[rows[k] for k in sorted(rows)]))
    write(OUT/'image_integrity.json',inventory);results={};queuepaths=set();memberships=0
    for name,j in jobs.items():
        fit,query=j['fit_rows'],j['rows'];memberships+=len(fit);coverage=[];conflicts=[];separation={}
        for key in ['sha256','pixel_sha256','group','source_case_id']:
            a={metadata[v['path']].get(key) for v in fit}-{None};b={metadata[v['path']].get(key) for v in query}-{None};separation[key]=sorted(a&b)
        for key in ['sha256','pixel_sha256','group','source_case_id']:conflicts+=clusters(fit,key,metadata)
        flags=defaultdict(set)
        for row in fit:
            if row['label'] in FOCUS and len(metadata[row['path']].get('tied_top_labels') or [])>1:flags[row['path']].add('equal_top_differential_annotations')
        for cluster in conflicts:
            for path in cluster['paths']:
                if metadata[path]['label'] in FOCUS:flags[path].add('own_fit_'+cluster['key']+'_multiple_dataset_labels')
        queue=[]
        for row in sorted(fit,key=lambda v:(v['label'],v['source'],v['path'])):
            path=row['path'];m=metadata[path]
            if path in flags:
                queue.append(dict(pool=name,role='fit_only',path=path,label=row['label'],sha256=row['sha256'],source=row['source'],group=row['group'],source_case_id=m['source_case_id'],review_reasons=sorted(flags[path]),source_label_status=m['source_label_status'],weighted_source_labels=m.get('weighted_source_labels'),tied_top_labels=m.get('tied_top_labels'),diagnostic_error_confirmed=False,reviewer=None,confirmed_label=None,review_evidence=None));queuepaths.add(path)
        lines(OUT/(name+'_fit_review.jsonl'),queue)
        for label in FOCUS:
            for source in ['original_train','SCIN']:
                selected=[metadata[v['path']] for v in fit if v['label']==label and v['source']==source];coverage.append(dict(disease=label,source=source,images=len(selected),proxy_groups=len({v['group'] for v in selected}),known_source_cases=len({v['source_case_id'] for v in selected if v['source_case_id']}),confirmed_patient_ids=sum(bool(v['confirmed_patient_id_available']) for v in selected),equal_top_annotation_images=sum(len(v.get('tied_top_labels') or [])>1 for v in selected),annotation_weight_below075_images=sum('top_annotation_weight_below075' in v['flags'] for v in selected),source_diagnostic_evidence_unknown_images=sum(v['source_label_status']=='folder_label_original_diagnostic_evidence_unavailable' for v in selected)))
        results[name]=dict(fit_images=len(fit),query_images=len(query),coverage=coverage,fit_query_overlap=separation,own_fit_multi_label_clusters=conflicts,fit_review_images=len(queue),fit_review_case_ids=len({v['source_case_id'] for v in queue if v['source_case_id']}),review_reason_counts=dict(Counter(reason for v in queue for reason in v['review_reasons'])))
    write(OUT/'results.json',dict(completed_utc=utc(),protocol_sha256=sha(OUT/'protocol.json'),jobs=results,unique_current_images=len(rows),fit_memberships=memberships,unique_review_images=len(queuepaths),labels_changed=0,images_removed=0,new_CNN_fits=0,new_metrics_computed=False,selected=None,serving_changed=False,global_5937_score_changed=False))
    for name,h in p['sources_sha256'].items():assert sha(ROOT/name)==h,name
    print(dict(unique_images=len(rows),fit_memberships=memberships,unique_review_images=len(queuepaths),per_pool={name:j['fit_review_images'] for name,j in results.items()}),flush=True)


if __name__=='__main__':main()
