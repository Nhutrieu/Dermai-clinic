"""Case-group nearest-neighbor voting in three frozen CNN feature spaces.

Fixed k=7, same train-only memory and neighbors for uniform/distance votes.
One fold, no new CNN fitting and no clinical confidence claim.
"""
from __future__ import annotations
import argparse
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

import pilot_teacher_focal_cnn as previous
import pilot_teacher_class_expert_bank as latent

ROOT,base,prior,latest=previous.ROOT,previous.base,previous.prior,previous.latest
features=latent.features
OUT=ROOT/'ai-service/reports/teacher_case_retrieval_fold0_seed42_20261024'
MODELS=ROOT/'ai-service/candidates'/OUT.name
K=7
METHODS=['current_policy','uniform_case_vote','distance_case_vote']


def embedding(blocks):
    if len(blocks)!=3 or len({len(x) for x in blocks})!=1:raise ValueError('Three aligned feature blocks required')
    output=[]
    for block in blocks:
        x=np.asarray(block,dtype=np.float64)
        if x.ndim!=2 or not np.isfinite(x).all():raise ValueError('Finite feature matrices required')
        norm=np.linalg.norm(x,axis=1,keepdims=True)
        if (norm<=0).any():raise ValueError('Nonzero feature norms required')
        output.append(x/norm)
    return np.concatenate(output,axis=1)/np.sqrt(3.)


def search(query,query_rows,memory,memory_rows,k=K):
    if (query.ndim!=2 or memory.ndim!=2 or query.shape[1]!=memory.shape[1]
            or len(query)!=len(query_rows) or len(memory)!=len(memory_rows) or k<1):
        raise ValueError('Aligned matrices/metadata and positive k required')
    if not np.allclose(np.linalg.norm(query,axis=1),1.,atol=1e-12,rtol=0) or not np.allclose(np.linalg.norm(memory,axis=1),1.,atol=1e-12,rtol=0):
        raise ValueError('Unit vectors required for cosine search')
    indices=[];distances=[]
    for start in range(0,len(query),64):
        similarity=np.round(np.clip(query[start:start+64]@memory.T,-1.,1.),12)
        for row,sim in zip(query_rows[start:start+64],similarity):
            selected=[];seen=set()
            for j in np.argsort(-sim,kind='stable'):
                candidate=memory_rows[int(j)]
                if any(candidate[key]==row[key] for key in ['path','sha256','group']):continue
                if candidate['group'] in seen:continue
                seen.add(candidate['group']);selected.append(int(j))
                if len(selected)==k:break
            if len(selected)!=k:raise ValueError('Not enough eligible distinct training groups')
            indices.append(selected);distances.append(1.-sim[selected])
    return np.asarray(indices,dtype=np.int64),np.asarray(distances,dtype=np.float64)


def vote(indices,distances,memory_targets,weighted):
    if indices.shape!=distances.shape or indices.ndim!=2 or indices.shape[1]<1:
        raise ValueError('Aligned nonempty neighbor matrices required')
    if not np.isfinite(distances).all() or (distances<0).any():raise ValueError('Finite nonnegative distances required')
    weights=np.ones(distances.shape,dtype=np.float64)
    if weighted:
        for i,d in enumerate(distances):
            zero=d<=1e-12
            weights[i]=zero.astype(float) if zero.any() else 1./d
    targets=np.asarray(memory_targets)[indices]
    q=np.column_stack([(weights*(targets==label)).sum(1) for label in range(5)])
    return q/q.sum(1,keepdims=True)


def choose(decisions,truth):
    scores={n:base.metrics(d,truth) for n,d in decisions.items()}
    trials={n:dict(metrics=s,guard_failures=prior.failures(s,scores['current_policy'])) for n,s in scores.items()}
    candidate=scores['distance_case_vote']
    if candidate['macro_f1']+1e-12<scores['uniform_case_vote']['macro_f1']:
        trials['distance_case_vote']['guard_failures'].append('macro_f1_below_uniform_control')
    for name in ['current_policy','uniform_case_vote']:
        if latest.previous.mean_focus(candidate)<=latest.previous.mean_focus(scores[name])+1e-12:
            trials['distance_case_vote']['guard_failures'].append('no_weak_mean_f1_gain_vs_'+name)
    passing=[n for n,t in trials.items() if not t['guard_failures']]
    selected=max(passing,key=lambda n:(scores[n]['macro_f1'],latest.previous.mean_focus(scores[n],'recall'),
                    scores[n]['accuracy'],n=='current_policy',n=='uniform_case_vote'))
    return dict(selected=selected,trials=trials)


