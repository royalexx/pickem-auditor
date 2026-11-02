"""Convex A/B probability blending; weights need chronological holdout evidence."""
import json
import hashlib
import math
import random
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
VERSION = 'history-v5+scouting-v7'
SCORE_RULE = 'joint_win_push_loss_log_loss_v1'
TRAINING_UNIT = 'unique_player_game_stat_v2'


def valid_evidence(ev, baseline_key, improved_key, as_of):
    """Validate the complete certificate before trusting its comparisons."""
    if not isinstance(ev,dict):return False
    try:
        for key,floor in (('train_n',300),('holdout_n',100),('holdout_dates',20)):
            value=ev[key]
            if isinstance(value,bool) or not isinstance(value,int) or value<floor:return False
        if ev['holdout_dates']>ev['holdout_n']:return False
        dates=[date.fromisoformat(ev[key]) for key in ('train_end','holdout_start','holdout_end')]
        if not dates[0]<dates[1]<=dates[2]<as_of:return False
        for key in (baseline_key,improved_key,'improvement_ci_low'):
            value=ev[key]
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:return False
        return ev.get('score_rule')==SCORE_RULE and ev[improved_key]<ev[baseline_key] and ev['improvement_ci_low']>0
    except (KeyError,TypeError,ValueError):return False


def config_path(root, scope):
    return Path(root) / "config" / "probability_blend" / (re.sub(r"[^A-Za-z0-9]+", "_", scope).strip("_") + ".json")


def combine(a, b, config_path=None, *, scope="global", as_of=None):
    out = dict(q_win=a['q_win_robust'], q_push=a['q_push_robust'],
               weights={'a': 1.0, 'b': 0.0}, validated=False,
               reason='no_validated_blend', version=VERSION)
    if b.get('abstain') or not b.get('reliable') or a.get('sample_block') or not a.get('observation_ids_verified'):
        out['reason'] = 'unreliable_engine'
        return out
    try:
        config_text = Path(config_path).read_text()
        cfg = json.loads(config_text)
        if not isinstance(cfg,dict):return out
        w = cfg['weight_a']
        ev = cfg['validation']
        if not valid_evidence(ev,'a_log_loss','blend_log_loss',as_of or date.today()):return out
        if (cfg.get('scope') != scope or cfg['engine_version'] != VERSION or
                cfg.get('training_unit') != TRAINING_UNIT or
                cfg.get('underpowered') is not False
                or ev.get('score_rule') != SCORE_RULE
                or isinstance(w, bool) or not isinstance(w, (int, float)) or not 0 < w < 1
                or ev['train_n'] < 300 or ev['holdout_n'] < 100
                or not ev['train_end'] < ev['holdout_start'] <= ev['holdout_end']
                or not ev['blend_log_loss'] < ev['a_log_loss']
                or ev.get('holdout_dates', 0) < 20
                or not math.isfinite(ev.get('improvement_ci_low', 0))
                or ev.get('improvement_ci_low', 0) <= 0
                or date.fromisoformat(ev['holdout_end']) >= (as_of or date.today())
                or not all(math.isfinite(ev[k]) for k in ('blend_log_loss', 'a_log_loss'))):
            return out
    except (OSError, TypeError, ValueError, KeyError):
        return out
    out.update(q_win=w*a['q_win_robust']+(1-w)*b['q_win_b'],
               q_push=w*a['q_push_robust']+(1-w)*b['q_push_b'],
               weights={'a': w, 'b': 1-w}, validated=True,
               reason='chronological_holdout_validated',
               config_version=hashlib.sha256(config_text.encode()).hexdigest()[:16])
    return out


def preview_70_30(a, b):
    """Uncalibrated A/B diagnostic, NEVER a deployed ranking probability.

    Print this only if both engines have verified evidence. Its presence must
    never set validated=True or bypass the chronological holdout requirement.
    """
    if (not isinstance(a, dict) or not isinstance(b, dict)
            or not a.get('observation_ids_verified') or a.get('sample_block')
            or not b.get('reliable') or b.get('abstain')
            or b.get('baseline_origin') != 'collector_observations'):
        return None
    try:
        aw, ap, bw, bp = (a['q_win_robust'], a['q_push_robust'],
                          b['q_win_b'], b['q_push_b'])
        if any(isinstance(p,bool) or not isinstance(p,(int,float)) or
               not math.isfinite(p) for p in (aw,ap,bw,bp)):
            return None
        if any(p < 0 or p > 1 for p in (aw,ap,bw,bp)) or aw+ap>1 or bw+bp>1:
            return None
    except KeyError:
        return None
    return {'q_win':.7*aw+.3*bw, 'q_push':.7*ap+.3*bp,
            'weight_a':.7, 'weight_b':.3, 'validated':False,
            'publication_eligible':False, 'purpose':'diagnostic_only'}


