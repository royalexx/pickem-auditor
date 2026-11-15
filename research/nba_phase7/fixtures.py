import json
from pathlib import Path
from v2.nba_ws1.store import Receipt
from v2.nba_joint.forecast import freeze

AT='2026-11-16T23:25:00Z'
GAME={'game_id':'espn:game:2','home_team_id':'espn:team:1','away_team_id':'espn:team:2','event_start_at':'2026-11-17T00:00:00.000000Z','status':'scheduled','venue':None}

def nba_team(tid=1):
    name='Team'+str(tid)
    return {'id':1000+tid,'info':{'TEAM_ID':1000+tid,'TEAM_CITY':'Fixture','TEAM_NAME':name,'TEAM_ABBREVIATION':'F'+str(tid)},'roster':[
        {'TeamID':1000+tid,'PLAYER_ID':tid*1000+i,'PLAYER':'Player '+str(tid)+'-'+str(i),'BIRTH_DATE':'JAN %02d, 1990'%(i+1),'NUM':str(i)} for i in range(6)]}

def nba_bytes(tid=1):return ('<script id="__NEXT_DATA__" type="application/json">'+json.dumps({'props':{'pageProps':{'team':nba_team(tid)}}})+'</script>').encode()

def espn_roster(tid=1):
    return {'team':{'id':str(tid),'displayName':'Fixture Team'+str(tid),'abbreviation':'F'+str(tid)},'athletes':[
        {'id':str(tid*100+i),'fullName':'Player '+str(tid)+'-'+str(i),'dateOfBirth':'1990-01-%02dT00:00Z'%(i+1),'jersey':str(i)} for i in range(6)]}

def receipt(raw,source):return Receipt.capture(raw,source=source,observed_at=AT,origin='fixture')

def fetch(url):
    if '/scoreboard?' in url:
        events=[]
        for gid in ('1','2'):
            events.append({'id':gid,'date':'2026-11-17T00:00Z','status':{'type':{'name':'STATUS_SCHEDULED'}},'competitions':[{'id':gid,'competitors':[
                {'homeAway':ha,'team':{'id':str(t),'displayName':'Fixture Team'+str(t)}} for ha,t in [('home',1),('away',2)]]}]})
        return json.dumps({'events':events}).encode()
    if '/summary?' in url:return b'{"injuries":[]}'
    if '/roster' in url:return json.dumps(espn_roster(int(url.split('/teams/')[1].split('/')[0]))).encode()
    if '/schedule?' in url:return b'{"events":[]}'
    raise AssertionError(url)

def supplements(folder):
    from dataclasses import asdict
    import gzip
    folder=Path(folder);folder.mkdir();items=[]
    for tid in (1,2):
        raw=nba_bytes(tid);r=receipt(raw,'https://www.nba.com/team/'+str(1000+tid)+'/team'+str(tid));filename=r.raw_sha256+'.gz';(folder/filename).write_bytes(gzip.compress(raw,mtime=0))
        items.append(dict(kind='nba_team_roster',receipt=asdict(r),path=filename))
    freeze(folder/'receipt.json',dict(items=items,errors=[],status='fixture_only'))
    return folder
