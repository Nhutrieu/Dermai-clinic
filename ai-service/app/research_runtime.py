"""Frozen eight-class E/G/S branches, with an explicitly separate serving vote.

No training/report imports, label lookup or patient/source metadata at runtime.
Vote shares are agreement scores, never calibrated disease probabilities.
"""
from dataclasses import dataclass, field
import base64
import hashlib
import io
import json
from pathlib import Path
from threading import RLock

import cv2
import numpy as np
import torch
from PIL import Image
from torch import nn

from .model import CLASSES, DISCLAIMER, GradCam, ModelBundle, OutOfScopeImageError, load_bundle, preprocess_image
from .ood import is_out_of_scope

CANCER = 5
SPECIAL = np.array([3, 4, 6, 2])


def softmax(values):
    values = np.asarray(values, dtype=np.float64)
    values = np.exp(values - values.max(axis=-1, keepdims=True))
    return values / values.sum(axis=-1, keepdims=True)


def classwise(parents, weights):
    arrays = [np.asarray(p, dtype=np.float64) for p in parents]
    if len(arrays) != 3 or any(p.ndim != 2 or p.shape[1] != 8 or
            p.shape != arrays[0].shape or not np.isfinite(p).all() or (p < 0).any() or
            not np.allclose(p.sum(1), 1, atol=1e-6) for p in arrays):
        raise ValueError("Expected three aligned Nx8 parent distributions")
    u = (1 - weights) * arrays[0] + weights * arrays[1]
    return u / u.sum(1, keepdims=True)


def linear_probability(head, x):
    return softmax(((x - head['mean']) / head['scale']) @ head['coef'].T + head['intercept'])


def route_fold(parents, weights, protected, stack=None, gate=None, specialist_probability=None):
    """Exact retained per-fold decisions; no serving aggregation here."""
    bc = classwise(parents, np.asarray(weights))
    reference = bc.argmax(1)
    decision = reference.copy()
    allowed = np.array([i for i in range(8) if i not in protected], dtype=int)
    mask = ~np.isin(reference, protected)
    if len(allowed) and mask.any():
        mixture = .75 * bc + .25 * parents[2]
        decision[mask] = allowed[mixture[mask][:, allowed].argmax(1)]
    ensemble = decision.copy()
    if stack is not None and gate is not None:
        logp = [np.log(np.clip(p, 1e-7, 1)) for p in parents]
        q = linear_probability(stack, np.concatenate(logp, axis=1))
        candidate = decision.copy()
        noncancer = np.array([0, 1, 2, 3, 4, 6, 7])
        eligible = decision != CANCER
        candidate[eligible] = noncancer[q[eligible][:, noncancer].argmax(1)]
        row = np.arange(len(decision))
        columns = [v[row, candidate] - v[row, decision] for v in logp]
        lq = np.log(np.clip(q, 1e-7, 1))
        columns.append(lq[row, candidate] - lq[row, decision])
        votes = np.stack([p.argmax(1) for p in parents], 1)
        columns.append(((votes == candidate[:, None]).sum(1) - (votes == decision[:, None]).sum(1)) / 3)
        columns.append(np.mean([-np.sum(p * lp, 1) / np.log(8) for p, lp in zip(parents, logp)], 0))
        x = np.column_stack([*columns, np.eye(8)[decision], np.eye(8)[candidate]])
        if str(gate['kind']) == 'always_keep':
            score = np.zeros(len(x))
        else:
            z = (((x - gate['mean']) / gate['scale']) @ gate['coef'][0] + gate['intercept'][0])
            score = np.exp(-np.logaddexp(0, -z))
        switch = eligible & (candidate != CANCER) & (candidate != decision) & (score > 2 / 3)
        decision[switch] = candidate[switch]
    if specialist_probability is not None:
        pp = np.asarray(specialist_probability)
        if pp.shape != (len(decision), 5) or not np.isfinite(pp).all() or (pp < 0).any() or not np.allclose(pp.sum(1), 1, atol=1e-6):
            raise ValueError("Invalid specialist distribution")
        winner = pp.argmax(1)
        accepted = np.isin(decision, SPECIAL) & (winner < 4) & (pp.max(1) >= .8)
        decision[accepted] = SPECIAL[winner[accepted]]
    if not np.array_equal(decision == CANCER, reference == CANCER):
        raise RuntimeError("SkinCancer decision mask changed inside a fold")
    return decision, reference, bc, ensemble


