"""Spatial input representation ablation: center crop versus five-view pooling.

Frozen original ResNet, equal-dimensional five-way heads, one image per row.
All crop geometry is fixed before validation, with exact cancer mask routing.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import time
import warnings

import numpy as np
import torch
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from torch.utils.data import DataLoader
from torchvision import transforms

from common import ImageSample,ImageSampleDataset,build_model,IMAGENET_MEAN,IMAGENET_STD
import pilot_teacher_balanced_pairs as previous

base,prior,latest,features=previous.base,previous.prior,previous.latest,previous.features
ROOT=previous.ROOT
NAME='teacher_spatial_multicrop_fold0_seed42_20261024'
OUT=ROOT/'ai-service/reports'/NAME
MODELS=ROOT/'ai-service/candidates'/NAME
METHODS=['current_policy','center_control','five_view']


class FiveViews:
    def __init__(self):
        self.resize=transforms.Resize(320,interpolation=transforms.InterpolationMode.BILINEAR,antialias=True)
        self.crop=transforms.FiveCrop(224)
        self.tensor=transforms.Compose([transforms.ToTensor(),transforms.Normalize(IMAGENET_MEAN,IMAGENET_STD)])

    def __call__(self,image):
        return torch.stack([self.tensor(view) for view in self.crop(self.resize(image))])


def pool_views(hidden,images):
    if hidden.ndim!=2 or hidden.shape[0]!=images*5:
        raise ValueError('Exactly five consecutive feature rows per original image required')
    return hidden.reshape(images,5,-1).mean(1)


def choose(decisions,truth):
    scores={n:base.metrics(d,truth) for n,d in decisions.items()}
    trials={n:dict(metrics=s,guard_failures=prior.failures(s,scores['current_policy'])) for n,s in scores.items()}
    treatment=scores['five_view']
    if treatment['macro_f1']+1e-12<scores['center_control']['macro_f1']:
        trials['five_view']['guard_failures'].append('macro_f1_below_center_control')
    for name in ['center_control','current_policy']:
        if latest.previous.mean_focus(treatment)<=latest.previous.mean_focus(scores[name])+1e-12:
            trials['five_view']['guard_failures'].append('no_weak_mean_f1_gain_vs_'+name)
    passing=[n for n in METHODS if not trials[n]['guard_failures']]
    selected=max(passing,key=lambda n:(scores[n]['macro_f1'],latest.previous.mean_focus(scores[n],'recall'),
                    scores[n]['accuracy'],n=='current_policy',n=='center_control'))
    return dict(selected=selected,trials=trials)


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');prior.verify(p);return p
    registry=base.read(ROOT/'ai-service/reports/active_research_track.json');assert registry['next_experiment'] is None
    old=base.read(previous.OUT/'protocol.json');prior.verify(old)
    assert base.read(previous.OUT/'completion.json')['status']=='complete_verified_pilot_not_selected'
    checkpoint=prior.checkpoint(0)
    files=[Path(__file__),ROOT/'ai-service/tests/test_teacher_spatial_multicrop.py',checkpoint,
        previous.OUT/'protocol.json',previous.OUT/'completion.json',previous.OUT/'independent_review.json',
        prior.MODELS/'fold_0/specialist.npz',ROOT/'ai-service/training/pilot_teacher_balanced_pairs.py',
        ROOT/'ai-service/training/pilot_teacher_pairwise_specialists.py',ROOT/'ai-service/training/common.py']
    p=dict(name=NAME,registered_utc=features.utc(),fold=0,classes=base.CLASSES,parent_protocol=old['parent_protocol'],
        configuration=features.CONFIG,checkpoint=checkpoint.relative_to(ROOT).as_posix(),
        frozen_sha256={**old['frozen_sha256'],**{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},
        intervention='Change image representation: original Resize256/CenterCrop224 cached ResNet2048 versus new Resize(short side320,bilinear,antialiasTrue)/FiveCrop224 fixed top-left,top-right,bottom-left,bottom-right,center. Same RGB/ImageNet normalization and original frozen ResNet. Mean five latent2048 vectors BEFORE head/scaler. Both final heads2048->5, same coefficient count.',
        fitting='Each representation has its own StandardScaler fit only4043train original-image rows. Multiply standardized five-view block by sqrt(train squared-norm energy of standardized center / five-view). Same unweighted multinomial C=.001, no new labels, no pair-loss, no sampling/epoch/grid. Refit center head and require old five-way specialist parameter identity within1e-10.',
        arithmetic='Original ResNet eval, FP32 tensors, cuDNN TF32 allowed, CUDA matmul TF32 off. Batch4 original images flattened image-major to20 crops (last batch shorter). Mean uses torch float32 reduction. Cache mean feature per image plus5x8 parent view probabilities; no across-image pooling.',
        image_accounting='4043train+718inner+1176outer=5937distinct development photos; source1709known photos separate. Five crops are dependent views, NOT5xnew independent images or extra patient cases. New crop forwards total38230 if all roles complete; no new CNN parameter updates.',
        routing='Same original five-way Lupus/Psoriasis/Tinea/Eczema/Other route, threshold>=.8, Other abstains. Only existing weak4 calls change and exact SkinCancer mask fixed.',
        selection='Compare current,center,fiveview on718inner. Same strict perweakRecall/F1,totalAccuracy/MacroF1,weakPrecision and otherRecall guards. Fiveview also MF>=center and meanweakF1 strictly above both current/center. Rank MF,meanweakRecall,Accuracy,ties current then center. Lock train/inner caches, heads and choice before new outer/source extraction. No scale/position/threshold search.',
        scope='Onefold exploratory pilot; new5937global score requires a separately frozen fivefold confirmation. Source slices remain historical and descriptive.',
        limitations=old['limitations']+[
            'This changes crop scale/position and pooling together, not an isolated test of each subcomponent. Fixed crops do not detect or segment lesions and can include healthy skin or omit a lesion.',
            'Frozen CNN weights are unchanged. This learns a head over new spatial features, not end-to-end CNN fine-tuning.',
            'Singlefold/seed, repeatedly inspected cohorts, no new patient test. Five dependent views increase inference cost but not independent sample size.',
            'AlexNet2012 averaged softmax predictions from10views including flips; this uses5mean latent vectors and a new head with Resize320. Only the general multi-view idea is borrowed, not a paper reproduction.'],
        references=['https://docs.pytorch.org/vision/0.20/generated/torchvision.transforms.FiveCrop.html',
            'https://papers.neurips.cc/paper_files/paper/2012/file/c399862d3b9d6b76c8436e924a68c45b-Paper.pdf'],
        runtime=dict(torch=torch.__version__,gpu=torch.cuda.get_device_name(0)),
        new_CNN_fits=0,new_backbones=0,global_5937_score_changed=False,serving_changed=False)
    OUT.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p);base.write(OUT/'research_registry_before.json',registry)
    registry['next_experiment']=OUT.relative_to(ROOT).as_posix();registry['next_experiment_status']='registered_spatial_multicrop_fold0'
    base.write(ROOT/'ai-service/reports/active_research_track.json',registry)
    return p


def extract(p,role,rows):
    path=OUT/f'{role}_five_view_features.npz'
    if path.exists():
        with np.load(path,allow_pickle=False) as z:
            assert z['paths'].tolist()==[r['path'] for r in rows]
            assert z['protocol_sha256'].item()==base.sha(OUT/'protocol.json')
            result=z['features'].copy()
        assert result.shape==(len(rows),2048) and np.isfinite(result).all()
        return result
    saved=torch.load(ROOT/p['checkpoint'],map_location='cpu',weights_only=False)
    assert saved['architecture']=='resnet50' and saved['classes']==base.CLASSES
    model=build_model('resnet50',8,False).cuda().eval().requires_grad_(False)
    model.load_state_dict(saved['model_state_dict'])
    backbone=torch.nn.Sequential(*list(model.children())[:-1]).eval()
    samples=[ImageSample(ROOT/r['path'],0,r['sha256'],r['group']) for r in rows]
    loader=DataLoader(ImageSampleDataset(samples,FiveViews()),batch_size=4,shuffle=False,num_workers=0,pin_memory=True)
    blocks=[];qq=[];started=features.utc();tick=time.monotonic()
    with torch.inference_mode():
        for i,(views,_) in enumerate(loader):
            n=len(views);hidden=backbone(views.flatten(0,1).cuda(non_blocking=True)).flatten(1)
            pooled=pool_views(hidden,n);prob=model.fc(hidden).softmax(1).reshape(n,5,8)
            blocks.append(pooled.cpu().numpy());qq.append(prob.cpu().numpy())
            if (i+1)%32==0 or (i+1)==len(loader):
                state=dict(state='extracting',role=role,images=sum(len(v) for v in blocks),total=len(rows),
                    crop_forwards=sum(len(v) for v in blocks)*5,seconds=time.monotonic()-tick,updated_utc=features.utc())
                base.write(OUT/'status.json',state);print(state,flush=True)
    result=np.concatenate(blocks);probability=np.concatenate(qq)
    assert result.shape==(len(rows),2048) and np.isfinite(result).all()
    temporary=path.with_suffix('.tmp.npz')
    np.savez_compressed(temporary,paths=[r['path'] for r in rows],features=result,view_probabilities=probability,
        protocol_sha256=base.sha(OUT/'protocol.json'),started_utc=started,completed_utc=features.utc())
    temporary.replace(path)
    del model,backbone;torch.cuda.empty_cache()
    return result


def center(role,rows):return previous.parent.cached(role,rows)


def representation(x,model):
    return np.multiply(features.standardize(x,model['mean'],model['scale']),model['factor'],dtype=np.float32)


def train_and_lock(p):
    parent=base.read(ROOT/p['parent_protocol']);train=prior.role_rows(parent,0,'train');inner=prior.role_rows(parent,0,'inner_validation')
    xx=[center('train',train),extract(p,'train',train)]
    vv=[center('inner_validation',inner),extract(p,'inner_validation',inner)]
    scalers=[StandardScaler().fit(x) for x in xx];zz=[s.transform(x) for s,x in zip(scalers,xx)]
    energy=[float(np.square(z.astype(float)).sum(1).mean()) for z in zz];factors=[1.,float(np.sqrt(energy[0]/energy[1]))]
    truth=latest.fiveway(np.array([base.CLASSES.index(r['label']) for r in train]))
    with np.load(latest.OUT/'fold_0/inner_decisions.npz',allow_pickle=False) as z:
        assert z['paths'].tolist()==[r['path'] for r in inner]
        current=z[base.read(latest.OUT/'fold_0/selection_locked.json')['selected']].copy();yy=z['truth'].copy()
    MODELS.mkdir(parents=True,exist_ok=True);dd=dict(current_policy=current);report={};probabilities={}
    for i,name in enumerate(['center_control','five_view']):
        model=dict(mean=scalers[i].mean_,scale=scalers[i].scale_,factor=factors[i])
        x=representation(xx[i],model)
        with warnings.catch_warnings():
            warnings.simplefilter('error',ConvergenceWarning)
            fit=LogisticRegression(**p['configuration']).fit(x,truth)
        model.update(coef=fit.coef_,intercept=fit.intercept_,classes=fit.classes_)
        np.savez_compressed(MODELS/f'{name}.npz',**model)
        q=features.probability(model,representation(vv[i],model));probabilities[name]=q;dd[name]=prior.route(current,q)
        report[name]=dict(images=len(x),dimensions=x.shape[1],head_coefficients=int(model['coef'].size+model['intercept'].size),
            iterations=fit.n_iter_.tolist(),train_mean_squared_norm=float(np.square(x.astype(float)).sum(1).mean()),factor=factors[i])
        if name=='center_control':
            with np.load(prior.MODELS/'fold_0/specialist.npz',allow_pickle=False) as old:
                error=max(float(np.abs(model[k]-old[k]).max()) for k in ['coef','intercept'])
            assert error<1e-10,error
            report['center_parameter_error']=error
    base.write(OUT/'training_report.json',report);lock=choose(dd,yy)
    np.savez_compressed(OUT/'inner_decisions.npz',paths=[r['path'] for r in inner],truth=yy,
        center_probability=probabilities['center_control'],five_view_probability=probabilities['five_view'],**dd)
    files=[*MODELS.glob('*.npz'),OUT/'training_report.json',OUT/'inner_decisions.npz',
           OUT/'train_five_view_features.npz',OUT/'inner_validation_five_view_features.npz']
    lock.update(locked_utc=features.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
        artifacts_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in files})
    base.write(OUT/'selection_locked.json',lock)
    print(dict(selected=lock['selected'],failures={n:t['guard_failures'] for n,t in lock['trials'].items()}),flush=True)


def evaluate(p):
    assert not (OUT/'results.json').exists(),'Preserve completed pilot'
    lock=base.read(OUT/'selection_locked.json');assert lock['protocol_sha256']==base.sha(OUT/'protocol.json')
    for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
    started=features.utc();parent=base.read(ROOT/p['parent_protocol']);source=base.read(features.SOURCE/'protocol.json')
    original={r['path']:r for r in base.read(latest.OUT/'oof_decisions.json')};external={r['path']:r for r in base.read(features.SOURCE/'source_decisions.json')}
    heads={}
    for name in ['center_control','five_view']:
        with np.load(MODELS/f'{name}.npz',allow_pickle=False) as z:heads[name]={k:z[k].copy() for k in z.files}
    output=[];scores={}
    for role,rows in [('outer_holdout',prior.role_rows(parent,0,'outer_holdout')),('source_transfer',source['rows'])]:
        yy=np.array([base.CLASSES.index(r['label']) for r in rows]);current=np.array([original[r['path']]['predictions']['validation_selected'] if role=='outer_holdout' else external[r['path']]['predictions']['validation_selected'][0] for r in rows])
        dd=dict(current_policy=current)
        for name,x in [('center_control',center(role,rows)),('five_view',extract(p,role,rows))]:
            q=features.probability(heads[name],representation(x,heads[name]));dd[name]=prior.route(current,q)
            np.savez_compressed(OUT/f'{role}_{name}_probabilities.npz',paths=[r['path'] for r in rows],probability=q)
        dd['validation_selected']=dd[lock['selected']]
        index={r['path']:i for i,r in enumerate(rows)};slices={'original_outer':list(index)} if role=='outer_holdout' else source['subsets']
        for name,paths in slices.items():
            ids=[index[path] for path in paths];scores[name]=dict(images=len(ids),methods={n:base.metrics(d[ids],yy[ids]) for n,d in dd.items()})
        output.extend(dict(**r,role=role,predictions={n:int(d[i]) for n,d in dd.items()}) for i,r in enumerate(rows))
    base.write(OUT/'held_decisions.json',output)
    r=dict(status='complete_exploratory_spatial_multicrop_pilot',fold=0,selected=lock['selected'],validation=lock['trials'],held=scores,
        held_started_utc=started,completed_utc=features.utc(),head_fits=2,new_CNN_fits=0,crop_forwards=38230,
        protocol_sha256=base.sha(OUT/'protocol.json'),selection_sha256=base.sha(OUT/'selection_locked.json'),
        global_5937_score_changed=False,serving_changed=False,limitations=p['limitations'])
    base.write(OUT/'results.json',r);prior.verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),
        feature_cache_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in OUT.glob('*_five_view_features.npz')}))
    base.write(OUT/'status.json',dict(state='evaluation_complete_awaiting_independent_review',selected=lock['selected'],updated_utc=features.utc()))
    print(dict(outer={n:{k:s[k] for k in ['accuracy','macro_f1']} for n,s in scores['original_outer']['methods'].items()}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    torch.set_num_threads(2);torch.backends.cudnn.allow_tf32=True;torch.backends.cuda.matmul.allow_tf32=False
    with threadpool_limits(limits=1):
        p=prepare()
        if args.prepare_only:return
        assert not (OUT/'results.json').exists(),'Preserve completed pilot'
        if not (OUT/'selection_locked.json').exists():
            assert not (OUT/'training_report.json').exists(),'Audit partial head fit before resuming'
            train_and_lock(p)
        evaluate(p)


if __name__=='__main__':main()
