"""Descriptive audit of locked OOF errors; no tuning, relabelling or training."""
from __future__ import annotations

import html
import json
from collections import Counter,defaultdict
from pathlib import Path
from urllib.parse import quote

import numpy as np

import evaluate_original_eight_cancer_locked_fusion as fusion

ROOT=fusion.ROOT
NAME='original_eight_error_source_audit_20261021'
OUT=ROOT/'ai-service/reports'/NAME
INVENTORY=ROOT/'ai-service/reports/original_eight_weak_train_audit_20261021/image_inventory.json'
VERIFIER=ROOT/'ai-service/reports/original_eight_psoriasis_verifier_fold0_seed42_20261021'
FOCUS=['Lupus','Psoriasis','Tinea']
ALIASES={'Acne':['Acne'],'Candidiasis':['Candida','Candida intertrigo'],'Eczema':['Eczema'],
         'Lupus':['Cutaneous lupus'],'Psoriasis':['Psoriasis'],'Tinea':['Tinea'],'Warts':['Verruca vulgaris']}


def independent_score(rows,field):
    matrix=np.zeros((8,8),dtype=np.int64)
    for row in rows:matrix[fusion.CLASSES.index(row['label']),row['predictions'][field]]+=1
    tp=matrix.diagonal();p=np.divide(tp,matrix.sum(0),out=np.zeros(8),where=matrix.sum(0)!=0)
    r=np.divide(tp,matrix.sum(1),out=np.zeros(8),where=matrix.sum(1)!=0)
    f=np.divide(2*p*r,p+r,out=np.zeros(8),where=p+r!=0)
    return dict(images=len(rows),correct=int(tp.sum()),accuracy=float(tp.sum()/len(rows)),macro_f1=float(f.mean()),confusion_matrix=matrix.tolist())


def cell(rows,inventory):
    correct=[row['predictions']['validation_selected']==fusion.CLASSES.index(row['label']) for row in rows]
    cases=defaultdict(list)
    for row,value in zip(rows,correct):
        meta=inventory[row['path']]
        cases[meta['source_case_id'] or 'unknown-case::'+row['path']].append(value)
    predictions=Counter(fusion.CLASSES[row['predictions']['validation_selected']] for row in rows)
    return dict(images=len(rows),correct=sum(correct),errors=len(rows)-sum(correct),
        recall=float(np.mean(correct)) if rows else None,predicted_labels=dict(sorted(predictions.items())),
        scene_groups=len({row['group'] for row in rows}),
        known_source_cases=len({inventory[row['path']]['source_case_id'] for row in rows if inventory[row['path']]['source_case_id']}),
        equal_known_case_mean_correctness=float(np.mean([np.mean(values) for values in cases.values()])) if rows and all(inventory[row['path']]['source_case_id'] for row in rows) else None)


