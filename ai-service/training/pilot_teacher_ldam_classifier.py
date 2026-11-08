"""Inner-only matched cosine CE/LDAM heads for Lupus/Psoriasis; no outer access."""
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import pilot_teacher_cosine_classifier as previous

ROOT, base, prior, latest = previous.ROOT, previous.base, previous.prior, previous.latest
OUT = ROOT / 'ai-service/reports/teacher_ldam_classifier_fold0_seed42_20261025'
MODELS = ROOT / 'ai-service/candidates' / OUT.name
ARMS = ['ce_control', 'ldam_head']
CONFIG = dict(seed=42, steps=400, lr=.01, betas=[.9, .999], epsilon=1e-8,
              scale=30., max_margin=.5, norm_epsilon=1e-12, threads=4)


def utc(): return datetime.now(timezone.utc).isoformat()


def margins(counts, max_margin=.5):
    counts = np.asarray(counts, dtype=float)
    if counts.shape != (8,) or not np.isfinite(counts).all() or (counts <= 0).any():
        raise ValueError('Eight positive finite train counts required')
    if not np.isfinite(max_margin) or max_margin < 0:
        raise ValueError('Nonnegative finite maximum margin required')
    raw = counts ** -.25
    return max_margin * raw / raw.max()


def training_logits(cosine, targets, margin, scale=30.):
    if cosine.ndim != 2 or cosine.shape[1] != 8 or targets.shape != (len(cosine),) or margin.shape != (8,):
        raise ValueError('Aligned eight-way cosine scores, targets and margins required')
    # LDAM shifts only the true-label cosine before common scaling. Inference omits it.
    offset = F.one_hot(targets, 8).to(cosine.dtype) * margin[targets, None]
    return scale * (cosine - offset)


def probability(z, weight):
    l = CONFIG['scale'] * z @ previous.unit(weight).T
    l -= l.max(1, keepdims=True); q = np.exp(l)
    return q / q.sum(1, keepdims=True)


def choose(decisions, truth):
    scores = {n: base.metrics(d, truth) for n, d in decisions.items()}
    trials = {n: dict(metrics=s, guard_failures=prior.failures(s, scores['current_policy'])) for n, s in scores.items()}
    new = scores['ldam_head']
    if new['macro_f1'] + 1e-12 < scores['ce_control']['macro_f1']:
        trials['ldam_head']['guard_failures'].append('macro_f1_below_ce_control')
    for n in ['current_policy', 'ce_control']:
        if previous.focus(new) <= previous.focus(scores[n]) + 1e-12:
            trials['ldam_head']['guard_failures'].append('no_Lupus_Psoriasis_mean_f1_gain_vs_' + n)
    passing = [n for n, t in trials.items() if not t['guard_failures']]
    selected = max(passing, key=lambda n: (scores[n]['macro_f1'],
        np.mean([scores[n]['per_class'][c]['recall'] for c in ['Lupus', 'Psoriasis', 'Tinea']]),
        scores[n]['accuracy'], n == 'current_policy', n == 'ce_control'))
    return dict(selected=selected, trials=trials)


