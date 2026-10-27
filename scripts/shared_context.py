"""One shared, source-derived lineup allocation applied to a probability mixture.

Research supplies statuses, never uplift coefficients. With/without comparisons
are observational, not causal identification. Missing support blocks adjustment.
"""
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from statistics import mean,stdev
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from usage_baseline import directory,source_stat
VERSION='shared-context-v4'

class ContextSupportMissing(ValueError):
    """Valid event, insufficient observations to estimate its numeric effect."""


def history_path(sport,team,stat):
    digest=hashlib.sha256(json.dumps([sport,team,source_stat(stat)]).encode()).hexdigest()
    return directory().parent/'lineups'/(digest+'.json')

def import_history(data):
    """Import complete team game observations, not forecast adjustments."""
    validate_history(data)
    path=history_path(data['sport'],data['team'],data['stat'])
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data));tmp.replace(path)
    return path

def validate_history(data):
    if data.get('sport') not in ('NBA','NHL','NFL') or not isinstance(data.get('team'),str) or not data.get('stat'):
        raise ValueError('lineup history requires sport/team/stat identity')
    seen=set()
    for row in data['games']:
        if not isinstance(row.get('id'),str) or not row['id'].strip():raise ValueError('lineup game needs stable ID')
        if row['id'] in seen:raise ValueError('duplicate lineup game')
        seen.add(row['id'])
        datetime.fromisoformat(row['date'])
        url=urlparse(row['source_url'])
        if url.scheme not in ('https','http') or not url.hostname or '.' not in url.hostname:
            raise ValueError('lineup history requires public source URLs')
        active=row['active_players'];values=row['production']
        if (not isinstance(active,list) or not active or any(not isinstance(p,str) or not p.strip() for p in active)
            or row.get('roster_complete') is not True or len(active)!=len(set(active)) or set(values)!=set(active)):
            raise ValueError('complete, unique active roster required')
        if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<0 for x in values.values()):
            raise ValueError('invalid lineup production')
        total=row['team_total']
        if isinstance(total,bool) or not isinstance(total,(int,float)) or not math.isfinite(total) or total<0 or not math.isclose(sum(values.values()),total,rel_tol=1e-8):
            raise ValueError('player production must conserve the declared team total')
        for metric,measurements in row.get('features',{}).items():
            if metric not in ('three_point_attempts','drives','passes_to','targets','first_read_targets',
                              'checkdown_targets','designed_targets','defensive_snaps','ice_time','shot_attempts',
                              'tackle_opportunities','potential_assists','rebound_chances'):
                raise ValueError('unknown tracking feature')
            if not isinstance(measurements,dict) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in measurements.values()):
                raise ValueError('invalid tracking feature')

def scaled_probabilities(pm,dist,mu,sd,vr,se,factor,factor_se,line,side):
    adjusted=mu*factor
    error=se*factor+mu*factor_se
    # Allocation changes expected count/exposure, not a second efficiency uplift.
    new_sd=sd*math.sqrt(factor) if dist=='normal' else None
    if dist=='normal' and pm.NormalDist(adjusted,math.hypot(new_sd,error)).cdf(-.5)>pm.NORMAL_NEGATIVE_MASS:
        raise ValueError('context predictive negative mass')
    q,p=pm.side_probs(dist,adjusted,line,side,new_sd,vr)
    over=q if side=='over' else 1-q-p
    under=q if side=='under' else 1-q-p
    variance=new_sd**2 if dist=='normal' else adjusted*(vr or 1)
    result=pm._robust_win(dist,adjusted,line,new_sd,vr,variance/max(error**2,1e-12),side,over,under,p)
    return dict(mean=adjusted,q_win=result['q_win_robust'],q_push=result['q_push_robust'],mean_se=error)

