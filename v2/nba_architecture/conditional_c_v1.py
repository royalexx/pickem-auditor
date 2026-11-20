"""Bounded native outcome transport and proper count/empirical score mechanics.

The frozen twenty-game source root is training evidence, not historical PIT
forecast validation. The issued future target has no admitted outcome yet.
"""
from collections import Counter
from pathlib import Path
import math
import re
from fractions import Fraction
from .p1_subset_handoff_v1 import canonical,digest
from .subset_contract_v1 import strict_json
from .subset_p3_v1 import require
from .prospective_s_sources_v1 import SPEC_SHA,next_data,official_vector
from .pbp_evidence_v1 import read_population
from .full_predictive_replay_v2 import read_issued_forecast
from .full_played_s_v1 import FullPlayedLaw
from v2.nba_opportunity import utc

PROFILE_SHA='5eab873f4cc744e29d3d4bcf483bb5c0726398146b0ee90b15be37814b59c9a8'
POPULATION_SHA='1d05830c44ee07fd89bbe7dcade95d70651a0cfae824e8f2edaadf30d4b20584'
PBP_READER_SHA='2fdb7ca21017fe567115cc4316f6b8109d52af9b908ffb0a6b177b585874c2f1'


def read_native_outcomes(*,raw_dir,population_path,original_raw_dir,spec_path,profile_path):
    """Admission is exact-source, exact-reader, compiled capability specific.

    Caller labels/flags/reviewer names cannot extend this frozen population.
    Counts are reported even for DNP, but never interpreted as played outcomes.
    """
    require(digest(Path(profile_path).read_bytes())==PROFILE_SHA,'C_UNREVIEWED_EVIDENCE_PROFILE')
    require(digest(Path(population_path).read_bytes())==POPULATION_SHA,'C_UNADMITTED_POPULATION')
    require(digest(Path(__file__).with_name('pbp_evidence_v1.py').read_bytes())==PBP_READER_SHA,'C_UNREVIEWED_NATIVE_READER')
    spec_raw=Path(spec_path).read_bytes();require(digest(spec_raw)==SPEC_SHA,'C_UNREVIEWED_ORIGINAL_BOX_MANIFEST')
    spec=strict_json(spec_raw);pop=strict_json(Path(population_path).read_bytes());root=Path(original_raw_dir)
    for name in pop['sources']:
        box='nba-box-'+name[4:];expected=spec['sources'][box]
        body=(root/box/'body.raw').read_bytes();rr=(root/box/'receipt.json').read_bytes();r=strict_json(rr)
        require(digest(body)==expected['body_sha256']==r['raw_sha256'] and digest(rr)==expected['receipt_sha256'],
            'C_ORIGINAL_BOX_FROZEN_BYTES')
        require(r['url']==expected['url'] and r['status']==200 and len(body)==r['bytes'],'C_ORIGINAL_BOX_CAPTURE')
        require(utc(r['retrieval_started_at'])<=utc(r['retrieval_completed_at'])<=utc(r['ingested_at']), 'C_BOX_CAPTURE_CLOCK')
        require(all(r.get(k) is None for k in ('source_published_at','original_historical_available_at',
            'correction_history_complete','predecessor_sha256')),'C_UNSUPPORTED_BOX_CLAIM')
    facts=read_population(raw_dir,population_path,original_raw_dir)
    require(facts['game_denominator']==20 and facts['rejected_games']==0 and all(
        r['facts']['all_credited_event_counts_reconciled'] for r in facts['rows']),'C_NATIVE_COUNT_RECONCILIATION')
    rows=[];games=[]
    for entry in facts['rows']:
        gid=entry['game_id'];f=entry['facts'];name='pbp-'+gid
        game=next_data((Path(raw_dir)/name/'body.raw').read_bytes())['game']
        receipt=strict_json((Path(raw_dir)/name/'receipt.json').read_bytes())
        prior_receipt=strict_json((root/('nba-box-'+gid)/'receipt.json').read_bytes())
        seen=set()
        for side in ('homeTeam','awayTeam'):
            team=game[side];tid=str(team['teamId'])
            for inactive,players in ((False,team['players']),(True,team.get('inactives',[]))):
                for player in players:
                    pid=str(player['personId']);require(pid not in seen,'C_DUPLICATE_NATIVE_ID');seen.add(pid)
                    comment=player.get('comment') or '';minutes=None if inactive else player['statistics']['minutes']
                    counts=None if inactive else {key:official_vector(player['statistics'])[key] for key in f['reconciled_event_credit_fields']}
                    reported_seconds=None
                    if inactive:state='SOURCE_LISTED_INACTIVE'
                    elif comment.startswith('DNP'):state='DNP_EXPLICIT'
                    elif minutes:
                        require(re.fullmatch(r'\d+:\d{2}',minutes) is not None,'C_REPORTED_MINUTE_FORMAT')
                        m,s=map(int,minutes.split(':'));require(s<60,'C_REPORTED_SECOND_SUPPORT');reported_seconds=m*60+s
                        state='PLAYED_REPORTED_POSITIVE' if reported_seconds>0 else 'PLAYED_DISPLAY_ZERO_EXACT_EXPOSURE_UNKNOWN'
                    else:state='UNKNOWN_PARTICIPATION'
                    played=state in ('PLAYED_REPORTED_POSITIVE','PLAYED_DISPLAY_ZERO_EXACT_EXPOSURE_UNKNOWN')
                    rows.append(dict(native_game_id=gid,native_player_id=pid,native_team_id=tid,
                        name=player['firstName']+' '+player['familyName'],participation_state=state,
                        source_comment=comment,reported_minutes=minutes,reported_seconds=reported_seconds,
                        exact_true_minutes=None,true_clock_zero_confirmed=False,reported_counts=counts,
                        played_conditional_counts=counts if played else None,
                        source_body_sha256=f['raw_sha256'],original_box_body_sha256=f['box_raw_sha256'],
                        observation_at=receipt['retrieval_completed_at'],retrieval_started_at=receipt['retrieval_started_at'],
                        retrieval_completed_at=receipt['retrieval_completed_at'],ingested_at=receipt['ingested_at'],
                        original_box_observed_at=prior_receipt['retrieval_completed_at'],source_published_at=None,
                        official_end_at=None,outcome_released_at=None,predecessor_sha256=None,
                        correction_history_complete=None,source_history_scope='EXACT_TWO_CAPTURED_SNAPSHOTS_ONLY',
                        reported_final=True,complete_eligible_roster_claim=False))
        games.append(dict(native_game_id=gid,start=f['game_start_at'],reported_final=True,
            duration_minutes=48+5*(game['period']-4),overtime_periods=game['period']-4,
            official_wallclock_end_at=None,source_end_wallclock_text=f['reported_end_wallclock_text'],
            original_pregame_evidence=False,historical_new_model_PIT_eligible=False,
            reason='TRAINING_GAME_NO_SUPPLIED_PRE_EVENT_NEW_MODEL_OR_FORECAST'))
    result=dict(schema='bounded-native-C-outcomes/1',capability='EXACT20_NATIVE_IDENTITIES_REPORTED_FINAL_AND14_COUNTS',
        evidence_profile_sha256=PROFILE_SHA,population_sha256=POPULATION_SHA,source_facts_payload_sha256=facts['payload_sha256'],
        source_row_denominator=len(rows),rows=rows,games=games,state_denominators=dict(Counter(r['participation_state'] for r in rows)),
        historical_new_model_PIT_eligible=0,complete_eligible_roster_claim=False,source_admission_extensible_by_caller=False,
        official_publication_clock_known=False,correction_history_complete=None,release=False)
    return dict(result,payload_sha256=digest(canonical(result)))


