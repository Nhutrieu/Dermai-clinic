"""Local utility math and fit-role boundaries for the Macro-F1 gate."""
from pathlib import Path
import sys
import numpy as np
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'training'))
import run_teacher_macro_f1_gate as trial


def f1(cm):
    den=cm.sum(0)+cm.sum(1)
    return np.divide(2*cm.diagonal(),den,out=np.zeros(8),where=den>0).mean()


def test_analytic_delta_matches_full_confusion_mutation_including_wrong_to_wrong():
    rng=np.random.default_rng(8);y=rng.integers(0,8,140);b=rng.integers(0,8,140);c=rng.integers(0,8,140)
    target,w,delta,cm=trial.utility_targets(b,c,y)
    for i in range(len(y)):
        if b[i]==5 or c[i]==5 or b[i]==c[i]:assert delta[i]==0 and target[i]==-1;continue
        changed=cm.copy();changed[y[i],b[i]]-=1;changed[y[i],c[i]]+=1
        assert abs(delta[i]-(f1(changed)-f1(cm)))<1e-14
    assert np.any((b!=y)&(c!=y)&(target>=0))
    assert abs(w.sum()-(trial.old.gate_targets(b,c,y)>=0).sum())<1e-12
    # Removing the only false positive of an unsupported class is well-defined.
    t,_,d,cm=trial.utility_targets(np.array([0,1]),np.array([2,0]),np.array([1,1]))
    assert np.isfinite(d).all() and np.isfinite(f1(cm))


def test_common_scaler_and_total_weight_mass_match_original_control():
    rng=np.random.default_rng(2);y=np.tile(np.arange(8),12);b=rng.integers(0,8,len(y));c=(y+1)%8
    c[::2]=y[::2];b[1::2]=y[1::2];x=rng.normal(size=(len(y),22))
    with threadpool_limits(limits=1):models,reports,trace=trial.fit_pair(x,b,c,y)
    assert models['conservative_control']['kind']=='logistic'
    assert np.array_equal(models['conservative_control']['mean'],models['macro_f1_gate']['mean'])
    assert np.array_equal(models['conservative_control']['scale'],models['macro_f1_gate']['scale'])
    assert abs(trace['utility_weights'].sum()-(trace['control_target']>=0).sum())<1e-12


def test_meta_held_labels_do_not_enter_utility_confusion_or_weights():
    rng=np.random.default_rng(5);n=100;fit=np.arange(80);hold=np.arange(80,100)
    y=np.tile(np.arange(8),13)[:n];b=y.copy();b[::3]=(b[::3]+1)%8
    candidate=y[fit].copy();candidate[1::3]=(candidate[1::3]+2)%8
    probability=np.full((80,8),.01);probability[np.arange(80),candidate]=.93
    source=dict(fit_indices=fit,hold_indices=hold,nested_probability=probability,
        gate_features=rng.normal(size=(80,22)),held_gate_features=rng.normal(size=(20,22)),held_candidate=(b[hold]+1)%8)
    changed=y.copy();changed[hold]=(changed[hold]+3)%8
    with threadpool_limits(limits=1):a=trial.fit_meta(source,y,b);d=trial.fit_meta(source,changed,b)
    for key in a[2]:np.testing.assert_array_equal(a[2][key],d[2][key])
    for arm in trial.ARMS:np.testing.assert_allclose(a[3][arm],d[3][arm],atol=0,rtol=0)


def test_absent_control_classes_always_keep_without_fake_utility_examples():
    x=np.zeros((4,22));b=np.array([0,0,0,5]);c=np.array([1,2,3,4]);y=b.copy()
    with threadpool_limits(limits=1):models,_,_=trial.fit_pair(x,b,c,y)
    assert all(m['kind']=='always_keep' for m in models.values())
    assert all((trial.old.gate_probability(m,x)==0).all() for m in models.values())
