import sys
from collections import Counter
from pathlib import Path

import torch
import pytest


TRAINING_DIR = Path(__file__).resolve().parents[1] / "training"
sys.path.insert(0, str(TRAINING_DIR))

from common import ImageSample  # noqa: E402
from train_supcon_convnext import BalancedSupConBatchSampler, supcon_loss  # noqa: E402


def test_supcon_prefers_same_class_embeddings_and_has_gradients():
    labels = torch.tensor([0, 1, 0, 1])
    aligned = torch.tensor(
        [[1.0, 0.0], [0.0, 1.0], [0.9, 0.1], [0.1, 0.9]],
        requires_grad=True,
    )
    mixed = torch.tensor(
        [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9]],
    )

    good_loss = supcon_loss(aligned, labels)
    bad_loss = supcon_loss(mixed, labels)
    good_loss.backward()

    assert good_loss.isfinite()
    assert good_loss < bad_loss
    assert aligned.grad is not None and aligned.grad.abs().sum() > 0


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA is unavailable")
def test_supcon_is_finite_under_cuda_autocast():
    embeddings = torch.randn(16, 128, device="cuda", requires_grad=True)
    labels = torch.arange(8, device="cuda").repeat(2)

    with torch.autocast(device_type="cuda", dtype=torch.float16):
        loss = supcon_loss(embeddings, labels)
    loss.backward()

    assert loss.isfinite()
    assert embeddings.grad is not None and embeddings.grad.isfinite().all()


def test_balanced_batches_contain_distinct_images_and_multiple_class_positives():
    samples = [ImageSample(Path(f"{label}_{image}.png"), label, f"{label}_{image}") for label in range(8) for image in range(3)]
    sampler = BalancedSupConBatchSampler(samples, seed=42)
    first_epoch = list(sampler)
    repeated_first_epoch = list(BalancedSupConBatchSampler(samples, seed=42))

    assert first_epoch == repeated_first_epoch
    assert len(first_epoch) == 3
    for batch in first_epoch:
        assert len(batch) == len(set(batch)) == 8
        assert sorted(Counter(samples[index].label for index in batch).values()) == [2, 2, 2, 2]
    assert list(sampler) != first_epoch
