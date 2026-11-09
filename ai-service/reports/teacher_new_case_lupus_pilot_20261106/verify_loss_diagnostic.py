from pathlib import Path
import importlib.util,hashlib
import numpy as np
import torch
from torch.nn import functional as F
from torch.utils.data import DataLoader
ROOT=Path('D:/DermAI Clinic');OUT=ROOT/'ai-service/reports/teacher_new_case_lupus_pilot_20261106'
s=importlib.util.spec_from_file_location('producer305',OUT/'run_experiment.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
read,write,sha=m.read,m.write,m.sha
def independent_metrics(y,p):
 cm=np.zeros((8,8),int);np.add.at(cm,(y,p),1);tp=cm.diagonal();support=cm.sum(1);pred=cm.sum(0)
 prec=np.divide(tp,pred,out=np.zeros(8,float),where=pred>0);rec=np.divide(tp,support,out=np.zeros(8,float),where=support>0);f1=np.divide(2*tp,support+pred,out=np.zeros(8,float),where=support+pred>0)
 return cm,tp.sum()/cm.sum(),f1.mean(),prec,rec,f1
def main():
 p=read(OUT/'protocol.json');r=read(OUT/'results.json');t=read(OUT/'training_report.json');a=m.load(OUT/'predictions.npz')
 for rel,h in p['frozen_sha256'].items():assert sha(ROOT/rel)==h,rel
 for name in ['training_locked.json','predictions_locked.json']:
  for rel,h in read(OUT/name)['artifacts_sha256'].items():assert sha(ROOT/rel)==h,rel
 assert read(OUT/'training_locked.json')['locked_utc']<=read(OUT/'predictions_locked.json')['locked_utc']<=r['completed_utc']
 torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False
 proofs={}
 for arm in m.ARMS:
  scores=a[arm+'_native_logits'][:,m.old.previous.INV].astype(np.float64);np.testing.assert_array_equal(scores,a[arm+'_scores']);proposal=scores.argmax(1);parent=a['parent296_nll'];margin=scores[np.arange(len(parent)),proposal]-scores[np.arange(len(parent)),parent]
  mask=(proposal!=parent)&(proposal!=5)&(parent!=5)&(np.isin(proposal,[3,4,6])|np.isin(parent,[3,4,6]))&(margin>np.log(2))
  np.testing.assert_array_equal(np.where(mask,proposal,parent),a[arm]);np.testing.assert_array_equal(a[arm]==5,parent==5)
  cm,acc,mf,pr,rec,f1=independent_metrics(a['truth'],a[arm]);reported=r['arms'][arm]['metrics'];np.testing.assert_array_equal(cm,reported['confusion_matrix']);assert abs(acc-reported['accuracy'])<1e-12 and abs(mf-reported['macro_f1'])<1e-12
  for i,c in enumerate(p['classes']):
   for key,value in [('precision',pr[i]),('recall',rec[i]),('f1',f1[i])]:assert abs(reported['per_class'][c][key]-value)<1e-12
  net=m.pool.repeat.fresh(p['imagenet_path'],42).cuda().eval();opt=torch.optim.AdamW([dict(params=[v for n,v in net.named_parameters() if n.startswith('classifier.')],lr=2e-4),dict(params=[v for n,v in net.named_parameters() if n.startswith('features.7.')],lr=5e-5)],weight_decay=.0002)
  rows=p['training_rows_by_arm'][arm];order=np.random.default_rng(421101).permutation(len(rows));loader=DataLoader(m.cnn.SeededDataset(m.fine.Images(rows,True),order.tolist(),1101),batch_size=16,shuffle=False,num_workers=0)
  proof=t[arm]['first_added_step'];seen=0
  for batchid,(x,y) in enumerate(loader):
   opt.zero_grad(set_to_none=True)
   with torch.autocast('cuda',dtype=torch.bfloat16):raw=net(x.cuda())
   z=raw.float();loss=-F.log_softmax(z,1)[torch.arange(len(y),device='cuda'),y.cuda()].mean();loss.backward();norm=torch.nn.utils.clip_grad_norm_([v for v in net.parameters() if v.requires_grad],2.);opt.step();seen+=1
   if batchid==proof['batch']:
    assert hashlib.sha256(x.numpy().tobytes()+y.numpy().tobytes()).hexdigest()==proof['input_sha256']
    assert any(order[batchid*16:batchid*16+len(y)]>=2699)
    checkpoint=torch.load(ROOT/proof['path'],map_location='cpu',weights_only=True);np.testing.assert_array_equal(z.detach().cpu().numpy(),checkpoint['logits'].numpy());delta=m.cnn.delta(net,'last_stage');maximum=max(float((delta[k]-checkpoint['delta_state'][k]).abs().max()) for k in delta)
    print(dict(arm=arm, parameter_max_abs=maximum, formula_loss=float(loss), saved_loss=proof['loss'], loss_abs_difference=abs(float(loss)-proof['loss'])),flush=True)
    assert maximum<2e-7
    assert abs(float(F.cross_entropy(z,y.cuda()))-proof['loss'])<1e-7
    proofs[arm]=dict(first_added_step_replayed_prefix_updates=seen,parameter_max_abs=maximum,gradient_norm=float(norm),metrics_recomputed=True);break
  assert seen==proof['prefix_updates'];del net,opt;torch.cuda.empty_cache()
 for one,two in zip(t[m.PRIMARY]['epoch_logs'],t[m.CONTROL]['epoch_logs']):
  for key in ['base_image_stream_sha256','label_stream_sha256','order_sha256']:assert one[key]==two[key]
 write(OUT/'verification_diagnostic.json',dict(status='PASS',checked_utc=m.utc(),protocol_sha256=sha(OUT/'protocol.json'),source_and_protected_hashes_unchanged=True,checks=proofs,both_first_added_source_updates_independently_replayed=True,all_six_base_streams_match_across_arms=True,clinical_review_performed=False,full_training_independently_replayed=False,query_native_forwards_independently_repeated=False,selected=None))
 print('PASS: provenance, source-containing updates, base streams and independent routing/metrics')
if __name__=='__main__':main()
