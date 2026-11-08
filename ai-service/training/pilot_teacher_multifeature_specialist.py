"""Frozen ResNet versus energy-matched three-parent feature specialist, fold 0.

This pilot changes the feature representation, not a CNN, label or threshold.
All choices use original inner validation before outer/source inference.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
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

import run_teacher_dropout_specialist as latest
from common import ImageSample, ImageSampleDataset, build_model, evaluation_transform

ROOT, base, prior = latest.ROOT, latest.base, latest.prior
NAME = 'teacher_multifeature_specialist_fold0_seed42_20261024'
OUT = ROOT / 'ai-service/reports' / NAME
MODELS = ROOT / 'ai-service/candidates' / NAME
ARCHS = ['efficientnet_b0', 'convnext_tiny', 'resnet50']
DIMS = [1280, 768, 2048]
FOLD = 0
SOURCE = latest.OUT / 'transfer_check'
CONFIG = dict(C=.001, solver='lbfgs', multi_class='multinomial', max_iter=3000,
              tol=1e-7, random_state=42)


def utc(): return datetime.now(timezone.utc).isoformat()


def standardize(x, mean, scale):
    x = np.asarray(x, dtype=np.float32).copy()
    x -= mean; x /= scale
    return x


def fit_transformers(blocks):
    if len(blocks) != 3 or len({len(x) for x in blocks}) != 1:
        raise ValueError('Three aligned feature blocks required')
    scalers = [StandardScaler().fit(x) for x in blocks]
    z = [s.transform(x) for s, x in zip(scalers, blocks)]
    energy = lambda x: float(np.square(x.astype(float)).sum(1).mean())
    reference_energy, joint_energy = energy(z[2]), energy(np.column_stack(z))
    if min(reference_energy, joint_energy) <= 0: raise ValueError('Nonzero train feature energy required')
    factor = float(np.sqrt(reference_energy / joint_energy))
    return [s.mean_ for s in scalers], [s.scale_ for s in scalers], factor, reference_energy


def transform(blocks, means, scales, factor, joint):
    if len(blocks) != 3 or len({len(x) for x in blocks}) != 1:
        raise ValueError('Aligned blocks required')
    z = [standardize(x, m, s) for x, m, s in zip(blocks, means, scales)]
    return np.multiply(np.column_stack(z), factor, dtype=np.float32) if joint else z[2]


def probability(model, x):
    z = x @ model['coef'].T + model['intercept']; z -= z.max(1, keepdims=True)
    q = np.exp(z); return q/q.sum(1, keepdims=True)


def choose(decisions, truth):
    scores = {n:base.metrics(p, truth) for n,p in decisions.items()}
    trials = {n:dict(metrics=s, guard_failures=prior.failures(s, scores['current_policy'])) for n,s in scores.items()}
    treatment, control = scores['multi_feature'], scores['resnet_control']
    if treatment['macro_f1'] + 1e-12 < control['macro_f1']:
        trials['multi_feature']['guard_failures'].append('macro_f1_below_resnet_control')
    for name in ['resnet_control','current_policy']:
        if latest.previous.mean_focus(treatment) <= latest.previous.mean_focus(scores[name]) + 1e-12:
            trials['multi_feature']['guard_failures'].append('no_weak_mean_f1_gain_vs_'+name)
    passing = [n for n,t in trials.items() if not t['guard_failures']]
    selected = max(passing, key=lambda n:(scores[n]['macro_f1'], latest.previous.mean_focus(scores[n], 'recall'),
                    scores[n]['accuracy'], n=='current_policy', n=='resnet_control'))
    return dict(selected=selected, trials=trials)


def prepare():
    if (OUT/'protocol.json').exists():
        p = base.read(OUT/'protocol.json'); prior.verify(p); return p
    registry = base.read(ROOT/'ai-service/reports/active_research_track.json')
    assert registry['next_experiment'] is None
    parent = base.read(latest.OUT/'protocol.json'); prior.verify(parent)
    source_audit = base.read(SOURCE/'protocol.json'); prior.verify(source_audit)
    original = base.read(ROOT/parent['parent_protocol'])
    assert base.read(latest.OUT/'completion.json')['status']=='complete_verified_exploratory'
    transfer = base.read(ROOT/'ai-service/reports/original_eight_resnet_transfer_seed42/protocol.json')
    members = {r['architecture']:r for r in transfer['members'] if r['fold']==0}
    files = [Path(__file__), ROOT/'ai-service/tests/test_teacher_multifeature_specialist.py',
        latest.OUT/'protocol.json', latest.OUT/'completion.json', latest.OUT/'results.json', latest.OUT/'oof_decisions.json',
        latest.OUT/'fold_0/selection_locked.json', latest.OUT/'fold_0/inner_decisions.npz',
        SOURCE/'protocol.json', SOURCE/'results.json', SOURCE/'source_decisions.json', SOURCE/'independent_review.json',
        SOURCE/'fold_0_resnet_features.npz', ROOT/'ai-service/training/common.py']
    for row in members.values():
        assert base.sha(ROOT/row['path'])==row['sha256']; files.append(ROOT/row['path'])
    for role in ['train','inner_validation','outer_holdout']:
        files.append(prior.OUT/f'B_specialist/fold_0/{role}_features.npz')
    files.append(prior.MODELS/'fold_0/specialist.npz')
    for path,row in original['manifest'].items(): assert base.sha(ROOT/path)==row['sha256'], path
    for row in source_audit['rows']: assert base.sha(ROOT/row['path'])==row['sha256'],row['path']
    p = dict(name=NAME, registered_utc=utc(), fold=0, images=5937, classes=base.CLASSES,
        parent_protocol=parent['parent_protocol'], latest_protocol=(latest.OUT/'protocol.json').relative_to(ROOT).as_posix(),
        frozen_sha256={**parent['frozen_sha256'], **source_audit['frozen_sha256'], **{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},
        members=members, configuration=CONFIG,
        intervention='Replace ResNet-only 2048 features with concatenated B0(1280), ConvNeXt(768), ResNet(2048) features. Frozen original CNNs; no new backbone training.',
        scaling='Each block StandardScaler fits only 4043 original train rows. Multiply joint standardized features by sqrt(train mean squared norm of ResNet / train mean squared norm of concatenation). Match total train feature energy, fixed before validation. No tuned parent weights.',
        control='Refit old five-way unweighted ResNet logistic C=.001 on exactly its original standardized float32 training cache; compare coefficients with saved B head. The joint head has more coefficients; representation and associated dimension are the intervention.',
        targets=['Lupus','Psoriasis','Tinea','Eczema','Other'],
        reference='Latest validation-selected dropout policy. Inner baseline uses saved meta-held/inner decisions plus its frozen fold choice; outer/source baseline uses path-keyed completed predictions.',
        routing='Original weak4/Other >=.8 route, exact current SkinCancer mask; no threshold search.',
        selection='Strict original per-weak Recall/F1 and total Accuracy/MacroF1 guards versus latest policy. Joint additionally MacroF1>=ResNet control and mean weak F1 strictly higher than both control and current. Rank MacroF1, weak mean Recall, Accuracy, ties current then control. Lock before outer/source feature extraction.',
        scope='One fixed fold-0 pilot, 4043 train / 718 inner / 1176 outer. Descriptive 1709 known source images evaluated by this one fold only. No new 5937 score and no five-system source average. Expand only under a separate registered full-CV follow-up if this validation selection accepts joint features.',
        limitations=parent['limitations']+[
            'Fold0 inner contains no SCIN Lupus. This pilot cannot establish improved SCIN Lupus or stability across folds/seeds.',
            'Raw latent features may retain cues lost in final probabilities, but complementary information or improved disease accuracy is a hypothesis, not a guarantee.',
            'One original CNN seed, previously studied inner/outer/source labels. No fresh independent clinical test.',
            'Feature dimension and number of head coefficients increase; energy matching controls overall feature scale but not feature correlations or all forms of regularization.'],
        references=['https://openaccess.thecvf.com/content_cvpr_workshops_2014/W15/html/Razavian_CNN_Features_Off-the-Shelf_2014_CVPR_paper.html',
                    'https://scikit-learn.org/1.3/modules/generated/sklearn.linear_model.LogisticRegression.html'],
        new_CNN_fits=0, serving_changed=False, global_5937_score_changed=False)
    OUT.mkdir(parents=True, exist_ok=True); base.write(OUT/'protocol.json', p)
    base.write(OUT/'research_registry_before.json', registry)
    registry['next_experiment']=OUT.relative_to(ROOT).as_posix(); registry['next_experiment_status']='registered_three_parent_feature_pilot'
    base.write(ROOT/'ai-service/reports/active_research_track.json', registry)
    return p


class Extractor:
    def __init__(self, p, architecture, role):
        checkpoint = torch.load(ROOT/p['members'][architecture]['path'], map_location='cpu', weights_only=False)
        assert checkpoint['classes']==base.CLASSES and checkpoint['architecture']==architecture
        # Reproduce the existing parent artifacts' member/role arithmetic.
        self.device = 'cpu' if architecture=='efficientnet_b0' and role!='source_transfer' else 'cuda'
        self.batch_size = 32 if self.device=='cpu' else 16
        self.model = build_model(architecture,8,False).to(self.device).eval().requires_grad_(False)
        self.model.load_state_dict(checkpoint['model_state_dict']); self.slot=[]
        self.last = self.model.classifier[1] if architecture=='efficientnet_b0' else self.model.classifier[2]
        self.handle = self.last.register_forward_pre_hook(lambda module, args:self.slot.append(args[0]))

    def infer(self, rows, label):
        samples=[ImageSample(ROOT/r['path'],0,r['sha256'],r['group']) for r in rows]
        loader=DataLoader(ImageSampleDataset(samples,evaluation_transform()),batch_size=self.batch_size,shuffle=False,num_workers=0,pin_memory=self.device=='cuda')
        xx=[];qq=[];started=time.monotonic()
        with torch.inference_mode():
            for i,(images,_) in enumerate(loader):
                logits=self.model(images.to(self.device,non_blocking=True)); assert len(self.slot)==1
                features=self.slot.pop()
                assert torch.equal(logits,torch.nn.functional.linear(features,self.last.weight,self.last.bias))
                xx.append(features.cpu().numpy());qq.append(logits.softmax(1).cpu().numpy())
                if (i+1)%64==0:
                    base.write(OUT/'status.json',dict(state='extracting',role=label,batches=i+1,images=sum(len(v) for v in xx),seconds=time.monotonic()-started))
                    print(dict(role=label,images=sum(len(v) for v in xx)),flush=True)
        assert not self.slot
        return np.concatenate(xx),np.concatenate(qq)

    def close(self):
        self.handle.remove();del self.model;torch.cuda.empty_cache()


def expected_probability(role, architecture, rows):
    if role=='train': return None
    if role=='inner_validation':
        with np.load(base.fold_dir(0)/'validation_predictions.npz',allow_pickle=False) as z:
            lookup={path:i for i,path in enumerate(z['paths'].tolist())}
            return z[architecture][[lookup[r['path']] for r in rows]]
    if role=='outer_holdout':
        original={r['path']:r for r in base.read(base.fold_dir(0)/'test_predictions.json')}
        return np.array([original[r['path']]['probabilities'][architecture] for r in rows])
    path=ROOT/f'ai-service/reports/original_eight_resnet_transfer_seed42/fold_0_{architecture}.npz'
    with np.load(path,allow_pickle=False) as z:
        lookup={path:i for i,path in enumerate(z['paths'].tolist())}
        return z['probabilities'][[lookup[r['path']] for r in rows]]


def blocks(p, role, rows):
    output=[]
    for architecture,dim in zip(ARCHS,DIMS):
        if architecture=='resnet50':
            if role=='source_transfer':
                with np.load(SOURCE/'fold_0_resnet_features.npz',allow_pickle=False) as z:
                    index={path:i for i,path in enumerate(z['paths'].tolist())}
                    features=z['features'][[index[r['path']] for r in rows]]
            else:
                paths,features,_=latest.cache.cached(0,role,base.read(ROOT/p['parent_protocol']))
                assert paths==[r['path'] for r in rows]
        else:
            path=OUT/f'{role}_{architecture}_features.npz'
            if path.exists():
                with np.load(path,allow_pickle=False) as z:
                    assert z['paths'].tolist()==[r['path'] for r in rows]
                    stored=z['protocol_sha256'].item()
                    compatible=(architecture=='convnext_tiny' and role=='train' and stored==p.get('compatible_convnext_train_protocol_sha256'))
                    assert stored in [base.sha(OUT/'protocol.json'),p.get('training_protocol_sha256')] or compatible
                    features=z['features'].copy();prob=z['probabilities'].copy()
            else:
                extractor=Extractor(p,architecture,role)
                try:features,prob=extractor.infer(rows,role+'_'+architecture)
                finally:extractor.close()
                np.savez_compressed(path,paths=[r['path'] for r in rows],features=features,probabilities=prob,
                                    protocol_sha256=base.sha(OUT/'protocol.json'),started_after_protocol=True)
            expected=expected_probability(role,architecture,rows)
            if expected is not None:
                error=float(np.abs(prob-expected).max())
                same_arithmetic=not (role=='outer_holdout' and architecture=='efficientnet_b0')
                if same_arithmetic:assert error<2e-6,(role,architecture,error)
                base.write(OUT/f'{role}_{architecture}_verification.json',dict(images=len(rows),maximum_probability_error=error,
                    historical_arithmetic_matches=same_arithmetic,
                    comparison='Strict historical identity' if same_arithmetic else 'CPU canonical features versus historical GPU outputs; independent CPU forward check required',
                    cache_sha256=base.sha(path)))
        assert features.shape==(len(rows),dim) and np.isfinite(features).all()
        output.append(features)
    return output


def run(p):
    assert not (OUT/'results.json').exists(),'Preserve completed pilot'
    if (OUT/'selection_locked.json').exists():
        evaluate_locked(p);return
    parent=base.read(ROOT/p['parent_protocol'])
    train_rows=prior.role_rows(parent,0,'train'); inner_rows=prior.role_rows(parent,0,'inner_validation')
    train=blocks(p,'train',train_rows); inner=blocks(p,'inner_validation',inner_rows)
    means,scales,factor,energy=fit_transformers(train)
    target=latest.fiveway(np.array([base.CLASSES.index(r['label']) for r in train_rows]))
    MODELS.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(MODELS/'transform.npz',factor=factor,**{f'mean_{i}':m for i,m in enumerate(means)},**{f'scale_{i}':s for i,s in enumerate(scales)})
    with np.load(latest.OUT/'fold_0/inner_decisions.npz',allow_pickle=False) as z:
        assert z['paths'].tolist()==[r['path'] for r in inner_rows]
        choice=base.read(latest.OUT/'fold_0/selection_locked.json')['selected'];current=z[choice].copy();truth=z['truth'].copy()
    heads={};decisions=dict(current_policy=current);reports={}
    for name,joint in [('resnet_control',False),('multi_feature',True)]:
        x=transform(train,means,scales,factor,joint)
        with warnings.catch_warnings():
            warnings.simplefilter('error',ConvergenceWarning)
            head=LogisticRegression(**CONFIG).fit(x,target)
        model=dict(coef=head.coef_,intercept=head.intercept_,classes=head.classes_);heads[name]=model
        np.savez_compressed(MODELS/f'{name}.npz',**model)
        pp=probability(model,transform(inner,means,scales,factor,joint))
        decisions[name]=prior.route(current,pp)
        np.savez_compressed(OUT/f'{name}_inner_probabilities.npz',paths=[r['path'] for r in inner_rows],probability=pp)
        reports[name]=dict(dimensions=x.shape[1],train_images=len(x),train_mean_squared_norm=float(np.square(x.astype(float)).sum(1).mean()),iterations=head.n_iter_.tolist())
    with np.load(prior.MODELS/'fold_0/specialist.npz',allow_pickle=False) as old:
        error=max(float(np.abs(heads['resnet_control']['coef']-old['coef']).max()),float(np.abs(heads['resnet_control']['intercept']-old['intercept']).max()))
        assert error<1e-10,error
    reports['control_coefficient_error']=error; reports['joint_factor']=factor; reports['reference_train_energy']=energy
    base.write(OUT/'training_report.json',reports)
    lock=choose(decisions,truth)
    lock.update(locked_utc=utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
        artifacts_sha256={x.relative_to(ROOT).as_posix():base.sha(x) for x in [*MODELS.glob('*.npz'),*OUT.glob('*inner_probabilities.npz'),OUT/'training_report.json']})
    base.write(OUT/'selection_locked.json',lock)
    print(dict(selected=lock['selected'],joint_failures=lock['trials']['multi_feature']['guard_failures']),flush=True)
    evaluate_locked(p)


def evaluate_locked(p):
    assert not (OUT/'results.json').exists(),'Preserve completed evaluation'
    parent=base.read(ROOT/p['parent_protocol']);lock=base.read(OUT/'selection_locked.json')
    assert lock['protocol_sha256']==p.get('training_protocol_sha256',base.sha(OUT/'protocol.json'))
    for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
    with np.load(MODELS/'transform.npz',allow_pickle=False) as z:
        factor=float(z['factor']);means=[z[f'mean_{i}'].copy() for i in range(3)];scales=[z[f'scale_{i}'].copy() for i in range(3)]
    heads={}
    for name in ['resnet_control','multi_feature']:
        with np.load(MODELS/f'{name}.npz',allow_pickle=False) as z:heads[name]={key:z[key].copy() for key in z.files}
    error=base.read(OUT/'training_report.json')['control_coefficient_error']
    output=[];scores={};started=utc()
    old_outer={r['path']:r for r in base.read(latest.OUT/'oof_decisions.json')}
    source_protocol=base.read(SOURCE/'protocol.json');old_source={r['path']:r for r in base.read(SOURCE/'source_decisions.json')}
    for role,rows in [('outer_holdout',prior.role_rows(parent,0,'outer_holdout')),('source_transfer',source_protocol['rows'])]:
        raw=blocks(p,role,rows);truth=np.array([base.CLASSES.index(r['label']) for r in rows])
        current=np.array([old_outer[r['path']]['predictions']['validation_selected'] if role=='outer_holdout' else old_source[r['path']]['predictions']['validation_selected'][0] for r in rows])
        dd=dict(current_policy=current)
        for name,joint in [('resnet_control',False),('multi_feature',True)]:
            pp=probability(heads[name],transform(raw,means,scales,factor,joint));dd[name]=prior.route(current,pp)
            np.savez_compressed(OUT/f'{name}_{role}_probabilities.npz',paths=[r['path'] for r in rows],probability=pp)
        dd['validation_selected']=dd[lock['selected']]
        for pred in dd.values():assert np.array_equal(pred==5,current==5)
        if role=='outer_holdout':
            slices={'original_outer':list(range(len(rows)))}
        else:
            index={r['path']:i for i,r in enumerate(rows)}
            slices={name:[index[path] for path in items] for name,items in source_protocol['subsets'].items()}
        for name,ids in slices.items():
            scores[name]=dict(images=len(ids),methods={n:base.metrics(pred[ids],truth[ids]) for n,pred in dd.items()})
        output.extend(dict(**r,role=role,predictions={n:int(pred[i]) for n,pred in dd.items()}) for i,r in enumerate(rows))
    base.write(OUT/'held_decisions.json',output)
    result=dict(status='complete_exploratory_three_parent_feature_pilot',fold=0,selected=lock['selected'],
        validation=lock['trials'],held=scores,held_started_utc=started,completed_utc=utc(),
        protocol_sha256=base.sha(OUT/'protocol.json'),selection_sha256=base.sha(OUT/'selection_locked.json'),
        training_protocol_sha256=lock['protocol_sha256'],
        new_CNN_fits=0,global_5937_score_changed=False,serving_changed=False,limitations=p['limitations'])
    base.write(OUT/'results.json',result);prior.verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),
        control_coefficient_error=error,selection_locked_before_outer_sources=True,train_only_scaling=True,
        feature_cache_sha256={x.relative_to(ROOT).as_posix():base.sha(x) for x in OUT.glob('*_features.npz')}))
    print({k:{n:{m:s[m] for m in ['accuracy','macro_f1']} for n,s in v['methods'].items()} for k,v in scores.items()},flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    torch.set_num_threads(2)
    with threadpool_limits(limits=1):
        p=prepare()
        if not args.prepare_only:run(p)


if __name__=='__main__':main()
