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
