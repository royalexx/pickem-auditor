"""One-time research-only NHL historical official source collector (no pregame certification).
Cohort frozen from every opening-day 2023-10-10 NHL regular-season game.
All retrieval clocks are genuine collection-time November 2026, never backdated.
"""
import concurrent.futures, datetime as dt, hashlib, json, pathlib, re, time, urllib.error, urllib.request
from collections import Counter
BASE="https://api-web.nhle.com/v1"
FIRST="2023-10-10"
SEASONS=(("20232024","2023-10-10","2024-04-23"),
         ("20242025","2024-10-08","2025-04-23"),
         ("20252026","2025-10-07","2026-04-23"))
EXPERIMENT="EXP-P5-NHL-SOG-HIST-20261114"

def canonical(x):return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def digest(b):return hashlib.sha256(b).hexdigest()
def geturl(url):
    err=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"PickemAuditor-HistoricalResearch/2.5","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=18) as resp:body=resp.read()
            obj=json.loads(body)
            if not isinstance(obj,dict):raise ValueError("NON_OBJECT_HTTP")
            return url,body,dt.datetime.now(dt.timezone.utc).isoformat(),obj
        except (urllib.error.URLError,TimeoutError,ValueError) as exc:
            err=repr(exc);time.sleep(0.35*(attempt+1))
    raise RuntimeError("OFFICIAL_HTTP_FAILED "+url+" "+str(err))

