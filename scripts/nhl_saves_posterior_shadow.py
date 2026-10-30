#!/usr/bin/env python3
"""Read-only prospective NHL goalie saves posterior sidecar.

Never modifies historical snapshots, market odds, the A/B blend or tier ranks.
Only uses the frozen convergence-approved release and verified pregame contexts.
Missing identity, time, venue, opponent, or source provenance -> unavailable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
TORONTO=ZoneInfo("America/Toronto")
VERSION="nhl-full-saves-posterior-shadow-v1"
EXPECTED_SHA={
    "posterior.nc":"d64c87f8c48b735545aee291525b6f041e5320b1da931d724c4ecbbd7283adc9",
    "manifest.json":"434f63a56ddecc1de316da62d58cc677cf74ed3412870ee96934e7989464db9b",
    "model_receipt.json":"0b0c9998a4c521439721302d0da49f269f07ac0f2201f67149c9690c27442a75"
}
TAG="research-nhl-saves-20261029-run40993538888"


class ModelUnavailable(ValueError): pass


def stamp(value):
    try:
        result=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if result.tzinfo is None: raise ValueError("timezone required")
        return result.astimezone(timezone.utc)
    except (TypeError,ValueError,OverflowError) as exc:
        raise ModelUnavailable("invalid_or_missing_event_timestamp") from exc


def ice_season(day):
    """NHL season starts in the second half of each calendar year."""
    return day.year if day.month>=7 else day.year-1


def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda:file.read(1024*1024),b""): h.update(block)
    return h.hexdigest()


def load_model(folder):
    folder=Path(folder)
    for name,sha in EXPECTED_SHA.items():
        path=folder/name
        if not path.is_file() or digest(path)!=sha:
            raise ModelUnavailable("unverified_release_asset:"+name)
    m=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    r=json.loads((folder/"model_receipt.json").read_text(encoding="utf-8"))
    d=m.get("diagnostics") or {}
    checks=(
        r.get("schema")=="precision_nhl_model_receipt_v1",
        r.get("status")=="converged",
        r.get("stat")=="saves",
        m.get("schema")=="multisport_joint_fit_manifest_v1",
        m.get("model_version")=="multisport-joint-bayes-v1",
        m.get("sport")=="NHL" and m.get("stat")=="saves" and m.get("family")=="count",
        m.get("max_per_position")==0,
        m.get("diagnosed_all_player_and_opponent_effects") is True,
        m.get("sampler_chains")==4 and m.get("sampler_retained_draws_per_chain")==2000,
        m.get("training_cutoff_exclusive")=="2026-10-29",
        r.get("as_of_exclusive")=="2026-10-29",
        d.get("posterior_sampling_ok") is True,
        isinstance(d.get("max_rhat"),(int,float)) and math.isfinite(d["max_rhat"]) and d["max_rhat"]<=1.01,
        isinstance(d.get("min_bulk_ess"),(int,float)) and math.isfinite(d["min_bulk_ess"]) and d["min_bulk_ess"]>=400,
        d.get("divergences")==0,
        isinstance(d.get("minimum_bfmi"),(int,float)) and math.isfinite(d["minimum_bfmi"]) and d["minimum_bfmi"]>=.30,
        len(m.get("players",[]))>=12 and bool(m.get("source_digest")),
        len(m.get("seasons",[]))>=2 and bool(m.get("last_game")),
    )
    if not all(checks):
        raise ModelUnavailable("release_manifest_failed_strict_convergence_or_provenance")
    return m


def identity(row):
    return tuple(str(row.get(k)) for k in
        ("game_date","sport","player_id","stat","side","reference_line","forecast_at","run_id"))


def validate_candidate(row, manifest, now):
    if row.get("run_type")!="shadow" or row.get("sport")!="NHL" or row.get("stat")!="saves":
        raise ModelUnavailable("not_an_nhl_saves_shadow_snapshot")
    at=stamp(row.get("forecast_at"))
    start=stamp(row.get("event_start"))
    day=date.fromisoformat(row["game_date"])
    if not at<start or not now<start or at.astimezone(TORONTO).date()!=day:
        raise ModelUnavailable("poststart_or_crossdate_forecast")
    cutoff=date.fromisoformat(manifest["training_cutoff_exclusive"])
    last=date.fromisoformat(manifest["last_game"])
    if day<cutoff or last>=day:
        raise ModelUnavailable("training_window_overlaps_slate_date")
    if ice_season(day)!=ice_season(last):
        raise ModelUnavailable("future_season_requires_new_frozen_fit")
    season=manifest["seasons"][-1]
    # A hockey season rollover must never silently use an old season effect.
    if not isinstance(season,str) or not season:
        raise ModelUnavailable("missing_historical_season_identity")
    player=str(row.get("player_id") or "").strip()
    opponent=str(row.get("opponent") or "").strip()
    team=str(row.get("team") or "").strip()
    if not player or player not in manifest["players"]:
        raise ModelUnavailable("player_identity_not_in_frozen_posterior")
    if not opponent or opponent not in manifest["opponents"]:
        raise ModelUnavailable("opponent_identity_not_in_frozen_posterior")
    if not team or team==opponent:
        raise ModelUnavailable("missing_or_invalid_team_identity")
    if row.get("matchup_orientation_verified") is not True:
        raise ModelUnavailable("unverified_venue_orientation")
    home_team=str(row.get("home_team") or "").strip()
    away_team=str(row.get("away_team") or "").strip()
    if not home_team or not away_team or home_team==away_team:
        raise ModelUnavailable("missing_verified_home_away")
    # Source owns venue orientation. No heuristics from a matchup string.
    if {team.casefold(),opponent.casefold()}!={home_team.casefold(),away_team.casefold()}:
        raise ModelUnavailable("venue_team_pair_mismatch")
    side=str(row.get("side") or "").strip().lower()
    if side not in ("over","under","higher","lower"):
        raise ModelUnavailable("unsupported_market_side")
    line=row.get("reference_line")
    if isinstance(line,bool) or not isinstance(line,(int,float)) or not math.isfinite(line) or line<0:
        raise ModelUnavailable("invalid_saves_market_line")
    if not row.get("run_id"):
        raise ModelUnavailable("missing_source_snapshot_run_id")
    return dict(player_id=player,opponent=opponent,season=season,
                home=team.casefold()==home_team.casefold(),line=float(line),side=side)


def evaluate(row, *, manifest, posterior, cache, now):
    meta={k:row.get(k) for k in (
        "game_date","forecast_at","event_start","sport","player","player_id",
        "stat","side","reference_line","run_id","team","opponent")}
    out={**meta,"engine":"nhl_full_population_saves",
         "version":VERSION,"release_tag":TAG,"model_source_digest":manifest.get("source_digest"),
         "status":"unavailable","publication_eligible":False,"ranking_allowed":False,
         "calibrated":False,"shadow_only":True,
         "generated_at":now.isoformat()}
    try:
        args=validate_candidate(row,manifest,now)
        from joint_population_bayes import forecast
        seed=int.from_bytes(hashlib.sha256(
            json.dumps(identity(row),separators=(",",":"),allow_nan=False).encode()).digest()[:8],"big")
        design={k:manifest[k] for k in (
            "sport","stat","family","players","positions","seasons","opponents",
            "player_position","source_digest","last_game")}
        q=forecast(posterior,design,
            player_id=args["player_id"],opponent=args["opponent"],
            season=args["season"],home=args["home"],line=args["line"],
            seed=seed,draws=1500,diagnostic=manifest["diagnostics"],cache=cache)
        qwin=q["q_over"] if args["side"] in ("over","higher") else q["q_under"]
        out.update(status="forecast",q_over=q["q_over"],q_under=q["q_under"],
                   q_push=q["q_push"],q_win=qwin,
                   numerical_mc_se=q["numerical_mc_se"],
                   conditional_on_appearance=True,
                   trained_through=manifest["last_game"],
                   model_eligible_for_rank=False)
    except (ModelUnavailable,KeyError,TypeError,ValueError,OverflowError) as exc:
        out["reason"]=str(exc) if isinstance(exc,ModelUnavailable) else type(exc).__name__
    return out


def run(*, snapshots, model_dir, game_date, out, receipt, now=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None: raise ValueError("timezone required")
    source=Path(snapshots)
    if not source.is_file(): raise ModelUnavailable("missing_daily_slate_snapshots")
    rows=[]
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        x=json.loads(line)
        if x.get("game_date")==game_date and x.get("sport")=="NHL" and x.get("stat")=="saves" and x.get("run_type")=="shadow":
            rows.append(x)
    # Preserve earlier prospective results on an afternoon retry. We never
    # recompute or rewrite an already stamped model forecast for the same slate.
    if len({identity(x) for x in rows})!=len(rows):
        raise ModelUnavailable("duplicate_saves_shadow_snapshot_identity")
    op=Path(out)
    retained=[]
    seen=set()
    if op.is_file():
        for line in op.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                raise ModelUnavailable("invalid_existing_saves_shadow_sidecar")
            r=json.loads(line)
            key=identity(r)
            if (r.get("version")!=VERSION or r.get("release_tag")!=TAG
                or r.get("game_date")!=game_date
                or r.get("publication_eligible") is not False
                or r.get("ranking_allowed") is not False
                or key in seen):
                raise ModelUnavailable("invalid_or_mutated_saves_shadow_sidecar")
            seen.add(key)
            retained.append(r)
    manifest=load_model(model_dir)
    import arviz as az
    from joint_population_bayes import posterior_cache
    posterior=az.from_netcdf(str(Path(model_dir)/"posterior.nc"))
    if posterior.posterior.sizes.get("chain")!=4 or posterior.posterior.sizes.get("draw")!=2000:
        raise ModelUnavailable("wrong_posterior_chain_or_draw_count")
    cache=posterior_cache(posterior)
    added=[evaluate(x,manifest=manifest,posterior=posterior,cache=cache,now=now)
           for x in rows if identity(x) not in seen]
    results=sorted(retained+added,key=lambda x:identity(x))
    rp=Path(receipt)
    op.parent.mkdir(parents=True,exist_ok=True);rp.parent.mkdir(parents=True,exist_ok=True)
    # Keep exact previously recorded JSON values, with an atomic replacement.
    output="".join(json.dumps(r,sort_keys=True,allow_nan=False)+"\n" for r in results)
    tmp=op.with_suffix(".tmp")
    tmp.write_text(output,encoding="utf-8")
    tmp.replace(op)
    reasons=Counter(r.get("reason") for r in results if r["status"]!="forecast")
    report={
        "schema":"nhl_saves_joint_posterior_daily_shadow_v1",
        "date":game_date,"release_tag":TAG,"source_digest":manifest["source_digest"],
        "snapshot_candidates":len(rows),"previously_recorded":len(retained),
        "new_rows":len(added),"total_rows":len(results),
        "forecast_count":sum(r["status"]=="forecast" for r in results),
        "unavailable_count":len(reasons) and sum(reasons.values()) or 0,
        "reasons":dict(reasons),"publication_eligible":False,
        "ranking_allowed":False,"production_snapshot_unchanged":True,
        "model_convergence_passed":True
    }
    rp.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("NHL_SAVES_SHADOW "+json.dumps(report,sort_keys=True),flush=True)
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshots",type=Path,required=True)
    p.add_argument("--model-dir",type=Path,required=True)
    p.add_argument("--date",required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--receipt",type=Path,required=True)
    a=p.parse_args(argv)
    date.fromisoformat(a.date)
    try:
        run(snapshots=a.snapshots,model_dir=a.model_dir,game_date=a.date,
            out=a.out,receipt=a.receipt)
    except Exception as exc:
        rp=a.receipt;rp.parent.mkdir(parents=True,exist_ok=True)
        rp.write_text(json.dumps({
            "schema":"nhl_saves_joint_posterior_daily_shadow_v1",
            "date":a.date,"release_tag":TAG,
            "status":"unavailable","error":f"{type(exc).__name__}:{exc}"[:300],
            "publication_eligible":False,"ranking_allowed":False,
            "production_snapshot_unchanged":True},sort_keys=True,indent=2)+"\n",encoding="utf-8")
        print("NHL_SAVES_SHADOW_FAILED "+type(exc).__name__+": "+str(exc)[:250],flush=True)
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
