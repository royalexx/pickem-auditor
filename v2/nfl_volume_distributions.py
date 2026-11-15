"""WS2 distribution-first research adapter; frozen v1 mathematical code is read-only.

No collectors, fitting of role priors, calibrated variants, or production writers.
New identifiers disclose the WS1 ten-observation source window and paired laws.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from .nfl_marginal_shadow import empirical, MODEL_IDS

FIELDS = {
    'pass_attempts': ('attempts',), 'pass_completions': ('completions',),
    'passing_yards': ('passing_yards',), 'rush_attempts': ('carries',),
    'rushing_yards': ('rushing_yards',), 'receiving_targets': ('targets',),
    'receptions': ('receptions',), 'receiving_yards': ('receiving_yards',),
    'tackles_assists': ('tackles_combined',),
    'rushing_receiving_yards': ('rushing_yards', 'receiving_yards'),
    'passing_rushing_yards': ('passing_yards', 'rushing_yards'),
}
EW = 'S2-ew-source-paired-hl4-v2'
UNIFORM = 'S2-uniform-source-paired-v2'
ACTIVE = (EW, UNIFORM)
UNAVAILABLE = tuple(m for m in MODEL_IDS if not m.startswith('S2-'))
CONFIG = dict(version='ws2-volume-distributions-v2', min_player=3, max_history=10,
              half_life=4.0, uncertainty_draws=1024,
              qb_history='official_schedule_starting_qb_id',
              calibration='uncalibrated', peers='not_authenticated')
PIN_SHA = 'c3ec93c78fcae413f66afe431f817f4d986f0fd1e884c665caefc5c7a3ed230c'
OLD_SHA = '5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71'
PIN_PATH = 'reports/nfl_20261115_prospective/market_extension_v2_5_1/FEATURE_PIN.json'


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def sha(x):
    return hashlib.sha256(x).hexdigest()


def stamp(x):
    d = datetime.fromisoformat(x.replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('NAIVE_TIMESTAMP')
    return d


def number(x):
    if x is None or isinstance(x, bool):
        raise ValueError('MISSING_OBSERVATION')
    y = float(x)
    if not math.isfinite(y) or not y.is_integer():
        raise ValueError('INVALID_DISCRETE_OBSERVATION')
    return int(y)


def validate_value(market, row):
    if market not in FIELDS:
        raise ValueError('UNAPPROVED_MARKET')
    if market == 'tackles_assists':
        raise ValueError('TACKLE_ACCOUNTING_NOT_INDEPENDENTLY_CERTIFIED')
    parts = {k: number(row['components'].get(k)) for k in FIELDS[market]}
    value = number(row.get('value'))
    if value != sum(parts.values()):
        raise ValueError('COMPONENT_IDENTITY_VIOLATION')
    if not market.endswith('yards') and value < 0:
        raise ValueError('NEGATIVE_COUNT')
    return value


def select_history(player, rows, freeze, forecast_at, starters):
    market = player['normalized_market']
    if market not in FIELDS or player['period'] != 'full_game':
        raise ValueError('UNAPPROVED_MARKET_OR_PERIOD')
    if stamp(player['event_start_at']) <= stamp(forecast_at):
        raise ValueError('KICKOFF_PASSED')
    if stamp(freeze) > stamp(forecast_at):
        raise ValueError('FUTURE_FREEZE')
    if market == 'tackles_assists':
        raise ValueError('TACKLE_ACCOUNTING_NOT_INDEPENDENTLY_CERTIFIED')
    if not player['model_input_ready']:
        raise ValueError('|'.join(player['abstention_reasons']) or 'WS1_NOT_READY')
    if not player.get('identity_source_sha256'):
        raise ValueError('UNBOUND_ELIGIBILITY')
    if player['position'] == 'QB':
        if player['eligibility_status'] != 'EXPECTED_STARTER' or not player.get('role_source_sha256'):
            raise ValueError('QB_NOT_SOURCE_EXPECTED_STARTER')
    seen = set(); selected = []; role_exclusions = 0
    for r in rows:
        if (r['player_id'], r['market'], r['period']) != (player['player_id'], market, player['period']):
            raise ValueError('HISTORY_IDENTITY_MISMATCH')
        key = (r['player_id'], r['game_id'], r['market'], r['period'])
        if key in seen:
            raise ValueError('DUPLICATE_SOURCE_IDENTITY')
        seen.add(key)
        if r['game_date'][:10] >= '2026-11-15' or r['game_id'] == player['game_id']:
            raise ValueError('TARGET_OR_FUTURE_GAME_IN_HISTORY')
        if stamp(r['source_available_at']) > stamp(freeze):
            raise ValueError('HISTORY_AFTER_CUTOFF')
        validate_value(market, r)
        if player['position'] == 'QB' and (r['game_id'], player['player_id']) not in starters:
            role_exclusions += 1
            continue
        selected.append(r)
    selected.sort(key=lambda r: (r['game_date'], r['game_id']))
    selected = selected[-CONFIG['max_history']:]
    if len(selected) < CONFIG['min_player']:
        raise ValueError('INSUFFICIENT_SOURCE_ROLE_APPEARANCES')
    return selected, role_exclusions


def quantile(masses, q):
    acc = 0.0
    for y, w in masses:
        acc += w
        if acc >= q - 1e-14:
            return y
    return masses[-1][0]


def distribution(player, history, model, forecast_at, freeze):
    if model not in ACTIVE:
        raise ValueError('MODEL_NOT_ACTIVATED')
    values = [validate_value(player['normalized_market'], r) for r in history]
    n = len(values)
    weights = np.array([2 ** (-(n-1-i)/CONFIG['half_life']) if model == EW else 1.0 for i in range(n)])
    weights /= weights.sum()
    law = empirical(values, weights.tolist())
    ess = float(1 / np.sum(weights**2))
    seed = int(sha(canonical([player['player_stat_id'], model, CONFIG]))[:16], 16)
    rng = np.random.default_rng(seed)
    # Weighted Bayesian bootstrap: explicitly conditional on observed support.
    # Mean concentration ESS is a modeling assumption, not reliability evidence.
    draws = rng.dirichlet(weights * ess, CONFIG['uncertainty_draws']) @ np.asarray(values)
    joint = [{'historical_game_id': r['game_id'], 'components': r['components'],
              'value': y, 'weight': float(w)} for r, y, w in zip(history, values, weights)]
    fingerprint = sha(canonical(dict(player=player, history=history, config=CONFIG, model=model)))
    return dict(game_id=player['game_id'], player_id=player['player_id'],
        player=player['player'], normalized_market=player['normalized_market'],
        period=player['period'], model_version=model, status='distribution',
        player_stat_id=player['player_stat_id'], predictive_mean=law.mean,
        predictive_variance=law.variance, pmf=law.parameters['masses'], joint_outcomes=joint,
        quantiles={str(q): quantile(law.parameters['masses'], q) for q in (.05, .25, .5, .75, .95)},
        support=dict(kind='signed_integer' if player['normalized_market'].endswith('yards') else 'nonnegative_integer',
                     observed_min=min(values), observed_max=max(values)),
        tail_assumption='finite_observed_support_only; unseen tails have zero modeled mass',
        dependence='same_game_source_pair' if len(FIELDS[player['normalized_market']]) == 2 else 'univariate',
        zero_mass=law.pmf(0), source_sample_depth=n, source_window_limit=10, effective_sample_size=ess,
        missing_source_observations=player.get('missing_stat_rows'),
        training_data_cutoff=freeze, latest_historical_game_date=max(r['game_date'] for r in history),
        historical_input_availability=max((r['source_available_at'] for r in history), key=stamp),
        model_input_fingerprint=fingerprint, forecast_at=forecast_at, kickoff_at=player['event_start_at'],
        eligibility=player['eligibility_status'], identity_source_sha256=player['identity_source_sha256'],
        role_source_sha256=player.get('role_source_sha256'), confirmed_participant=player['confirmed_game_day_active'],
        conditional_participation='starting_and_appearing' if player['position'] == 'QB' else 'appearing',
        participation_probability=None, role_uncertainty='archived_role_only; current_active_status_unconfirmed',
        parameter_uncertainty=dict(method='weighted_bayesian_bootstrap', seed=seed,
            draws=CONFIG['uncertainty_draws'], dirichlet_concentration=(weights*ess).tolist(),
            mean_q05=float(np.quantile(draws,.05)), mean_q95=float(np.quantile(draws,.95)),
            assumption='conditional_on_observed_support_and_exchangeable_games; no calibrated_coverage_claim'),
        sampling_uncertainty='limited_player_games; serial_and_role_dependence_not_identified',
        out_of_support_warning='any_contract_line_outside_observed_support_is_extrapolation_unsupported',
        calibration_status='uncalibrated', abstention_reason=None,
        distribution_sha256=sha(canonical(dict(pmf=law.parameters['masses'], joint_outcomes=joint))),
        research_only=True, production_ranking_allowed=False)


def contract_probabilities(d, contract, forecast_at):
    """Evaluate an immutable law without refitting or introducing synthetic lines."""
    c = contract['original_record']
    if contract['player_stat_id'] != d['player_stat_id'] or contract['normalized_market'] != d['normalized_market']:
        raise ValueError('CONTRACT_DISTRIBUTION_IDENTITY_MISMATCH')
    if (c['event_id'], c['period']) != (d['game_id'], d['period']):
        raise ValueError('CONTRACT_EVENT_PERIOD_MISMATCH')
    if not c['source_certified'] or not c.get('book') or not c.get('source_sha256'):
        raise ValueError('ORIGINAL_CONTRACT_SOURCE_UNVERIFIED')
    if stamp(c['source_received_at']) > stamp(forecast_at):
        raise ValueError('FUTURE_CONTRACT')
    line = float(c['line'])
    if not math.isfinite(line):
        raise ValueError('INVALID_LINE')
    under = math.fsum(p for y,p in d['pmf'] if y < line)
    over = math.fsum(p for y,p in d['pmf'] if y > line)
    push = math.fsum(p for y,p in d['pmf'] if y == line)
    if abs(over+under+push-1)>1e-12:
        raise ValueError('PROBABILITY_NORMALIZATION')
    return dict(candidate_id=c['candidate_id'], quote_id=c['quote_id'],
        player_stat_id=d['player_stat_id'], game_id=d['game_id'], player_id=d['player_id'],
        normalized_market=d['normalized_market'], period=d['period'], book=c['book'], line=line,
        model_version=d['model_version'], distribution_sha256=d['distribution_sha256'],
        q_over=over, q_under=under, q_push=push, forecast_at=forecast_at,
        source_sha256=c['source_sha256'], original_record_sha256=sha(canonical(c)),
        original_source_manifest_sha256=contract['original_source_manifest_sha256'],
        out_of_support=line<d['support']['observed_min'] or line>d['support']['observed_max'],
        settlement_semantics=c.get('settlement_semantics'),
        status='UNCERTIFIED_SHADOW_CONDITIONAL_APPEARANCE', research_only=True)


def bound(root, ref):
    path=(root/ref['path']).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('SOURCE_PATH_ESCAPE')
    raw=path.read_bytes()
    if sha(raw) != ref['sha256']:
        raise ValueError('SOURCE_SHA256_MISMATCH:'+ref['path'])
    return raw


def raw_rows(raw, name):
    if name.endswith('.gz'):
        obj=json.loads(gzip.decompress(raw))
        if isinstance(obj,list): return obj
        for key in ('rows','data','stats','games'):
            if isinstance(obj.get(key),list): return obj[key]
        raise ValueError('UNKNOWN_RAW_ARCHIVE_SCHEMA')
    import csv,io
    return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))


def verify_sources(root, pin, players, histories):
    """Independently bind every used component to raw stats and official schedules.

    Targets are official recorded targets, never inferred from receptions. Team
    passing attempts are summed from the same raw team-game, with missing exposure
    disclosed; no target-rate challenger is activated from unverified denominators.
    """
    stats={}; games={}; starters=set(); verified=[]; exposures=defaultdict(list)
    for ref in pin['source_evidence']:
        raw=bound(root,ref); verified.append(ref)
        if stamp(ref['source_available_at'])>stamp(pin['feature_freeze_at']):
            raise ValueError('RAW_SOURCE_AFTER_FREEZE')
        rows=raw_rows(raw,ref['path'])
        if 'games' in Path(ref['path']).name or {'home_qb_id','away_qb_id'} <= set(rows[0]):
            for r in rows:
                games[r['game_id']]=r
                for side in ('home','away'):
                    pid=r.get(side+'_qb_id')
                    if pid: starters.add((r['game_id'],'gsis:'+pid))
        elif 'stats' in Path(ref['path']).name or 'targets' in rows[0]:
            for r in rows:
                pid=r.get('player_id') or r.get('gsis_id'); gid=r.get('game_id')
                if not gid:
                    team=r.get('recent_team') or r.get('team')
                    matches=[g['game_id'] for g in games.values() if str(g.get('season'))==str(r.get('season'))
                             and str(g.get('week'))==str(r.get('week')) and team in (g.get('away_team'),g.get('home_team'))
                             and g.get('game_type')=='REG']
                    if len(matches)==1: gid=matches[0]
                if not gid or not pid: continue
                key=(ref['sha256'],'gsis:'+pid,gid)
                if key in stats: raise ValueError('DUPLICATE_RAW_PLAYER_GAME')
                stats[key]=r
                team=r.get('recent_team') or r.get('team')
                if team: exposures[(ref['sha256'],gid,team)].append(r)
    unavailable_exposure=0; target_checks=0
    for h in histories:
        r=stats.get((h['source_sha256'],h['player_id'],h['game_id']))
        g=games.get(h['game_id'])
        if not r or not g: raise ValueError('UNBOUND_HISTORICAL_RAW_RECORD')
        if g['gameday'][:10] != h['game_date'][:10] or h['game_date'][:10]>='2026-11-15':
            raise ValueError('RAW_GAME_DATE_MISMATCH_OR_LEAKAGE')
        for k,v in h['components'].items():
            if number(r.get(k))!=number(v): raise ValueError('RAW_COMPONENT_MISMATCH')
        validate_value(h['market'],h)
        if h['market']=='receiving_targets':
            targets=number(r.get('targets')); receptions=number(r.get('receptions'))
            if not 0<=receptions<=targets: raise ValueError('RECEPTIONS_TARGETS_INCONSISTENT')
            team=r.get('recent_team') or r.get('team')
            cohort=exposures.get((h['source_sha256'],h['game_id'],team),[])
            try:
                attempts=sum(number(x.get('attempts')) for x in cohort)
                completions=sum(number(x.get('completions')) for x in cohort)
                team_targets=sum(number(x.get('targets')) for x in cohort)
                if not cohort or attempts<=0: raise ValueError('MISSING_TEAM_EXPOSURE')
            except ValueError:
                unavailable_exposure+=1
            else:
                if not 0<=completions<=attempts or not targets<=team_targets<=attempts:
                    raise ValueError('TARGETS_PASSING_OPPORTUNITIES_INCONSISTENT')
                target_checks+=1
    # Eligibility identities and QB1 source hashes are verified as raw source bytes.
    old=pin['previous_canonical_manifest']
    old_bytes=bound(root,old); original=json.loads(old_bytes)
    sources=original['sources']; by_hash={r['sha256']:r for r in sources.values() if r.get('archive_path')}
    eligibility_raw={}
    for digest in {p.get(k) for p in players for k in ('identity_source_sha256','role_source_sha256')} - {None}:
        rec=by_hash[digest]
        if stamp(rec['source_received_at'])>stamp(pin['feature_freeze_at']): raise ValueError('FUTURE_ELIGIBILITY_SOURCE')
        eligibility_raw[digest]=json.loads(bound(root,dict(path='reports/nfl_20261115_prospective/'+rec['archive_path'],sha256=digest)))
    for p in players:
        if p['position']!='QB' or not p['model_input_ready']: continue
        depth=eligibility_raw[p['role_source_sha256']]
        first=[]
        for chart in depth.get('depthchart') or depth.get('depthCharts') or []:
            for key,pos in (chart.get('positions') or {}).items():
                if str(key).lower() not in ('qb','quarterback'): continue
                ordered=pos.get('athletes') or []
                if ordered:
                    node=ordered[0].get('athlete') or ordered[0]
                    if node.get('id'): first.append(str(node['id']))
        if set(first)!={p['espn_player_id']}: raise ValueError('RAW_EXPECTED_STARTER_MISMATCH')
    return starters,dict(raw_files_verified=len(verified), eligibility_sources_verified=len(eligibility_raw),
                         target_opportunity_checks=target_checks, target_exposure_unavailable=unavailable_exposure,
                         evidence=verified)


def write_once(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f: f.write(data)
    return dict(path=str(path),sha256=sha(data),bytes=len(data))


def run(root, out, code_commit):
    root=Path(root).resolve(); out=Path(out)
    pin_raw=bound(root,dict(path=PIN_PATH,sha256=PIN_SHA));pin=json.loads(pin_raw)
    bound(root,pin['expanded_manifest'])
    if pin['previous_canonical_manifest']['sha256']!=OLD_SHA: raise ValueError('WRONG_BASELINE')
    tables={k:[json.loads(l) for l in bound(root,r).splitlines()] for k,r in pin['tables'].items()}
    players=tables['player_stats'];histories=tables['paired_history']
    if len({(p['game_id'],p['player_id'],p['normalized_market'],p['period']) for p in players}) != len(players):
        raise ValueError('DUPLICATE_PLAYER_STAT')
    starters,source_audit=verify_sources(root,pin,players,histories)
    by_stat=defaultdict(list)
    for r in histories: by_stat[r['player_stat_id']].append(r)
    # Every original offer is bound to its archived provider bytes, even when unmodeled.
    original=json.loads(bound(root,pin['previous_canonical_manifest']))
    source_by_hash={r['sha256']:r for r in original['sources'].values() if r.get('archive_path')}
    for digest in {c['original_record']['source_sha256'] for c in tables['original_contracts']}:
        rec=source_by_hash[digest]
        bound(root,dict(path='reports/nfl_20261115_prospective/'+rec['archive_path'],sha256=rec['sha256']))
    old_index=root/'reports/nfl_20261115_prospective/simple_models/sunday_first_forecasts_v1/INDEX.json'
    old_index_hash=sha(old_index.read_bytes())
    old_pop=old_index.parent/'first_forecast_population.jsonl'; old_pop_hash=sha(old_pop.read_bytes())
    if old_index_hash!='cc8049b9335b09d578b9ecae8982616e88c8f0208f06114ab720291413ec85a4' or old_pop_hash!='766245a051b4b3247009040a0c28df82fde285fb237ab40087d510bcfd4efd5d':
        raise ValueError('FROZEN_BASELINE_BYTES_CHANGED')
    now=datetime.now(timezone.utc).isoformat()
    code_hashes={str(Path(__file__).name):sha(Path(__file__).read_bytes()),
                 'nfl_marginal_shadow.py':sha(Path(__file__).with_name('nfl_marginal_shadow.py').read_bytes())}
    model_sha=sha(canonical(dict(config=CONFIG,code=code_hashes,models=ACTIVE)))
    rows=[];canaries=[];canary_markets=set();matrix=defaultdict(Counter)
    # Genuine first-player canaries run before bulk generation. T+A remains explicit abstention.
    for p in players:
        if p['normalized_market'] in canary_markets: continue
        try: hs,excluded=select_history(p,by_stat[p['player_stat_id']],pin['feature_freeze_at'],now,starters)
        except ValueError: continue
        r=distribution(p,hs,EW,now,pin['feature_freeze_at'])
        assert abs(sum(w for _,w in r['pmf'])-1)<1e-12
        assert all(x['value']==sum(x['components'].values()) for x in r['joint_outcomes'])
        r['model_sha256']=model_sha;r['source_pin_sha256']=PIN_SHA
        r['canary_checked_at']=datetime.now(timezone.utc).isoformat()
        canaries.append(r);canary_markets.add(p['normalized_market'])
    for p in players:
        reason=None;hs=[];excluded=0
        try: hs,excluded=select_history(p,by_stat[p['player_stat_id']],pin['feature_freeze_at'],now,starters)
        except ValueError as exc: reason=str(exc)
        for model in (*ACTIVE,*UNAVAILABLE):
            r=dict(game_id=p['game_id'],player_id=p['player_id'],player=p['player'],
                player_stat_id=p['player_stat_id'],normalized_market=p['normalized_market'],period=p['period'],
                model_version=model,forecast_at=now,status='abstention',research_only=True,
                training_data_cutoff=pin['feature_freeze_at'],source_pin_sha256=PIN_SHA,
                model_sha256=model_sha,model_input_fingerprint=sha(canonical(dict(player=p,history=by_stat[p['player_stat_id']],model=model,config=CONFIG))),
                eligibility=p['eligibility_status'],conditional_participation='starting_and_appearing' if p['position']=='QB' else 'appearing')
            why=reason
            if model in UNAVAILABLE:
                why=('ORIGINAL_FROZEN_PRODUCTION_CONTROL_NOT_AVAILABLE' if model.startswith(('S6','S7')) else
                     'SOURCE_BOUND_HISTORICAL_ROLE_PEERS_NOT_AVAILABLE')
                if reason: why=reason+';'+why
            if why: r['abstention_reason']=why
            else:
                r=distribution(p,hs,model,now,pin['feature_freeze_at'])
                r['historical_nonstarter_games_excluded']=excluded
                r['model_sha256']=model_sha;r['source_pin_sha256']=PIN_SHA
            rows.append(r);matrix[(model,p['normalized_market'])][r['status']]+=1
    ds={(r['player_stat_id'],r['model_version']):r for r in rows if r['status']=='distribution'}
    contracts=[];contract_seen=set()
    for c in tables['original_contracts']:
        if c['candidate_id'] in contract_seen: raise ValueError('DUPLICATE_ORIGINAL_CONTRACT')
        contract_seen.add(c['candidate_id'])
        for model in ACTIVE:
            d=ds.get((c['player_stat_id'],model))
            r=dict(candidate_id=c['candidate_id'],quote_id=c['quote_id'],model_version=model,
                   normalized_market=c['normalized_market'],status='abstention',abstention_reason='NO_ELIGIBLE_DISTRIBUTION')
            if d:
                try:r=contract_probabilities(d,c,now)
                except ValueError as exc:r['abstention_reason']=str(exc)
            contracts.append(r)
    # Last timing gate uses actual completion clock, never a requested/backdated timestamp.
    completed=datetime.now(timezone.utc).isoformat()
    if any(stamp(d['kickoff_at'])<=stamp(completed) for d in ds.values()):
        raise ValueError('KICKOFF_PASSED_DURING_EXECUTION_NO_LEDGER_PUBLISHED')
    out.mkdir(parents=True,exist_ok=False)
    artifacts={}
    for name,data in [('canaries',canaries),('distributions_and_abstentions',rows),('original_contract_evaluations',contracts)]:
        artifacts[name]=write_once(out/(name+'.jsonl'),b''.join(canonical(r)+b'\n' for r in data))
        artifacts[name]['rows']=len(data)
    manifest=dict(schema='ws2-ws6-distribution-handoff-v2',status='UNCERTIFIED_SHADOW',
        forecast_at=now,completed_at=completed,code_commit=code_commit,code_sha256=code_hashes,
        model_sha256=model_sha,configuration=CONFIG,source_pin_sha256=PIN_SHA,source_pin_path=PIN_PATH,
        source_manifest_sha256=OLD_SHA,source_audit=source_audit,artifacts=artifacts,
        player_stat_universe=len(players),original_contract_universe=len(contract_seen),
        real_player_stat_distribution_counts={m:sum(r['status']=='distribution' and r['model_version']==m for r in rows) for m in ACTIVE},
        authentic_contract_probability_counts={m:sum(r['status'].startswith('UNCERTIFIED') and r['model_version']==m for r in contracts) for m in ACTIVE},
        model_market_matrix=[dict(model=m,market=k,**matrix[(m,k)]) for m in (*ACTIVE,*UNAVAILABLE) for k in FIELDS],
        unsupported_canaries={m:'TACKLE_ACCOUNTING_NOT_INDEPENDENTLY_CERTIFIED' for m in FIELDS if m not in canary_markets},
        preserved_baseline=dict(index_sha256=old_index_hash,population_sha256=old_pop_hash,forecasts=1672),
        calibration='NONE; calibrated_variants_abstain_NO_FROZEN_CHRONOLOGICALLY_VALIDATED_CALIBRATOR',
        additional_model_investigation=dict(shrunk_empirical='abstain_missing_role_peers',regularized_target_rate='abstain_missing_frozen_rate_prior',
            team_passing_exposure='raw_historical_consistency_checks_only_no_frozen_pregame_exposure_model',
            overdispersed_counts='S4_abstain_missing_role_peers',position_prior='abstain_missing_historical_role_binding'),
        production_modified=False,release_authority=False,
        limitations=pin['limitations']+['Ten observed games supplied by WS1; QB subsets may be smaller',
            'Joint outcomes enforce component sums; independently estimated marginal histories need not share a sample window',
            'Sampling/role dependence and unseen tail uncertainty unresolved; no accuracy or edge claim',
            'Historical chronological promotion validation blocked by original as-of availability; no calibrator promotion'])
    assert sha(old_index.read_bytes())==old_index_hash and sha(old_pop.read_bytes())==old_pop_hash
    ref=write_once(out/'HANDOFF_WS6.json',canonical(manifest)+b'\n')
    return dict(handoff=ref,**{k:manifest[k] for k in ('forecast_at','completed_at','real_player_stat_distribution_counts',
        'authentic_contract_probability_counts','model_market_matrix','unsupported_canaries','model_sha256','preserved_baseline')})