def fit(rows):
    """Fit once on earlier settled forecasts, evaluate on untouched later dates.

    Input: id (one unique prop/event), date, a_win, a_push, b_win,
    b_push, outcome (win/loss/push). Fit and validate the same unconditional
    three-outcome distribution that is deployed, including push calibration.
    """
    unique = {}
    scopes = {r.get('scope') for r in rows}
    if len(scopes) != 1 or None in scopes:
        raise ValueError('fit one explicit sport/stat scope at a time')
    for r in rows:
        date.fromisoformat(r['date'])
        if r['id'] in unique:
            raise ValueError('duplicate prop/event id')
        if r['outcome'] not in ('win', 'loss', 'push'):
            raise ValueError('unsettled outcome')
        for prefix in ('a', 'b'):
            win, push = r[prefix+'_win'], r[prefix+'_push']
            if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in (win, push)) or not (0 <= win <= 1 and 0 <= push < 1 and win+push <= 1):
                raise ValueError('invalid probability mass')
        unique[r['id']] = r
    data = sorted(unique.values(), key=lambda r:r['date'])
    if len(data) < 400:
        raise ValueError('need 300 training and 100 holdout outcomes')
    cutoff = data[max(300, int(len(data)*.75))]['date']
    train = [r for r in data if r['date'] < cutoff]
    holdout = [r for r in data if r['date'] >= cutoff]
    if len(train) < 300 or len(holdout) < 100:
        raise ValueError('insufficient distinct chronological dates')
    def loss(group, w):
        total = 0
        for r in group:
            win=w*r['a_win']+(1-w)*r['b_win']
            push=w*r['a_push']+(1-w)*r['b_push']
            p={'win':win,'push':push,'loss':1-win-push}[r['outcome']]
            p = min(1-1e-12, max(1e-12, p))
            total -= math.log(p)
        return total/len(group)
    w = min((i/100 for i in range(1,100)), key=lambda w:loss(train,w))
    # Date-cluster bootstrap preserves within-day dependence. A validation loss
    # improvement alone is insufficient: its 95% lower bound must be positive.
    groups = {}
    for r in holdout:
        groups.setdefault(r['date'], []).append(r)
    rng = random.Random(1729)
    days = sorted(groups)
    improvements = []
    for _ in range(1000):
        sample = [r for day in rng.choices(days, k=len(days)) for r in groups[day]]
        improvements.append(loss(sample, 1)-loss(sample, w))
    lower = sorted(improvements)[24] if len(days) >= 20 else 0.0
    return dict(scope=next(iter(scopes)), engine_version=VERSION,
                training_unit=TRAINING_UNIT, weight_a=w, underpowered=False,
                validation=dict(score_rule=SCORE_RULE,train_n=len(train), holdout_n=len(holdout),
                                train_unique_events=len(set(r.get('event_key',r['id']) for r in train)),
                                holdout_unique_events=len(set(r.get('event_key',r['id']) for r in holdout)),
                                train_unique_player_games=len(set(r.get('player_game_id',r['id']) for r in train)),
                                holdout_unique_player_games=len(set(r.get('player_game_id',r['id']) for r in holdout)),
                                train_pushes=sum(r['outcome']=='push' for r in train),
                                holdout_pushes=sum(r['outcome']=='push' for r in holdout),
                                train_end=train[-1]['date'], holdout_start=holdout[0]['date'],
                                holdout_end=holdout[-1]['date'],
                                blend_log_loss=loss(holdout,w), a_log_loss=loss(holdout,1),
                                holdout_dates=len(days), improvement_ci_low=lower))


def canonical_player_game(row):
    """Stable game/player/stat training unit; no name/date inference."""
    inputs=row.get("inputs") if isinstance(row.get("inputs"),dict) else {}
    namespace=str(row.get("event_id_namespace") or inputs.get("event_id_namespace") or "").strip()
    event_id=str(row.get("event_id") or inputs.get("event_id") or "").strip()
    player_id=str(row.get("player_id") or inputs.get("player_id") or "").strip()
    if not namespace or not event_id or not player_id:
        return None
    return json.dumps([row.get("sport"),namespace,event_id,player_id,row.get("stat")],
                      separators=(",",":"),ensure_ascii=False)


