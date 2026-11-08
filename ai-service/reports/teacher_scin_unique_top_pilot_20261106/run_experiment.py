"""303: metadata-only source-tie curation versus case-size matched removal control."""
from pathlib import Path
from datetime import datetime,timezone
import importlib.util,json,hashlib,os,gc,math
import numpy as np
import torch
from torch.nn import functional as F
from torch.utils.data import DataLoader
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;R=OUT.parent
AUDIT=R/'teacher_scin_unique_top_audit_20261106';PREVIOUS=R/'teacher_cnn8_gce_20261106';FULL=R/'teacher_fine_eight_cnn_pilot_20261104'
MODELS=ROOT/'ai-service/candidates'/OUT.name
spec=importlib.util.spec_from_file_location('scin303_parent301',PREVIOUS/'run_experiment.py');previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
pool,cnn,fine,io=previous.pool,previous.cnn,previous.fine,previous.io
read,write,sha,utc=previous.read,previous.write,previous.sha,previous.utc
PRIMARY='unique_top';MATCHED='matched_control';FULL_CONTROL='natural_ce_control';ARMS=[MATCHED,PRIMARY]

def objective(logits,y,weights):
    if weights.ndim!=1 or len(weights)!=len(y) or not torch.isfinite(weights).all() or (weights<0).any():raise ValueError('Invalid fixed fit weights')
    return (F.cross_entropy(logits,y,reduction='none')*weights).mean()

def load(p):
    with np.load(p,allow_pickle=False) as a:return dict(a)

def status(state,**kw):
    write(OUT/'status.json',dict(state=state,pid=os.getpid(),updated_utc=utc(),selected=None,serving_changed=False,**kw))

