# SCIN supplement

DermAI uses a strictly filtered subset of the Skin Condition Image Network (SCIN) release
1.0.0 for research and educational evaluation.

- Source: <https://github.com/google-research-datasets/scin>
- Dataset paper: <https://doi.org/10.1001/jamanetworkopen.2024.46615>
- License: <https://github.com/google-research-datasets/scin/blob/main/LICENSE>

The license requires attribution when sharing the material or adaptations and prohibits any
attempt to re-identify or re-link contributors. Do not commit images or raw metadata.

The local CSV files are ignored by Git. Prepare the subset with:

```powershell
python ai-service\scripts\prepare_scin.py `
  --metadata ai-service\data-sources\scin `
  --output SkinDisease\scin-v1 `
  --minimum-weight 0.5 `
  --external-ratio 0.2 `
  --seed 42
```

The script applies a narrow label map, groups by `case_id`, reserves external cases before
training, verifies every image and removes exact duplicates. `SkinCancer` is not supplemented
because SCIN's retrospective differential labels are too sparse for this broad class.

## Prepared subset used by the current model

- 1,217 valid images after filtering and verification.
- 977 images in the training pool.
- 240 images in a case-disjoint external test set.
- Two exact duplicates were removed; one source object returned HTTP 404.
- The external set is strongly imbalanced: Eczema 156, Tinea 31, Psoriasis 22,
  Acne 19, Warts 7, Lupus 4, Candidiasis 1 and SkinCancer 0.

After merging the training pool with the local dataset and cleaning conflicts,
the current run uses 5,053 training images, 894 validation images, 564 images in
the fixed original test set and the 240-image SCIN external test set.

Results, limitations, checkpoint checksum and rollback instructions are recorded
in [`../../../docs/model-card-scin-v1.md`](../../../docs/model-card-scin-v1.md).
