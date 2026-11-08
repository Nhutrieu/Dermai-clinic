"""Pair discovery and safe binary routing behavior."""
from pathlib import Path
import sys
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'training'))
import pilot_teacher_pairwise_specialists as trial


def test_pair_discovery_uses_balanced_confusion_and_excludes_cancer():
    truth=np.repeat(np.arange(8),20);pred=truth.copy()
    pred[truth==3]=5  # No supported non-cancer rival for Lupus.
    pred[np.flatnonzero(truth==4)[:3]]=2
    pred[np.flatnonzero(truth==6)[:4]]=2
    plan=trial.select_pairs(truth,pred)
    assert plan['pairs']==[[2,4],[2,6]]
    assert not plan['details']['Lupus']['used']
    assert all(5 not in pair for pair in plan['pairs'])
    with pytest.raises(ValueError):trial.select_pairs(np.array([3]),np.array([2]))


def test_pair_switches_abstain_on_conflicts_and_never_chain_or_change_cancer():
    pairs=[[2,3],[2,4],[3,4]]
    current=np.array([2,2,3,5,7])
    q=np.full((5,3,2),.5)
    q[0,0]=[.1,.9]; q[0,1]=[.1,.9]  # Two conflicting destinations -> keep2.
    q[1,0]=[.1,.9]; q[1,2]=[.1,.9]  # Only pair(2,3) applies to original2.
    q[2,0]=[.9,.1]
    q[3:]=[.1,.9]
    np.testing.assert_array_equal(trial.pair_route(current,q,pairs),[2,3,2,5,7])
    with pytest.raises(ValueError):trial.pair_route(current,np.full((5,1,2),.5),[[3,5]])
    with pytest.raises(ValueError):trial.pair_route(current,np.full((5,2,2),.5),[[2,3],[2,3]])


def test_conditional_scores_stay_finite_under_extreme_logits():
    logits=np.array([[1000.,-1000.,-999.],[-1000.,1000.,999.]])
    q=trial.conditional(logits,[[1,2]])
    np.testing.assert_allclose(q.sum(2),1)
    assert np.isfinite(q).all()
    np.testing.assert_allclose(q[:,0,1],[1/(1+np.exp(-1)),1/(1+np.exp(1))])
    assert trial.conditional(logits,[]).shape==(2,0,2)


def test_serialized_binary_multinomial_matches_library_probability_convention():
    rng=np.random.default_rng(42);x=rng.normal(size=(40,5)).astype(np.float32)
    y=np.where(x[:,0]>0,4,2);scaler=StandardScaler().fit(x);weights=np.full(len(x),2.)
    saved,_=trial.fit(x,y,weights,scaler)
    fitted=LogisticRegression(**trial.CONFIG).fit(scaler.transform(x),y,sample_weight=weights)
    from scipy.special import expit
    np.testing.assert_allclose(expit(trial.logits(saved,x)[:,0]),fitted.predict_proba(scaler.transform(x))[:,1],atol=1e-12)
    assert float(saved['logit_multiplier'])==2.


def test_total_gain_does_not_override_weak_recall_guard_and_ties_keep_current():
    truth=np.repeat(np.arange(8),20);current=truth.copy();current[:6]=7
    bad=truth.copy();bad[np.flatnonzero(truth==3)[0]]=2
    decisions=dict(current_policy=current,conditional_control=current.copy(),binary_pairs=bad)
    assert trial.choose(decisions,truth)['selected']=='current_policy'
    assert trial.choose({n:truth.copy() for n in decisions},truth)['selected']=='current_policy'