def build_review_packet(inventory,roles):
    # Queue solely from source metadata, NOT selected/ranked using OOF errors.
    rows=[]
    for path,meta in sorted(inventory.items()):
        if meta['label'] not in FOCUS or len(meta.get('tied_top_labels',[]))<2:continue
        assert fusion.sha(ROOT/path)==meta['sha256']
        row={key:meta.get(key) for key in ['path','label','sha256','group','source','source_case_id',
             'weighted_source_labels','tied_top_labels','source_label_status','confirmed_patient_id_available']}
        row.update(role_by_fold={str(fold):next(role for role,paths in values.items() if path in paths) for fold,values in enumerate(roles)},
            reason='Published differential has multiple equal top labels; not proof of wrong diagnosis',
            confirmed_label=None,reviewer=None,review_evidence=None,diagnostic_error_confirmed=False)
        rows.append(row)
    assert len(rows)==32
    (OUT/'metadata_review_queue.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')
    cards=[]
    for index,row in enumerate(rows,1):
        role=row['role_by_fold']['0'];train=role=='train'
        image_url='../../../'+quote(row['path'],safe='/')
        labels=html.escape(json.dumps(row['weighted_source_labels'],ensure_ascii=False))
        cards.append(f'''<article data-label="{row['label']}" data-role="{role}">
<h2>{index}. {row['label']}</h2><p class="badge">Fold 0: {html.escape(role)}</p>
<a href="{image_url}" target="_blank" rel="noopener"><img loading="lazy" src="{image_url}" alt="Ảnh có nhãn nguồn {row['label']}; chưa xác nhận chẩn đoán"></a>
<p><b>Nhãn nguồn và trọng số:</b> {labels}</p><p><b>Mã ca:</b> {html.escape(row['source_case_id'])}</p>
<p class="path">{html.escape(row['path'])}</p><p>{'Có thể rà cho train fold 0.' if train else 'Không đưa ảnh này vào train fold 0.'}</p>
<label>Ghi chú rà soát <textarea aria-label="Ghi chú ảnh {index}"></textarea></label>
</article>''')
    page='''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hồ sơ rà nhãn tám bệnh</title><style>body{font:16px/1.5 system-ui;margin:24px;background:#f6f7fb;color:#152035}main{max-width:1300px;margin:auto}h1{line-height:1.2}.notice{padding:16px;background:#fff0ce;border-left:5px solid #bd7900}.controls{position:sticky;top:0;background:#fff;padding:12px;display:flex;gap:16px;flex-wrap:wrap;border:1px solid #ddd}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px;margin-top:18px}article{background:white;padding:16px;border:1px solid #ddd;border-radius:8px}article img{width:100%;height:290px;object-fit:contain;background:#eef1f6}h2{font-size:19px;margin:0}.badge{font-weight:bold}.path{font-size:12px;overflow-wrap:anywhere}textarea{display:block;width:100%;box-sizing:border-box;min-height:75px}select,button{font:inherit}article[hidden]{display:none}small{display:block}</style>
<main><h1>32 ảnh cần rà nhãn nguồn</h1><p>Danh sách chọn bằng nhãn đồng hạng trong metadata, không chọn bằng lỗi AI. Mặc định chỉ hiển thị ảnh train fold 0.</p>
<div class="notice"><b>Chưa có kết luận bác sĩ.</b> Trọng số nguồn không phải xác suất chẩn đoán. Không tự đổi/xóa nhãn vì AI đoán khác. Ảnh inner/outer được giữ riêng để biết vai trò; không chuyển sang train. Mã ca không phải mã bệnh nhân đã xác minh.</div>
<p>Ảnh được đọc trực tiếp từ thư mục dự án, không tải lên mạng. Ghi chú chỉ lưu khi bấm xuất; tải lại trang sẽ mất ghi chú chưa xuất.</p>
<div class="controls"><label>Bệnh <select id="label"><option value="all">Tất cả</option><option>Psoriasis</option><option>Tinea</option></select></label><label>Vai trò fold 0 <select id="role"><option value="train">Train</option><option value="inner_validation">Inner validation</option><option value="outer_holdout">Outer holdout</option><option value="all">Tất cả vai trò</option></select></label><span id="count"></span><button id="export">Xuất ghi chú JSON</button></div><div class="grid">'''+''.join(cards)+'''</div></main><script>
const rows='''+json.dumps(rows,ensure_ascii=False).replace('<','\\u003c')+''';
const cards=[...document.querySelectorAll('article')],label=document.getElementById('label'),role=document.getElementById('role');
function filter(){let n=0;for(const card of cards){card.hidden=!((label.value==='all'||card.dataset.label===label.value)&&(role.value==='all'||card.dataset.role===role.value));if(!card.hidden)n++;}document.getElementById('count').textContent=n+' ảnh';}
label.onchange=role.onchange=filter;filter();document.getElementById('export').onclick=()=>{const notes=rows.map((r,i)=>({...r,review_note:cards[i].querySelector('textarea').value,confirmed_label:null,diagnostic_error_confirmed:false}));const u=URL.createObjectURL(new Blob([JSON.stringify(notes,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='ghi_chu_ra_nhan.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};
</script></html>'''
    (OUT/'review_images.html').write_text(page,encoding='utf-8')
    return rows


