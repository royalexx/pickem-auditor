"""Point-in-time features and frozen chronological design matrices for NHL."""
from __future__ import annotations

import math
from datetime import timedelta

import nhl_context_data as store

MARKETS = ("saves", "shots", "hits", "blocks")
BASE_FEATURES = ("home", "rest_difference", "recent_workload")
CONTEXT_FEATURES = ("opportunity_for", "opportunity_against", "venue_for", "venue_against")
XG_FEATURES = ("opponent_goal_quality", "team_goal_quality")


def pilot_cohort(rows, games, *, min_seasons=2):
    """Training-only latest-game cohort with a prior-season anchor when needed.

    A last-200-games cohort entirely within one season cannot identify the
    next-season variance required for early-season holdouts. Reserve one quarter
    for the latest preceding season if a previous training season is available.
    Selection uses dates/identities only, never target magnitudes or holdouts.
    """
    if not isinstance(games,int) or isinstance(games,bool) or games<0:
        raise ValueError("invalid_pilot_game_limit")
    if games==0:
        return rows
    if min_seasons not in (1,2) or games<min_seasons:
        raise ValueError("pilot_too_small_for_season_hierarchy")
    game_info={}
    for row in rows:
        key=row["game_id"]
        value=(row["start_time"],row["season"])
        if key in game_info and game_info[key]!=value:
            raise ValueError("inconsistent_training_game_metadata")
        game_info[key]=value
    ordered=sorted(game_info,key=lambda gid:(store.instant(game_info[gid][0]),gid))
    chosen=ordered[-games:]
    chosen_seasons={game_info[g][1] for g in chosen}
    seasons=sorted({v[1] for v in game_info.values()})
    if len(chosen_seasons)<min_seasons and len(seasons)>=min_seasons:
        prior=[g for g in ordered if game_info[g][1]==seasons[-2]]
        anchor=min(max(1,games//4),len(prior),games-1)
        recent=[g for g in ordered if game_info[g][1]==seasons[-1]]
        chosen=prior[-anchor:]+recent[-(games-anchor):]
        # If a short recent season leaves room, fill from other earlier games.
        available=games-len(chosen)
        if available:
            current=set(chosen)
            chosen=[g for g in ordered if g not in current][-available:]+chosen
    allowed=set(chosen)
    return [r for r in rows if r["game_id"] in allowed]


def shrunk_rate(rows, field, *, prior, prior_games=5):
    """Exposure-weighted per-60 estimate; fixed priors never use holdout data."""
    if any(r.get(field) is None for r in rows):
        raise ValueError("missing_opportunity_metric:" + field)
    exposure = sum(r["game_minutes"] for r in rows)
    return (sum(r[field] for r in rows) + prior * prior_games) / (exposure / 60 + prior_games)


def _rest(rows, at):
    if not rows:
        return 3.0
    # Days between starts; capped to avoid offseason leverage.
    return min(7., max(0., (store.instant(at) - store.instant(rows[-1]["start_time"])).total_seconds() / 86400))


def validate_xg(rows):
    """Provider and model vintage are mandatory, not interchangeable estimates."""
    seen = set()
    for row in rows:
        for key in ("game_id", "team", "provider", "model_version", "model_trained_through",
                    "available_at", "source_url", "source_sha256", "xgf", "xga"):
            if key not in row:
                raise ValueError("missing_xg_provenance:" + key)
        key = (row["game_id"], row["team"], row["provider"], row["model_version"])
        if key in seen:
            raise ValueError("duplicate_xg_team_game")
        seen.add(key)
        store.instant(row["available_at"])
        store.instant(row["model_trained_through"])
        if not row["provider"] or not row["model_version"] or len(row["source_sha256"]) != 64:
            raise ValueError("invalid_xg_source")
        for metric in ("xgf", "xga"):
            value = row[metric]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 30:
                raise ValueError("invalid_xg_value")
    versions = {(r["provider"], r["model_version"]) for r in rows}
    if len(versions) > 1:
        raise ValueError("mixed_xg_model_versions_require_separate_experiment")
    return rows


def context(index, matchup, *, player_id, position, market, feature_set="context", xg_rows=()):
    """Same path for historical training and pregame forecasts.

    The matchup contains identities/start time/home only. Actual game minutes,
    target counts, future lineup labels and sportsbook odds are not read here.
    """
    if market not in MARKETS or feature_set not in ("base", "context", "xg"):
        raise ValueError("unsupported_context_experiment")
    if not isinstance(matchup["home"], bool) or matchup["team"] == matchup["opponent"]:
        raise ValueError("invalid_pregame_matchup")
    if position not in (("G",) if market == "saves" else ("F", "D")):
        raise ValueError("market_position_mismatch")
    at = matchup["start_time"]
    gid = matchup.get("game_id")
    team = index.before("teams", matchup["team"], at, exclude_game=gid)
    opp = index.before("teams", matchup["opponent"], at, exclude_game=gid)
    player = index.before("goalies" if position == "G" else "skaters", str(player_id), at, exclude_game=gid)
    if market == "saves":
        player = [r for r in player if r["starter"]]
    prior_toi = {"F": 16., "D": 20., "G": 57.}[position]
    recent = player[-5:]
    avg_toi = (sum(r["minutes"] for r in recent) + 3 * prior_toi) / (len(recent) + 3)
    features = [float(matchup["home"]), (_rest(team, at) - _rest(opp, at)) / 7,
                math.log(avg_toi / prior_toi)]
    names = list(BASE_FEATURES)
    if feature_set != "base":
        # Different opportunity mechanisms, never use opponent SOG for every stat.
        if market == "saves":
            a, b, af, bf, prior = opp, team, "shots_for", "shots_against", 30.
            av = [r for r in a if r["home"] != matchup["home"]]
            bv = [r for r in b if r["home"] == matchup["home"]]
        elif market == "shots":
            a, b, af, bf, prior = team, opp, "shots_for", "shots_against", 30.
            av = [r for r in a if r["home"] == matchup["home"]]
            bv = [r for r in b if r["home"] != matchup["home"]]
        elif market == "hits":
            a, b, af, bf, prior = team, opp, "hits", "hits", 22.
            av = [r for r in a if r["home"] == matchup["home"]]
            bv = [r for r in b if r["home"] != matchup["home"]]
        else:
            # Team blocks measure blocks credited under local scorekeeping;
            # opponent attempts measure incoming opportunities. Requires PBP
            # attempt enrichment; no silent substitution of shots on goal.
            a, b, af, bf, prior = team, opp, "blocks", "attempts_for", 15.
            av = [r for r in a if r["home"] == matchup["home"]]
            bv = [r for r in b if r["home"] != matchup["home"]]
        bprior = 55. if market == "blocks" else prior
        ar = shrunk_rate(a, af, prior=prior)
        br = shrunk_rate(b, bf, prior=bprior)
        features += [math.log(ar / prior), math.log(br / bprior),
                     math.log(shrunk_rate(av, af, prior=ar, prior_games=10) / ar),
                     math.log(shrunk_rate(bv, bf, prior=br, prior_games=10) / br)]
        names += list(CONTEXT_FEATURES)
    xg_count = 0
    if feature_set == "xg":
        if market != "saves":
            raise ValueError("xg_conversion_features_currently_saves_only")
        validate_xg(xg_rows)
        lookup = {(r["game_id"], r["team"]): r for r in xg_rows
                  if store.instant(r["available_at"]) < store.instant(at)
                  and store.instant(r["model_trained_through"]) < store.instant(at)}
        def quality(history, field, shot_field):
            pairs = [(r, lookup[(r["game_id"], r["team"])]) for r in history
                     if (r["game_id"], r["team"]) in lookup]
            if not pairs:
                raise ValueError("missing_point_in_time_xg_history")
            total = sum(x[field] for _, x in pairs)
            shots = sum(r[shot_field] for r, _ in pairs)
            if shots == 0:
                raise ValueError("xg_history_without_shots")
            return math.log((total + .09 * 150) / (shots + 150) / .09), len(pairs)
        oq, on = quality(opp, "xgf", "shots_for")
        tq, tn = quality(team, "xga", "shots_against")
        features += [oq, tq]
        names += list(XG_FEATURES)
        xg_count = min(on, tn)
    if not all(math.isfinite(v) for v in features):
        raise ValueError("nonfinite_context_feature")
    return {"values": features, "names": names, "team_games": len(team), "opponent_games": len(opp),
            "player_games": len(player), "xg_games": xg_count,
            "identity": {"game_id":gid,"player_id":str(player_id),"team":matchup["team"],
                         "opponent":matchup["opponent"],"home":matchup["home"],"position":position},
            "availability_policy": index.policy, "computed_before": at,
            "latest_source_game_start": max((r["start_time"] for r in team + opp + player), default=None)}


def examples(bundles, *, market, policy="retrospective_next_day", feature_set="context",
             xg_rows=(), min_team_games=5):
    """Construct covariates BEFORE attaching current-game training outcomes."""
    if min_team_games < 0:
        raise ValueError("invalid_warmup")
    validate_xg(xg_rows)
    index = store.HistoryIndex(bundles, policy=policy)
    rows, omitted = [], []
    for bundle in bundles:
        table = bundle["goalies"] if market == "saves" else bundle["skaters"]
        for row in table:
            if market == "saves" and not row["starter"]:
                continue  # Model is explicitly conditional on starting.
            try:
                f = context(index, row, player_id=row["player_id"], position=row["position"],
                            market=market, feature_set=feature_set, xg_rows=xg_rows)
                if min(f["team_games"], f["opponent_games"]) < min_team_games:
                    raise ValueError("insufficient_pregame_team_history")
            except ValueError as exc:
                omitted.append({"game_id": row["game_id"], "player_id": row["player_id"], "reason": str(exc)})
                continue
            rows.append({**row, "market": market, "features": f,
                         "target": row["saves"] if market == "saves" else row[market],
                         "target_available_at": (bundle["source"]["observed_at"] if policy == "recorded" else
                            (store.instant(row["start_time"])+timedelta(hours=12)).isoformat()),
                         "source_sha256": bundle["source"]["sha256"]})
    return rows, omitted


def prepare(rows, *, cutoff, feature_set="context", min_rows=200):
    """Training-only identities, standardization, and manifest digest."""
    import numpy as np
    end = store.instant(cutoff)
    if not rows or any(store.instant(r["start_time"]) >= end or store.instant(r["target_available_at"]) >= end for r in rows):
        raise ValueError("training_contains_cutoff_or_future_game")
    if len(rows) < min_rows:
        raise ValueError("insufficient_context_training_rows")
    keys = [(r["game_id"], r["player_id"]) for r in rows]
    if len(keys) != len(set(keys)) or len({r["market"] for r in rows}) != 1:
        raise ValueError("duplicate_or_mixed_training_population")
    for row in rows:
        if row["features"]["computed_before"] != row["start_time"]:
            raise ValueError("context_feature_time_mismatch")
        if not 0 < row["minutes"] <= row["game_minutes"] + .02:
            raise ValueError("invalid_training_exposure")
        store.count(row["target"])
        if row["market"] == "saves":
            store.count(row["shots_against"])
            if row["target"] > row["shots_against"] or not row["starter"]:
                raise ValueError("invalid_starter_saves_target")
    players = sorted({r["player_id"] for r in rows})
    teams = sorted({r[k] for r in rows for k in ("team", "opponent")})
    seasons = sorted({r["season"] for r in rows})
    positions = sorted({r["position"] for r in rows})
    identity_positions = {}
    for row in rows:
        pid = row["player_id"]
        old = identity_positions.setdefault(pid,row["position"])
        if old != row["position"]:
            raise ValueError("position_change_requires_explicit_mapping")
    names = rows[0]["features"]["names"]
    expected = list(BASE_FEATURES)+(list(CONTEXT_FEATURES) if feature_set != "base" else [])
    if feature_set == "xg":
        expected += list(XG_FEATURES)
    if names != expected or len({r["features"]["availability_policy"] for r in rows}) != 1:
        raise ValueError("feature_set_or_availability_policy_mismatch")
    if any(r["features"]["names"] != names for r in rows):
        raise ValueError("inconsistent_feature_design")
    x = np.asarray([r["features"]["values"] for r in rows], dtype=float)
    if not np.isfinite(x).all():
        raise ValueError("nonfinite_design_matrix")
    center = x.mean(axis=0)
    scale = x.std(axis=0)
    scale = np.where(scale > .05, scale, 1.)
    pmap, tmap, smap, posmap = ({v:i for i,v in enumerate(items)} for items in (players,teams,seasons,positions))
    player_position = {pid: posmap[identity_positions[pid]] for pid in players}
    return {"schema": "nhl-context-design-v1", "market": rows[0]["market"], "feature_set": feature_set,
            "players": players, "teams": teams, "seasons": seasons, "positions": positions,
            "player_position": player_position, "feature_names": names,
            "center": center.tolist(), "scale": scale.tolist(), "x": ((x-center)/scale).tolist(),
            "player_idx": [pmap[r["player_id"]] for r in rows],
            "team_idx": [tmap[r["team"]] for r in rows],
            "opponent_idx": [tmap[r["opponent"]] for r in rows],
            "season_idx": [smap[r["season"]] for r in rows],
            "position_idx": [posmap[r["position"]] for r in rows],
            "minutes": [r["minutes"] for r in rows], "game_minutes": [r["game_minutes"] for r in rows],
            "target": [r["target"] for r in rows],
            "shots_against": [r.get("shots_against", 0) for r in rows],
            "cutoff_exclusive": cutoff, "source_digest": store.digest(sorted(rows, key=lambda r: (r["start_time"],r["game_id"],r["player_id"]))),
            "rows": len(rows), "games": len({r["game_id"] for r in rows}),
            "availability_policy": rows[0]["features"]["availability_policy"],
            "training_game_durations": sorted({(r["game_id"], r["game_minutes"]) for r in rows}),
            "ranking_allowed": False}
