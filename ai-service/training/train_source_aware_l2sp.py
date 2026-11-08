"""Matched fresh-ImageNet L2-SP addition; repaired fold0, inner only."""
from collections import Counter
from pathlib import Path
import argparse
import copy
import hashlib
import json
import math
import time
import numpy as np
import torch
from threadpoolctl import threadpool_limits
import train_source_aware_resnet_baseline as base

ROOT = base.ROOT
REFERENCE = base.OUT
REFERENCE_MODELS = base.MODELS
OUT = ROOT / 'ai-service/reports/teacher_source_aware_l2sp_fold0_seed42_20261026'
MODELS = ROOT / 'ai-service/candidates' / OUT.name
ALPHA = .01


def anchor_penalty(model, reference, alpha=ALPHA):
    """Unnormalized FP32 parameter sum, excluding the new classifier and buffers."""
    terms = [(v - reference[n]).square().sum() for n, v in model.named_parameters()
             if not n.startswith('fc.') and v.requires_grad]
    return .5 * alpha * torch.stack(terms).sum() if terms else next(model.parameters()).new_zeros(())


def assessment(candidate, reference):
    eps = 1e-12
    checks = dict(accuracy=candidate['accuracy'] >= reference['accuracy'] - .005 - eps,
                  macro_f1=candidate['macro_f1'] > reference['macro_f1'] + eps)
    for c in base.CLASSES:
        a, b = candidate['per_class'][c], reference['per_class'][c]
        floor = 0. if c in ['Lupus', 'Psoriasis', 'Tinea', 'SkinCancer'] else .02
        checks[c + '_recall'] = a['recall'] >= b['recall'] - floor - eps
        if c in ['Lupus', 'Psoriasis', 'Tinea']:
            checks[c + '_f1'] = a['f1'] >= b['f1'] - eps
            checks[c + '_precision'] = a['precision'] >= b['precision'] - .02 - eps
    weak = ['Lupus', 'Psoriasis', 'Tinea']
    checks['weak_mean_f1'] = sum(candidate['per_class'][c]['f1'] for c in weak) > sum(reference['per_class'][c]['f1'] for c in weak) + eps
    return dict(passed=all(checks.values()), checks=checks)


