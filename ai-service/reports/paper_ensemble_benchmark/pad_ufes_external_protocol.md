# Frozen PAD-UFES-20 external check protocol

Recorded before downloading images or running any checkpoint on PAD-UFES-20 (08/10/2026).

## Source and scope

Use version 1 of the [official PAD-UFES-20 release](https://data.mendeley.com/datasets/zr7vgbcyr2/1), all available PNG images and its official metadata. This is a new smartphone skin-lesion source with patient IDs; it is not an eight-class DermAI test. The dataset's three malignant labels are BCC, SCC (including Bowen disease), and MEL. ACK, NEV and SEK are nonmalignant categories in this dataset but do not match DermAI's seven non-SkinCancer classes. Do not train, calibrate, select checkpoints, or tune thresholds using PAD images.

## Locked models and outputs

Evaluate four already trained checkpoints: current EfficientNet-B0 baseline, the frozen equal-weight three-model ensemble (baseline + EfficientNet-B0 V2c + ResNet50), regularized ConvNeXt-Tiny, and ConvNeXt-Tiny after supervised contrastive fine-tuning. Use the checkpoints' existing temperature calibration and the unchanged 224-pixel image transform. The binary flag is `argmax(8-class probability) == SkinCancer`. Do not select a PAD-derived probability threshold.

For each model report malignant image-level sensitivity, patient-level sensitivity (a patient is flagged if any of their malignant images is flagged), separate BCC/SCC/MEL sensitivities, and `SkinCancer` flag rates on ACK/NEV/SEK. Report counts and Wilson 95% intervals; compare models on the same images with a paired patient-cluster bootstrap (seed 42). This tests a limited cancer-flag behavior, not eight-class accuracy, screening safety, or clinical fitness. If image/metadata coverage is incomplete, report the exact coverage and do not imply whole-dataset results.

## Independence and audit

Before model inference, match filenames and SHA-256 hashes against DermAI's historical train, fixed test and SCIN images. Check a perceptual hash for possible near duplicates; flag potential matches for human review rather than automatically assuming independence. Record the exact PAD version, archive integrity, metadata image and patient counts, biopsy status, missing images, and any excluded records. The historical SkinDisease set lacks complete patient IDs, so patient overlap cannot be conclusively excluded even if hashes do not match.

Report results even if all models fail. The PAD test is exploratory because it is from a different task distribution; do not use its metrics to choose an ensemble for deployment.
