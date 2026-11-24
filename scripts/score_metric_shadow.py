"""Score an immutable early shadow packet against original final NHL/ESPN boxes."""
import argparse
import hashlib
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path.cwd()))
from v2.official_nba_nhl_capture import normalized_team, nhl_stat_rows, nba_stat_rows


def clock():
    return datetime.now(timezone.utc)


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def write_once(path, payload):
    with path.open("xb") as file:
        file.write(payload)
        file.flush()
    if path.read_bytes() != payload:
        raise OSError("immutable_write_readback_failed")


def poisson_scores(actual, rate):
    if not math.isfinite(rate) or not 0 < rate < 250:
        raise ValueError("invalid_poisson_mean")
    if type(actual) is not int or not 0 <= actual <= 200:
        raise ValueError("invalid_box_actual")
    mass = math.exp(-rate)
    cdf = mass
    crps = 0.0
    limit = max(actual+100, int(rate+20*math.sqrt(rate)+50))
    for k in range(limit):
        crps += (cdf-int(k>=actual))**2
        mass *= rate/(k+1)
        cdf += mass
    if abs(cdf-1)>1e-12:
        raise ValueError("truncation_diagnostic")
    return crps, rate-actual*math.log(rate)+math.lgamma(actual+1)


def url_for(sport, game_id):
    if not re.fullmatch(r"\d{7,12}",game_id):
        raise ValueError("invalid_game_id")
    if sport=="NHL":
        return f"https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore"
    return f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"


def read_final(sport, path, game, freeze, already=None):
    game_id=game["game_id"]
    uri=url_for(sport,game_id)
    if already:
        raw=(already/f"{game_id}.json").read_bytes()
        transport="provided_original_body"
    else:
        request=Request(uri,headers={"User-Agent":"pickem-auditor research final archive","Accept":"application/json"})
        with urlopen(request,timeout=15) as response:
            raw=response.read(3_000_001)
        transport="fresh_official_read"
    if len(raw)>3_000_000:
        raise ValueError("source_body_too_large")
    observed=clock()
    digest=sha(raw)
    name=f"{game_id}-{digest}.json"
    write_once(path/name,raw)
    receipt={"source_url":uri,"body_sha256":digest,"path":name,"observed_at":observed.isoformat(),
             "transport":transport}
    try:
        data=json.loads(raw)
        if sport=="NHL":
            sid,start=data["id"],data["startTimeUTC"]
        else:
            comp,=data["header"]["competitions"]
            sid,start=comp["id"],comp["date"]
        if (str(sid)!=game_id or instant(start)<=freeze or instant(start)>=observed
                or abs((instant(start)-instant(game["start_at"])).total_seconds())>90*60):
            raise ValueError("official_game_or_start_mismatch")
        teams={normalized_team(game[k],sport) for k in ("home","away")}
        rows=(nhl_stat_rows if sport=="NHL" else nba_stat_rows)(data,expected_teams=teams)
        return rows,receipt
    except (ValueError,TypeError,KeyError,IndexError) as exc:
        return None,{**receipt,"failure":str(exc)[:200]}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--pregame",type=Path,required=True)
    p.add_argument("--sha256",required=True)
    p.add_argument("--sport",choices=("NHL","NBA"),required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--source-dir",type=Path)
    a=p.parse_args()
    raw=a.pregame.read_bytes()
    if sha(raw)!=a.sha256:
        p.error("pregame_packet_digest_mismatch")
    packet=json.loads(raw)
    freeze=instant(packet["freeze_at"])
    sport=packet["sports"][a.sport]
    if any(instant(g["start_at"])<=freeze for g in sport["games"]):
        p.error("pregame_freeze_invalid")
    a.out.mkdir(parents=True,exist_ok=False)
    archive=a.out/"original-finals"
    archive.mkdir()
    statuses={}; finals={}
    for g in sport["games"]:
        try:
            results,receipt=read_final(a.sport,archive,g,freeze,a.source_dir)
        except (ValueError,TypeError,KeyError,IndexError,OSError) as exc:
            results=None
            receipt={"source_url":url_for(a.sport,g["game_id"]),"failure":str(exc)[:200]}
        statuses[g["game_id"]]=receipt
        if results is not None:
            finals[g["game_id"]]=results
    key="shots on goal" if a.sport=="NHL" else "points"
    dispositions=Counter(); scored=[]; unresolved=[]
    models=None
    for row in sport["forecasts"]:
        ident={k:row[k] for k in ("game_id","player_id","team")}
        g=ident["game_id"]; product=finals.get(g,{})
        source=product.get(ident["player_id"])
        if models is None:
            models=sorted(row["poisson_means"])
        if sorted(row["poisson_means"])!=models:
            raise ValueError("unequal_model_coverage")
        if g not in finals:
            status="final_unavailable_or_rejected"
        elif source is None:
            status="no_verified_played_appearance"
        elif normalized_team(ident["team"],a.sport)!=source["team"]:
            status="player_team_mismatch"
        else:
            status="scored"
            actual=source[key]
            values={name:poisson_scores(actual,rate) for name,rate in row["poisson_means"].items()}
            scored.append({**ident,"actual":actual,"crps":{n:v[0] for n,v in values.items()},
                           "nll":{n:v[1] for n,v in values.items()}})
        dispositions[status]+=1
        if status!="scored":
            unresolved.append({**ident,"status":status})
    assert sum(dispositions.values())==len(sport["forecasts"])
    summary={"schema":"v25-metric-shadow-postgame-v1","scored_at":clock().isoformat(),
             "sport":a.sport,"pregame_sha256":a.sha256,"prefreeze_exclusions":sport["exclusions"],
             "scheduled_games":len(sport["games"]),"final_games_verified":len(finals),
             "dispositions":dict(dispositions),"game_source_receipts":statuses,"scored":scored,
             "unresolved":unresolved,"comparison_scope":"single-date descriptive paired count scores"}
    if scored:
        totals={n:{"crps":sum(r["crps"][n] for r in scored)/len(scored),
                   "nll":sum(r["nll"][n] for r in scored)/len(scored)} for n in models}
        comparisons={}
        rng=random.Random(20261124)
        games=sorted({r["game_id"] for r in scored})
        for challenger in models:
            if challenger=="baseline":
                continue
            clusters=defaultdict(list)
            for r in scored:
                clusters[r["game_id"]].append(r["crps"][challenger]-r["crps"]["baseline"])
            boot=[]
            if len(games)>1:
                for _ in range(2000):
                    draw=rng.choices(games,k=len(games))
                    boot.append(sum(sum(clusters[g]) for g in draw)/sum(len(clusters[g]) for g in draw))
                boot.sort()
            comparisons[challenger]={"delta_crps":totals[challenger]["crps"]-totals["baseline"]["crps"],
                "game_cluster_descriptive_95":[boot[50],boot[1949]] if boot else None}
        summary.update({"scores":totals,"paired_vs_baseline":comparisons})
    payload=(json.dumps(summary,sort_keys=True,indent=2)+"\n").encode()
    write_once(a.out/"settlement.json",payload)
    print(json.dumps({"sport":a.sport,"sha256":sha(payload),"saved":str(a.out/"settlement.json"),
                      "final":len(finals),"attempted":len(sport["forecasts"]),"dispositions":dict(dispositions),
                      "paired":summary.get("paired_vs_baseline",{})},sort_keys=True))


if __name__=="__main__":
    main()