def score_count(model,count):
    """Numerical mechanics only. Actual scoring additionally requires a verified
    forecast/outcome/clock/identity join. Unresolved tails remain NO_SCORE.
    """
    require(type(count) is int and count>=0,'C_COUNT_SUPPORT')
    law=FullPlayedLaw(**model)
    try:
        value=law.logpmf(count)
    except ValueError as exc:
        return dict(status='NO_SCORE_NUMERICAL_UNRESOLVED',reason=str(exc),count=count,score=None)
    if value['exact_structural_zero']:
        return dict(status='EXACT_ZERO_PROBABILITY',count=count,negative_log_score='POSITIVE_INFINITY',
            epsilon_clipped=False,diagnostics=value)
    return dict(status='NUMERICAL_SCORE_MECHANICS_ONLY',count=count,negative_log_score=-value['log_probability'],
        diagnostics=value,epsilon_clipped=False,count_support_truncated=False)


def threshold_probabilities(model,line):
    """Exact integer side definitions, full-law tail queries; no synthetic offer.
    The returned mass is a numerical estimate with its diagnostics, not proof
    of rare-tail relative precision. Caller supplies no availability authority.
    """
    require(type(line) in (str,int,float) and type(line) is not bool,'C_THRESHOLD_TYPE')
    threshold=Fraction(str(line));require(threshold>=0,'C_THRESHOLD_SUPPORT')
    law=FullPlayedLaw(**model);floor=threshold.numerator//threshold.denominator
    under=law.query([floor-1 if threshold.denominator==1 else floor],kind='cdf') if floor or threshold.denominator!=1 else None
    push=law.query([floor],kind='pmf') if threshold.denominator==1 else None
    over=law.query([floor],kind='sf')
    result=dict(under=under['probabilities'][0] if under else 0.,push=push['probabilities'][0] if push else 0.,over=over['probabilities'][0])
    require(abs(sum(result.values())-1)<1e-8,'C_COMPLEMENTARITY_UNRESOLVED')
    return dict(result,diagnostics=dict(under=under,push=push,over=over),line=str(threshold),
        offered_quote_available=False,rare_tail_relative_precision_accepted=False)


