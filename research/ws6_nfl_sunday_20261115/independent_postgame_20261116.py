"""WS6 independent postgame rescore. Research-only; never edits frozen inputs."""
from __future__ import annotations
import collections, csv, datetime as dt, hashlib, io, json, math, pathlib, random, re
import numpy as np
import requests

ROOT = pathlib.Path("reports/nfl_20261115_prospective")
OUT = ROOT / "ws6_independent_postgame_20261116_v1"
COMPARE = ROOT / "ensemble_20261115_research_shadow/comparison_original_quotes_1845.jsonl"
HANDOFF = ROOT / "joint_models/all_market_v04/WS6_HANDOFF_20261115.json"
JR = ROOT / "joint_models/all_market_v04/frozen"
EPSN = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
UTC = dt.timezone.utc
MAP = {"pass attempts":"pass_attempts","completions":"pass_completions",
       "passing yards":"passing_yards","rush attempts":"rush_attempts",
       "rushing yards":"rushing_yards","receptions":"receptions",
       "receiving yards":"receiving_yards","tackles + assists":"tackles_assists"}
MAPPED = {v:k for k,v in MAP.items()}

def h(b): return hashlib.sha256(b).hexdigest()
def utc(x):
    if not x: return None
    y=dt.datetime.fromisoformat(str(x).replace("Z","+00:00"))
    return y.astimezone(UTC) if y.tzinfo else None
def norm(s): return re.sub(r"[^a-z0-9]+","",str(s).lower())
def num(x):
    try: return float(str(x).replace(",",""))
    except Exception: return None
def load(path): return json.loads(path.read_bytes())
def rows(path): return [json.loads(x) for x in path.read_bytes().splitlines() if x]
def frozen_write(path,b):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=b: raise RuntimeError("IMMUTABLE_OUTPUT_COLLISION:"+str(path))
        return
    with path.open("xb") as f: f.write(b)
def dump(path,obj):
    frozen_write(path,(json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+"\n").encode())
def source(path,expected=None):
    b=path.read_bytes(); actual=h(b)
    if expected and actual!=expected: raise RuntimeError("SOURCE_SHA_MISMATCH:"+str(path))
    return actual
def interval_draw(vals,y,a):
    lo,hi=np.quantile(vals,[(1-a)/2,(1+a)/2])
    return int(lo<=y<=hi),float(lo),float(hi)
def crps_sample(vals,y):
    x=np.sort(np.asarray(vals,dtype=float)); n=x.size
    # E|X-y| - 0.5 E|X-X'| with empirical law of n equally weighted atoms.
    return float(np.mean(np.abs(x-y))-np.dot(2*np.arange(n)-n+1,x)/(n*n))
def parse_boxscore(event,blob):
    j=json.loads(blob); header=j.get("header",{}).get("competitions",[{}])[0]
    if j.get("header",{}).get("id") not in (None,str(event)): raise ValueError("WRONG_GAME_HEADER")
    typ=header.get("status",{}).get("type",{})
    if typ.get("name")!="STATUS_FINAL": raise ValueError("NONFINAL")
    byid,byname={},collections.defaultdict(set)
    bad=[]
    for team in j.get("boxscore",{}).get("players",[]):
        abbr=team.get("team",{}).get("abbreviation")
        for cat in team.get("statistics",[]):
            category=cat.get("name","")
            labels=cat.get("labels",[])
            for a in cat.get("athletes",[]):
                pl=a.get("athlete",{})
                pid=str(pl.get("id",""))
                pname=pl.get("displayName","")
                if not pid: continue
                byname[norm(pname)].add(pid)
                rec=byid.setdefault(pid,{"id":pid,"name":pname,"team":abbr,"present_categories":set(),"stats":{},"defensive_parity_ok":True})
                if rec["team"]!=abbr: bad.append((pid,"CONFLICTING_TEAM"))
                rec["present_categories"].add(category)
                values=dict(zip(labels,a.get("stats",[])))
                target=None
                if category=="passing":
                    c=values.get("C/ATT","").split("/")
                    if len(c)==2:
                        rec["stats"]["pass_completions"]=num(c[0])
                        rec["stats"]["pass_attempts"]=num(c[1])
                    rec["stats"]["passing_yards"]=num(values.get("YDS"))
                elif category=="rushing":
                    rec["stats"]["rush_attempts"]=num(values.get("CAR"))
                    rec["stats"]["rushing_yards"]=num(values.get("YDS"))
                elif category=="receiving":
                    rec["stats"]["receptions"]=num(values.get("REC"))
                    rec["stats"]["receiving_yards"]=num(values.get("YDS"))
                    rec["stats"]["receiving_targets"]=num(values.get("TGTS"))
                elif category=="defensive":
                    t=num(values.get("TOT"));solo=num(values.get("SOLO"))
                    rec["stats"]["tackles_assists"]=t
                    if t is not None and solo is not None and t+1e-6<solo:
                        rec["defensive_parity_ok"]=False
    for x in byid.values(): x["present_categories"]=sorted(x["present_categories"])
    return byid,byname,bad