def prepare():
    if (OUT/'protocol.json').exists():
        p=base.read(OUT/'protocol.json');prior.verify(p);return p
    reg=base.read(ROOT/'ai-service/reports/active_research_track.json');assert reg['next_experiment'] is None
    old=base.read(previous.OUT/'protocol.json');prior.verify(old)
    assert base.read(previous.OUT/'completion.json')['status']=='complete_verified_pilot_not_selected'
    files=[Path(__file__),ROOT/'ai-service/tests/test_teacher_case_retrieval.py',
        ROOT/'ai-service/training/pilot_teacher_focal_cnn.py',ROOT/'ai-service/training/pilot_teacher_class_expert_bank.py',
        previous.OUT/'protocol.json',previous.OUT/'completion.json',previous.OUT/'independent_review.json',
        features.OUT/'protocol.json',features.OUT/'verification.json',features.OUT/'independent_review.json']
    p=dict(name=OUT.name,registered_utc=features.utc(),fold=0,classes=base.CLASSES,parent_protocol=old['parent_protocol'],
        frozen_sha256={**old['frozen_sha256'],**{x.relative_to(ROOT).as_posix():base.sha(x) for x in files}},
        representation='Reuse SHA-frozen original fold0 B0(1280),ConvNeXt(768),ResNet(2048) latent caches. Independently L2-normalize each block in float64, concatenate divided bysqrt3:4096unit-vector. Equal block cosine contribution, no fitted scaler or CNN changes.',
        memory='All4043originaltrain photos with their original labels/path/SHA/scene-case group. No inner,outer or source row in memory. Vote target maps original labels to Lupus/Psoriasis/Tinea/Eczema/Other; labels are not corrected or inferred.',
        retrieval='Fixed k7 distinct training groups per query. CPUfloat64 dot products in64row chunks, cosine clipped[-1,1] and rounded12decimals for ranking/weight distance. Stabledescending order, original train index breaks exact ties. Skip same path OR SHA OR group as query. At most nearest photo per group votes; mixed-label groups retain the nearest photo original label, no group relabeling.',
        intervention='Same memory,representation,k7,eligible neighbor indices and routing. Control uniform1/7 votes. Treatment inverse cosine distance weights; if any distance<=1e-12 use only zero-distance neighbors with equal mass. No k/metric/scale/threshold/weight grid or trainable gating.',
        routing='Five-way vote scores routed by fixed>=.8 rule; only current Lupus/Psoriasis/Tinea/Eczema calls change, Other abstains and exact SkinCancer mask preserved. Vote fractions are not calibrated clinical probabilities or conformal confidence.',
        selection='On718inner compare current/uniform/distance with existing strict perweakRecall/F1,totalAccuracy/MacroF1,weakPrecision and otherRecall guards. Distance also MF>=uniform and meanweakF1 strictly above both current/uniform. Rank MF,meanweakRecall,Accuracy,ties current thenuniform. Lock memory,inner neighbor evidence and choice before outer/source retrieval.',
        scope='Onefold exploratory pilot4043train/718inner/1176outer/1709known-source. No new5937global score. Each neighbor is one known scene/case group, not necessarily a verified separate patient.',
        limitations=old['limitations']+[
            'No focal-CNN checkpoints, spatial multicrop features or pairwise heads from preceding pilots are used here; original three CNN latent caches only.',
            'Nearest-neighbor similarity can reflect background/source/skin-tone cues rather than a diagnosis. Original public labels and scene groups are not expert-reviewed patient diagnoses.',
            'Class imbalance and domain shift remain in memory. Filtering recorded path/SHA/group cannot prove patient independence when patientIDs are absent.',
            'Papernot/McDaniel2018 DkNN uses representations across layers and calibrated nonconformity. This custom final-feature/group-vote adaptation does not implement fullDkNN, conformal calibration or its robustness claims.'],
        references=['https://arxiv.org/abs/1803.04765','https://scikit-learn.org/1.3/modules/neighbors.html'],
        k=K,new_CNN_fits=0,new_backbones=0,global_5937_score_changed=False,serving_changed=False)
    OUT.mkdir(parents=True,exist_ok=True);base.write(OUT/'protocol.json',p);base.write(OUT/'research_registry_before.json',reg)
    reg['next_experiment']=OUT.relative_to(ROOT).as_posix();reg['next_experiment_status']='registered_group_case_retrieval_fold0'
    base.write(ROOT/'ai-service/reports/active_research_track.json',reg);return p


def memory(p):
    parent=base.read(ROOT/p['parent_protocol']);rows=prior.role_rows(parent,0,'train')
    path=MODELS/'memory_bank.npz'
    if path.exists():
        with np.load(path,allow_pickle=False) as z:
            assert z['paths'].tolist()==[r['path'] for r in rows] and z['protocol_sha256'].item()==base.sha(OUT/'protocol.json')
            return rows,z['features'].copy(),z['targets'].copy()
    vectors=embedding(latent.cached_blocks('train',rows))
    targets=latest.fiveway(np.array([base.CLASSES.index(r['label']) for r in rows]))
    MODELS.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path,paths=[r['path'] for r in rows],sha256=[r['sha256'] for r in rows],groups=[r['group'] for r in rows],
        labels=[r['label'] for r in rows],features=vectors,targets=targets,protocol_sha256=base.sha(OUT/'protocol.json'))
    return rows,vectors,targets


