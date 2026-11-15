"""Execute existing O4 and J1-J3 using a pinned repaired WS1 package."""
import argparse, csv, io, json, sys, math
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'research/nfl_opportunity_20261115'),str(Path(__file__).resolve().parents[1]/'reports/nfl_20261115_prospective/joint_models')]
import models as m
import joint_simulator as j
from nfl_tackle_repair import read,jsonl,table,csvrows,stamp,sha,now,canonical,unchanged
from nfl_stat_definitions import combined_tackles_assists

def run(root,pinpath,out):
    if out.exists():raise ValueError('OUTPUT_EXISTS')
    out.mkdir(parents=True)
    pin=json.loads(pinpath.read_bytes());freeze=now();pinsha=sha(pinpath.read_bytes())
    data={k:jsonl(read(root,v)) for k,v in pin['tables'].items()}
    raw={k:csvrows(root,v) for k,v in pin['source_receipts'].items() if v.get('raw_path')}
    games={g['game_id']:g for g in raw['games2026'] if g.get('season')=='2026' and g.get('game_type')=='REG' and g.get('gameday','')<'2026-11-15' and g.get('result')}
    groups=defaultdict(list)
    for r in raw['stats2026']:
        if r.get('game_id') in games and r.get('season_type')=='REG':groups[r['game_id'],r['team']].append(r)
    teams={};exclusions=Counter()
    for (gid,team),rs in groups.items():
        counts=[]
        for field in ('attempts','carries','sacks_suffered'):
            vals=[]
            for r in rs:
                try:
                    v=float(r[field]);assert math.isfinite(v) and v>=0 and v.is_integer()
                    vals.append(v)
                except (KeyError,ValueError,AssertionError):break
            if len(vals)!=len(rs):break
            counts.append(sum(vals))
        if len(counts)!=3:exclusions['INCOMPLETE_TEAM_COUNTS']+=1;continue
        g=games[gid];pa,ru,sa=counts
        if team not in (g['home_team'],g['away_team']):raise ValueError('TEAM_GAME_MISMATCH')
        teams[gid,team]={'game_id':gid,'team':team,'opponent':g['away_team'] if team==g['home_team'] else g['home_team'],
            'plays':int(pa+ru+sa),'pass_attempts':int(pa),'rush_attempts':int(ru),'sacks':int(sa),
            'season':2026,'week':int(g['week']),'end_at':g['gameday']+'T23:59:59Z','pace_seconds':None}
    stats={(r['game_id'],'gsis:'+r['player_id']):r for r in raw['stats2026']}
    players=[];snap_index={(r['player_id'],r['game_id']):r for r in data['defensive_snaps']}
    for h in data['history']:
        sr=stats.get((h['game_id'],h['player_id']));sn=snap_index.get((h['player_id'],h['game_id']))
        if not sr or not sn or sn['defensive_snaps']<=0:exclusions['HISTORY_WITHOUT_POSITIVE_DEFENSE_SNAPS']+=1;continue
        if combined_tackles_assists(sr)!=h['combined_total']:raise ValueError('RAW_COMPONENT_HANDOFF_MISMATCH')
        if sr['team']!=sn['team']:raise ValueError('SNAP_STATS_TEAM_MISMATCH')
        t=teams.get((h['game_id'],sr['team']));opp=teams.get((h['game_id'],sn['opponent']))
        if not t or not opp:exclusions['MISSING_OPPONENT_EXPOSURE']+=1;continue
        if sn['defensive_snaps']>opp['plays']:exclusions['SNAPS_EXCEED_OBSERVED_OPPONENT_PLAYS']+=1;continue
        if stamp(h['source_available_at'])>stamp(freeze) or stamp(sn['source_available_at'])>stamp(freeze):raise ValueError('FUTURE_SOURCE')
        players.append({'game_id':h['game_id'],'player_id':h['player_id'],'team':sr['team'],'position':sr['position'],
            'season':2026,'week':t['week'],'end_at':t['end_at'],'state':'played','snaps':sn['defensive_snaps'],
            **dict(zip(m.COMPONENTS,[float(sr[k]) for k in ('def_tackles_solo','def_tackles_with_assist','def_tackle_assists')]))})
    # Only source-authenticated paired exposures reach the O4 API; omitted rows
    # are counted above, not recoded as zero. Require three paired games.
    model=m.OpportunityModel.from_defensive_history(teams,players,freeze)
    roster={r['player_stat_id']:r for r in data['defender_coverage']}; ledger=[];param={};events={};reasons=Counter()
    for c in data['original_contracts']:
        q=c['original_record'];p=roster.get(c['player_stat_id']);reason=None
        row={'candidate_id':c['candidate_id'],'quote_id':c['quote_id'],'original_contract':c,'feature_pin_sha256':pinsha,
            'input_freeze_at':freeze,'source_cutoff_at':max(v['observed_received_at'] for v in pin['source_receipts'].values() if v.get('observed_received_at')),
            'O4':{'status':'ABSTAIN'},'J1':{'status':'ABSTAIN'},'J2':{'status':'ABSTAIN'},'J3':{'status':'ABSTAIN'},
            'certification':'UNCERTIFIED','conditioning':'appearance','weather_status':'WEATHER_EFFECT_NOT_ESTIMATED'}
        if not q.get('source_certified') or not q.get('research_shadow_eligible'):reason='ORIGINAL_QUOTE_NOT_SOURCE_ELIGIBLE'
        elif not p:reason='UNMAPPED_PLAYER_STAT'
        elif not p['source_count_model_ready']:reason='|'.join(p['source_count_abstention_reasons'])
        elif stamp(q['event_start_at'])<=stamp(freeze):reason='KICKOFF_PASSED'
        if not reason:
            r={'player_id':p['player_id'],'team':p['team'],'position':p['position'],'status':'uncertain','participation_probability':1.}
            # Match provider team abbreviations explicitly; WS1 uses ESPN WSH etc.
            aliases={'WSH':'WAS','LAR':'LA'}
            r['team']=aliases.get(r['team'],r['team']);opp=aliases.get(p['opponent'],p['opponent'])
            e={'game_id':q['event_id'],'home':r['team'],'away':opp,'event_start':q['event_start_at']}
            try:
                hs=[h for h in model.history(r) if h['state']=='played']
                par=m.defensive_parameters(hs,teams,players,r['position'])
                env=model.environment(e)
                x,active,diagnostics=model.defender(e,r,env[opp])
                x=x['tackles + assists'];probs=m.oup(x,q['line']);at=now()
                if stamp(at)>=stamp(q['event_start_at']):raise ValueError('KICKOFF_PASSED_AT_FORECAST')
                row['O4']={'status':'FORECAST','model':'O4-defensive-components-v1-tackle-repair-v252','forecast_at':at,
                    'probabilities':probs,'moments':m.summary(x),'distribution':m.distribution(x),'diagnostics':diagnostics,
                    'conditional_on_appearance':True,'max_mc_standard_error':math.sqrt(.25/len(x))}
                param[q['event_id'],r['player_id']]={'player_id':r['player_id'],'role':'DEFENDER','participation':1.,'snap_share':par['snap_alpha']/(par['snap_alpha']+par['snap_beta']),
                    'verified_defensive_parameters':par,'team':r['team']}
                events[q['event_id']]=e
            except (ValueError,KeyError) as exc:reason=str(exc)
        if reason:
            reasons[reason]+=1
            for k in ('O4','J1','J2','J3'):row[k]={'status':'ABSTAIN','reason':reason}
        ledger.append(row)
    # Existing shared-state simulator, existing frozen SCENARIOS, no new simulator.
    joint_files=[]
    for eid,e in events.items():
        event={'event_id':eid,'teams':[]}
        for team in (e['home'],e['away']):
            h=sorted([t for t in teams.values() if t['team']==team],key=lambda t:t['week'])[-10:]
            if len(h)<3:raise ValueError('MISSING_TEAM_CONTEXT')
            den=sum(t['plays'] for t in h)
            event['teams'].append({'team_id':team,'plays_mean':float(np.mean([t['plays'] for t in h])),
                'pass_rate':sum(t['pass_attempts'] for t in h)/den,'sack_rate':sum(t['sacks'] for t in h)/den,
                'players':[v for (ev,pid),v in param.items() if ev==eid and v['team']==team]})
        for model_id in ('J1','J2','J3'):
            rng=np.random.default_rng(int(sha(canonical([pinsha,eid,model_id]))[:16],16));draws=defaultdict(list);exposure_checks=0
            scripts=list(j.SCENARIOS);weights=[j.SCENARIOS[s][2] for s in scripts]
            for _ in range(4096):
                script=str(rng.choice(scripts,p=weights)) if model_id=='J3' else 'neutral'
                values,state=j.game_once(event,rng,model_id,script)
                for (ev,pid),p in param.items():
                    if ev!=eid:continue
                    draws[pid].append(values.get((pid,'tackles_assists'),0))
                    st=state[p['team']]['defense'][pid];assert 0<=st['defensive_snaps']<=st['opponent_plays'];exposure_checks+=1
            rec=table(out,eid+'_'+model_id+'_draws',[{'player_id':pid,'draws':xs} for pid,xs in sorted(draws.items())]);joint_files.append(rec)
            for row in ledger:
                q=row['original_contract']['original_record'];p=roster.get(row['original_contract']['player_stat_id'])
                if q['event_id']!=eid or row['O4']['status']!='FORECAST':continue
                xs=np.asarray(draws[p['player_id']]);at=now()
                if stamp(at)>=stamp(q['event_start_at']):row[model_id]={'status':'ABSTAIN','reason':'KICKOFF_PASSED_AT_FORECAST'};continue
                row[model_id]={'status':'FORECAST','model_version':j.VERSION,'forecast_at':at,'probabilities':m.oup(xs,q['line']),
                    'moments':m.summary(xs),'shared_draws':rec,'draws':4096,'exposure_checks':exposure_checks,
                    'scenario_policy':'existing frozen SCENARIOS assumptions; uncalibrated and not source-estimated' if model_id=='J3' else 'neutral',
                    'max_mc_standard_error':math.sqrt(.25/4096)}
    ref=table(out,'opportunity_joint_ledger',ledger)
    report={'schema':'tackle-opportunity-repair-v252','freeze':freeze,'feature_pin_sha256':pinsha,'quotes':len(ledger),'source_player_rows':len(players),
        'team_games':len(teams),'exclusions':dict(exclusions),'abstentions':dict(reasons),'forecast_counts':{k:sum(r[k]['status']=='FORECAST' for r in ledger) for k in ('O4','J1','J2','J3')},
        'ledger':ref,'joint_files':joint_files,'certified':0,'independently_accepted':0,'source_count_only':True}
    unchanged(out/'EXECUTION_RECEIPT.json',canonical(report));print(json.dumps(report));return report
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--pin',type=Path,required=True);a.add_argument('--out',type=Path,required=True);x=a.parse_args();run(x.root,x.pin,x.out)
