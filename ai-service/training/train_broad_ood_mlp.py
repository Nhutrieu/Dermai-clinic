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


def rate(values: np.ndarray, threshold: float) -> float:
    return float((values >= threshold).mean()) if len(values) else 0.0


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
        description="Huấn luyện cổng MLP phát hiện ảnh ngoài phạm vi đa dạng."
    )
    parser.add_argument("--cache", type=Path, default=Path("candidates/broad_scope_embeddings.npz"))
    parser.add_argument("--base-profile", type=Path, default=Path("models/ood_profile.json"))
    parser.add_argument("--output", type=Path, default=Path("candidates/ood_profile_broad_mlp.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/ai_evidence/broad_ood_gate.json"))
    parser.add_argument("--max-id-fpr", type=float, default=0.03)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()

    cached = np.load(args.cache, allow_pickle=False)
    arrays = {name: cached[name].astype(np.float32) for name in cached.files}
    required = {
        "id_train", "id_validation", "id_test", "local_train", "local_validation",
        "local_test", "wound_train", "wound_validation", "wound_test",
        "scin_train", "scin_calibration", "broad_train", "broad_validation", "broad_test",
    }
    missing = sorted(required.difference(arrays))
    if missing:
        raise ValueError(f"Cache thiếu các mảng: {', '.join(missing)}")

    train_id = np.concatenate([arrays["id_train"], arrays["scin_train"]])
    train_ood = np.concatenate(
        [arrays["local_train"], arrays["wound_train"], arrays["broad_train"]]
    )
    train_raw = np.concatenate([train_id, train_ood])
    targets = np.concatenate(
        [np.zeros(len(train_id), dtype=np.float32), np.ones(len(train_ood), dtype=np.float32)]
    )
    feature_mean = train_raw.mean(axis=0)
    feature_scale = train_raw.std(axis=0)
    feature_scale = np.where(feature_scale < 1e-6, 1.0, feature_scale)

    def scaled(name: str) -> np.ndarray:
        return ((arrays[name] - feature_mean) / feature_scale).astype(np.float32)

    train_x = ((train_raw - feature_mean) / feature_scale).astype(np.float32)
    validation = {name: scaled(name) for name in (
        "id_validation", "scin_calibration", "local_validation",
        "wound_validation", "broad_validation"
    )}
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    positive_weight = torch.tensor(
        [len(train_id) / max(1, len(train_ood))], dtype=torch.float32, device=device
    )
    loader = DataLoader(
        TensorDataset(torch.from_numpy(train_x), torch.from_numpy(targets)),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
    )

    trials: list[dict] = []
    best: dict | None = None
    for hidden in (32, 64, 96):
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
                for inputs, batch_targets in loader:
                    inputs = inputs.to(device)
                    batch_targets = batch_targets.to(device)
                    optimizer.zero_grad(set_to_none=True)
                    loss = criterion(model(inputs), batch_targets)
                    loss.backward()
                    optimizer.step()

                scores = {
                    name: probabilities(model, matrix, device)
                    for name, matrix in validation.items()
                }
                threshold = threshold_for_id(
                    [scores["id_validation"], scores["scin_calibration"]],
                    args.max_id_fpr,
                )
                metrics = {
                    "internal_id_false_rejection_rate": rate(scores["id_validation"], threshold),
                    "scin_false_rejection_rate": rate(scores["scin_calibration"], threshold),
                    "local_ood_rejection_rate": rate(scores["local_validation"], threshold),
                    "wound_rejection_rate": rate(scores["wound_validation"], threshold),
                    "broad_ood_rejection_rate": rate(scores["broad_validation"], threshold),
                }
                objective = (
                    metrics["broad_ood_rejection_rate"]
                    + 0.75 * metrics["wound_rejection_rate"]
                    + 0.25 * metrics["local_ood_rejection_rate"]
                )
                if best_trial is None or objective > best_trial["objective"] + 1e-6:
                    best_trial = {
                        "hidden": hidden,
                        "seed": seed,
                        "epoch": epoch,
                        "objective": objective,
                        "threshold": threshold,
                        **metrics,
                        "state": copy.deepcopy(model.state_dict()),
                    }
                    stale = 0
                else:
                    stale += 1
                if stale >= 12:
                    break
            assert best_trial is not None
            trials.append({key: value for key, value in best_trial.items() if key != "state"})
            if best is None or best_trial["objective"] > best["objective"]:
                best = best_trial

    assert best is not None
    selected = ScopeMlp(train_x.shape[1], int(best["hidden"])).to(device)
    selected.load_state_dict(best["state"])
    threshold = float(best["threshold"])
    test = {name: probabilities(selected, scaled(name), device) for name in (
        "id_test", "local_test", "wound_test", "broad_test"
    )}
    held_out = {
        "id_count": len(test["id_test"]),
        "id_false_rejection_rate": rate(test["id_test"], threshold),
        "local_ood_count": len(test["local_test"]),
        "local_ood_rejection_rate": rate(test["local_test"], threshold),
        "wound_count": len(test["wound_test"]),
        "wound_rejection_rate": rate(test["wound_test"], threshold),
        "broad_ood_count": len(test["broad_test"]),
        "broad_ood_rejection_rate": rate(test["broad_test"], threshold),
        "id_vs_broad_ood": binary_metrics(test["id_test"], test["broad_test"]),
    }
    deployment_ready = bool(
        held_out["id_false_rejection_rate"] <= 0.04
        and held_out["wound_rejection_rate"] >= 0.75
        and held_out["broad_ood_rejection_rate"] >= 0.85
    )

    first: nn.Linear = selected.layers[0]  # type: ignore[assignment]
    second: nn.Linear = selected.layers[3]  # type: ignore[assignment]
    base = json.loads(args.base_profile.read_text(encoding="utf-8"))
    report = {
        "method": "frozen_feature_mlp_scope_gate_with_wseg_and_caltech101",
        "model_version": base["model_version"],
        "selection": "Hyperparameters, epoch and threshold selected on validation data only.",
        "trials": trials,
        "selected": {key: value for key, value in best.items() if key != "state"},
        "held_out_test": held_out,
        "deployment_ready": deployment_ready,
        "deployment_policy": "Held-out ID false rejection <= 4%, wound rejection >= 75%, broad OOD rejection >= 85%.",
        "limitations": [
            "No finite dataset guarantees rejection of every possible uploaded image.",
            "The gate only rejects unsupported content; it does not diagnose non-skin images or wounds.",
            "Caltech 101 is used only as broad negative/OOD data and never as a disease class.",
        ],
    }
    profile = {
        "schema_version": 5,
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
    for key in ("hard_negative_exemplars", "hard_negative_similarity_threshold"):
        if key in base:
            profile[key] = base[key]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not deployment_ready:
        raise SystemExit("Candidate không đạt chính sách triển khai; chưa thay profile đang chạy.")


if __name__ == "__main__":
    main()
