"""Source-bound prospective all-market execution. Never reconstruct pregame time."""
import collections,copy,datetime as dt,hashlib,json,pathlib,sys
import numpy as np
J=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(J))
import joint_simulator as sim
import ws4_original_contract_adapter as ad
from all_market_v04.conditional import VERSION,MARKETS,COUNTS,covariance,require
MAP={'pass attempts':'pass_attempts','completions':'completions','passing yards':'passing_yards',
 'rush attempts':'rushing_attempts','rushing yards':'rushing_yards','receiving targets':'targets',
 'receptions':'receptions','receiving yards':'receiving_yards','tackles + assists':'tackles_assists',
 'rushing + receiving yards':'rushing_receiving_yards','passing + rushing yards':'passing_rushing_yards'}

def roles(raw):
    found={}
    def walk(x):
        if isinstance(x,dict):
            pos=x.get('position',{})
            if x.get('id') and isinstance(pos,dict) and pos.get('abbreviation'):
                found[str(x['id'])]=pos['abbreviation']
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(raw);return found


def parameterize(team,roster,ids,h):
    histteam=ad.HISTORY_TEAM_ALIAS.get(team['team_id'],team['team_id'])
    pool=[r for r in h if r['team']==histteam]
    require(len(pool)>0,'NO_TEAM_PLAYER_HISTORY')
    totals={k:sum(float(r.get(k,0) or 0) for r in pool) for k in ('attempts','targets','receptions','carries','receiving_yards','rushing_yards')}
    require(0<totals['targets']<=totals['attempts'] and totals['carries']>0,'INVALID_HISTORICAL_TEAM_ACCOUNTING')
    players=[];rejected=[];used=set()
    for pid,pos in sorted(roster.items()):
        if pos not in ('QB','RB','WR','TE','FB'):continue
        if pos=='QB' and pid!=team['starter_qb_id']:continue
        gsis=ids.get(pid,set())
        if len(gsis)!=1:
            rejected.append((pid,pos,'IDENTITY_CROSSWALK_UNVERIFIED'));continue
        gid=next(iter(gsis))
        if gid in used:raise ValueError('DUPLICATE_PLAYER_JOIN')
        used.add(gid)
        mine=[r for r in pool if r['player_id']==gid and r['position']==pos]
        if len(mine)<3:
            rejected.append((pid,pos,'INSUFFICIENT_SAME_TEAM_ROLE_HISTORY'));continue
        targets=sum(r['targets'] for r in mine);catches=sum(r['receptions'] for r in mine);carries=sum(r['carries'] for r in mine)
        require(0<=catches<=targets,'INVALID_PLAYER_CATCH_HISTORY')
        recv=[r['receiving_yards']/r['receptions'] for r in mine if r['receptions']>0]
        rush=[r['rushing_yards']/r['carries'] for r in mine if r['carries']>0]
        peers=[r for r in h if r['position']==pos]
        pt=sum(r['targets'] for r in peers);pc=sum(r['receptions'] for r in peers)
        prior=pc/pt if pt else 0.5
        # Two equivalent targets: explicit weak position partial-pooling prior.
        # Opportunity shares retain observed seasonal team denominators; no
        # renormalization to inflate players to historical per-game averages.
        players.append(dict(player_id=pid,gsis_id=gid,position=pos,n_history_games=len(mine),
          target_share=targets/totals['attempts'] if pos!='QB' else 0,rush_share=carries/totals['carries'],
          historical_targets=targets if pos!='QB' else 0,historical_catches=catches if pos!='QB' else 0,historical_carries=carries,
          catch_alpha=catches+2*prior,catch_beta=targets-catches+2*(1-prior),
          receiving_marks=recv or [0.],rushing_marks=rush or [0.],
          historical_game_ids=sorted(r['game_id'] for r in mine)))
    require(team['starter_qb_id'] in {p['player_id'] for p in players},'QB_HISTORY_UNAVAILABLE')
    remtar=totals['attempts']-sum(p['historical_targets'] for p in players)
    remcatch=totals['receptions']-sum(p['historical_catches'] for p in players)
    require(0<=remcatch<=remtar,'INVALID_RESIDUAL_COMPLETIONS')
    # Residual combines unattributed incomplete attempts and omitted receivers.
    residual=dict(catch_alpha=remcatch+.5,catch_beta=remtar-remcatch+.5,
      receiving_marks=[r['receiving_yards']/r['receptions'] for r in pool if r['receptions']>0],
      rushing_marks=[r['rushing_yards']/r['carries'] for r in pool if r['carries']>0])
    return dict(players=players,residual=residual,allocation_concentration=28.,
       historical_totals=totals,prior_equivalent_targets=2,uncertainty_status='FROZEN_SENSITIVITY_NOT_CALIBRATED'),rejected


