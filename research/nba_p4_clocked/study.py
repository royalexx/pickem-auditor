"""Execute the frozen native n=4 comparison and preserve attempted paths."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from math import fsum, log, sqrt
from pathlib import Path

import numpy as np
from scipy.stats import nbinom

from research.nba_p4_latest.fixture import build
from research.nba_p4_latest.repeated_seeds import full_count_laws
from v2.nba_joint.clocked import STATS, COMBOS
from v2.nba_joint.clocked_native import prepare_native, run_seed
from v2.nba_joint.clocked_replay import reconstruct
from v2.nba_joint.latest_upstream import load_upstream, prepare

SEEDS = range(200000, 200256)
CUT = {'points': (30, 60), 'rebounds': (12, 20), 'assists': (10, 20),
       'threes': (5, 20), 'pr': (40, 70), 'pa': (40, 70), 'ra': (20, 35),
       'pra': (50, 80)}
METRICS = (*STATS, *COMBOS)


def write_record(handle, row):
    handle.write((json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode())


def shard(prepared, seeds, output):
    summary = []
    with output.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='',
                                                      mtime=0, compresslevel=1) as gz:
        for seed in seeds:
            packet = run_seed(prepared, seed)
            catalog = []
            for path in packet['paths']:
                row = {k: path[k] for k in ('scenario_id', 'weight', 'status')}
                row['attempts'] = len(path['attempts'])
                row['rejected_checkpoints'] = dict(Counter(
                    a['periods'][-1]['period'] for a in path['attempts']
                    if a['status'] != 'accepted'))
                if 'normalizer' in path:
                    z = row['Z'] = path['normalizer']['Z']
                    row['failure_probability_given_latents'] = (1 - z) ** 128
                    row['maximum_normalizer_block_mass_error'] = max(
                        b['mass_error'] for b in path['normalizer']['blocks'])
                for attempt in path['attempts']:
                    totals = reconstruct(path['plan'], attempt)
                    if attempt['status'] == 'accepted':
                        row['totals'] = totals
                catalog.append(row)
                # The common plan remains in inputs.json, keyed by scenario.
                path.pop('plan', None)
            summary.append({'seed': seed, 'status': packet['status'], 'paths': catalog})
            write_record(gz, packet)
    return summary


def summarize(rows, references, prepared):
    metrics, totals = {}, {}
    for idx, spec in enumerate(prepared['scenarios']):
        sid = spec['scenario_id']
        group = [r['paths'][idx] for r in rows]
        legal = [r['totals']['players'] for r in group if r['status'] == 'accepted']
        n = len(legal)
        attempts = sum(r['attempts'] for r in group)
        totals[sid] = {'completions': n, 'seed_denominator': len(group), 'attempts': attempts,
                       'rejections': attempts - n,
                       'failure_by_status': dict(Counter(r['status'] for r in group)),
                       'rejected_by_period': dict(sum((Counter(r['rejected_checkpoints']) for r in group), Counter())),
                       'Z_range': [min(r['Z'] for r in group), max(r['Z'] for r in group)] if 'Z' in group[0] else None,
                       'expected_failures_given_latents': fsum(r.get('failure_probability_given_latents', 1)
                                                              for r in group)}
        metrics[sid] = {}
        if not n:
            continue
        bounds = 7 * sum(len(p['ends']) for p in spec['plan']['periods'])
        # Family size overbounds every declared marginal integer threshold plus scalars,
        # including pooled comparisons and every scenario. Clusters are independent seeds.
        k = (len(prepared['scenarios']) + 1) * len(legal[0]) * len(METRICS) * (bounds + 10)
        epsilon = sqrt(log(2 * k / .05) / (2 * n))
        for pid in legal[0]:
            values = np.array([[r[pid][s] for s in METRICS] for r in legal])
            covariance = np.cov(values[:, :4], rowvar=False, ddof=0)
            player = metrics[sid][pid] = {'primitive_covariance': covariance.tolist(),
                                          'distribution_denominator': n,
                                          'scope': 'descriptive conditional on completion'}
            for col, stat in enumerate(METRICS):
                obs = values[:, col]
                support = np.arange(int(obs.max()) + 1)
                counts = np.bincount(obs)
                pmf = counts / n
                entry = player[stat] = {'histogram_counts': counts.tolist(),
                    'mean': float(obs.mean()), 'variance': float(obs.var()),
                    'zero_count': int(counts[0]),
                    'mean_cluster_se': float(obs.std(ddof=1)/sqrt(n)) if n > 1 else None,
                    'tails': {str(th): {'count': int(np.count_nonzero(obs >= th))} for th in CUT[stat]}}
                if stat not in STATS:
                    continue
                ref = references[pid][stat][idx]
                shape, prob = ref['shape'], ref['success_probability']
                mean_error = abs(entry['mean'] - ref['mean'])
                ks = float(np.max(np.abs(1-np.cumsum(pmf) - nbinom.sf(support, shape, prob))))
                entry.update(reference_mean=ref['mean'], reference_variance=ref['variance'],
                             mean_absolute_error=mean_error, ks=ks,
                             reference_zero=float(nbinom.pmf(0, shape, prob)),
                             simultaneous_indicator_radius=epsilon,
                             simultaneous_mean_radius=epsilon * bounds,
                             mean_lower_error=max(0., mean_error - epsilon * bounds),
                             ks_lower_error=max(0., ks - epsilon))
                for key, t in entry['tails'].items():
                    t['reference'] = float(nbinom.sf(int(key)-1, shape, prob))
                    t['zero_event_upper_95_unadjusted'] = 1-.05**(1/n) if not t['count'] else None
    return {'status': 'screen_only_no_forecast', 'seed_denominator': len(rows),
            'complete_seed_count': sum(r['status'] == 'accepted' for r in rows),
            'scenarios': totals, 'descriptive_scenario_metrics': metrics,
            'pooled_forecast_pmf': None, 'observed_games': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir()
    root = prepare()
    inputs = build(root)
    p2, _ = load_upstream(root)
    references = full_count_laws(inputs, p2)
    prepared = prepare_native(*inputs, upstream_root=root,
                              evidence_mode='latest_synthetic_engineering')
    with (args.output / 'inputs.json').open('xb') as handle:
        write_record(handle, {'prepared': prepared, 'full_S_reference': references,
                              'pregame': inputs[0], 'G': inputs[1], 'O': inputs[2],
                              'O_sidecar': inputs[3]})
    with ProcessPoolExecutor(max_workers=8) as pool:
        jobs = [pool.submit(shard, prepared, SEEDS[i:i+32], args.output / f'paths_{i//32}.jsonl.gz')
                for i in range(0, len(SEEDS), 32)]
        rows = [row for job in jobs for row in job.result()]
    with (args.output / 'denominators.json').open('xb') as handle:
        write_record(handle, rows)
    with (args.output / 'summary.json').open('xb') as handle:
        write_record(handle, summarize(rows, references, prepared))


if __name__ == '__main__':
    main()