def official_sources(events):
    # First original official capture is immutable. Subsequent runs replay cached bytes.
    off=OUT/"official_source"
    files={}
    scoreboard=off/"espn_scoreboard_20261115.json"
    if not scoreboard.exists():
        res=requests.get(EPSN+"scoreboard?dates=20261115",timeout=30)
        res.raise_for_status();frozen_write(scoreboard,res.content)
    sj=load(scoreboard)
    es={str(e["id"]):e for e in sj.get("events",[])}
    for event in sorted(events):
        if event not in es:raise RuntimeError("MISSING_OFFICIAL_GAME:"+event)
        typ=es[event].get("status",{}).get("type",{})
        if typ.get("name")!="STATUS_FINAL":raise RuntimeError("UNFINISHED_EVENT:"+event)
        path=off/("espn_"+event+"_summary.json")
        if not path.exists():
            res=requests.get(EPSN+"summary?event="+event,timeout=30);res.raise_for_status()
            frozen_write(path,res.content)
        byid,byname,bad=parse_boxscore(event,path.read_bytes())
        files[event]={"path":str(path),"sha256":source(path),"observed_players":len(byid),"name_collisions":sum(len(ids)>1 for ids in byname.values()),"errors":bad}
        files[event]["_ids"]=byid
        files[event]["_names"]=byname
    summary={"scoreboard":{"path":str(scoreboard),"sha256":source(scoreboard)},
             "events":{k:{x:y for x,y in v.items() if not x.startswith("_")} for k,v in files.items()}}
    return files,summary

def get_stat(event,plid,name,market,files):
    f=files.get(event)
    if f is None:return None,"EVENT_MISSING",None
    ids=f["_ids"]
    # Prefer the immutable ESPN player_id from the original simulator.
    if plid:
        player=ids.get(str(plid))
        if player is None: return None,"PLAYER_NOT_BOXED",None
        if name and norm(name)!=norm(player["name"]): return None,"PLAYER_ID_NAME_CONFLICT",player
    else:
        matches=f["_names"].get(norm(name),set())
        if len(matches)!=1: return None,("PLAYER_NAME_AMBIGUOUS" if matches else "PLAYER_NOT_BOXED"),None
        player=ids[next(iter(matches))]
    if market not in player["stats"]:
        return None,"CATEGORY_NOT_BOXED",player
    value=player["stats"][market]
    if value is None or not math.isfinite(value):return None,"UNPARSEABLE_STAT",player
    if market=="tackles_assists" and not player["defensive_parity_ok"]:
        return None,"TACKLE_INTERNAL_PARITY",player
    return float(value),"OBSERVED",player

