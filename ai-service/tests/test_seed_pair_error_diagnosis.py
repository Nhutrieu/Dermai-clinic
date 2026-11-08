from pathlib import Path
import importlib.util
import numpy as np
import pytest

PATH = Path(__file__).resolve().parents[1] / 'reports/teacher_seed_pair_error_diagnosis_20261105/run_experiment.py'
spec = importlib.util.spec_from_file_location('diagnosis293', PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_funnel_agreement_cancer_only_lupus_and_strict_confirmation():
    parent = np.array([0, 0, 5, 0, 0, 0, 0])
    ce = np.zeros((7, 8)); cb = ce.copy(); six = np.zeros((7, 6))
    cb[:, 0] = 2.; ce[:, 3] = .2; ce[1, 0] = 3.
    cb[3, 0] = 0.; cb[3, 1] = 2.  # Psoriasis destination removed by add-only policy
    six[:, 0] = 1.; six[4, 0] = 0.  # strict tie rejected
    ce[5, 0] = 1.7  # gain only .5, less than ln2
    ce[5, 4] = 2.2  # CE proposes a different label, so disagreement passes
    ce[6] = 0.; ce[6, 4] = 1.; cb[6, 0] = np.log(2.)  # exact gain boundary
    cand, natural, masks, margin, gain, pred = m.funnel(parent, ce, cb, six)
    np.testing.assert_array_equal(pred, [3, 0, 5, 0, 0, 0, 0])
    assert masks[1, 0] and not masks[1, 1]
    assert masks[2, 1] and not masks[2, 2]
    assert masks[3, 3] and not masks[3, 4]
    assert masks[4, 4] and not masks[4, 5]
    assert masks[5, 2] and not masks[5, 3]
    assert masks[6, 2] and not masks[6, 3]
    np.testing.assert_array_equal(m.funnel(parent, ce, ce, six)[-1], parent)
    assert m.reason(3, 0, 3, 3, 2., 2., masks[1]) == 'CE_CB_agree_on_correct_label'
    with pytest.raises(ValueError): m.funnel(parent, ce[:, :7], cb, six)


def test_bootstrap_resamples_whole_groups_with_paired_multiplicity():
    inverse = np.array([0, 0, 1, 2, 2, 2])
    np.testing.assert_array_equal(m.row_weights([2, 0, 2], inverse, 3), [1, 1, 0, 2, 2, 2])
    np.testing.assert_array_equal(m.row_weights([0, 1, 2], inverse, 3), np.ones(6))
    with pytest.raises(ValueError): m.row_weights([0, 1], inverse, 3)
    with pytest.raises(ValueError): m.row_weights([0, 1, 3], inverse, 3)


def test_metric_endpoints_with_absent_classes_and_known_confusion():
    cm = np.diag([1, 2, 3, 4, 5, 6, 7, 8]); cm[3, 0] = 2
    v = m.metric_vector(cm)
    assert len(v) == 12 and v[0] == 36/38
    assert v[2] == 1 and v[3] == 4/6 and v[4] == 8/10
    assert v[-1] == 1
    z = np.zeros((8, 8)); z[0, 0] = 2
    np.testing.assert_array_equal(m.metric_vector(z), [1., .125] + [0.] * 10)
