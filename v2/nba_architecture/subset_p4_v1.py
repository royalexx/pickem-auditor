"""P2/P3 -> P4 conditional-law transport with explicit statistic abstentions.

Minute-law consumption is real. No S or J numerical producer is manufactured.
Original full-team P4 APIs and physical-budget contracts remain unchanged.
"""
import json
from pathlib import Path

from v2.nba_opportunity import MinuteLaw
from .p1_subset_handoff_v1 import canonical,digest
from .subset_contract_v1 import strict_json
from .subset_p2_v1 import read_p2,STATS
from .subset_p3_v1 import read_p3,require

VERSION='nba-subset-p4/1.0.0'


def read_native_minute_law(forecast):
    """Consume an actual native forecast, preserving given-played semantics."""
    require(isinstance(forecast,dict),'P4_NATIVE_FORECAST_SCHEMA')
    require(forecast.get('schema')=='NBAOpportunityForecast/1.0.0'
        and forecast.get('status')=='UNCERTIFIED/SHADOW','P4_NATIVE_FORECAST_VERSION')
    unsigned={k:v for k,v in forecast.items() if k!='forecast_id'}
    require(digest(json.dumps(unsigned,sort_keys=True).encode())==forecast.get('forecast_id'),'P4_NATIVE_FORECAST_ID')
    require(forecast.get('participation_probability') is None
        and forecast.get('active_roster_eligible') is None
        and forecast.get('scenario_ids')==[],'P4_UNSUPPORTED_PARTICIPATION_OR_TEAM_CLAIM')
    law=forecast['distribution']
    require(set(law)=={'mean','variance','ot_probability','ot_continuation','family'},'P4_NATIVE_LAW_FIELDS')
    require(all(type(law[k]) in (float,int) for k in ('mean','variance','ot_probability','ot_continuation')),'P4_NATIVE_LAW_NUMERIC')
    native=MinuteLaw(**law);summary=native.summary()
    require(all(canonical(forecast[k])==canonical(v) for k,v in summary.items()),'P4_NATIVE_LAW_MOMENT_OR_QUANTILE_MISMATCH')
    return dict(kind='CONDITIONAL_MINUTE_LAW_BOUNDARY_ONLY',
        native_forecast_id=forecast['forecast_id'],distribution=law,
        conditioning='conditional_on_participation',participation_probability=None,
        legal_eligibility=None,summary=summary,team_scenario=None)


def run_p4(p2_raw,p3_raw,*,source_raw,capture_dir,cohort,history_dir,model_path,forecast_at):
    p2=read_p2(p2_raw,source_raw=source_raw,capture_dir=capture_dir,cohort=cohort)
    p3=read_p3(p3_raw,source_raw=source_raw,capture_dir=capture_dir,cohort=cohort,
        history_dir=history_dir,model_path=model_path,forecast_at=forecast_at)
    s={(r['player_id'],r['team_id'],r['statistic']):r for r in p2['rows']}
    rows=[];native_laws=0
    for minutes in p3['rows']:
        law=read_native_minute_law(minutes['forecast']) if minutes['forecast'] else None
        native_laws+=law is not None
        for statistic in STATS:
            sr=s[(minutes['player_id'],minutes['team_id'],statistic)]
            if sr['reason']=='P1_SOURCE_ABSTENTION':reason='P1_SOURCE_ABSTENTION'
            elif law is None:reason='P3_CONDITIONAL_MINUTES_UNAVAILABLE:'+str(minutes['reason'])
            else:reason='P2_STATISTIC_KERNEL_UNAVAILABLE'
            rows.append(dict(game_id=cohort['game_id'],player_id=minutes['player_id'],
                team_id=minutes['team_id'],model=minutes['model'],statistic=statistic,
                status='ABSTAIN_STATISTIC_FORECAST',reason=reason,forecast=None,
                conditioning='conditional_on_participation',participation_probability=None,
                legal_eligibility=None,minute_handoff=law,
                minute_handoff_status='READ_NATIVE_CONDITIONAL_LAW' if law else 'UNAVAILABLE',
                statistic_kernel=None,joint_scenario=None,actual_joint_model_executed=False))
    payload=dict(schema=VERSION,stage='P4',profile='source_listed_subset',
        implementation_sha256=digest(Path(__file__).read_bytes()),
        p1_handoff_sha256=p2['p1_handoff_sha256'],p2_handoff_sha256=p2['payload_sha256'],p3_handoff_sha256=p3['payload_sha256'],
        candidate_denominator=p3['candidate_denominator'],attempt_denominator=len(rows),
        native_minute_laws_read=native_laws,minute_stat_references=sum(r['minute_handoff'] is not None for r in rows),
        statistic_forecasted_rows=0,abstained_rows=len(rows),rows=rows,
        joint_law_status='NOT_EXERCISED_UNAVAILABLE',team_normalization_performed=False,
        coupling_protocol_admission='NONE_FOR_THIS_REAL_SUBSET',production_release=False,
        missing_mechanisms=['Reviewed source-bound saved S kernels and native role/exposure dispatch.',
            'Reviewed compatible conditional subset joint law and numerical dispatch, including required shot-attempt/conversion primitives and physical accounting; individual minute marginals do not supply a full-team witness.'])
    return dict(payload,payload_sha256=digest(canonical(payload)))


def read_p4(raw,**inputs):
    value=strict_json(raw);expected=run_p4(**inputs)
    require(canonical(value)==canonical(expected),'P4_UPSTREAM_OR_OUTPUT_MISMATCH')
    return value
