"""Independent arithmetic audit of serialized simulator fields; fails closed."""
import numpy as np


def check(ok,reason):
    if not bool(ok):raise ValueError('SIMULATION_CONSTRAINT_VIOLATION:'+reason)


def audit(o):
    c=o['stats'];n=o['n'];m=o['minutes'];length=o['state']['duration']
    check(o['attempted_scenarios']==n and o['rejected_scenarios']==0,'SCENARIO_DENOMINATOR')
    check(len(o['scenario_ids'])==len(set(o['scenario_ids']))==n,'SCENARIO_IDENTITY')
    check(np.all(np.isfinite(m)) and np.all(m>=0) and np.all(m<=length[:,None]+1e-8),'PLAYER_MINUTES')
    check(np.allclose(length,48+5*o['state']['overtime'],atol=1e-10),'OVERTIME')
    for i in o['team_indices']:check(np.allclose(m[:,i].sum(axis=1),5*length,atol=1e-7,rtol=0),'TEAM_MINUTES')
    for k,v in c.items():check(v.shape==m.shape and np.issubdtype(v.dtype,np.integer) and np.all(v>=0),'COUNT_SUPPORT:'+k)
    check(np.array_equal(c['points'],2*c['two_pm']+3*c['threes']+c['ftm']),'POINTS_IDENTITY')
    check(np.all(c['two_pm']<=c['two_pa']) and np.all(c['threes']<=c['three_pa']) and np.all(c['ftm']<=c['fta']),'CONVERSIONS')
    for k,parts in {'pr':['points','rebounds'],'pa':['points','assists'],'ra':['rebounds','assists'],'pra':['points','rebounds','assists']}.items():check(np.array_equal(c[k],sum(c[x] for x in parts)),'COMBO:'+k)
    check(np.array_equal(c['rebounds'],c['oreb']+c['dreb']),'REBOUND_IDENTITY')
    for i,p in enumerate(o['players']):
        if p['eligible'] is False or p.get('participation_probability')==0:check(np.all(m[:,i]==0) and all(np.all(v[:,i]==0) for v in c.values()),'INACTIVE_EXPOSURE')
        check(all(np.all(v[m[:,i]==0,i]==0) for v in c.values()),'ZERO_MINUTES_EVENTS')
    for j,ledger in enumerate(o['event_ledgers']):
        a=np.asarray(ledger['assist_matrix']);check(np.trace(a)==0,'SELF_ASSIST')
        check(np.array_equal(a.sum(axis=1),c['assists'][j]),'ASSIST_ACCOUNTING')
        check(np.all(a.sum(axis=0)<=c['two_pm'][j]+c['threes'][j]),'ASSIST_SCORER_CAP')
        for t,ix in enumerate(o['team_indices']):
            check(c['assists'][j,ix].sum()+ledger['unassisted'][t]==(c['two_pm'][j,ix]+c['threes'][j,ix]).sum(),'ASSIST_FG_IDENTITY')
            other=o['team_indices'][1-t];r=ledger['rebounds'][t]
            check(r['credited']<=r['available'] and r['credited']+r['unattributed']==r['available'],'REBOUND_OPPORTUNITIES')
            check(c['oreb'][j,ix].sum()==r['offensive'] and c['dreb'][j,other].sum()==r['defensive'],'REBOUND_ALLOCATION')
            seg=o['lineup_segments'][j][t];check(bool(seg),'MISSING_LINEUP_WITNESS')
            check(abs(seg[0]['start'])<1e-7 and abs(seg[-1]['end']-length[j])<1e-7,'LINEUP_CLOCK')
            integrated=np.zeros(len(ix))
            for k,s in enumerate(seg):
                ids=s['player_indices'];check(len(ids)==len(set(ids))==5,'FIVE_ON_COURT')
                check(s['end']>s['start'] and (k==0 or abs(s['start']-seg[k-1]['end'])<1e-7),'STINT_CONTINUITY')
                integrated[ids]+=s['end']-s['start']
            check(np.allclose(integrated,m[j,ix],atol=1e-7,rtol=0),'LINEUP_MINUTE_RECONCILIATION')
    return {'violations':0,'scenarios':n,'team_scenarios':2*n,'player_scenarios':int(m.size),'five_on_court':'witness, not a learned substitution chain'}