def main():
    now=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root=pathlib.Path.cwd()/"reports"/"phase5_nhl_sog_historical"/now
    root.mkdir(parents=True,exist_ok=False)
    httpmeta=[];failures=[];rawseen=set()
    def archive(ans):
        url,body,received,obj=ans
        h=digest(body);dst=root/"raw_official_https"/(h+".json")
        dst.parent.mkdir(parents=True,exist_ok=True)
        if h not in rawseen:
            with dst.open("xb") as f:f.write(body)
            rawseen.add(h)
        httpmeta.append({"url":url,"sha256":h,"received_at_utc":received,
                         "path":str(dst.relative_to(root)),
                         "bytes":len(body),"original_pregame_archive":False})
        return obj
    first_sched=archive(geturl(BASE+"/schedule/"+FIRST))
    opening=sorted((g for week in first_sched.get("gameWeek",[]) if week.get("date")==FIRST
                   for g in week.get("games",[]) if g.get("gameType")==2),
                   key=lambda g:g["id"])
    if len(opening)<3:raise RuntimeError("OPENING_DATE_COHORT_SCHEDULE_UNAVAILABLE")
    roster={};opening_source={}
    for g in opening:
        obj=archive(geturl(BASE+"/gamecenter/"+str(g["id"])+"/boxscore"))
        if obj.get("gameState") not in ("OFF","FINAL"):raise RuntimeError("OPENING_EVENT_NOT_FINAL")
        for part in ("homeTeam","awayTeam"):
            for position,group in (("forwards","F"),("defense","D")):
                for r in obj.get("playerByGameStats",{}).get(part,{}).get(position,[]):
                    pid=str(r.get("playerId") or "")
                    if not re.fullmatch(r"\d+",pid):raise RuntimeError("PLAYER_ID_INVALID")
                    if pid in roster and roster[pid]!=group:raise RuntimeError("OPENING_PLAYER_ROLE_COLLISION")
                    roster[pid]=group;opening_source[pid]=str(g["id"])
    if len(roster)<60 or sum(x=="D" for x in roster.values())<20:
        raise RuntimeError("OPENING_DAY_PEER_GROUP_TOO_SMALL")
    print("FROZEN_PRE_EVAL_OPENING_COHORT",len(roster),dict(Counter(roster.values())),
          [g["id"] for g in opening],flush=True)
    eventmap={}
    for season,first,last in SEASONS:
        start=dt.date.fromisoformat(first);stop=dt.date.fromisoformat(last)
        day=start
        while day<=stop:
            url=BASE+"/schedule/"+day.isoformat()
            try:data=archive(geturl(url))
            except Exception as exc:
                failures.append({"kind":"SCHEDULE_FETCH","url":url,"exception":str(exc)})
                day+=dt.timedelta(days=7);continue
            for week in data.get("gameWeek",[]):
                wd=str(week.get("date") or "")
                if not first<=wd<=last:continue
                for g in week.get("games",[]):
                    if g.get("gameType")!=2 or str(g.get("season"))!=season:continue
                    gid=str(g.get("id"));teams=[g.get("homeTeam",{}).get("abbrev"),g.get("awayTeam",{}).get("abbrev")]
                    e={"game_id":gid,"game_date":wd,"season":season,
                       "start_utc":g.get("startTimeUTC"),"teams":teams}
                    if gid in eventmap and eventmap[gid]!=e:raise RuntimeError("SCHEDULE_EVENT_CONTRADICTION")
                    eventmap[gid]=e
            day+=dt.timedelta(days=7)
    if len(eventmap)<2500:
        raise RuntimeError("HISTORICAL_SCHEDULE_SOURCE_COVERAGE_TOO_LOW:"+str(len(eventmap)))
    print("OFFICIAL_SCHEDULE_EVENTS",len(eventmap),flush=True)
    jobs=[(pid,season,BASE+"/player/"+pid+"/game-log/"+season+"/2")
          for pid in sorted(roster) for season,*_ in SEASONS]
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(geturl,job[2]):job for job in jobs}
        for idx,f in enumerate(concurrent.futures.as_completed(futures),1):
            pid,season,url=futures[f]
            try:results.append((pid,season,f.result()))
            except Exception as exc:failures.append({"kind":"GAME_LOG_FETCH","player_id":pid,
                                                     "season":season,"url":url,"exception":str(exc)})
            if idx%100==0:print("GAMES_LOG_RETRIEVAL",idx,len(jobs),flush=True)
    observations=[];keys=set();missing_games=Counter();source_ref=[]
    for pid,season,result in sorted(results,key=lambda x:(x[0],x[1])):
        doc=archive(result)
        entries=doc.get("gameLog",[])
        if not isinstance(entries,list):raise RuntimeError("OFFICIAL_GAME_LOG_NOT_ARRAY")
        source_ref.append({"pid":pid,"season":season,"sha256":digest(result[1]),"n":len(entries)})
        for r in entries:
            gid=str(r.get("gameId") or "")
            if gid not in eventmap:
                missing_games[season]+=1;continue
            e=eventmap[gid]
            if e["season"]!=season or e["game_date"]!=r.get("gameDate"):
                raise RuntimeError("OFFICIAL_GAMELOG_SCHEDULE_DATE_CONFLICT")
            team=r.get("teamAbbrev")
            if team not in e["teams"]:
                raise RuntimeError("OFFICIAL_HISTORICAL_TEAM_CONFLICT:"+pid+":"+gid+":"+str(team))
            shots=r.get("shots");toi=r.get("toi")
            if type(shots) is not int or not isinstance(toi,str) or not re.fullmatch(r"\d{1,2}:[0-5]\d",toi):
                failures.append({"kind":"INVALID_OFFICIAL_STAT","pid":pid,"gid":gid});continue
            mm,ss=(int(x) for x in toi.split(":"))
            if not 0 < mm+ss/60 <= 65:
                failures.append({"kind":"INVALID_OFFICIAL_TOI","pid":pid,"gid":gid});continue
            key=(pid,gid)
            if key in keys:raise RuntimeError("DUPLICATE_OFFICIAL_PLAYER_GAME")
            keys.add(key)
            observations.append({"player_id":pid,"game_id":gid,"season":season,
               "game_date":r["gameDate"],"team":team,"position_group":roster[pid],
               "sog":shots,"toi_minutes":mm+ss/60,"official_log_body_sha256":digest(result[1]),
               "retrieved_after_historical_game":True})
    def write(name,data):
        b=b"".join(canonical(r)+b"\n" for r in data) if name.endswith(".jsonl") else canonical(data)
        with (root/name).open("xb") as f:f.write(b)
        return {"path":str((root/name).relative_to(pathlib.Path.cwd())),
                "sha256":digest(b),"bytes":len(b)}
    ob_ref=write("observations.jsonl",sorted(observations,key=lambda x:(x["game_date"],x["game_id"],x["player_id"])))
    schedule_ref=write("schedule.jsonl",sorted(eventmap.values(),key=lambda x:(x["game_date"],x["game_id"])))
    manifest={"experiment_id":EXPERIMENT,"schema":"historical_official_refetch_20261114_v1",
      "source_url_prefix":BASE,"first_cohort_date":FIRST,
      "initial_cohort_rule":"every played F/D skater in 2023-10-10 opening regular-season games, not selected on later SOG",
      "initial_cohort_n":len(roster),"first_date_games":[str(g["id"]) for g in opening],
      "initial_cohort_positions":dict(Counter(roster.values())),"initial_player_ids_with_roles":roster,
      "first_game_source":opening_source,
      "coverage_seasons":list(s[0] for s in SEASONS),
      "logs_attempted":len(jobs),"logs_succeeded":len(results),"obs_count":len(observations),
      "obs_by_season":dict(Counter(r["season"] for r in observations)),
      "unique_played_players":len({r["player_id"] for r in observations}),
      "official_scheduled_games":len(eventmap),
      "game_logs_without_complete_schedule_by_season":dict(missing_games),
      "http_source_receipts":httpmeta,"game_log_receipts":source_ref,
      "failures":failures,"observations_file":ob_ref,"schedule_file":schedule_ref,
      "source_capture":dt.datetime.now(dt.timezone.utc).isoformat(),
      "time_truth":"RETRIEVED_NOW_NOT_HISTORICALLY_AVAILABLE_PRE_GAME",
      "historical_rolling_evaluation_only":True,"D2_historical_offer_evidence":False}
    manifestref=write("source_manifest.json",manifest)
    print("PHASE5_OFFICIAL_SOURCE_COVERAGE",json.dumps(
      {k:v for k,v in manifest.items() if k in ("initial_cohort_n","initial_cohort_positions",
      "logs_attempted","logs_succeeded","obs_count","obs_by_season",
      "unique_played_players","official_scheduled_games",
      "game_logs_without_complete_schedule_by_season","failures",
      "observations_file","schedule_file")},sort_keys=True)[:9000],flush=True)
    print("PHASE5_SOURCE_MANIFEST",json.dumps(manifestref,sort_keys=True),flush=True)
    return str(root)
if __name__=="__main__":main()
