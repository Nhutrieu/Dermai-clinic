"""305: three new author-labelled clinical Lupus photos versus matched old-photo replay."""
from pathlib import Path
from collections import Counter
import importlib.util,hashlib,json,os,gc
import numpy as np
import torch
from torch.nn import functional as F
from torch.utils.data import DataLoader
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;R=OUT.parent;DATA=R/'teacher_open_case_photo_intake_20261106';PREVIOUS=R/'teacher_scin_unique_top_pilot_20261106'
MODELS=ROOT/'ai-service/candidates'/OUT.name
s=importlib.util.spec_from_file_location('source305_parent303',PREVIOUS/'run_experiment.py');old=importlib.util.module_from_spec(s);s.loader.exec_module(old)
pool,cnn,fine,io=old.pool,old.cnn,old.fine,old.io
read,write,sha,utc=old.read,old.write,old.sha,old.utc
PRIMARY='new_case_lupus';CONTROL='old_lupus_replay';FULL='natural_ce_control';ARMS=[CONTROL,PRIMARY]

def make_arms(base,candidates):
    if len(candidates)!=3:raise ValueError('Exactly the three frozen single-photo candidates required')
    if any(v['label']!='Lupus' or v['technical_visual_review_pending'] for v in candidates):raise ValueError('Only technically reviewed source-labelled Lupus candidates allowed')
    if len({v['path'] for v in candidates})!=3 or len({v['source_group'] for v in candidates})!=3:raise ValueError('Three distinct source paths/article groups required')
    if {v['sha256'] for v in candidates}&{v['sha256'] for v in base}:raise ValueError('New byte fingerprint already in fit')
    if {v['path'] for v in candidates}&{v['path'] for v in base}:raise ValueError('New path already in fit')
    eligible=sorted([v for v in base if v['label']=='Lupus' and v['source']=='original_train'],key=lambda v:hashlib.sha256(('42:305:'+v['sha256']+':'+v['path']).encode()).hexdigest())
    replay=[];groups=set()
    for row in eligible:
        if row['group'] in groups:continue
        replay.append(dict(row));groups.add(row['group'])
        if len(replay)==3:break
    if len(replay)!=3:raise ValueError('Not enough own-fit Lupus proxy groups for replay control')
    new=[dict(path=v['path'],label='Lupus',sha256=v['sha256'],source='PMC_case_report',group=v['source_group'],article=v['pmcid'],source_label_status='author_reported_case_figure_not_project_clinically_reviewed') for v in sorted(candidates,key=lambda v:v['sha256'])]
    arms={CONTROL:[dict(v) for v in base]+replay,PRIMARY:[dict(v) for v in base]+new}
    assert Counter(v['label'] for v in arms[CONTROL])==Counter(v['label'] for v in arms[PRIMARY])
    return arms

def load(p):
    with np.load(p,allow_pickle=False) as a:return dict(a)

def status(state,**kw):write(OUT/'status.json',dict(state=state,pid=os.getpid(),updated_utc=utc(),selected=None,serving_changed=False,**kw))

