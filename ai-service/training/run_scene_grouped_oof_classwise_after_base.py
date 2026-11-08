"""Wait for the fixed-weight OOF report, then evaluate inner-fitted class-wise fusion."""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone

from evaluate_scene_grouped_oof_classwise_fusion import OUTPUT, SUMMARY
from evaluate_scene_grouped_oof_ensemble import OUTPUT as FIXED_OUTPUT
from prepare_scene_grouped_oof_folds import PROJECT


def main() -> None:
    while not FIXED_OUTPUT.exists():
        print(f"Waiting for 10 OOF runs: {datetime.now(timezone.utc).isoformat()}", flush=True)
        time.sleep(60)
    if OUTPUT.exists() or SUMMARY.exists():
        if OUTPUT.exists() and SUMMARY.exists():
            print(f"Class-wise comparison already complete: {OUTPUT}", flush=True)
            return
        raise FileExistsError("Partial class-wise report needs inspection")
    subprocess.run(
        [sys.executable, str(PROJECT / "ai-service/training/prepare_scene_grouped_oof_inner_predictions.py")],
        cwd=PROJECT, check=True,
    )
    subprocess.run(
        [sys.executable, str(PROJECT / "ai-service/training/evaluate_scene_grouped_oof_classwise_fusion.py")],
        cwd=PROJECT, check=True,
    )


if __name__ == "__main__":
    main()
