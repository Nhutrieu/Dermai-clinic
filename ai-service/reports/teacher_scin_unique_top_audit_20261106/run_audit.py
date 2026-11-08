"""302: fit-only reconciliation of SCIN source annotations and matched curation manifests."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
import ast,csv,hashlib,json,math

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;R=OUT.parent
FOCUS={'Lupus','Psoriasis','Tinea','Eczema'}
CLASSES=['Acne','Candidiasis','Eczema','Lupus','Psoriasis','SkinCancer','Tinea','Warts']
ALIASES={'Acne':'Acne','Candida':'Candidiasis','Candida intertrigo':'Candidiasis','Eczema':'Eczema','Cutaneous lupus':'Lupus','Psoriasis':'Psoriasis','Tinea':'Tinea','Verruca vulgaris':'Warts'}
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def parse(raw):
    node=ast.parse(raw,mode='eval').body
    if not isinstance(node,ast.Dict):raise ValueError('Expected weighted-label dictionary')
    names=[ast.literal_eval(k) for k in node.keys]
    if len(set(names))!=len(names):raise ValueError('Duplicate source label')
    d=ast.literal_eval(node)
    if not d:raise ValueError('No source labels')
    if any(not isinstance(k,str) or not k or isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 or v>1 for k,v in d.items()):raise ValueError('Invalid source weight')
    return {k:float(v) for k,v in d.items()}

def decision(raw,minimum=.5):
    d=parse(raw);top=max(d.values());names=sorted(k for k,v in d.items() if v==top)
    target=ALIASES.get(names[0]) if len(names)==1 else None
    return dict(weighted_labels=d,top_weight=top,top_labels=names,unique_top=len(names)==1,
                strict_target=target if top>=minimum and len(names)==1 else None,
                reason='tied_source_top' if len(names)>1 else 'below_existing_minimum' if top<minimum else 'outside_existing_narrow_map' if target is None else 'unique_source_top_not_clinically_confirmed',
                legacy_first_target=ALIASES.get(max(d,key=d.get)) if top>=minimum else None,
                possible_legacy_targets=sorted({ALIASES.get(k,'OUTSIDE_EIGHT') for k in names}) if top>=minimum else [],
                clinical_confirmation=False)

def units(rows,labels):
    cases=defaultdict(list)
    for row in rows:
        if row['source']=='SCIN':cases[row['path'].split('/')[-2]].append(row)
    result=[]
    for case,rr in sorted(cases.items()):
        assert len({v['label'] for v in rr})==1
        dec=decision(labels[case]['weighted_skin_condition_label'])
        assert dec['legacy_first_target']==rr[0]['label'],case
        result.append(dict(case_id=case,label=rr[0]['label'],images=len(rr),paths=sorted(v['path'] for v in rr),decision=dec))
    return result

def masks(rows,case_units,seed=42):
    # Only the four preregistered target/confounder classes are affected.
    rejected=[u for u in case_units if u['label'] in FOCUS and not u['decision']['unique_top']]
    candidates=defaultdict(list)
    for u in case_units:
        if u['label'] in FOCUS and u['decision']['unique_top']:candidates[(u['label'],u['images'])].append(u)
    requested=Counter((u['label'],u['images']) for u in rejected)
    matched=[]
    for key,n in sorted(requested.items()):
        available=sorted(candidates[key],key=lambda u:hashlib.sha256(f'{seed}:302:{u["case_id"]}'.encode()).hexdigest())
        if len(available)<n:raise ValueError(f'Cannot match case-size/source/class stratum {key}: {len(available)} < {n}')
        matched.extend(available[:n])
    reject_paths={p for u in rejected for p in u['paths']};random_paths={p for u in matched for p in u['paths']}
    assert not reject_paths&random_paths
    byarm={}
    for arm,excluded in [('full',set()),('unique_top',reject_paths),('matched_control',random_paths)]:
        before=Counter(v['label'] for v in rows);after=Counter(v['label'] for v in rows if v['path'] not in excluded)
        assert all(after[c]>0 for c in CLASSES)
        # Keep total effective loss weight for each dataset label unchanged.
        weights=[0. if v['path'] in excluded else before[v['label']]/after[v['label']] for v in rows]
        for c in CLASSES:assert abs(sum(w for w,v in zip(weights,rows) if v['label']==c)-before[c])<1e-8
        byarm[arm]=dict(excluded_paths=sorted(excluded),retained_images=len(rows)-len(excluded),retained_by_class=dict(after),loss_weights=weights)
    assert byarm['unique_top']['retained_by_class']==byarm['matched_control']['retained_by_class']
    return dict(arms=byarm,excluded_source_cases={a:[{k:u[k] for k in ('case_id','label','images','paths')} for u in uu] for a,uu in [('unique_top',rejected),('matched_control',matched)]},
                matched_case_size_counts={f'{c}/{size}':n for (c,size),n in sorted(requested.items())})

def main():
    assert not(OUT/'protocol.json').exists(),'Preserve audit registration'
    files=[R/'teacher_ept_two_pool_repeat_20261103/protocol.json',R/'original_eight_weak_train_audit_20261021/image_inventory.json',R/'teacher_weak_data_readiness_20261103/results.json',ROOT/'ai-service/data-sources/scin/scin_labels.csv',ROOT/'ai-service/data-sources/scin/scin_cases.csv',ROOT/'ai-service/scripts/prepare_scin.py',Path(__file__),ROOT/'ai-service/tests/test_scin_unique_top_audit.py']
    frozen={f.relative_to(ROOT).as_posix():sha(f) for f in files}
    for rel in ['ai-service/models/best_model.pth','ai-service/app/config.py','ai-service/reports/active_research_track.json']:frozen[rel]=sha(ROOT/rel)
    p=dict(registered_utc=utc(),sources_sha256=frozen,scope='Own-FIT SCIN metadata only in three frozen historical TRAIN pools. Query rows used only for overlap prevention. No model scores or loss read.',
           rule='Keep original narrow label map and minimum .5. Detect exact ties in raw weighted source labels independent of dictionary order; do not expand medical aliases or assign a new label. Probe masks only SCIN tied-top cases for Lupus/Psoriasis/Tinea/Eczema; all images of a known source case together.',
           control='Fixed SHA-rank seed42; remove different unique-top SCIN cases matching class AND number of images per case exactly. All eight class total loss weights preserved. If exact matching impossible, do not train.',
           limitations=['Unique top is a metadata property, not confirmed diagnosis or expert review.','Tied diagnoses can be clinically related; no alias expansion without source support.','Old folder labels lack original diagnostic evidence.','No new images, labels, patients or independent test. Existing queries are repeatedly used development sets.'],
           images_added=0,labels_changed=0,images_deleted=0,serving_changed=False,global_5937_score_changed=False)
    write(OUT/'protocol.json',p)
    sp=read(files[0]);inventory={v['path']:v for v in read(files[1])}
    with files[3].open(encoding='utf-8-sig',newline='') as f:label_rows=list(csv.DictReader(f))
    assert len({v['case_id'] for v in label_rows})==len(label_rows)
    labels={v['case_id']:v for v in label_rows}
    with files[4].open(encoding='utf-8-sig',newline='') as f:case_rows=list(csv.DictReader(f))
    cases={v['case_id']:v for v in case_rows};outputs={};unique=set();seen_images={};fit_memberships=0
    for name,j in sp['jobs'].items():
        fit,query=j['fit_rows'],j['rows'];fit_memberships+=len(fit)
        overlap={}
        for key in ['path','sha256','group']:
            a={v[key] for v in fit};b={v[key] for v in query};overlap[key]=len(a&b);assert not a&b
        fitcase={v['path'].split('/')[-2] for v in fit if v['source']=='SCIN'}
        forbidden=[v for role,rr in j['roles'].items() if role!='train' for v in rr]+query
        forbidcase={v['path'].split('/')[-2] for v in forbidden if v['source']=='SCIN'}
        overlap['case_id']=len(fitcase&forbidcase);assert not fitcase&forbidcase
        cc=units(fit,labels);ms=masks(fit,cc);details=[]
        for u in cc:
            for path in u['paths']:
                row=next(v for v in fit if v['path']==path);m=inventory[path]
                for key in ('label','sha256','source','group'):assert m[key]==row[key]
                assert u['decision']['weighted_labels']==m['weighted_source_labels']
                assert Path(path).name in [Path(cases[u['case_id']].get(f'image_{i}_path','')).name for i in (1,2,3)]
                if path not in seen_images:assert sha(ROOT/path)==row['sha256'];seen_images[path]=row['sha256']
                unique.add(path)
            details.append(dict(**u,reviewer=None,confirmed_label=None,review_evidence=None))
        write(OUT/(name+'_source_cases.json'),details)
        write(OUT/(name+'_probe_manifest.json'),dict(pool=name,fit_paths=[v['path'] for v in fit],fit_sha256=[v['sha256'] for v in fit],**ms))
        tied=[u for u in cc if u['label'] in FOCUS and not u['decision']['unique_top']]
        counts={c:dict(cases=sum(u['label']==c for u in tied),images=sum(u['images'] for u in tied if u['label']==c)) for c in sorted(FOCUS)}
        outputs[name]=dict(fit_images=len(fit),query_images=len(query),scin_fit_images=sum(u['images'] for u in cc),scin_source_cases=len(cc),tied_target_cases=len(tied),tied_target_images=sum(u['images'] for u in tied),tied_by_class=counts,
             order_sensitive_target_cases=sum(len(u['decision']['possible_legacy_targets'])>1 for u in tied),overlaps=overlap,exact_matched_control=True,retained_images=ms['arms']['unique_top']['retained_images'],
             lupus_scin_retained=sum(u['images'] for u in cc if u['label']=='Lupus' and u['decision']['unique_top']))
    write(OUT/'results.json',dict(completed_utc=utc(),protocol_sha256=sha(OUT/'protocol.json'),pools=outputs,unique_scin_fit_images_checked=len(unique),all_4031_image_integrity_audit_reused=True,fit_memberships=fit_memberships,new_clinical_reviews=0,new_images=0,labels_changed=0,CNN_fits=0,selected=None))
    for rel,h in frozen.items():assert sha(ROOT/rel)==h,rel
    print(json.dumps(outputs,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
