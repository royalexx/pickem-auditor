"""Pre-2024 team/defense opportunity challenger with five-game player form.

Only 2021–2023 games played before January 1, 2024 are admissible inputs.
The 2024 evaluation forecasts use one frozen 2023-12-31 snapshot, even in W18.

Hierarchical empirical-Bayes/shrinkage rates; not a sampled NUTS posterior.
Counts use a predeclared Negative Binomial; yards use a heavy-tailed Student t.
NGS can contribute to QB/reception/rushing efficiency, not QB read labeling.
FTN checkdowns are optional and fail closed on post-cutoff pull provenance.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date
import math
from statistics import median
from nfl_pre2024_pbp_ngs_sources import CUTOFF,_gameday

VOLUME_MARKETS=("pass attempts","completions","passing yards","targets",
 "receptions","receiving yards","carries","rushing yards",
 "tackles + assists","solo tackles","tackle assists")
COUNT_MARKETS=set(VOLUME_MARKETS)-{"passing yards","receiving yards","rushing yards"}
ROLE_POS={
 "pass attempts":{"QB"},"completions":{"QB"},"passing yards":{"QB"},
 "targets":{"WR","RB","TE"},"receptions":{"WR","RB","TE"},
 "receiving yards":{"WR","RB","TE"},"carries":{"QB","RB"},
 "rushing yards":{"QB","RB"},
 "tackles + assists":{"LB","MLB","OLB","ILB","DE","DT","NT","CB","DB","S","FS","SS"},
 "solo tackles":{"LB","MLB","OLB","ILB","DE","DT","NT","CB","DB","S","FS","SS"},
 "tackle assists":{"LB","MLB","OLB","ILB","DE","DT","NT","CB","DB","S","FS","SS"}
}
MARKET_TEAM_METRIC={
 "pass attempts":"pass_attempts","completions":"pass_attempts",
 "passing yards":"pass_attempts","targets":"pass_attempts",
 "receptions":"pass_attempts","receiving yards":"pass_attempts",
 "carries":"rush_attempts","rushing yards":"rush_attempts",
 "tackles + assists":"dropbacks","solo tackles":"dropbacks",
 "tackle assists":"dropbacks",
}
MARKET_BASE_PRIOR={
 "pass attempts":29.,"completions":19.,"passing yards":215.,
 "targets":4.5,"receptions":3.,"receiving yards":37.,
 "carries":8.,"rushing yards":35.,"tackles + assists":4.,
 "solo tackles":2.4,"tackle assists":1.3,
}
COUNT_DISPERSION={"pass attempts":30.,"completions":24.,"targets":5.,
 "receptions":5.,"carries":12.,"tackles + assists":5.,
 "solo tackles":4.,"tackle assists":4.}
YARD_SCALE={"passing yards":54.,"receiving yards":21.,"rushing yards":24.}
MIN_PLAYER_PRIOR_APPEARANCES=3
PLAYER_HALF_LIFE_DAYS=35.
TEAM_HALF_LIFE_DAYS=120.
PRIOR_TEAM_GAMES=5.
PRIOR_PLAYER_GAMES=1.25
CURRENT_PLAYER_WEIGHT_CAP=.82
TEAM_FACTOR_RANGE=(.72,1.32)
VERSION="pre2024_pbp_ngs_team_defense_lastfive_gamma_prior_v1"

def _day(s):
 return date.fromisoformat(str(s)[:10])

def _weighted(rows,asof,key,*,half_life,limit=None):
 z=sorted((r for r in rows if _day(r.get("game_date") or r.get("gameday"))<asof),
          key=lambda r:(r.get("game_date") or r.get("gameday")),reverse=True)
 if limit is not None:z=z[:limit]
 if not z:return None,0.
 pairs=[]
 for r in z:
  age=(asof-_day(r.get("game_date") or r.get("gameday"))).days
  w=2.**(-age/half_life)
  val=float(r.get(key,0.))
  if not math.isfinite(val):continue
  pairs.append((val,w))
 if not pairs:return None,0.
 weight=sum(w for _,w in pairs)
 return sum(v*w for v,w in pairs)/weight,weight

def _regularize(v,effective,reference,pseudogames):
 if v is None:return reference
 return (v*effective+reference*pseudogames)/(effective+pseudogames)

def _clip(x,lo,hi):
 return max(lo,min(hi,x))

def historical_sources(player_rows,pbp_games,ngs):
 """Build as-of addressable histories from pre-2024 sources only."""
 from nfl_pre2024_pbp_ngs_sources import assert_pre2024_training_inputs
 flat_ngs=[r for rows in ngs.values() for r in rows]
 assert_pre2024_training_inputs(player_rows=player_rows,pbp_games=pbp_games,
                               ngs_rows=flat_ngs)
 state=dict(player=defaultdict(list),role=defaultdict(list),
            team_offense=defaultdict(list),opponent_allowed=defaultdict(list),
            league_offense=defaultdict(list),ngs=defaultdict(list),
            latest_by_player={},team_games=len(pbp_games),
            _train_cutoff=CUTOFF.isoformat())
 for row in player_rows:
  stat=row["stat"];position=row["position"]
  if stat not in VOLUME_MARKETS or position not in ROLE_POS[stat]:continue
  pid=str(row["player_id"])
  day=str(row["game_date"])
  x={"gameday":day,"game_date":day,
      "value":float(row["value"]),
      "workload":float(row.get("workload",0.)),
      "position":position,"team":row["team"],"season":int(row["season"])}
  state["player"][(stat,pid)].append(x)
  state["role"][(stat,position)].append(x)
  prev=state["latest_by_player"].get(pid)
  if prev is None or day>prev["gameday"]:
   state["latest_by_player"][pid]={"gameday":day,"team":row["team"],
                       "position":position,"season":int(row["season"])}
 for x in pbp_games:
  team,opp=x["team"],x["opponent"]
  day=x["gameday"]
  for metric in set(MARKET_TEAM_METRIC.values())|{
       "short_pass_attempts","short_rb_targets","neutral_passes",
       "neutral_rushes","pass_completions","qb_hits",
       "charted_checkdowns","charted_dropbacks","passing_yards","rushing_yards"}:
   item={"gameday":day,"value":float(x.get(metric,0.))}
   state["team_offense"][(metric,team)].append(item)
   state["opponent_allowed"][(metric,opp)].append(item)
   state["league_offense"][metric].append(item)
 for kind,rows in ngs.items():
  for x in rows:
   pid=str(x["player_id"])
   state["ngs"][(kind,pid)].append(x)
 for bucket in ("player","role","team_offense","opponent_allowed","league_offense","ngs"):
  for key in state[bucket]:
   state[bucket][key].sort(key=lambda x:x.get("game_date") or x["gameday"])
 return state

def team_metric_ratio(state,metric,team,opponent,asof,*,team_weight=.62):
 global_avg,ng=_weighted(state["league_offense"].get(metric,()),asof,
                        "value",half_life=TEAM_HALF_LIFE_DAYS)
 if global_avg is None or global_avg<.08:return 1.,{"source":"insufficient_team_metric", "metric":metric}
 own,ne=_weighted(state["team_offense"].get((metric,team),()),asof,
                  "value",half_life=TEAM_HALF_LIFE_DAYS,limit=30)
 # opponent_allowed means the number of offense opportunities a defense faced.
 allow,nd=_weighted(state["opponent_allowed"].get((metric,opponent),()),asof,
                    "value",half_life=TEAM_HALF_LIFE_DAYS,limit=30)
 own=_regularize(own,ne,global_avg,PRIOR_TEAM_GAMES)
 allow=_regularize(allow,nd,global_avg,PRIOR_TEAM_GAMES)
 ownratio=_clip(own/global_avg,.6,1.5)
 defratio=_clip(allow/global_avg,.6,1.5)
 ratio=_clip(ownratio**team_weight*defratio**(1.-team_weight),*TEAM_FACTOR_RANGE)
 return ratio,{"metric":metric,"own_ratio":ownratio,"opponent_allowed_ratio":defratio,
               "team_effective_games":ne,"opponent_effective_games":nd,
               "league_rate":global_avg,"source":"pre2024_pbp"}

def _ngs_effect(state,stat,player_id,asof):
 # Efficiency-only NGS correction, shrunk to at most ±10%. Never fabricates
 # charted checkdowns from air yards or says a short pass is a true read #3.
 conf={
  "completions":("passing","completion_percentage_above_expectation",.005),
  "passing yards":("passing","avg_intended_air_yards",.012),
  "receiving yards":("receiving","avg_yac_above_expectation",.014),
  "rushing yards":("rushing","rush_yards_over_expected_per_att",.014),
 }
 if stat not in conf:return 1.,{"ngs_status":"not_relevant_to_market"}
 kind,field,slope=conf[stat]
 items=state["ngs"].get((kind,player_id),())
 val,n=_weighted(items,asof,field,half_life=70.,limit=5)
 if val is None or n<.2:return 1.,{"ngs_status":"missing_sparse_or_unavailable"}
 # Expected completion above expectation is percentage points; e.g. 5 -> 2.5%,
 # not a 5-percentage-point probability boost.
 shift=slope*val
 if stat=="passing yards":shift=slope*(val-8.)
 factor=_clip(1.+shift,.90,1.10)
 return factor,{"ngs_status":"included_only_pre2024","ngs_field":field,
                "ngs_recent":val,"ngs_factor":factor}

def player_rate(state,stat,pid,position,team,asof,*,recent_usage=True):
 history=[r for r in state["player"].get((stat,pid),())
          if _day(r["gameday"])<asof and r["team"]==team]
 history.sort(key=lambda r:r["gameday"],reverse=True)
 if len(history)<MIN_PLAYER_PRIOR_APPEARANCES:return None,{"status":"no_prior_player_usage"}
 recent=history[:5]
 role,eff=_weighted(state["role"].get((stat,position),()),asof,
                    "value",half_life=140.,limit=2000)
 prior=_regularize(role,eff,MARKET_BASE_PRIOR[stat],12.)
 rv,rw=_weighted(recent,asof,"value",half_life=PLAYER_HALF_LIFE_DAYS)
 if rv is None:return None,{"status":"missing_recent_usage"}
 share=(min(CURRENT_PLAYER_WEIGHT_CAP,.25+.114*len(recent))
        if recent_usage else 0.)
 # Compare against a more stable 10-game player baseline without recent emphasis.
 if not recent_usage:
  baseline,_=_weighted(history[:10],asof,"value",half_life=365.)
  rv=baseline if baseline is not None else prior
  share=.35
 mean=max(0.,share*rv+(1.-share)*prior)
 return mean,{"player_recent_mean":rv,"player_recent_games":len(recent),
       "player_recent_weight":share,"role_prior":prior,
       "role_prior_effective_n":eff,"player_last_team":team}

def predict(state,*,stat,player_id,position,team,opponent,
            asof,variant="full"):
 """Compute one score before any 2024 outcome is available."""
 if stat not in VOLUME_MARKETS:raise ValueError("unsupported_or_excluded_market")
 if position not in ROLE_POS[stat]:return None,{"status":"position_market_ineligible"}
 day=_day(asof)
 # No 2024 information may be consumed for features; even late 2024 forecasts
 # use the frozen December 31 2023 model state and as-of.
 if day>CUTOFF:raise ValueError("forecast_asof_after_pre2024_cutoff")
 if not team or not opponent or team==opponent:
  return None,{"status":"invalid_fixture"}
 val,evidence=player_rate(state,stat,str(player_id),position,team,day,
                           recent_usage=variant!="player_long_term")
 if val is None:return None,evidence
 if variant in ("player_only","player_long_term"):
  return val,{**evidence,"team_factor":1.,"ngs_factor":1.,
              "model_variant":variant}
 metric=MARKET_TEAM_METRIC[stat]
 # Tackle opportunities are driven by the OTHER team's offense.
 att_team=opponent if "tackle" in stat else team
 def_team=team if "tackle" in stat else opponent
 ratio,tme=team_metric_ratio(state,metric,att_team,def_team,day)
 if stat in ("targets","receptions","receiving yards") and position=="RB":
  short_ratio,sme=team_metric_ratio(state,"short_rb_targets",att_team,def_team,day)
  if sme["source"]=="pre2024_pbp":ratio*=short_ratio**.25
  evidence["rb_short_target_proxy"]=sme
 if stat in ("targets","receptions","receiving yards") and position=="TE":
  short_ratio,sme=team_metric_ratio(state,"short_pass_attempts",att_team,def_team,day)
  if sme["source"]=="pre2024_pbp":ratio*=short_ratio**.15
  evidence["te_short_pass_proxy"]=sme
 if stat in ("pass attempts","completions","passing yards"):
  neutral_ratio,sme=team_metric_ratio(state,"neutral_passes",att_team,def_team,day)
  if sme["source"]=="pre2024_pbp":ratio*=neutral_ratio**.18
  evidence["neutral_script"]=sme
 ratio=_clip(ratio,.70,1.34)
 ngs,meta=(_ngs_effect(state,stat,str(player_id),day)
           if variant=="full" else (1.,{"ngs_status":"ablation_disabled"}))
 mean=max(0.,val*ratio*ngs)
 if not math.isfinite(mean) or mean>1000:
  return None,{"status":"unreliable_projection"}
 return mean,{**evidence,**tme,**meta,"team_factor":ratio,
      "ngs_factor":ngs,"model_variant":variant,
      "pre2024_training_only":True,
      "2024_status_verified":False,"bookmaker_offer_verified":False,
      "real_checkdown_read_verified":False}

def research_line(state,*,stat,player_id,position,team,asof):
 if stat not in VOLUME_MARKETS:return None
 history=[r for r in state["player"].get((stat,str(player_id)),())
          if _day(r["gameday"])<_day(asof) and r["team"]==team]
 history.sort(key=lambda r:r["gameday"],reverse=True)
 if len(history)<MIN_PLAYER_PRIOR_APPEARANCES:return None
 last5=sorted(float(x["value"]) for x in history[:5])
 m5=median(last5)
 hist=sorted(float(x["value"]) for x in history[:10])
 m10=median(hist)
 ref=MARKET_BASE_PRIOR[stat]
 raw=.65*m5+.25*m10+.10*ref
 return math.floor(max(0.,raw))+.5

def prob_over(mean,line,market,history=None):
 if mean is None or line is None:return None
 if market in COUNT_MARKETS:
  from scipy.stats import nbinom
  k=COUNT_DISPERSION[market]
  return float(nbinom.sf(math.floor(line),k,k/(k+max(1e-8,mean))))
 from scipy.stats import t
 sigma=YARD_SCALE[market]
 return float(t.sf((line-mean)/sigma,df=5))

def rank_research_only(predictions):
 """A research preview, never a sportsbook ranking or bet."""
 return {"production_allowed":False,"sportsbook_lines_verified":False,
    "roster_2024_verified":False,"research_forecasts":len(predictions),
    "top_picks":[], "reason":"synthetic_line_and_2024_roster_unverified_abstain"}
