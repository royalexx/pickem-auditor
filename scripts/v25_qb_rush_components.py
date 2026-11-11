"""Phase 2 NHL-independent NFL QB rushing decomposition, prequential-only research.

Creates *joint* count/yard draws for four disjoint, box-score-reconcilable
QB rush events:
  scramble = quarterback dropback -> rushing gain
  designed = rush not arising from a QB dropback (includes some aborted snaps)
  kneel    = clock management (separate highly negative yard component)
  other    = unclassified, explicitly retained rather than discarded

The sources are dated retrospectively. All inference occurs with games STRICTLY
before the requested season/week. Caller supplies a pre-event QB1 identity,
never inferred from final score or actual QB pass/rush statistics.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime,timezone
import hashlib
import json
import math
import numpy as np

KINDS=("scramble","designed","kneel","other")
SCHEMA="nfl_qb_rush_component_model_prequential_v1"
SHRINK_GAMES=8.0
MAX_SAMPLES=4096
MIN_SAMPLES=128


class ComponentModelError(ValueError):
    pass


def require(ok,code):
    if not ok:raise ComponentModelError(code)


def digest(o):
    raw=json.dumps(o,sort_keys=True,separators=(",",":"),allow_nan=False,default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def seed_from(*parts):
    return int(digest([str(x) for x in parts])[:16],16)


def _finite_nonnegative(x,name):
    require(not isinstance(x,bool),name+"_boolean")
    try:v=float(x)
    except (ValueError,TypeError,OverflowError) as exc:
        raise ComponentModelError(name+"_invalid") from exc
    require(math.isfinite(v) and v>=0,name+"_out_of_range")
    return v


def verify_component_row(row):
    require(isinstance(row,dict),"source_not_mapping")
    require(row.get("season") in (2021,2022,2023,2024,2025),
            "unsupported_component_season")
    wk=row.get("week")
    require(type(wk) is int and 1<=wk<=18,"bad_week")
    for field in ("game_id","team","player_id"):
        require(isinstance(row.get(field),str) and bool(row[field]),
                "missing_"+field)
    require(row.get("reconciled_to_weekly_stats") is True,
            "unreconciled_boxscore_source_must_abstain")
    require(row.get("source_original_capture_verified") is not True,
            "source_retrospective_does_not_verify_pregame")
    require(set(row["counts"])==set(KINDS) and set(row["yards"])==set(KINDS),
            "incomplete_disjoint_categories")
    counts={}
    yards={}
    for k in KINDS:
        v=_finite_nonnegative(row["counts"][k],"count_"+k)
        require(float(v).is_integer(),"noninteger_count_"+k)
        counts[k]=int(v)
        y=row["yards"][k]
        require(not isinstance(y,bool) and isinstance(y,(int,float))
                and math.isfinite(float(y)),"invalid_yards_"+k)
        yards[k]=float(y)
        require(counts[k] or abs(yards[k])<1e-9,"yards_without_count_"+k)
    n=sum(counts.values())
    require(n==row["official_attempts"],"count_does_not_reconcile")
    require(math.isclose(sum(yards.values()),float(row["official_rushing_yards"]),
                         abs_tol=1e-7),"yards_does_not_reconcile")
    drop=_finite_nonnegative(row["dropbacks"],"dropbacks")
    require(float(drop).is_integer(),"noninteger_dropbacks")
    return counts,yards,int(drop)


def _asof(row,year,week):
    season=row["season"]
    return season<year or (season==year and row["week"]<week)


class QBRushComponentModel:
    """Hierarchical, zero-capable, no-present-game-feature baseline challenger.

    Counts:
      dropbacks ~ Gamma-Poisson, player / QB population with 8-game shrinkage;
      scramble attempts ~ Beta-Binomial(dropbacks, prior player/pool rate);
      designed/kneel/other attempts ~ Gamma-Poisson per-game intensities,
      each separately pooled by player and prior QB population.
    Yards:
      signed, regularized per-attempt Student-t innovations conditioned on
      sampled component attempts, using only earlier appearance observations.
      Zero rushes => exactly zero yards with nonzero probability.
    """

    def __init__(self,rows,*,forecast_year,forecast_week):
        require(forecast_year in (2024,2025),"experimental_year_scope")
        require(type(forecast_week) is int and 1<=forecast_week<=18,
                "invalid_forecast_week")
        self.year=forecast_year;self.week=forecast_week
        self.rows=[];self.by_player=defaultdict(list)
        self.prior_sources_discarded=0
        self.temporal_ids=set()
        for row in rows:
            # No future outcome is permitted to enter inference. Fail the
            # entire fit rather than silently filtering leaked current-week.
            require(_asof(row,forecast_year,forecast_week),
                    "current_or_future_QB_PBP_leak")
            key=(row.get("season"),row.get("week"),row.get("game_id"),
                 row.get("team"),row.get("player_id"))
            require(key not in self.temporal_ids,"duplicate_component_player_game")
            self.temporal_ids.add(key)
            try:counts,yards,drop=verify_component_row(row)
            except ComponentModelError as exc:
                # Off-by-one / provider reconciliation is an EXPLICIT
                # nontraining rejection, never an imputed zero.
                if str(exc)=="unreconciled_boxscore_source_must_abstain":
                    self.prior_sources_discarded+=1;continue
                raise
            obj={"counts":counts,"yards":yards,"dropbacks":drop,
                 "team":row["team"],"year":row["season"],"week":row["week"]}
            self.rows.append(obj)
            self.by_player[row["player_id"]].append(obj)
        require(len(self.rows)>=80,"insufficient_pre_event_component_training_games")
        for pid in self.by_player:
            self.by_player[pid].sort(key=lambda x:(x["year"],x["week"]))
        self.peer=self.rows
        self.reference={"source_training_rows":len(self.rows),
                        "discarded_unreconciled":self.prior_sources_discarded,
                        "max_allowed_season":forecast_year,
                        "max_allowed_week_exclusive":forecast_week,
                        "training_source_is_retrospective":True}

    @staticmethod
    def _avg(rows,getter):
        return sum(getter(r) for r in rows)/len(rows) if rows else 0.0

    def _params(self,pid):
        own=self.by_player.get(pid,[])[-12:]
        peer=self.peer
        # Pool count intensities from prior QB-game appearances, but never
        # let a rarely appearing player win with a zero-observation prior.
        w=len(own)/(len(own)+SHRINK_GAMES)
        baseline={"n_appearance_history":len(own),
                  "prior_QB_games":len(peer),"player_shrink_weight":w}
        per_kind={}
        for name in KINDS:
            popcount=self._avg(peer,lambda r:r["counts"][name])
            player_count=self._avg(own,lambda r:r["counts"][name])
            intensity=(1-w)*popcount+w*player_count
            pop_attempts=sum(r["counts"][name] for r in peer)
            player_attempts=sum(r["counts"][name] for r in own)
            popyards=sum(r["yards"][name] for r in peer)
            playeryards=sum(r["yards"][name] for r in own)
            # Same prior for all players, but type-specific: kneel component
            # is not allowed to borrow scramble 5-yard means.
            prior_attempts=16 if name in ("scramble","designed") else 30
            mean_yards=(playeryards+prior_attempts*
                        (popyards/pop_attempts if pop_attempts else 0.0))/(player_attempts+prior_attempts)
            # The innovation scale prevents a tiny finite sample of historical
            # player game totals from defining an impossible-to-cross range.
            # Precommitted floor by type; Student-t heavy tails handle rare long
            # scrambles and designed rushes, and negative-yardage rushes.
            floor={"scramble":4.5,"designed":4.5,"kneel":0.35,"other":4.5}[name]
            # Game-level per-attempt mean provides a conservative estimator.
            observed=[r["yards"][name]/r["counts"][name]
                      for r in own if r["counts"][name]>0]
            scale=max(floor, float(np.std(observed,ddof=1))
                      if len(observed)>1 else floor)
            per_kind[name]={"mu_count":max(0.0,intensity),
                            "mean_yards_per_attempt":float(mean_yards),
                            "yard_scale":float(min(scale,25.0)),
                            "prior_attempts":prior_attempts}
        # Dropback count and scramble share are separated.
        pop_drop=self._avg(peer,lambda r:r["dropbacks"])
        own_drop=self._avg(own,lambda r:r["dropbacks"])
        mu_drop=max(.0,w*own_drop+(1-w)*pop_drop)
        pool_scr=sum(r["counts"]["scramble"] for r in peer)
        pool_drop=sum(r["dropbacks"] for r in peer)
        pool_scramble_share=(pool_scr+1)/(pool_drop+2)
        own_scr=sum(r["counts"]["scramble"] for r in own)
        own_drop_total=sum(r["dropbacks"] for r in own)
        # Beta strength mimics 50 historic dropbacks and preserves variance.
        strength=50.0
        a=strength*pool_scramble_share+own_scr
        b=strength*(1-pool_scramble_share)+max(0,own_drop_total-own_scr)
        require(a>0 and b>0,"scramble_rate_fit_invalid")
        baseline["dropback_mu"]=mu_drop
        baseline["scramble_alpha"]=a
        baseline["scramble_beta"]=b
        baseline["scramble_pool_rate"]=pool_scramble_share
        baseline["types"]=per_kind
        return baseline

    def draw(self,pid,*,n=512,seed=20261111):
        require(type(n) is int and MIN_SAMPLES<=n<=MAX_SAMPLES,"bad_draw_count")
        require(isinstance(pid,str) and bool(pid),"invalid_qb_player_id")
        # A QB1 named by the independent, dated research selector may be a
        # rookie with no NFL appearances. Cold starts use only the prior QB
        # population and are marked distinctly; a model MUST NOT infer the
        # starter from observed current-week participation or known outcome.
        p=self._params(pid)
        rng=np.random.default_rng(seed_from(SCHEMA,self.year,self.week,pid,seed))
        pace=rng.gamma(shape=20.0,scale=1/20.0,size=n)
        drop_mu=p["dropback_mu"]
        dropbacks=rng.poisson(np.maximum(0,drop_mu*pace))
        scramble_p=rng.beta(p["scramble_alpha"],p["scramble_beta"],n)
        counts={"scramble":rng.binomial(dropbacks,np.clip(scramble_p,0,1))}
        for kind in ("designed","kneel","other"):
            # Each component has a true zero outcome under Gamma-Poisson
            # rather than the historical-yards empirical-residual support.
            intensity=p["types"][kind]["mu_count"]
            gamestate=rng.gamma(shape=7.0,scale=1/7.0,size=n)
            counts[kind]=rng.poisson(np.maximum(0.0,intensity*pace*gamestate))
        yards={}
        for kind in KINDS:
            kcount=counts[kind]
            max_count=int(kcount.max())
            if max_count==0:
                yards[kind]=np.zeros(n,dtype=float)
                continue
            pars=p["types"][kind]
            if kind=="kneel":
                # Respect a small signed class of realistic kneeling losses.
                yard_per=-rng.choice([1,2],size=(n,max_count),p=[.85,.15])
            else:
                trial=pars["mean_yards_per_attempt"]+pars["yard_scale"]*rng.standard_t(
                    df=5,size=(n,max_count))
                # Wide physical limits per attempt, not a postgame line cap.
                yard_per=np.rint(np.clip(trial,-18,85))
            mask=np.arange(max_count)[None,:]<kcount[:,None]
            yards[kind]=np.sum(yard_per*mask,axis=1).astype(float)
        attempts=sum(counts.values(),np.zeros(n,dtype=int))
        total_yards=sum(yards.values(),np.zeros(n,dtype=float))
        require(np.all(attempts>=0) and np.all(np.isfinite(total_yards)),
                "invalid_component_draws")
        require(np.all(attempts==sum(counts[k] for k in KINDS)),
                "rushing_attempt_components_do_not_conserve")
        require(np.all(total_yards==sum(yards[k] for k in KINDS)),
                "rushing_yard_components_do_not_conserve")
        return {"schema":SCHEMA,"player_id":pid,
                "counts":{k:counts[k].astype(int).tolist() for k in KINDS},
                "type_yards":{k:yards[k].tolist() for k in KINDS},
                "qb_rushing_attempts":attempts.astype(int).tolist(),
                "qb_rushing_yards":total_yards.tolist(),
                "parameters":p,
                "QB_cold_start_no_prior_games":p["n_appearance_history"]==0,
                "forecast_season":self.year,"forecast_week":self.week,
                "model_supports_zero_yards":bool(np.any(total_yards==0)),
                "inference_does_not_consume_current_game_data":True,
                "source_reconciliation":self.reference,
                "research_only":True,"production_authorized":False}
