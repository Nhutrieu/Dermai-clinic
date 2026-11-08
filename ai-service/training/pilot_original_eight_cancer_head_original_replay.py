"""Fixed PAD binary head versus same head with original eight train replay."""
import argparse
import warnings
from collections import Counter

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from common import CLASSES,save_json,sha256_file
from evaluate_scene_grouped_oof_ensemble import score
import pilot_original_eight_frozen_cancer_head as prior
import audit_original_eight_cancer_head_disagreements as audit

ROOT=prior.ROOT
OUT=ROOT/'ai-service/reports/original_eight_cancer_head_original_replay_fold0_seed42'
MODELS=ROOT/'ai-service/candidates/original_eight_cancer_head_original_replay_fold0_seed42'
BRANCHES=('control','replay')
METHODS=('old_classwise','control_cancer25','replay_cancer25')


def original_weights(rows):
    groups={c:{r['group'] for r in rows if r['label']==c} for c in CLASSES}
    counts=Counter((r['label'],r['group']) for r in rows)
    return np.array([(.5 if r['label']=='SkinCancer' else .5/7)/len(groups[r['label']])/
                     counts[r['label'],r['group']] for r in rows],dtype=float)


def register():
    assert not (OUT/'protocol.json').exists(),'Preserve registered experiment'
    av=prior.read(audit.OUT/'verification.json');assert av['status']=='PASS'
    assert av['results_sha256']==sha256_file(audit.OUT/'results.json')
    h=prior.read(prior.OUT/'protocol.json');ap=prior.read(audit.OUT/'protocol.json')
    prior.check_frozen(ap);rr=ap['splits']['original_train']
    assert len(rr)==4043 and len(h['train'])==1169
    assert {r['path'] for r in rr}.isdisjoint(r['path'] for r in h['train'])
    assert {r['sha256'] for r in rr}.isdisjoint(r['sha256'] for r in h['train'])
    assert {r['group'] for r in rr}.isdisjoint(r['group'] for s in h['splits'].values() for r in s)
    files=[audit.OUT/'protocol.json',audit.OUT/'results.json',audit.OUT/'verification.json',audit.OUT/'original_train.npz',
           prior.OUT/'train_features.npz',prior.MODELS/'binary.npz']
    files += [prior.OUT/(s+'.npz') for s in (*prior.pad.prior.SPLITS,'pad_validation')]
    frozen={**ap['sources'],**{x.relative_to(ROOT).as_posix():sha256_file(x) for x in files}}
    codes=dict(ap['code_sha256'])
    for n in ('pilot_original_eight_cancer_head_original_replay.py','verify_original_eight_cancer_head_original_replay.py',
              'verify_original_eight_frozen_cancer_head.py'):
        codes[n]=sha256_file(ROOT/'ai-service/training'/n)
    p=dict(classes=CLASSES,pad_train=h['train'],original_train=rr,splits=h['splits'],pad_validation=h['pad_validation'],
        sources=frozen,code_sha256=codes,
        configuration=dict(seed=42,C=.001,solver='lbfgs',max_iter=3000,tol=1e-7,original_mass=.25,
                           cancer_mass_weight=.25,backbone_frozen=True,scaler_frozen=True),
        hypothesis='Train/validation audit found out-of-scope inflammatory classes frequently flagged by PAD head. Adding labelled original-train binary supervision may reduce these confusions without whole-CNN changes.',
        training='Both use exact frozen 2048 ResNet features and PAD-only train scaler from prior pilot. Control repeats prior1169PAD binary objective. Replay adds4043original train binary targets SkinCancer versus seven other classes. Total sample weight1169 both: control PAD100%, replay PAD75%/original25%. Each domain cancer/negative total mass50/50, original negatives equal seven classes then scene-group then photo. PAD patient/subtype weighting unchanged. Same C/solver/no grid/no threshold fit.',
        selection='Old reference plus control/replay fixed cancer-only25% fusion. Prior original/DC/PAD guard, same rank and old fallback. Freeze selection before accessing held-role feature caches to generate new predictions.',
        limits=h['limits']+['Original SkinCancer folder targets not all biopsy-confirmed or subtype-resolved; negative diagnoses retain original source uncertainty.',
                              'Original scene/case groups are not confirmed patient IDs. Replay reuses existing images, no new labelled cases.',
                              'Adding original supervision changes cohort; this is not a new independent test or global OOF result.'])
    save_json(OUT/'protocol.json',p);return p