def prepare():
    if (OUT / 'protocol.json').exists():
        p = base.read(OUT / 'protocol.json'); base.verify(p); return p
    assert base.read(REFERENCE / 'completion.json')['status'] == 'complete_verified_fresh_baseline_inner_only'
    rp = base.read(REFERENCE / 'protocol.json'); base.verify(rp)
    base.assert_roles(rp['roles'])
    for rows in rp['roles'].values():
        for r in rows: assert base.sha(ROOT / r['path']) == r['sha256']
    initial = base.contract.load_fresh('resnet50', 0)
    assert base.state_sha(initial.state_dict()) == rp['initial_state_sha256']
    MODELS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(MODELS / 'initial_head.npz', weight=initial.fc.weight.detach().numpy(), bias=initial.fc.bias.detach().numpy())
    files = [Path(__file__), ROOT / 'ai-service/tests/test_source_aware_l2sp.py',
             ROOT / 'tmp/review_source_aware_l2sp_20261026.py',
             ROOT / 'tmp/review_source_aware_resnet_baseline_20261026_v4.py',
             ROOT / 'tmp/review_teacher_priorities_20261022.py',
             REFERENCE / 'protocol.json', REFERENCE / 'results.json', REFERENCE / 'completion.json',
             REFERENCE / 'independent_review.json', REFERENCE_MODELS / 'history.json',
             REFERENCE_MODELS / 'best_model.pth', REFERENCE_MODELS / 'warmup_model.pth',
             *[ROOT / path for path in rp['frozen_sha256']]]
    p = dict(registered_utc=base.utc(), classes=base.CLASSES, roles=rp['roles'],
             configuration=dict(base.CONFIG, l2sp_alpha=ALPHA),
             class_counts=rp['class_counts'], class_weights=rp['class_weights'],
             imagenet_path=rp['imagenet_path'], imagenet_sha256=rp['imagenet_sha256'],
             initial_state_sha256=rp['initial_state_sha256'],
             initial_backbone_parameter_sha256=rp['initial_backbone_parameter_sha256'],
             frozen_sha256={f.relative_to(ROOT).as_posix(): base.sha(f) for f in files},
             intervention='CE + alpha/2 * sum over pretrained backbone PARAMETERS of (w-w_ImageNet)^2; alpha=.01 fixed before training. Sum is NOT divided by parameter count. New fc and BN running buffers excluded. Same AdamW decay as baseline retained: adapted additive L2-SP, not exact paper reproduction.',
             source=dict(title='Explicit Inductive Bias for Transfer Learning with Convolutional Networks',
                         authors='Li, Grandvalet, Davoine', venue='ICML 2018',
                         url='https://proceedings.mlr.press/v80/li18a.html'),
             coefficient='Single pragmatic .01, not tuned or claimed optimal; no alpha, seed, threshold or backbone sweep.',
             matched='Same fresh ImageNet state, eight classes, repaired roles, 24 epochs, augmentation, epoch/order/RNG, optimizer groups, EMA, freeze2+unfreeze22, BN update behavior and raw/EMA selection as reference. Only added backbone anchoring loss. Not compute-time matched because penalty adds work.',
             selection='Rank each epoch raw/EMA by Macro F1, Top3, minus CE validation loss, exact raw tie/earliest epoch as baseline. Anchor penalty never added to validation score. After locking one checkpoint, assess against reference; do not search another epoch to pass guards.',
             guards='Accuracy drop <=.005; MacroF1 strict increase; SkinCancer recall no decrease; each Lupus/Psoriasis/Tinea recall and F1 no decrease, precision drop <=.02; weak mean F1 strict increase; other recalls drop <=.02. Prospective exploratory pilot rule, not historical ensemble promotion rule.',
             scope='One fresh CNN/fold/seed; only train and 718 inner. No outer/source transfer, no legacy embeddings/gates, no ensemble blending or deployment.',
             limitations=['Historically inspected development data; not new patient test.',
                          'SCIN Lupus inner one photo/one group; stable source improvement cannot be established.',
                          'A passing inner pilot would require broader matched evaluation; it cannot replace retained OOF or serving.'],
             intended_updates=6072, outer_scored=False, global_5937_score_changed=False, serving_changed=False)
    base.write(OUT / 'protocol.json', p); base.status('registered_l2sp', total_epochs=24); return p


