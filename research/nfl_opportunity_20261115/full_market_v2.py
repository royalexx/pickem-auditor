"""Quote-independent reduced-information extension; frozen v1 is untouched.

V2 reuses v1 team, share, conversion and frozen role equations. Composite
components share game draw indices. This is not a joint team passing-yard ledger.
O4 is gated pending official component semantics, including overlapping credits.
"""
import math
from collections import Counter
import numpy as np
from . import models as m

VERSION='nfl-opportunity-full-market-v2'
MODELS=tuple(x.rsplit('-v1',1)[0]+'-full-market-v2' for x in m.MODELS)
MARKET_MAP={'pass_attempts':'pass attempts','pass_completions':'completions',
 'passing_yards':'passing yards','rush_attempts':'carries','rushing_yards':'rushing yards',
 'receiving_targets':'targets','receptions':'receptions','receiving_yards':'receiving yards',
 'tackles_assists':'tackles + assists','rushing_receiving_yards':'rushing + receiving yards',
 'passing_rushing_yards':'passing + rushing yards'}
MARKETS=tuple(MARKET_MAP)
RECEIVING={'receiving_targets','receptions','receiving_yards'}
RUSHING={'rush_attempts','rushing_yards'}
QB={'pass_attempts','pass_completions','passing_yards',*RUSHING,'passing_rushing_yards'}
OFFENSE={*RECEIVING,*RUSHING,'rushing_receiving_yards'}

def eligible(index,position,market):
    if index==1:return position in {'WR','RB','TE'} and market in OFFENSE
    if index==2:return position=='QB' and market in QB
    if index==3:return position in m.DEFENSE and market=='tackles_assists'
    if index==4:return (position in {'WR','RB','TE'} and market in OFFENSE) or (position=='QB' and market in QB)
    return False

