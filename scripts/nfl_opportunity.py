"""Full-game opportunity mechanisms from season profiles; no flat stock bonuses."""
import math
from datetime import datetime, timezone
from nfl_season_store import BUCKETS, CATEGORIES, VERSION


def finite(value,name):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):
        raise ValueError(name+' must be finite')
    return float(value)


def checked_fact(fact,now):
    from research_packet import _validate_fact
    issues=[];v=_validate_fact('scenario_projection',fact,issues,require_fresh=True,now=now)
    if issues or v is None or v.confidence!='confirmed':raise ValueError('projection requires fresh confirmed evidence')
    return v.value


def project(spec,context,packet,*,now=None):
    """Return opportunities and conditional conversion override, plus auditable deltas."""
    now=now or datetime.now(timezone.utc)
    if not isinstance(context,dict) or context.get('metadata',{}).get('version')!=VERSION:
        raise ValueError('current-season profile unavailable')
    meta=context['metadata']
    season=now.year-(now.month<3)
    if meta.get('season')!=season:raise ValueError('season profile does not match evaluation season')
    stamp=datetime.fromisoformat(meta['retrieved_at'].replace('Z','+00:00'))
    if not 0 <= (now-stamp).total_seconds() <= 3600:
        raise ValueError('season source must be refreshed/reverified for this run')
    if meta.get('missing_play_game_ids'):raise ValueError('incomplete completed-game history')
    mode=spec.get('mode')
    if mode=='receiving':
        passer=str(spec.get('passer_id') or '')
        if str(checked_fact(packet.get('confirmed_passer'),now))!=passer:
            raise ValueError('starting passer identity not confirmed')
        q=context.get('passers',{}).get(f"{context['team']}|{passer}")
        if not q:raise ValueError('passer has no season profile for this offense')
        r=q['receivers'].get(str(context['player_id']))
        if not r:raise ValueError('receiver has no observed target profile with this passer')
        attempts=finite(spec.get('expected_pass_attempts'),'expected_pass_attempts')
        if attempts<=0:raise ValueError('pass attempts must be positive')
        counts=dict(q['targeted']);receiver_counts=dict(r['buckets']);throws=q['throws']
        if spec.get('use_defense_adjustment',True):
            # The upcoming defense is excluded from the offense baseline before
            # its tendency is applied. Otherwise that matchup could enter twice.
            counts={k:counts.get(k,0)-q['by_defense'].get(context['opponent'],{}).get(k,0) for k in BUCKETS}
            receiver_counts={k:receiver_counts.get(k,0)-r['by_defense'].get(context['opponent'],{}).get(k,0) for k in BUCKETS}
            throws-=q['throws_by_defense'].get(context['opponent'],0)
        targeted=sum(counts.values())
        if targeted<=0 or throws<=0:raise ValueError('no independent offense baseline outside upcoming defense')
        probabilities={k:counts.get(k,0)/targeted for k in BUCKETS}
        mix={k:(probabilities.get(k) or 0.) for k in BUCKETS}
        # Compare defense to the QBs it actually faced, using their other opponents.
        # Unknown/unclassified reads stay an explicit component, never a win for D.
        adjustments={k:1. for k in BUCKETS};adjustment_notes=[]
        if spec.get('use_defense_adjustment',True):
            d=context.get('defense')
            if not d or not d['opponent_adjusted_comparable_targets']:
                raise ValueError('defense lacks opponent-QB comparison sample')
            if d['unmatched_qbs']:
                adjustment_notes.append('Passers without an other-opponent baseline are excluded from both sides of the comparison: '+str(len(d['unmatched_qbs'])))
            for k in BUCKETS[:-1]:
                expected=d['opponent_qb_expected_counts'].get(k,0)
                actual=d['matched_actual_counts'].get(k,0)
                if expected>0:adjustments[k]=actual/expected
                elif actual>0 or mix[k]>0:
                    raise ValueError('read bucket has no comparison baseline')
            # Preserve unknown probability, changing only the observed known-read mix.
            known=1-mix['unknown'];norm=sum(mix[k]*adjustments[k] for k in BUCKETS[:-1])
            if known and norm<=0:raise ValueError('invalid matched read mixture')
            for k in BUCKETS[:-1]:mix[k]=known*mix[k]*adjustments[k]/norm if norm else 0
            adjustment_notes.append('Observed opponent-QB adjusted tendency; not an identified causal defense effect.')
        shares={k:receiver_counts.get(k,0)/counts[k] if counts.get(k) else 0. for k in BUCKETS}
        baseline=sum((probabilities.get(k) or 0.)*shares[k] for k in BUCKETS)
        matched=sum(mix[k]*shares[k] for k in BUCKETS)
        targetable=targeted/throws
        expected_targets=attempts*targetable*matched
        base_targets=attempts*targetable*baseline
        effects=[]
        reasons=[]
        receiver_n=sum(receiver_counts.values())
        known_n=targeted-counts.get('unknown',0)
        if targeted<100 or receiver_n<20 or len(q['by_game'])<3:
            reasons.append('thin_independent_passer_receiver_history')
        if known_n/targeted<.8:reasons.append('insufficient_read_classification')
        # Delta-method sampling envelope. Reciprocal count terms include the
        # offense mix, recipient allocation and matched-defense comparison.
        # Add rather than cancel errors from dependent components. This is a
        # conservative approximation, not a fitted causal or hierarchical model.
        relative_se=1/math.sqrt(targeted)+1/math.sqrt(max(receiver_n,1))
        if spec.get('use_defense_adjustment',True):
            comparable=d['opponent_adjusted_comparable_targets']
            if comparable<100:reasons.append('thin_defense_comparison')
            relative_se+=1/math.sqrt(max(comparable,1))
            for k in BUCKETS[:-1]:
                if probabilities[k]*shares[k]>0:
                    expected=d['opponent_qb_expected_counts'].get(k,0)
                    actual=d['matched_actual_counts'].get(k,0)
                    if min(expected,actual,counts.get(k,0))<10:
                        reasons.append('sparse_read_bucket_comparison')
                    relative_se+=mix[k]*shares[k]/max(matched,1e-12)*(1/math.sqrt(max(expected,1))+1/math.sqrt(max(actual,1))+1/math.sqrt(max(counts.get(k,0),1)))
            effects.append(dict(event_id=f"nfl:{season}:{context['opponent']}:read_tendency",
                                inputs=['read_bucket_mix'],applied_by='season_opportunity_projection'))
        return dict(effects=effects,opportunities=expected_targets,conversion=None,mode=mode,
                    reliability_reasons=sorted(set(reasons)),relative_se=relative_se,
                    sample_counts=dict(offense_targets=targeted,receiver_targets=receiver_n,known_reads=known_n),
                    expected_targets=expected_targets,offense_only_targets=base_targets,
                    opportunity_delta=expected_targets-base_targets,bucket_mix=mix,
                    receiver_share_by_bucket=shares,defense_ratio_by_bucket=adjustments,
                    targetable_rate=targetable,pass_attempts=attempts,
                    comparison_targets=(context.get('defense') or {}).get('opponent_adjusted_comparable_targets'),
                    read_coverage=1-counts.get('unknown',0)/targeted,
                    baseline_excludes_upcoming_defense=spec.get('use_defense_adjustment',True),
                    notes=adjustment_notes,
                    source_snapshot=meta)
    if mode=='tackles':
        player=context.get('defender');opponent=context.get('opponent_offense');own=context.get('own_defense')
        if not player or not opponent or not own:raise ValueError('missing tackle or opponent play-mix history')
        plays=finite(spec.get('expected_defensive_plays'),'expected_defensive_plays')
        if plays<=0:raise ValueError('expected defensive plays must be positive')
        total=sum(opponent['categories'].values())
        mix={k:opponent['categories'].get(k,0)/total for k in CATEGORIES} if total else {}
        if 'play_mix' in spec:
            supplied=spec['play_mix']
            if checked_fact(spec.get('mix_evidence'),now)!=supplied:raise ValueError('play-mix evidence mismatch')
            if not isinstance(supplied,dict) or set(supplied)-set(CATEGORIES):raise ValueError('unknown play category')
            mix={k:finite(supplied.get(k,0),'play_mix') for k in CATEGORIES}
        if not mix or any(v<0 for v in mix.values()) or abs(sum(mix.values())-1)>1e-9:
            raise ValueError('play mix must be nonnegative and sum to one')
        role_factor=finite(spec.get('role_factor',1.),'role_factor')
        if role_factor<=0:raise ValueError('role_factor must be positive')
        if role_factor!=1 and checked_fact(spec.get('role_evidence'),now)!=role_factor:
            raise ValueError('role change requires matching evidence; no automatic injury bonus')
        rates=player['credit_rate_per_team_play']
        for k in CATEGORIES:
            if mix[k]>0 and rates.get(k) is None:raise ValueError('unobserved tackle category: '+k)
            if (rates.get(k) or 0)*role_factor>1:raise ValueError('role adjustment implies more than one credit per team play')
        conversion=sum(mix[k]*(rates.get(k) or 0.)*role_factor for k in CATEGORIES)
        base_total=sum(own['categories'].values())
        baseline=sum(player['credits'].values())/base_total if base_total else 0
        from effect_ledger import fact_events
        effects=[dict(event_id=f"nfl:{season}:{context['opponent']}:play_mix",
                      inputs=['play_mix'],applied_by='season_opportunity_projection')]
        if 'play_mix' in spec:
            effects.extend(dict(event_id=e,inputs=['play_mix'],applied_by='sourced_mix_scenario') for e in fact_events(spec['mix_evidence']))
        if role_factor!=1:
            effects.extend(dict(event_id=e,inputs=['role_factor'],applied_by='sourced_role_scenario') for e in fact_events(spec['role_evidence']))
        reasons=[]
        active=[k for k in CATEGORIES if mix[k]>0]
        if total<100 or base_total<100 or sum(player['credits'].values())<20 or len(player['games'])<3:
            reasons.append('thin_tackle_play_history')
        if any(player['team_play_denominators'].get(k,0)<30 for k in active):
            reasons.append('sparse_tackle_category')
        relative_se=1/math.sqrt(max(total,1))+1/math.sqrt(max(sum(player['credits'].values()),1))
        relative_se+=sum(mix[k]/math.sqrt(max(player['team_play_denominators'].get(k,0),1)) for k in active)
        # Sourced role/mix overrides also need measured uncertainty to qualify.
        # Until those transformations supply it, keep them visible diagnostics.
        if role_factor!=1 or 'play_mix' in spec:reasons.append('unquantified_role_or_mix_override')
        return dict(effects=effects,opportunities=plays,conversion=conversion,mode=mode,
                    reliability_reasons=reasons,relative_se=relative_se,
                    sample_counts=dict(opponent_plays=total,own_plays=base_total,credits=sum(player['credits'].values())),
                    expected_tackles_assists=plays*conversion,baseline_same_volume=plays*baseline,
                    opportunity_delta=plays*(conversion-baseline),play_mix=mix,
                    personal_credit_rates=rates,role_factor=role_factor,
                    notes=['Rates include historical bench/absence exposure. No on-field alignment or causal injury effect is inferred.'],
                    source_snapshot=meta)
    raise ValueError('unknown season projection mode')