def train(p):
    assert not (OUT / 'results.json').exists(), 'Preserve completed experiment'
    base.seed_everything(42); model = base.contract.load_fresh('resnet50', 0).cuda()
    assert base.state_sha(model.state_dict()) == p['initial_state_sha256']
    anchor = {n: v.detach().clone() for n, v in model.named_parameters() if not n.startswith('fc.')}
    ema = copy.deepcopy(model).eval().requires_grad_(False)
    backbone, head = base.trainer.classifier_parameters(model)
    opt = torch.optim.AdamW([dict(params=backbone, lr=5e-5), dict(params=head, lr=2e-4)], weight_decay=.0002)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=22, eta_min=1e-6)
    weights = torch.tensor(p['class_weights'], dtype=torch.float32, device='cuda')
    criterion = torch.nn.CrossEntropyLoss(weight=weights, label_smoothing=.05)
    dataset = base.ImageSampleDataset(base.samples(p['roles']['train']), base.trainer.training_transform_v2())
    history = []; best = None; start = 1; resume = MODELS / 'resume_state.pth'
    if resume.exists():
        saved = torch.load(resume, map_location='cpu', weights_only=False)
        assert saved['protocol_sha256'] == base.sha(OUT / 'protocol.json')
        model.load_state_dict(saved['model']); ema.load_state_dict(saved['ema'])
        opt.load_state_dict(saved['optimizer']); scheduler.load_state_dict(saved['scheduler'])
        history = saved['history']; best = saved['best']; start = saved['epoch'] + 1; del saved
    for epoch in range(start, 25):
        began = time.monotonic(); base.seed_everything(42 + epoch)
        for v in backbone: v.requires_grad_(epoch > 2)
        model.train(); order = torch.randperm(len(dataset), generator=torch.Generator().manual_seed(42 + epoch)).tolist()
        loader = base.trainer.make_loader(base.SeededDataset(dataset, order, epoch), 16, False, 0, True)
        aug = hashlib.sha256(); labels = hashlib.sha256(); total_ce = 0.; total_anchor = 0.; correct = 0; updates = 0; probe = {}; ema_probe = {}
        base.status('training_l2sp', epoch=epoch, total_epochs=24, batches=0, total_batches=len(loader))
        if epoch == 4:
            base.atomic_save(dict(model_state_dict=model.state_dict(), protocol_sha256=base.sha(OUT / 'protocol.json')), MODELS / 'epoch04_before_probe.pth')
        for batch, (x, y) in enumerate(loader):
            aug.update(x.numpy().tobytes()); labels.update(y.numpy().tobytes()); x = x.cuda(); y = y.cuda(); opt.zero_grad(set_to_none=True)
            with torch.autocast('cuda', dtype=torch.bfloat16): logits = model(x)
            ce = criterion(logits.float(), y); penalty = anchor_penalty(model, anchor); loss = ce + penalty
            assert torch.isfinite(loss); loss.backward()
            if batch == 0:
                probe = dict(logits=logits.detach().float().cpu().numpy(), targets=y.cpu().numpy(),
                             loss=np.array(float(loss.detach())), ce=np.array(float(ce.detach())), penalty=np.array(float(penalty.detach())),
                             fc_gradient=model.fc.weight.grad.detach().cpu().numpy().copy())
                if epoch == 4:
                    probe['backbone_gradient'] = model.layer4[2].conv3.weight.grad.detach().cpu().numpy().copy()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 2, error_if_nonfinite=True); opt.step()
            if batch + 1 == len(loader):
                for key in ['fc.weight', 'bn1.running_mean']: ema_probe['before_' + key] = ema.state_dict()[key].detach().cpu().numpy().copy()
            base.trainer.update_ema(ema, model, .995)
            if batch + 1 == len(loader):
                for key in ['fc.weight', 'bn1.running_mean']:
                    ema_probe['model_' + key] = model.state_dict()[key].detach().cpu().numpy().copy()
                    ema_probe['after_' + key] = ema.state_dict()[key].detach().cpu().numpy().copy()
            if batch == 0: probe['gradient_norm_before_clip'] = np.array(float(norm))
            updates += 1; total_ce += float(ce.detach()); total_anchor += float(penalty.detach()); correct += int((logits.argmax(1) == y).sum())
            if (batch + 1) % 64 == 0:
                base.status('training_l2sp', epoch=epoch, total_epochs=24, batches=batch+1, total_batches=len(loader), seconds=time.monotonic()-began)
        assert updates == 253 and all(torch.isfinite(v).all() for v in model.state_dict().values() if v.is_floating_point())
        if epoch <= 2: assert base.backbone_sha(model) == p['initial_backbone_parameter_sha256']
        if epoch == 2: base.atomic_save(dict(model_state_dict=model.state_dict(), epoch=epoch, protocol_sha256=base.sha(OUT / 'protocol.json')), MODELS / 'warmup_model.pth')
        validation = {}; hashes = {}
        for source, chosen in [('raw', model), ('ema', ema)]:
            s, q, ll = base.infer(chosen, p['roles']['inner_validation'], weights); validation[source] = s; hashes[source] = base.state_sha(chosen.state_dict())
            np.savez_compressed(MODELS / f'epoch_{epoch:02d}_{source}_inner.npz', paths=[r['path'] for r in p['roles']['inner_validation']], probabilities=q, logits=ll)
        source = max(['raw', 'ema'], key=lambda n: (*base.objective(validation[n]), n == 'raw'))
        improved = best is None or tuple(base.objective(validation[source])) > tuple(best['objective'])
        if improved:
            best = dict(epoch=epoch, source=source, objective=base.objective(validation[source]), validation=validation[source], state_sha256=hashes[source])
            base.atomic_save(dict(model_state_dict=(model if source == 'raw' else ema).state_dict(), architecture='resnet50', classes=base.CLASSES,
                                  epoch=epoch, selected_weights=source, protocol_sha256=base.sha(OUT / 'protocol.json'), research_only=True), MODELS / 'best_model.pth')
        if epoch > 2: scheduler.step()
        row = dict(epoch=epoch, actual_updates=updates, online_train_loss=(total_ce+total_anchor)/updates,
                   online_ce=total_ce/updates, online_anchor=total_anchor/updates, online_train_accuracy=correct/len(dataset),
                   train_images=len(dataset), unique_images=len(set(order)), class_draw_counts=dict(Counter(p['roles']['train'][i]['label'] for i in order)),
                   order_sha256=hashlib.sha256(json.dumps(order).encode()).hexdigest(), augmentation_sha256=aug.hexdigest(), labels_sha256=labels.hexdigest(),
                   backbone_frozen=epoch<=2, backbone_parameters_sha256=base.backbone_sha(model), validation=validation,
                   model_state_sha256=hashes, selected_weights=source, selected_new_best=improved, best_epoch=best['epoch'],
                   learning_rates_after_scheduler=[g['lr'] for g in opt.param_groups], seconds=time.monotonic()-began)
        np.savez_compressed(MODELS / f'epoch_{epoch:02d}_loss_probe.npz', **probe)
        np.savez_compressed(MODELS / f'epoch_{epoch:02d}_ema_probe.npz', **ema_probe)
        history.append(row); base.write(MODELS / 'history.json', history)
        base.atomic_save(dict(protocol_sha256=base.sha(OUT / 'protocol.json'), epoch=epoch, model=model.state_dict(), ema=ema.state_dict(),
                              optimizer=opt.state_dict(), scheduler=scheduler.state_dict(), history=history, best=best), resume)
        base.status('epoch_committed_l2sp', epoch=epoch, total_epochs=24, best_epoch=best['epoch'], seconds=row['seconds'])
        print(json.dumps(dict(epoch=epoch, macro_f1=validation[source]['macro_f1'], best_epoch=best['epoch'], mean_anchor=row['online_anchor'], seconds=row['seconds'])), flush=True)
    inner = p['roles']['inner_validation']; y = np.array([base.CLASSES.index(r['label']) for r in inner])
    with np.load(MODELS / f"epoch_{best['epoch']:02d}_{best['source']}_inner.npz") as z: q = z['probabilities'].copy()
    np.savez_compressed(OUT / 'inner_selected_probabilities.npz', paths=[r['path'] for r in inner], truth=y, probabilities=q)
    per_source = {}
    for name in ['original_train', 'SCIN']:
        ix = np.array([r['source']==name for r in inner]); per_source[name] = base.metrics_base.metrics(q[ix].argmax(1), y[ix])
    ref = base.read(REFERENCE / 'results.json')['best']['validation']
    artifacts = [*MODELS.glob('*.npz'), *MODELS.glob('*.pth'), MODELS / 'history.json']
    base.write(OUT / 'selection_locked.json', dict(locked_utc=base.utc(), best=best, artifacts_sha256={f.relative_to(ROOT).as_posix():base.sha(f) for f in artifacts}))
    base.write(OUT / 'results.json', dict(status='training_complete_awaiting_independent_review', best=best, reference=ref,
               assessment=assessment(best['validation'], ref), per_source=per_source, epochs=24, optimizer_updates=6072,
               new_CNN_fits=1, outer_scored=False, source_transfer_scored=False, global_5937_score_changed=False, serving_changed=False,
               protocol_sha256=base.sha(OUT / 'protocol.json')))
    base.verify(p); base.status('training_complete_awaiting_independent_review', epoch=24, total_epochs=24, best_epoch=best['epoch'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--prepare-only', action='store_true'); args = parser.parse_args()
    torch.set_num_threads(4); base.OUT = OUT; base.MODELS = MODELS; base.process_lock(); protocol = prepare()
    if not args.prepare_only:
        with threadpool_limits(limits=4): train(protocol)
