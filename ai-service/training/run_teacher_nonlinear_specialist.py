"""Isolate ReLU in an original-train-only, frozen-feature specialist.

Identical 2048->128->5 factorized heads: identity control versus ReLU.
The completed Macro-F1 gate is the frozen reference, never fitted again.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

import run_teacher_macro_f1_gate as gate
import run_teacher_balanced_specialist as cache

prior = cache.previous
base = prior.base
ROOT = base.ROOT
NAME = 'teacher_nonlinear_specialist_seed42_20261023'
OUT = ROOT / 'ai-service/reports' / NAME
MODELS = ROOT / 'ai-service/candidates' / NAME
ARMS = ['linear_control', 'nonlinear_specialist']
CONFIG = dict(seed=42, epochs=20, batch_size=64, hidden=128,
              learning_rate=.0003, weight_decay=.001, gradient_clip=2.,
              threshold=.8, precision='CPU FP32, two torch threads',
              loss='Unweighted five-way CrossEntropyLoss, mean reduction')
TOL = 1e-12


def utc():
    return datetime.now(timezone.utc).isoformat()


class Head(nn.Module):
    def __init__(self, nonlinear: bool):
        super().__init__()
        self.nonlinear = nonlinear
        self.encoder = nn.Linear(2048, 128)
        self.output = nn.Linear(128, 5)
        nn.init.zeros_(self.output.weight)
        nn.init.zeros_(self.output.bias)

    def forward(self, x):
        z = self.encoder(x)
        return self.output(F.relu(z) if self.nonlinear else z)


def sampling(n, epoch):
    return torch.randperm(n, generator=torch.Generator().manual_seed(20261023 + epoch))


def state_sha(state):
    h = hashlib.sha256()
    for name, tensor in sorted(state.items()):
        h.update(name.encode()); h.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def mean_focus(score, key='f1'):
    return float(np.mean([score['per_class'][base.CLASSES[i]][key] for i in prior.FOCUS]))


def route(current, probability):
    return prior.route(current, probability)


def choose(decisions, truth):
    scores = {name: base.metrics(pred, truth) for name, pred in decisions.items()}
    trials = {name: dict(metrics=s, guard_failures=prior.failures(s, scores['current_gate']))
              for name, s in scores.items()}
    candidate, control = scores['nonlinear_specialist'], scores['linear_control']
    if candidate['macro_f1'] + TOL < control['macro_f1']:
        trials['nonlinear_specialist']['guard_failures'].append('macro_f1_below_linear_control')
    if mean_focus(candidate) <= mean_focus(control) + TOL:
        trials['nonlinear_specialist']['guard_failures'].append('no_focus_mean_f1_gain_vs_linear_control')
    passing = [n for n, t in trials.items() if not t['guard_failures']]
    selected = max(passing, key=lambda n: (scores[n]['macro_f1'], mean_focus(scores[n], 'recall'),
                   scores[n]['accuracy'], n == 'current_gate', n == 'linear_control'))
    return dict(selected=selected, trials=trials)


def epoch_assess(pred, truth, reference):
    score = base.metrics(pred, truth)
    failed = prior.failures(score, reference)
    return score, failed, [int(not failed), score['macro_f1'], mean_focus(score), score['accuracy']]


def probability(model, x):
    model.eval()
    with torch.inference_mode():
        return model(x).softmax(1).numpy().astype(float)


def inner_reference(fold, paths):
    lock = base.read(gate.OUT / f'fold_{fold}/selection_locked.json')
    with np.load(gate.OUT / f'fold_{fold}/inner_crossfit.npz', allow_pickle=False) as z:
        assert z['paths'].tolist() == paths
        assert z['protocol_sha256'].item() == base.sha(gate.OUT / 'protocol.json')
        key = {'current_fusion': 'current', 'macro_f1_gate': 'utility_decision',
               'conservative_control': 'control_decision'}[lock['selected']]
        return z[key].copy(), z['truth'].copy()


def prepare():
    if (OUT / 'protocol.json').exists():
        p = base.read(OUT / 'protocol.json'); prior.verify(p); return p
    registry = base.read(ROOT / 'ai-service/reports/active_research_track.json')
    assert registry['next_experiment'] is None
    parent = base.read(prior.OUT / 'protocol.json'); prior.verify(parent)
    g = base.read(gate.OUT / 'protocol.json'); prior.verify(g)
    assert base.read(gate.OUT / 'completion.json')['status'] == 'complete_verified_exploratory'
    files = [Path(__file__), ROOT / 'ai-service/tests/test_teacher_nonlinear_specialist.py',
             Path(cache.__file__), Path(prior.__file__), gate.OUT / 'protocol.json',
             gate.OUT / 'results.json', gate.OUT / 'oof_decisions.json', gate.OUT / 'completion.json',
             gate.OUT / 'independent_review.json', gate.OUT / 'all_selections_locked.json']
    for f in range(5):
        files += [prior.OUT / f'B_specialist/fold_{f}/{role}_features.npz'
                  for role in ['train', 'inner_validation', 'outer_holdout']]
        files += [prior.MODELS / f'fold_{f}/specialist.npz',
                  gate.OUT / f'fold_{f}/inner_crossfit.npz', gate.OUT / f'fold_{f}/selection_locked.json']
    p = dict(name=NAME, registered_utc=utc(), classes=base.CLASSES, images=5937, folds=5,
             parent_protocol=(prior.OUT / 'protocol.json').relative_to(ROOT).as_posix(),
             current_gate_protocol=(gate.OUT / 'protocol.json').relative_to(ROOT).as_posix(),
             frozen_sha256={**parent['frozen_sha256'], **g['frozen_sha256'],
                 **{x.relative_to(ROOT).as_posix(): base.sha(x) for x in files}},
             configuration=CONFIG,
             intervention='Only change identity activation to ReLU between two Linear layers2048->128->5. Same parameter count and initial tensors. Output layer zero so initial logits exactly identical.',
             labels=['Lupus', 'Psoriasis', 'Tinea', 'Eczema', 'Other'],
             control='Factorized affine classifier trained with AdamW; not the old sklearn LBFGS logistic optimum. No LayerNorm/dropout or auxiliary data.',
             training='Original fold train feature cache only. Every train row exactly once per epoch, same deterministic permutation/batches in both arms.20epochs each, no early termination, classweights, mining or resampling.',
             scaling='Reuse old five-way head train-only StandardScaler and independently assert exact agreement with fit on current training cache. No validation/outer rows in scaler or gradients.',
             checkpoint='Each arm ranks routed inner guard-pass, MacroF1, meanweakF1, Accuracy, earliest tie, across20epochs. Allguard failures are reported; a saved best does not imply adoption.',
             reference='Completed MacroF1 validation-selected policy. Inner reference uses cached meta-held decisions by frozen fold choice, never final gate fitted back on its inner training rows. Outer reference reuses completed5937 path-keyed OOF artifact.',
             routing='Same weak4/Other route threshold>=.8; only current Lupus/Psoriasis/Tinea/Eczema may switch, Other abstains. Exact SkinCancer mask preserved. No threshold sweep.',
             selection='Original strict perweakRecall/F1 guards, Accuracy/MacroF1 nondecreasing against currentgate. ReLU additionally MacroF1>=linear and meanweakF1 strictly>linear. Rank MacroF1, meanweakRecall, Accuracy, tiescurrentthenlinear. Lock all5 before new outer evaluation.',
             reporting='Raw linear, raw ReLU and validation-selected versus originalfusion and currentgate; each disease/fold/source, groupbootstrap1000 paired differences vs currentgate. Truth-based all3wrong subgroup only descriptive after lock, never training filter.',
             new_CNN_fits=0, trainable_heads=10, serving_changed=False,
             limitations=g['limitations'] + [
                 'This is a local activation ablation, not a reproduction of a dermatology paper or a guaranteed cure for errors shared by all parents.',
                 'The old CNN features were fitted on original train and selected using inner labels. Specialist20checkpoint selection adds development exposure; no fresh independent test.',
                 'Identity arm is linear in input but has factorized nonconvex optimization, not an optimizer-matched replication of old one-layer LBFGS.',
                 'Same .8 threshold isolates activation but score distributions may differ; no disease calibration claim.',
                 'Inner currentgate crossfit scores and outer finalgate scores have different fit sizes. Five CNNfolds and oneheadseed are not multiseed validation.',
                 'No new source images or source-generalization conclusion from this experiment alone.'],
             references=['https://scikit-learn.org/stable/modules/neural_networks_supervised.html',
                         'https://docs.pytorch.org/docs/stable/generated/torch.nn.CrossEntropyLoss.html'])
    OUT.mkdir(parents=True, exist_ok=True)
    base.write(OUT / 'protocol.json', p)
    base.write(OUT / 'research_registry_before.json', registry)
    registry['next_experiment'] = OUT.relative_to(ROOT).as_posix()
    registry['next_experiment_status'] = 'registered_identity_vs_relu_original_only_specialist'
    base.write(ROOT / 'ai-service/reports/active_research_track.json', registry)
    return p


def fit_all(p):
    assert not (OUT / 'all_selections_locked.json').exists(), 'Preserve completed training'
    parent = base.read(ROOT / p['parent_protocol'])
    for f in range(5):
        folder = OUT / f'fold_{f}'; folder.mkdir(parents=True, exist_ok=True)
        paths, raw, _ = cache.cached(f, 'train', parent)
        assert paths == parent['folds'][f]['roles']['train']
        labels = np.array([base.CLASSES.index(parent['manifest'][x]['class']) for x in paths])
        target = np.array([prior.SPECIAL.index(int(i)) if i in prior.SPECIAL else 4 for i in labels])
        with np.load(prior.MODELS / f'fold_{f}/specialist.npz', allow_pickle=False) as z:
            mean, scale = z['mean'].copy(), z['scale'].copy()
        scaler = StandardScaler().fit(raw)
        assert np.allclose(mean, scaler.mean_, atol=1e-10, rtol=0)
        assert np.allclose(scale, scaler.scale_, atol=1e-10, rtol=0)
        np.savez_compressed(folder / 'scaler.npz', mean=mean, scale=scale)
        def tensor(x): return torch.from_numpy(((x-mean)/scale).astype(np.float32))
        train_x, train_y = tensor(raw), torch.as_tensor(target, dtype=torch.long)
        inner_paths, xx, _ = cache.cached(f, 'inner_validation', parent)
        current, truth = inner_reference(f, inner_paths)
        assert truth.tolist() == [base.CLASSES.index(parent['manifest'][x]['class']) for x in inner_paths]
        inner_x = tensor(xx); ref_score = base.metrics(current, truth)
        validation = {}; histories = {}; initial_states = []
        for arm in ARMS:
            dest = MODELS / f'fold_{f}' / arm; dest.mkdir(parents=True, exist_ok=True)
            torch.manual_seed(CONFIG['seed']); model = Head(arm == 'nonlinear_specialist')
            initial = {k: v.clone() for k, v in model.state_dict().items()}
            initial_states.append(state_sha(initial))
            assert np.array_equal(probability(model, inner_x), np.full((len(inner_x), 5), .2, dtype=np.float32).astype(float))
            optimizer = torch.optim.AdamW(model.parameters(), lr=CONFIG['learning_rate'], weight_decay=CONFIG['weight_decay'])
            history = []; best = None; updates = 0; first_gradient = None
            for epoch in range(1, CONFIG['epochs'] + 1):
                start = time.monotonic(); model.train(); order = sampling(len(train_x), epoch)
                total_loss = 0.
                for ids in order.split(CONFIG['batch_size']):
                    optimizer.zero_grad(set_to_none=True)
                    loss = F.cross_entropy(model(train_x[ids]), train_y[ids])
                    if not torch.isfinite(loss): raise FloatingPointError('Nonfinite specialist loss')
                    loss.backward()
                    if epoch == 1 and first_gradient is None:
                        first_gradient = float(model.encoder.weight.grad.abs().max())
                        assert first_gradient == 0.
                    nn.utils.clip_grad_norm_(model.parameters(), CONFIG['gradient_clip'], error_if_nonfinite=True)
                    optimizer.step(); total_loss += float(loss.detach()) * len(ids); updates += 1
                pp = probability(model, inner_x); pred = route(current, pp)
                score, failures, key = epoch_assess(pred, truth, ref_score)
                changed = {k: bool(not torch.equal(v, initial[k])) for k, v in model.state_dict().items()}
                assert all(changed.values()), changed
                improved = best is None or tuple(key) > tuple(best['objective'])
                if improved:
                    best = dict(epoch=epoch, objective=key, metrics=score, guard_failures=failures)
                    torch.save(dict(model_state_dict=model.state_dict(), arm=arm, epoch=epoch,
                                    protocol_sha256=base.sha(OUT / 'protocol.json')), dest / 'best_model.pth')
                history.append(dict(epoch=epoch, loss=total_loss/len(train_x), actual_updates=len(order.split(CONFIG['batch_size'])),
                    sampling_sha256=hashlib.sha256(order.numpy().tobytes()).hexdigest(), metrics=score,
                    guard_failures=failures, objective=key, best_epoch=best['epoch'], new_best=improved,
                    tensor_changed_from_initial=changed, seconds=time.monotonic()-start))
                base.write(dest / 'history.json', history)
                base.write(OUT / 'status.json', dict(state='training', fold=f, arm=arm, epoch=epoch, utc=utc()))
                if epoch % 5 == 0:
                    print(dict(fold=f, arm=arm, epoch=epoch, loss=history[-1]['loss'], best=best['epoch']), flush=True)
            torch.save(dict(model_state_dict=model.state_dict(), optimizer_state_dict=optimizer.state_dict(),
                            protocol_sha256=base.sha(OUT / 'protocol.json')), dest / 'last_state.pth')
            model.load_state_dict(torch.load(dest / 'best_model.pth', weights_only=False)['model_state_dict'])
            validation[arm] = probability(model, inner_x); histories[arm] = history
            np.savez_compressed(dest / 'validation_probabilities.npz', paths=inner_paths, probability=validation[arm])
            base.write(dest / 'training_report.json', dict(fold=f, arm=arm, epochs=20, actual_updates=updates,
                train_images=len(paths), target_counts=np.bincount(target, minlength=5).tolist(), best=best,
                initial_state_sha256=initial_states[-1], first_encoder_gradient_max=first_gradient,
                trainable_parameters=sum(t.numel() for t in model.parameters()), checkpoint_sha256=base.sha(dest / 'best_model.pth')))
        assert initial_states[0] == initial_states[1]
        assert [h['sampling_sha256'] for h in histories[ARMS[0]]] == [h['sampling_sha256'] for h in histories[ARMS[1]]]
        decisions = dict(current_gate=current, **{a: route(current, q) for a, q in validation.items()})
        selection = choose(decisions, truth)
        np.savez_compressed(folder / 'inner_decisions.npz', paths=inner_paths, truth=truth, **decisions,
                            **{a+'_probability': q for a, q in validation.items()})
        artifacts = [folder / 'scaler.npz', folder / 'inner_decisions.npz', *(MODELS / f'fold_{f}').rglob('*')]
        selection.update(locked_utc=utc(), protocol_sha256=base.sha(OUT / 'protocol.json'),
                         artifacts_sha256={x.relative_to(ROOT).as_posix(): base.sha(x) for x in artifacts if x.is_file()})
        base.write(folder / 'selection_locked.json', selection)
        print(dict(fold=f, selected=selection['selected'], failures={n:t['guard_failures'] for n,t in selection['trials'].items()}), flush=True)
    base.write(OUT / 'all_selections_locked.json', dict(locked_utc=utc(),
               protocol_sha256=base.sha(OUT / 'protocol.json'),
               selections_sha256={str(f): base.sha(OUT / f'fold_{f}/selection_locked.json') for f in range(5)},
               actual_heads=10, epochs_each=20, new_CNN_fits=0))
    prior.verify(p)


def evaluate(p):
    assert not (OUT / 'results.json').exists(), 'Preserve completed evaluation'
    parent = base.read(ROOT / p['parent_protocol']); locks = base.read(OUT / 'all_selections_locked.json')
    assert locks['selections_sha256'] == {str(f): base.sha(OUT / f'fold_{f}/selection_locked.json') for f in range(5)}
    frozen_rows = {r['path']: r for r in base.read(gate.OUT / 'oof_decisions.json')}
    rows = []; started = utc()
    for f in range(5):
        lock = base.read(OUT / f'fold_{f}/selection_locked.json')
        for path, digest in lock['artifacts_sha256'].items(): assert base.sha(ROOT / path) == digest
        raw_rows, _, _, baseline = prior.outer_rows(parent, f)
        paths, xx, _ = cache.cached(f, 'outer_holdout', parent)
        assert paths == [r['path'] for r in raw_rows]
        current = np.array([frozen_rows[x]['predictions']['validation_selected'] for x in paths])
        with np.load(OUT / f'fold_{f}/scaler.npz', allow_pickle=False) as z:
            x = torch.from_numpy(((xx-z['mean'])/z['scale']).astype(np.float32))
        decisions = dict(original_fusion=baseline, current_gate=current); probs = {}
        for arm in ARMS:
            model = Head(arm == 'nonlinear_specialist')
            model.load_state_dict(torch.load(MODELS / f'fold_{f}' / arm / 'best_model.pth', weights_only=False)['model_state_dict'])
            probs[arm] = probability(model, x); decisions[arm] = route(current, probs[arm])
        decisions['validation_selected'] = decisions[lock['selected']]
        rr = prior.records(raw_rows, f, decisions)
        for i, r in enumerate(rr):
            parents = [int(np.argmax(raw_rows[i]['probabilities'][k])) for k in gate.old.stack.PARENTS]
            truth = base.CLASSES.index(r['label'])
            r.update(parent_top1=parents, all_three_wrong=all(v != truth for v in parents))
        rows += rr
        np.savez_compressed(OUT / f'fold_{f}/outer_probabilities.npz', paths=paths,
                            **{a+'_probability': q for a, q in probs.items()})
    rows.sort(key=lambda r:r['path']); assert len(rows) == len({r['path'] for r in rows}) == 5937
    y = np.array([base.CLASSES.index(r['label']) for r in rows])
    current = np.array([r['predictions']['current_gate'] for r in rows]); methods = {}
    def effect(pred, mask):
        return dict(images=int(mask.sum()), changed=int(((pred!=current)&mask).sum()),
                    corrected=int(((pred==y)&(current!=y)&mask).sum()), broken=int(((pred!=y)&(current==y)&mask).sum()))
    for name in rows[0]['predictions']:
        pred = np.array([r['predictions'][name] for r in rows]); assert np.array_equal(pred==5, current==5)
        score = base.metrics(pred, y)
        score.update(correct=int((pred==y).sum()), **{k:v for k,v in effect(pred, np.ones(len(y), bool)).items() if k!='images'},
                     paired_delta_vs_current_95pct=prior.paired_intervals(rows, pred, current, y))
        score['per_source'] = {s:dict(images=int((mask:=np.array([r['source']==s for r in rows])).sum()),
                                        **base.metrics(pred[mask], y[mask])) for s in ['original_train', 'SCIN']}
        score['error_subgroups'] = {}
        for label, mask in [('all_three_wrong', np.array([r['all_three_wrong'] for r in rows])),
                            ('at_least_one_parent_right', np.array([not r['all_three_wrong'] for r in rows]))]:
            score['error_subgroups'][label] = effect(pred, mask)
        methods[name] = score
    previous = base.read(gate.OUT / 'results.json')['methods']['validation_selected']
    assert methods['current_gate']['confusion_matrix'] == previous['confusion_matrix']
    per_fold = []
    for f in range(5):
        mask = np.array([r['fold']==f for r in rows])
        per_fold.append(dict(fold=f, selected=base.read(OUT / f'fold_{f}/selection_locked.json')['selected'],
            methods={n:base.metrics(np.array([r['predictions'][n] for r in rows])[mask], y[mask]) for n in methods}))
    result = dict(status='complete_exploratory_identity_vs_relu_specialist', images=5937, methods=methods,
                  per_fold=per_fold, outer_started_utc=started, completed_utc=utc(),
                  protocol_sha256=base.sha(OUT / 'protocol.json'), all_selections_sha256=base.sha(OUT / 'all_selections_locked.json'),
                  trainable_heads=10, epochs_each=20, new_CNN_fits=0, reference_baseline_changed=False,
                  serving_changed=False, limitations=p['limitations'])
    base.write(OUT / 'oof_decisions.json', rows); base.write(OUT / 'results.json', result); prior.verify(p)
    base.write(OUT / 'verification.json', dict(status='PASS', results_sha256=base.sha(OUT / 'results.json'),
               all_five_locked_before_outer=True, train_only_scaler=True, identical_initial_states_and_batches=True,
               exact_cancer_mask=True, new_CNN_fits=0))
    base.write(OUT / 'status.json', dict(state='complete', utc=utc()))
    print({n:{k:s[k] for k in ['accuracy','macro_f1','correct']} for n,s in methods.items()}, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(); torch.set_num_threads(2); torch.use_deterministic_algorithms(True)
    with threadpool_limits(limits=1):
        p = prepare()
        if not args.prepare_only:
            fit_all(p); evaluate(p)


if __name__ == '__main__':
    main()
