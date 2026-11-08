import sys
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))

from common import ImageSample  # noqa: E402
import train_v2  # noqa: E402


def test_pixel_check_rejects_dhash_collision_and_review_link_keeps_low_correlation_pair(monkeypatch):
    paths = [Path(f"sample_{name}.jpg") for name in "abcdef"]
    samples = [ImageSample(path, 0, path.stem) for path in paths]
    second = (1 << 20) | (1 << 21)
    third = (1 << 40) | (1 << 41)
    hashes = dict(zip(paths, [0, 1, second, second | (1 << 22), third, third | (1 << 42)]))
    vectors = {
        paths[0]: np.array([1, -1], dtype=np.float32),
        paths[1]: np.array([-1, 1], dtype=np.float32),
        paths[2]: np.array([1, -1], dtype=np.float32),
        paths[3]: np.array([-1, 1], dtype=np.float32),
        paths[4]: np.array([1, -1], dtype=np.float32),
        paths[5]: np.array([1, -1], dtype=np.float32),
    }
    monkeypatch.setattr(train_v2, "normalized_gray", vectors.__getitem__)

    grouped, conflicts, audit = train_v2.group_near_duplicates(
        samples, hashes, radius=1, pixel_correlation=0.85,
        reviewed_pairs=[(paths[2], paths[3])],
    )
    by_path = {sample.path: sample.group_id for sample in grouped}
    assert by_path[paths[0]] != by_path[paths[1]]
    assert by_path[paths[2]] == by_path[paths[3]]
    assert by_path[paths[4]] == by_path[paths[5]]
    assert not conflicts
    assert audit["dhash_candidate_pairs"] == 3
    assert audit["pixel_accepted_pairs"] == 1
    assert audit["reviewed_pairs_linked"] == 1
