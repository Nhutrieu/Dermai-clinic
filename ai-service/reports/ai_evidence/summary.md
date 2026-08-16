# AI evaluation evidence

Generated at `2026-08-14T10:15:53.794735+00:00` from model `efficientnet_b0-20260728T185742Z`.

## Integrity

- Checkpoint: `ai-service/models/best_model.pth`
- SHA-256: `914f83a85c4dbff06424e0a48f1121950f10e3c0ce8d5a9f68369b38106cc3df` (verified against expected value: `True`)
- Size: 16370790 bytes

## Calibration and error evidence

| Evaluation set | Images | Accuracy | ECE (15 bins) | Brier | NLL | Errors |
|---|---:|---:|---:|---:|---:|---:|
| Fixed test | 564 | 78.90% | 0.1061 | 0.3222 | 0.8385 | 119 |
| SCIN external | 240 | 67.92% | 0.1902 | 0.4822 | 1.2197 | 77 |

ECE is equal-width Top-1 ECE. Brier is the multiclass sum-of-squares mean. These are raw softmax scores; no calibration method was fitted on test data. Per-image files use image SHA-256 identifiers, not source filenames.

- Fixed-test dominant confusions: Tinea→Eczema (13); Lupus→Psoriasis (8); Psoriasis→Eczema (8). Errors at confidence ≥ 0.90: 38; examples by hash prefix: `sha256:f6c989d920322a66…` Eczema→Psoriasis (100.00%); `sha256:ec3c37cce3eb6f71…` Eczema→Psoriasis (99.94%); `sha256:8de667d93415ec0b…` Psoriasis→SkinCancer (99.94%).
- SCIN-external dominant confusions: Tinea→Eczema (19); Eczema→Acne (10); Psoriasis→Eczema (10). Errors at confidence ≥ 0.90: 22; examples by hash prefix: `sha256:437828b108fbeab6…` Tinea→Eczema (99.99%); `sha256:c80b90a9dd405f01…` Tinea→Eczema (99.76%); `sha256:921be687068f1873…` Psoriasis→Eczema (99.72%).
- The 0.55 policy accepted 98/119 fixed-test errors and 62/77 external errors; it is not a reliable correctness or OOD gate.

## Local latency

| Device | Model-forward p50 | `app.predict` + Grad-CAM p50 |
|---|---:|---:|
| cpu | 10.98 ms | 92.09 ms |
| cuda | 6.72 ms | 56.87 ms |

The full measurement starts from an already decoded PIL image and excludes HTTP upload, decoding, RAG and frontend latency. Raw samples and p95/p99 are in `latency.json`.

## OOD and Grad-CAM limits

- Synthetic non-clinical probes rejected at confidence < 0.55: 0/6 (0.00%). Rejecting none is a failed sanity check for the current threshold and demonstrates overconfident behavior on these probes. It is not a clinical OOD benchmark.
- True OOD AUROC/AUPR/FPR95: unavailable because no labeled, clinically representative OOD set exists locally.
- Grad-CAM metadata generated for 16 deterministic correct/error examples. Overlay files are not tracked; clinical review remains pending.
- Subgroup evidence by skin tone, age, sex and Vietnamese population: unavailable from the normalized evaluation inputs.

## Artifacts

See `manifest.json` for provenance and the JSON files beside this summary for reliability bins, per-image probabilities/errors, latency samples, synthetic probes and Grad-CAM statistics.