def prepare():
    assert not(OUT/'protocol.json').exists(),'Preserve305 registration'
    original=read(PREVIOUS/'protocol.json');done=read(DATA/'completion.json')
    assert done['source_verification']=='PASS' and done['single_photo_pilot_candidates']==3
    assert read(PREVIOUS/'verification.json')['status']=='PASS'
    candidates=[json.loads(x) for x in (DATA/'single_photo_pilot_candidates.jsonl').read_text(encoding='utf-8').splitlines()]
    arms=make_arms(original['fit_rows'],candidates);frozen=dict(original['frozen_sha256'])
    for rel,h in done['artifacts_sha256'].items():
        file=DATA/rel;assert sha(file)==h;frozen[file.relative_to(ROOT).as_posix()]=h
    for file in [DATA/'completion.json',Path(__file__),OUT/'unit_checks.json',ROOT/'ai-service/tests/test_new_case_lupus_pilot.py',ROOT/'tmp/verify_new_case_lupus_pilot_20261106.py',PREVIOUS/'completion.json',PREVIOUS/'protocol.json',PREVIOUS/'predictions.npz']:
        frozen[file.relative_to(ROOT).as_posix()]=sha(file)
    p={k:original[k] for k in ['classes','job_name','job','fit_rows','query_rows','roles','endpoint','imagenet_path','imagenet_sha256']}
    images=dict(original['image_manifest'])
    for row in candidates:images[row['path']]=row['sha256']
    forbidden=p['query_rows']+[v for name,rr in p['roles'].items() if name!='train' for v in rr]
    for key in ['path','sha256','group']:
        assert not {v[key] for v in arms[PRIMARY][-3:]}&{v[key] for v in forbidden}
    p.update(registered_utc=utc(),frozen_sha256=frozen,image_manifest=images,primary=PRIMARY,control=CONTROL,training_rows_by_arm=arms,source_candidates=candidates,
      hypothesis='Test a small valid source change: three newly retrieved published clinical Lupus photographs, caption-labelled by authors, compared with three additional own-fit old Lupus photographs. Source labels are not new project clinical confirmation. This adds source images instead of masking uncertain source ties.',
      source_admission='All three single, non-composite clinical images from304, chosen by modality before any model scoring. Accept published labels only for this auxiliary TRAIN pilot. Original304 manifests stay provisional/not admitted;305copies declare pilot role only. The other eight composite clinical figure files and the diagram are not used. No new test images, clinical relabeling, patient-independence claim, or AI-generated pictures.',
      control_design='Append3source rows in PRIMARY, append3deterministic SHA-ranked original_train Lupus rows from distinct ownfit proxy groups inCONTROL. All2699oldfit images remain, one visit each/epoch;3addedLupus visits inBOTHarms. Identical2702-row label vector/order/augmentation seeds each epoch. Control intentionally repeats3oldimages; unique images2699vs2702. Not a source-matched clinical-confirmation study.',
      training='FreshImageNetConvNeXtTinyCNN8 seed42, onlyclassifier/features7trainable, naturalCE 6epochsfixed, model.eval/noDropPath; AdamWhead2e-4,last5e-5,WD.0002,clip2,batch16,BF16forward/FP32lossparams. Each arm169updates/epoch/1014total,16212tensorviews,18addedLupusvisits. No addedloss/resampling/classweights/augmentation/epochselection. Botharms match oneanother; their2702row shuffle andlastbatch differfromold2699CE279, so the replay arm controls this change.',
      boundary='Freeze new source evidence, data/code/tests/checker and all settings before training. All6 base-image streams and full label/order streams must match acrossarms; only addedphoto tensors may differ. Save and independently replay first update containing addedphoto. LockBOTHmodels/logs beforequery; lockbothscore arrays beforemetrics. No otherquery/inner/outer evaluation.',
      routing='Exact old294margin>ln2, weakendpoint, noCancerendpoint, parent=fixedNLL296unadmittedreference. No newgates/calibration/thresholdfitting. Keepallold283guards and288/294/295/296retention/blockguards; PRIMARY must keepAcc/weakP/R/F1 and strictlyraiseMF/LupusRecallvsFullCEandreplayCONTROL; eachqueryblockAcc/MF>=controls. Cancerpredictionmaskexact. Noafterresultrelaxation.',
      limitations=['Onlythree newsourcefiles/articleproxies, notverifiednewpatients.','ReportedLupusdiagnoses were not reviewed anew by a projectclinician.','Case reports may be atypical or differ from self-captured SCIN photos.','OnehistoricalTRAINquery1332 adaptivepilot, notblind, mainvalidation, global5937orclinicalaccuracy.','NewsourceonlyLupus; Psoriasis/Tineacomposites notused. Needstability before anyadmission evenifpilotimproves.'],CNN_fits=2,CNN_updates=2028,train_tensor_views=32424,new_source_files=3,new_source_image_visits=18,query_forwards=2664,selected=None,promotion_eligible=False,global_5937_score_changed=False,serving_changed=False,research_registry_changed=False)
    for rel,h in frozen.items():assert sha(ROOT/rel)==h,rel
    for rel,h in images.items():assert sha(ROOT/rel)==h,rel
    assert sha(Path(p['imagenet_path']))==p['imagenet_sha256'] and torch.cuda.is_available()
    MODELS.mkdir(parents=True,exist_ok=True);write(OUT/'protocol.json',p);status('registered305');return p