def assess(p,push,y,line):
    if any(x is None or not math.isfinite(x) for x in [p,push,y,line]):return None
    under=1-p-push
    if min(p,push,under)<-1e-7 or max(p,push,under)>1+1e-7:return None
    direction="OVER" if y>line else "UNDER" if y<line else "PUSH"
    # Three-way Brier / categorical log loss (no binary reduction on a push).
    dist={"OVER":p,"UNDER":under,"PUSH":push}
    bs=sum((dist[d]-(d==direction))**2 for d in dist)
    ll=-math.log(max(dist[direction],1e-12))
    if direction=="PUSH":return dict(direction=direction,brier=None,logloss=None,hit=None,three_way_brier=bs,three_way_logloss=ll,conf=None)
    q=p/(p+under) if p+under else None
    if q is None:return None
    z=int(direction=="OVER")
    confident=max(q,1-q)
    hit=int((q>=.5)==bool(z)) if abs(q-.5)>1e-12 else None
    return dict(direction=direction,brier=(q-z)**2,logloss=-math.log(max(q if z else 1-q,1e-12)),
                hit=hit,three_way_brier=bs,three_way_logloss=ll,conf=confident,p_over_cond=q,observed_over=z)

def dedup(df):
    # Identity excludes provider/book but never excludes a distinct offered line.
    grouped=collections.defaultdict(list)
    for r in df:grouped[(r["model"],r["event"],r["player_id"] or norm(r["player"]),r["market"],r["line"],r["period"])].append(r)
    out=[];conflicts=[]
    for key,rs in grouped.items():
        scores={(round(r["p_over"],10),round(r["p_push"],10),round(r["mean"],7) if r["mean"] is not None else None) for r in rs}
        if len(scores)!=1:
            conflicts.append({"key":str(key),"n":len(rs),"scores":list(scores)[:6]})
            continue
        t=dict(rs[0]);t["duplicate_quotes"]=len(rs)-1
        out.append(t)
    return out,conflicts

def score_summary(rr):
    x=[a for a in rr if a.get("brier") is not None]
    return dict(scored=len(x),three_way_scored=sum(a.get("three_way_brier") is not None for a in rr),
       brier=float(np.mean([a["brier"] for a in x])) if x else None,
       logloss=float(np.mean([a["logloss"] for a in x])) if x else None,
       hit_rate=float(np.mean([a["hit"] for a in x if a["hit"] is not None])) if any(a["hit"] is not None for a in x) else None,
       high_conf_n=sum(a["conf"]>=.8 for a in x),
       high_conf_hits=sum(a["hit"]==1 and a["conf"]>=.8 for a in x),
       mean_signed_error=float(np.mean([a["mean"]-a["y"] for a in x if a["mean"] is not None])) if any(a["mean"] is not None for a in x) else None,
       mean_abs_error=float(np.mean([abs(a["mean"]-a["y"]) for a in x if a["mean"] is not None])) if any(a["mean"] is not None for a in x) else None,
       crps=float(np.mean([a["crps"] for a in x if a.get("crps") is not None])) if any(a.get("crps") is not None for a in x) else None,
       intervals={str(c):{"n":sum(str(c) in a.get("intervals",{}) for a in x),
           "coverage":float(np.mean([a["intervals"][str(c)] for a in x if str(c) in a.get("intervals",{})])) if any(str(c) in a.get("intervals",{}) for a in x) else None}
           for c in (0.5,0.8,0.9,0.95)})

def paired(aa,bb,seed=20261116):
    a={(x["event"],x["player_id"] or norm(x["player"]),x["market"],x["line"],x["period"]):x for x in aa if x.get("brier") is not None}
    b={(x["event"],x["player_id"] or norm(x["player"]),x["market"],x["line"],x["period"]):x for x in bb if x.get("brier") is not None}
    keys=sorted(set(a)&set(b),key=str)
    if not keys:return {"matched":0}
    delta=np.array([a[k]["brier"]-b[k]["brier"] for k in keys])
    groups=collections.defaultdict(list)
    for i,k in enumerate(keys):groups[k[0]].append(i)
    g=list(groups.values());rng=np.random.default_rng(seed)
    ci=None
    if len(g)>1:
        vals=[]
        for _ in range(3000):
            ix=np.concatenate([g[j] for j in rng.integers(0,len(g),len(g))])
            vals.append(float(np.mean(delta[ix])))
        ci=[float(x) for x in np.quantile(vals,[.025,.975])]
    return {"matched":len(keys),"games":len(g),"brier_a":float(np.mean([a[k]["brier"] for k in keys])),
            "brier_b":float(np.mean([b[k]["brier"] for k in keys])),
            "delta_a_minus_b":float(np.mean(delta)),"game_bootstrap_ci95":ci,
            "date_cluster_ci":"UNESTIMABLE_SINGLE_DATE"}

