import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import classification_report, confusion_matrix
from torch import nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, models, transforms

CLASSES = ["Acne", "Candidiasis", "Eczema", "Lupus", "Psoriasis", "SkinCancer", "Tinea", "Warts"]


def architecture(name: str, classes: int, pretrained=True):
    if name == "resnet50":
        model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT if pretrained else None)
        model.fc = nn.Linear(model.fc.in_features, classes)
    elif name == "convnext_tiny":
        model = models.convnext_tiny(weights=models.ConvNeXt_Tiny_Weights.DEFAULT if pretrained else None)
        model.classifier[2] = nn.Linear(model.classifier[2].in_features, classes)
    else:
        model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT if pretrained else None)
        model.classifier[1] = nn.Linear(model.classifier[1].in_features, classes)
    return model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--model", choices=["efficientnet_b0", "resnet50", "convnext_tiny"], default="efficientnet_b0")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--output", type=Path, default=Path("models"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    train_tf = transforms.Compose([
        transforms.Resize(256), transforms.RandomResizedCrop(224, scale=(.8, 1)),
        transforms.RandomHorizontalFlip(), transforms.RandomRotation(12),
        transforms.ColorJitter(.15, .15, .15, .05), transforms.ToTensor(),
        transforms.Normalize([.485,.456,.406],[.229,.224,.225])
    ])
    full = datasets.ImageFolder(args.data / "train", transform=train_tf)
    keep = {full.class_to_idx[name]: i for i, name in enumerate(CLASSES)}
    indices = [i for i, (_, target) in enumerate(full.samples) if target in keep]
    subset = torch.utils.data.Subset(full, indices)
    # Remap labels without copying the 1.3 GB dataset.
    subset.dataset.target_transform = lambda x: keep[x]
    val_size = max(1, int(.15 * len(subset)))
    train_set, val_set = random_split(subset, [len(subset)-val_size, val_size], generator=torch.Generator().manual_seed(args.seed))
    loaders = {
        "train": DataLoader(train_set, args.batch_size, shuffle=True, num_workers=2),
        "val": DataLoader(val_set, args.batch_size, shuffle=False, num_workers=2),
    }
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = architecture(args.model, len(CLASSES)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    loss_fn, best, history = nn.CrossEntropyLoss(), -1.0, []
    args.output.mkdir(parents=True, exist_ok=True)
    for epoch in range(args.epochs):
        epoch_metrics = {}
        for phase in ("train", "val"):
            model.train(phase == "train")
            correct = total = 0; losses = []
            all_y, all_pred = [], []
            for x, y in loaders[phase]:
                x, y = x.to(device), y.to(device)
                optimizer.zero_grad(set_to_none=True)
                with torch.set_grad_enabled(phase == "train"):
                    logits = model(x); loss = loss_fn(logits, y)
                    if phase == "train": loss.backward(); optimizer.step()
                pred = logits.argmax(1)
                losses.append(loss.item()); correct += (pred == y).sum().item(); total += y.numel()
                all_y.extend(y.cpu().tolist()); all_pred.extend(pred.cpu().tolist())
            report = classification_report(all_y, all_pred, output_dict=True, zero_division=0)
            epoch_metrics[phase] = {"loss": float(np.mean(losses)), "accuracy": correct/total, "macro_f1": report["macro avg"]["f1-score"]}
            if phase == "val" and report["macro avg"]["f1-score"] > best:
                best = report["macro avg"]["f1-score"]
                torch.save({"model_state_dict": model.state_dict(), "architecture": args.model, "classes": CLASSES, "version": f"{args.model}-best"}, args.output / "best_model.pth")
                (args.output / "confusion_matrix.json").write_text(json.dumps(confusion_matrix(all_y, all_pred).tolist()), encoding="utf-8")
        history.append(epoch_metrics); print(epoch + 1, epoch_metrics)
    (args.output / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