def prepare():
    assert not (OUT / 'protocol.json').exists(), 'Preserve registered pilot'
    old = base.read(previous.OUT / 'protocol.json')
    assert base.read(previous.OUT / 'completion.json')['status'] == 'complete_verified_pilot_not_selected'
    assert base.read(ROOT / 'ai-service/reports/active_research_track.json')['next_experiment'] is None
    roles = old['roles']
    for a, b in [('train', 'inner_validation'), ('train', 'outer_holdout'), ('inner_validation', 'outer_holdout')]:
        for k in ['path', 'sha256', 'group']:
            assert {r[k] for r in roles[a]}.isdisjoint({r[k] for r in roles[b]})
    counts = np.bincount([base.CLASSES.index(r['label']) for r in roles['train']], minlength=8)
    files = [Path(__file__), ROOT / 'ai-service/tests/test_teacher_ldam_classifier.py',
             ROOT / 'tmp/review_teacher_ldam_classifier_20261025.py', Path(previous.__file__),
             Path(prior.__file__), Path(base.__file__), previous.OUT / 'protocol.json',
             previous.OUT / 'completion.json', latest.OUT / 'results.json',
             latest.OUT / 'fold_0/inner_decisions.npz', latest.OUT / 'fold_0/selection_locked.json',
             ROOT / 'ai-service/app/config.py', ROOT / 'ai-service/models/best_model.pth',
             ROOT / 'ai-service/reports/active_research_track.json']
    files += [prior.OUT / f'B_specialist/fold_0/{role}_features.npz' for role in ['train', 'inner_validation']]
    images = {r['path']: r['sha256'] for role in ['train', 'inner_validation'] for r in roles[role]}
    for path, digest in images.items(): assert base.sha(ROOT / path) == digest, path
    p = dict(name=OUT.name, registered_utc=utc(), classes=base.CLASSES, fold=0,
        roles=roles, configuration=CONFIG, train_counts=counts.tolist(), margins=margins(counts).tolist(),
        frozen_sha256={x.relative_to(ROOT).as_posix(): base.sha(x) for x in files},
        representation='Original fold0 frozen ResNet2048 train/inner caches. StandardScaler fit only4043train, then rowL2. Both8wayheads are row-normalized8x2048weights, no bias; identicalseed42unit-normalinitial.',
        comparison='FullbatchFP64CPUAdam400steps,lr.01,betas.9/.999,eps1e-8,noWd/clip/scheduler/sampling/weighting/DRW. CE:CE(30*cosine,y); LDAM:CE(30*(cosine-onehot(y)*m_y),y), m_c=.5*n_c^(-1/4)/max_j(n_j^(-1/4)), countsfromtrainonly. Bothfinalstep400,noepochselection. Onlytraininglossdiffers. Rawinferenceuses30*cosinewithoutmargininboth.',
        routing=old['routing'],
        selection='Current/CE/LDAM on718inner. OriginalstrictAccuracy/MF,eachweakRecall/F1,weakprecisiondrop<=.02,otherrecalldrop<=.02,CancerP/Rexact. LDAMalsoMF>=CE and meanLupus/PsoriasisF1strictly>bothcurrent/CE. RankMF,mean3weakRecall,Acc,tiecurrentthenCE. No margin/scale/threshold/step/seed sweep.',
        scope='Inner-onlyfixedpilot, no reading outer/sourcefeatures/probabilities/labels forscoring. No5937OOFscore. Lockselectionandreportbotharms includingfailure; confirmationisaseparatefutureexperimentifinnerpromising.',
        references=['https://arxiv.org/abs/1906.07413', 'https://github.com/kaidic/LDAM-DRW/blob/master/losses.py'],
        limitations=['AdaptsLDAMlosswithauthorsdefaultsmaxmargin.5/scale30; frozenfeatures/Adam/standardization arelocaladaptations,notfullCNNbenchmarkorLDAM-DRWreproduction.',
            'Classimbalanceisahypothesis,notestablishedcauseofLupus/Psoriasiserrors. Canincreaserareclassfalsepositivesorloseotherrecalls.',
            'Historicalinner/upstreamreused; nofreshpatientvalidation,independentCNNinitializationorclinicalguarantee. Innerfold0hasnoSCINLupus.',
            'Fixedfull8waythreshold.8isnotcalibratedequallyacrosslosses. Missingfeatureinformationoruncertainlabelscannotbeassumedfixedbyloss.'],
        image_sha256_checked=len(images), new_heads=2, updates_each=400,
        new_CNN_fits=0, new_CNN_forwards=0, global_5937_score_changed=False,
        serving_changed=False, research_registry_changed=False)
    OUT.mkdir(parents=True, exist_ok=True); base.write(OUT / 'protocol.json', p)
    base.write(OUT / 'status.json', dict(state='registered_inner_only', updated_utc=utc()))
    return p