def apply(candidate,a,b,blend,context,now):
    import pickem_math as pm
    from nfl_opportunity import checked_fact
    from effect_ledger import fact_events
    out=dict(q_win=blend['q_win'],q_push=blend['q_push'],applied=False,eligible=True,
             ledger=[],version=VERSION,validated=False)
    if context is None:return out
    try:
        if not isinstance(context,dict) or set(context)-{'subject_status','events'}:
            raise ValueError('context accepts sourced statuses, not numeric adjustments')
        status=context.get('subject_status')
        if status is not None:
            value=checked_fact(status,now)
            if value=='out':
                return {**out,'q_win':None,'q_push':None,'eligible':False,'reason':'PLAYER_OUT','projection':None}
            if value!='active':raise ValueError('subject availability unresolved')
        events=context.get('events',[])
        if not isinstance(events,list):raise ValueError('context events must be a list')
        if not events:return out
        if not a.get('observation_ids_verified') or b.get('baseline_origin')!='collector_observations':
            raise ValueError('shared context requires source-only engine baselines')
        # Validate every declaration before allowing an unsupported-data fallback.
        # An early missing field must not conceal a later duplicate or uplift.
        players=set();roots=set();missing_metadata=False
        for event in events:
            if not isinstance(event,dict) or set(event)-{'player_id','availability','effective_at'}:
                raise ValueError('invalid context event or numeric coefficient')
            player=str(event.get('player_id') or '')
            if not player or player in players:raise ValueError('missing or duplicate absent player')
            if player==str(candidate.get('player_id')):raise ValueError('subject is absent')
            players.add(player)
            availability=event.get('availability')
            if checked_fact(availability,now)!='out':raise ValueError('redistribution requires confirmed absence')
            if any(k in availability for k in ('event_id','event_ids','causal_event')):
                for root in fact_events(availability):
                    if root in roots:raise ValueError('duplicate root event')
                    roots.add(root)
            else:missing_metadata=True
            if not event.get('effective_at') or not availability.get('effective_at'):
                missing_metadata=True
            else:
                if event['effective_at'] != availability['effective_at']:
                    raise ValueError('effective time must match the sourced absence fact')
                stamp=datetime.fromisoformat(event['effective_at'].replace('Z','+00:00'))
                if stamp.tzinfo is None or stamp > now:raise ValueError('invalid event effective time')
        if missing_metadata:
            raise ContextSupportMissing('confirmed absence lacks event identity or sourced effective time')
        seen=set();absent=[];stamps=[]
        for event in events:
            if not isinstance(event,dict):raise ValueError('context event must be an object')
            if set(event)-{'player_id','availability','effective_at'}:raise ValueError('event cannot contain numeric coefficients')
            player=str(event['player_id'])
            if checked_fact(event['availability'],now)!='out':raise ValueError('redistribution requires confirmed absence')
            if player in absent:raise ValueError('duplicate absent player')
            absent.append(player)
            for ident in fact_events(event['availability']):
                if ident in seen:raise ValueError('duplicate root event')
                seen.add(ident)
            stamp=datetime.fromisoformat(event['effective_at'].replace('Z','+00:00'))
            if event['availability'].get('effective_at')!=event['effective_at']:
                raise ValueError('effective time must match the sourced absence fact')
            if stamp.tzinfo is None or stamp>now:raise ValueError('invalid event effective time')
            if stamp.astimezone(ZoneInfo('America/Toronto')).date()<=datetime.fromisoformat(b['history_through']).date():
                raise ValueError('event overlaps baseline history; rebuild a clean baseline before applying it')
            stamps.append(stamp)
        subject=str(candidate['player_id'])
        if subject in absent:raise ValueError('subject is absent')
        data=json.loads(history_path(candidate['sport'],candidate['team'],candidate['stat']).read_text())
        if (any(data.get(k)!=candidate.get(k) for k in ('sport','team')) or
            source_stat(data.get('stat'))!=source_stat(candidate.get('stat'))):raise ValueError('lineup history identity mismatch')
        validate_history(data)
        from usage_baseline import local_day
        calendar={g['id']:g for g in data['games']}
        # Source baselines must be covered by the team observations; otherwise
        # the already-embedded allocation cannot be measured safely.
        ids=candidate.get('observation_ids') or {}
        weighted=[]
        for window in ('baseline','recent','prior'):
            values=ids.get(window,[])
            if window=='recent' and len(values)<5:continue
            weight=min(len(values),20)/len(values) if window=='prior' and values else 1.
            weighted.extend((ident,weight) for ident in values)
        b_ids=b['terms']['observation_ids']
        recent_ids=b['terms']['recent_observation_ids']
        if not weighted or not b_ids or not recent_ids or any(i not in calendar for i in set(b_ids)|{i for i,w in weighted}):
            raise ContextSupportMissing('lineup history does not cover both source baselines')
        baseline_games=[calendar[i] for i in set(b_ids)|{i for i,w in weighted}]
        observed=b['terms']['observed_production']
        if any(str(candidate['player_id']) not in g['production'] or g['production'][str(candidate['player_id'])]!=observed.get(g['id']) for g in baseline_games):
            raise ValueError('lineup and engine source production disagree')
        event_day=min(stamps).astimezone(ZoneInfo('America/Toronto')).date()
        if any(local_day(g['date'])>=event_day for g in baseline_games):
            raise ValueError('baseline lineup observation overlaps event')
        # Exclude observations at/after the event so upcoming outcomes cannot
        # revise the comparison used for this forecast.
        present=[];missing=[];used=[]
        for game in data['games']:
            day=local_day(game['date'])
            if day>=event_day or day>=now.astimezone(ZoneInfo('America/Toronto')).date():continue
            active=set(str(x) for x in game['active_players'])
            if subject not in active:continue
            if game['team_total']==0:continue  # no defined allocation; retained in baseline team budgets
            state=all(p in active for p in absent)
            joint_missing=all(p not in active for p in absent)
            if not state and not joint_missing:continue
            # Reallocate the same resource among the same eligible comparison
            # roster. A second concurrent missing teammate is not a second bonus.
            (present if state else missing).append(game)
            used.append(game['id'])
        if min(len(present),len(missing))<10:raise ContextSupportMissing('need ten complete games in each joint lineup state')
        rosters={tuple(sorted(str(p) for p in game['active_players'] if str(p) not in absent)) for game in present+missing}
        if len(rosters)!=1:raise ContextSupportMissing('comparison rosters differ beyond declared absences')
        def shares(games):
            roster=next(iter(rosters))
            return {p:mean(g['production'].get(p,0)/g['team_total'] for g in games) for p in roster}
        before=shares(present);after=shares(missing)
        # Missing-player share is redistributed once across the active roster;
        # normalize the observed absent-state shares to conserve team production.
        norm=sum(after.values());after={p:v/norm for p,v in after.items()}
        if before.get(subject,0)<=0:raise ContextSupportMissing('no subject baseline allocation')
        # Replace each component's allocation using its own source-period team
        # budget. Do not apply a full present->absent factor to a baseline that
        # has already observed some/all of that absence workload.
        a_budget=sum(calendar[i]['team_total']*w for i,w in weighted)/sum(w for i,w in weighted)
        b_budget=mean(calendar[i]['team_total'] for i in recent_ids)
        factor_a=a_budget*after[subject]/a['shrunk_mean']
        factor_b=b_budget*after[subject]/b['mean_b']
        if min(factor_a,factor_b)<=0:raise ContextSupportMissing('zero contextual allocation unsupported')
        x=[g['production'].get(subject,0)/g['team_total'] for g in present]
        y=[g['production'].get(subject,0)/g['team_total'] for g in missing]
        relative_se=max(1/math.sqrt(min(len(x),len(y))),
                       stdev(x)/math.sqrt(len(x))/mean(x)+stdev(y)/math.sqrt(len(y))/mean(y))
        factor_se_a=factor_a*relative_se;factor_se_b=factor_b*relative_se
        role_changes={}
        features=set.intersection(*(set(g.get('features',{})) for g in present+missing))
        for feature in sorted(features):
            entities=set.intersection(*(set(g['features'][feature]) for g in present+missing))
            for entity in sorted(entities):
                before_value=mean(g['features'][feature][entity] for g in present)
                after_value=mean(g['features'][feature][entity] for g in missing)
                role_changes[f'{feature}|{entity}']=dict(with_teammates=before_value,without_teammates=after_value,
                    delta=after_value-before_value,interpretation='observed joint-lineup association; not an additional multiplier')
        dist=candidate['dist'];sd=a.get('sd_used');vr=a.get('var_ratio_used')
        if dist=='negbin' and vr is None:
            vr=min(candidate['var_ratio'],pm.VAR_RATIO_CAP)
        adjusted_a=scaled_probabilities(pm,dist,a['shrunk_mean'],sd,vr,a['mean_se'],factor_a,factor_se_a,candidate['line'],candidate['side'])
        d=b['terms']['distribution']
        adjusted_b=scaled_probabilities(pm,d['dist'],b['mean_b'],d['sd'],d['var_ratio'],b['se_b'],factor_b,factor_se_b,candidate['line'],candidate['side'])
        w=blend['weights']['a']
        out.update(q_win=w*adjusted_a['q_win']+(1-w)*adjusted_b['q_win'],
                   q_push=w*adjusted_a['q_push']+(1-w)*adjusted_b['q_push'],applied=True,
                   factor=factor_a,factor_se=factor_se_a,
                   factors={'a':factor_a,'b':factor_b},team_budgets={'a':a_budget,'b':b_budget},
                   components={'a':adjusted_a,'b':adjusted_b},
                   allocation_shares=after,history_ids=used,
                   observed_role_changes=role_changes,
                   ledger=[dict(event_ids=sorted(seen),inputs=['joint_team_allocation'],applied_by='shared_context')],
                   reason='observed_joint_lineup_allocation; context accuracy unvalidated')
    except (ContextSupportMissing, FileNotFoundError) as exc:
        # Keep the verified baseline visible, but never call it adjusted or
        # publish a tier when a known absence could change its allocation.
        out.update(q_win=None,q_push=None,eligible=False,reason='CONTEXT_UNRESOLVED',
                   detail=str(exc),baseline_only=dict(q_win=blend['q_win'],q_push=blend['q_push']),
                   ranking_ceiling='Watchlist',adjustment_status='unsupported')
    except (OSError,ValueError,KeyError,TypeError,ZeroDivisionError,AttributeError) as exc:
        out.update(q_win=None,q_push=None,eligible=False,reason='CONTEXT_UNRESOLVED',detail=str(exc))
    return out

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--import-history',required=True)
    args=parser.parse_args();print(import_history(json.loads(Path(args.import_history).read_text())))