def prepare():
    assert not(OUT/'protocol.json').exists(),'Preserve303 registration'
    parent=read(PREVIOUS/'protocol.json');done=read(PREVIOUS/'completion.json')
    assert done['final_integrity_check']['status']=='PASS' and read(PREVIOUS/'independent_review.json')['status']=='PASS'
    audit=read(AUDIT/'protocol.json');frozen=dict(audit['sources_sha256'])
    extra=[AUDIT/'protocol.json',AUDIT/'results.json',AUDIT/'fold1_cv0_probe_manifest.json',AUDIT/'fold1_cv0_source_cases.json',PREVIOUS/'protocol.json',PREVIOUS/'predictions.npz',PREVIOUS/'training_report.json',PREVIOUS/'run_experiment.py',FULL/'training_report.json',Path(__file__),ROOT/'ai-service/tests/test_scin_unique_top_objective.py',OUT/'unit_checks.json',ROOT/'tmp/verify_scin_unique_top_pilot_20261106.py']
    for f in extra:frozen[f.relative_to(ROOT).as_posix()]=sha(f)
    for module in [pool,cnn,fine,io,pool.transfer,pool.repeat]:
        f=Path(module.__file__);frozen[f.relative_to(ROOT).as_posix()]=sha(f)
    p={key:parent[key] for key in ['classes','job_name','job','fit_rows','query_rows','roles','image_manifest','endpoint','imagenet_path','imagenet_sha256']}
    manifest=read(AUDIT/'fold1_cv0_probe_manifest.json')
    assert manifest['fit_paths']==[v['path'] for v in p['fit_rows']]
    assert manifest['fit_sha256']==[v['sha256'] for v in p['fit_rows']]
    p.update(registered_utc=utc(),frozen_sha256=frozen,primary=PRIMARY,matched_control=MATCHED,full_control=FULL_CONTROL,arms=ARMS,
      hypothesis='Test whether not learning from source-tied SCIN cases improves classification compared with equal-size source/class/case-size matched removals. Metadata only, not model mistakes. No expansion of medical aliases, relabeling or claim of clinical label correction.',
      intervention='Ownfit only; mask all known source-case members with tied raw top labels in Lupus/Psoriasis/Tinea/Eczema. Fixed per-image weights:0 for masked; N_class/N_retained_class otherwise. Keep per-class total loss weight equal to original. Both new arms use same weighted CE formula, all2699 images/order/augmentation/updates as279. Zero-weight images are forwarded but do not contribute data gradient; no BatchNorm, model.eval, no DropPath.',
      matched_control_design='Mask DIFFERENT unique-top SCIN cases, exact match class and number of images per case to treatment. Fixed SHA rank seed42, no model outcomes. Retained image/class/source counts and effective class weight totals identical. Not a proof that unambiguous source diagnosis is correct.',
      training='Two fresh ConvNeXt-Tiny/ImageNet seed42 CNN8, only classifier/features7 trainable; same initialization as279. Natural CE weightedmean per batch. Six epochs fixed; AdamW head2e-4,last5e-5,WD.0002,clip2,batch16,BF16forward/FP32loss/params,eval mode. All6 input streams must match279. No warmup on excluded labels, learned weights, new backbone, extra source, class resampling, GCE, SupCon, CutMix, EMA or checkpoint selection.',
      endpoint_addition='Keep all previous301/283 constraints and all288/294/295/NLL296 references, each query block Accuracy/MF>=reference; SkinCancer prediction mask exact. Primary must keep Acc and weak P/R/F1 and strictly raise MF and LupusRecall versus BOTH fullCE and matched control. Allthree block Acc/MF>=bothcontrols. No post-result relaxation or branch switching. Existing NLL reference is unadmitted.',
      boundary='Freeze source-only manifests, protocol, code, tests and checker before training. Lock BOTH checkpoints/proofs/logs before any new query forward. Lock both score arrays and routed predictions before computing metrics. Fresh CNNs never fit query/inner/main outer; historical query has been used adaptively before and is not blind.',
      limitations=['One fixed historical TRAIN query1332, not global5937 or newpatients.','Metadataunique-top does not imply clinical certainty; tied labels can describe related diseases.','Source tie-filter cannot add missing LupusSCIN cases: fit1 and query8 remain.','Matched removals control data volume, source/class counts and case sizes, not every aspect of image difficulty.','A single pilot cannot establish stable benefit; no clinical review or source label correction.'],
      fit_loss_manifests=manifest['arms'],matched_case_size_counts=manifest['matched_case_size_counts'],CNN_fits=2,CNN_updates=2028,train_tensor_views=32388,query_forwards=2664,new_images=0,labels_changed=0,selected=None,promotion_eligible=False,global_5937_score_changed=False,serving_changed=False,research_registry_changed=False)
    for rel,h in frozen.items():assert sha(ROOT/rel)==h,rel
    for rel,h in p['image_manifest'].items():assert sha(ROOT/rel)==h,rel
    assert sha(Path(p['imagenet_path']))==p['imagenet_sha256']
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    MODELS.mkdir(parents=True,exist_ok=True);write(OUT/'protocol.json',p);status('registered303');return p

