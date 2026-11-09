"""NFL tackles + assists snap-share challenger (shadow, never a production blend).

Decompose predicted credited tackles into opposing offensive plays, player
defensive snap share, and tackles credited per player snap. Fit only
pre-event records; no opponent-specific out-of-sample outcome leaks.
Teammate conditioning requires archived source-receipted *pregame statuses*
for both historical games and the upcoming game; never infer absence from
a missing player-stat row. Empirical alpha/dispersion is NOT tuned here.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import json
import math
import random

from point_in_time_provenance import instant, verified_source_receipt, ProvenanceError

VERSION="nfl-tackle-snap-share-shadow-v1"
STATS="tackles + assists"
POSITIONS=frozenset({"LB","MLB","OLB","ILB","DE","DT","NT","CB","DB","S","FS","SS"})
ALPHA=8.0                       # fixed research dispersion, not learned
MAX_GAMES=12
POSITION_PSEUDO_GAMES=3.0
RATE_PSEUDO_SNAPS=120.0
MIN_POSITION_GAMES=25
MIN_PLAYER_GAMES=3
MIN_CONTRAST_GAMES=3


class TackleChallengerError(ValueError):
    pass


def positive(value, label, *, zero=False):
    if type(value) not in (float,int) or not math.isfinite(value) or (value<0 if zero else value<=0):
        raise TackleChallengerError("invalid_"+label)
    return float(value)


def parse_stamp(value,label):
    try:
        return instant(value,label)
    except (ProvenanceError,TypeError,ValueError) as exc:
        raise TackleChallengerError("invalid_"+label) from exc


def normalize_bundles(bundles):
    """Use the *existing* nfl_context_data.normalize output, not a new name join.

    PBP opposing offensive scrimmage plays supply the denominator; the
    conservative population_nfl unique-week/player snap join supplies defense
    snaps and actual T+A. Always mark start+18h source timing as approximate.
    """
    out=[];seen=set();quality=Counter()
    games={};sources=set()
    if not isinstance(bundles,(list,tuple)) or not bundles:
        raise TackleChallengerError("missing_normalized_source_bundles")
    for bundle in bundles:
        if (not isinstance(bundle,dict)
                or bundle.get("schema")!="nfl-context-data-v1"
                or bundle.get("availability_policy")!="retrospective_start_plus_18h"
                or not isinstance(bundle.get("source_digest"),str)):
            raise TackleChallengerError("unsupported_historical_source_or_timing")
        sources.add(bundle["source_digest"])
        for teamrow in bundle.get("teams") or ():
            key=(str(teamrow.get("game_id")),str(teamrow.get("team")))
            if key in games:raise TackleChallengerError("duplicate_team_game_source")
            games[key]=teamrow
    for bundle in bundles:
        for p in bundle.get("players") or ():
            if p.get("stat")!=STATS or p.get("position") not in POSITIONS:
                continue
            quality["candidate_defender_game_rows"]+=1
            game=str(p.get("game_id"));team=str(p.get("team"));opponent=str(p.get("opponent"))
            key=(game,str(p.get("player_id")))
            if key in seen:raise TackleChallengerError("duplicate_defender_game")
            seen.add(key)
            offense=games.get((game,opponent))
            own=games.get((game,team))
            if (not offense or not own or offense.get("opponent")!=team
                    or own.get("opponent")!=opponent):
                raise TackleChallengerError("missing_opponent_pbp_exposure")
            try:
                before=parse_stamp(p.get("start_time"),"game_start")
                available=parse_stamp(p.get("available_at"),"history_available")
                if not before<available:raise TackleChallengerError("nonfuture_history_availability")
                snaps=positive(p.get("workload"),"player_defense_snaps")
                plays=positive(offense.get("plays"),"team_defense_plays")
                actual=positive(p.get("value"),"tackles_assists",zero=True)
            except (TypeError,ValueError) as exc:
                raise TackleChallengerError("invalid_snap_or_tackle_measurement") from exc
            # PBP and PFR team denominators can differ by nullified plays;
            # never silently cap the player's participation to 100%.
            if snaps>plays:
                quality["excluded_snap_count_exceeds_pbp_team_plays"]+=1
                continue
            if actual>snaps:
                quality["excluded_tackles_exceed_on_field_snaps"]+=1
                continue
            quality["accepted_defender_game_rows"]+=1
            out.append(dict(game_id=game,player_id=str(p["player_id"]),
                            team=team,opponent=opponent,position=str(p["position"]),
                            start_time=before.isoformat(),available_at=available.isoformat(),
                            team_defensive_plays=plays,player_defensive_snaps=snaps,
                            tackles_assists=actual,source_digest=bundle["source_digest"]))
    if not out:
        raise TackleChallengerError("no_valid_defensive_snap_rows")
    return {"schema":VERSION,"rows":sorted(out,key=lambda r:(r["start_time"],r["game_id"],r["player_id"])),
            "history_source_digests":sorted(sources),
            "time_provenance":"retrospective_game_plus_18h_not_immutable_provider_capture",
            "source_quality_counts":dict(quality),
            "production_eligible":False}


def verified_status(report, *, forecast_at, game_id, team, teammate_id, archive_root):
    """Authenticate source bytes + status identity; never infer inactive from missing."""
    if not isinstance(report,dict) or report.get("status") not in ("active","inactive"):
        raise TackleChallengerError("missing_explicit_teammate_status")
    if (str(report.get("game_id"))!=str(game_id)
            or str(report.get("team"))!=str(team)
            or str(report.get("teammate_id"))!=str(teammate_id)):
        raise TackleChallengerError("teammate_status_contract_mismatch")
    when=parse_stamp(forecast_at,"teammate_forecast_at")
    try:
        source_id=verified_source_receipt(report.get("source_receipt"),forecast=when,
                                          archive_root=Path(archive_root) if archive_root is not None else None)
    except (ProvenanceError,ValueError,TypeError) as exc:
        raise TackleChallengerError("uncertified_teammate_status_receipt") from exc
    # The immutable source bytes must also contain the *same* asserted
    # athlete/game/status fields. A checked SHA of unrelated text cannot
    # authorize an arbitrary injury/roster claim.
    try:
        receipt=report["source_receipt"]
        archive=(Path(archive_root)/receipt["archive_path"]).resolve()
        raw=json.loads(archive.read_text(encoding="utf-8"))
        if (raw.get("schema")!="verified-nfl-teammate-status-v1"
                or str(raw.get("game_id"))!=str(game_id)
                or str(raw.get("team"))!=str(team)
                or str(raw.get("teammate_id"))!=str(teammate_id)
                or raw.get("status")!=report["status"]
                or parse_stamp(raw.get("event_start"),"archived_teammate_event_start")!=
                   parse_stamp(report.get("event_start"),"reported_teammate_event_start")):
            raise TackleChallengerError("archived_teammate_status_identity_mismatch")
    except TackleChallengerError:
        raise
    except (OSError,UnicodeError,ValueError,TypeError,KeyError) as exc:
        raise TackleChallengerError("archived_teammate_status_unreadable_or_mismatched") from exc
    return report["status"],source_id


def conditional_statuses(reports, *, teammate_id, team, archive_root, game_starts):
    """Collect explicit historical statuses authenticated before each *game*.

    The source must have been published and retrieved before its game start.
    A snapless teammate, absent boxscore, or postgame retrospective page
    cannot be used to impute inactive status.
    """
    if not reports:return {}
    if not isinstance(reports,list):raise TackleChallengerError("bad_historical_teammate_reports")
    result={}
    for item in reports:
        if str(item.get("teammate_id"))!=str(teammate_id) or str(item.get("team"))!=str(team):
            raise TackleChallengerError("historical_teammate_identity_mismatch")
        gid=str(item.get("game_id"))
        # Reports outside the last-twelve input window are not model
        # features; their contents must not influence this projection.
        if gid not in game_starts:
            continue
        if gid in result:raise TackleChallengerError("duplicate_historical_teammate_report")
        # Reject asserted availability timed against a different or fictitious
        # kickoff for this exact archived team/player game.
        if gid not in game_starts or parse_stamp(item.get("event_start"),"historical_teammate_start") != parse_stamp(
                game_starts[gid],"historical_real_start"):
            raise TackleChallengerError("historical_teammate_event_time_mismatch")
        pregame=(parse_stamp(game_starts[gid],"historical_real_start")-timedelta(seconds=1)).isoformat()
        state,_=verified_status(item,forecast_at=pregame,
                 game_id=gid,team=team,teammate_id=teammate_id,archive_root=archive_root)
        result[gid]=state
    return result


def score_probability(mean, line, *, alpha=ALPHA):
    """Coherent NB mass for a credited-tackle count, using a FIXED alpha."""
    mu=positive(mean,"count_mean",zero=True)
    dispersion=positive(alpha,"count_dispersion")
    if type(line) not in (int,float) or not math.isfinite(line) or line<0:
        raise TackleChallengerError("invalid_tackle_line")
    k=int(math.floor(line))
    p=dispersion/(dispersion+mu)
    first=p**dispersion
    pmf=first
    lower=pmf
    for i in range(1,k+1):
        pmf*=((i-1+dispersion)/i)*(1-p)
        lower+=pmf
    lower=max(0.,min(1.,lower))
    push=pmf if float(line).is_integer() else 0.
    under=max(0.,lower-push)
    over=max(0.,1.-lower)
    # Report the probability on the same conditional nonpush scale as the
    # production comparison; preserve the unconditioned pushes separately.
    return {"q_over":over,"q_under":under,"q_push":push,
            "p_over_no_push":over/(1-push) if push<1 else None,
            "p_under_no_push":under/(1-push) if push<1 else None,
            "alpha_fixed":dispersion,"distribution":"negative_binomial_fixed_alpha_research"}



def index_research_history(history):
    """Prepare chronological **in-memory only** prefixes for fast OOS scoring.

    Sorting keys are actual source availability instants, not final game
    results or the holdout target. All queries cut the prefix at forecast_at.
    The index must be constructed after the source rows are frozen.
    """
    if history.get("schema")!=VERSION:
        raise TackleChallengerError("invalid_challenger_history")
    grouped=defaultdict(list)
    for row in history["rows"]:
        grouped[("player",row["team"],row["player_id"])].append(row)
        grouped[("position",row["position"])].append(row)
        grouped[("position_player",row["position"],row["player_id"])].append(row)
    index={}
    for key,rows in grouped.items():
        chronological=sorted(rows,key=lambda r:(
            parse_stamp(r["available_at"],"indexed_available"),
            r["start_time"],r["game_id"],r["player_id"]))
        timestamps=[];sums={"share":[0.0],"credits":[0.0],"snaps":[0.0]}
        for row in chronological:
            timestamps.append(parse_stamp(row["available_at"],"indexed_available"))
            sums["share"].append(sums["share"][-1]+
                     row["player_defensive_snaps"]/row["team_defensive_plays"])
            sums["credits"].append(sums["credits"][-1]+row["tackles_assists"])
            sums["snaps"].append(sums["snaps"][-1]+row["player_defensive_snaps"])
        index[key]={"rows":chronological,"times":timestamps,"sums":sums}
    return {**history,"_index":index}


def indexed_prior(index,key,when):
    bucket=index.get(key)
    if not bucket:return [],(0,0.,0.,0.)
    n=bisect_right(bucket["times"],when)
    data=bucket["sums"]
    return bucket["rows"][:n],(n,data["share"][n],data["credits"][n],data["snaps"][n])


def predict(history, *, player_id,team,forecast_at,event_start,
            expected_defensive_plays,line,game_id=None,
            teammate_id=None,teammate_report=None,
            historical_teammate_reports=None,archive_root=None):
    """Predict from *only* prior available games. Always research-only."""
    if not isinstance(history,dict) or history.get("schema")!=VERSION:
        raise TackleChallengerError("invalid_challenger_history")
    now=parse_stamp(forecast_at,"forecast_at")
    start=parse_stamp(event_start,"event_start")
    if not now<start:raise TackleChallengerError("late_or_invalid_forecast")
    volume=positive(expected_defensive_plays,"expected_defensive_plays")
    if volume>120:raise TackleChallengerError("implausible_expected_defensive_plays")
    indexed=history.get("_index")
    if indexed is None:
        selected=[r for r in history["rows"] if str(r["player_id"])==str(player_id)
                  and r["team"]==team and parse_stamp(r["start_time"],"history_start")<start
                  and parse_stamp(r["available_at"],"history_available")<=now]
    else:
        selected,_=indexed_prior(indexed,("player",team,str(player_id)),now)
        if any(parse_stamp(r["start_time"],"history_start")>=start for r in selected):
            raise TackleChallengerError("indexed_future_game_leak")
    selected.sort(key=lambda r:(r["start_time"],r["game_id"]))
    selected=selected[-MAX_GAMES:]
    if len({r["game_id"] for r in selected})!=len(selected):
        raise TackleChallengerError("duplicate_player_game_in_history")
    if len(selected)<MIN_PLAYER_GAMES:
        return {"schema":VERSION,"status":"abstain","reason":"insufficient_prior_player_games",
                "player_games":len(selected),"production_eligible":False,
                "ranking_allowed":False}
    positions=Counter(r["position"] for r in selected)
    position=positions.most_common(1)[0][0]
    if indexed is None:
        pool=[r for r in history["rows"] if r["player_id"]!=str(player_id)
              and r["position"]==position and
              parse_stamp(r["start_time"],"history_start")<start
              and parse_stamp(r["available_at"],"history_available")<=now]
        pool_games=len(pool)
        prior_share_numerator=sum(r["player_defensive_snaps"]/r["team_defensive_plays"] for r in pool)
        prior_credit_numerator=sum(r["tackles_assists"] for r in pool)
        prior_snap_denominator=sum(r["player_defensive_snaps"] for r in pool)
    else:
        _,full=indexed_prior(indexed,("position",position),now)
        _,own=indexed_prior(indexed,("position_player",position,str(player_id)),now)
        pool_games=full[0]-own[0]
        prior_share_numerator=full[1]-own[1]
        prior_credit_numerator=full[2]-own[2]
        prior_snap_denominator=full[3]-own[3]
    reasons=[]
    if pool_games<MIN_POSITION_GAMES:
        reasons.append("sparse_position_prior")
        prior_share=sum(r["player_defensive_snaps"]/r["team_defensive_plays"] for r in selected)/len(selected)
        prior_rate=sum(r["tackles_assists"] for r in selected)/sum(r["player_defensive_snaps"] for r in selected)
        share_prior_games=0.0
        rate_prior_snaps=0.0
    else:
        prior_share=prior_share_numerator/pool_games
        prior_rate=prior_credit_numerator/prior_snap_denominator
        share_prior_games=POSITION_PSEUDO_GAMES
        rate_prior_snaps=RATE_PSEUDO_SNAPS
    # Recency weights are set before outcomes, not tuned on the heldout games.
    weights=[2.**(-(len(selected)-1-i)/4.0) for i in range(len(selected))]
    wsum=sum(weights)
    observed_share=sum(w*r["player_defensive_snaps"]/r["team_defensive_plays"]
                       for w,r in zip(weights,selected))
    share=(share_prior_games*prior_share+observed_share)/(share_prior_games+wsum)
    weighted_snaps=sum(w*r["player_defensive_snaps"] for w,r in zip(weights,selected))
    weighted_credits=sum(w*r["tackles_assists"] for w,r in zip(weights,selected))
    rate=(rate_prior_snaps*prior_rate+weighted_credits)/(rate_prior_snaps+weighted_snaps)
    base_share=share
    teammate_effect=None
    if teammate_id is not None or teammate_report is not None or historical_teammate_reports:
        if teammate_id is None or str(teammate_id)==str(player_id):
            raise TackleChallengerError("missing_or_self_teammate_id")
        # Explicit future game ID is required when teammate is included.
        if not isinstance(teammate_report,dict):
            reasons.append("future_teammate_status_unverified")
        else:
            gid=teammate_report.get("game_id")
            if not gid or not game_id or str(gid)!=str(game_id):
                raise TackleChallengerError("future_teammate_game_id_missing_or_mismatched")
            if parse_stamp(teammate_report.get("event_start"),"teammate_future_event_start")!=start:
                raise TackleChallengerError("future_teammate_event_time_mismatch")
            state,receipt=verified_status(teammate_report,forecast_at=now.isoformat(),
                game_id=gid,team=team,teammate_id=teammate_id,archive_root=archive_root)
            historical=conditional_statuses(historical_teammate_reports,
                teammate_id=teammate_id,team=team,archive_root=archive_root,
                game_starts={r["game_id"]:r["start_time"] for r in selected})
            by={k:[] for k in ("active","inactive")}
            for w,row in zip(weights,selected):
                status=historical.get(str(row["game_id"]))
                if status in by:
                    by[status].append((w,row["player_defensive_snaps"]/row["team_defensive_plays"]))
            if any(len(by[k])<MIN_CONTRAST_GAMES for k in by):
                reasons.append("insufficient_confirmed_teammate_contrast")
            else:
                def weighted_mean(a):
                    return sum(w*s for w,s in a)/sum(w for w,_ in a)
                active=weighted_mean(by["active"])
                inactive=weighted_mean(by["inactive"])
                both=by["active"]+by["inactive"]
                mixture=weighted_mean(both)
                # The effect contrasts historical conditional *snap share*,
                # and is partially pooled. It is NOT an automatic injury
                # bonus, nor may it be applied again by Engine B.
                shrink=min(.60,min(len(by["active"]),len(by["inactive"]))/
                           (min(len(by["active"]),len(by["inactive"]))+4.))
                raw=(inactive if state=="inactive" else active)-mixture
                shift=max(-.20,min(.20,shrink*raw))
                share=max(0.0,min(1.0,share+shift))
                teammate_effect={"teammate_id":str(teammate_id),
                                 "confirmed_status":state,"source_id":receipt,
                                 "effect_on_snap_share":shift,
                                 "historical_active_games":len(by["active"]),
                                 "historical_inactive_games":len(by["inactive"]),
                                 "method":"sourced_conditional_share_partial_pool_not_causal"}
    expected_snaps=volume*share
    expected_tackles=expected_snaps*rate
    baseline_rate=sum(w*r["tackles_assists"] for w,r in zip(weights,selected))/sum(
        w*r["team_defensive_plays"] for w,r in zip(weights,selected))
    baseline=volume*baseline_rate
    var=sum(w*((r["player_defensive_snaps"]/r["team_defensive_plays"])-base_share)**2
            for w,r in zip(weights,selected))/wsum
    share_stdev=math.sqrt(max(0.,var))
    relative_se_lower=math.sqrt(
        (share_stdev/max(share,1e-6)/math.sqrt(len(selected)))**2
        +1/max(1.,sum(r["tackles_assists"] for r in selected)))
    distribution=score_probability(expected_tackles,line)
    if len(selected)<6:reasons.append("few_recent_defender_games")
    if teammate_effect is None and teammate_id is not None:
        reasons.append("teammate_availability_not_applied")
    return {"schema":VERSION,"status":"research_forecast",
            "forecast_at":now.isoformat(),"event_start":start.isoformat(),
            "player_id":str(player_id),"team":team,"position":position,
            "player_games":len(selected),"source_timing":history.get("time_provenance"),
            "projection_components":{
                "expected_team_defensive_plays":volume,
                "estimated_defensive_snap_share":share,
                "base_defensive_snap_share":base_share,
                "estimated_player_defensive_snaps":expected_snaps,
                "estimated_credited_tackles_per_snap":rate,
                "expected_tackles_assists":expected_tackles,
                "team_play_rate_control_expected_tackles":baseline,
                "share_observed_sd":share_stdev,
                "conditional_teammate_effect":teammate_effect,
                "conditional_teammate_status_requires_archived_evidence":True},
            "statistical_support":{"position_peer_games":pool_games,
                 "prior_player_game_ids":[r["game_id"] for r in selected],
                 "source_history_digests":history.get("history_source_digests",[]),
                 "relative_se_lower_bound_excludes_game_volume_error":relative_se_lower,
                 "dispersion":"fixed_alpha_8_unvalidated"},
            **distribution,
            "reliability_reasons":sorted(set(reasons)),
            "model_family":"snap_share_times_per_snap_conversion",
            "training_started":False,"production_eligible":False,
            "ranking_allowed":False,
            "limitations":[
                "Historical prior data uses a retrospective start+18h lag, not immutable provider publication receipts",
                "Expected defensive play volume is externally supplied and has unquantified uncertainty",
                "Population, role and dispersion estimates are uncalibrated research-only hypotheses",
                "No missing teammate game is assumed to be inactive"]}


def walk_forward(history, *, from_time, line=5.5, max_rows=10000):
    """Research-only chronological fixed-line baseline comparison.

    The future player's outcome and actual team plays are used only to
    settle the prediction, never to set expected game volume.
    Fixed 5.5 is NOT an archived sportsbook line.
    """
    boundary=parse_stamp(from_time,"holdout_begin")
    history=index_research_history(history)
    allrows=history["rows"]
    done=[];skipped=Counter();seen=set()
    # Team offense history is indexed by opponent: the offense's plays
    # from games in which these defenders faced them are retrospectively
    # observed but never from the heldout game itself.
    own_team=defaultdict(list)
    for r in allrows:
        own_team[r["team"]].append(r)
    for target in sorted(allrows,key=lambda r:(r["start_time"],r["game_id"],r["player_id"])):
        now=parse_stamp(target["start_time"],"game_start")
        if now<boundary:continue
        key=(target["game_id"],target["player_id"])
        if key in seen:raise TackleChallengerError("duplicate_backtest_player_game")
        seen.add(key)
        # The pregame opponent offensive-play-volume forecast needs its
        # own historical offensive dataset; use a neutral, predeclared
        # 65-play scenario rather than the heldout team's actual plays.
        prediction=predict(history,player_id=target["player_id"],team=target["team"],
            game_id=target["game_id"],
            forecast_at=(now-timedelta(hours=2)).isoformat(),
            event_start=now.isoformat(),
            expected_defensive_plays=65.,line=line)
        # The forecast date must be strictly before kickoff. Do not
        # fall back to choosing the observed target event play total.
        if prediction.get("status")!="research_forecast":
            skipped[prediction.get("reason","missing")]+=1
            continue
        # Actual on-field volume and conversion are appended ONLY after
        # the pregame forecast has been computed. They are explanatory
        # postgame diagnostics, not model inputs.
        done.append({"game_id":target["game_id"],"date":now.date().isoformat(),
            "stat":STATS,"actual":target["tackles_assists"],
            "actual_player_defensive_snaps":target["player_defensive_snaps"],
            "actual_team_defensive_plays":target["team_defensive_plays"],
            "actual_snap_share":target["player_defensive_snaps"]/target["team_defensive_plays"],
            "actual_tackles_per_snap":target["tackles_assists"]/target["player_defensive_snaps"],
            "q_over":prediction["q_over"],
            "q_under":prediction["q_under"],
            "baseline":score_probability(
                prediction["projection_components"]["team_play_rate_control_expected_tackles"],line),
            "forecast":prediction})
        if len(done)>=max_rows:break
    return {"schema":"nfl-tackle-walk-forward-research-v1","line":line,
            "line_source":"fixed_5_5_synthetic_research_not_market",
            "n":len(done),"rows":done,"excluded":dict(skipped),
            "training_started":False,"production_eligible":False}



def summarize_walk_forward(report, *, seed=20261108, bootstraps=500):
    """Evaluate the same *fixed synthetic line* on matched holdout outcomes.

    A repeated team/game contributes multiple correlated defenders, so
    resampling occurs at the date level, never by independent prop row.
    Chronological replay based on a retrospective +18h availability
    approximation cannot establish point-in-time provider validity.
    """
    if report.get("schema")!="nfl-tackle-walk-forward-research-v1":
        raise TackleChallengerError("invalid_walk_forward_source")
    valid=[]
    for r in report.get("rows",[]):
        actual=positive(r.get("actual"),"holdout_actual",zero=True)
        line=positive(report.get("line"),"walk_forward_line",zero=True)
        if actual==line:
            continue
        p=r["q_over"];b=r["baseline"]["q_over"]
        if not (type(p) in (int,float) and type(b) in (int,float)
                and math.isfinite(p) and math.isfinite(b) and
                0<=p<=1 and 0<=b<=1):
            raise TackleChallengerError("invalid_walk_forward_probabilities")
        y=int(actual>line)
        valid.append((str(r["date"]),p,b,y))
    if not valid:
        return {"n":0,"status":"no_valid_holdout"}
    def calculate(xs):
        n=len(xs)
        def log_loss(p,y):
            p=min(1-1e-12,max(1e-12,p))
            return -y*math.log(p)-(1-y)*math.log1p(-p)
        mean_brier_chal=sum((p-y)**2 for _date,p,b,y in xs)/n
        mean_brier_base=sum((b-y)**2 for _date,p,b,y in xs)/n
        mean_log_chal=sum(log_loss(p,y) for _date,p,b,y in xs)/n
        mean_log_base=sum(log_loss(b,y) for _date,p,b,y in xs)/n
        return {"n":n,"brier_challenger":mean_brier_chal,
                "brier_team_play_control":mean_brier_base,
                "brier_delta_challenger_minus_control":mean_brier_chal-mean_brier_base,
                "logloss_challenger":mean_log_chal,
                "logloss_team_play_control":mean_log_base,
                "logloss_delta_challenger_minus_control":mean_log_chal-mean_log_base}
    scored=calculate(valid)
    clusters=defaultdict(list)
    for row in valid:clusters[row[0]].append(row)
    dates=sorted(clusters)
    interval=None
    status="insufficient_independent_dates_for_promotion"
    if len(dates)>=20 and len(valid)>=100:
        rng=random.Random(seed)
        draws={"brier":[],"logloss":[]}
        for _ in range(bootstraps):
            sample=[r for d in rng.choices(dates,k=len(dates)) for r in clusters[d]]
            value=calculate(sample)
            draws["brier"].append(value["brier_delta_challenger_minus_control"])
            draws["logloss"].append(value["logloss_delta_challenger_minus_control"])
        interval={k:[sorted(xs)[int(.025*bootstraps)],
                     sorted(xs)[int(.975*bootstraps)-1]]
                  for k,xs in draws.items()}
        status="research_only_date_cluster_interval_not_production_calibration"
    return {"schema":"nfl-tackle-challenger-walk-forward-scoring-v1",
            "source":"retrospective_plus_18h_historical_availability_unverified",
            "line_source":report["line_source"],"n_dates":len(dates),
            "score":scored,"interval_95":interval,"status":status,
            "ranking_allowed":False,"production_eligible":False,
            "training_started":False}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--normalized-bundles",required=True,type=Path,
                    help="Original JSON array of nfl_context_data.normalize bundles")
    ap.add_argument("--walk-forward-from",
                    help="Research-only chronological replay start (UTC instant)")
    ap.add_argument("--max-holdout-rows",type=int,default=4200)
    ap.add_argument("--player-id")
    ap.add_argument("--team")
    ap.add_argument("--game-id")
    ap.add_argument("--forecast-at")
    ap.add_argument("--event-start")
    ap.add_argument("--expected-defensive-plays",type=float)
    ap.add_argument("--line",type=float)
    ap.add_argument("--teammate-id")
    ap.add_argument("--teammate-report",type=Path)
    ap.add_argument("--historical-teammate-reports",type=Path)
    ap.add_argument("--archive-root",type=Path)
    ap.add_argument("--out",type=Path)
    a=ap.parse_args(argv)
    history=normalize_bundles(json.loads(a.normalized_bundles.read_text()))
    if a.walk_forward_from:
        if a.teammate_id or a.teammate_report:
            ap.error("teammate conditioning requires archived game-specific pregame reports")
        if not 100<=a.max_holdout_rows<=50000:
            ap.error("invalid walk-forward row cap")
        research=walk_forward(history,from_time=a.walk_forward_from,
                              line=5.5 if a.line is None else a.line,
                              max_rows=a.max_holdout_rows)
        result={
            "schema":"nfl-tackle-challenger-research-report-v1",
            "input_source_digests":history["history_source_digests"],
            "source_quality_counts":history["source_quality_counts"],
            "historical_timing_policy":history["time_provenance"],
            "walk_forward_from":a.walk_forward_from,
            "max_holdout_rows":a.max_holdout_rows,
            "score":summarize_walk_forward(research),
            "production_eligible":False,
            "ranking_allowed":False,"training_started":False}
    else:
        if (not a.player_id or not a.team or not a.forecast_at or
                not a.event_start or a.line is None or
                a.expected_defensive_plays is None):
            ap.error("single challenger forecast needs exact player/team, forecast/event "
                     "time, pregame expected defensive plays and a line")
        teammate=json.loads(a.teammate_report.read_text()) if a.teammate_report else None
        archived=json.loads(a.historical_teammate_reports.read_text()) if a.historical_teammate_reports else None
        result=predict(history,player_id=a.player_id,team=a.team,
            game_id=a.game_id,forecast_at=a.forecast_at,event_start=a.event_start,
            expected_defensive_plays=a.expected_defensive_plays,line=a.line,
            teammate_id=a.teammate_id,teammate_report=teammate,
            historical_teammate_reports=archived,archive_root=a.archive_root)
    data=json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n"
    if a.out:
        if a.out.exists() and a.out.read_text()!=data:
            raise TackleChallengerError("would_overwrite_different_forecast_or_report")
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(data)
    print(data)


if __name__=="__main__":
    main()