class FullMarketModel(m.OpportunityModel):
    def offense(self,e,team,env,mixture=False):
        v,a,d,f=super().offense(e,team,env,mixture)
        # Do not invent a rushing role from a zero-only historical WR/TE sample.
        for r in self.p['roster']:
            if r['game_id']!=e['game_id'] or r['team']!=team:continue
            pid=r['player_id'];x=v.get(pid,{})
            if r['position'] in {'WR','TE'} and not any((h.get('carries') or 0)>0 for h in self.history(r)):
                for k in ('carries','rushing yards'):x.pop(k,None)
                # Removed allocation remains in the residual; never reallocates new volume.
            for total,left,right in [('rushing + receiving yards','rushing yards','receiving yards'),
                                     ('passing + rushing yards','passing yards','rushing yards')]:
                if left in x and right in x:x[total]=x[left]+x[right]
        return v,a,d,f

    def run(self):
        stats=[];teams=[];checks=[]
        def emit(r,index,market,x=None,reason=None,diagnostics=None):
            row={'game_id':r['game_id'],'team':r['team'],'player_id':r['player_id'],
                 'market':market,'model':MODELS[index],'variant':'neutral','status':'abstain',
                 'conditioning':'appearance and expected QB1 starting; uncalibrated scenario',
                 'weather_status':'WEATHER_EFFECT_NOT_ESTIMATED','reason':reason,
                 'source_id':r['source_id']}
            if x is not None:
                row.update(status='forecast',reason=None,distribution=m.distribution(x),
                           moments=m.summary(x),max_mc_standard_error=math.sqrt(.25/len(x)),diagnostics=diagnostics)
            stats.append(row)
        for e in self.p['events']:
            roster=[r for r in self.p['roster'] if r['game_id']==e['game_id']]
            try:env=self.environment(e)
            except m.GateError as exc:
                for r in roster:
                    for i in range(1,5):
                        for market in MARKETS:
                            if eligible(i,r['position'],market):emit(r,i,market,reason=str(exc))
                continue
            for team,opponent in ((e['home'],e['away']),(e['away'],e['home'])):
                en=env[team]
                error=int(np.max(np.abs(en['plays']-en['pass_attempts']-en['rush_attempts']-en['sacks'])))
                m.require(error==0,'team_conservation')
                teams.append({'game_id':e['game_id'],'team':team,'opponent':opponent,'model':MODELS[0],
                              'variant':'neutral','conservation_max_error':error,
                              'metric_definition':'accounting opportunities = attempts + official rushes + sacks suffered; not all penalty snaps',
                              'distributions':{k:m.distribution(v) if v is not None else None for k,v in en.items()},
                              'pace_status':'NOT_ESTIMATED' if en['pace_seconds'] is None else 'observed_history',
                              'weather_status':'WEATHER_EFFECT_NOT_ESTIMATED'})
                for mixture in (False,True):
                    v,a,d,f=self.offense(e,team,en,mixture)
                    targets=sum(x.get('targets',np.zeros(self.n,dtype=int)) for x in v.values())
                    carries=sum(x.get('carries',np.zeros(self.n,dtype=int)) for x in v.values())
                    m.require(np.all(targets<=en['pass_attempts']) and np.all(carries<=en['rush_attempts']),'allocation_conservation')
                    checks.append({'game_id':e['game_id'],'team':team,'mixture':mixture,
                                   'target_residual':m.summary(en['pass_attempts']-targets),
                                   'rush_residual':m.summary(en['rush_attempts']-carries),'max_conservation_error':0})
                    for r in roster:
                        if r['team']!=team or r['position'] not in {'QB','RB','WR','TE'}:continue
                        pid=r['player_id'];x=v.get(pid,{})
                        for left,right in [('receptions','targets'),('completions','pass attempts')]:
                            if left in x and right in x:m.require(np.all(x[left]<=x[right]),'player_count_constraint')
                        if 'pass attempts' in x:m.require(np.all(x['pass attempts']+x.get('carries',0)<=en['plays']-en['sacks']),'qb_accounting')
                        i=4 if mixture else 2 if r['position']=='QB' else 1
                        for market,metric in MARKET_MAP.items():
                            if not eligible(i,r['position'],market):continue
                            mask=a.get(pid)
                            reason=f.get(pid)
                            if reason is None and metric not in x:reason='MISSING_COMPONENT_OR_VERIFIED_WORKLOAD'
                            if reason is None and (mask is None or not mask.any()):reason='NO_SIMULATED_PARTICIPATION'
                            emit(r,i,market,x[metric][mask] if reason is None else None,reason,d.get(pid))
            for r in roster:
                if r['position'] in m.DEFENSE:
                    emit(r,3,'tackles_assists',reason='OFFICIAL_COMBINED_TACKLE_CREDIT_SEMANTICS_UNVERIFIED')
        indexed={(x['game_id'],x['player_id'],x['model'],x['market']):x for x in stats}
        contracts=[]
        for c in self.p['contracts']:
            market=next((k for k,v in MARKET_MAP.items() if v==c['stat']),None)
            market={'qb rushing attempts':'rush_attempts','qb rushing yards':'rushing_yards'}.get(c['stat'],market)
            for i in range(5):
                r=indexed.get((c['game_id'],c['player_id'],MODELS[i],market))
                out={'contract':c,'model':MODELS[i],'market':market,'variant':'neutral','status':'abstain',
                     'reason':r['reason'] if r else 'OUTSIDE_MODEL_ELIGIBILITY',
                     'settlement_status':'UNVERIFIED_PRODUCT_TERMS; conditional statistic only'}
                if r and r['status']=='forecast':
                    v=np.asarray(r['distribution']['values']);p=np.asarray(r['distribution']['masses'])
                    prob={k:float(p[mask].sum()) for k,mask in [('over',v>c['line']),('under',v<c['line']),('push',v==c['line'])]}
                    m.probability_object(prob)
                    out.update(status='forecast',reason=None,probabilities_conditional=prob,
                               player_stat_key=[c['game_id'],c['player_id'],MODELS[i],market])
                contracts.append(out)
        return {'schema':VERSION,'status':'SHADOW_ONLY_UNCERTIFIED','forecast_at':self.p['forecast_at'],
                'input_freeze_at':self.p['manifest']['input_freeze_at'],
                'training_cutoff_at':self.p['manifest']['training_cutoff_at'],'draws':self.n,
                'player_stat_rows':stats,'contract_rows':contracts,'team_opportunities':teams,'constraint_checks':checks,
                'seed_policy':'unchanged v1 deterministic SHA-256 game/team streams; matched component indices',
                'weather_forecasts':0,'role_weights':m.ROLE_WEIGHTS,'role_multipliers':m.ROLE_MULTIPLIERS}