def train(p):
    reference=read(FULL/'training_report.json');records={}
    for arm in ARMS:
        net=pool.repeat.fresh(p['imagenet_path'],42).cuda().eval();frozen=cnn.frozen_hash(net,'last_stage');initial=cnn.state_sha(cnn.delta(net,'last_stage'))
        assert initial==reference['initial_trainable_sha256'] and frozen==reference['frozen_initial_sha256']
        opt=torch.optim.AdamW([dict(params=[v for n,v in net.named_parameters() if n.startswith('classifier.')],lr=2e-4),dict(params=[v for n,v in net.named_parameters() if n.startswith('features.7.')],lr=5e-5)],weight_decay=.0002)
        base=fine.Images(p['fit_rows'],True);w=np.asarray(p['fit_loss_manifests'][arm]['loss_weights'],dtype=np.float32);assert len(w)==len(base)
        logs=[];steps=0;proof=None
        for epoch in range(1,7):
            order=np.random.default_rng(421100+epoch).permutation(len(base));loader=DataLoader(cnn.SeededDataset(base,order.tolist(),1100+epoch),batch_size=16,shuffle=False,num_workers=0)
            stream=hashlib.sha256();pixels=hashlib.sha256();weightstream=hashlib.sha256();loss_sum=0.;normmax=0.;count=0;active=0
            status('training303',arm=arm,epoch=epoch,epochs=6)
            for batchid,(x,y) in enumerate(loader):
                selected=order[count:count+len(y)];weights=torch.from_numpy(w[selected]).cuda();xb,yb=x.numpy().tobytes(),y.numpy().tobytes()
                stream.update(xb);stream.update(yb);pixels.update(xb);weightstream.update(w[selected].tobytes());opt.zero_grad(set_to_none=True)
                with torch.autocast('cuda',dtype=torch.bfloat16):raw=net(x.cuda())
                logits=raw.float();loss=objective(logits,y.cuda(),weights);assert torch.isfinite(loss);loss.backward()
                for n,v in net.named_parameters():
                    if v.grad is not None:assert cnn.allowed(n,'last_stage') and torch.isfinite(v.grad).all()
                norm=torch.nn.utils.clip_grad_norm_([v for v in net.parameters() if v.requires_grad],2.);assert torch.isfinite(norm);opt.step()
                steps+=1;count+=len(y);active+=int((weights>0).sum());loss_sum+=float(loss.detach())*len(y);normmax=max(normmax,float(norm))
                if epoch==1 and batchid==0:
                    f=MODELS/(arm+'_first_step.pth');delta=cnn.delta(net,'last_stage');torch.save(dict(delta_state=delta,logits=logits.detach().cpu(),weights=weights.cpu()),f)
                    proof=dict(path=f.relative_to(ROOT).as_posix(),input_sha256=hashlib.sha256(xb+yb).hexdigest(),delta_sha256=cnn.state_sha(delta),loss=float(loss.detach()),gradient_norm_before_clip=float(norm))
                if batchid%50==0:print(dict(arm=arm,epoch=epoch,batch=batchid,steps=steps),flush=True)
            rec=dict(epoch=epoch,steps=169,cumulative_updates=steps,rows=count,active_loss_rows=active,masked_loss_rows=count-active,mean_weighted_ce=loss_sum/count,input_stream_sha256=stream.hexdigest(),image_stream_sha256=pixels.hexdigest(),weight_stream_sha256=weightstream.hexdigest(),order_sha256=hashlib.sha256(order.astype('<i8').tobytes()).hexdigest(),trainable_sha256=cnn.state_sha(cnn.delta(net,'last_stage')),gradient_norm_max_before_clip=normmax)
            ref=reference['epoch_logs'][epoch-1]
            for key in ['input_stream_sha256','image_stream_sha256','order_sha256']:assert rec[key]==ref[key],(arm,epoch,key)
            assert count==2699 and active==p['fit_loss_manifests'][arm]['retained_images']
            assert cnn.frozen_hash(net,'last_stage')==frozen and not any(m.training for m in net.modules())
            logs.append(rec);write(OUT/(arm+'_train_progress.json'),dict(epoch_logs=logs));print(dict(arm=arm,epoch_done=epoch,loss=loss_sum/count),flush=True)
        f=MODELS/(arm+'.pth');torch.save(dict(delta_state=cnn.delta(net,'last_stage'),phase='source_unique_top303',arm=arm,seed=42,epoch=6,updates=steps,auxiliary_outputs=8,imagenet_sha256=p['imagenet_sha256'],frozen_sha256=frozen),f)
        records[arm]=dict(checkpoint=f.relative_to(ROOT).as_posix(),rows=2699,retained_images=p['fit_loss_manifests'][arm]['retained_images'],epochs=6,steps=steps,initial_trainable_sha256=initial,frozen_initial_sha256=frozen,frozen_final_sha256=cnn.frozen_hash(net,'last_stage'),epoch_logs=logs,first_step=proof,query_forward_during_training=False)
        del net,opt;gc.collect();torch.cuda.empty_cache()
    write(OUT/'training_report.json',records)
    files=[OUT/'training_report.json']
    for arm in ARMS:files.extend([ROOT/records[arm]['checkpoint'],ROOT/records[arm]['first_step']['path'],OUT/(arm+'_train_progress.json')])
    write(OUT/'training_locked.json',dict(locked_utc=utc(),protocol_sha256=sha(OUT/'protocol.json'),query_forward_started=False,artifacts_sha256={f.relative_to(ROOT).as_posix():sha(f) for f in files}))