def fit(p):
    MODELS.mkdir(parents=True, exist_ok=True)
    train = p['roles']['train']; inner = p['roles']['inner_validation']
    raw = previous.cached('train', train); scaler = StandardScaler().fit(raw)
    z = previous.unit(scaler.transform(raw)); iz = previous.unit(scaler.transform(previous.cached('inner_validation', inner)))
    y = np.array([base.CLASSES.index(r['label']) for r in train]); yt = torch.tensor(y, dtype=torch.long); x = torch.tensor(z, dtype=torch.float64)
    generator = torch.Generator().manual_seed(42)
    initial = F.normalize(torch.randn(8, 2048, dtype=torch.float64, generator=generator), dim=1)
    np.savez_compressed(MODELS / 'shared.npz', mean=scaler.mean_, scale=scaler.scale_, initial=initial.numpy(), margins=p['margins'])
    with np.load(latest.OUT / 'fold_0/inner_decisions.npz') as a:
        assert a['paths'].tolist() == [r['path'] for r in inner]
        truth = a['truth'].copy(); current = a[base.read(latest.OUT / 'fold_0/selection_locked.json')['selected']].copy()
    dd = dict(current_policy=current); report = {}; raw_scores = {}
    for name in ARMS:
        w = torch.nn.Parameter(initial.clone()); opt = torch.optim.Adam([w], lr=.01, betas=(.9, .999), eps=1e-8)
        margin = torch.tensor(p['margins'] if name == 'ldam_head' else np.zeros(8), dtype=torch.float64); history = []
        base.write(OUT / 'status.json', dict(state='training_head', arm=name, updated_utc=utc()))
        for step in range(1, 401):
            opt.zero_grad(set_to_none=True); cosine = x @ F.normalize(w, dim=1, eps=1e-12).T
            loss = F.cross_entropy(training_logits(cosine, yt, margin), yt)
            assert torch.isfinite(loss); loss.backward(); assert torch.isfinite(w.grad).all()
            if step == 1 or step % 20 == 0:
                history.append(dict(step=step, loss_before_update=float(loss.detach()), gradient_norm=float(w.grad.norm()),
                                    weight_norms=w.detach().norm(dim=1).tolist()))
            opt.step()
        weight = w.detach().numpy().copy(); np.savez_compressed(MODELS / f'{name}.npz', weight=weight, classes=base.CLASSES)
        q = probability(iz, weight); dd[name] = previous.route(current, q); raw_scores[name] = base.metrics(q.argmax(1), truth)
        np.savez_compressed(OUT / f'inner_{name}_probabilities.npz', paths=[r['path'] for r in inner], probabilities=q)
        report[name] = dict(steps=400, optimizer_steps=int(opt.state[w]['step']), parameters=weight.size,
            train_images=len(y), history=history, train_raw=base.metrics(probability(z, weight).argmax(1), y))
        print(dict(arm=name, steps=400, raw_inner=raw_scores[name]['accuracy'], routed_inner=base.metrics(dd[name], truth)['macro_f1']), flush=True)
    base.write(OUT / 'training_report.json', report)
    np.savez_compressed(OUT / 'inner_decisions.npz', paths=[r['path'] for r in inner], truth=truth, **dd)
    lock = choose(dd, truth); artifacts = [*MODELS.glob('*.npz'), OUT / 'training_report.json', OUT / 'inner_decisions.npz', *OUT.glob('inner_*_probabilities.npz')]
    lock.update(locked_utc=utc(), protocol_sha256=base.sha(OUT / 'protocol.json'), raw_validation=raw_scores,
                artifacts_sha256={path.relative_to(ROOT).as_posix(): base.sha(path) for path in artifacts})
    base.write(OUT / 'selection_locked.json', lock)
    result = dict(status='complete_inner_only_awaiting_review', selected=lock['selected'], validation=lock['trials'],
        raw_validation=raw_scores, new_heads=2, optimizer_updates=800, new_CNN_fits=0, new_CNN_forwards=0,
        outer_scored=False, source_scored=False, global_5937_score_changed=False, serving_changed=False,
        completed_utc=utc(), protocol_sha256=base.sha(OUT / 'protocol.json'), selection_sha256=base.sha(OUT / 'selection_locked.json'))
    base.write(OUT / 'results.json', result); prior.verify(p)
    base.write(OUT / 'verification.json', dict(status='PASS', results_sha256=base.sha(OUT / 'results.json')))
    base.write(OUT / 'status.json', dict(state='inner_complete_awaiting_review', updated_utc=utc()))
    print(dict(selected=lock['selected'], failures={n: t['guard_failures'] for n, t in lock['trials'].items()}), flush=True)


if __name__ == '__main__':
    torch.set_num_threads(4)
    with threadpool_limits(limits=4): fit(prepare())
