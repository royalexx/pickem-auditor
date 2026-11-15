"""O1–O5 lower-information research models; never a source collector.

Strict WS1 interchange is documented in README. Hashing proves byte identity,
not source truth. The consumer requires original source clocks and identities;
certification still belongs to WS1. No outcome or production modules imported.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from zoneinfo import ZoneInfo
import numpy as np

VERSION = 'nfl-opportunity-20261115-v1-tackle-repair-v252'
DAY = '2026-11-15'
MODELS = ('O1-context-volume-v1', 'O2-position-usage-v1', 'O3-qb-mean-preserving-v1',
          'O4-defensive-components-v1', 'O5-role-mixture-v1')
# Frozen sensitivity assumptions, not learned or optimized on Sunday outcomes.
ROLE_WEIGHTS = (.2, .6, .2)
ROLE_MULTIPLIERS = (.6, 1., 1.25)
DEFENSE = {'LB', 'MLB', 'ILB', 'OLB', 'DE', 'DT', 'NT', 'CB', 'DB', 'S', 'FS', 'SS'}
QB_MARKETS = {'pass attempts', 'completions', 'passing yards', 'qb rushing attempts', 'qb rushing yards'}
COMPONENTS = ('solo', 'with_assist', 'tackle_assists')
TEAM_FIELDS = {'game_id','team','opponent','season','week','end_at','source_id',
               'plays','pass_attempts','rush_attempts','sacks','pace_seconds'}
PLAYER_FIELDS = {'game_id','team','player_id','position','season','week','end_at','source_id',
                 'state','snaps','routes','targets','receptions','receiving_yards','carries',
                 'rushing_yards','pass_attempts','completions','passing_yards','designed_runs',
                 'scrambles','solo','with_assist','tackle_assists'}
ROSTER_FIELDS = {'game_id','team','player_id','position','source_id','status',
                 'participation_probability','expected_starter','starter_probability'}
EVENT_FIELDS = {'game_id','home','away','season','week','event_start','source_id'}
CONTRACT_FIELDS = {'contract_id','game_id','team','player_id','stat','line','period',
                   'source_id','dnp_policy','frozen_60_40','market','comparison_probabilities',
                   'quote_id','book','over_odds','under_odds','original_contract'}

class GateError(ValueError):
    pass

def require(ok, reason):
    if not ok:
        raise GateError(reason)

def stamp(value):
    require(isinstance(value, str) and 'T' in value, 'timestamp_missing')
    try:
        t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise GateError('timestamp_invalid') from exc
    require(t.tzinfo is not None, 'timestamp_naive')
    return t.astimezone(timezone.utc)

def number(value, label, lo=0, hi=math.inf):
    require(type(value) in (int, float) and math.isfinite(value) and lo <= value <= hi,
            'invalid_' + label)
    return float(value)

def canonical(x):
    return (json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def strict_json(raw):
    def pairs(items):
        out = {}
        for k,v in items:
            require(k not in out, 'duplicate_json_key')
            out[k] = v
        return out
    def bad_constant(value):
        raise GateError('nonfinite_json_constant')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)

def seed(*parts):
    return int(sha(canonical(parts))[:16], 16)

def summary(x):
    x = np.asarray(x)
    require(x.size > 0 and np.isfinite(x).all(), 'invalid_draws')
    return {'mean': float(x.mean()), 'sd': float(x.std()),
            'q05': float(np.quantile(x, .05)), 'q50': float(np.quantile(x, .5)),
            'q95': float(np.quantile(x, .95))}

def distribution(x):
    values, counts = np.unique(x,return_counts=True)
    return {'family':'empirical_predictive','samples':int(len(x)),
            'values':values.tolist(),'masses':(counts/len(x)).tolist()}

def oup(x, line):
    number(line, 'line', -math.inf)
    p = {'over': float(np.mean(x > line)), 'under': float(np.mean(x < line)),
         'push': float(np.mean(x == line))}
    require(abs(sum(p.values()) - 1) < 1e-12, 'probability_noncomplementary')
    return p

def probability_object(p):
    require(isinstance(p, dict) and set(p) == {'over','under','push'}, 'probability_schema')
    for k, v in p.items():
        number(v, k, 0, 1)
    require(abs(sum(p.values()) - 1) < 1e-8, 'probability_noncomplementary')

def unique(rows, fields, label):
    ids = [tuple(r.get(k) for k in fields) for r in rows]
    require(all(all(isinstance(x, str) and x for x in k) for k in ids), 'missing_' + label)
    require(len(ids) == len(set(ids)), 'duplicate_' + label)

def load_packet(path, expected_sha, now):
    """Read WS1-produced local bytes only. No network, source collection or backfill."""
    path = Path(path).resolve()
    raw = path.read_bytes()
    require(sha(raw) == expected_sha, 'manifest_hash_mismatch')
    manifest = strict_json(raw)
    require(manifest.get('schema') == 'ws1-nfl-pregame-opportunity-v1', 'unsupported_ws1_schema')
    require(manifest.get('producer_workstream') == 1 and manifest.get('day') == DAY,
            'wrong_producer_or_day')
    freeze = stamp(manifest.get('input_freeze_at'))
    cutoff = stamp(manifest.get('training_cutoff_at'))
    now = stamp(now)
    require(cutoff <= freeze <= now, 'cutoff_chronology')
    sources = manifest.get('sources')
    require(isinstance(sources, list) and sources, 'missing_original_sources')
    unique(sources, ('source_id',), 'source')
    source_map = {}
    for s in sources:
        require(isinstance(s.get('sha256'),str) and re.fullmatch('[0-9a-f]{64}',s['sha256']),
                'missing_source_hash')
        require(s.get('original') is True and isinstance(s.get('provider'),str) and s['provider'],
                'not_original_source')
        source_path = (path.parent / s.get('path','')).resolve()
        require(source_path.is_relative_to(path.parent) and source_path.is_file(), 'missing_original_source_bytes')
        hasher = hashlib.sha256()
        with source_path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                hasher.update(chunk)
        require(hasher.hexdigest() == s['sha256'], 'original_source_hash_mismatch')
        available, ingested = stamp(s.get('first_available_at')), stamp(s.get('ingested_at'))
        require(available <= ingested <= freeze, 'source_after_freeze')
        source_map[s['source_id']] = s
    packet = {'manifest': manifest, 'manifest_sha256': expected_sha, 'forecast_at': now.isoformat()}
    fields = {'events':EVENT_FIELDS, 'team_history':TEAM_FIELDS, 'player_history':PLAYER_FIELDS,
              'roster':ROSTER_FIELDS, 'contracts':CONTRACT_FIELDS}
    files = manifest.get('files', {})
    require(set(files) == set(fields), 'missing_input_table')
    for name, allowed in fields.items():
        desc = files[name]
        target = (path.parent / desc['path']).resolve()
        require(target.is_relative_to(path.parent), 'input_path_escape')
        data = target.read_bytes()
        require(sha(data) == desc['sha256'], 'table_hash_mismatch_' + name)
        rows = strict_json(data)
        require(isinstance(rows, list), 'invalid_table_' + name)
        for row in rows:
            require(isinstance(row,dict) and set(row) <= allowed, 'unknown_feature_' + name)
            require(row.get('source_id') in source_map, 'unbound_source_' + name)
            if name.endswith('_history'):
                end = stamp(row.get('end_at'))
                src = source_map[row['source_id']]
                require(end <= stamp(src['first_available_at']) <= stamp(src['ingested_at']) <= cutoff,
                        'historical_source_after_training_cutoff')
        packet[name] = rows
    validate(packet)
    return packet

def validate(p):
    cutoff = stamp(p['manifest']['training_cutoff_at'])
    require(cutoff <= stamp(p['manifest']['input_freeze_at']) <= stamp(p['forecast_at']), 'cutoff_chronology')
    events, teams, players, roster, contracts = (p[k] for k in
        ('events','team_history','player_history','roster','contracts'))
    unique(events, ('game_id',), 'event')
    unique(teams, ('game_id','team'), 'team_game')
    unique(players, ('game_id','player_id'), 'player_game')
    unique(roster, ('game_id','player_id'), 'roster_player')
    unique(contracts, ('contract_id',), 'contract')
    require(events, 'missing_target_events')
    identities = [(c.get('game_id'),c.get('team'),c.get('player_id'),c.get('stat'),c.get('line'),
                   c.get('period'),c.get('book'),c.get('quote_id')) for c in contracts]
    require(len(identities)==len(set(identities)), 'duplicate_exact_contract')
    em = {e['game_id']: e for e in events}
    for e in events:
        for h in [e]+teams+players:
            require(type(h.get('season')) is int and type(h.get('week')) is int
                    and 1 <= h['week'] <= 22, 'invalid_season_week')
        require(e['home'] != e['away'], 'self_opponent')
        require(stamp(e['event_start']).astimezone(ZoneInfo('America/Toronto')).date().isoformat() == DAY,
                'wrong_event_day')
        require(stamp(p['forecast_at']) < stamp(e['event_start']), 'kickoff_passed')
        for h in teams + players:
            require(stamp(h['end_at']) <= cutoff, 'historical_game_after_training_cutoff')
            require((h['season'], h['week']) < (e['season'], e['week']), 'future_week_training')
            require(h['game_id'] != e['game_id'] and stamp(h['end_at']) < stamp(e['event_start']),
                    'target_event_in_training')
    tm = {(r['game_id'],r['team']):r for r in teams}
    for t in teams:
        for k in ('plays','pass_attempts','rush_attempts','sacks'):
            number(t.get(k),k)
            require(float(t[k]).is_integer(), 'noninteger_team_exposure')
        require(t['plays'] == t['pass_attempts'] + t['rush_attempts'] + t['sacks'],
                'team_exposure_nonconservation')
        require(t['plays'] > 0, 'zero_team_plays')
        require(t['team'] != t['opponent'], 'historical_self_opponent')
        opposite = tm.get((t['game_id'],t['opponent']))
        if opposite is not None:
            require(opposite['opponent']==t['team'] and
                    (opposite['season'],opposite['week'])==(t['season'],t['week']),
                    'historical_team_pair_mismatch')
        if t.get('pace_seconds') is not None:
            number(t['pace_seconds'], 'pace_seconds', 1, 120)
    for r in players:
        require((r['game_id'],r['team']) in tm, 'missing_historical_team')
        require(r.get('state') in ('played','dnp','unknown'), 'missing_participation_state')
        for k in PLAYER_FIELDS - {'game_id','team','player_id','position','season','week',
                                  'end_at','source_id','state'}:
            if r.get(k) is not None:
                number(r[k], k, -math.inf if k.endswith('_yards') else 0)
                if not k.endswith('_yards'):
                    require(float(r[k]).is_integer(), 'noninteger_player_count_' + k)
        if r['state'] != 'played':
            require(all(r.get(k) is None for k in ('snaps','targets','carries',*COMPONENTS)),
                    'nonparticipant_numeric_workload')
        t = tm[r['game_id'],r['team']]
        require((r['season'],r['week'],r['end_at'])==(t['season'],t['week'],t['end_at']),
                'player_team_historical_identity_mismatch')
        if r.get('position') in DEFENSE:
            opp = tm.get((r['game_id'],t['opponent']))
            require(opp is not None, 'missing_opponent_exposure')
            if r.get('snaps') is not None:
                require(r['snaps'] <= opp['plays'], 'snap_share_range')
            if all(r.get(k) is not None for k in COMPONENTS) and r.get('snaps') is not None:
                pass # Combined credits are not a mutually exclusive snap allocation.
        if r.get('routes') is not None:
            require(r['routes'] <= t['pass_attempts'] + t['sacks'], 'route_share_range')
            if r.get('targets') is not None:
                require(r['targets'] <= r['routes'], 'targets_exceed_routes')
        for k, cap in (('targets','pass_attempts'),('pass_attempts','pass_attempts'),('carries','rush_attempts')):
            if r.get(k) is not None:
                require(r[k] <= t[cap], 'player_exposure_range')
        if r.get('receptions') is not None and r.get('targets') is not None:
            require(r['receptions'] <= r['targets'], 'receptions_exceed_targets')
        if r.get('completions') is not None and r.get('pass_attempts') is not None:
            require(r['completions'] <= r['pass_attempts'], 'completions_exceed_attempts')
    for r in roster:
        e = em.get(r['game_id'])
        require(e is not None and r['team'] in (e['home'],e['away']), 'roster_identity_mismatch')
        require(r.get('status') in ('available','uncertain','out'), 'unknown_roster_status')
        if r.get('participation_probability') is not None:
            number(r['participation_probability'],'participation_probability',0,1)
        if r.get('expected_starter') is not None:
            require(type(r['expected_starter']) is bool, 'invalid_starter_identity_flag')
        if r.get('starter_probability') is not None:
            number(r['starter_probability'],'starter_probability',0,1)
    for e in events:
        for team in (e['home'],e['away']):
            require(sum(r.get('expected_starter') is True for r in roster
                        if r['game_id'] == e['game_id'] and r['team'] == team and r['position'] == 'QB') <= 1,
                    'duplicate_starting_qb')
    for c in contracts:
        require(all(isinstance(c.get(k),str) and c[k] for k in
                    ('game_id','team','player_id','stat','book','quote_id')), 'incomplete_contract_identity')
        require(c.get('game_id') in em, 'unknown_contract_event')
        number(c.get('line'), 'line', -math.inf)
        require(c.get('period') == 'full_game' and c.get('dnp_policy') == 'void',
                'unsupported_contract_terms')
        for name in ('frozen_60_40','market'):
            if c.get(name) is not None:
                probability_object(c[name])
    # Aggregated observed identities must conserve historical team exposures too.
    for key,t in tm.items():
        ps = [r for r in players if (r['game_id'],r['team']) == key]
        for metric, cap in (('targets','pass_attempts'),('pass_attempts','pass_attempts'),('carries','rush_attempts')):
            require(sum(r.get(metric) or 0 for r in ps) <= t[cap], 'aggregate_historical_' + metric)

def defensive_parameters(played, teams, players, position):
    """Same-team historical exposure adapter; no manufactured missing denominator."""
    require(len(played)>=3,'insufficient_defensive_history')
    require(all(all(h.get(k) is not None for k in (*COMPONENTS,'snaps')) for h in played),
            'missing_official_tackle_component_or_snaps')
    def exposure(h):
        t=teams[h['game_id'],h['team']]
        return teams[h['game_id'],t['opponent']]['plays']
    require(all(h['snaps']>0 and h['snaps']<=exposure(h) for h in played),'invalid_defensive_exposure')
    for h in played:
        require(all(isinstance(h[k],(int,float)) and math.isfinite(h[k]) and h[k]>=0 and float(h[k]).is_integer() for k in COMPONENTS),'invalid_tackle_component')
    recent=played[-2:];den=sum(exposure(h) for h in recent);snaps=sum(h['snaps'] for h in recent)
    peers=[h for h in players if h['position']==position and h['state']=='played' and h.get('snaps') and
           all(h.get(k) is not None for k in COMPONENTS)]
    peer_den=sum(h['snaps'] for h in peers)
    require(peer_den>0,'missing_defensive_position_prior')
    prior=sum(sum(h[k] for k in COMPONENTS) for h in peers)/peer_den
    require(prior>0,'nonpositive_defensive_position_prior')
    return {'snap_alpha':1+snaps,'snap_beta':1+den-snaps,
            'rate_alpha':sum(sum(h[k] for k in COMPONENTS) for h in played)+120*prior,
            'rate_beta':sum(h['snaps'] for h in played)+120,
            'history_games':len(played),'peer_snap_denominator':peer_den}


class OpportunityModel:
    def __init__(self, packet, draws=8192):
        require(type(draws) is int and 1024 <= draws <= 65536, 'draw_budget')
        validate(packet)
        self.p, self.n = packet, draws
        self.teams = {(r['game_id'],r['team']):r for r in packet['team_history']}
        self.players = packet['player_history']
        self.cutoff = stamp(packet['manifest']['training_cutoff_at'])

    @classmethod
    def from_defensive_history(cls, teams, players, freeze, draws=4096):
        """Bounded adapter for the pinned WS1 defensive-only handoff.

        The caller authenticates receipt hashes before this API. This validates
        the model inputs without pretending to construct an offensive roster.
        """
        require(1024<=draws<=65536,'draw_budget')
        cutoff=stamp(freeze)
        for h in players:
            require(stamp(h['end_at'])<cutoff,'future_defensive_history')
            require((h['game_id'],h['team']) in teams,'missing_defensive_team_history')
        for h in teams.values():
            require(stamp(h['end_at'])<cutoff,'future_team_history')
            require(h['plays']==h['pass_attempts']+h['rush_attempts']+h['sacks'],'team_play_accounting')
        obj=cls.__new__(cls)
        obj.n=draws;obj.teams=teams;obj.players=players;obj.cutoff=cutoff;obj.p={}
        return obj

    def history(self, r):
        # Recent role requires same-team history, not stale roles before a transfer.
        return sorted([h for h in self.players if h['player_id'] == r['player_id']
                       and h['team'] == r['team']], key=lambda h:(h['season'],h['week']))[-8:]

    def played(self, r, fields):
        return [h for h in self.history(r) if h['state'] == 'played'
                and all(h.get(k) is not None for k in fields)]

    def rate(self, r, field, exposure, pseudo=60):
        obs = self.played(r, (field,))
        peers = [h for h in self.players if h['position'] == r['position']
                 and h['state'] == 'played' and h.get(field) is not None]
        def den(h):
            return self.teams[h['game_id'],h['team']][exposure]
        require(obs and peers, 'missing_' + field + '_history')
        d = sum(den(h) for h in obs)
        pd = sum(den(h) for h in peers)
        require(d > 0 and pd > 0, 'missing_' + exposure)
        prior = sum(h[field] for h in peers)/pd
        return float(np.clip((sum(h[field] for h in obs) + pseudo*prior)/(d+pseudo), .00001,.99999))

    def conversion(self, r, success, exposure, rng):
        obs = self.played(r, (success,exposure))
        peers = [h for h in self.players if h['position'] == r['position'] and
                 h['state'] == 'played' and h.get(success) is not None and h.get(exposure) is not None]
        require(obs and peers, 'missing_' + success + '_conversion')
        den = sum(h[exposure] for h in obs)
        peerden = sum(h[exposure] for h in peers)
        require(den > 0 and peerden > 0, 'zero_conversion_exposure')
        prior = np.clip(sum(h[success] for h in peers)/peerden, .001,.999)
        num = sum(h[success] for h in obs)
        return rng.beta(num+20*prior, den-num+20*(1-prior),self.n)

    def yards(self, r, field, exposure, count, rng):
        obs = self.played(r,(field,exposure))
        require(obs, 'missing_' + field)
        den = sum(h[exposure] for h in obs)
        require(den > 0, 'zero_yardage_exposure')
        # Signed aggregate yardage; no invented route depth or play tracking.
        mean = sum(h[field] for h in obs)/den
        scale = max(2., float(np.std([h[field]/h[exposure] for h in obs if h[exposure]>0])))
        sampled_mean = rng.normal(mean, scale/math.sqrt(max(1,len(obs))), self.n)
        y = np.rint(count*sampled_mean + np.sqrt(count)*scale*rng.standard_t(5,self.n))
        return np.where(count > 0,y,0).astype(int)

    def environment(self, e):
        rng = np.random.default_rng(seed(VERSION,e['game_id'],'O1'))
        common = rng.normal(0,.07,self.n)
        script = rng.normal(0,.20,self.n)  # zero-mean prior uncertainty, not final script
        env = {}
        for j,(team,opp) in enumerate(((e['home'],e['away']),(e['away'],e['home']))):
            off = sorted([h for h in self.teams.values() if h['team']==team],key=lambda h:(h['season'],h['week']))[-10:]
            defense = sorted([h for h in self.teams.values() if h['opponent']==opp],key=lambda h:(h['season'],h['week']))[-10:]
            require(len(off)>=3 and len(defense)>=3, 'insufficient_team_context')
            # V3 causal decomposition, lower-information variant, not the original V3 ridge/blend.
            mu = .5*np.mean([h['plays'] for h in off]) + .5*np.mean([h['plays'] for h in defense])
            rate = .5*sum(h['pass_attempts'] for h in off)/sum(h['plays'] for h in off)
            rate += .5*sum(h['pass_attempts'] for h in defense)/sum(h['plays'] for h in defense)
            sack = (sum(h['sacks'] for h in off)+1)/(sum(h['plays'] for h in off)+40)
            plays = rng.poisson(mu*np.exp(common+rng.normal(0,.07,self.n)-.07**2))
            sacks = rng.binomial(plays,np.clip(sack,0,.3))
            available = plays-sacks
            # Convert unconditional pass rate to a nonsack pass rate.
            rate = np.clip(rate/(1-sack),.01,.99)
            fraction = 1/(1+np.exp(-(math.log(rate/(1-rate)) + (-1 if j else 1)*script)))
            attempts = rng.binomial(available,fraction)
            pace = [h['pace_seconds'] for h in off+defense if h.get('pace_seconds') is not None]
            env[team] = {'plays':plays,'pass_attempts':attempts,'rush_attempts':available-attempts,
                         'sacks':sacks,'pace_seconds':rng.choice(pace,self.n) if pace else None}
        return env

    def offense(self, e, team, env, mixture=False):
        rng = np.random.default_rng(seed(VERSION,e['game_id'],team,'O5' if mixture else 'O2O3'))
        roster = sorted([r for r in self.p['roster'] if r['game_id']==e['game_id'] and
                         r['team']==team and r['position'] in {'QB','RB','WR','TE'}],key=lambda r:r['player_id'])
        results, diagnostics, active, role, errors = {}, {}, {}, {}, {}
        for r in roster:
            pid = r['player_id']
            results[pid] = {}
            try:
                require(r.get('participation_probability') is not None,'missing_participation_probability')
                prob = r['participation_probability']
                require(r['status'] != 'out' or prob == 0,'out_player_positive_participation')
                require(self.history(r), 'missing_player_history')
                require((stamp(e['event_start'])-stamp(self.history(r)[-1]['end_at'])).days <= 28,
                        'stale_player_role')
                active[pid] = rng.random(self.n) < prob
                role[pid] = rng.choice(ROLE_MULTIPLIERS,self.n,p=ROLE_WEIGHTS) if mixture else np.ones(self.n)
                diagnostics[pid] = {'history_games':len(self.history(r)), 'p_participation':prob,
                    'role_states':list(ROLE_MULTIPLIERS) if mixture else [1.],
                    'role_weights':list(ROLE_WEIGHTS) if mixture else [1.],
                    'availability_unknown_history':sum(h['state']=='unknown' for h in self.history(r))}
                if r['position']=='QB':
                    require(r.get('expected_starter') is True and r.get('starter_probability') is not None
                            and r['starter_probability'] > 0,'qb_not_identified_pregame_starter')
                    # Starter/nonstarter kept separate. Primary props conditional on starting.
                    diagnostics[pid]['p_start'] = r['starter_probability']
                    diagnostics[pid]['backup_scenario'] = 'not_in_primary_cohort; no_full_starter_workload'
            except GateError as exc:
                errors[pid] = str(exc)
        good = [r for r in roster if r['player_id'] not in errors]
        route_caps, route_target_means = {}, {}
        for r in good:
            if r['position'] not in {'WR','TE','RB'}:
                continue
            pid = r['player_id']
            obs = self.played(r, ('routes','targets'))
            if not obs:
                diagnostics[pid]['route_dependency'] = 'unavailable; targets-per-attempt variant'
                continue
            try:
                dropbacks = sum(self.teams[h['game_id'],h['team']]['pass_attempts'] +
                                self.teams[h['game_id'],h['team']]['sacks'] for h in obs)
                routes = sum(h['routes'] for h in obs)
                require(dropbacks > 0 and routes > 0, 'zero_route_exposure')
                share = rng.beta(1+routes,1+dropbacks-routes,self.n)
                route_caps[pid] = rng.binomial(env['pass_attempts']+env['sacks'],share)*active[pid]
                results[pid]['routes'] = route_caps[pid]
                tprr = self.conversion(r,'targets','routes',rng)
                route_target_means[pid] = float(np.mean((env['pass_attempts']+env['sacks'])*share*tprr)
                                               /max(1.,np.mean(env['pass_attempts'])))
                diagnostics[pid]['route_participation'] = summary(share)
                diagnostics[pid]['target_probability_per_route'] = summary(tprr)
                diagnostics[pid]['route_history_games'] = len(obs)
            except GateError as exc:
                diagnostics[pid]['route_dependency'] = str(exc)
        # One residual bucket retains opportunities for omitted players and throwaways.
        for metric,cap,positions in (('targets','pass_attempts',{'WR','TE','RB'}),
                                    ('carries','rush_attempts',{'RB','QB','WR','TE'})):
            eligible, means = [], []
            for r in good:
                if r['position'] not in positions: continue
                try:
                    means.append(route_target_means[r['player_id']] if metric == 'targets' and
                                 r['player_id'] in route_target_means else self.rate(r,metric,cap))
                    eligible.append(r)
                except GateError as exc:
                    diagnostics[r['player_id']]['missing_'+metric] = str(exc)
            if not eligible: continue
            # Cap total allocated mean at 98%; do not force a partial roster to exhaust volume.
            means = np.asarray(means)
            means *= min(1.,.98/means.sum())
            alpha = np.r_[means,1-means.sum()]*80
            weights = rng.dirichlet(alpha,self.n)
            for j,r in enumerate(eligible):
                weights[:,j] *= role[r['player_id']]*active[r['player_id']]
            weights /= weights.sum(axis=1,keepdims=True)
            remaining = env[cap].copy()
            remaining_p = np.ones(self.n)
            for j,r in enumerate(eligible):
                prob = np.clip(weights[:,j]/np.maximum(remaining_p,1e-12),0,1)
                draw = rng.binomial(remaining,prob)
                if metric == 'targets' and r['player_id'] in route_caps:
                    draw = np.minimum(draw, route_caps[r['player_id']])
                results[r['player_id']][metric] = draw
                remaining -= draw; remaining_p -= weights[:,j]
            require((remaining>=0).all(),'sample_exposure_nonconservation')
            diagnostics['team_'+metric] = {'residual':summary(remaining),
                'max_conservation_error':int(np.max(np.abs(sum(results[r['player_id']][metric] for r in eligible)+remaining-env[cap])))}
        for r in good:
            pid = r['player_id']; vals = results[pid]
            if r['position']=='QB':
                try:
                    s = self.rate(r,'pass_attempts','pass_attempts',pseudo=26)
                    share = rng.beta(60*s,60*(1-s),self.n)
                    vals['pass attempts'] = rng.binomial(env['pass_attempts'],share)*active[pid]
                    diagnostics[pid]['qb_share'] = {'historical_shrunk_share':s,
                        'old_v4_beta_mean':(12+35*s)/59,'v41_beta_mean':(1+60*s)/62,
                        'O3_beta_mean':s,'starter_share_draws':summary(share)}
                    vals['completions'] = rng.binomial(vals['pass attempts'],self.conversion(r,'completions','pass_attempts',rng))
                    vals['passing yards'] = self.yards(r,'passing_yards','completions',vals['completions'],rng)
                except GateError as exc:
                    diagnostics[pid]['missing_qb_conversion'] = str(exc)
            if 'targets' in vals:
                try:
                    vals['receptions'] = rng.binomial(vals['targets'],self.conversion(r,'receptions','targets',rng))
                    vals['receiving yards'] = self.yards(r,'receiving_yards','receptions',vals['receptions'],rng)
                except GateError as exc:
                    diagnostics[pid]['missing_receiving_conversion'] = str(exc)
            if 'carries' in vals:
                try:
                    vals['rushing yards'] = self.yards(r,'rushing_yards','carries',vals['carries'],rng)
                except GateError as exc:
                    diagnostics[pid]['missing_rushing_conversion'] = str(exc)
                if r['position']=='QB':
                    vals['qb rushing attempts'] = vals['carries']
                    if 'rushing yards' in vals: vals['qb rushing yards'] = vals['rushing yards']
            diagnostics[pid]['tracking_variant'] = ('targets_per_attempt_with_observed_route_cap'
                if pid in route_caps else 'targets_per_attempt_no_route_tracking')
        return results, active, diagnostics, errors

    def defender(self, e, r, opponent):
        rng = np.random.default_rng(seed(VERSION,e['game_id'],r['player_id'],'O4'))
        require(r.get('participation_probability') is not None,'missing_participation_probability')
        require(r['status']!='out' or r['participation_probability']==0,'out_player_positive_participation')
        hist = self.history(r)
        require(hist and (stamp(e['event_start'])-stamp(hist[-1]['end_at'])).days <= 28,'stale_defensive_role')
        played = [h for h in hist if h['state']=='played']
        par = defensive_parameters(played, self.teams, self.players, r['position'])
        share = rng.beta(par['snap_alpha'],par['snap_beta'],self.n)
        active = rng.random(self.n)<r['participation_probability']
        onfield = rng.binomial(opponent['plays'],share)*active
        rate = rng.gamma(par['rate_alpha'],1/par['rate_beta'],self.n)
        combined = rng.poisson(onfield*rate)
        return {'tackles + assists':combined},active,{
            'defensive_snaps':summary(onfield),'onfield_share':summary(share),
            'history_games':len(hist),'parameters':par,
            'variant':'combined credited count per defensive snap; gamma-poisson rate uncertainty',
            'team_tackle_budget':'no cap or mutually exclusive cross-player allocation',
            'weather_status':'WEATHER_EFFECT_NOT_ESTIMATED'}

    def run(self):
        team_outputs, workload, rows = [], [], []
        for e in self.p['events']:
            try:
                env = self.environment(e)
            except GateError as exc:
                for c in self.p['contracts']:
                    if c['game_id']==e['game_id']:
                        for model in MODELS:
                            rows.append({'contract':c,'model':model,'status':'abstain','reason':str(exc)})
                continue
            values, masks, diag, failures = {}, {}, {}, {}
            roster = [r for r in self.p['roster'] if r['game_id']==e['game_id']]
            for team,opp in ((e['home'],e['away']),(e['away'],e['home'])):
                team_outputs.append({'game_id':e['game_id'],'team':team,'opponent':opp,
                    'model':MODELS[0], 'opportunities':{k:summary(v) if v is not None else None for k,v in env[team].items()},
                    'distributions':{k:distribution(v) if v is not None else None for k,v in env[team].items()},
                    'expected_script':'zero-mean latent script; no timestamped spread/total used',
                    'variant':'V3-inspired lower-information contextual decomposition; not original V3 ridge/blend',
                    'weather':'not used; no source-verified weather dependency',
                    'conservation_max_error':int(np.max(np.abs(env[team]['plays']-env[team]['pass_attempts']-
                                                             env[team]['rush_attempts']-env[team]['sacks'])))})
                for mixture in (False,True):
                    v,a,d,f = self.offense(e,team,env[team],mixture)
                    tag = 'mixture' if mixture else 'stable'
                    for pid in v:
                        values[tag,pid], masks[tag,pid] = v[pid], a.get(pid)
                        diag[tag,pid] = d.get(pid,{})
                        if pid in f: failures[tag,pid] = f[pid]
                        workload.append({'game_id':e['game_id'],'player_id':pid,'team':team,'variant':tag,
                            'diagnostics':d.get(pid,{}),'abstention':f.get(pid),
                            'workload_unconditional':{k:summary(x) for k,x in v[pid].items()},
                            'team_allocation':{k:x for k,x in d.items() if k.startswith('team_')}})
            for r in roster:
                if r['position'] not in DEFENSE: continue
                tag,pid = 'defense',r['player_id']
                opp = e['away'] if r['team']==e['home'] else e['home']
                try:
                    v,a,d = self.defender(e,r,env[opp])
                    values[tag,pid],masks[tag,pid],diag[tag,pid] = v,a,d
                    workload.append({'game_id':e['game_id'],'player_id':pid,'team':r['team'],
                        'variant':tag,'diagnostics':d,'workload_unconditional':{k:summary(x) for k,x in v.items()}})
                except GateError as exc:
                    failures[tag,pid] = str(exc)
            for c in self.p['contracts']:
                if c['game_id'] != e['game_id']: continue
                r = next((r for r in roster if r['player_id']==c['player_id'] and r['team']==c['team']),None)
                for i,model in enumerate(MODELS):
                    row = {'contract':c,'model':model,'status':'abstain'}
                    try:
                        require(i!=0,'O1_team_distribution_only')
                        require(r is not None,'contract_roster_identity_mismatch')
                        pos,pid,metric = r['position'],r['player_id'],c['stat']
                        if i==1: require(pos in {'WR','RB','TE'},'outside_O2_scope')
                        if i==2: require(pos=='QB' and metric in QB_MARKETS,'outside_O3_scope')
                        if i==3: require(pos in DEFENSE,'outside_O4_scope')
                        if i==4: require(pos in {'WR','RB','TE','QB'},'outside_O5_offensive_scope')
                        if i==4 and pos=='QB':
                            require(metric in {'qb rushing attempts','qb rushing yards'},'outside_O5_role_sensitive_scope')
                        if pos=='QB':
                            require(r.get('expected_starter') is True and
                                    (r.get('starter_probability') or 0)>0,'qb_not_identified_pregame_starter')
                        tag = 'defense' if i==3 else 'mixture' if i==4 else 'stable'
                        require((tag,pid) not in failures,failures.get((tag,pid),'player_unavailable'))
                        v = values.get((tag,pid),{})
                        require(metric in v,'missing_market_dependency')
                        mask = masks[tag,pid]
                        require(mask is not None and mask.sum()>0,'no_simulated_participation')
                        cond = oup(v[metric][mask],c['line'])
                        row.update(status='forecast', probabilities_conditional=cond,
                            conditioning='identified_starter_and_participation' if pos=='QB' else 'participation',
                            unconditional_stat_probabilities=oup(v[metric],c['line']),
                            dnp_probability=1-float(mask.mean()),
                            dnp_settlement='void; unconditional stat zero is not a settled Under',
                            workload_conditional=summary(v[metric][mask]),
                            predictive_distribution_conditional=distribution(v[metric][mask]),
                            diagnostics=diag.get((tag,pid),{}),
                            max_mc_standard_error=math.sqrt(.25/int(mask.sum())),
                            comparison_over_differences={name:cond['over']-c[name]['over'] if c.get(name) is not None else None
                                                         for name in ('frozen_60_40','market')})
                    except GateError as exc:
                        row['reason'] = str(exc)
                    rows.append(row)
        counts = Counter((r['model'],r['contract']['stat'],r['status'],r.get('reason','')) for r in rows)
        stability = []
        matched = {(r['contract']['contract_id'],r['model']):r for r in rows if r['status']=='forecast'}
        for c in self.p['contracts']:
            alt = matched.get((c['contract_id'],MODELS[4]))
            base = matched.get((c['contract_id'],MODELS[1])) or matched.get((c['contract_id'],MODELS[2]))
            if alt is not None and base is not None:
                a,b = alt['probabilities_conditional']['over'],base['probabilities_conditional']['over']
                stability.append({'contract_id':c['contract_id'],'stable_model':base['model'],
                    'mixture_minus_stable_p_over':a-b,
                    'mixture_minus_stable_mean':alt['workload_conditional']['mean']-base['workload_conditional']['mean'],
                    'direction_disagrees':(a>=.5)!=(b>=.5),
                    'interpretation':'sensitivity to frozen assumptions, not evidence of a known role change'})
        return {'schema':VERSION,'day':DAY,'status':'SHADOW_ONLY_UNCERTIFIED',
                'manifest_sha256':self.p['manifest_sha256'],'forecast_at':self.p['forecast_at'],
                'training_cutoff_at':self.p['manifest']['training_cutoff_at'],
                'input_freeze_at':self.p['manifest']['input_freeze_at'],'draws':self.n,
                'original_contracts_attempted':len(self.p['contracts']),
                'rows':rows,'team_opportunities':team_outputs,'player_workloads':workload,
                'role_stability_comparison':stability,
                'counts_by_market_model_status':[{'model':m,'market':s,'status':st,'reason':reason,'n':n}
                                               for (m,s,st,reason),n in sorted(counts.items())],
                'limitations':['O1 lower-information adaptation, not a rerun of frozen V3',
                    'O2 routes/TPRR unavailable in this variant; targets per team pass attempt',
                    'O3 signed yardage conditional on completions; no depth or designed-run/scramble split',
                    'O4 defender marginals; no joint tackle or personnel-package conservation claim',
                    'O5 frozen sensitivity assumptions; no claim that role change is known',
                    'Passing and receiving conversion are separate marginal models; no joint completion/yardage accounting claim',
                    'No prospective accuracy result before independently sourced settlement'],
                'release_authority':'NONE; no production, Tiers, edge claim or scheduling'}

def freeze_output(report, root):
    """Content-addressed immutable run directory; exclusive create, no overwrite."""
    report = {**report,'code_files_sha256':{p.name:sha(p.read_bytes()) for p in
               sorted(Path(__file__).parent.glob('*.py')) if not p.name.startswith('test_')}}
    data = canonical(report)
    destination = Path(root)/sha(data)
    destination.mkdir(parents=True,exist_ok=False)
    with (destination/'report.json').open('xb') as f: f.write(data)
    receipt = {'schema':VERSION,'report_sha256':sha(data),'report_bytes':len(data),
               'status':report['status'],'created_at':datetime.now(timezone.utc).isoformat()}
    with (destination/'receipt.json').open('xb') as f: f.write(canonical(receipt))
    return {'directory':str(destination),**receipt}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--draws',type=int,default=8192)
    parser.add_argument('--output',type=Path,default=Path('reports/nfl_20261115_prospective/opportunity_models'))
    args=parser.parse_args(argv)
    now=datetime.now(timezone.utc).isoformat()
    if args.manifest is None:
        report={'schema':VERSION,'day':DAY,'forecast_at':now,'status':'BLOCKED_BY_DATA',
                'models':list(MODELS),'reason':'WS1_immutable_pregame_manifest_not_supplied',
                'original_contracts_attempted':None,'forecasts':0,
                'contract_universe':'unknown; not an empty or zero-reject universe',
                'dependencies':['WS1 manifest and pinned hash','original exact contract/quote bytes',
                    'prior team/player history with source clocks','pregame roster and identified starting QBs'],
                'no_collector_run':True,'no_baseline_modified':True}
    else:
        require(args.manifest_sha256 is not None,'missing_manifest_hash_pin')
        try:
            packet=load_packet(args.manifest,args.manifest_sha256,now)
            report=OpportunityModel(packet,args.draws).run()
        except (GateError, OSError, json.JSONDecodeError) as exc:
            report={'schema':VERSION,'day':DAY,'forecast_at':now,'status':'REJECTED_INPUT',
                    'models':list(MODELS),'manifest_sha256_pin':args.manifest_sha256,
                    'reason':str(exc) if isinstance(exc,GateError) else type(exc).__name__,
                    'original_contracts_attempted':None,'forecasts':0,'no_collector_run':True}
    print(json.dumps(freeze_output(report,args.output),sort_keys=True))

if __name__=='__main__':
    main()
