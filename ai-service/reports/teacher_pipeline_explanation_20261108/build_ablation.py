"""Retrospective component removal; no fits, tuning, or changed selections."""
from pathlib import Path
import hashlib
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / 'ai-service/reports/teacher_dropout_specialist_seed42_20261023'
CLASSES = ['Acne', 'Candidiasis', 'Eczema', 'Lupus', 'Psoriasis', 'SkinCancer', 'Tinea', 'Warts']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(y, pred):
    cm = np.bincount(8*y+pred, minlength=64).reshape(8, 8)
    tp = cm.diagonal()
    p = np.divide(tp, cm.sum(0), out=np.zeros(8), where=cm.sum(0)>0)
    r = np.divide(tp, cm.sum(1), out=np.zeros(8), where=cm.sum(1)>0)
    f = np.divide(2*tp, cm.sum(0)+cm.sum(1), out=np.zeros(8), where=(cm.sum(0)+cm.sum(1))>0)
    return dict(images=len(y), correct=int(tp.sum()), accuracy=float(tp.sum()/len(y)),
                macro_f1=float(f.mean()), confusion_matrix=cm.tolist(),
                per_class={c:dict(support=int(cm[i].sum()), precision=float(p[i]), recall=float(r[i]), f1=float(f[i]))
                           for i,c in enumerate(CLASSES)})


def specialist_route(current, probability):
    special = np.array([3, 4, 6, 2])
    winner = probability.argmax(1)
    accepted = np.isin(current, special) & (winner < 4) & (probability.max(1) >= .8)
    result = current.copy()
    result[accepted] = special[winner[accepted]]
    assert np.array_equal(result==5, current==5)
    return result


def main():
    assert not (OUT/'results.json').exists(), 'Preserve this analysis once completed'
    files = [SOURCE/'oof_decisions.json', SOURCE/'results.json', SOURCE/'protocol.json', SOURCE/'all_selections_locked.json',
             ROOT/'ai-service/reports/scene_grouped_oof_classwise_fusion_seed42.json', Path(__file__)]
    for fold in range(5):
        files += [SOURCE/f'fold_{fold}/selection_locked.json', SOURCE/f'fold_{fold}/outer_probabilities.npz']
    frozen = {str(p.relative_to(ROOT).as_posix()):sha(p) for p in files}
    protocol = dict(date='2026-11-08', analysis='Retrospective fixed-checkpoint component removal on previously inspected development OOF',
                    images=5937, new_fits=0, new_selections=0,
                    definition_E='Validation-selected protected B0/ConvNeXt classwise plus ResNet25 fusion from original_fusion',
                    definition_G='Already locked Macro-F1 utility gate, folds0/3 only',
                    definition_S='Already locked Dropout specialist, folds1/2 only; same checkpoint/scaler/threshold=.8',
                    limitations=['No fresh independent patient test.', 'No refitting or reselection after removing a component.',
                                 'E+S is a new descriptive recomputation, not a newly validated selection.',
                                 'Existing CNN/ensemble choices used inner validation; not fully nested end-to-end training.',
                                 'No final calibrated probability distribution is produced by label routing.'], frozen_sha256=frozen)
    (OUT/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    rows = read(SOURCE/'oof_decisions.json')
    assert len(rows)==len({r['path'] for r in rows})==5937
    y = np.array([CLASSES.index(r['label']) for r in rows])
    fold_ids = np.array([r['fold'] for r in rows])
    e = np.array([r['predictions']['original_fusion'] for r in rows])
    eg = np.array([r['predictions']['current_gate'] for r in rows])
    final = np.array([r['predictions']['validation_selected'] for r in rows])
    es = e.copy()
    reconstructed = eg.copy()
    selected = {}
    for fold in range(5):
        lock = read(SOURCE/f'fold_{fold}/selection_locked.json')
        selected[str(fold)] = lock['selected']
        mask = fold_ids == fold
        with np.load(SOURCE/f'fold_{fold}/outer_probabilities.npz',allow_pickle=False) as z:
            pathmap = {str(p):i for i,p in enumerate(z['paths'])}
            pp = z['dropout_specialist_probability'][[pathmap[r['path']] for r in rows if r['fold']==fold]]
        assert pp.shape==(int(mask.sum()),5)
        assert np.isfinite(pp).all() and (pp>=0).all() and np.allclose(pp.sum(1),1,atol=1e-6)
        raw = specialist_route(eg[mask],pp)
        assert np.array_equal(raw,np.array([r['predictions']['dropout_specialist'] for r in rows])[mask])
        if lock['selected']=='dropout_specialist':
            es[mask] = specialist_route(e[mask],pp)
            reconstructed[mask] = raw
        else:
            assert lock['selected']=='current_gate'
    assert selected=={'0':'current_gate','1':'dropout_specialist','2':'dropout_specialist','3':'current_gate','4':'current_gate'}
    assert np.array_equal(eg[np.isin(fold_ids,[1,2,4])],e[np.isin(fold_ids,[1,2,4])])
    assert np.array_equal(final,reconstructed)
    predictions = dict(ensemble=e, ensemble_specialist_fixed=es, ensemble_gate=eg, ensemble_gate_specialist=final)
    saved = read(SOURCE/'results.json')['methods']
    methods = {}
    for name,pred in predictions.items():
        assert np.array_equal(pred==5,e==5)
        s = metrics(y,pred)
        s.update(changed_vs_E=int((pred!=e).sum()), corrected_vs_E=int(((pred==y)&(e!=y)).sum()),
                 broken_vs_E=int(((pred!=y)&(e==y)).sum()))
        if name!='ensemble_specialist_fixed':
            key={'ensemble':'original_fusion','ensemble_gate':'current_gate','ensemble_gate_specialist':'validation_selected'}[name]
            assert s['confusion_matrix']==saved[key]['confusion_matrix']
            assert math.isclose(s['accuracy'],saved[key]['accuracy'],abs_tol=1e-14)
            assert math.isclose(s['macro_f1'],saved[key]['macro_f1'],abs_tol=1e-14)
        methods[name]=s
    old=read(ROOT/'ai-service/reports/scene_grouped_oof_classwise_fusion_seed42.json')
    weights={str(f['fold']):{c:f['weights'][c]['convnext_weight'] for c in CLASSES} for f in old['folds']}
    results=dict(status='PASS',scope=protocol['analysis'], images=5937, classes=CLASSES,
                 methods=methods, specialist_frozen_selections=selected, convnext_weights=weights,
                 per_fold={str(f):{n:metrics(y[fold_ids==f],p[fold_ids==f]) for n,p in predictions.items()} for f in range(5)},
                 verification=dict(saved_three_confusion_matrices_exact=True, all_five_specialist_routes_reconstructed=True,
                                   all_cancer_masks_exact=True, no_model_training=True, no_new_selection=True),
                 protocol_sha256=sha(OUT/'protocol.json'))
    assert all(sha(ROOT/k)==v for k,v in frozen.items())
    (OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:{a:v[a] for a in ['correct','accuracy','macro_f1','changed_vs_E','corrected_vs_E','broken_vs_E']} for k,v in methods.items()},indent=2))
    print('convnext_weights',json.dumps(weights))
    print('weak_metrics',json.dumps({k:{c:v['per_class'][c] for c in ['Lupus','Psoriasis','Tinea','SkinCancer']} for k,v in methods.items()}))


if __name__=='__main__':
    main()