def empirical_scores(samples,outcome):
    require(isinstance(samples,list) and len(samples)>=2 and all(type(x) is int and x>=0 for x in samples), 'C_EMPIRICAL_SAMPLES')
    require(type(outcome) is int and outcome>=0,'C_COUNT_SUPPORT')
    n=len(samples);s=sorted(samples);first=math.fsum(abs(x-outcome) for x in s)/n
    pair_half=math.fsum((2*i-n+1)*x for i,x in enumerate(s))
    hits=sum(x==outcome for x in s)
    return dict(empirical_crps=first-pair_half/n**2,fair_ensemble_crps=first-pair_half/(n*(n-1)),
        empirical_negative_log_score=-math.log(hits/n) if hits else 'POSITIVE_INFINITY_EMPIRICAL_MEASURE',
        finite_empirical_support_is_not_population_support=True,population_zero_probability_claim=False,
        rare_event_log_score_resolved=False,n=n,hits=hits,epsilon_clipped=False)


def replay_and_pending(full_raw,parent_raw,*,full_inputs,outcome_inputs):
    transport=read_issued_forecast(full_raw,parent_raw,**full_inputs)
    outcomes=read_native_outcomes(**outcome_inputs)
    forecast=strict_json(full_raw);rows=[]
    # This v1 source root contains twenty training games only. There is no
    # admitted target-game crosswalk/outcome; a caller cannot substitute one.
    for r in forecast['law_payload']['rows']:
        rows.append(dict(game_id=forecast['cohort']['game_id'],player_id=r['player_id'],team_id=r['team_id'],
            statistic=r['statistic'],status='FORECAST_ABSTAINED' if r['model'] is None else 'OUTCOME_PENDING',
            outcome_status='PENDING_NO_ADMITTED_TARGET_FINAL_CAPTURE_OR_DATED_NATIVE_CROSSWALK',score=None,
            forecast_available=r['model'] is not None,participation_probability=None,legal_eligibility=None))
    return dict(schema='full-played-C-replay/1',forecast_transport=transport,attempt_denominator=len(rows),rows=rows,
        forecasted_rows=sum(r['forecast_available'] for r in rows),forecast_abstentions=sum(not r['forecast_available'] for r in rows),
        pending_outcomes=len(rows),scored_rows=0,historical_source_games=len(outcomes['games']),
        historical_PIT_eligible=0,new_forecast_issued=False,scoring_admitted=False,release=False,
        exact_missing_evidence=['TARGET_FINAL_NATIVE_BOX_AND_PBP_CAPTURE_AFTER_EVENT','DATED_TARGET_NATIVE_TO_FORECAST_IDENTITY_JOIN',
            'INDEPENDENT_TARGET_OUTCOME_ADMISSION','GENUINE_PRE_EVENT_NEW_MODEL_FORECASTS_ON_HISTORICAL_VALIDATION_COHORT'])