def main():
    base=rows(COMPARE)
    manifest=load(HANDOFF)
    pin=manifest["handoff"]["original_contract_ledger"]
    jpath=JR/pathlib.Path(pin["path"]).name
    source(COMPARE,"0e398b781070ce648b7dc46bf726f6eed850b40e67366de355d516ff028ecc8f")
    source(jpath,pin["sha256"])
    archived=rows(jpath) if jpath.suffix==".jsonl" else load(jpath)
    assert len(base)==1845 and len(archived)==5535
    valid_events={str(x["event_id"]) for x in base if x.get("event_id")}
    files,official=official_sources(valid_events)
    ids_by_quote={}
    for a in archived:
        if a.get("player_id") and a.get("quote_id"): ids_by_quote.setdefault(a["quote_id"],str(a["player_id"]))
    quote_index={r["quote_id"]:r for r in base}
    count=collections.Counter(); raw=[]; rejected=[]; frozen_files={}
    # All original quote-level models, including the obsolete smaller J original.
    for r in base:
        event=str(r.get("event_id") or "")
        if not event:count["original_missing_event"]+=1
        for mid,d in r.get("models",{}).items():
            src={"model":mid,"event":event,"player":r["player"],"player_id":ids_by_quote.get(r["quote_id"]),
                 "market":MAP.get(r["stat"]),"line":float(r["line"]),"period":"full_game",
                 "p_over":d.get("over"),"p_push":d.get("push"),"mean":d.get("mean"),
                 "forecast_at":d.get("forecast_at"),"source_file":str(COMPARE),
                 "quote_id":r["quote_id"],"is_tackle":r["stat"]=="tackles + assists"}
            raw.append(src)
    # Canonical latest v0.4.2/0.4.3 only; no mixing earlier v0.4.1 intermediate.
    for r in archived:
        if r.get("model_id") not in ("J1","J2") or r.get("status")!="FORECAST":continue
        orig=quote_index.get(r.get("quote_id"))
        if orig is None: raise RuntimeError("J_QUOTE_NOT_IN_FROZEN_UNIVERSE")
        fn=JR/(r["forecast_file_sha256"]+".json")
        if str(fn) not in frozen_files:
            source(fn,r["forecast_file_sha256"])
            obj=load(fn)
            freeze=utc(obj.get("forecast_created_at"))
            src_receipt=obj.get("source_receipts",{})
            cutoff=utc(src_receipt.get("model_training_cutoff_conservative_snapshot_at"))
            built=utc(src_receipt.get("built_at"))
            frozen_files[str(fn)]={"sha256":r["forecast_file_sha256"],"freeze":str(freeze),
                "training_cutoff":str(cutoff),"source_built_at":str(built),"payload":obj}
        meta=frozen_files[str(fn)]
        raw.append({"model":r["model_id"]+"_v04","event":str(r["event_id"]),
             "player":orig["player"],"player_id":str(r.get("player_id") or ""),
             "market":r["normalized_market"],"line":float(r["line"]),"period":r.get("period","full_game"),
             "p_over":r["p_over"],"p_push":r["p_push"],"mean":r.get("mean"),
             "forecast_at":meta["freeze"],"source_file":str(fn),
             "quote_id":r["quote_id"],"is_tackle":False,"quantiles":r.get("quantiles"),
             "team":r.get("team"),"draws_key":r.get("model_id")})
    # Read-only temporal and probability screening. No after-kickoff model accepted.
    accepted=[]; recov=collections.Counter()
    start={str(x["event_id"]):utc(x["kickoff_utc"]) for x in base if x.get("event_id") and x.get("kickoff_utc")}
    for x in raw:
        m=x["model"]
        event=x["event"]; f=utc(x.get("forecast_at")); kickoff=start.get(event)
        if not kickoff or not f or f>=kickoff:
            recov[(m,"MISSING_OR_POST_KICKOFF_FORECAST")]+=1;continue
        if m.endswith("_v04"):
            meta=frozen_files[x["source_file"]]
            cut=utc(meta["training_cutoff"]);b=utc(meta["source_built_at"])
            if cut is None or b is None or cut>b or b>f:
                recov[(m,"TRAINING_OR_INPUT_TIME_INVALID")]+=1;continue
        if x["market"] not in MAPPED:recov[(m,"UNSUPPORTED_MARKET")]+=1;continue
        p=x["p_over"];push=x["p_push"]
        if not isinstance(p,(float,int)) or not isinstance(push,(float,int)) or min(p,push,1-p-push)<-1e-7:
            recov[(m,"PROBABILITY_FAILURE")]+=1;continue
        y,st,pl=get_stat(event,x["player_id"],x["player"],x["market"],files)
        if st!="OBSERVED":
            recov[(m,st)]+=1;continue
        s=assess(float(p),float(push),y,x["line"])
        if s is None:recov[(m,"SCORE_FAILURE")]+=1;continue
        d={**x,**s,"y":y,"status":"TACKLE_PROVISIONAL" if x["is_tackle"] else "RESEARCH_ONLY",
           "player_id":pl["id"],"team":pl["team"],
           "crps":None,"intervals":{}}
        if x["model"].endswith("_v04"):
            obj=frozen_files[x["source_file"]]["payload"]
            series=obj.get("draw_records",{}).get(x["draws_key"],{}).get("series",{})
            key="|".join((x.get("team") or "",str(x["player_id"]),x["market"]))
            vals=series.get(key)
            if vals:
                vv=np.array(vals,dtype=float)
                d["crps"]=crps_sample(vv,y)
                for c in (.5,.8,.9,.95):d["intervals"][str(c)]=interval_draw(vv,y,c)[0]
                d["pit_mid"]=float(np.mean(vv<y)+.5*np.mean(vv==y))
                d["tail95_miss"]=int(y<np.quantile(vv,.025) or y>np.quantile(vv,.975))
            else: recov[(m,"DRAWS_MISSING_FOR_FORECAST")]+=1
        accepted.append(d)
    uniq,conflicts=dedup(accepted)
    if conflicts: count["inconsistent_book_repeated_contracts"]=len(conflicts)
    models=sorted(set(x["model"] for x in raw))
    summary={m:score_summary([x for x in uniq if x["model"]==m]) for m in models}
    for m in models:
        o=[x for x in raw if x["model"]==m]
        summary[m]["quote_level_forecasts"]=len(o)
        summary[m]["unique_scored"]=summary[m]["scored"]
        summary[m]["duplicate_quote_excess"]=sum(x["duplicate_quotes"] for x in uniq if x["model"]==m)
        summary[m]["exclusions"]={k[1]:v for k,v in recov.items() if k[0]==m}
        markets=sorted(set(x["market"] for x in uniq if x["model"]==m))
        summary[m]["markets"]={k:score_summary([x for x in uniq if x["model"]==m and x["market"]==k]) for k in markets}
        bands=collections.defaultdict(list)
        for x in uniq:
            if x["model"]!=m or x.get("conf") is None: continue
            conf=x["conf"];label="0.50-0.60" if conf<.6 else "0.60-0.70" if conf<.7 else "0.70-0.80" if conf<.8 else "0.80-0.90" if conf<.9 else "0.90-1.00"
            bands[label].append(x)
        summary[m]["conditional_calibration"]={k:{"n":len(v),"claimed":float(np.mean([z["conf"] for z in v])),
                                              "observed":float(np.mean([z["hit"] for z in v if z["hit"] is not None]))} for k,v in sorted(bands.items())}
    pairs={}
    for a,b in [("J1_v04","J2_v04"),("S2_original","J2_v04"),
                ("S2-ew-source-paired-hl4-v2","J2_v04"),("O5-role-mixture-full-market-v2","J2_v04"),
                ("S2_original","O5-role-mixture-full-market-v2"),("T_S4_repaired","T_J2_repaired")]:
        pairs[a+"_vs_"+b]=paired([r for r in uniq if r["model"]==a],[r for r in uniq if r["model"]==b])
    # Largest absolute pregame point/volume discrepancies on independently boxed players, distinct player/stat/model.
    errors=[];seen=set()
    for x in sorted(uniq,key=lambda z:abs((z["mean"] or 0)-z["y"]) if z["mean"] is not None else -1,reverse=True):
        if x["mean"] is None:continue
        k=(x["model"],x["event"],x["player_id"],x["market"])
        if k in seen:continue
        seen.add(k)
        errors.append({k:x.get(k) for k in ("model","event","player","player_id","team","market","mean","y","forecast_at","source_file")})
        errors[-1]["signed_error"]=x["mean"]-x["y"]
        errors[-1]["absolute_error"]=abs(x["mean"]-x["y"])
    source_manifest={"schema":"WS6_INDEPENDENT_POSTGAME_SOURCE_MANIFEST_V1",
       "original_comparison":{"path":str(COMPARE),"sha256":source(COMPARE),"rows":len(base)},
       "v04_joint_ledger":{"path":str(jpath),"sha256":source(jpath),"rows":len(archived)},
       "ws6_handoff":{"path":str(HANDOFF),"sha256":source(HANDOFF)},
       "frozen_simulations":{k:{x:y for x,y in v.items() if x!="payload"} for k,v in frozen_files.items()},
       "official":official,"date_clusters":1,"run_no_rewrite":True}
    audit={"schema":"WS6_INDEPENDENT_NOV15_V1","status":"RESEARCH_SHADOW_UNCERTIFIED",
       "original_quote_observations":len(base),"original_missing_event":count["original_missing_event"],
       "official_finals":len(files),"quote_model_rows_attempted":len(raw),
       "deduplicated_scored_model_rows":len(uniq),"n_model_score_conflicts":len(conflicts),
       "models":summary,"paired":pairs,"exclusions_per_model":{m:summary[m]["exclusions"] for m in models},
       "top25_largest_point_errors":errors[:25],
       "limitations":["Original sportsbook provider metadata unverified; not a betting settlement.",
         "ESPN tackle TOT has not been independently cross-checked with authoritative GSIS combined solo/assists.",
         "Only one game date; date-clustered interval unestimable. Game bootstrap is descriptive.",
         "Absent ESPN category/athlete never automatically assigned zero.",
         "Quote-level duplicates deduplicated for sport-event scoring.",
         "Full distribution/PIT/CRPS only when original simulation draws match player+stat."]}
    # Output immutable input hash receipt and compact reports; raw official hashes retained.
    dump(OUT/"source_manifest.json",source_manifest)
    dump(OUT/"independent_scorecard.json",audit)
    dump(OUT/"duplicate_conflicts.json",conflicts)
    fd=io.StringIO(newline="")
    w=csv.DictWriter(fd,fieldnames=list(errors[0]) if errors else ["model"])
    w.writeheader();w.writerows(errors[:25])
    frozen_write(OUT/"top25_errors.csv",fd.getvalue().encode())
    print(json.dumps({"artifacts":{p.name:h(p.read_bytes()) for p in OUT.iterdir() if p.is_file()},
      "official_final":len(files),"source_sha":source(COMPARE),"joint_sha":source(jpath),
      "scored_by_model":{m:{k:v for k,v in s.items() if k in ("scored","brier","logloss","high_conf_n","high_conf_hits","duplicate_quote_excess","quote_level_forecasts","exclusions","intervals","crps")} for m,s in summary.items()},
      "matched":pairs,"top_errors":errors[:4],"conflicts":conflicts[:3]},default=str))
if __name__=="__main__":main()