def predict(p):
    records=read(OUT/'training_report.json');locked=read(OUT/'training_locked.json')
    for rel,h in locked['artifacts_sha256'].items():assert sha(ROOT/rel)==h,rel
    a=load(PREVIOUS/'predictions.npz')
    for arm in ARMS:
        ck=torch.load(ROOT/records[arm]['checkpoint'],map_location='cpu',weights_only=True);net=pool.repeat.fresh(p['imagenet_path'],42);net.load_state_dict(ck['delta_state'],strict=False);net=net.cuda().eval();state=cnn.state_sha(net.state_dict());values=[];status('query_inference303',arm=arm)
        with torch.inference_mode():
            for x,_ in DataLoader(fine.Images(p['query_rows']),batch_size=16,shuffle=False,num_workers=0):values.append(net(x.cuda()).float().cpu().numpy())
        raw=np.concatenate(values);assert cnn.state_sha(net.state_dict())==state;scores=raw[:,previous.INV];pred,d=pool.route(a['parent296_nll'],scores)
        a[arm]=pred;a[arm+'_native_logits']=raw;a[arm+'_scores']=scores
        for k,v in d.items():a[arm+'_'+k]=v
        del net;gc.collect();torch.cuda.empty_cache()
    f=OUT/'predictions.npz';np.savez_compressed(f,**a)
    write(OUT/'predictions_locked.json',dict(locked_utc=utc(),protocol_sha256=sha(OUT/'protocol.json'),metrics_started=False,artifacts_sha256={f.relative_to(ROOT).as_posix():sha(f)}))

def score(p):
    a=load(OUT/'predictions.npz');truth=a['truth'];refs={k:io.metrics(a[k],truth) for k in previous.REFS+[FULL_CONTROL,pool.CONTROL]};results={}
    for arm in ARMS:
        pool.transfer.OUT=OUT;rec=pool.transfer.score_arm(p,arm);original=rec['full_pass'];m=rec['metrics'];retained={k:pool.keep_failures(m,refs[k],k) for k in previous.REFS}
        uniform=pool.keep_failures(m,refs[pool.CONTROL],'uniform294',require_LP=False)
        checks=[FULL_CONTROL]+([MATCHED] if arm==PRIMARY else [])
        comparisons={k:pool.keep_failures(m,io.metrics(a[k],truth),k) for k in checks}
        blocks={};blockpass=True
        for i,file in enumerate(p['job']['cv_plans']):
            ix=load(ROOT/file)['holdout_indices'];cand=io.metrics(a[arm][ix],truth[ix]);b=dict(images=len(ix),candidate=cand,comparisons={})
            for k in previous.REFS+checks:
                old=io.metrics(a[k][ix],truth[ix]);ok=all(cand[metric]>=old[metric]-1e-12 for metric in ['accuracy','macro_f1']);b['comparisons'][k]=dict(accuracy=old['accuracy'],macro_f1=old['macro_f1'],passed=ok);blockpass=blockpass and ok
            blocks[str(i)]=b
        rec.update(original_283_guard_pass=original,retained_failures=retained,versus_uniform294_failures=uniform,treatment_control_failures=comparisons,block_diagnostics=blocks,
            full_pass=original and not(any(retained.values()) or uniform or any(comparisons.values())) and blockpass,
            raw_metrics=io.metrics(np.argmax(a[arm+'_scores'],axis=1),truth),selected=None)
        write(OUT/(arm+'_results.json'),rec);results[arm]=rec
    write(OUT/'results.json',dict(completed_utc=utc(),protocol_sha256=sha(OUT/'protocol.json'),primary=PRIMARY,controls=[FULL_CONTROL,MATCHED],query_images=1332,reference_metrics=refs,arms=results,CNN_fits=2,CNN_updates=2028,train_tensor_views=32388,active_loss_images_per_arm=2639,query_forwards=2664,selected=None,promotion_eligible=False,global_5937_score_changed=False,serving_changed=False,research_registry_changed=False))
    status('awaiting_verification303');print({a:dict(accuracy=results[a]['metrics']['accuracy'],macro_f1=results[a]['metrics']['macro_f1'],full_pass=results[a]['full_pass']) for a in ARMS},flush=True)

if __name__=='__main__':
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False
    with threadpool_limits(limits=4):p=prepare();train(p);predict(p);score(p)
