from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class ScopeMlp(nn.Module):
    def __init__(self, features: int, hidden: int):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(features, hidden),
            nn.ReLU(),
            nn.Dropout(0.10),
            nn.Linear(hidden, 1),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.layers(values).squeeze(1)


def probabilities(model: nn.Module, values: np.ndarray, device: torch.device) -> np.ndarray:
    model.eval()
    output: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(values), 1024):
            batch = torch.from_numpy(values[start : start + 1024]).float().to(device)
            output.append(torch.sigmoid(model(batch)).cpu().numpy())
    return np.concatenate(output) if output else np.asarray([], dtype=np.float32)


def threshold_for_id(groups: list[np.ndarray], max_fpr: float) -> float:
    return max(
        float(np.quantile(group, 1.0 - max_fpr, method="higher"))
        for group in groups
        if len(group)
    )


def rejection_rate(values: np.ndarray, threshold: float) -> float | None:
    return float((values >= threshold).mean()) if len(values) else None


def binary_metrics(id_values: np.ndarray, ood_values: np.ndarray) -> dict:
    labels = np.concatenate([np.zeros(len(id_values)), np.ones(len(ood_values))])
    values = np.concatenate([id_values, ood_values])
    fpr, tpr, _thresholds = roc_curve(labels, values)
    reached = np.flatnonzero(tpr >= 0.95)
    return {
        "auroc": float(roc_auc_score(labels, values)),
        "aupr_ood": float(average_precision_score(labels, values)),
        "fpr95": float(fpr[reached[0]]) if len(reached) else 1.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Huấn luyện cổng MLP phát hiện ảnh ngoài phạm vi từ cache đặc trưng."
    )
    parser.add_argument(
        "--cache", type=Path, default=Path("candidates/wseg_scope_embeddings.npz")
    )
    parser.add_argument(
        "--base-profile", type=Path, default=Path("models/ood_profile.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("candidates/ood_profile_wseg_mlp.json")
    )
    parser.add_argument(
        "--report", type=Path, default=Path("reports/ai_evidence/wseg_mlp_gate.json")
    )
    parser.add_argument("--max-id-fpr", type=float, default=0.05)
    parser.add_argument("--epochs", type=int, default=70)
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()

    cached = np.load(args.cache, allow_pickle=False)
    arrays = {name: cached[name].astype(np.float32) for name in cached.files}
    required = {
        "id_train", "id_validation", "id_test", "local_train", "local_validation",
        "local_test", "wound_train", "wound_validation", "wound_test",
        "scin_train", "scin_calibration",
    }
    missing = sorted(required.difference(arrays))
    if missing:
        raise ValueError(f"Cache thiếu các mảng: {', '.join(missing)}")

    train_id = np.concatenate([arrays["id_train"], arrays["scin_train"]])
    train_ood = np.concatenate([arrays["local_train"], arrays["wound_train"]])
    train_x_raw = np.concatenate([train_id, train_ood])
    train_y = np.concatenate(
        [np.zeros(len(train_id), dtype=np.float32), np.ones(len(train_ood), dtype=np.float32)]
    )
    feature_mean = train_x_raw.mean(axis=0)
    feature_scale = train_x_raw.std(axis=0)
    feature_scale = np.where(feature_scale < 1e-6, 1.0, feature_scale)

    def scaled(name: str) -> np.ndarray:
        return ((arrays[name] - feature_mean) / feature_scale).astype(np.float32)

    train_x = ((train_x_raw - feature_mean) / feature_scale).astype(np.float32)
    validation = {
        "id": scaled("id_validation"),
        "scin": scaled("scin_calibration"),
        "local": scaled("local_validation"),
        "wound": scaled("wound_validation"),
    }
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    positive_weight = torch.tensor(
        [len(train_id) / max(1, len(train_ood))], dtype=torch.float32, device=device
    )
    loader = DataLoader(
        TensorDataset(torch.from_numpy(train_x), torch.from_numpy(train_y)),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
    )

    trials: list[dict] = []
    best: dict | None = None
    for hidden in (32, 64):
        for seed in (42, 43):
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
            model = ScopeMlp(train_x.shape[1], hidden).to(device)
            optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
            criterion = nn.BCEWithLogitsLoss(pos_weight=positive_weight)
            best_trial: dict | None = None
            stale = 0
            for epoch in range(1, args.epochs + 1):
                model.train()
                for inputs, targets in loader:
                    inputs = inputs.to(device)
                    targets = targets.to(device)
                    optimizer.zero_grad(set_to_none=True)
                    loss = criterion(model(inputs), targets)
                    loss.backward()
                    optimizer.step()

                id_scores = probabilities(model, validation["id"], device)
                scin_scores = probabilities(model, validation["scin"], device)
                local_scores = probabilities(model, validation["local"], device)
                wound_scores = probabilities(model, validation["wound"], device)
                threshold = threshold_for_id([id_scores, scin_scores], args.max_id_fpr)
                wound_recall = float((wound_scores >= threshold).mean())
                local_recall = float((local_scores >= threshold).mean())
                objective = wound_recall + 0.25 * local_recall
                if best_trial is None or objective > best_trial["objective"] + 1e-6:
                    best_trial = {
                        "hidden": hidden,
                        "seed": seed,
                        "epoch": epoch,
                        "objective": objective,
                        "threshold": threshold,
                        "internal_id_false_rejection_rate": float((id_scores >= threshold).mean()),
                        "scin_false_rejection_rate": float((scin_scores >= threshold).mean()),
                        "local_ood_rejection_rate": local_recall,
                        "wound_rejection_rate": wound_recall,
                        "state": copy.deepcopy(model.state_dict()),
                    }
                    stale = 0
                else:
                    stale += 1
                if stale >= 10:
                    break
            assert best_trial is not None
            trials.append({key: value for key, value in best_trial.items() if key != "state"})
            if best is None or best_trial["objective"] > best["objective"]:
                best = best_trial

    assert best is not None
    selected = ScopeMlp(train_x.shape[1], int(best["hidden"])).to(device)
    selected.load_state_dict(best["state"])
    threshold = float(best["threshold"])
    test_id = probabilities(selected, scaled("id_test"), device)
    test_local = probabilities(selected, scaled("local_test"), device)
    test_wound = probabilities(selected, scaled("wound_test"), device)
    test_id_fpr = rejection_rate(test_id, threshold)
    test_wound_recall = rejection_rate(test_wound, threshold)
    target_90_ready = bool(
        test_id_fpr is not None
        and test_wound_recall is not None
        and test_id_fpr <= 0.075
        and test_wound_recall >= 0.90
    )
    balanced_deployment_ready = bool(
        test_id_fpr is not None
        and test_wound_recall is not None
        and test_id_fpr <= 0.03
        and test_wound_recall >= 0.75
    )

    first: nn.Linear = selected.layers[0]  # type: ignore[assignment]
    second: nn.Linear = selected.layers[3]  # type: ignore[assignment]
    base = json.loads(args.base_profile.read_text(encoding="utf-8"))
    report = {
        "method": "frozen_feature_mlp_scope_gate_with_wseg",
        "model_version": base["model_version"],
        "selection": "Hyperparameters and epoch selected on validation data only.",
        "trials": trials,
        "selected": {key: value for key, value in best.items() if key != "state"},
        "held_out_test": {
            "id_count": len(test_id),
            "id_false_rejection_rate": test_id_fpr,
            "local_ood_count": len(test_local),
            "local_ood_rejection_rate": rejection_rate(test_local, threshold),
            "wound_count": len(test_wound),
            "wound_rejection_rate": test_wound_recall,
            "id_vs_wound": binary_metrics(test_id, test_wound),
        },
        "target_90_ready": target_90_ready,
        "balanced_deployment_ready": balanced_deployment_ready,
        "deployment_policy": "Balanced safety gate: wound rejection >= 75% and held-out ID false rejection <= 3%.",
        "limitations": [
            "WSeg is a clinical wound dataset and does not guarantee rejection of every superficial phone-photo scratch.",
            "The gate rejects unsupported images; it does not diagnose wounds.",
        ],
    }
    profile = {
        "schema_version": 4,
        "model_version": base["model_version"],
        "classes": base["classes"],
        "method": "frozen_feature_mlp_scope_gate",
        "score_threshold": threshold,
        "feature_mean": feature_mean.tolist(),
        "feature_scale": feature_scale.tolist(),
        "mlp_weights": [
            first.weight.detach().cpu().numpy().tolist(),
            second.weight.detach().cpu().numpy().tolist(),
        ],
        "mlp_biases": [
            first.bias.detach().cpu().numpy().tolist(),
            second.bias.detach().cpu().numpy().tolist(),
        ],
        "training_summary": report,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