def aggregate(decisions, references, bc):
    """Serving-only rule, fixed before evaluation: protected plurality vote.

    Ties use mean BC score, then canonical class order. Cancer membership is
    fixed to the BC vote. Returned shares stay raw counts even on override;
    they are not moved or renormalized to disguise disagreement.
    """
    decisions, references = np.asarray(decisions), np.asarray(references)
    if decisions.shape != (5,) or references.shape != (5,) or np.asarray(bc).shape != (5, 8):
        raise ValueError("Exactly five fold decisions required")
    if not np.isin(decisions, range(8)).all() or not np.isin(references, range(8)).all():
        raise ValueError("Unknown class index")
    if not np.array_equal(decisions == CANCER, references == CANCER):
        raise ValueError("Fold cancer votes changed")
    shares = np.bincount(decisions, minlength=8) / 5
    reference_shares = np.bincount(references, minlength=8) / 5
    mean = np.asarray(bc).mean(0)
    rank = lambda scores: sorted(range(8), key=lambda c: (-scores[c], -round(float(mean[c]), 12), c))
    base_winner = rank(reference_shares)[0]
    raw_order = rank(shares)
    winner = CANCER if base_winner == CANCER else next(c for c in raw_order if c != CANCER)
    order = [winner] + [c for c in raw_order if c != winner]
    override = winner != raw_order[0]
    tied = sum(shares == shares.max()) > 1
    return winner, order, shares, override, tied


class Specialist(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = nn.Linear(2048, 128)
        self.output = nn.Linear(128, 5)

    def forward(self, x):
        return self.output(torch.relu(self.encoder(x)))


@dataclass
class FoldBundle:
    members: tuple[ModelBundle, ...]
    weights: np.ndarray
    protected: list[int]
    stack: dict | None = None
    gate: dict | None = None
    specialist: nn.Module | None = None
    scaler: dict | None = None


@dataclass
class ResearchBundle:
    folds: tuple[FoldBundle, ...]
    ood_gate: ModelBundle
    version: str
    classes: list[str]
    device: torch.device
    lock: RLock = field(default_factory=RLock)


def checked_path(root, entry):
    path = (root / entry['path']).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"Missing or invalid research asset: {entry['path']}")
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    if h.hexdigest() != entry['sha256']:
        raise ValueError(f"Research asset SHA-256 mismatch: {entry['path']}")
    return path


def load_research(manifest_path):
    manifest_path = Path(manifest_path)
    m = json.loads(manifest_path.read_text(encoding='utf-8'))
    if m.get('schema_version') != 1 or m.get('classes') != CLASSES or m.get('aggregation') != 'protected_fold_vote_v1':
        raise ValueError("Unsupported research serving manifest")
    if [f['fold'] for f in m['folds']] != list(range(5)):
        raise ValueError("Five ordered folds required")
    root = manifest_path.parent
    # Verify ALL package files before loading any tensors; no silent B0 fallback.
    for entry in m['assets'].values():
        checked_path(root, entry)
    asset = lambda key: checked_path(root, m['assets'][key])
    def arrays(key):
        with np.load(asset(key), allow_pickle=False) as a:
            return {k: a[k].copy() for k in a.files}
    ood = load_bundle(asset('ood_model'), asset('ood_profile'))
    if ood is None or ood.ood_profile is None or ood.classes != CLASSES:
        raise ValueError("Compatible OOD gate required")
    folds = []
    for f in m['folds']:
        members = tuple(load_bundle(asset(key)) for key in f['members'])
        if len(members) != 3 or any(v is None or v.classes != CLASSES or v.device != ood.device or v.temperature != 1 for v in members):
            raise ValueError("Incompatible parent checkpoints")
        weights = np.asarray(f['convnext_weights'], dtype=float)
        if weights.shape != (8,) or not np.isin(weights, [.25, .5, .75]).all() or CANCER not in f['protected']:
            raise ValueError("Invalid fold fusion policy")
        stack, gate = arrays(f['stack']) if f.get('stack') else None, arrays(f['gate']) if f.get('gate') else None
        if (stack is None) != (gate is None):
            raise ValueError("Stack and gate must be supplied together")
        if stack is not None:
            if stack['coef'].shape != (8, 24) or not np.array_equal(stack['classes'], np.arange(8)) or (stack['scale'] <= 0).any():
                raise ValueError("Invalid stacking parameters")
            if str(gate['kind']) not in ['logistic', 'always_keep'] or gate['mean'].shape != (22,) or (gate['scale'] <= 0).any():
                raise ValueError("Invalid gate parameters")
        specialist, scaler = None, None
        if f.get('specialist'):
            scaler = arrays(f['scaler'])
            if scaler['mean'].shape != (2048,) or (scaler['scale'] <= 0).any():
                raise ValueError("Invalid specialist scaler")
            specialist = Specialist()
            ck = torch.load(asset(f['specialist']), map_location='cpu', weights_only=True)
            specialist.load_state_dict(ck['model_state_dict'])
            specialist = specialist.to(ood.device).eval()
        folds.append(FoldBundle(members, weights, f['protected'], stack, gate, specialist, scaler))
    return ResearchBundle(tuple(folds), ood, m['name'], CLASSES.copy(), ood.device)


