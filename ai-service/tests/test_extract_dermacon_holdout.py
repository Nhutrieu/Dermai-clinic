import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))

from extract_dermacon_holdout import archive_index, extract  # noqa: E402


def test_extract_only_selected_images_with_flat_safe_names(tmp_path):
    sample = tmp_path / "sample.jpg"
    Image.new("RGB", (8, 8), "red").save(sample)
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.write(sample, "DATASET/selected.jpg")
        target.write(sample, "DATASET/unused.jpg")
    index = archive_index([archive], {"selected.jpg"})
    report = extract(index, tmp_path / "output")
    assert report == {"extracted": 1, "unique_sha256": 1, "exact_duplicate_groups": []}
    assert (tmp_path / "output" / "selected.jpg").is_file()
    assert not (tmp_path / "output" / "unused.jpg").exists()
    with pytest.raises(ValueError, match="Missing"):
        archive_index([archive], {"absent.jpg"})