def train(p):
    reference=read(R/'teacher_fine_eight_cnn_pilot_20261104/training_report.json');records={}
    for arm in ARMS:
        rows=p['training_rows_by_arm'][arm];net=pool.repeat.fresh(p['imagenet_path'],42).cuda().eval();initial=cnn.state_sha(cnn.delta(net,'last_stage'));frozen=cnn.frozen_hash(net,'last_stage')
        assert initial==reference['initial_trainable_sha256'] and frozen==reference['frozen_initial_sha256']
        opt=torch.optim.AdamW([dict(params=[v for n,v in net.named_parameters() if n.startswith('classifier.')],lr=2e-4),dict(params=[v for n,v in net.named_parameters() if n.startswith('features.7.')],lr=5e-5)],weight_decay=.0002)
        logs=[];steps=0;proof=None;base=fine.Images(rows,True)
        for epoch in range(1,7):
            order=np.random.default_rng(421100+epoch).permutation(len(rows));loader=DataLoader(cnn.SeededDataset(base,order.tolist(),1100+epoch),batch_size=16,shuffle=False,num_workers=0)
            stream=hashlib.sha256();base_stream=hashlib.sha256();labelstream=hashlib.sha256();count=0;added=0;loss_sum=0.;status('training305',arm=arm,epoch=epoch,epochs=6)
            for batchid,(x,y) in enumerate(loader):
                indices=order[count:count+len(y)];original=indices<2699;new=~original;xb,yb=x.numpy().tobytes(),y.numpy().tobytes();stream.update(xb);stream.update(yb);labelstream.update(yb);base_stream.update(x.numpy()[original].tobytes())
                opt.zero_grad(set_to_none=True)
                with torch.autocast('cuda',dtype=torch.bfloat16):raw=net(x.cuda())
                logits=raw.float();loss=F.cross_entropy(logits,y.cuda());assert torch.isfinite(loss);loss.backward()
                for n,param in net.named_parameters():
                    if param.grad is not None:assert cnn.allowed(n,'last_stage') and torch.isfinite(param.grad).all()
                norm=torch.nn.utils.clip_grad_norm_([v for v in net.parameters() if v.requires_grad],2.);assert torch.isfinite(norm);opt.step();steps+=1;count+=len(y);added+=int(new.sum());loss_sum+=float(loss.detach())*len(y)
                if proof is None and new.any():
                    file=MODELS/(arm+'_first_added_step.pth');delta=cnn.delta(net,'last_stage');torch.save(dict(delta_state=delta,logits=logits.detach().cpu()),file)
                    proof=dict(path=file.relative_to(ROOT).as_posix(),epoch=epoch,batch=batchid,prefix_updates=steps,added_row_indices=indices[new].tolist(),input_sha256=hashlib.sha256(xb+yb).hexdigest(),delta_sha256=cnn.state_sha(delta),loss=float(loss.detach()),gradient_norm=float(norm))
                if batchid%60==0:print(dict(arm=arm,epoch=epoch,batch=batchid,steps=steps),flush=True)
            rec=dict(epoch=epoch,rows=count,added_Lupus_visits=added,base_image_visits=count-added,mean_ce=loss_sum/count,input_stream_sha256=stream.hexdigest(),base_image_stream_sha256=base_stream.hexdigest(),label_stream_sha256=labelstream.hexdigest(),order_sha256=hashlib.sha256(order.astype('<i8').tobytes()).hexdigest(),trainable_sha256=cnn.state_sha(cnn.delta(net,'last_stage')))
            assert count==2702 and added==3 and cnn.frozen_hash(net,'last_stage')==frozen
            logs.append(rec);write(OUT/(arm+'_train_progress.json'),dict(epoch_logs=logs));print(dict(arm=arm,epoch_done=epoch,loss=loss_sum/count),flush=True)
        assert steps==1014 and proof is not None
        file=MODELS/(arm+'.pth');torch.save(dict(delta_state=cnn.delta(net,'last_stage'),phase='new_case_lupus305',arm=arm,seed=42,epoch=6,updates=steps,imagenet_sha256=p['imagenet_sha256'],frozen_sha256=frozen),file)
        records[arm]=dict(checkpoint=file.relative_to(ROOT).as_posix(),rows=2702,unique_fit_images=len({v['sha256'] for v in rows}),epochs=6,steps=steps,initial_trainable_sha256=initial,frozen_initial_sha256=frozen,frozen_final_sha256=cnn.frozen_hash(net,'last_stage'),first_added_step=proof,epoch_logs=logs,query_forward_during_training=False)
        del net,opt;gc.collect();torch.cuda.empty_cache()
    for a,b in zip(records[CONTROL]['epoch_logs'],records[PRIMARY]['epoch_logs']):
        for k in ['base_image_stream_sha256','label_stream_sha256','order_sha256']:assert a[k]==b[k],k
    write(OUT/'training_report.json',records);files=[OUT/'training_report.json']
    for arm in ARMS:files.extend([ROOT/records[arm]['checkpoint'],ROOT/records[arm]['first_added_step']['path'],OUT/(arm+'_train_progress.json')])
    write(OUT/'training_locked.json',dict(locked_utc=utc(),protocol_sha256=sha(OUT/'protocol.json'),query_forward_started=False,artifacts_sha256={f.relative_to(ROOT).as_posix():sha(f) for f in files}))