def train(p):
    assert not MODELS.exists(),'Preserve trained heads';MODELS.mkdir(parents=True)
    with np.load(prior.OUT/'train_features.npz') as z:
        assert z['paths'].tolist()==[r['path'] for r in p['pad_train']]
        xp=z['features'].copy();wp=z['sample_weights'].copy()
    with np.load(audit.OUT/'original_train.npz') as z:
        assert z['paths'].tolist()==[r['path'] for r in p['original_train']]
        xo=z['features'].copy()
    with np.load(prior.MODELS/'binary.npz') as z:old={k:z[k].copy() for k in z.files}
    scaler=StandardScaler();scaler.mean_=old['mean'];scaler.scale_=old['scale'];scaler.n_features_in_=2048
    padz=scaler.transform(xp);oldz=scaler.transform(xo)
    yp=np.array([int(r['source_label'] in prior.DIAGNOSES[:3]) for r in p['pad_train']])
    yo=np.array([int(r['label']=='SkinCancer') for r in p['original_train']])
    ow=original_weights(p['original_train'])*1169*.25
    heads={};reports={}
    for branch in BRANCHES:
        x=padz if branch=='control' else np.concatenate([padz,oldz])
        y=yp if branch=='control' else np.concatenate([yp,yo])
        w=wp if branch=='control' else np.concatenate([.75*wp,ow])
        assert np.isclose(w.sum(),1169) and np.isclose(w[y==1].sum(),584.5)
        with warnings.catch_warnings():
            warnings.simplefilter('error',ConvergenceWarning)
            model=LogisticRegression(C=.001,solver='lbfgs',max_iter=3000,tol=1e-7,random_state=42).fit(x,y,sample_weight=w)
        if branch=='control':
            assert np.allclose(model.coef_,old['coefficients'],atol=1e-7)
            assert np.allclose(model.intercept_,old['intercept'],atol=1e-7)
        heads[branch]=(scaler,model)
        np.savez_compressed(MODELS/(branch+'.npz'),mean=scaler.mean_,scale=scaler.scale_,coefficients=model.coef_,intercept=model.intercept_,classes=model.classes_)
        reports[branch]=dict(training_rows=len(y),sum_weights=float(w.sum()),cancer_weight=float(w[y==1].sum()),
                             iterations=model.n_iter_.tolist(),checkpoint_sha256=sha256_file(MODELS/(branch+'.npz')))
        np.savez_compressed(OUT/(branch+'_training_targets.npz'),truth=y,sample_weights=w)
    save_json(OUT/'training_report.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),branches=reports,
        control_reproduced_prior_binary=True,scaler_unchanged=True,backbone_frozen=True,
        original_class_mass={c:float(ow[[r['label']==c for r in p['original_train']]].sum()) for c in CLASSES}))
    return heads


def predictions(split,p,heads):
    rows=p['pad_validation'] if split=='pad_validation' else p['splits'][split]
    with np.load(prior.OUT/(split+'.npz')) as z:
        assert z['paths'].tolist()==[r['path'] for r in rows]
        x=z['features'];ref=z['old_classwise'].copy();oldbinary=z['binary_cancer'].copy()
    values=dict(old_classwise=ref);aux={}
    for b,(scaler,model) in heads.items():
        aux[b]=model.predict_proba(scaler.transform(x))[:,1]
        values[b+'_cancer25']=prior.fuse(ref,aux[b])
    assert np.allclose(aux['control'],oldbinary,atol=1e-7)
    arrays=dict(paths=[r['path'] for r in rows],**values,**{b+'_cancer':q for b,q in aux.items()})
    if split!='pad_validation':arrays['truth']=np.array([CLASSES.index(r['label']) for r in rows])
    np.savez_compressed(OUT/(split+'.npz'),**arrays)
    return values,aux


def evaluate(p,heads):
    trial={n:dict(name=n) for n in METHODS};results={}
    for split in prior.pad.prior.SPLITS[:2]:
        values,_=predictions(split,p,heads);y=np.array([CLASSES.index(r['label']) for r in p['splits'][split]])
        results[split]={n:score(q,y) for n,q in values.items()}
        for n in METHODS:trial[n][split]=results[split][n]
    values,aux=predictions('pad_validation',p,heads)
    pm={n:prior.pad.cancer_score(q,p['pad_validation']) for n,q in values.items()}
    for n,t in trial.items():
        t['eligible']=bool(prior.pad.prior.eligible(t,trial['old_classwise']) and
            pm[n]['non_cancer_flag_rate']<=pm['old_classwise']['non_cancer_flag_rate']+1e-12 and
            all(pm[n]['by_diagnosis'][d]['flag_rate']>=pm['old_classwise']['by_diagnosis'][d]['flag_rate']-1e-12 for d in prior.DIAGNOSES[:3]))
    selected=sorted([t for t in trial.values() if t['eligible']],key=prior.pad.prior.rank)[0]['name']
    save_json(OUT/'selection_locked.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),selected=selected,trials=trial,
        checkpoints={b:sha256_file(MODELS/(b+'.npz')) for b in BRANCHES}))
    for split in prior.pad.prior.SPLITS[2:]:
        values,_=predictions(split,p,heads);y=np.array([CLASSES.index(r['label']) for r in p['splits'][split]])
        results[split]={n:score(q,y) for n,q in values.items()}
    prior.check_frozen(p)
    save_json(OUT/'results.json',dict(protocol_sha256=sha256_file(OUT/'protocol.json'),selection_sha256=sha256_file(OUT/'selection_locked.json'),
        selected=selected,results=results,pad_validation=pm,scope='Fixed source-supervision pilot, same frozen backbone/scaler; exploratory previously investigated held roles. No new independent test.'))
    print('Completed original-train replay head; selected='+selected,flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    p=prior.read(OUT/'protocol.json') if args.resume else register();prior.check_frozen(p)
    if args.prepare_only:print('Registered fixed25% original-train binary replay.');return
    assert not (OUT/'results.json').exists();evaluate(p,train(p))


if __name__=='__main__':main()
