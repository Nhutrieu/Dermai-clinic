"""Matched hidden-dropout ablation on the frozen ResNet specialist.

The preceding ReLU head is reproduced exactly as the control. Only add
Dropout(0.5) after ReLU; retain every other training and routing decision.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
from pathlib import Path
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from threadpoolctl import threadpool_limits

import run_teacher_nonlinear_specialist as previous

ROOT, base, prior, cache = previous.ROOT, previous.base, previous.prior, previous.cache
NAME = 'teacher_dropout_specialist_seed42_20261023'
OUT = ROOT / 'ai-service/reports' / NAME
MODELS = ROOT / 'ai-service/candidates' / NAME
ARMS = ['dropout_control', 'dropout_specialist']
CONFIG = {**previous.CONFIG, 'hidden_dropout': .5, 'dropout_stream_seed': 20261023}
TOL = 1e-12
probability = previous.probability
sampling = previous.sampling


class Head(previous.Head):
    def __init__(self, dropout_p):
        super().__init__(True)
        self.dropout = nn.Dropout(dropout_p)

    def forward(self, x):
        return self.output(self.dropout(F.relu(self.encoder(x))))


@contextmanager
def dropout_stream(fold):
    # One advancing stream per complete arm fit. Batch permutations have their
    # own Generator, so masks cannot change training order or initialization.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(CONFIG['dropout_stream_seed'] + fold)
        yield


def fiveway(y):
    return np.array([prior.SPECIAL.index(int(i)) if i in prior.SPECIAL else 4 for i in y])


def evaluation(model, x, target):
    model.eval()
    with torch.inference_mode():
        logits = model(x); pp = logits.softmax(1)
        return dict(cross_entropy=float(F.cross_entropy(logits, target)),
                    accuracy=float((logits.argmax(1) == target).float().mean()),
                    mean_confidence=float(pp.max(1).values.mean()),
                    mean_true_class_probability=float(pp.gather(1, target[:, None]).mean()))


def choose(decisions, truth):
    scores = {n: base.metrics(p, truth) for n, p in decisions.items()}
    trials = {n: dict(metrics=s, guard_failures=prior.failures(s, scores['current_gate'])) for n, s in scores.items()}
    treatment, control = scores['dropout_specialist'], scores['dropout_control']
    if treatment['macro_f1'] + TOL < control['macro_f1']:
        trials['dropout_specialist']['guard_failures'].append('macro_f1_below_dropout_control')
    if previous.mean_focus(treatment) <= previous.mean_focus(control) + TOL:
        trials['dropout_specialist']['guard_failures'].append('no_focus_mean_f1_gain_vs_dropout_control')
    passing = [n for n, t in trials.items() if not t['guard_failures']]
    selected = max(passing, key=lambda n: (scores[n]['macro_f1'], previous.mean_focus(scores[n], 'recall'),
                   scores[n]['accuracy'], n == 'current_gate', n == 'dropout_control'))
    return dict(selected=selected, trials=trials)


def prepare():
    if (OUT / 'protocol.json').exists():
        p = base.read(OUT / 'protocol.json'); prior.verify(p); return p
    registry = base.read(ROOT / 'ai-service/reports/active_research_track.json')
    assert registry['next_experiment'] is None
    parent = base.read(previous.OUT / 'protocol.json'); prior.verify(parent)
    assert base.read(previous.OUT / 'completion.json')['status'] == 'complete_verified_not_selected'
    files = [Path(__file__), ROOT / 'ai-service/tests/test_teacher_dropout_specialist.py', Path(previous.__file__),
             previous.OUT / 'protocol.json', previous.OUT / 'results.json', previous.OUT / 'completion.json',
             previous.OUT / 'independent_review.json', previous.OUT / 'oof_decisions.json']
    for f in range(5):
        files += [x for x in (previous.MODELS / f'fold_{f}/nonlinear_specialist').iterdir() if x.is_file()]
        files += [previous.OUT / f'fold_{f}/scaler.npz', previous.OUT / f'fold_{f}/selection_locked.json']
    p = dict(name=NAME, registered_utc=previous.utc(), classes=base.CLASSES, folds=5, images=5937,
             parent_protocol=parent['parent_protocol'], previous_protocol=(previous.OUT / 'protocol.json').relative_to(ROOT).as_posix(),
             frozen_sha256={**parent['frozen_sha256'], **{x.relative_to(ROOT).as_posix(): base.sha(x) for x in files}},
             configuration=CONFIG,
             intervention='Only add standard elementwise Dropout(p=0.5) after hidden ReLU and before output. Control has p=0. Same 2048->128->5 parameters, initial tensors, train rows, scaler, loss, AdamW, batches and 20 epochs.',
             rng='Initialize both arms at seed 42. Fork CPU torch RNG for whole arm fit and seed once at 20261023+fold. Stream advances across all batches/epochs. Independent batch Generator remains 20261023+epoch; dropout cannot change order. Restore global RNG on exit.',
             evaluation='Use model.eval() for all train/inner/outer diagnostics and prediction. Inverted dropout scales survivors during train; no extra weight scaling at eval, no Monte Carlo dropout. Report deterministic five-way train/inner CE, accuracy and confidence every epoch, separately from stochastic training loss.',
             control='Refit preceding ReLU head and reproduce every epoch loss/metrics/objective, best and final model tensors, optimizer tensors and validation probabilities before outer scoring. Metadata/checkpoint byte hashes can differ.',
             reference=parent['reference'], routing=parent['routing'], checkpoint=parent['checkpoint'],
             selection='Strict prior guards versus frozen current gate. Dropout additionally Macro F1 >= matched control and mean F1 of Lupus/Psoriasis/Tinea strictly greater. Rank Macro F1, mean weak recall, Accuracy; exact ties prefer current gate then control. Lock all five choices before this outer evaluation.',
             reporting='Raw control, raw dropout, validation-selected, current gate and original fusion; all diseases, folds, sources, confusion matrices and 1000 paired group-bootstrap intervals versus current gate. Include routing coverage at unchanged 0.8. No p, threshold, seed or epoch-budget sweep.',
             trainable_heads=10, new_CNN_fits=0, serving_changed=False,
             limitations=parent['limitations'] + [
                 'One prechosen dropout probability and 20-epoch budget test this configuration only; rejection does not show all dropout methods are ineffective.',
                 'Dropout may change score scale and accepted switches at fixed 0.8; no probability calibration or threshold adjustment is inferred.',
                 'Stochastic dropout training loss is not comparable to deterministic control training loss. Use eval-mode diagnostics for the head generalization gap.',
                 'No new source evaluation is implied. If selected policy is unchanged, only that unchanged policy inherits its previous descriptive transfer results.'],
             references=['https://jmlr.org/papers/v15/srivastava14a.html',
                         'https://docs.pytorch.org/docs/stable/generated/torch.nn.Dropout.html',
                         'https://docs.pytorch.org/docs/stable/random.html'])
    OUT.mkdir(parents=True, exist_ok=True); base.write(OUT / 'protocol.json', p)
    base.write(OUT / 'research_registry_before.json', registry)
    registry['next_experiment'] = OUT.relative_to(ROOT).as_posix()
    registry['next_experiment_status'] = 'registered_hidden_dropout_only_specialist'
    base.write(ROOT / 'ai-service/reports/active_research_track.json', registry)
    return p


def tensor_match(actual, expected):
    assert actual.keys() == expected.keys()
    for key in actual:
        if isinstance(actual[key], torch.Tensor):
            assert torch.equal(actual[key], expected[key]), key
        elif isinstance(actual[key], dict): tensor_match(actual[key], expected[key])
        else: assert actual[key] == expected[key], key


def fit_all(p):
    assert not (OUT / 'all_selections_locked.json').exists(), 'Preserve completed fits'
    parent = base.read(ROOT / p['parent_protocol'])
    for f in range(5):
        folder = OUT / f'fold_{f}'; folder.mkdir(parents=True, exist_ok=True)
        paths, raw, _ = cache.cached(f, 'train', parent)
        labels = np.array([base.CLASSES.index(parent['manifest'][x]['class']) for x in paths])
        target = fiveway(labels)
        with np.load(previous.OUT / f'fold_{f}/scaler.npz', allow_pickle=False) as z:
            mean, scale = z['mean'].copy(), z['scale'].copy()
        np.savez_compressed(folder / 'scaler.npz', mean=mean, scale=scale)
        def tensor(x): return torch.from_numpy(((x-mean)/scale).astype(np.float32))
        tx, ty = tensor(raw), torch.as_tensor(target, dtype=torch.long)
        ipaths, xx, _ = cache.cached(f, 'inner_validation', parent)
        current, truth = previous.inner_reference(f, ipaths)
        ix = tensor(xx); iy = torch.as_tensor(fiveway(truth), dtype=torch.long)
        ref = base.metrics(current, truth); pp = {}; initial_hashes = []; histories = {}
        old_dest = previous.MODELS / f'fold_{f}/nonlinear_specialist'; old_history = base.read(old_dest / 'history.json')
        for arm in ARMS:
            dest = MODELS / f'fold_{f}' / arm; dest.mkdir(parents=True, exist_ok=True)
            torch.manual_seed(CONFIG['seed']); model = Head(0. if arm == 'dropout_control' else .5)
            initial_hashes.append(previous.state_sha(model.state_dict()))
            optimizer = torch.optim.AdamW(model.parameters(), lr=CONFIG['learning_rate'], weight_decay=CONFIG['weight_decay'])
            history = []; best = None; updates = 0; started = time.monotonic()
            global_before = torch.get_rng_state().clone()
            with dropout_stream(f):
                stream_initial = hashlib.sha256(torch.get_rng_state().numpy().tobytes()).hexdigest()
                for epoch in range(1, 21):
                    model.train(); order = sampling(len(tx), epoch); total = 0.
                    for ids in order.split(CONFIG['batch_size']):
                        optimizer.zero_grad(set_to_none=True); loss = F.cross_entropy(model(tx[ids]), ty[ids])
                        if not torch.isfinite(loss): raise FloatingPointError('Nonfinite dropout head loss')
                        loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), CONFIG['gradient_clip'], error_if_nonfinite=True)
                        optimizer.step(); total += float(loss.detach()) * len(ids); updates += 1
                    proposed = probability(model, ix); pred = previous.route(current, proposed)
                    score, failures, objective = previous.epoch_assess(pred, truth, ref)
                    improved = best is None or tuple(objective) > tuple(best['objective'])
                    if improved:
                        best = dict(epoch=epoch, objective=objective, metrics=score, guard_failures=failures)
                        torch.save(dict(model_state_dict=model.state_dict(), arm=arm, epoch=epoch,
                                        protocol_sha256=base.sha(OUT / 'protocol.json')), dest / 'best_model.pth')
                    row = dict(epoch=epoch, stochastic_train_loss=total/len(tx), actual_updates=len(order.split(CONFIG['batch_size'])),
                        sampling_sha256=hashlib.sha256(order.numpy().tobytes()).hexdigest(), metrics=score,
                        guard_failures=failures, objective=objective, new_best=improved, best_epoch=best['epoch'],
                        evaluation=dict(train=evaluation(model, tx, ty), inner=evaluation(model, ix, iy)),
                        dropout_rng_sha256=hashlib.sha256(torch.get_rng_state().numpy().tobytes()).hexdigest())
                    if arm == 'dropout_control':
                        old = old_history[epoch-1]
                        assert abs(old['loss']-row['stochastic_train_loss']) < 1e-12
                        for key in ['metrics','guard_failures','objective','new_best','best_epoch','sampling_sha256','actual_updates']:
                            assert old[key] == row[key], key
                    history.append(row); base.write(dest / 'history.json', history)
                    base.write(OUT / 'status.json', dict(state='training', fold=f, arm=arm, epoch=epoch, utc=previous.utc()))
                    if epoch % 5 == 0:
                        print(dict(fold=f, arm=arm, epoch=epoch, best=best['epoch'],
                                   train_ce=row['evaluation']['train']['cross_entropy'], inner_ce=row['evaluation']['inner']['cross_entropy']), flush=True)
                stream_final = hashlib.sha256(torch.get_rng_state().numpy().tobytes()).hexdigest()
                assert (stream_initial == stream_final) == (arm == 'dropout_control')
            assert torch.equal(global_before, torch.get_rng_state())
            final = dict(model_state_dict=model.state_dict(), optimizer_state_dict=optimizer.state_dict(),
                         protocol_sha256=base.sha(OUT / 'protocol.json'))
            if arm == 'dropout_control':
                old_last = torch.load(old_dest / 'last_state.pth', weights_only=False)
                tensor_match(final['model_state_dict'], old_last['model_state_dict'])
                tensor_match(final['optimizer_state_dict'], old_last['optimizer_state_dict'])
            torch.save(final, dest / 'last_state.pth')
            model.load_state_dict(torch.load(dest / 'best_model.pth', weights_only=False)['model_state_dict'])
            pp[arm] = probability(model, ix); histories[arm] = history
            if arm == 'dropout_control':
                tensor_match(model.state_dict(), torch.load(old_dest / 'best_model.pth', weights_only=False)['model_state_dict'])
                with np.load(old_dest / 'validation_probabilities.npz', allow_pickle=False) as z:
                    assert z['paths'].tolist() == ipaths and np.array_equal(z['probability'], pp[arm])
            np.savez_compressed(dest / 'validation_probabilities.npz', paths=ipaths, probability=pp[arm])
            base.write(dest / 'training_report.json', dict(fold=f, arm=arm, dropout_p=model.dropout.p,
                epochs=20, actual_updates=updates, train_images=len(paths), target_counts=np.bincount(target, minlength=5).tolist(),
                best=best, initial_state_sha256=initial_hashes[-1], trainable_parameters=sum(x.numel() for x in model.parameters()),
                checkpoint_sha256=base.sha(dest / 'best_model.pth'), dropout_stream_seed=20261023+f,
                stream_initial_sha256=stream_initial, stream_final_sha256=stream_final, global_rng_restored=True,
                control_matches_previous=arm == 'dropout_control', seconds=time.monotonic()-started))
        assert initial_hashes[0] == initial_hashes[1]
        assert [h['sampling_sha256'] for h in histories[ARMS[0]]] == [h['sampling_sha256'] for h in histories[ARMS[1]]]
        decisions = dict(current_gate=current, **{a:previous.route(current, q) for a,q in pp.items()})
        selection = choose(decisions, truth)
        np.savez_compressed(folder / 'inner_decisions.npz', paths=ipaths, truth=truth, **decisions,
                            **{a+'_probability':q for a,q in pp.items()})
        artifacts = [folder / 'scaler.npz', folder / 'inner_decisions.npz', *(MODELS / f'fold_{f}').rglob('*')]
        selection.update(locked_utc=previous.utc(), protocol_sha256=base.sha(OUT / 'protocol.json'),
                         artifacts_sha256={x.relative_to(ROOT).as_posix():base.sha(x) for x in artifacts if x.is_file()})
        base.write(folder / 'selection_locked.json', selection)
        print(dict(fold=f, selected=selection['selected'], dropout_failures=selection['trials']['dropout_specialist']['guard_failures']), flush=True)
    base.write(OUT / 'all_selections_locked.json', dict(locked_utc=previous.utc(), actual_heads=10, epochs_each=20,
        protocol_sha256=base.sha(OUT / 'protocol.json'),
        selections_sha256={str(f):base.sha(OUT / f'fold_{f}/selection_locked.json') for f in range(5)}))
    prior.verify(p)


def coverage(current, probability, prediction):
    winner = probability.argmax(1); inside = np.isin(current, prior.SPECIAL)
    candidate = np.asarray(prior.SPECIAL)[np.minimum(winner, 3)]
    mask = dict(outside_scope=~inside, other_abstention=inside&(winner==4),
                same_label=inside&(winner<4)&(candidate==current),
                below_threshold=inside&(winner<4)&(candidate!=current)&(probability.max(1)<.8),
                accepted_switch=inside&(winner<4)&(candidate!=current)&(probability.max(1)>=.8))
    assert np.all(np.sum(list(mask.values()), axis=0) == 1)
    expected = current.copy(); expected[mask['accepted_switch']] = candidate[mask['accepted_switch']]
    assert np.array_equal(expected, prediction)
    return {key:int(value.sum()) for key,value in mask.items()}


def evaluate(p):
    assert not (OUT / 'results.json').exists(), 'Preserve completed evaluation'
    locks = base.read(OUT / 'all_selections_locked.json'); parent = base.read(ROOT / p['parent_protocol'])
    assert locks['selections_sha256'] == {str(f):base.sha(OUT / f'fold_{f}/selection_locked.json') for f in range(5)}
    old_rows = {r['path']:r for r in base.read(previous.OUT / 'oof_decisions.json')}
    rows = []; probabilities = {a:{} for a in ARMS}; started = previous.utc()
    for f in range(5):
        lock = base.read(OUT / f'fold_{f}/selection_locked.json')
        for path,digest in lock['artifacts_sha256'].items():assert base.sha(ROOT/path) == digest
        raw_rows, _, _, original = prior.outer_rows(parent, f)
        paths, xx, _ = cache.cached(f, 'outer_holdout', parent); assert paths == [r['path'] for r in raw_rows]
        current = np.array([old_rows[x]['predictions']['current_gate'] for x in paths])
        with np.load(OUT / f'fold_{f}/scaler.npz', allow_pickle=False) as z:
            x = torch.from_numpy(((xx-z['mean'])/z['scale']).astype(np.float32))
        decisions = dict(original_fusion=original, current_gate=current); pp = {}
        for arm in ARMS:
            model = Head(0. if arm == 'dropout_control' else .5)
            model.load_state_dict(torch.load(MODELS / f'fold_{f}' / arm / 'best_model.pth', weights_only=False)['model_state_dict'])
            pp[arm] = probability(model, x); decisions[arm] = previous.route(current, pp[arm])
            probabilities[arm].update(zip(paths, pp[arm]))
        assert np.array_equal(decisions['dropout_control'], [old_rows[x]['predictions']['nonlinear_specialist'] for x in paths])
        decisions['validation_selected'] = decisions[lock['selected']]
        rows += prior.records(raw_rows, f, decisions)
        np.savez_compressed(OUT / f'fold_{f}/outer_probabilities.npz', paths=paths, **{a+'_probability':q for a,q in pp.items()})
    rows.sort(key=lambda r:r['path']); assert len(rows) == len({r['path'] for r in rows}) == 5937
    y = np.array([base.CLASSES.index(r['label']) for r in rows]); current = np.array([r['predictions']['current_gate'] for r in rows])
    methods = {}
    for name in rows[0]['predictions']:
        pred = np.array([r['predictions'][name] for r in rows]); assert np.array_equal(pred==5, current==5)
        score = base.metrics(pred, y)
        score.update(correct=int((pred==y).sum()), changed=int((pred!=current).sum()),
            corrected=int(((current!=y)&(pred==y)).sum()), broken=int(((current==y)&(pred!=y)).sum()),
            wrong_to_wrong=int(((current!=pred)&(current!=y)&(pred!=y)).sum()),
            paired_delta_vs_current_95pct=prior.paired_intervals(rows, pred, current, y))
        score['per_source'] = {}
        for source in ['original_train','SCIN']:
            mask = np.array([r['source']==source for r in rows])
            score['per_source'][source] = dict(images=int(mask.sum()), **base.metrics(pred[mask], y[mask]))
        if name in ARMS:
            score['routing_coverage'] = coverage(current, np.asarray([probabilities[name][r['path']] for r in rows]), pred)
        methods[name] = score
    old = base.read(previous.OUT / 'results.json')['methods']
    for a,b in [('original_fusion','original_fusion'),('current_gate','current_gate'),('dropout_control','nonlinear_specialist')]:
        assert methods[a]['confusion_matrix'] == old[b]['confusion_matrix']
    per_fold = []
    for f in range(5):
        mask = np.array([r['fold']==f for r in rows])
        per_fold.append(dict(fold=f, selected=base.read(OUT / f'fold_{f}/selection_locked.json')['selected'],
            methods={n:base.metrics(np.array([r['predictions'][n] for r in rows])[mask], y[mask]) for n in methods}))
    result = dict(status='complete_exploratory_hidden_dropout_only', images=5937, methods=methods, per_fold=per_fold,
        outer_started_utc=started, completed_utc=previous.utc(), protocol_sha256=base.sha(OUT / 'protocol.json'),
        all_selections_sha256=base.sha(OUT / 'all_selections_locked.json'), trainable_heads=10, epochs_each=20,
        new_CNN_fits=0, reference_baseline_changed=False, serving_changed=False, limitations=p['limitations'])
    base.write(OUT / 'oof_decisions.json', rows); base.write(OUT / 'results.json', result); prior.verify(p)
    base.write(OUT / 'verification.json', dict(status='PASS', results_sha256=base.sha(OUT / 'results.json'),
        original_control_exactly_reproduced=True, same_initial_tensors_and_batches=True,
        dropout_rng_isolated=True, evaluation_dropout_disabled=True, all_five_locked_before_outer=True, exact_cancer_mask=True))
    base.write(OUT / 'status.json', dict(state='complete', utc=previous.utc()))
    print({n:{k:s[k] for k in ['accuracy','macro_f1','correct']} for n,s in methods.items()}, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(); torch.set_num_threads(2); torch.use_deterministic_algorithms(True)
    with threadpool_limits(limits=1):
        p = prepare()
        if not args.prepare_only:fit_all(p); evaluate(p)


if __name__ == '__main__':main()