def main():
    assert not (OUT/'summary.json').exists(),'Preserve completed audit'
    files=[fusion.OUT/'oof_decisions.json',fusion.OUT/'results.json',fusion.OUT/'independent_review.json',
        INVENTORY,fusion.CV/'protocol.json',VERIFIER/'protocol.json',VERIFIER/'independent_review.json',
        *[VERIFIER/(role+'_features.npz') for role in ['train','inner','outer']],fusion.BENCHMARK,fusion.SERVING,Path(__file__)]
    protocol=dict(date='2026-10-21',purpose='Describe locked errors, source labels and raw ResNet train/held-role gap. No model selection.',
        frozen_sha256={path.relative_to(ROOT).as_posix():fusion.sha(path) for path in files},
        no_training=True,no_relabelling=True,limits='All OOF data previously used in research; descriptive only, not a fresh test. Source, label quality, group composition and difficulty are confounded.')
    fusion.write(OUT/'protocol.json',protocol)
    assert fusion.read(fusion.OUT/'independent_review.json')['status']=='PASS'
    assert fusion.read(VERIFIER/'independent_review.json')['status']=='PASS'
    rows=fusion.read(fusion.OUT/'oof_decisions.json');inventory={r['path']:r for r in fusion.read(INVENTORY)}
    roles=[fold['roles'] for fold in fusion.read(fusion.CV/'protocol.json')['folds']]
    assert len(rows)==len(inventory)==5937 and {r['path'] for r in rows}==set(inventory)
    for row in rows:
        assert row['path'] in roles[row['fold']]['outer_holdout']
        meta=inventory[row['path']]
        for key in ['label','sha256','group','source']:assert row[key]==meta[key]
    summary=dict(images=5937,classes=fusion.CLASSES,full_metrics={},per_source={},source_class_cells=[],
        scin_annotation_strata=[],weak_error_differentials=[],fold0_raw_resnet_gap=[],global_5937_score_changed=False,labels_changed=0,serving_changed=False)
    expected=fusion.read(fusion.OUT/'results.json')['methods']
    for method in ['old_classwise','validation_selected']:
        actual=independent_score(rows,method);target=expected[method]
        assert actual['confusion_matrix']==target['confusion_matrix']
        for metric in ['accuracy','macro_f1']:assert abs(actual[metric]-target[metric])<1e-12
        summary['full_metrics'][method]=actual
    for source in ['original_train','SCIN']:
        source_rows=[r for r in rows if r['source']==source]
        summary['per_source'][source]=independent_score(source_rows,'validation_selected')
        for label in fusion.CLASSES:
            rr=[r for r in source_rows if r['label']==label]
            if rr:summary['source_class_cells'].append(dict(source=source,label=label,**cell(rr,inventory)))
    for label in FOCUS:
        source_rows=[r for r in rows if r['source']=='SCIN' and r['label']==label]
        for name in ['tied_top','unique_top_below1','single_label_weight1']:
            def stratum(row):
                m=inventory[row['path']]
                if len(m['tied_top_labels'])>1:return 'tied_top'
                if m['top_annotation_weight']<1-1e-12:return 'unique_top_below1'
                return 'single_label_weight1'
            rr=[r for r in source_rows if stratum(r)==name]
            summary['scin_annotation_strata'].append(dict(label=label,stratum=name,**cell(rr,inventory)))
        wrong=[r for r in source_rows if r['predictions']['validation_selected']!=fusion.CLASSES.index(label)]
        to_eczema=[r for r in wrong if r['predictions']['validation_selected']==2]
        includes_eczema=[r for r in to_eczema if inventory[r['path']]['weighted_source_labels'].get('Eczema',0)>0]
        summary['weak_error_differentials'].append(dict(label=label,wrong_images=len(wrong),wrong_to_eczema=len(to_eczema),
            wrong_to_eczema_with_eczema_in_published_differential=len(includes_eczema),
            caveat='Alternative-label agreement is descriptive; published hard label remains the evaluation target.'))
    verifier_protocol=fusion.read(VERIFIER/'protocol.json')
    for short,role in [('train','train'),('inner','inner_validation'),('outer','outer_holdout')]:
        expected_paths=verifier_protocol['roles'][role]
        with np.load(VERIFIER/(short+'_features.npz'),allow_pickle=False) as data:
            paths=data['paths'].tolist();probs=data['original_resnet']
        if short=='train':paths=paths[:4043];probs=probs[:4043]
        assert set(paths)=={r['path'] for r in expected_paths}
        for source in ['original_train','SCIN']:
            for label in FOCUS:
                indices=[i for i,path in enumerate(paths) if inventory[path]['source']==source and inventory[path]['label']==label]
                truth=fusion.CLASSES.index(label)
                correct=int((probs[indices].argmax(1)==truth).sum()) if indices else 0
                summary['fold0_raw_resnet_gap'].append(dict(role=role,source=source,label=label,images=len(indices),correct=correct,recall=correct/len(indices) if indices else None))
    review=build_review_packet(inventory,roles)
    summary['metadata_review_queue']=dict(images=len(review),source_cases=len({r['source_case_id'] for r in review}),
        by_label=dict(Counter(r['label'] for r in review)),fold0_roles=dict(Counter(r['role_by_fold']['0'] for r in review)),
        selection_rule='Metadata ties only; no prediction-error ranking',diagnostic_errors_confirmed=0)
    for path,h in protocol['frozen_sha256'].items():assert fusion.sha(ROOT/path)==h,path
    # Aggregation identities make the source tables traceable to the full result.
    assert sum(s['images'] for s in summary['per_source'].values())==5937
    assert sum(s['correct'] for s in summary['per_source'].values())==summary['full_metrics']['validation_selected']['correct']
    for label in FOCUS:
        cells=[c for c in summary['source_class_cells'] if c['label']==label]
        assert sum(c['correct'] for c in cells)==expected['validation_selected']['confusion_matrix'][fusion.CLASSES.index(label)][fusion.CLASSES.index(label)]
    fusion.write(OUT/'summary.json',summary)
    fusion.write(OUT/'verification.json',dict(status='PASS',scope='Locked decision, arithmetic, source-role and packet integrity; no clinical label adjudication',
        protocol_sha256=fusion.sha(OUT/'protocol.json'),summary_sha256=fusion.sha(OUT/'summary.json'),
        review_queue_sha256=fusion.sha(OUT/'metadata_review_queue.jsonl'),review_images_sha256_checked=32,
        full_oof_rows_checked=5937,source_totals_reproduce_full_score=True,labels_changed=0,serving_changed=False))
    print(json.dumps(dict(complete=True,review_queue=summary['metadata_review_queue'],sources=summary['per_source']),ensure_ascii=True))


if __name__=='__main__':main()
