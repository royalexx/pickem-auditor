"""P0 source exclusions, explicit unfitted P1/P2 and gated existing-J2 handoff."""
import copy
import math
from datetime import datetime,timezone
from v2.nba_joint import simulate
from v2.nba_joint.common import sha,instant
from v2.nba_opportunity import causal_features

MODEL_HASH='e424c7f98bba50315dfde81a60978855d6ceb8c72aba8ad0af310eb31283326f'
VALIDATED_REAL_PARTICIPATION_METHODS=()


def participation_layer(roster,availability,*,game_abbreviations):
    freeze=instant(roster['input_freeze_at']);game=roster['game'];day=instant(game['event_start_at']).astimezone(__import__('zoneinfo').ZoneInfo('America/Toronto')).date().isoformat()
    rows=[]
    for p in roster['players']:
        evidence=[r for r in availability.get('resolved',[]) if r['player_id']==p['player_id'] and r['team_id']==p['team_id']]
        accepted=[];rejected=[]
        for r in evidence:
            reasons=[]
            if r['evidence_kind']!='original_source_identity_bridge':reasons.append('NOT_ORIGINAL_EVIDENCE')
            if instant(r['retrieved_at'])>freeze or instant(r['published_at_claim'])>freeze:reasons.append('AVAILABILITY_AFTER_FREEZE')
            if not instant(r['identity_evidence']['valid_from'])<=freeze<instant(r['identity_evidence']['valid_until']):reasons.append('CROSSWALK_NOT_ASOF')
            if datetime.strptime(r['date'],'%m/%d/%Y').date().isoformat()!=day:reasons.append('WRONG_GAME_DAY')
            if set(r['matchup'].split('@'))!=set(game_abbreviations):reasons.append('WRONG_GAME_TEAMS')
            if r['time'].split()[0]!=instant(game['event_start_at']).astimezone(__import__('zoneinfo').ZoneInfo('America/Toronto')).strftime('%I:%M'):reasons.append('WRONG_GAME_TIME')
            if reasons:rejected.append({'row':r,'reasons':reasons})
            else:accepted.append(r)
        statuses={r['status'] for r in accepted};conflict=len(statuses)>1
        inactive=not conflict and statuses=={'Out'}
        rows.append(dict(player_id=p['player_id'],team_id=p['team_id'],game_id=game['game_id'],eligibility=p.get('eligibility'),
            availability='conflicting' if conflict else next(iter(statuses)) if statuses else 'unknown',announced_starting_role=None,
            P0_probability=0. if inactive else None,P0_method='official_out_source_exclusion' if inactive else None,
            probability_semantics='deterministic exclusion from current original report, not a calibrated positive participation estimator' if inactive else 'unknown',
            P1_probability=None,P2_probability=None,uncertainty='no fitted calibrated estimator',
            accepted_availability=accepted,rejected_availability=rejected,
            abstention_reasons=['LEGAL_GAME_ELIGIBILITY_UNAVAILABLE','P1_P2_TRAINING_UNIVERSE_UNAVAILABLE']+(['PARTICIPATION_UNKNOWN'] if not inactive else [])+(['CONFLICTING_AVAILABILITY'] if conflict else [])))
    return dict(schema='NBAParticipationLayer/1.0.0',game=game,input_freeze_at=roster['input_freeze_at'],rows=rows,
        methods={'P0':'deterministic verified-status exclusion; other players unknown','P1':'UNFITTED_NO_GENUINE_ELIGIBLE_TRAINING_UNIVERSE','P2':'UNFITTED_NO_GENUINE_ELIGIBLE_TRAINING_UNIVERSE'},
        complete_game_day_universe=roster['coverage']['complete_game_day_universe'],
        source_exclusions=sum(r['P0_probability']==0 for r in rows),positive_validated_probabilities=0,
        status='BLOCKED-BY-DATA',market_semantics='no participation => separate DNP/void state; never silently Under or push')


def require_participation_ready(layer):
    if not layer['complete_game_day_universe']:raise ValueError('COMPLETE_GAME_DAY_UNIVERSE_UNAVAILABLE')
    for r in layer['rows']:
        if r['eligibility'] is None:raise ValueError('LEGAL_ELIGIBILITY_UNKNOWN')
        if r['eligibility'] and r['P0_probability'] is None:raise ValueError('PARTICIPATION_UNKNOWN')
    if not VALIDATED_REAL_PARTICIPATION_METHODS:raise ValueError('VALIDATED_PARTICIPATION_METHOD_UNAVAILABLE')
    return layer


def participation_aware_j2(game,model,*,layer,n=128,seed=20261115,fixture=False):
    if sha(model)!=MODEL_HASH and not fixture:raise ValueError('FROZEN_MODEL_CHANGED')
    if fixture:
        if game['mode']!='synthetic' or layer.get('evidence_kind')!='synthetic_fixture':raise ValueError('FIXTURE_NOT_REAL_SOURCE')
    else:
        require_participation_ready(layer)
        if game['mode']!='prospective':raise ValueError('REAL_FORECAST_REQUIRES_PROSPECTIVE_WS1')
        if datetime.now(timezone.utc)>=instant(game['event_start_at']):raise ValueError('PREGAME_WINDOW_CLOSED')
    if layer['game_id']!=game['game_id']:raise ValueError('PARTICIPATION_GAME_IDENTITY')
    rows=layer['players'];mapping={r['player_id']:r for r in rows}
    if len(mapping)!=len(rows) or set(mapping)!={p['player_id'] for p in game['players']}:raise ValueError('INCOMPLETE_PARTICIPATION_UNIVERSE')
    g=copy.deepcopy(game);g['conditional_on_roster']=False
    for p in g['players']:
        r=mapping[p['player_id']]
        if r['team_id']!=p['team_id'] or r['eligible'] is None:raise ValueError('PARTICIPATION_PLAYER_IDENTITY_OR_ELIGIBILITY')
        probability=r['probability']
        if probability is None or isinstance(probability,bool) or not math.isfinite(probability) or not 0<=probability<=1:raise ValueError('PARTICIPATION_UNKNOWN_OR_INVALID')
        if not r['eligible'] and probability!=0:raise ValueError('INACTIVE_PARTICIPATION_CONFLICT')
        if not p.get('minute_features'):raise ValueError('M0_LAW_UNAVAILABLE')
        p['eligible']=r['eligible'];p['participation_probability']=probability
    # Existing J2 aborts on ANY underfilled/infeasible draw. It does not redraw
    # participant sets until feasible (which would condition the probability law).
    output=simulate(g,model,n=n,seed=seed)
    output['participation_research']={'evidence_kind':'synthetic_fixture' if fixture else 'source_qualified_research','model_unchanged':True,
        'conditional_minutes':'M0 given entry','unconditional_counts':'structural zero for no entry; DNP settlement handled separately'}
    return output
