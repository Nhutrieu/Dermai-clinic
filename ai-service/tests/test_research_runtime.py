import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.model import CLASSES
from app.research_runtime import aggregate, load_research, route_fold, serving_scores, _predict_locked


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


def test_fixed_branch_uses_real_three_parent_scores():
    bc = distribution(3, .7)[None, :]
    resnet = distribution(4, .99)[None, :]
    parents = [bc, bc, resnet]
    d, ref, p, _ = route_fold(parents, np.full(8, .5), [1, 5])
    order, scores, override, _ = serving_scores(parents, p, int(ref[0]), [1, 5], int(d[0]))
    np.testing.assert_allclose(scores, (.75 * bc + .25 * resnet)[0])
    assert order[0] == d[0] and not override
    assert not np.isclose(scores[order[0]] * 5, round(scores[order[0]] * 5))


def test_protected_policy_never_swaps_raw_scores_to_match_the_label():
    # ResNet would favor Cancer, but the retained rule cannot add it.
    bc = np.array([[.18, .01, .18, .18, .18, .08, .18, .01]])
    parents = [bc, bc, distribution(5, .99)[None, :]]
    d, ref, p, _ = route_fold(parents, np.full(8, .5), [1, 5])
    order, scores, override, _ = serving_scores(parents, p, int(ref[0]), [1, 5], int(d[0]))
    assert d[0] != 5 and order[0] == d[0] and scores[5] > scores[d[0]] and override
    np.testing.assert_allclose(scores, (.75 * bc + .25 * parents[2])[0])
    cancer = distribution(5)[None, :]
    d, ref, p, _ = route_fold([cancer, cancer, parents[2]], np.full(8, .5), [1, 5])
    _, scores, _, _ = serving_scores([cancer, cancer, parents[2]], p, int(ref[0]), [1, 5], int(d[0]))
    assert d[0] == 5
    np.testing.assert_array_equal(scores, cancer[0])


def test_fold_count_must_match_explicit_serving_mode():
    from types import SimpleNamespace
    with pytest.raises(ValueError, match='Fold count'):
        _predict_locked(SimpleNamespace(folds=[None] * 5), None, .7, .2, .65)
    with pytest.raises(ValueError, match='Fold count'):
        _predict_locked(SimpleNamespace(folds=[None], aggregation='protected_fold_vote_v1'), None, .7, .2, .65)


@pytest.mark.parametrize('count', [1, 5])
def test_prediction_runs_configured_branches_and_uses_matching_scores_and_cam(monkeypatch, count):
    from types import SimpleNamespace
    import torch
    from PIL import Image
    from app import research_runtime as runtime

    calls, cams = [], []
    class Parent(torch.nn.Module):
        def __init__(self, index):
            super().__init__()
            self.index = index

        def forward(self, x):
            calls.append(self.index)
            winner = [3, 3, 3, 4, 4][self.index // 3]
            return torch.tensor(np.log(distribution(winner, .73))[None, :], dtype=torch.float32)

    class Cam:
        def __init__(self, model, layer):
            cams.append(model.index)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def create(self, x, winner):
            return np.zeros((224, 224))

    monkeypatch.setattr(runtime, 'GradCam', Cam)
    monkeypatch.setattr(runtime, 'is_out_of_scope', lambda *args: (False, {}))
    folds = [runtime.FoldBundle(tuple(SimpleNamespace(model=Parent(i * 3 + j), target_layer=None)
                                    for j in range(3)), np.full(8, .5), [1, 5]) for i in range(count)]
    ood = SimpleNamespace(extract_embeddings=lambda x: torch.zeros((1, 4)), ood_profile={})
    bundle = SimpleNamespace(folds=folds, ood_gate=ood, device=torch.device('cpu'),
                             serving_fold=4 if count == 1 else None, version='test',
                             aggregation='single_fold_v1' if count == 1 else 'protected_fold_vote_v1')
    result = _predict_locked(bundle, Image.new('RGB', (224, 224)), .7, .2, .65)
    assert calls == list(range(count * 3)) and cams == [0]
    assert result['disease'] == result['top3'][0]['label'] == 'Lupus'
    assert not result['confidence_is_calibrated']
    if count == 1:
        assert result['confidence'] == pytest.approx(.73)
        assert result['score_type'] == 'ensemble_evidence' and result['serving_fold'] == 4
        assert result['gradcam_method'] == 'illustrative_b0_fold4'
        assert 'fold_decisions' not in result
    else:
        assert result['confidence'] == .6 and result['score_type'] == 'fold_vote_fraction'
        assert result['fold_decisions'] == ['Lupus'] * 3 + ['Psoriasis'] * 2
        assert result['gradcam_method'] == 'illustrative_b0_fold0'
        assert 'serving_fold' not in result


def test_vote_manifest_requires_five_ordered_folds(tmp_path):
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(dict(schema_version=1, classes=CLASSES, aggregation='protected_fold_vote_v1', folds=[dict(fold=4)])))
    with pytest.raises(ValueError, match='Five ordered folds'):
        load_research(path)


def test_package_fails_closed_on_bad_hash_or_missing_asset(tmp_path):
    asset = tmp_path / 'weights.pth'
    asset.write_bytes(b'not-tensors')
    m = dict(schema_version=2, classes=CLASSES, aggregation='single_fold_v1', serving_fold=4,
             folds=[dict(fold=4)], assets={'test':dict(path='weights.pth',sha256='bad')})
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


def test_vote_preserves_cancer_reference_without_swapping_scores():
    ref = [5, 5, 3, 4, 6]
    d = [5, 5, 3, 3, 3]
    winner, order, shares, override, tied = aggregate(d, ref, np.stack([distribution(c) for c in ref]))
    assert winner == order[0] == 5 and override and not tied
    assert shares[5] == .4 and shares[3] == .6
    ref = [5, 5, 3, 3, 3]
    winner, _, shares, override, _ = aggregate([5, 5, 3, 4, 6], ref, np.stack([distribution(c) for c in ref]))
    assert winner != 5 and shares[5] == .4 and override
    with pytest.raises(ValueError, match='cancer votes'):
        aggregate([5, 3, 3, 4, 6], ref, np.stack([distribution(c) for c in ref]))


def test_vote_tie_uses_original_deterministic_rule():
    d = [3, 3, 4, 4, 6]
    bc = np.stack([distribution(c) for c in d])
    assert aggregate(d, d, bc)[0] == 3 and aggregate(d, d, bc)[-1]


def test_serving_selection_uses_only_inner_scores_and_deterministic_ties():
    from training.select_single_fold_serving import choose
    rows = [dict(fold=0, macro_f1=.8, accuracy=.9),
            dict(fold=1, macro_f1=.81, accuracy=.8),
            dict(fold=2, macro_f1=.81, accuracy=.8)]
    assert choose(rows) == 1