def retrieve(p,role,rows,bank):
    bank_rows,bank_vectors,targets=bank
    query=embedding(latent.cached_blocks(role,rows));ids,dist=search(query,rows,bank_vectors,bank_rows,p['k'])
    qq={name:vote(ids,dist,targets,weighted) for name,weighted in [('uniform_case_vote',False),('distance_case_vote',True)]}
    np.savez_compressed(OUT/f'{role}_neighbors.npz',paths=[r['path'] for r in rows],indices=ids,distances=dist,**qq)
    return qq


def select_and_lock(p):
    bank=memory(p);parent=base.read(ROOT/p['parent_protocol']);rows=prior.role_rows(parent,0,'inner_validation')
    qq=retrieve(p,'inner_validation',rows,bank)
    with np.load(latest.OUT/'fold_0/inner_decisions.npz',allow_pickle=False) as z:
        assert z['paths'].tolist()==[r['path'] for r in rows]
        truth=z['truth'].copy();current=z[base.read(latest.OUT/'fold_0/selection_locked.json')['selected']].copy()
    dd=dict(current_policy=current);dd.update({n:prior.route(current,q) for n,q in qq.items()})
    lock=choose(dd,truth)
    np.savez_compressed(OUT/'inner_decisions.npz',paths=[r['path'] for r in rows],truth=truth,**dd)
    lock.update(locked_utc=features.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),
        artifacts_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in [MODELS/'memory_bank.npz',OUT/'inner_validation_neighbors.npz',OUT/'inner_decisions.npz']})
    base.write(OUT/'selection_locked.json',lock)
    print(dict(selected=lock['selected'],failures={n:t['guard_failures'] for n,t in lock['trials'].items()}),flush=True)


def evaluate(p):
    assert not (OUT/'results.json').exists(),'Preserve completed pilot'
    lock=base.read(OUT/'selection_locked.json');assert lock['protocol_sha256']==base.sha(OUT/'protocol.json')
    for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path)==digest,path
    bank=memory(p);parent=base.read(ROOT/p['parent_protocol']);source=base.read(features.SOURCE/'protocol.json');started=features.utc()
    original={r['path']:r for r in base.read(latest.OUT/'oof_decisions.json')};external={r['path']:r for r in base.read(features.SOURCE/'source_decisions.json')}
    output=[];scores={}
    for role,rows in [('outer_holdout',prior.role_rows(parent,0,'outer_holdout')),('source_transfer',source['rows'])]:
        truth=np.array([base.CLASSES.index(r['label']) for r in rows]);current=np.array([original[r['path']]['predictions']['validation_selected'] if role=='outer_holdout' else external[r['path']]['predictions']['validation_selected'][0] for r in rows])
        qq=retrieve(p,role,rows,bank);dd=dict(current_policy=current)
        dd.update({n:prior.route(current,q) for n,q in qq.items()});dd['validation_selected']=dd[lock['selected']]
        idx={r['path']:i for i,r in enumerate(rows)};slices={'original_outer':list(idx)} if role=='outer_holdout' else source['subsets']
        for name,paths in slices.items():
            ids=[idx[path] for path in paths];scores[name]=dict(images=len(ids),methods={n:base.metrics(d[ids],truth[ids]) for n,d in dd.items()})
        output.extend(dict(**r,role=role,predictions={n:int(d[i]) for n,d in dd.items()}) for i,r in enumerate(rows))
    base.write(OUT/'held_decisions.json',output)
    r=dict(status='complete_exploratory_case_retrieval_pilot',fold=0,selected=lock['selected'],validation=lock['trials'],held=scores,
        held_started_utc=started,completed_utc=features.utc(),protocol_sha256=base.sha(OUT/'protocol.json'),selection_sha256=base.sha(OUT/'selection_locked.json'),
        memory_images=4043,memory_groups=len({r['group'] for r in bank[0]}),k=K,new_CNN_fits=0,global_5937_score_changed=False,serving_changed=False,limitations=p['limitations'])
    base.write(OUT/'results.json',r);prior.verify(p)
    base.write(OUT/'verification.json',dict(status='PASS',results_sha256=base.sha(OUT/'results.json'),
        neighbors_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in OUT.glob('*_neighbors.npz')}))
    print(dict(inner={n:{k:t['metrics'][k] for k in ['accuracy','macro_f1']} for n,t in r['validation'].items()},
        outer={n:{k:s[k] for k in ['accuracy','macro_f1']} for n,s in scores['original_outer']['methods'].items()}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    with threadpool_limits(limits=2):
        p=prepare()
        if args.prepare_only:return
        assert not (OUT/'results.json').exists(),'Preserve completed pilot'
        if not (OUT/'selection_locked.json').exists():select_and_lock(p)
        evaluate(p)


if __name__=='__main__':main()
