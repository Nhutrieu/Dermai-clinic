import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.model import CLASSES
from app.research_runtime import aggregate, load_research, route_fold


def distribution(winner, confidence=.9):
    p = np.full(8, (1 - confidence) / 7)
    p[winner] = confidence
    return p


def test_specialist_threshold_other_and_cancer_masks():
    p = np.stack([distribution(c) for c in [3, 4, 5, 0]])
    # S can change a weak prediction at >= .8; Other abstains. Cancer/Acne stay.
    sp = np.array([[.05, .8, .05, .05, .05], [0, 0, 0, 0, 1],
                   [1, 0, 0, 0, 0], [1, 0, 0, 0, 0]])
    result, ref, _, _ = route_fold([p, p, p], np.full(8, .5), list(range(8)), specialist_probability=sp)
    assert ref.tolist() == [3, 4, 5, 0]
    assert result.tolist() == [4, 4, 5, 0]
    sp[0] = [.0501, .7999, .05, .05, .05]
    assert route_fold([p, p, p], np.full(8, .5), list(range(8)), specialist_probability=sp)[0][0] == 3


def test_serving_vote_keeps_cancer_reference_without_faking_confidence():
    ref = [5, 5, 3, 4, 6]
    decisions = [5, 5, 3, 3, 3]
    bc = np.stack([distribution(c) for c in ref])
    winner, order, shares, override, tied = aggregate(decisions, ref, bc)
    assert winner == 5 and order[0] == 5 and override
    assert shares[5] == .4 and shares[3] == .6  # Scores are NOT swapped.
    assert not tied


def test_serving_vote_cannot_add_cancer_after_noncancer_concentration_changes():
    ref = [5, 5, 3, 3, 3]
    decisions = [5, 5, 3, 4, 6]
    bc = np.stack([distribution(c) for c in ref])
    winner, _, shares, override, _ = aggregate(decisions, ref, bc)
    assert winner != 5 and shares[5] == .4 and override
    with pytest.raises(ValueError, match='cancer votes'):
        aggregate([5, 3, 3, 4, 6], ref, bc)


def test_vote_ties_are_deterministic_and_flagged():
    d = [3, 3, 4, 4, 6]
    bc = np.stack([distribution(c) for c in d])
    a, b = aggregate(d, d, bc), aggregate(d, d, bc)
    assert a[0] == b[0] == 3 and a[-1]


def test_package_fails_closed_on_bad_hash_or_missing_asset(tmp_path):
    asset = tmp_path / 'weights.pth'
    asset.write_bytes(b'not-tensors')
    m = dict(schema_version=1, classes=CLASSES, aggregation='protected_fold_vote_v1',
             folds=[dict(fold=i) for i in range(5)], assets={'test':dict(path='weights.pth',sha256='bad')})
    path = tmp_path / 'manifest.json';path.write_text(json.dumps(m))
    with pytest.raises(ValueError, match='SHA-256'):
        load_research(path)
    m['assets']['test']['sha256'] = hashlib.sha256(asset.read_bytes()).hexdigest()
    asset.unlink();path.write_text(json.dumps(m))
    with pytest.raises(ValueError, match='Missing'):
        load_research(path)


def test_research_rollback_is_explicit():
    assert Settings(research_manifest_path='off').research_manifest_path is None
    assert Settings(research_manifest_path='none').research_manifest_path is None
    assert Settings().research_manifest_path.name == 'manifest.json'