def predict_research(bundle, image, confidence_threshold=.7, confidence_margin_threshold=.2, normalized_entropy_threshold=.65):
    with bundle.lock:
        return _predict_locked(bundle, image, confidence_threshold, confidence_margin_threshold, normalized_entropy_threshold)


def _predict_locked(bundle, image, confidence_threshold, margin_threshold, entropy_threshold):
    x, base = preprocess_image(image)
    x = x.unsqueeze(0).to(bundle.device)
    embedding = bundle.ood_gate.extract_embeddings(x)[0].cpu().numpy()
    rejected, _ = is_out_of_scope(embedding, bundle.ood_gate.ood_profile)
    if rejected:
        raise OutOfScopeImageError("Ảnh nằm ngoài phạm vi tám nhóm bệnh được hỗ trợ. Vui lòng chọn ảnh tổn thương da khác hoặc khám trực tiếp.")
    decisions, references, bcs = [], [], []
    for f in bundle.folds:
        pp, features = [], []
        handle = None
        if f.specialist is not None:
            handle = f.members[2].model.avgpool.register_forward_hook(lambda _m, _a, y: features.append(y.flatten(1)))
        try:
            with torch.no_grad():
                for member in f.members:
                    pp.append(member.model(x).softmax(1).cpu().numpy().astype(np.float64))
                sp = None
                if f.specialist is not None:
                    # sklearn scaler uses float64 arithmetic before float32 head input.
                    z = (features[0].cpu().numpy() - f.scaler['mean']) / f.scaler['scale']
                    sp = f.specialist(torch.from_numpy(z.astype(np.float32)).to(bundle.device)).softmax(1).cpu().numpy()
        finally:
            if handle is not None:
                handle.remove()
        d, ref, bc, _ = route_fold(pp, f.weights, f.protected, f.stack, f.gate, sp)
        decisions.append(int(d[0])); references.append(int(ref[0])); bcs.append(bc[0])
    winner, order, shares, override, tied = aggregate(decisions, references, bcs)
    entropy = float(-np.sum(shares * np.log(np.clip(shares, 1e-12, 1))) / np.log(8))
    other = max(shares[c] for c in range(8) if c != winner)
    uncertain = bool(override or tied or shares[winner] < confidence_threshold or shares[winner] - other < margin_threshold or entropy > entropy_threshold)
    # Display an illustrative parent CAM, not a false gradient of discrete voting.
    cam_member = bundle.folds[0].members[0]
    with GradCam(cam_member.model, cam_member.target_layer) as cam:
        heat = cam.create(x, winner)
    cam_member.model.zero_grad(set_to_none=True)
    heat = cv2.resize(heat, (224, 224))
    color = cv2.cvtColor(cv2.applyColorMap(np.uint8(255 * heat), cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB)
    stream = io.BytesIO()
    Image.fromarray(np.uint8(.55 * base + .45 * color)).save(stream, format='PNG')
    return dict(disease=CLASSES[winner], confidence=round(float(shares[winner]), 6),
                top3=[dict(label=CLASSES[c], probability=round(float(shares[c]), 6)) for c in order[:3]],
                gradcam_image='data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode(),
                model_version=bundle.version, uncertain=uncertain, disclaimer=DISCLAIMER,
                score_type='fold_vote_fraction', confidence_is_calibrated=False,
                decision_policy_applied=override, gradcam_method='illustrative_b0_fold0',
                fold_decisions=[CLASSES[d] for d in decisions])
