"""Nested gate boundaries, target semantics, fallback and fixed cancer calls."""
from pathlib import Path
import sys
import numpy as np
import pytest
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'training'))
import run_teacher_conservative_gate as trial


def test_gate_features_are_runtime_values_with_fixed_shape_and_vote_normalization():
    p=np.full((8,8),.01);p[np.arange(8),np.arange(8)]=.93
    current=np.roll(np.arange(8),1);x,candidate=trial.gate_features([p,p,p],p,current)
    assert x.shape==(8,22) and np.isfinite(x).all()
    assert np.array_equal(x[:,6:14].argmax(1),current)
    assert np.array_equal(x[:,14:22].argmax(1),candidate)
    assert x[2,4]==1 and x[6,4]==0  # Cancer baseline is never replaced.
    with pytest.raises(ValueError):trial.gate_features([p,p,p],p[:,:7],current)


def test_decisive_targets_and_strict_threshold_keep_all_cancer_masks():
    current=np.array([2,3,2,5,0]);candidate=np.array([3,4,3,3,5]);truth=np.array([3,3,4,3,5])
    assert trial.gate_targets(current,candidate,truth).tolist()==[1,0,-1,-1,-1]
    score=np.array([2/3,2/3+1e-6,.99,1.,1.])
    assert trial.route(current,candidate,score).tolist()==[2,4,3,5,0]
    assert np.array_equal(trial.route(current,candidate,score)==5,current==5)


def test_missing_either_gate_target_is_always_keep_without_fake_training_rows():
    x=np.random.default_rng(9).normal(size=(4,22))
    for target in [np.array([-1,-1,-1,-1]),np.array([1,1,-1,1]),np.array([0,0,0,-1])]:
        model,report=trial.fit_gate(x,target)
        assert model['kind']=='always_keep' and report['fit_rows']==int((target>=0).sum())
        assert trial.gate_probability(model,x).tolist()==[0]*4


def test_held_meta_labels_cannot_change_own_candidate_or_gate_predictions():
    rng=np.random.default_rng(7);y=np.repeat(np.arange(8),24);groups=np.repeat(np.arange(96),2)
    parents=[]
    for _ in range(3):
        p=rng.uniform(.01,1,(len(y),8));p[np.arange(len(y)),y]+=rng.uniform(0,1,len(y));p/=p.sum(1,keepdims=True);parents.append(p)
    current=parents[0].argmax(1);parts=trial.stack.assignments(y,groups)
    changed=y.copy();changed[parts==0]=(changed[parts==0]+3)%8
    with threadpool_limits(limits=1):
        a=trial.fit_part(parents,current,y,groups,parts,0)
        b=trial.fit_part(parents,current,changed,groups,parts,0)
    for i in [0,1,2,3]:np.testing.assert_allclose(a[i],b[i],atol=1e-12,rtol=0)
    report=a[4];held=set(groups[report['hold_indices']])
    assert held.isdisjoint(groups[report['fit_indices']])
    for nested in report['nested']:
        assert set(groups[nested['fit_indices']]).isdisjoint(groups[nested['hold_indices']])
        assert held.isdisjoint(groups[nested['fit_indices']])