def predict(p):
    for rel,h in read(OUT/'training_locked.json')['artifacts_sha256'].items():assert sha(ROOT/rel)==h
    records=read(OUT/'training_report.json');a=load(PREVIOUS/'predictions.npz')
    for arm in ARMS:
        ck=torch.load(ROOT/records[arm]['checkpoint'],map_location='cpu',weights_only=True);net=pool.repeat.fresh(p['imagenet_path'],42);net.load_state_dict(ck['delta_state'],strict=False);net=net.cuda().eval();state=cnn.state_sha(net.state_dict());values=[];status('query_inference305',arm=arm)
        with torch.inference_mode():
            for x,_ in DataLoader(fine.Images(p['query_rows']),batch_size=16,shuffle=False,num_workers=0):values.append(net(x.cuda()).float().cpu().numpy())
        raw=np.concatenate(values);assert cnn.state_sha(net.state_dict())==state;scores=raw[:,old.previous.INV];pred,diagnostic=pool.route(a['parent296_nll'],scores)
        a[arm]=pred;a[arm+'_native_logits']=raw;a[arm+'_scores']=scores
        for k,v in diagnostic.items():a[arm+'_'+k]=v
        del net;gc.collect();torch.cuda.empty_cache()
    f=OUT/'predictions.npz';np.savez_compressed(f,**a);write(OUT/'predictions_locked.json',dict(locked_utc=utc(),protocol_sha256=sha(OUT/'protocol.json'),metrics_started=False,artifacts_sha256={f.relative_to(ROOT).as_posix():sha(f)}))

def score(p):
    a=load(OUT/'predictions.npz');truth=a['truth'];refs={k:io.metrics(a[k],truth) for k in old.previous.REFS+[FULL,pool.CONTROL]};arms={}
    for arm in ARMS:
        pool.transfer.OUT=OUT;rec=pool.transfer.score_arm(p,arm);passed=rec['full_pass'];metric=rec['metrics'];keep={k:pool.keep_failures(metric,refs[k],k) for k in old.previous.REFS};uniform=pool.keep_failures(metric,refs[pool.CONTROL],'uniform294',require_LP=False)
        controls=[FULL]+([CONTROL] if arm==PRIMARY else []);comparisons={k:pool.keep_failures(metric,io.metrics(a[k],truth),k) for k in controls};blocks={};blocks_ok=True
        for i,file in enumerate(p['job']['cv_plans']):
            ix=load(ROOT/file)['holdout_indices'];candidate=io.metrics(a[arm][ix],truth[ix]);block=dict(images=len(ix),candidate=candidate,comparisons={})
            for k in old.previous.REFS+controls:
                b=io.metrics(a[k][ix],truth[ix]);ok=all(candidate[m]>=b[m]-1e-12 for m in ['accuracy','macro_f1']);blocks_ok=blocks_ok and ok;block['comparisons'][k]=dict(accuracy=b['accuracy'],macro_f1=b['macro_f1'],passed=ok)
            blocks[str(i)]=block
        rec.update(original_283_pass=passed,retained_failures=keep,versus_uniform294_failures=uniform,treatment_control_failures=comparisons,block_diagnostics=blocks,full_pass=passed and not(any(keep.values()) or uniform or any(comparisons.values())) and blocks_ok,raw_metrics=io.metrics(a[arm+'_scores'].argmax(1),truth),selected=None)
        write(OUT/(arm+'_results.json'),rec);arms[arm]=rec
    write(OUT/'results.json',dict(completed_utc=utc(),protocol_sha256=sha(OUT/'protocol.json'),primary=PRIMARY,controls=[FULL,CONTROL],query_images=1332,reference_metrics=refs,arms=arms,CNN_fits=2,CNN_updates=2028,train_tensor_views=32424,new_source_files=3,new_source_image_visits=18,query_forwards=2664,selected=None,promotion_eligible=False,global_5937_score_changed=False,serving_changed=False,research_registry_changed=False))
    status('awaiting_verification305');print({k:dict(accuracy=v['metrics']['accuracy'],macro_f1=v['metrics']['macro_f1'],full_pass=v['full_pass']) for k,v in arms.items()},flush=True)

if __name__=='__main__':
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False
    with threadpool_limits(limits=4):p=prepare();train(p);predict(p);score(p)
