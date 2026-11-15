"""WS4 research-only NFL shared-game simulation, v0.1 (2026-11-14).

No collection, training, sportsbook retrieval, ranking, betting or production changes.
An unmatched or uncertified real source manifest must ABSTAIN, never be fabricated.
All scenario parameters are source-side pregame inputs; synthetic examples are tests only.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
import time
from collections import Counter, defaultdict
from typing import Any
import numpy as np

SCHEMA = "PA_WS4_JOINT_INPUT_v1"
VERSION = "ws4_j1234_v0.3.1"
COUNT_STATS = {"pass_attempts", "completions", "passing_tds", "qb_rushing_attempts",
               "carries", "targets", "receptions", "receiving_tds", "rushing_tds",
               "solo_tackles", "tackle_assists", "tackles_assists"}
YARD_STATS = {"passing_yards", "qb_rushing_yards", "rushing_yards", "receiving_yards"}
STATS = COUNT_STATS | YARD_STATS
SUPPORTED_PERIODS = {"full_game_including_overtime", "full_game"}
SCENARIOS = {
    "neutral": (0.0, 0.0, 0.50),
    "pass_heavy_underdog": (0.24, 0.10, 0.20),
    "run_heavy_favorite": (-0.20, 0.03, 0.20),
    "low_tempo": (0.0, -0.16, 0.10),
}

class ContractError(ValueError):
    pass


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def sha(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def utc(value: str) -> dt.datetime:
    if not isinstance(value, str) or not (value.endswith("Z") or "+" in value[10:] or "-" in value[10:]):
        raise ContractError("TIMESTAMP_NOT_TIMEZONE_AWARE")
    try:
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if t.tzinfo is None or t.utcoffset() is None:
            raise ValueError("naive")
        return t.astimezone(dt.timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ContractError("INVALID_TIME") from exc


def prob(p: Any, field: str) -> float:
    if not isinstance(p, (float, int)) or not math.isfinite(p) or not (0 <= p <= 1):
        raise ContractError("INVALID_PROBABILITY:" + field)
    return float(p)


def positive(x: Any, field: str, allow_zero: bool = False) -> float:
    if not isinstance(x, (float, int)) or not math.isfinite(x) or x < 0 or (x == 0 and not allow_zero):
        raise ContractError("INVALID_PARAMETER:" + field)
    return float(x)


def validate(payload: dict) -> tuple[str, dt.datetime]:
    if payload.get("schema") != SCHEMA:
        raise ContractError("UNRECOGNIZED_CANONICAL_ADAPTER_SCHEMA")
    fixture = payload.get("synthetic_fixture") is True
    if not fixture and payload.get("source_certification_status") not in ("CERTIFIED", "SOURCE_CERTIFIED_RESEARCH_SHADOW"):
        raise ContractError("SOURCE_MANIFEST_NOT_CERTIFIED")
    freeze = utc(payload["input_freeze_at"])
    train = utc(payload["model_training_cutoff_at"])
    if train > freeze: raise ContractError("POST_FREEZE_MODEL_TRAINING")
    if not fixture and not payload.get("input_manifest_sha256"):
        raise ContractError("MISSING_IMMUTABLE_INPUT_SHA")
    if not isinstance(payload.get("events"), list) or not payload["events"]:
        raise ContractError("MISSING_EVENT_UNIVERSE")
    if not isinstance(payload.get("contracts"), list):
        raise ContractError("MISSING_EXACT_CONTRACT_UNIVERSE")
    event_by_id = {}
    team_seen = set()
    for event in payload["events"]:
        eid = event.get("event_id")
        if not eid or eid in event_by_id: raise ContractError("DUPLICATE_OR_MISSING_EVENT_ID")
        start = utc(event["event_start_at"])
        if freeze >= start: raise ContractError("POST_KICKOFF_FREEZE")
        if not fixture:
            if not event.get("scenario_source_receipts"):
                raise ContractError("SCENARIO_SOURCE_RECEIPTS_MISSING")
            for receipt in event["scenario_source_receipts"]:
                if not receipt.get("source_uri") or not receipt.get("sha256") or len(receipt["sha256"]) != 64:
                    raise ContractError("SCENARIO_SOURCE_RECEIPTS_MISSING")
                if utc(receipt["available_at"]) > freeze:
                    raise ContractError("POST_FREEZE_SCENARIO_SOURCE")
            if not event.get("source_receipts"):
                raise ContractError("SOURCE_RECEIPT_MISSING")
            for receipt in event["source_receipts"]:
                if not receipt.get("source_uri") or not receipt.get("sha256") or len(receipt["sha256"]) != 64:
                    raise ContractError("SOURCE_RECEIPT_MISSING")
                if utc(receipt["available_at"]) > freeze:
                    raise ContractError("POST_FREEZE_SOURCE")
        teams = event.get("teams")
        if not isinstance(teams, list) or len(teams) != 2:
            raise ContractError("NOT_TWO_TEAMS")
        ids = [t.get("team_id") for t in teams]
        if not all(ids) or len(set(ids)) != 2: raise ContractError("INVALID_TEAM_IDENTITY")
        players = set()
        for team in teams:
            positive(team["plays_mean"], "plays_mean")
            prob(team["pass_rate"], "pass_rate")
            prob(team.get("sack_rate", .065), "sack_rate")
            if team["pass_rate"] + team.get("sack_rate", .065) >= 1:
                raise ContractError("PASS_PLUS_SACK_EXCEEDS_ONE")
            if not isinstance(team.get("players"), list): raise ContractError("PLAYER_UNIVERSE_MISSING")
            qb = team.get("starter_qb_id")
            for pl in team["players"]:
                pid = pl.get("player_id")
                if not pid or pid in players: raise ContractError("PLAYER_ID_COLLISION")
                players.add(pid)
                if pl.get("role") not in ("QB", "RB", "RECEIVER", "DEFENDER"):
                    raise ContractError("UNSUPPORTED_ROLE")
                prob(pl.get("participation", 1.0), "participation")
                if pl["role"] in ("RB", "RECEIVER", "DEFENDER"):
                    positive(pl.get("share", 0), "share", allow_zero=True)
                if pl["role"] == "DEFENDER": prob(pl.get("snap_share", 0.8), "snap_share")
            starters = [p for p in team["players"] if p["role"] == "QB" and p["player_id"] == qb]
            if qb and (len(starters) != 1 or not (team.get("starter_status") == "CONFIRMED_PREGAME" or (payload.get("source_certification_status") == "SOURCE_CERTIFIED_RESEARCH_SHADOW" and team.get("starter_status") == "EXPECTED_STARTER_SOURCE_BACKED" and team.get("starter_source_receipts")))):
                raise ContractError("UNVERIFIED_STARTER")
            if not fixture and not qb: raise ContractError("STARTER_IDENTITY_MISSING")
            team_seen.add((eid, team["team_id"]))
        event_by_id[eid] = event
    seen_contracts = set()
    for c in payload["contracts"]:
        cid = c.get("contract_id")
        if not cid or cid in seen_contracts: raise ContractError("DUPLICATE_OR_MISSING_CONTRACT_ID")
        seen_contracts.add(cid)
        if c.get("event_id") not in event_by_id: raise ContractError("CONTRACT_EVENT_MISMATCH")
        if (c.get("event_id"), c.get("team_id")) not in team_seen:
            raise ContractError("CONTRACT_TEAM_MISMATCH")
        if not isinstance(c.get("line"), (int, float)) or not math.isfinite(c["line"]):
            raise ContractError("INVALID_ORIGINAL_LINE")
        if not isinstance(c.get("original_quote_id"), str) or not c["original_quote_id"]:
            raise ContractError("ORIGINAL_OFFER_ID_MISSING")
        if not fixture:
            if utc(c["original_quote_at"]) > freeze: raise ContractError("POST_FREEZE_QUOTE")
            if not c.get("original_quote_receipt_sha256") or len(c["original_quote_receipt_sha256"]) != 64:
                raise ContractError("QUOTE_RECEIPT_MISSING")
    if not fixture:
        for event in payload["events"]:
            for team in event["teams"]:
                prob(team.get("starter_attempt_share"), "starter_attempt_share")
    return ("SYNTHETIC_FIXTURE" if fixture else ("UNCERTIFIED_SHADOW" if payload.get("source_certification_status") == "SOURCE_CERTIFIED_RESEARCH_SHADOW" else "CERTIFIED_SHADOW")), freeze


def pick_index(rng: np.random.Generator, items: list[dict], field: str, selected: dict, j2: bool,
               cache: dict | None = None, tag: str = "") -> int:
    """A residual category always competes; no player can exceed the team pool."""
    if cache is not None and tag in cache:
        weights = cache[tag]
    else:
        weights = np.array([p.get(field, 0) * selected.get(p["player_id"], 1) for p in items] + [1.0], dtype=float)
        if j2:
            # One draw per GAME (not per play) induces compositional overdispersion.
            concentration = 28.0
            weights = rng.gamma(np.maximum(weights * concentration, 1e-7), 1.0)
        weights = weights / weights.sum()
        if cache is not None: cache[tag] = weights
    return int(rng.choice(len(weights), p=weights))


def marked_yards(rng: np.random.Generator, mean: float, sd: float, j2: bool,
                 lower: float, upper: float) -> int:
    z = float(rng.standard_t(5) * math.sqrt(3 / 5)) if j2 else float(rng.standard_normal())
    return int(round(np.clip(mean + sd * z, lower, upper)))


def game_once(event: dict, rng: np.random.Generator, model: str, script: str) -> tuple[dict, dict]:
    j2 = model in ("J2", "J3")
    pass_shift, pace_shift, _ = SCENARIOS[script]
    zpace = float(rng.normal())
    zscript = float(rng.normal())
    outputs = defaultdict(int)
    state: dict[str, dict] = {}
    selected_by_team = {}
    snap_probability_by_team = {}
    # Source-supplied event-level team states, shared game pace + opposing game script.
    for i, team in enumerate(event["teams"]):
        side = 1 if i == 0 else -1
        plays_mean = team["plays_mean"] * math.exp(pace_shift + .085 * zpace)
        if j2:
            # Mean-one Gamma multiplicative uncertainty; no mean shift relative to J1.
            plays_mean *= float(rng.gamma(shape=25.0, scale=1 / 25.0))
        plays = int(rng.poisson(plays_mean))
        # Do not clip outcomes; upper tails are genuine, unlike a finite cap misdescribed as physical.
        base_pass = float(team["pass_rate"])
        logit = math.log(max(1e-5, base_pass) / max(1e-5, 1-base_pass))
        role=team.get("pregame_game_role","UNKNOWN")
        effective_pass_shift=pass_shift
        if script=="pass_heavy_underdog":
            effective_pass_shift=pass_shift if role=="UNDERDOG" else -0.04
        elif script=="run_heavy_favorite":
            effective_pass_shift=pass_shift if role=="FAVORITE" else 0.05
        ppass_raw = 1/(1+math.exp(-(logit + effective_pass_shift + side*.12*zscript)))
        sack = float(team.get("sack_rate", .065))
        ppass = ppass_raw * (1-sack)
        counts = rng.multinomial(plays, [ppass, sack, 1-ppass-sack])
        pass_attempts, sacks, rush_attempts = map(int, counts)
        state[team["team_id"]] = dict(plays=plays, pass_attempts=pass_attempts,
                                      sacks=sacks, rush_attempts=rush_attempts,
                                      receivers={}, backs={}, defense={})
        players=team["players"]
        selected={}
        for p in players:
            active_probability = float(p.get("participation", 1.0))
            selected[p["player_id"]] = int(rng.random() < active_probability) if j2 else (1 if active_probability == 1 else int(rng.random() < active_probability))
        selected_by_team[team["team_id"]] = selected
        game_snap = {}
        for p in players:
            if p["role"] == "DEFENDER":
                q=float(p.get("snap_share",.8))
                game_snap[p["player_id"]] = float(rng.beta(max(.01,q*35),max(.01,(1-q)*35))) if j2 else q
        snap_probability_by_team[team["team_id"]] = game_snap
        game_alloc = {}
        game_catch_rates={}
        receivers=[p for p in players if p["role"] in ("RECEIVER", "RB")]
        backs=[p for p in players if p["role"] == "RB"]
        for recv in receivers:
            rate=prob(recv.get("catch_rate",.66),"catch_rate")
            game_catch_rates[recv["player_id"]] = float(rng.beta(max(.01,rate*35),max(.01,(1-rate)*35))) if j2 else rate
        unassigned_rate=prob(team.get("unassigned_catch_rate",.40),"unassigned_catch_rate")
        game_catch_rates["UNASSIGNED"] = float(rng.beta(max(.01,unassigned_rate*35),max(.01,(1-unassigned_rate)*35))) if j2 else unassigned_rate
        qb_id=team.get("starter_qb_id")
        if qb_id and selected.get(qb_id,0):
            # No unsupported QB exit-risk assumptions: supplied conditional probability only.
            exit_p=float(team.get("qb_verified_exit_probability",0)) if j2 else 0.0
            prob(exit_p,"qb_verified_exit_probability")
            starter_fraction=float(rng.beta(3,5)) if j2 and rng.random()<exit_p else 1.0
            qb_attempts=int(rng.binomial(pass_attempts,float(team.get("starter_attempt_share", 1.0))*starter_fraction))
        else:
            qb_attempts=0
        # Two QB origin classes ensure starter comps/yards/TD <= team totals.
        receptions_per_player=defaultdict(int)
        for qb_origin,natt in ((("STARTER",qb_attempts),("RELIEF",pass_attempts-qb_attempts)) if receivers else ()):
            for _ in range(natt):
                idx=pick_index(rng,receivers,"share",selected,j2,game_alloc,"receivers")
                chosen = receivers[idx] if idx < len(receivers) else None
                if chosen:
                    pid=chosen["player_id"]
                    outputs[(pid,"targets")]+=1
                    state[team["team_id"]]["receivers"].setdefault(pid,{"targets":0,"receptions":0})["targets"]+=1
                    rate=game_catch_rates[pid]
                else:
                    pid=None
                    rate=game_catch_rates["UNASSIGNED"]
                if rng.random()<rate:
                    if pid:
                        outputs[(pid,"receptions")]+=1
                        receptions_per_player[pid]+=1
                        state[team["team_id"]]["receivers"][pid]["receptions"]+=1
                        m=float(chosen.get("yards_per_catch",9.5))
                        sd=positive(chosen.get("yards_sd",8),"yards_sd")
                        td_rate=prob(chosen.get("td_per_catch",.07),"td_per_catch")
                    else:
                        m=float(team.get("unassigned_ypc",6))
                        sd=8.0; td_rate=.045
                    yards=marked_yards(rng,m,sd,j2,-20,100)
                    td=int(rng.random()<td_rate)
                    if pid:
                        outputs[(pid,"receiving_yards")]+=yards
                        outputs[(pid,"receiving_tds")]+=td
                    if qb_origin=="STARTER" and qb_id:
                        outputs[(qb_id,"completions")]+=1
                        outputs[(qb_id,"passing_yards")]+=yards
                        outputs[(qb_id,"passing_tds")]+=td
        if qb_id: outputs[(qb_id,"pass_attempts")]+=qb_attempts
        # All rushing-play carry allocation is one categorical draw, not independent player counts.
        rush_items=backs+([next(p for p in players if p["player_id"]==qb_id)] if qb_id else [])
        for _ in range(rush_attempts if any(float(p.get("rush_share",0))>0 for p in rush_items) else 0):
            idx=pick_index(rng,rush_items,"rush_share",selected,j2,game_alloc,"rushers")
            chosen=rush_items[idx] if idx<len(rush_items) else None
            if chosen:
                pid=chosen["player_id"]
                stat="qb_rushing_attempts" if chosen["role"]=="QB" else "carries"
                ystat="qb_rushing_yards" if chosen["role"]=="QB" else "rushing_yards"
                outputs[(pid,stat)]+=1
                yards=marked_yards(rng,float(chosen.get("yards_per_carry",4.2)),
                                   positive(chosen.get("rush_yards_sd",5.2),"rush_yards_sd"),j2,-15,90)
                outputs[(pid,ystat)]+=yards
                outputs[(pid,"rushing_tds")]+=int(rng.random()<prob(chosen.get("rush_td_rate",.025),"rush_td_rate"))
                r=state[team["team_id"]]["backs"].setdefault(pid,{"carries":0})
                r["carries"]+=1
        state[team["team_id"]]["starter_qb_attempts"]=qb_attempts
    # Defensive opportunities depend on OPPONENT generated plays and defensive participation.
    for i, team in enumerate(event["teams"]):
        other=event["teams"][1-i]
        opp=state[other["team_id"]]
        defenders=[p for p in team["players"] if p["role"]=="DEFENDER"]
        # Preserve anonymous defensive opportunities without inventing a tackle-credit rate.
        if not defenders:
            continue
        for _ in range(opp["plays"]):
            is_pass=rng.random()<opp["pass_attempts"]/max(opp["plays"],1)
            # Non-tackled passing incompletions and out-of-bounds remain plausible.
            tackle_rate=(.65 if is_pass else .88)
            if rng.random()>tackle_rate:continue
            available=[];weights=[]
            for p in defenders:
                if selected_by_team[team["team_id"]].get(p["player_id"],0) and rng.random()<snap_probability_by_team[team["team_id"]][p["player_id"]]:
                    available.append(p)
                    weights.append(float(p.get("share",0)))
            # Anonymous defender absorbs missing roster and unknown credited players.
            weights.append(1.0)
            norm=np.array(weights,dtype=float)
            norm/=norm.sum()
            solo=rng.random()<.75
            if solo:
                chosen=int(rng.choice(len(norm),p=norm))
                if chosen<len(available):
                    pid=available[chosen]["player_id"]
                    outputs[(pid,"solo_tackles")]+=1
                    outputs[(pid,"tackles_assists")]+=1
            else:
                # Two distinct assist credits; never solo+assist to a defender on the same play.
                count=min(2,len(available)+1)
                chosen=rng.choice(len(norm),size=count,replace=False,p=norm)
                for ix in chosen:
                    if ix<len(available):
                        pid=available[ix]["player_id"]
                        outputs[(pid,"tackle_assists")]+=1
                        outputs[(pid,"tackles_assists")]+=1
    return dict(outputs),state


def sample_event(event:dict, model:str, n:int, frozen_id:str, scenario:str|None=None) -> tuple[list[dict],list[dict]]:
    if model not in ("J1","J2","J3"):raise ContractError("MODEL_UNKNOWN")
    if not 1<=n<=4096:raise ContractError("SIMULATION_COUNT_OUT_OF_BOUNDS")
    seed=int(hashlib.sha256((frozen_id+"|"+event["event_id"]+"|"+model+"|"+VERSION).encode()).hexdigest()[:16],16)
    rng=np.random.default_rng(seed)
    samples=[];states=[]
    scenarios=list(SCENARIOS)
    weights=np.array([SCENARIOS[s][2] for s in scenarios],dtype=float)
    for _ in range(n):
        sc=(rng.choice(scenarios,p=weights) if model=="J3" else (scenario or "neutral"))
        if sc not in SCENARIOS:raise ContractError("SCENARIO_UNKNOWN")
        s,st=game_once(event,rng,model,sc)
        samples.append(s);states.append(st)
    return samples,states


def describe(arr:np.ndarray,line:float,stat:str) -> dict:
    p_over=float(np.mean(arr>line));p_under=float(np.mean(arr<line));p_push=float(np.mean(arr==line))
    if not np.isclose(p_over+p_under+p_push,1.0,atol=1e-12):
        raise ContractError("BROKEN_COMPLEMENTARITY")
    distribution = None
    if stat in COUNT_STATS:
        support, observed = np.unique(arr.astype(np.int64), return_counts=True)
        distribution = {str(int(v)): float(n/len(arr)) for v,n in zip(support,observed)}
    return {"p_over":p_over,"p_under":p_under,"p_push":p_push,
            "pmf":distribution, "mean":float(np.mean(arr)),"variance":float(np.var(arr)),
            "q05":float(np.quantile(arr,.05)),"q50":float(np.quantile(arr,.50)),
            "q95":float(np.quantile(arr,.95)),"zero_rate":float(np.mean(arr==0)),
            "mc_se_over":float(math.sqrt(p_over*(1-p_over)/len(arr))),
            "mc_se_under":float(math.sqrt(p_under*(1-p_under)/len(arr))),
            "draws":len(arr),"line":line,"stat":stat}


def run_manifest(manifest:dict,draws:int=512, models:tuple[str,...]=("J1","J2","J3")) -> dict:
    status,freeze=validate(manifest)
    if status != "SYNTHETIC_FIXTURE" and any(dt.datetime.now(dt.timezone.utc) >= utc(e["event_start_at"]) for e in manifest["events"]):
        raise ContractError("PREDICTION_CREATED_AFTER_KICKOFF")
    frozen_id=manifest.get("input_manifest_sha256") or sha(manifest)
    events={e["event_id"]:e for e in manifest["events"]}
    available=defaultdict(list)
    for c in manifest["contracts"]:available[c["event_id"]].append(c)
    results=[];diagnostics=[];counts=Counter()
    for event_id,event in events.items():
        teams={t["team_id"]:t for t in event["teams"]}
        players={p["player_id"]:(p,t) for t in event["teams"] for p in t["players"]}
        for model in models:
            samples,states=sample_event(event,model,draws,frozen_id)
            # Every simulation, including omitted/nonoffered players, gets structural checks.
            for s,st in zip(samples,states):
                for t in event["teams"]:
                    x=st[t["team_id"]]
                    assert x["plays"]==x["pass_attempts"]+x["sacks"]+x["rush_attempts"]
                    assert sum(v["targets"] for v in x["receivers"].values())<=x["pass_attempts"]
                    assert sum(v["receptions"] for v in x["receivers"].values())<=x["pass_attempts"]
                    assert all(v["receptions"]<=v["targets"] for v in x["receivers"].values())
                    assert sum(v["carries"] for v in x["backs"].values())<=x["rush_attempts"]
                    assert x["starter_qb_attempts"]<=x["pass_attempts"]
                for (pid,stat),v in s.items():
                    assert stat not in COUNT_STATS or (v>=0 and int(v)==v)
                for pid,(p,_) in players.items():
                    assert s.get((pid,"tackles_assists"),0)==s.get((pid,"solo_tackles"),0)+s.get((pid,"tackle_assists"),0)
            conditionals = {}
            if model == "J3":
                for script in SCENARIOS:
                    scenario_draws=max(64,draws//4)
                    cond,_=sample_event(event,"J2",scenario_draws,frozen_id+"|conditional|"+script,script)
                    conditionals[script]=cond
            for c in available[event_id]:
                player=players.get(c["player_id"])
                reason=None
                if not player:reason="PLAYER_NOT_IN_FROZEN_ROSTER"
                elif player[1]["team_id"]!=c["team_id"]:reason="CONTRACT_PLAYER_TEAM_MISMATCH"
                elif c.get("stat_key") not in STATS:reason="UNSUPPORTED_STAT"
                elif c.get("period") not in SUPPORTED_PERIODS:reason="UNSUPPORTED_PERIOD"
                elif player[0]["role"]=="QB" and player[0]["player_id"]!=player[1].get("starter_qb_id"):
                    reason="BACKUP_QB_INELIGIBLE"
                elif player[0]["role"]=="QB" and player[1].get("starter_status")!="CONFIRMED_PREGAME" and not (status=="UNCERTIFIED_SHADOW" and player[1].get("starter_status")=="EXPECTED_STARTER_SOURCE_BACKED"):
                    reason="QB_STARTER_UNCONFIRMED"
                elif c["stat_key"].startswith("qb_") and player[0]["role"]!="QB":reason="STAT_ROLE_MISMATCH"
                elif c["stat_key"] in ("pass_attempts","passing_yards","passing_tds","completions") and player[0]["role"]!="QB":reason="STAT_ROLE_MISMATCH"
                elif c["stat_key"] in ("solo_tackles","tackle_assists","tackles_assists") and player[0]["role"]!="DEFENDER":reason="STAT_ROLE_MISMATCH"
                elif c["stat_key"] in ("targets","receptions","receiving_yards","receiving_tds") and player[0]["role"] not in ("RECEIVER", "RB"):reason="STAT_ROLE_MISMATCH"
                elif c["stat_key"] == "carries" and player[0]["role"]!="RB":reason="STAT_ROLE_MISMATCH"
                elif c["stat_key"] == "rushing_yards" and player[0]["role"]!="RB":reason="STAT_ROLE_MISMATCH"
                # Original quote and period identity are retained unmodified.
                row={k:c.get(k) for k in ("contract_id","original_quote_id","original_quote_at","original_quote_receipt_sha256",
                                          "event_id","team_id","player_id","stat_key","period","line")}
                row.update(model_id=model,model_version=VERSION,input_id=frozen_id,
                           input_freeze_at=manifest["input_freeze_at"],classification=status,
                           source_certification_status=manifest.get("source_certification_status","SYNTHETIC"),
                           seed_key=frozen_id+"|"+event_id+"|"+model+"|"+VERSION)
                if reason:
                    row.update(status="ABSTAIN",reason=reason)
                    counts[reason]+=1
                else:
                    vals=np.array([s.get((c["player_id"],c["stat_key"]),0) for s in samples],dtype=float)
                    row.update(status="FORECAST",**describe(vals,float(c["line"]),c["stat_key"]))
                    if model == "J3":
                        row["scenario_conditional"]={k:describe(np.asarray([s.get((c["player_id"],c["stat_key"]),0)
                                                for s in sample],dtype=float),float(c["line"]),c["stat_key"])
                                                for k,sample in conditionals.items()}
                    counts["FORECAST"]+=1
                results.append(row)
            # J4 dependence diagnostic from shared-state outcomes. Independent product is null.
            pairs=[]
            qs=[p for p,t in players.values() if p["role"]=="QB" and t["team_id"] in teams]
            for qb in qs:
                t=next(t for t in event["teams"] if t["starter_qb_id"]==qb["player_id"])
                for recv in [p for p in t["players"] if p["role"]=="RECEIVER"][:3]:
                    a=np.array([s.get((qb["player_id"],"pass_attempts"),0) for s in samples],dtype=float)
                    b=np.array([s.get((recv["player_id"],"targets"),0) for s in samples],dtype=float)
                    corr=float(np.corrcoef(a,b)[0,1]) if np.std(a)>0 and np.std(b)>0 else None
                    pairs.append({"type":"QB_ATTEMPTS_WR_TARGETS","a":qb["player_id"],"b":recv["player_id"],"corr":corr})
            for team in event["teams"]:
                tid=team["team_id"]
                backs=[p for p in team["players"] if p["role"]=="RB"]
                receivers=[p for p in team["players"] if p["role"]=="RECEIVER"]
                defenders=[p for p in team["players"] if p["role"]=="DEFENDER"]
                opponent=next(t for t in event["teams"] if t["team_id"]!=tid)
                paired=[("RB_CARRIES_TEAM_PASS",[(p["player_id"],"carries"),(tid,"_TEAM_PASS")]) for p in backs]
                paired += [("OPP_PLAYS_DEFENDER_TACKLES",[(opponent["team_id"],"_TEAM_PLAYS"),(p["player_id"],"tackles_assists")]) for p in defenders]
                if len(receivers)>=2:
                    paired.append(("RECEIVER_TARGET_COMPETITION",[(receivers[0]["player_id"],"targets"),(receivers[1]["player_id"],"targets")]))
                if receivers:
                    paired.append(("QB_COMPLETIONS_RECEIVER_CATCHES",[(team["starter_qb_id"],"completions"),(receivers[0]["player_id"],"receptions")]))
                for family,((a,sa),(b,sb)) in paired:
                    def series(person,stat):
                        if stat=="_TEAM_PASS":return np.asarray([st[person]["pass_attempts"] for st in states],dtype=float)
                        if stat=="_TEAM_PLAYS":return np.asarray([st[person]["plays"] for st in states],dtype=float)
                        return np.asarray([s.get((person,stat),0) for s in samples],dtype=float)
                    va,vb=series(a,sa),series(b,sb)
                    corr=float(np.corrcoef(va,vb)[0,1]) if va.std()>0 and vb.std()>0 else None
                    pairs.append(dict(type=family,a=a,a_stat=sa,b=b,b_stat=sb,corr=corr))
            diagnostics.append(dict(event_id=event_id,model_id=model,draws=draws,dependence_pairs=pairs,
                                    status="OUTCOME_BLIND_NOT_VALIDATED"))
    output={"schema":"PA_WS4_SHADOW_OUTPUT_v1","model_version":VERSION,
            "classification":status,"source_input_sha256":frozen_id,
            "freeze":manifest["input_freeze_at"],"generated_by":"joint_simulator.py",
            "scenarios":{k:{"pass_logit_offset":v[0],"pace_log_offset":v[1],"weight":v[2]} for k,v in SCENARIOS.items()},
            "denominators":dict(counts),"contracts":results,"dependence_diagnostics":diagnostics,
            "warning":"Unvalidated research candidate; no production picks or profitability claims."}
    output["forecast_created_at"]=dt.datetime.now(dt.timezone.utc).isoformat()
    if status != "SYNTHETIC_FIXTURE" and any(utc(output["forecast_created_at"]) >= utc(e["event_start_at"]) for e in manifest["events"]):
        raise ContractError("FORECAST_FINISHED_AFTER_KICKOFF")
    output["original_period_policy"]="original_full_game_retained_product_specific_settlement_unverified"
    output["output_sha256"]=sha(output)
    return output


def atomic_new_json(path:pathlib.Path,obj:dict)->None:
    # No overwrite or retroactive mutation. A second run must choose a new versioned path.
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as fh:
        json.dump(obj,fh,sort_keys=True,indent=2,allow_nan=False)
        fh.write("\n")


def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True,type=pathlib.Path)
    ap.add_argument("--output",required=True,type=pathlib.Path)
    ap.add_argument("--draws",type=int,default=512)
    a=ap.parse_args()
    raw=a.input.read_bytes();data=json.loads(raw)
    started=time.perf_counter();out=run_manifest(data,a.draws)
    out["runtime_seconds_unrounded"]=time.perf_counter()-started
    out["raw_input_file_sha256"]=hashlib.sha256(raw).hexdigest()
    out["output_sha256"]=sha({k:v for k,v in out.items() if k!="output_sha256"})
    atomic_new_json(a.output,out)
    print(json.dumps({"classification":out["classification"],"source_input_sha256":out["source_input_sha256"],
                      "output_sha256":out["output_sha256"],"denominators":out["denominators"],
                      "runtime_seconds":out["runtime_seconds_unrounded"]},sort_keys=True))

if __name__=="__main__":main()