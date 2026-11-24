"""Score two frozen NBA count distributions against the original shadow finals."""
import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,str(Path.cwd()))
from scripts.score_metric_shadow import instant, poisson_scores, write_once
from v2.official_nba_nhl_capture import nba_stat_rows, normalized_team


def read_verified(path, expected):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError("artifact_digest_mismatch:"+str(path.name))
    return json.loads(raw)


def probability_scores(actual, mean, r=None, components=None):
    if type(actual) is not int or not 0<=actual<=200:
        raise ValueError("invalid_official_points")
    if not math.isfinite(mean) or not 0<mean<250:
        raise ValueError("invalid_forecast_mean")
    if (r is None)==(components is None):
        raise ValueError("ambiguous_count_distribution")
    if r is not None:
        if not math.isfinite(r) or not r>0:
            raise ValueError("invalid_NB2_size")
        p=r/(r+mean)
        pmf=[math.exp(r*math.log(p))]
    else:
        if not all(math.isfinite(x) and x>=0 for x in components):
            raise ValueError("invalid_compound_rates")
        if not math.isclose(sum(k*v for k,v in enumerate(components,1)),mean,rel_tol=1e-12):
            raise ValueError("compound_mean_mismatch")
        pmf=[math.exp(-sum(components))]
    cdf=pmf[0]
    score=(cdf-int(actual==0))**2
    for k in range(1,8192):
        if r is not None:
            pmf.append(pmf[-1]*(k+r-1)/k*(1-p))
        else:
            pmf.append(sum(j*components[j-1]*pmf[k-j] for j in range(1,min(k,3)+1))/k)
        cdf+=pmf[-1]
        score+=(cdf-int(actual<=k))**2
        if k>=actual and abs(cdf-1)<1e-12:
            return score,-math.log(max(pmf[actual],1e-300))
    raise ValueError("unresolved_PMF_tail")


def key(row):
    return row["game_id"],row["team"],row["player_id"]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--companion",type=Path,required=True)
    parser.add_argument("--companion-sha",required=True)
    parser.add_argument("--parent",type=Path,required=True)
    parser.add_argument("--settlement",type=Path,required=True)
    parser.add_argument("--settlement-sha",required=True)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    companion=read_verified(a.companion,a.companion_sha)
    parent_sha=companion["parent_pregame_sha256"]
    parent=read_verified(a.parent,parent_sha)["sports"]["NBA"]
    final=read_verified(a.settlement,a.settlement_sha)
    if final["sport"]!="NBA" or final["pregame_sha256"]!=parent_sha:
        raise ValueError("settlement_parent_mismatch")
    original={key(r):r for r in parent["forecasts"]}
    if len(original)!=len(parent["forecasts"]):
        raise ValueError("duplicate_original_forecast")
    games={g["game_id"]:g for g in parent["games"]}
    boxes={}
    for r in final["scored"]:
        g=r["game_id"]
        if g in boxes:
            continue
        receipt=final["game_source_receipts"][g]
        source=a.settlement.parent/"original-finals"/Path(receipt["path"]).name
        body=read_verified(source,receipt["body_sha256"])
        comp,=body["header"]["competitions"]
        if str(comp["id"])!=g or not instant(comp["date"])>instant(companion["freeze_at"]):
            raise ValueError("source_game_or_clock_mismatch")
        boxes[g]=nba_stat_rows(body,expected_teams={normalized_team(games[g][s],"NBA") for s in ("home","away")})
    grades={key(r):r for r in final["scored"]}
    unresolved={key(r):r["status"] for r in final["unresolved"]}
    if (grades.keys() & unresolved.keys() or grades.keys() | unresolved.keys() != original.keys()
            or len(grades)+len(unresolved)!=len(final["scored"])+len(final["unresolved"])):
        raise ValueError("parent_denominator_mismatch")
    scores=[]; dispositions=Counter(); seen=set()
    for row in companion["forecasts"]:
        identity=key(row)
        if identity in seen or identity not in original:
            raise ValueError("companion_identity_mismatch")
        seen.add(identity)
        if row["start_at"]!=original[identity]["start_at"] or instant(row["start_at"])<=instant(companion["freeze_at"]):
            raise ValueError("companion_freeze_invalid")
        mean=row["eFG_mean"]
        if mean!=original[identity]["poisson_means"]["actual_eFG_pct"]:
            raise ValueError("parent_efg_mean_mismatch")
        if identity in unresolved:
            dispositions[unresolved[identity]]+=1;continue
        game,team,player=identity
        actual=grades[identity]["actual"]
        original_player=boxes[game].get(player)
        if original_player is None or original_player["team"]!=normalized_team(team,"NBA") or original_player["points"]!=actual:
            raise ValueError("official_actual_mismatch")
        components=[row["compound_made_rates"][n] for n in ("free_throws","twos","threes")]
        z={"efg_poisson":poisson_scores(actual,mean),
           "efg_NB2":probability_scores(actual,mean,r=row["NB2_size"]),
           "efg_compound":probability_scores(actual,mean,components=components)}
        scores.append({"game_id":game,"team":team,"player_id":player,"actual":actual,"scores":z})
        dispositions["scored"]+=1
    assert sum(dispositions.values())==len(companion["forecasts"])
    results={}
    if scores:
        for model in scores[0]["scores"]:
            d={metric:sum(r["scores"][model][i] for r in scores)/len(scores)
                    for i,metric in enumerate(("crps","log_loss"))}
            results[model]=d
    report={"schema":"v25-nba-shadow-distribution-final-v1","scored_at":datetime.now(timezone.utc).isoformat(),
         "pregame_sha256":a.companion_sha,"parent_sha256":parent_sha,"original_settlement_sha256":a.settlement_sha,
         "dispositions":dict(dispositions),"coverage_exclusions":companion["exclusions"],
         "summary":results,"match_evidence":scores,"scope":"Single-date descriptive paired scores"}
    payload=(json.dumps(report,indent=2,sort_keys=True)+"\n").encode()
    write_once(a.out,payload)
    print(json.dumps({"path":str(a.out),"sha256":hashlib.sha256(payload).hexdigest(),
                      "dispositions":dict(dispositions),"summary":results},sort_keys=True))


if __name__=="__main__":
    main()