def summarize(a,stat,line=None):
    a=np.asarray(a,dtype=float)
    out=dict(mean=float(a.mean()),variance=float(a.var()),quantiles={str(p):float(np.quantile(a,p)) for p in (.01,.05,.25,.5,.75,.95,.99)},
      draws=len(a),effective_simulation_draws=len(a),mc_se_mean=float(a.std()/np.sqrt(len(a))))
    if line is not None:
        for label,mask in [('over',a>line),('under',a<line),('push',a==line)]:
            p=float(mask.mean());out['p_'+label]=p;out['mc_se_'+label]=float(np.sqrt(p*(1-p)/len(a)))
    return out


def run(limit=None,draws=4096):
    m,ids,h,_,_,_=ad.load_inputs(ad.ROOT)
    require(all(r['season']==2025 and r['season_type']=='REG' for r in h),'FUTURE_HISTORY')
    before={str(p):ad.digest(p.read_bytes()) for p in (J/'real_original_qb_attempts_multievent_v031').glob('*.json')}
    require(len(before)==11,'FROZEN_WS4_FILES_MISSING')
    outdir=J/'all_market_v04'/'frozen';outdir.mkdir(parents=True,exist_ok=True)
    seen=set(); receipts=[];errors=[]
    while limit is None or len(seen)<limit:
        packet=ad.build_canary(exclude_event_ids=seen,include_all_qb_quotes=True)
        if not packet['input']:break
        payload=packet['input'];event=payload['events'][0];eid=event['event_id'];seen.add(eid)
        try:
            parameters={};missing=[];roster_receipts=[]
            for t in event['teams']:
                key='espn_'+t['team_id']+'_roster'
                require(key in m['sources'],'MISSING_ROSTER_SOURCE:'+key)
                raw,rr=ad.source_receipt(m['sources'][key],ad.ROOT);roster_receipts.append(rr)
                roster=roles(raw);require(len(roster)>20,'INCOMPLETE_SOURCE_ROSTER')
                par,rejected=parameterize(t,roster,ids,h)
                parameters[t['team_id']]=par
                missing.extend(dict(team_id=t['team_id'],player_id=p,position=pos,reason=why) for p,pos,why in rejected)
                # Defensive roster universe is retained as explicit abstentions.
                missing.extend(dict(team_id=t['team_id'],player_id=p,position=pos,reason='MISSING_AUTHENTIC_DEFENDER_SNAP_EXPOSURE') for p,pos in roster.items() if pos in ('LB','S','CB','DE','DT','DB','OLB','ILB','SAF','NT'))
            event['all_market_parameters']=parameters
            event['source_receipts']+=roster_receipts
            payload['input_manifest_sha256']=ad.digest(ad.canonical({k:v for k,v in payload.items() if k!='input_manifest_sha256'}))
            sim.validate(payload)
            require(ad.now()<ad.parse_time(event['event_start_at']),'KICKOFF_CLOSED')
            results=[];contracts=[];diagnostics=[];draw_records={}
            universe=[]
            for tid,par in parameters.items():
                for p in par['players']:
                    stats=['rushing_attempts','rushing_yards']
                    stats+=['pass_attempts','completions','passing_yards','passing_rushing_yards'] if p['position']=='QB' else ['targets','receptions','receiving_yards','rushing_receiving_yards']
                    universe.extend((tid,p['player_id'],s) for s in stats)
            for model in ('J1','J2'):
                samples,states=sim.sample_event(event,model,draws,payload['input_manifest_sha256']+'|'+VERSION)
                bykey={}
                for tid,pid,stat in universe:
                    a=np.array([s.get((pid,stat),0) for s in samples],dtype=int);bykey[(tid,pid,stat)]=a
                    row=dict(event_id=eid,team_id=tid,player_id=pid,stat_key=stat,model_id=model,model_version=VERSION,
                       status='FORECAST',classification='UNCERTIFIED_SHADOW_ROLE_CONDITIONAL',weather='NEUTRAL',**summarize(a,stat))
                    if stat in ('rushing_receiving_yards','passing_rushing_yards'):
                        k='receiving_yards' if stat=='rushing_receiving_yards' else 'passing_yards'
                        row['composite_diagnostics']=covariance([s.get((pid,k),0) for s in samples],[s.get((pid,'rushing_yards'),0) for s in samples])
                    row.update(input_sha256=payload['input_manifest_sha256'],parameter_sha256=ad.digest(ad.canonical(parameters)))
                    results.append(row)
                for c in m['candidates']:
                    if c.get('event_id')!=eid:continue
                    stat=MAP.get(c['stat']);key=(c.get('team'),c.get('player_id'),stat)
                    row={k:c.get(k) for k in ('candidate_id','quote_id','event_id','team','player_id','stat','line','period','source_sha256','source_received_at')}
                    row.update(model_id=model,model_version=VERSION,status='ABSTAIN')
                    if not c.get('source_certified') or not c.get('research_shadow_eligible'):row['reason']='SOURCE_OR_ROLE_UNCERTIFIED'
                    elif c.get('period') not in sim.SUPPORTED_PERIODS:row['reason']='UNSUPPORTED_PERIOD'
                    elif ad.parse_time(c['source_received_at'])>ad.parse_time(payload['input_freeze_at']):row['reason']='FUTURE_QUOTE'
                    elif key not in bykey:row['reason']='MISSING_ROLE_HISTORY_OR_DEFENDER_EXPOSURE'
                    else:row.update(status='FORECAST',**summarize(bykey[key],stat,float(c['line'])))
                    contracts.append(row)
                # Matched draws allow independent arithmetic / probability reproduction.
                draw_records[model]={'series':{tid+'|'+pid+'|'+stat:a.tolist() for (tid,pid,stat),a in bykey.items()},
                  'conservation_checks':len(states)*2,'violations':0,
                  'team_states':{t['team_id']:{k:[st[t['team_id']][k] for st in states] for k in ('plays','pass_attempts','sacks','rush_attempts','starter_qb_attempts','team_completions','team_passing_yards','team_rushing_yards','residual_targets','residual_rush_attempts','residual_receptions','residual_receiving_yards','residual_rushing_yards')} for t in event['teams']}}
                diagnostics.append(dict(model_id=model,role='J4_DEPENDENCE_DIAGNOSTIC_ONLY',composite_pairs=sum('composite_diagnostics' in r and r['model_id']==model for r in results)))
            created=ad.now().isoformat();require(ad.parse_time(created)<ad.parse_time(event['event_start_at']),'FINISHED_AFTER_KICKOFF')
            seal=dict(schema='PA_WS4_ALL_MARKET_EVENT_v04',model_version=VERSION,input_packet=payload,parameter_sha256=ad.digest(ad.canonical(parameters)),
              implementation_sha256={str(p.relative_to(J)):ad.digest(p.read_bytes()) for p in [J/'joint_simulator.py',pathlib.Path(__file__),J/'all_market_v04/conditional.py']},
              source_receipts=packet['data_receipts'],forecast_created_at=created,distributions=results,contracts=contracts,
              player_abstentions=missing,draw_records=draw_records,dependence_diagnostics=diagnostics,
              model_abstentions={'J3':'NO_CERTIFIED_PREGAME_GAME_SCRIPT_PARAMETERS','J4':'DIAGNOSTIC_ONLY'},
              weather_estimated_count=0,weather_neutral_count=len(results),
              limitations=['No authenticated game-day active confirmation; all outputs conditional on participation',
               globals().get('HISTORY_DESCRIPTION','2024 team volumes and 2025 player history are stale versus 2026'),
               'Per-game average signed yard marks are not play-level gain distributions; tails unvalidated',
               'J2 concentration 28 and pace Gamma 25 are sensitivity assumptions, not calibrated',
               'Scrambles and kneels included in official carries; spikes/throwaways in residual attempts; sacks excluded from attempts',
               'No play-level decomposition of those internal events available; no fabricated rates',
               'No historical weather coefficient fitting; weather neutral only'],research_only=True)
            raw=ad.canonical(seal)+b'\n';sh=ad.digest(raw);dest=outdir/(sh+'.json')
            with dest.open('xb') as f:f.write(raw)
            rec=dict(event_id=eid,path=str(dest.relative_to(J)),sha256=sh,distributions=len(results),contracts=dict(collections.Counter(x['status'] for x in contracts)),created_at=created,kickoff=event['event_start_at'])
            receipts.append(rec);print('FROZEN',json.dumps(rec),flush=True)
        except Exception as exc:
            errors.append(dict(event_id=eid,reason=str(exc)));print('ABSTAIN_EVENT',eid,str(exc),flush=True)
    require(before=={str(p):ad.digest(p.read_bytes()) for p in (J/'real_original_qb_attempts_multievent_v031').glob('*.json')},'FROZEN_ORIGINAL_CHANGED')
    summary=dict(schema='PA_WS4_WS6_ALL_MARKET_HANDOFF_v04',version=VERSION,events=receipts,failures=errors,
      frozen_v031_preserved=before,source_hashes={'ws1':ad.CANONICAL_WS1,'stats2025':ad.HISTORY_2025_SHA,'crosswalk':ad.CROSSWALK_SHA},
      markets=list(MARKETS),status='SHADOW_ONLY',J3='ABSTAIN_NO_CERTIFIED_SCRIPT',tackles_assists='ABSTAIN_NO_DEFENDER_EXPOSURE')
    raw=ad.canonical(summary)+b'\n';dest=outdir/(ad.digest(raw)+'.handoff.json')
    with dest.open('xb') as f:f.write(raw)
    print('HANDOFF',str(dest),ad.digest(raw),flush=True)
    return summary

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int);ap.add_argument('--draws',type=int,default=4096)
    a=ap.parse_args();run(a.limit,a.draws)
