# ConvNeXt-Tiny supervised contrastive fine-tuning protocol

Recorded before the first SupCon run on 08/10/2026.

## Question

Does a supervised contrastive objective improve the eight-class representation of the existing regularized ConvNeXt-Tiny checkpoint? This is an exploratory fine-tuning experiment, not a new independent validation.

## Frozen setup

- Initialize from `convnext_tiny_regularized_seed42/best_model.pth` (selected on validation only). Keep its architecture, class order, 224-pixel input, seed 42, source data, exact/near-duplicate cleaning (`dHash` radius 0) and grouped 85/15 train/validation split.
- Use two independent training augmentations per labeled image. The encoder and a 128-dimensional projection MLP produce normalized embeddings. Supervised contrastive loss uses every other view with the same class as a positive and different classes as negatives; always includes the second view of the same image. Combine this with weighted cross-entropy on both views: `total = CE + 0.1 * SupCon`, contrastive temperature 0.07.
- Train at most 8 epochs, batch size 8 original images (16 views), AdamW weight decay 0.01, learning rates `1e-5` backbone, `5e-5` classifier, `1e-4` projection. EMA decay 0.5 per epoch. Select raw or EMA model at each epoch by validation macro F1, then top-3 and validation CE loss. Early stopping patience 4. The projection head is training-only; saved inference checkpoint is a standard ConvNeXt-Tiny.
- Log train CE, SupCon and total losses separately. Evaluate the initial checkpoint on the same validation split before fine-tuning. Do not change this recipe in response to fixed-test or SCIN results.

## Evaluation rule

Compare validation macro F1 and per-class F1 against the initial checkpoint. Then evaluate the selected SupCon checkpoint once on the historical 564-image fixed test and 240-image SCIN case holdout, reporting accuracy, macro F1, calibration and SkinCancer/Lupus recall even if worse. These holdouts have already been used repeatedly, so results are exploratory. Clinical or deployment claims require a new patient-disjoint source with sufficient SkinCancer cases.

Method basis: [Khosla et al., NeurIPS 2020](https://proceedings.neurips.cc/paper_files/paper/2020/hash/d89a66c7c80a29b1bdbab0f2a1a94af8-Abstract.html). Dermatology precedent: [Balanced Supervised Contrastive Learning for Skin Lesion Classification](https://ieeexplore.ieee.org/document/10393927/) studies a related two-branch objective on lesion images; its data and performance cannot be transferred to this project directly.
