# WSeg wound-image dataset

This project uses the **original wound photographs only** from WSeg to train and
evaluate the out-of-scope safety gate. Segmentation masks are not used.

- Dataset card: https://huggingface.co/datasets/subbareddyoota/wseg_dataset
- Official project: https://github.com/subbareddy248/WSNET
- Paper: https://openaccess.thecvf.com/content/WACV2023/papers/Oota_WSNet_Towards_an_Effective_Method_for_Wound_Image_Segmentation_WACV_2023_paper.pdf
- Dataset license: CC BY-NC 4.0
- Downloaded archive: 2,686 wound photographs and 2,686 masks

The downloaded images live below `SkinDisease/`, which is excluded from Git.
They are suitable for the project's research/demo use. Commercial use requires
a separate license review.

The deterministic split is 70% training, 15% validation, and 15% held-out test.
Exact duplicate file hashes are removed before splitting. The held-out test set
is never used to fit the logistic gate or choose its threshold.
