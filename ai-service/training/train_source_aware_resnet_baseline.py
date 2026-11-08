"""Fresh ImageNet ResNet50 baseline on repaired fold0; inner-only24epochs."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import time
import numpy as np
import torch
from torch.nn import functional as F
from threadpoolctl import threadpool_limits
from common import CLASSES, ImageSample, ImageSampleDataset, evaluation_transform, seed_everything
import train_v2 as trainer
import evaluate_original_eight_cancer_locked_fusion as metrics_base
from pilot_original_eight_imagenet_mixup import SeededDataset, state_sha
from pilot_original_eight_balanced_softmax import atomic_save

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / 'ai-service/reports/teacher_source_aware_inner_design_20261025'
OUT = ROOT / 'ai-service/reports/teacher_source_aware_resnet_baseline_fold0_seed42_20261026'
MODELS = ROOT / 'ai-service/candidates' / OUT.name
CONFIG = dict(architecture='resnet50', fold=0, seed=42, epochs=24, freeze_epochs=2,
    batch_size=16, workers=0, backbone_lr=5e-5, head_lr=2e-4, weight_decay=.0002,
    beta=.999, label_smoothing=.05, ema_decay=.995, gradient_clip=2., threads=4)
_spec = importlib.util.spec_from_file_location('source_aware_training_contract', DESIGN / 'training_contract.py')
contract = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(contract)
HANDLE = None


def utc(): return datetime.now(timezone.utc).isoformat()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p, x): Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def status(state, **items):
    row = dict(state=state, pid=os.getpid(), updated_utc=utc(), report=OUT.relative_to(ROOT).as_posix(), **items)
    write(OUT / 'status.json', row); write(ROOT / 'ai-service/reports/source_aware_training_status.json', row)


def process_lock():
    global HANDLE
    import msvcrt
    OUT.mkdir(parents=True, exist_ok=True); handle = (OUT / 'runner.lock').open('a+b')
    if handle.tell() == 0: handle.write(b'0'); handle.flush()
    handle.seek(0)
    try: msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError: handle.close(); raise RuntimeError('Baseline runner already active')
    HANDLE = handle


def assert_roles(roles):
    if set(roles) != {'train', 'inner_validation', 'outer_holdout'}: raise ValueError('Three locked roles required')
    for role, rows in roles.items():
        if len({r['path'] for r in rows}) != len(rows): raise ValueError('Repeated path in ' + role)
    for a, b in [('train', 'inner_validation'), ('train', 'outer_holdout'), ('inner_validation', 'outer_holdout')]:
        for key in ['path', 'sha256', 'group']:
            if {r[key] for r in roles[a]} & {r[key] for r in roles[b]}: raise ValueError('Role overlap: ' + key)


def smoothed_weighted_loss(logits, truth, weights, epsilon=.05):
    """NumPy reference used by tests/diagnostics; training uses torch CE."""
    logits = np.asarray(logits, dtype=float); truth = np.asarray(truth, dtype=int); weights = np.asarray(weights, dtype=float)
    z = logits - logits.max(1, keepdims=True); logp = z - np.log(np.exp(z).sum(1, keepdims=True))
    loss = -(1 - epsilon) * weights[truth] * logp[np.arange(len(truth)), truth]
    loss -= epsilon * (logp * weights).sum(1) / logits.shape[1]
    return float(loss.sum() / weights[truth].sum())


def backbone_sha(model):
    return state_sha({n: p.detach() for n, p in model.named_parameters() if not n.startswith('fc.')})


def samples(rows): return [ImageSample(ROOT / r['path'], CLASSES.index(r['label']), r['sha256'], r['group']) for r in rows]


def score(logits, truth, weights):
    tensor = torch.from_numpy(logits)
    q = tensor.softmax(1).numpy().astype(float); s = metrics_base.metrics(q.argmax(1), truth)
    s.update(top3_accuracy=float((np.argsort(q, axis=1)[:, -3:] == truth[:, None]).any(1).mean()),
        loss=float(F.cross_entropy(tensor, torch.tensor(truth, dtype=torch.long), weight=weights.cpu(), label_smoothing=.05)))
    return s, q


def infer(model, rows, weights):
    model.eval(); logits = []
    loader = trainer.make_loader(ImageSampleDataset(samples(rows), evaluation_transform()), 16, False, 0, True)
    with torch.inference_mode():
        for x, _ in loader: logits.append(model(x.cuda()).float().cpu().numpy())
    logits = np.concatenate(logits); truth = np.array([CLASSES.index(r['label']) for r in rows])
    s, q = score(logits, truth, weights); return s, q, logits


def objective(s): return [s['macro_f1'], s['top3_accuracy'], -s['loss']]


def verify(p):
    for path, h in p['frozen_sha256'].items(): assert sha(ROOT / path) == h, path
    assert sha(p['imagenet_path']) == p['imagenet_sha256']


def prepare():
    if (OUT / 'protocol.json').exists():
        p = read(OUT / 'protocol.json'); verify(p); return p
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    assert read(DESIGN / 'completion.json')['status'] == 'complete_verified_design_training_not_started'
    design = read(DESIGN / 'folds.json'); roles = {role: [dict(path=x, **design['manifest'][x]) for x in paths]
        for role, paths in design['folds'][0]['roles'].items()}; assert_roles(roles)
    assert [len(roles[r]) for r in ['train', 'inner_validation', 'outer_holdout']] == [4043, 718, 1176]
    for rows in roles.values():
        for r in rows: assert sha(ROOT / r['path']) == r['sha256'], r['path']
    seed_everything(42); initial = contract.load_fresh('resnet50', 0)
    initial_state = state_sha(initial.state_dict()); initial_backbone = backbone_sha(initial)
    MODELS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(MODELS / 'initial_head.npz', weight=initial.fc.weight.detach().numpy(), bias=initial.fc.bias.detach().numpy())
    init = read(DESIGN / 'training_contract.json')['initializers']['resnet50']; del initial
    counts = np.bincount([CLASSES.index(r['label']) for r in roles['train']], minlength=8)
    w = (1 - .999) / (1 - .999 ** counts); w /= w.mean()
    files = [Path(__file__), ROOT / 'ai-service/tests/test_source_aware_resnet_baseline.py',
        ROOT / 'tmp/review_source_aware_resnet_baseline_20261026.py', DESIGN / 'folds.json', DESIGN / 'protocol.json',
        DESIGN / 'completion.json', DESIGN / 'training_contract.json', DESIGN / 'training_contract.py',
        ROOT / 'ai-service/training/common.py', ROOT / 'ai-service/training/train_v2.py',
        ROOT / 'ai-service/training/pilot_original_eight_imagenet_mixup.py',
        ROOT / 'ai-service/training/pilot_original_eight_balanced_softmax.py',
        ROOT / 'ai-service/training/evaluate_original_eight_cancer_locked_fusion.py',
        ROOT / 'ai-service/app/config.py', ROOT / 'ai-service/models/best_model.pth',
        ROOT / 'ai-service/reports/active_research_track.json', OUT / 'dtype_fix_amendment.json',
        *sorted((OUT / 'v1_failure').glob('*.py')), OUT / 'v1_failure/protocol.json']
    p = dict(registered_utc=utc(), protocol_revision=2, dtype_amendment_sha256=sha(OUT / 'dtype_fix_amendment.json'),
        classes=CLASSES, roles=roles, configuration=CONFIG,
        frozen_sha256={f.relative_to(ROOT).as_posix(): sha(f) for f in files},
        imagenet_path=init['path'], imagenet_sha256=init['sha256'], initial_state_sha256=initial_state,
        initial_backbone_parameter_sha256=initial_backbone, class_counts=counts.tolist(), class_weights=w.tolist(),
        scope='OnefreshResNet50fold0reference onrepairedtrain4043/inner718, full24epochs regardlessresults. Notnew5foldOOF/ensemble,notainterventionclaim. Noouter/source-transfer inferenceorlegacygates.',
        initialization='ExactregisteredImageNetV2backbone plusfresh8classheadseed42. No DermAIcheckpoint/cachedembedding. ProtectedcontractvalidatesSHA. Allsamplegroups/SHAroleschecked.',
        training='Existingfreshplainrecipe: AdamWbackbone5e-5/head2e-4,wd.0002,weightedCEeffectivebeta.999/smoothing.05,clip2. Batch16workers0,eachoriginaltrainphotoonceperepoch. Epoch1/2backboneparametersfrozenbutBNrunningstatsupdate; epoch3..24fullunfreeze. Cosine22 afterwarmup eta1e-6. BF16forward/FP32loss/params/optimizer,noGradScaler. PerstepEMA.995overallfloatstates; integerbufferscopied.',
        augmentation='Originaltrain_v2V2operators. Ordermanualseed42+epoch. SeededDatasetaugmentation420000+epoch*10000+positionisolatesPython/NumPy/TorchCPU. NoMixUp,newsampling,lossorbackbone.',
        selection='EachEpochFP32raw/EMAinner. RankMacroF1,Top3,-globalweighted-smoothedCE; exactweighttiespreferraw. Bestepochstrictimprovementonly, earliesttie. Full24epochnoearlystop. Lockcheckpoint/reportbeforeanypotentialfutureouter use; do not compareold/newinnersasifsamephotos.',
        recovery='Atomicmodel/EMA/optimizer/scheduler/historycheckpointaftereachcompleteepoch; onresume rerunonlyuncommittedepochfromlastcheckpointwithsameepochseeds. Partialdiscardedworknotcountedascommittedupdates. Windowsrunnerfilelockpreventsduplicateinvocation.',
        limitations=['OnlyoneCNN/fold/seedandhistoricaldata. NewinnerSCINLupusonephoto/onegroup; any0or100%recallisnotstableevidence.',
            'Newbaselineisonanewinnerselectionprotocol; oldensembleinnercomparisonwouldleak. Globalretainedresearch/APIremainunchanged; no guaranteeofimprovement.',
            'Freshinitializationpreventslegacyweightseeingnewinnerduringtraining; doesnotmakehistoricallyinspectedouteranewpatienttest.'],
        intended_updates=24 * math.ceil(4043 / 16), new_CNN_fits=1, global_5937_score_changed=False,
        serving_changed=False, research_registry_changed=False,
        runtime=dict(torch=torch.__version__, gpu=torch.cuda.get_device_name(0)))
    write(OUT / 'protocol.json', p); status('registered', epochs=24); return p


def train(p):
    assert not (OUT / 'results.json').exists(), 'Preserve completed baseline'
    seed_everything(42); model = contract.load_fresh('resnet50', 0)
    assert state_sha(model.state_dict()) == p['initial_state_sha256']; model.cuda()
    ema = copy.deepcopy(model).eval().requires_grad_(False); backbone, head = trainer.classifier_parameters(model)
    opt = torch.optim.AdamW([dict(params=backbone, lr=5e-5), dict(params=head, lr=2e-4)], weight_decay=.0002)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=22, eta_min=1e-6)
    weights = torch.tensor(p['class_weights'], dtype=torch.float32, device='cuda'); criterion = torch.nn.CrossEntropyLoss(weight=weights, label_smoothing=.05)
    dataset = ImageSampleDataset(samples(p['roles']['train']), trainer.training_transform_v2())
    history = []; start = 1; best = None; resume = MODELS / 'resume_state.pth'
    if resume.exists():
        saved = torch.load(resume, map_location='cpu', weights_only=False)
        assert saved['protocol_sha256'] == sha(OUT / 'protocol.json')
        model.load_state_dict(saved['model']); ema.load_state_dict(saved['ema']); opt.load_state_dict(saved['optimizer']); scheduler.load_state_dict(saved['scheduler'])
        history = saved['history']; best = saved['best']; start = saved['epoch'] + 1; del saved
    for epoch in range(start, 25):
        began = time.monotonic(); seed_everything(42 + epoch)
        for param in backbone: param.requires_grad_(epoch > 2)
        model.train(); order = torch.randperm(len(dataset), generator=torch.Generator().manual_seed(42 + epoch)).tolist()
        loader = trainer.make_loader(SeededDataset(dataset, order, epoch), 16, False, 0, True)
        aug = hashlib.sha256(); labels = hashlib.sha256(); updates = 0; total_loss = 0.; correct = 0; probe = {}; ema_probe = {}
        status('training', epoch=epoch, total_epochs=24, batches=0, total_batches=len(loader), best_epoch=None if best is None else best['epoch'])
        for batch, (x, y) in enumerate(loader):
            aug.update(x.numpy().tobytes()); labels.update(y.numpy().tobytes()); x = x.cuda(); y = y.cuda(); opt.zero_grad(set_to_none=True)
            with torch.autocast('cuda', dtype=torch.bfloat16): logits = model(x)
            loss = criterion(logits.float(), y); assert torch.isfinite(loss); loss.backward()
            if batch == 0:
                probe = dict(logits=logits.detach().float().cpu().numpy(), targets=y.cpu().numpy(), loss=np.array(float(loss.detach())), fc_gradient=model.fc.weight.grad.detach().cpu().numpy().copy())
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 2, error_if_nonfinite=True); opt.step()
            if batch + 1 == len(loader):
                for key in ['fc.weight', 'bn1.running_mean']: ema_probe['before_' + key] = ema.state_dict()[key].detach().cpu().numpy().copy()
            trainer.update_ema(ema, model, .995)
            if batch + 1 == len(loader):
                for key in ['fc.weight', 'bn1.running_mean']:
                    ema_probe['model_' + key] = model.state_dict()[key].detach().cpu().numpy().copy(); ema_probe['after_' + key] = ema.state_dict()[key].detach().cpu().numpy().copy()
            if batch == 0: probe['gradient_norm_before_clip'] = np.array(float(norm))
            updates += 1; total_loss += float(loss.detach()); correct += int((logits.argmax(1) == y).sum())
            if (batch + 1) % 64 == 0: status('training', epoch=epoch, total_epochs=24, batches=batch + 1, total_batches=len(loader), seconds=time.monotonic() - began)
        assert updates == 253 and all(torch.isfinite(v).all() for v in model.state_dict().values() if v.is_floating_point())
        if epoch <= 2: assert backbone_sha(model) == p['initial_backbone_parameter_sha256']
        if epoch == 2: atomic_save(dict(model_state_dict=model.state_dict(), epoch=epoch, protocol_sha256=sha(OUT / 'protocol.json')), MODELS / 'warmup_model.pth')
        validation = {}; state_hashes = {}
        for source, chosen in [('raw', model), ('ema', ema)]:
            s, q, ll = infer(chosen, p['roles']['inner_validation'], weights); validation[source] = s; state_hashes[source] = state_sha(chosen.state_dict())
            np.savez_compressed(MODELS / f'epoch_{epoch:02d}_{source}_inner.npz', paths=[r['path'] for r in p['roles']['inner_validation']], probabilities=q, logits=ll)
        source = max(['raw', 'ema'], key=lambda n: (*objective(validation[n]), n == 'raw'))
        improved = best is None or tuple(objective(validation[source])) > tuple(best['objective'])
        if improved:
            best = dict(epoch=epoch, source=source, objective=objective(validation[source]), validation=validation[source], state_sha256=state_hashes[source])
            atomic_save(dict(model_state_dict=(model if source == 'raw' else ema).state_dict(), architecture='resnet50', classes=CLASSES,
                epoch=epoch, selected_weights=source, protocol_sha256=sha(OUT / 'protocol.json'), research_only=True), MODELS / 'best_model.pth')
        if epoch > 2: scheduler.step()
        row = dict(epoch=epoch, actual_updates=updates, online_train_loss=total_loss / updates, online_train_accuracy=correct / len(dataset),
            train_images=len(dataset), unique_images=len(set(order)), class_draw_counts=dict(Counter(p['roles']['train'][i]['label'] for i in order)),
            order_sha256=hashlib.sha256(json.dumps(order).encode()).hexdigest(), augmentation_sha256=aug.hexdigest(), labels_sha256=labels.hexdigest(),
            backbone_frozen=epoch <= 2, backbone_parameters_sha256=backbone_sha(model), validation=validation, model_state_sha256=state_hashes,
            selected_weights=source, selected_new_best=improved, best_epoch=best['epoch'], learning_rates_after_scheduler=[g['lr'] for g in opt.param_groups], seconds=time.monotonic() - began)
        np.savez_compressed(MODELS / f'epoch_{epoch:02d}_loss_probe.npz', **probe); np.savez_compressed(MODELS / f'epoch_{epoch:02d}_ema_probe.npz', **ema_probe)
        history.append(row); write(MODELS / 'history.json', history)
        atomic_save(dict(protocol_sha256=sha(OUT / 'protocol.json'), epoch=epoch, model=model.state_dict(), ema=ema.state_dict(), optimizer=opt.state_dict(), scheduler=scheduler.state_dict(), history=history, best=best), resume)
        status('epoch_committed', epoch=epoch, total_epochs=24, best_epoch=best['epoch'], macro_f1=validation[source]['macro_f1'], seconds=row['seconds'])
        print(json.dumps(dict(epoch=epoch, raw_accuracy=validation['raw']['accuracy'], raw_macro_f1=validation['raw']['macro_f1'], ema_accuracy=validation['ema']['accuracy'], ema_macro_f1=validation['ema']['macro_f1'], best_epoch=best['epoch'], seconds=row['seconds'])), flush=True)
    assert len(history) == 24
    write(MODELS / 'training_report.json', dict(epochs=24, actual_updates=sum(x['actual_updates'] for x in history),
        best=best, checkpoint_sha256=sha(MODELS / 'best_model.pth'), protocol_sha256=sha(OUT / 'protocol.json'), class_counts=p['class_counts'], class_weights=p['class_weights']))
    inner = p['roles']['inner_validation']; truth = np.array([CLASSES.index(r['label']) for r in inner])
    with np.load(MODELS / f"epoch_{best['epoch']:02d}_{best['source']}_inner.npz") as z: q = z['probabilities'].copy()
    np.savez_compressed(OUT / 'inner_selected_probabilities.npz', paths=[r['path'] for r in inner], truth=truth, probabilities=q)
    per_source = {}
    for name in ['original_train', 'SCIN']:
        ix = np.array([(r['source'] == name) for r in inner]); per_source[name] = metrics_base.metrics(q[ix].argmax(1), truth[ix])
    files = [*MODELS.glob('*.npz'), MODELS / 'best_model.pth', MODELS / 'warmup_model.pth', MODELS / 'history.json', MODELS / 'training_report.json']
    write(OUT / 'selection_locked.json', dict(locked_utc=utc(), best=best, artifacts_sha256={f.relative_to(ROOT).as_posix(): sha(f) for f in files}))
    write(OUT / 'results.json', dict(status='training_complete_awaiting_independent_review', best=best, inner_images=718, per_source=per_source,
        epochs=24, optimizer_updates=6072, new_CNN_fits=1, outer_scored=False, source_transfer_scored=False,
        global_5937_score_changed=False, serving_changed=False, protocol_sha256=sha(OUT / 'protocol.json')))
    verify(p); status('training_complete_awaiting_independent_review', epoch=24, total_epochs=24, best_epoch=best['epoch'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--prepare-only', action='store_true'); args = parser.parse_args()
    torch.set_num_threads(4); process_lock(); protocol = prepare()
    if not args.prepare_only:
        with threadpool_limits(limits=4): train(protocol)
