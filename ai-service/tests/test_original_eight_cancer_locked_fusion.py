"""Protect cancer decisions and validation-only selection semantics."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'training'))
import evaluate_original_eight_cancer_locked_fusion as fusion


def probabilities(labels):
    result = np.full((len(labels),8),.02)
    result[np.arange(len(labels)),labels] = .86
    return result


def test_cancer_mask_is_exact_even_when_resnet_disagrees_or_suggests_new_cancer():
    reference = probabilities([5,0,1,2,3,4,6,7])
    resnet = probabilities([0,5,5,5,5,5,5,5])
    actual = fusion.decide(reference,resnet,[5])
    assert np.array_equal(actual==5,reference.argmax(1)==5)
    assert actual[0]==5


def test_extra_protected_class_can_neither_lose_nor_gain_predicted_rows():
    rng = np.random.default_rng(12)
    reference = rng.dirichlet(np.ones(8),size=1000)
    resnet = rng.dirichlet(np.ones(8),size=1000)
    actual = fusion.decide(reference,resnet,[1,5])
    for label in [1,5]:
        assert np.array_equal(actual==label,reference.argmax(1)==label)
    assert np.any(actual!=reference.argmax(1))


def test_lock_all_is_reference_and_prediction_rejects_invalid_inputs():
    reference = probabilities(range(8))
    resnet = reference[::-1].copy()
    assert np.array_equal(fusion.decide(reference,resnet,range(8)),np.arange(8))
    with pytest.raises(ValueError):fusion.decide(reference,resnet,[])
    with pytest.raises(ValueError):fusion.decide(reference,resnet*.5,[5])


def test_adaptation_protects_class_harmed_on_validation_without_outer_data():
    # Class1 has a fragile reference margin, which the mixture would overturn.
    reference = probabilities(range(8))
    reference[1] = [.34,.36,.05,.05,.05,.05,.05,.05]
    resnet = probabilities([0,0,2,3,4,5,6,7])
    truth = np.arange(8)
    protection,trace = fusion.learn_protected(reference,resnet,truth)
    assert 1 in protection and 5 in protection
    assert len(trace)<=8
    selection = fusion.select(reference,resnet,truth)
    assert selection['selected']==fusion.REFERENCE  # Original wins identical metrics.
    assert 'recall_Candidiasis' in selection['trials'][fusion.FIXED]['guard_failures']
    assert not selection['trials'][fusion.ADAPTIVE]['guard_failures']


def test_metrics_match_manual_counts_and_cannot_hide_total_score_decline():
    truth=np.arange(8)
    base=fusion.metrics(truth,truth)
    wrong=truth.copy();wrong[0]=2
    score=fusion.metrics(wrong,truth)
    assert score['accuracy']==7/8
    assert score['confusion_matrix'][0][2]==1
    failures=fusion.guard_failures(score,base)
    assert 'accuracy' in failures and 'macro_f1' in failures and 'recall_Acne' in failures
