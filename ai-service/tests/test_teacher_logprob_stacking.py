"""Protect the meta-holdout boundary and the exact cancer decision mask."""
from pathlib import Path
import sys

import numpy as np
import pytest
from threadpoolctl import threadpool_limits

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'training'))
import run_teacher_logprob_stacking as trial


def test_parent_input_validation_and_log_floor():
    p = np.eye(8)
    x = trial.features([p, p, p])
    assert x.shape == (8, 24) and np.isfinite(x).all()
    assert x[0, 0] == 0 and x[0, 1] == np.log(trial.EPS)
    for bad in [p * .5, np.full((8, 8), np.nan), -p]:
        with pytest.raises(ValueError):
            trial.features([p, p, bad])


def test_crossfit_groups_and_held_labels_do_not_affect_own_fit():
    y = np.repeat(np.arange(8), 24)
    groups = np.repeat(np.arange(96), 2)
    parts = trial.assignments(y, groups)
    for group in np.unique(groups):
        assert len(set(parts[groups == group])) == 1
    x = np.random.default_rng(7).normal(size=(len(y), 24))
    changed = y.copy()
    changed[parts == 0] = (changed[parts == 0] + 1) % 8
    with threadpool_limits(limits=1):
        first, _ = trial.crossfit(x, y, parts)
        second, _ = trial.crossfit(x, changed, parts)
    assert np.allclose(first[parts == 0], second[parts == 0], atol=1e-12)


def test_routing_preserves_all_cancer_calls_even_head_disagrees():
    current = np.arange(8)
    p = np.full((8, 8), .01)
    p[:, 5] = .8  # Cannot create new cancer calls.
    p[:, 3] = .14
    out = trial.route(current, p)
    assert np.array_equal(out == 5, current == 5)
    assert out.tolist() == [3, 3, 3, 3, 3, 5, 3, 3]
    with pytest.raises(ValueError):
        trial.route(current, p[:, :5])
