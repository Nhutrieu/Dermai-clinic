"""Matched head wiring, isolated dropout randomness and adoption guards."""
from pathlib import Path
import sys

import numpy as np
import torch
from sklearn.metrics import f1_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'training'))
import run_teacher_dropout_specialist as trial
import run_teacher_nonlinear_specialist as previous


def _coordinate_head(head):
    # Expose the first five hidden coordinates at output. A known nonzero
    # function makes placement/scaling observable despite zero output init.
    with torch.no_grad():
        for parameter in head.parameters():
            parameter.zero_()
        for coordinate in range(5):
            head.encoder.weight[coordinate, coordinate] = 1
            head.output.weight[coordinate, coordinate] = 1
    return head


def test_shared_initial_tensors_and_zero_dropout_reproduce_previous_relu_head():
    with torch.random.fork_rng():
        torch.manual_seed(42)
        old = previous.Head(True)
        torch.manual_seed(42)
        control = trial.Head(0.)
        torch.manual_seed(42)
        dropout = trial.Head(.5)
        assert list(old.state_dict()) == list(control.state_dict()) == list(dropout.state_dict())
        for name, value in old.state_dict().items():
            torch.testing.assert_close(value, control.state_dict()[name], rtol=0, atol=0)
            torch.testing.assert_close(value, dropout.state_dict()[name], rtol=0, atol=0)
        x = torch.randn(13, 2048, generator=torch.Generator().manual_seed(81))
        assert torch.count_nonzero(dropout(x)).item() == 0
        # Nonzero parameters ensure p=0 equivalence is not only zero-logit init.
        _coordinate_head(old)
        control.load_state_dict(old.state_dict())
        for training in (True, False):
            old.train(training)
            control.train(training)
            torch.testing.assert_close(control(x), old(x), rtol=0, atol=0)


def test_hidden_dropout_is_inverted_after_relu_and_probability_disables_it():
    with torch.random.fork_rng():
        head = _coordinate_head(trial.Head(.5))
        x = torch.zeros(64, 2048)
        x[:, :5] = torch.tensor([-1., 1., 2., 3., 4.])
        head.train()
        torch.manual_seed(73)
        actual = head(x).detach()
        assert torch.count_nonzero(actual[:, 0]).item() == 0  # ReLU precedes mask.
        for column in range(1, 5):
            np.testing.assert_array_equal(torch.unique(actual[:, column]).numpy(), [0., 2. * column])
        expected_logits = torch.tensor([0., 1., 2., 3., 4.]).repeat(len(x), 1)
        # Exercise the production probability helper, not just Dropout.eval().
        first = trial.probability(head, x)
        assert not head.training and not head.dropout.training
        np.testing.assert_array_equal(first, trial.probability(head, x))
        np.testing.assert_array_equal(first, expected_logits.softmax(1).numpy().astype(float))
        torch.testing.assert_close(head(x), expected_logits, rtol=0, atol=0)


def test_dropout_stream_replays_evolving_masks_restores_rng_and_preserves_batches():
    with torch.random.fork_rng():
        head = _coordinate_head(trial.Head(.5)).train()
        x = torch.ones(48, 2048)
        torch.manual_seed(103)
        global_before = torch.random.get_rng_state().clone()
        expected_order = previous.sampling(137, 4)

        def run(fold):
            with trial.dropout_stream(fold):
                first = head(x).detach().clone()
                order_before = trial.sampling(137, 4)
                second = head(x).detach().clone()
                order_after = trial.sampling(137, 4)
            torch.testing.assert_close(torch.random.get_rng_state(), global_before, rtol=0, atol=0)
            assert torch.equal(order_before, expected_order)
            assert torch.equal(order_after, expected_order)
            return first, second

        first, second = run(2)
        assert not torch.equal(first, second)  # Context seeds once, not every batch.
        replay_first, replay_second = run(2)
        torch.testing.assert_close(first, replay_first, rtol=0, atol=0)
        torch.testing.assert_close(second, replay_second, rtol=0, atol=0)
        other_first, _ = run(3)
        assert not torch.equal(first, other_first)
        assert torch.equal(trial.sampling(137, 4), expected_order)


def test_selection_keeps_reference_on_ties_or_weak_harm_and_requires_control_gain():
    truth = np.repeat(np.arange(8), 20)
    identical = {name: truth.copy() for name in
                 ('current_gate', 'dropout_control', 'dropout_specialist')}
    assert trial.choose(identical, truth)['selected'] == 'current_gate'

    # Overall gain without a weak-class F1 gain over control is insufficient.
    current = truth.copy()
    current[0] = 7
    decisions = dict(current_gate=current, dropout_control=current.copy(),
                     dropout_specialist=truth.copy())
    assert f1_score(truth, truth, average='macro') > f1_score(truth, current, average='macro')
    assert trial.choose(decisions, truth)['selected'] == 'current_gate'

    # Better aggregate performance cannot compensate for lost Lupus recall.
    current = truth.copy()
    current[:6] = 7
    harmful = truth.copy()
    harmful[np.flatnonzero(truth == 3)[0]] = 2
    assert f1_score(truth, harmful, average='macro') > f1_score(truth, current, average='macro')
    decisions = dict(current_gate=current, dropout_control=current.copy(),
                     dropout_specialist=harmful)
    assert trial.choose(decisions, truth)['selected'] == 'current_gate'

    current = truth.copy()
    current[np.flatnonzero(truth == 3)[0]] = 2
    # Tied recovered weak errors favor the matched p=0 control.
    decisions = dict(current_gate=current, dropout_control=truth.copy(),
                     dropout_specialist=truth.copy())
    assert trial.choose(decisions, truth)['selected'] == 'dropout_control'
    # A genuine gain beyond control may be selected under the same guards.
    decisions['dropout_control'] = current.copy()
    assert trial.choose(decisions, truth)['selected'] == 'dropout_specialist'
