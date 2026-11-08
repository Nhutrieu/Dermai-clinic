"""Verify fixed source-transfer predictions and report source-specific limits."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from common import CLASSES,save_json,sha256_file
from evaluate_original_eight_resnet_transfer import ROOT,OUT,CV,OUTER,SOURCES,ARCHS,METHODS,read,aggregate,source_metrics
from evaluate_new_ensemble_holdout import read_new_samples
from summarize_original_eight_resnet50 import independently_score
from summarize_original_eight_resnet50_cv import paired_bootstrap

BASE='old_classwise'; CAND='reference_resnet_w0.25'
NAMES={'efficientnet_b0':'B0 (trung bình 5 fold)','convnext_tiny':'ConvNeXt (trung bình 5 fold)',
       'resnet50':'ResNet (trung bình 5 fold)',BASE:'Ensemble B0/ConvNeXt theo bệnh',CAND:'75% ensemble cũ + 25% ResNet'}


def recall_comparison(rows,a,b,reps=2000):
    truth=np.asarray([CLASSES.index(r['label']) for r in rows]); result={}
    for i,c in enumerate(CLASSES):
        idx=np.flatnonzero(truth==i)
        if not len(idx): continue
        _,ids=np.unique([rows[j]['group'] for j in idx],return_inverse=True); g=int(ids.max()+1)
        n=np.bincount(ids); da=(a[idx].argmax(1)==i).astype(int)-(b[idx].argmax(1)==i).astype(int)
        delta=np.bincount(ids,weights=da); rng=np.random.default_rng(20261013+i); boot=[]
        for _ in range(reps):
            sample=rng.integers(0,g,size=g); boot.append(delta[sample].sum()/n[sample].sum())
        result[c]=dict(images=len(idx),cases=g,recall_delta=float(da.mean()),
                       recall_delta_ci95=np.quantile(boot,[.025,.975]).tolist(),
                       candidate_correct_reference_wrong=int((da==1).sum()),reference_correct_candidate_wrong=int((da==-1).sum()))
    return result


def verify():
    protocol=read(OUT/'protocol.json'); audit=read(OUT/'audit.json'); result=read(OUT/'results.json'); pred=read(OUT/'predictions.json')
    assert protocol['classes']==CLASSES and result['protocol_sha256']==sha256_file(OUT/'protocol.json')
    assert protocol['audit_sha256']==sha256_file(OUT/'audit.json') and protocol['outer_manifest_sha256']==sha256_file(OUTER)
    assert protocol['cv_protocol_sha256']==sha256_file(CV/'protocol.json') and protocol['cv_verification_sha256']==sha256_file(CV/'verification.json')
    for name,h in protocol['code_sha256'].items(): assert sha256_file(ROOT/'ai-service/training'/name)==h
    for name,h in protocol['upstream'].items(): assert sha256_file(ROOT/name)==h
    for member in protocol['members']: assert sha256_file(ROOT/member['path'])==member['sha256']
    assert len(protocol['members'])==15 and {(m['fold'],m['architecture']) for m in protocol['members']}=={(f,a) for f in range(5) for a in ARCHS}
    rows=[]; by_source={}; old_sha={r['sha256'] for r in read(OUTER)['images']}
    for source,d in audit['sources'].items():
        directory,count,labelsha=SOURCES[source]; root=ROOT/directory
        assert sha256_file(root/'labels_no_near.csv')==labelsha and d['input_images']==count
        samples,meta=read_new_samples(root,root/'labels_no_near.csv'); assert meta==d['metadata']
        assert [(s.path.relative_to(ROOT).as_posix(),s.digest,CLASSES[s.label],s.group_id) for s in samples]==[(r['path'],r['sha256'],r['label'],r['group']) for r in d['rows']]
        rr=[r for r in d['rows'] if r['included']]; assert len(rr)==d['images'] and len({r['group'] for r in rr})==d['cases']
        assert {r['sha256'] for r in rr}.isdisjoint(old_sha) and len({r['path'] for r in rr})==len(rr)
        assert len(d['excluded'])==count-len(rr) and all(not r['included'] for r in d['excluded'])
        by_source[source]=rr; rows.extend(rr)
    assert len(rows)==result['images']==len(pred)
    paths=np.asarray([r['path'] for r in rows]); raw={}
    for member in protocol['members']:
        f,a=member['fold'],member['architecture']; path=OUT/f'fold_{f}_{a}.npz'
        assert (OUT/'protocol.json').stat().st_mtime_ns<path.stat().st_mtime_ns
        with np.load(path) as data:
            assert np.array_equal(data['paths'],paths) and data['protocol_sha256'].item()==sha256_file(OUT/'protocol.json')
            raw[(f,a)]=data['probabilities']
        assert raw[(f,a)].shape==(len(rows),8) and np.isfinite(raw[(f,a)]).all() and (raw[(f,a)]>=0).all()
        assert np.allclose(raw[(f,a)].sum(1),1,atol=1e-6,rtol=0)
    rebuilt=aggregate(raw,protocol['reference_weights']); start=0; comparisons={}
    for source,rr in by_source.items():
        end=start+len(rr); yy=np.asarray([CLASSES.index(r['label']) for r in rr]); sourcepred=pred[start:end]; d=result['sources'][source]
        assert d['images']==len(rr) and d['cases']==audit['sources'][source]['cases'] and d['excluded']==len(audit['sources'][source]['excluded'])
        for row,actual in zip(rr,sourcepred):
            assert {k:actual[k] for k in row}==row and actual['source']==source and set(actual['probabilities'])==set(METHODS)
        for k,p in rebuilt.items():
            values=p[start:end]; assert np.array_equal(values,np.asarray([r['probabilities'][k] for r in sourcepred]))
            independent=independently_score(yy,values); metrics=source_metrics(values,yy)
            assert all(metrics[field]==value for field,value in independent.items()) and metrics==d['results'][k]
            present=np.unique(yy); cm=np.asarray(independent['confusion_matrix']); tp=np.diag(cm)
            f1=np.divide(2*tp,cm.sum(0)+cm.sum(1),out=np.zeros(8),where=cm.sum(0)+cm.sum(1)>0)
            assert abs(f1[present].mean()-metrics['macro_f1_present_classes'])<1e-12
        aa,bb=rebuilt[CAND][start:end],rebuilt[BASE][start:end]
        comparison=paired_bootstrap(rr,aa,bb)
        comparison.update(accuracy_delta=d['results'][CAND]['accuracy']-d['results'][BASE]['accuracy'],
                          macro_f1_8_delta=d['results'][CAND]['macro_f1']-d['results'][BASE]['macro_f1'],
                          macro_f1_present_delta=d['results'][CAND]['macro_f1_present_classes']-d['results'][BASE]['macro_f1_present_classes'],
                          per_class_recall=recall_comparison(rr,aa,bb))
        comparison['caveat']='Descriptive previously inspected source, frozen five-fold bagged models, paired bootstrap on published case IDs. No inference about fresh independent data or training-seed uncertainty.'
        comparisons[source]=comparison; start=end
    state=read(ROOT/'ai-service/reports/active_research_track.json')
    assert state['active_track']=='original_eight' and state['classes']==CLASSES and sha256_file(ROOT/state['serving_checkpoint'])==state['serving_checkpoint_sha256']
    return result,comparisons


def plot_confusion(cm,path,title):
    cm=np.asarray(cm); fig,ax=plt.subplots(figsize=(11,9)); im=ax.imshow(cm,cmap='Blues'); fig.colorbar(im,ax=ax)
    ax.set(xticks=range(8),yticks=range(8),xticklabels=CLASSES,yticklabels=CLASSES,xlabel='Predicted',ylabel='Published label',title=title)
    plt.setp(ax.get_xticklabels(),rotation=40,ha='right')
    for i in range(8):
        for j in range(8): ax.text(j,i,str(cm[i,j]),ha='center',va='center',color='white' if cm[i,j]>cm.max()/2 else 'black')
    fig.tight_layout(); fig.savefig(path,dpi=160); plt.close(fig)


def main():
    result,comparisons=verify(); save_json(OUT/'paired_comparisons.json',comparisons)
    save_json(OUT/'verification.json',dict(status='PASS',verifier_code_sha256=sha256_file(Path(__file__)),
        protocol_sha256=sha256_file(OUT/'protocol.json'),results_sha256=sha256_file(OUT/'results.json'),predictions_sha256=sha256_file(OUT/'predictions.json'),
        comparison_sha256=sha256_file(OUT/'paired_comparisons.json'),images=result['images'],checkpoint_count=15,
        checks=['Original eight classes, active track and serving SHA unchanged','Frozen15checkpoints/source labels/code hashes unchanged',
                'Registered duplicate quarantine; exact disjointness from original5937pool','Source order, image SHA and published case identity verified',
                'Each member probability artifact follows protocol registration','Five-fold reference and fixed75:25 reconstructed from raw member outputs',
                'Independent NumPy confusion, Accuracy, precision, recall, eight-class and present-class Macro F1',
                'Separate source scores; paired case bootstrap; no source-based fit or new-eight checkpoints']))
    lines=['# Kiểm tra chuyển nguồn của ensemble bộ cũ có ResNet','',
           '**Hoàn tất; kiểm chứng PASS. Các nguồn này đã được xem trước đây, không phải test mới độc lập.**','',
           'Giữ nguyên 15 checkpoint (ba kiến trúc × năm fold). Trung bình xác suất năm fold cho từng kiến trúc; đối chứng là trung bình năm ensemble B0/ConvNeXt theo bệnh với trọng số inner đã khóa. So sánh công thức cố định 75% đối chứng + 25% ResNet. Không chỉnh nhiệt độ, trọng số, ngưỡng hoặc chọn checkpoint theo các nguồn này.','',
           'Kiểm tra SHA-256 và dHash khoảng cách tối đa 3 với toàn bộ 5.937 ảnh phát triển trước khi suy luận; ảnh nghi trùng được để riêng. dHash là kiểm tra ảnh nghi trùng, không chứng minh tính độc lập theo bệnh nhân.','']
    for source,d in result['sources'].items():
        m=d['results']; present=m[BASE]['present_classes']; cmp=comparisons[source]
        lines += [f'## {source}','',f"{d['images']} ảnh / {d['cases']} ca; {d['excluded']} ảnh để riêng vì nghi trùng. Nhãn có mẫu: {', '.join(present)}.",'',
                  '| Phương án | Đúng | Accuracy | Macro F1, lớp có mẫu | Macro F1, đủ 8 lớp |',
                  '|---|---:|---:|---:|---:|']
        for k in METHODS:
            a=m[k]; lines.append(f"| {NAMES[k]} | {a['correct']} | {a['accuracy']:.2%} | {a['macro_f1_present_classes']:.2%} | {a['macro_f1']:.2%} |")
        lines += ['','Tất cả model vẫn dự đoán tám lớp. Macro F1 lớp có mẫu lấy trung bình F1 của các nhãn có ảnh thật trong nguồn; đây không phải việc giới hạn model chỉ dự đoán các nhãn đó.',
                  '', '| Bệnh | Ảnh | Ca | Recall cũ | Recall 75:25 | Precision cũ | Precision 75:25 | F1 cũ | F1 75:25 |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
        for c in present:
            a,b=m[BASE]['per_class'][c],m[CAND]['per_class'][c]; cases=cmp['per_class_recall'][c]['cases']
            values=[v[field] for field in ('recall','precision','f1') for v in (a,b)]
            lines.append(f"| {c} | {a['support']} | {cases} | "+' | '.join(f'{v:.2%}' for v in values)+' |')
        ci=cmp['accuracy_delta_ci95']
        lines += ['',f"Chênh Accuracy 75:25 − cũ: {cmp['accuracy_delta']*100:+.2f} điểm %, CI95% [{ci[0]*100:+.2f}; {ci[1]*100:+.2f}], bootstrap cặp theo ca, 2.000 lần."]
        for c in ('Lupus','Psoriasis','SkinCancer'):
            if c in cmp['per_class_recall']:
                q=cmp['per_class_recall'][c]; cc=q['recall_delta_ci95']
                lines.append(f"- {c}: {q['images']} ảnh/{q['cases']} ca; Δ Recall {q['recall_delta']*100:+.2f} điểm %, CI95% [{cc[0]*100:+.2f}; {cc[1]*100:+.2f}].")
        for k in (BASE,CAND): plot_confusion(m[k]['confusion_matrix'],OUT/f'{source}_{k}_confusion.png',f'{source}: {k} ({d["images"]} photos)')
        lines += ['',f"[Ma trận đối chứng]({source}_{BASE}_confusion.png), [ma trận 75:25]({source}_{CAND}_confusion.png).",'']
    lines += ['## Cách đọc kết quả','',
              '- Báo cáo từng nguồn riêng; không gộp hai tỷ lệ accuracy thành điểm tổng tám bệnh.',
              '- SkinDisNet chỉ có Eczema/Tinea. DermaCon có ít ca Lupus/SkinCancer; số liệu đó chưa đủ để xác nhận hiệu năng lâm sàng.',
              '- Các nguồn đã được dùng trong nghiên cứu trước đây. Giữ phép đo chuyển nguồn này ở mức mô tả; một tập mới chưa xem mới có thể xác nhận khả năng tổng quát.',
              '- Trung bình năm fold khác cách dự đoán OOF một model mỗi ảnh; không gọi chênh lệch với79,06%OOF là mức tăng/giảm trên cùng phép đo.',
              '- Checkpoint ứng dụng giữ nguyên; kết quả nguồn không dùng để chỉnh thêm trọng số.',
              '', '[Giao thức](protocol.json), [audit](audit.json), [kết quả từng nguồn](results.json), [xác minh](verification.json), [bootstrap cặp](paired_comparisons.json).','']
    (OUT/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(verification='PASS',sources={s:{k:{field:d['results'][k][field] for field in ('accuracy','macro_f1_present_classes')} for k in (BASE,CAND)} for s,d in result['sources'].items()})),flush=True)


if __name__=='__main__': main()
