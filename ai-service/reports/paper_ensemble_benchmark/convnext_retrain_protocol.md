# ConvNeXt-Tiny retraining protocol (fixed before the run)

## Observation

The first ConvNeXt-Tiny run reached training macro F1 `0.9864` and validation macro F1 `0.7734` at its selected epoch 12. By epoch 19, training macro F1 was `0.9996` while validation was `0.7692`. This large gap is evidence of overfitting, although it does not establish that the network memorized individual images.

## Planned intervention

Use the same cleaned 8-class dataset, class order, seed 42, 224-pixel input, case-grouped SCIN split, fixed test and SCIN case holdout. Initialize again from the official ImageNet ConvNeXt-Tiny weights. Freeze the backbone for two epochs, then fine-tune it at `0.1 ×` the classifier learning rate (`3e-5` versus `3e-4`). Increase label smoothing from `0.05` to `0.10` and AdamW weight decay from `2e-4` to `0.01`. Use an epoch-level EMA decay of `0.5` instead of `0.99`; the prior epoch-level `0.99` EMA lagged far behind the raw model. Select the checkpoint by validation macro F1, with early stopping patience 6.

The lower backbone learning rate and delayed unfreezing follow the principle of conservative fine-tuning of a pretrained ConvNeXt. The [official ConvNeXt fine-tuning recipe](https://github.com/facebookresearch/ConvNeXt/blob/main/TRAINING.md) also uses a lower fine-tuning learning rate than initial training and disables MixUp/CutMix in its fine-tuning example. The exact values here are adapted to this smaller dataset and hardware; they are hypotheses, not established optimal values.

## Evaluation rule

Compare the selected checkpoint's **validation macro F1** and train–validation gap with the original run first. Then report fixed-test accuracy, macro F1, `SkinCancer`/`Lupus` recall, and SCIN case-holdout accuracy/macro F1 regardless of whether the model improves. Do not use these holdouts to revise this recipe or choose the final model. A truly final comparison requires new independent cases, especially for `SkinCancer` and Vietnamese users.
