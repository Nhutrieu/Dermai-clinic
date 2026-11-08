"""Safety/selection properties for the two supervisor-requested experiments."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'training'))
import run_teacher_priorities_ensemble_specialist as trial


def probs(labels):
    a = np.full((len(labels), 8), .02)
    a[np.arange(len(labels)), labels] = .86
    return a


def test_weighted_route_protects_complete_class_masks_even_at_extreme_weights():
    reference = probs(range(8))
    other = probs([5, 5, 5, 5, 5, 0, 5, 5])
    for alpha in [0., .1, .5, 1.]:
        result = trial.mixture(reference, other, [1, 5], alpha)
        for label in [1, 5]:
            assert np.array_equal(result == label, reference.argmax(1) == label)
    assert np.array_equal(trial.mixture(reference, other, list(range(8)), .5), np.arange(8))


def test_specialist_other_abstains_and_cannot_create_or_remove_cancer():
    current = np.arange(8)
    head = np.full((8, 5), .01)
    head[:, 0] = .96  # Confident Lupus, but only target-group calls may change.
    head[4] = [.01, .01, .01, .01, .96]  # Other means leave current Psoriasis.
    result = trial.route(current, head)
    assert result.tolist() == [0, 1, 3, 3, 4, 5, 3, 7]
    assert np.array_equal(result == 5, current == 5)


def test_threshold_and_invalid_specialist_probabilities():
    head = np.array([[.79, .06, .05, .05, .05], [.8, .05, .05, .05, .05]])
    assert trial.route([2, 2], head).tolist() == [2, 3]
    with pytest.raises(ValueError):
        trial.route([2], np.array([[1., 1., 0., 0., 0.]]))
    with pytest.raises(ValueError):
        trial.mixture(probs([2]), probs([3]), [5], 1.1)


def test_validation_selection_falls_back_on_tie_or_focus_recall_loss():
    truth = np.arange(8)
    same = trial.choose(dict(current_fusion=truth, specialist=truth.copy()), truth)
    assert same['selected'] == 'current_fusion'
    candidate = truth.copy()
    candidate[3] = 2
    result = trial.choose(dict(current_fusion=truth, specialist=candidate), truth)
    assert result['selected'] == 'current_fusion'
    assert 'Lupus_recall' in result['trials']['specialist']['guard_failures']


def test_head_numpy_softmax_matches_manual_and_is_stable(tmp_path):
    path = tmp_path / 'head.npz'
    coef = np.arange(15).reshape(5, 3) / 20
    np.savez(path, mean=np.zeros(3), scale=np.ones(3), coef=coef,
             intercept=np.zeros(5), classes=np.arange(5))
    x = np.array([[1., 2., 3.], [10000., 20000., 30000.]])
    actual = trial.head_probability(path, x)
    expected = np.exp(x[:1] @ coef.T - (x[:1] @ coef.T).max(1, keepdims=True))
    expected /= expected.sum(1, keepdims=True)
    assert np.allclose(actual[:1], expected)
    assert np.isfinite(actual).all() and np.allclose(actual.sum(1), 1)
