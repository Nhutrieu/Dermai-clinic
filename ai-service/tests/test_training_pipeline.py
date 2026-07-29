import sys
from pathlib import Path


TRAINING_DIR = Path(__file__).resolve().parents[1] / "training"
sys.path.insert(0, str(TRAINING_DIR))

from common import (  # noqa: E402
    CLASSES,
    ImageSample,
    class_counts,
    exclude_cross_split_duplicates,
    grouped_stratified_split,
)


def sample(name: str, label: int, digest: str, group_id: str | None = None) -> ImageSample:
    return ImageSample(Path(name), label, digest, group_id)


def test_cross_split_duplicates_are_removed_from_training():
    training = [sample("train-a", 0, "same"), sample("train-b", 0, "unique")]
    test = [sample("test-a", 0, "same")]

    kept, excluded = exclude_cross_split_duplicates(training, test)

    assert [item.path.name for item in kept] == ["train-b"]
    assert [item.path.name for item in excluded] == ["train-a"]


def test_grouped_split_is_stratified_and_does_not_leak_duplicate_hashes():
    samples = []
    for label in range(len(CLASSES)):
        for index in range(10):
            digest = f"{label}-{index // 2}"
            samples.append(sample(f"{label}-{index}.jpg", label, digest))

    training, validation = grouped_stratified_split(samples, 0.2, seed=42, num_classes=8)

    assert all(count > 0 for count in class_counts(training).values())
    assert all(count > 0 for count in class_counts(validation).values())
    assert {item.digest for item in training}.isdisjoint(
        {item.digest for item in validation}
    )


def test_grouped_split_keeps_distinct_images_from_same_case_together():
    samples = []
    for label in range(len(CLASSES)):
        for case_index in range(5):
            for image_index in range(2):
                samples.append(
                    sample(
                        f"{label}-{case_index}-{image_index}.jpg",
                        label,
                        f"digest-{label}-{case_index}-{image_index}",
                        f"case-{label}-{case_index}",
                    )
                )

    training, validation = grouped_stratified_split(samples, 0.2, seed=42, num_classes=8)

    assert {item.group_id for item in training}.isdisjoint(
        {item.group_id for item in validation}
    )