def from_snapshots(rows, scope):
    """Only forecasts from current engines qualify; keep earliest per prop."""
    selected = {}
    def stamp(row):
        try:
            value=datetime.fromisoformat(row['forecast_at'].replace('Z','+00:00'))
            return value.timestamp() if value.tzinfo else math.inf
        except (KeyError,ValueError,TypeError,AttributeError):return math.inf
    for row in sorted(rows, key=stamp):
        a, b = row.get('engine_a') or {}, row.get('engine_b') or {}
        if (a.get('version') != 'history-v5' or b.get('version') != 'scouting-v7'
                or b.get('baseline_origin')!='collector_observations'
                or (row.get('shared_context') or {}).get('applied')
                or not a.get('reliable') or not b.get('reliable') or b.get('abstain')
                or not a.get('observation_ids_verified')
                or row.get('outcome') not in ('win', 'loss', 'push')
                or f"{row.get('sport')}|{row.get('stat')}" != scope):
            continue
        # A game-date label alone cannot prove a forecast preceded the game.
        try:
            forecast=datetime.fromisoformat(row['forecast_at'].replace('Z','+00:00'))
            start=datetime.fromisoformat(row['event_start'].replace('Z','+00:00'))
            if forecast.tzinfo is None or start.tzinfo is None or forecast>=start:
                continue
            if start.astimezone(ZoneInfo('America/Toronto')).date().isoformat()!=row.get('game_date'):continue
        except (KeyError,ValueError,TypeError,AttributeError):
            continue
        # A display name and calendar date do not identify a unique game.
        # Require collector-owned event/player IDs (same-name players and
        # doubleheaders exist) and a settlement timestamp after game start.
        ident=canonical_player_game(row)
        if ident is None:
            continue
        try:
            settled=datetime.fromisoformat(str(row["settled_at"]).replace('Z','+00:00'))
            if settled.tzinfo is None or settled<=start:continue
        except (KeyError,ValueError,TypeError,AttributeError):continue
        # One player-game-stat contributes at most one supervised training
        # observation. Extra sides/lines cannot inflate confidence/ESS.
        player_game=ident
        parts=json.loads(ident)
        namespace,event_id=parts[1],parts[2]
        if ident in selected:
            if selected[ident]['outcome'] != row['outcome']:
                # Different lines can legitimately have different outcomes;
                # they cannot be treated as independent observations here.
                # The earliest pregame side/line remains the frozen selection.
                continue
            continue
        selected[ident]=dict(id=ident, scope=scope, date=row['game_date'],
            a_win=a['q_win_robust'], a_push=a['q_push_robust'],
            b_win=b['q_win'], b_push=b['q_push'], outcome=row['outcome'],
            forecast_at=row['forecast_at'], event_key=namespace+":"+event_id,
            player_game_id=player_game, selected_side=row.get('side'),
            selected_line=row.get('reference_line'))
    return list(selected.values())


def fit_scopes(rows, root, *, as_of=None):
    """Fit candidates without silently registering or deleting live certificates.

    Existing valid deployments are retained. New candidates are written under
    reports/ for explicit offline review; activation must be a separate
    controlled operation after provenance and prospective policy validation.
    """
    scopes={f"{r.get('sport')}|{r.get('stat')}" for r in rows if r.get('sport') and r.get('stat')}
    directory=Path(root)/'config'/'probability_blend'
    # Existing scopes must be re-evaluated even if their qualifying rows vanish.
    if directory.exists():
        for path in directory.glob('*.json'):
            try:scopes.add(json.loads(path.read_text())['scope'])
            except (ValueError,KeyError):
                # Unknown/invalid files are never promoted by combine().
                # Retain bytes for investigation and rollback, not auto-delete.
                continue
    results={}
    for scope in sorted(scopes):
        path=config_path(root,scope)
        # Keep an evidence-backed deployment stable while its prospective context
        # sample accumulates. Refitting every weekly run changes the fingerprint
        # even when the learned weight barely moves, invalidating that sample.
        deployed=combine({'q_win_robust':.5,'q_push_robust':0,'sample_block':False,'observation_ids_verified':True},
                         {'q_win_b':.5,'q_push_b':0,'reliable':True,'abstain':False},path,scope=scope,as_of=as_of)
        if deployed['validated']:
            results[scope]={'status':'validated','deployment_retained':True,'config_version':deployed['config_version']}
            continue
        try:
            cfg=fit(from_snapshots(rows,scope))
            ev=cfg['validation']
            eligible=(ev['holdout_dates']>=20 and ev['improvement_ci_low']>0 and
                      ev['blend_log_loss']<ev['a_log_loss'] and
                      date.fromisoformat(ev['holdout_end'])<(as_of or date.today()))
            if eligible:
                proposal=(Path(root)/'reports'/'calibration_candidates'/
                          'probability_blend'/path.name)
                proposal.parent.mkdir(parents=True,exist_ok=True)
                temporary=proposal.with_suffix('.tmp')
                temporary.write_text(json.dumps(cfg,sort_keys=True,indent=2)+'\n')
                temporary.replace(proposal)
                results[scope]={'status':'candidate_pending_registration',
                                'path':str(proposal),'validation':ev,
                                'production_unchanged':True}
                continue
            reason='holdout_improvement_not_established'
        except (ValueError,KeyError,TypeError) as exc:
            reason=str(exc)
        results[scope]={'status':'underpowered_or_unvalidated','reason':reason,
                        'production_unchanged':True}
    return results


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='settled forecast or snapshot JSONL')
    parser.add_argument('--snapshots', action='store_true')
    parser.add_argument('--scope', help='SPORT|stat; required with --snapshots')
    parser.add_argument('--out', required=True)
    args=parser.parse_args()
    rows=[json.loads(line) for line in Path(args.input).read_text().splitlines() if line.strip()]
    if args.snapshots:
        if not args.scope:
            parser.error('--snapshots requires --scope')
        rows=from_snapshots(rows, args.scope)
    cfg=fit(rows)
    path=Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2)+'\n')
