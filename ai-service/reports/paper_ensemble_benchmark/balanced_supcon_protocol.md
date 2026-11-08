# Balanced-batch supervised contrastive protocol

Recorded on 08/10/2026 before the first balanced-batch training run. The historical fixed test, SCIN holdout and PAD-UFES-20 have already been inspected; none may be used for checkpoint selection or tuning this experiment. Its only model-selection endpoint is the existing 892-image validation split. This is exploratory development, not independent validation.

## Hypothesis

The earlier SupCon run used randomly shuffled batches of eight original images. Every image had its own augmented positive, but some classes could have no *other image* of the same class in a batch. The [SupCon paper](https://proceedings.neurips.cc/paper_files/paper/2020/hash/d89a66c7c80a29b1bdbab0f2a1a94af8-Abstract.html) uses other samples of the same label as additional positives. Test whether guaranteeing those positives improves validation macro F1.

## Frozen change

Keep the earlier regularized ConvNeXt-Tiny checkpoint as initialization, the same dataset cleaning, group split, seed 42, two augmentation views, projection head, CE/SupCon weights, optimizer, learning rates, scheduler, EMA, maximum eight epochs and checkpoint selection rule. Change only the batch construction: each batch contains **four distinct classes and two distinct original images per class** (eight originals, sixteen views). Sample classes uniformly; sample images without replacement within each batch, allowing reuse across batches. Draw `ceil(train_image_count / 8)` batches per epoch. This oversamples rare classes and may itself cause overfitting; report train–validation gap and class-specific validation F1.

## Decision rule

Select checkpoint by validation macro F1, then top-3 accuracy and validation CE loss. Compare the selected validation macro F1 and per-class F1 with regularized ConvNeXt and the earlier randomly batched SupCon result. Report all eight epoch rows. Do not evaluate this checkpoint on fixed test, SCIN or PAD; a fresh independent eight-class holdout would be needed for a final accuracy claim.
