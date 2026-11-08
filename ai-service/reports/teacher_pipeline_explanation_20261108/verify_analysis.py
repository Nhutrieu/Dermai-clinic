"""Cross-check descriptive table using saved labels and sklearn metrics."""
from pathlib import Path
import json
import hashlib
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protocol=read(OUT/'protocol.json')
for path,digest in protocol['frozen_sha256'].items():
    assert sha(ROOT/path)==digest,path
r=read(OUT/'results.json')
rows=read(ROOT/'ai-service/reports/teacher_dropout_specialist_seed42_20261023/oof_decisions.json')
y=[r['classes'].index(x['label']) for x in rows]
e=[x['predictions']['original_fusion'] for x in rows]
predictions={
    'ensemble':e,
    'ensemble_specialist_fixed':[x['predictions']['validation_selected'] if x['fold'] in [1,2] else x['predictions']['original_fusion'] for x in rows],
    'ensemble_gate':[x['predictions']['current_gate'] for x in rows],
    'ensemble_gate_specialist':[x['predictions']['validation_selected'] for x in rows]}
for name,p in predictions.items():
    expected=r['methods'][name]
    assert confusion_matrix(y,p,labels=range(8)).tolist()==expected['confusion_matrix']
    assert abs(accuracy_score(y,p)-expected['accuracy'])<1e-14
    precision,recall,f1,support=precision_recall_fscore_support(y,p,labels=range(8),zero_division=0)
    assert abs(float(f1.mean())-expected['macro_f1'])<1e-14
    for i,c in enumerate(r['classes']):
        for k,v in [('precision',precision[i]),('recall',recall[i]),('f1',f1[i]),('support',support[i])]:
            assert abs(float(v)-expected['per_class'][c][k])<1e-14
    assert [(v==5) for v in p]==[(v==5) for v in e]
protected={
    'ai-service/models/best_model.pth':'975e4852023ebb9d3af544b819bec0b887cf75b1467447c87c40591da90b7a17',
    'ai-service/app/config.py':'bda739d518517f2967b30abf99f3dd8780c811b740792bfa2715b5ff436221e1',
    'ai-service/reports/active_research_track.json':'231db2e97b6fee5bad69ba890ac9d8f12ac5825fb56f488209b77478d1cb8f19'}
for p,d in protected.items():assert sha(ROOT/p)==d,p
v=dict(status='PASS', images=5937, method_sets=4, sklearn_metrics_match=True,
       frozen_source_hashes_match=True, serving_and_registry_hashes_unchanged=True,
       exact_cancer_masks=True, new_fits=0, new_selections=0,
       results_sha256=sha(OUT/'results.json'), verifier_sha256=sha(Path(__file__)), protected_sha256=protected)
(OUT/'verification.json').write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
print(json.dumps(v,indent=2))
