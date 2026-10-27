"""Engine B: source-owned historical workload times observed conversion.

Upcoming events belong to shared_context. Legacy qualitative/numeric scenarios
are diagnostic only and cannot become a reliable production baseline. Neither
Engine A's mean nor sportsbook probabilities supply Engine B's forecast.
"""
import math
from datetime import datetime, timezone
from urllib.parse import urlparse

VERSION = 'scouting-v7'
DIMENSIONS = ('matchup', 'opportunity', 'injuries', 'game_script')


def project_scout(candidate, now=None):
    import pickem_math as pm
    coverage = {}
    def abstain(reason):
        return dict(mean_b=None, q_win_b=None, q_push_b=None, se_b=None,
                    abstain=True, abstain_reason=reason, terms={}, reliable=False,
                    version=VERSION,coverage=coverage)
    packet = candidate.get('scouting')
    if not isinstance(packet, dict):
        return abstain('missing_scouting_packet')
    candidate=dict(candidate)
    try:
        candidate['stat']=pm._optional_stat(candidate.get('stat'))
    except pm.PickemError:
        return abstain('unsupported_sport_stat')
    supported={'NFL':pm.NFL_STATS,'NBA':pm.NBA_STATS,'NHL':pm.NHL_STATS}
    if candidate.get('stat') not in supported.get(candidate.get('sport'),()):
        return abstain('unsupported_sport_stat')
    now = now or datetime.now(timezone.utc)
    if packet.get('historical_usage'):
        try:
            # Event facts and free researcher numbers have no path into this
            # baseline. The collector owns the referenced observations.
            from usage_baseline import project
            return project(candidate,now)
        except (OSError,KeyError,ValueError,TypeError,OverflowError) as exc:
            result=abstain('invalid_collector_usage_history');result['abstain_detail']=str(exc)
            return result
    evidence = packet.get('evidence', {})
    if not isinstance(evidence, dict):
        return abstain('invalid_scouting_evidence')
    for dimension in DIMENSIONS:
        fact = evidence.get(dimension)
        if not isinstance(fact, dict):
            return abstain('missing_' + dimension)
        from research_packet import _validate_fact
        issues = []
        verified = _validate_fact(dimension, fact, issues, require_fresh=True, now=now)
        if issues or verified is None:
            return abstain('invalid_' + dimension)
        try:
            stamp = datetime.fromisoformat(str(fact['retrieved_at']).replace('Z', '+00:00'))
            age = (now - stamp).total_seconds() / 60
            url = urlparse(fact['source_url'])
            if (not 0 <= age <= 60 or url.scheme not in ('http', 'https') or
                    not url.hostname or 'underdog' in url.hostname.lower() or
                    not str(fact.get('value', '')).strip() or
                    fact.get('confidence') != 'confirmed'):
                return abstain('unverified_' + dimension)
        except (KeyError, ValueError, TypeError):
            return abstain('invalid_' + dimension)
    from scouting_checklist import required_checks
    required = required_checks(candidate.get('sport'), candidate.get('stat'))
    supporting = packet.get('supporting_stats', {})
    if not isinstance(supporting, dict):
        return abstain('invalid_supporting_stats')
    covered, gaps = {}, []
    for check in required:
        fact = supporting.get(check)
        issues = []
        verified = _validate_fact(check, fact, issues, require_fresh=True, now=now)
        if verified is None or issues or verified.confidence != 'confirmed' or verified.value in (None, ''):
            gaps.append(check)
        else:
            covered[check] = fact
    needs_season=(candidate.get('sport')=='NFL' and candidate.get('stat') in ('receptions','receiving yards','tackles','tackles + assists'))
    season_available=isinstance(packet.get('season_context'),dict)
    coverage = dict(required=required, sourced=list(covered), missing=gaps,
                    season_history_required=needs_season,season_history_available=season_available,
                    complete=bool(required) and not gaps and (not needs_season or season_available))
    scenarios = packet.get('scenarios')
    if not isinstance(scenarios, list) or len(scenarios) < 2:
        return abstain('need_uncertainty_scenarios')
    terms = []
    quality_reasons=['researcher_numeric_baseline_not_eligible']
    if needs_season and (not candidate.get('player_id') or not candidate.get('team')):
        quality_reasons.append('missing_season_candidate_identity')
    # Scenario weights are forecast assumptions too. A plausible narrative is
    # not quantitative support for assigning it a 40% probability.
    weight_fact=packet.get('scenario_weight_evidence')
    if weight_fact is None:
        quality_reasons.append('unsourced_scenario_weights')
    else:
        try:
            from nfl_opportunity import checked_fact,finite
            weight_data=checked_fact(weight_fact,now)
            counts=weight_data['counts']
            if not isinstance(counts,list) or len(counts)!=len(scenarios):raise ValueError('scenario counts mismatch')
            counts=[finite(x,'scenario count') for x in counts]
            if any(x<0 or not x.is_integer() for x in counts) or sum(counts)<1 or not weight_data.get('method'):
                raise ValueError('scenario weights require observed counts and method')
            if any(abs(row['weight']-n/sum(counts))>1e-9 for row,n in zip(scenarios,counts)):
                raise ValueError('scenario weights do not match sourced frequencies')
            if sum(counts)<50:quality_reasons.append('thin_scenario_frequency_sample')
        except (KeyError,TypeError,ValueError,AttributeError) as exc:
            result=abstain('invalid_scenario_weight_evidence');result['abstain_detail']=str(exc)
            return result
    try:
        for row in scenarios:
            if not isinstance(row, dict):
                return abstain('invalid_scenario')
            # Each scenario covers the TOTAL stat, never just a read subset.
            if row.get('scope') != 'full_game' or not row.get('rationale'):
                return abstain('unjustified_scenario')
            def number(name):
                value = row[name]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(name)
                return float(value)
            w=number('weight')
            has_projection='season_projection' in row
            if has_projection and 'opportunities' in row:
                return abstain('manual_and_season_opportunities_conflict')
            tackle_projection=has_projection and row['season_projection'].get('mode')=='tackles'
            if has_projection:
                allowed={'receptions':'receiving','receiving yards':'receiving',
                         'tackles + assists':'tackles'}
                if candidate.get('sport')!='NFL' or allowed.get(candidate.get('stat'))!=row['season_projection'].get('mode'):
                    return abstain('season_projection_stat_mode_mismatch')
            if tackle_projection and 'conversion' in row:
                return abstain('manual_and_season_conversion_conflict')
            from scouting_inputs import resolve
            controlled=resolve(row,candidate,now)
            estimates=(controlled or {}).get('estimates',{})
            volume=None if has_projection else (estimates['opportunities']['value'] if controlled else number('opportunities'))
            conversion=None if tackle_projection else (estimates['conversion']['value'] if controlled else number('conversion'))
            if controlled is None:quality_reasons.append('uncontrolled_numeric_inputs')
            elif not controlled['sufficient']:quality_reasons.append('thin_numeric_input_samples')
            if not 0 < w < 1:return abstain('invalid_scenario')
            drivers = row.get('drivers')
            if not isinstance(drivers, list) or not drivers or any(d not in covered for d in drivers):
                return abstain('scenario_drivers_need_sourced_stats')
            if needs_season and season_available and 'season_projection' not in row:
                return abstain('season_profile_must_drive_opportunities')
            season_projection = None
            automatic_effects = list((controlled or {}).get('effects',[]))
            if 'season_projection' in row:
                if candidate.get('sport') != 'NFL':return abstain('season_projection_requires_nfl')
                from nfl_opportunity import project as project_opportunities
                season_context=packet.get('season_context')
                if candidate.get('player_id') is not None and str(candidate['player_id'])!=str((season_context or {}).get('player_id')):
                    return abstain('season_player_identity_mismatch')
                if candidate.get('team') and candidate['team']!=(season_context or {}).get('team'):
                    return abstain('season_team_identity_mismatch')
                spec=dict(row['season_projection'])
                for key,value in estimates.items():
                    if key.startswith('expected_'):spec[key]=value['value']
                season_projection=project_opportunities(spec,season_context,packet,now=now)
                # Replace, never multiply, a manually entered opportunity figure.
                volume=season_projection['opportunities']
                if season_projection['conversion'] is not None:conversion=season_projection['conversion']
                automatic_effects+=season_projection.get('effects',[])
                quality_reasons+=season_projection.get('reliability_reasons',[])
            from effect_ledger import audit_scenario
            audit_row={**row,'embedded_event_ids':(controlled or {}).get('embedded',row.get('embedded_event_ids',[]))}
            effect_ledger=audit_scenario(audit_row,{**evidence,**covered},automatic_effects)
            if volume is None or conversion is None or volume <= 0 or conversion <= 0:
                return abstain("nonpositive_scenario_projection")
            if candidate.get('stat') in ('receptions','completions','tackles','tackles + assists','threes','saves','blocked shots','shots on goal','assists','rebounds') and conversion>1:
                return abstain('conversion_exceeds_one_per_opportunity')
            mean = volume * conversion
            dist = row.get('dist')
            # Dispersion belongs to the scouting scenario, not Engine A.
            sd, vr = row.get('sd'), row.get('var_ratio')
            if dist == 'poisson' and (sd is not None or vr is not None):
                return abstain('poisson_extra_params')
            if dist == 'normal' and vr is not None:
                return abstain('normal_extra_params')
            if dist == 'normal':
                sd = pm._finite('sd', sd)
                if sd <= 0 or pm.NormalDist(mean, sd).cdf(-.5) > pm.NORMAL_NEGATIVE_MASS:
                    return abstain('normal_negative_mass')
            q, push = pm.side_probs(dist, mean, candidate['line'], candidate['side'], sd, vr)
            point_q,point_push=q,push
            mean_se=None
            if controlled:
                # Conservative first-order propagation: add relative SEs (allows
                # perfectly correlated volume/rate errors), rather than assuming
                # independence. Between-script uncertainty is mixed separately.
                relative=sum(v['se']/v['value'] for v in estimates.values())
                if season_projection:relative+=season_projection['relative_se']
                mean_se=mean*relative
                process_variance=sd**2 if dist=='normal' else mean*(vr if dist=='negbin' else 1)
                n_eff=process_variance/mean_se**2
                over=point_q if candidate['side']=='over' else 1-point_q-point_push
                under=point_q if candidate['side']=='under' else 1-point_q-point_push
                robust=pm._robust_win(dist,mean,candidate['line'],sd,vr,n_eff,candidate['side'],over,under,point_push)
                q,push=robust['q_win_robust'],robust['q_push_robust']
                if dist=='normal' and pm.NormalDist(mean,math.hypot(sd,mean_se)).cdf(-.5)>pm.NORMAL_NEGATIVE_MASS:
                    return abstain('normal_predictive_negative_mass')
            terms.append(dict(weight=w, mean=mean, q_win=q, q_push=push,
                              q_win_point=point_q,q_push_point=point_push,mean_se=mean_se,
                              rationale=row['rationale'],drivers=drivers,
                              effect_ledger=effect_ledger,season_projection=season_projection))
        if abs(sum(x['weight'] for x in terms) - 1) > 1e-9:
            return abstain('scenario_weights_must_sum_to_one')
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        result=abstain('invalid_scenario')
        result['abstain_detail']=str(exc)
        return result
    mean = sum(x['weight'] * x['mean'] for x in terms)
    return dict(mean_b=mean,
                q_win_b=sum(x['weight'] * x['q_win'] for x in terms),
                q_push_b=sum(x['weight'] * x['q_push'] for x in terms),
                se_b=math.sqrt(sum(x['weight'] * ((x['mean'] - mean)**2+(x['mean_se'] or 0)**2) for x in terms)),
                abstain=False, abstain_reason=None, reliable=coverage['complete'] and not quality_reasons, version=VERSION,
                quality=dict(evidence_complete=coverage['complete'],
                    numeric_provenance_complete='uncontrolled_numeric_inputs' not in quality_reasons,
                    data_sufficient=not quality_reasons,reasons=sorted(set(quality_reasons)),
                    calibrated=False, sample_floor_policy='20 numeric observations; season-specific floors'),
                coverage=coverage,
                terms={'scenarios': terms, 'evidence': evidence, 'supporting_stats': covered},
                uncertainty='scenario_mixture_with_propagated_input_uncertainty' if not quality_reasons else 'diagnostic_scenario_mixture', calibrated=False)
