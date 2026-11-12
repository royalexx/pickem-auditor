"""NFL V5 research-only: ONE latent game scenario feeds all offensive and
defensive player props. No post-hoc QB rewrite; no independent per-market draws.

For every game and every scenario:
  shared tempo/script -> two teams' plays/pass/rush
  -> eligible QB1/team passing allocation -> receiver targets/catches/yards
  -> QB1 completions and passing yards are SUMS from those very catches
  -> QB rush components then finite remaining team rushing pool -> RB carries/yards
  -> opponent defensive tackle events from rushes + completed passes
  -> solo/assisted tackle credits are drawn from those same finite events.

Each factor-profile simulation is internally consistent. If blending profiles,
the caller MUST choose one profile for the entire two-team game/scenario.
Any legacy model remains an independent benchmark, never a source of player-
specific substitutions within the joint scenario. Historical inputs are
retrospective research-only, not independently certified pregame sources.
"""
from __future__ import annotations
import collections,hashlib,math
import numpy as np
from nfl_v4_factor_tuning_model_20261111 import (
    ContextFactorModel as HistoricalFactors, FittedRegressor,
    PROFILES as V4_PROFILES, require, seed)
from nfl_decade_context_v3_model_20261111 import MARKETS13,decay_record
from v25_decade_joint_opportunity import DEFENSE

VERSION="v5_4_player_history_constrained_opportunity_research_20261112"
PROFILES={
 "recent":dict(V4_PROFILES["recent"]),
 "balanced":{"half_life":2.5,"appearances":8,"usage_prior_games":1.8,
             "opponent_strength":1.0,"tackle_exposure":1.0,
             "recency_decay":.92,"ridge":32.},
 "long":dict(V4_PROFILES["long"]),
}
DEFAULT_WEIGHTS=np.array([.15,.70,.15],dtype=float)
STAT_CONTRACT=tuple(MARKETS13)

def as_int(a,n,label):
 a=np.asarray(a)
 require(a.shape==(n,) and np.all(np.isfinite(a)) and
         np.all(a>=0) and np.all(a==np.floor(a)),label+"_invalid_counts")
 return a.astype(np.int64)

def draw_allocation(rng,counts,weights,concentration=45.):
 """One nonnegative multinomial for each scenario, WITH unassigned bucket."""
 counts=np.asarray(counts,dtype=np.int64)
 n=len(counts);k=len(weights)
 require(k>=1 and all(v>=0 for v in weights),"allocation_nonnegative")
 weights=np.asarray(weights,dtype=float)
 require(np.isfinite(weights).all() and weights.sum()>0,"allocation_rates_valid")
 probs=weights/weights.sum()
 concentration=np.maximum(.025,probs*concentration)
 out=np.zeros((k,n),dtype=np.int64)
 for j,nj in enumerate(counts):
  if nj:out[:,j]=rng.multinomial(int(nj),rng.dirichlet(concentration))
 require(np.array_equal(out.sum(axis=0),counts),"allocation_pool_not_conserved")
 return out

def draw_dynamic_allocation(rng,counts,weights_by_scenario,concentration=45.):
 """Conditional allocation with scenario-specific player availability masks."""
 count=np.asarray(counts,dtype=np.int64)
 matrix=np.asarray(weights_by_scenario,dtype=float)
 require(matrix.ndim==2 and matrix.shape[1]==len(count),"dynamic_opportunity_shape")
 require(np.isfinite(matrix).all() and np.all(matrix>=0),"dynamic_opportunity_nonnegative")
 k,n=matrix.shape
 out=np.zeros((k,n),dtype=np.int64)
 for j in range(n):
  prob=matrix[:,j]
  require(prob.sum()>0,"dynamic_no_residual_bucket")
  prob=prob/prob.sum()
  if count[j]:
   allowed=prob>0
   chosen=np.zeros(k,dtype=float)
   chosen[allowed]=rng.dirichlet(np.maximum(.025,prob[allowed]*concentration))
   out[:,j]=rng.multinomial(int(count[j]),chosen)
 require(np.array_equal(out.sum(axis=0),count),"dynamic_opportunity_not_conserved")
 return out

def allocate_historical_moments(rg,pool,expected,concentration,cap_fraction):
 """Protect named prior workloads while retaining ONE finite shared pool.
 Expected row i is history-derived mean opportunities conditional on a sampled
 participation state. The residual category gets everything not assigned.
 """
 pool=np.asarray(pool,dtype=np.int64);n=len(pool)
 expected=np.asarray(expected,dtype=float)
 require(expected.ndim==2 and expected.shape[1]==n and
   np.all(expected>=0) and np.isfinite(expected).all(),
   "historical_allocator_shape_invalid")
 k=expected.shape[0]
 out=np.zeros((k+1,n),dtype=np.int64)
 if k==0:
  out[0]=pool;return out
 cap=np.clip(float(cap_fraction),.01,1.)
 pressure=expected.sum(axis=0)/np.maximum(pool,1)
 active_fraction=np.clip(np.minimum(cap,pressure),0,1)
 named_budget=rg.binomial(pool,active_fraction)
 for j in range(n):
  count=int(named_budget[j])
  if count:
   weights=expected[:,j]
   require(weights.sum()>0,"positive_known_budget_but_zero_expectation")
   weights=weights/weights.sum()
   mask=weights>0
   pp=np.zeros(k)
   pp[mask]=rg.dirichlet(np.maximum(.02,weights[mask]*concentration))
   out[:k,j]=rg.multinomial(count,pp)
 out[k]=pool-out[:k].sum(axis=0)
 require(np.array_equal(out.sum(axis=0),pool),"history_alloc_not_conserved")
 return out

class JointFactorWeights:
 """Three *entire-game* profile choices; no independent prop-level ensemble."""
 def __init__(self):
  self.s=np.zeros(3);self.weeks=0
 def get(self):
  log=np.log(DEFAULT_WEIGHTS)-20*self.s
  w=np.exp(log-np.max(log));w=w/w.sum()
  return .94*w+.06*DEFAULT_WEIGHTS
 def update(self,market_scores):
  # Week-settled macro-market-balanced proper loss. No current labels in input.
  means=[]
  for vals in market_scores.values():
   if vals:
    a=np.asarray(vals,dtype=float)
    require(a.ndim==2 and a.shape[1]==3,"profile_loss_shape")
    means.append(a.mean(axis=0))
  if means:
   x=np.mean(means,axis=0);x=x-x.mean()
   self.s=.9*self.s+.1*x
   self.weeks+=1
 def receipt(self):
  return {"loss_ema":self.s.tolist(),"weeks_prior":self.weeks,
          "weights":self.get().tolist()}
 def restore(self,j):
  self.s=np.asarray(j["loss_ema"],dtype=float);self.weeks=int(j["weeks_prior"])
  require(np.allclose(self.get(),j["weights"],atol=1e-12),
          "factor_state_receipt_mismatch")

class JointGameModel(HistoricalFactors):
 def __init__(self,history,year,week,profile):
  require(profile in PROFILES.values(),"unknown_context_profile")
  super().__init__(history,year,week,profile)
  # Every sufficient statistic below is calculated from strictly BEFORE
  # (year,week) rows. The same population history informs every market.
  require(all(g["season"]<year or (g["season"]==year and g["week"]<week)
          for g in history),"LEAKAGE_historical_priors_current_week")
  self._history_priors=self._fit_historical_pregame_priors()
  self._role_participation=self._fit_participation_history()
  self._roster_coverage=self._fit_roster_coverage()

 def _fit_historical_pregame_priors(self):
  from collections import defaultdict
  sums=defaultdict(float)
  role=defaultdict(lambda:defaultdict(float))
  for g in self.history:
   wt=decay_record(g["season"],g["week"],self.year,self.week,
                   self.profile["half_life"])
   stats=g["players"]
   total_targets=0.
   for p in stats.values():
    r=p["role"];v=p["values"]
    if r in ("WR","TE","RB"):
     tg=float(v.get("targets",0))
     ct=float(v.get("receptions",0))
     yd=float(v.get("receiving yards",0))
     total_targets+=tg
     role[r]["t"]+=wt*tg;role[r]["c"]+=wt*ct
     role[r]["y"]+=wt*yd
     sums["catch_targets"]+=wt*tg
     sums["catch_receptions"]+=wt*ct
     sums["recv_yards"]+=wt*yd
   sums["team_pass"]+=wt*max(0,float(g["pass_attempts"]))
   sums["named_targets"]+=wt*total_targets
   op=self.allhist.get((g["event_id"],g["opponent"]))
   if op:
    # Approximate two credited assisted tackles per event, with explicit
    # future latent auxiliary pool for omitted special-team/stat events.
    solo=sum(float(p["values"].get("solo tackles",0))
        for p in stats.values() if p["role"] in DEFENSE)
    assist=sum(float(p["values"].get("tackle assists",0))
        for p in stats.values() if p["role"] in DEFENSE)
    oppcatch=sum(float(p["values"].get("completions",0))
        for p in op["players"].values() if p["role"]=="QB")
    eligible=max(0.,float(op["rush_attempts"])+oppcatch)
    sums["def_solo"]+=wt*solo
    sums["def_assist_events"]+=wt*.5*assist
    sums["def_scrimmage"]+=wt*eligible
    sums["def_team_games"]+=wt
    sums["missing_tackle_events"]+=wt*max(0.,solo+.5*assist-eligible)
  rec=sums["catch_receptions"]
  rolepri={}
  for r,z in role.items():
   rolepri[r]={"catch":float(np.clip((z["c"]+12*.64)/(z["t"]+12),.42,.90)),
    "yards_per_catch":float(np.clip((z["y"]+30*10.5)/(z["c"]+30),4,22))}
  tackles=sums["def_solo"]+sums["def_assist_events"]
  return {
   "source_max_year_week":max((g["season"],g["week"]) for g in self.history),
   "rec_target_rate":float(np.clip((sums["named_targets"]+40*.87)/
     (sums["team_pass"]+40),.65,.98)),
   "catch_rate":float(np.clip((rec+30*.65)/(sums["catch_targets"]+30),.42,.90)),
   "yards_per_catch":float(np.clip((sums["recv_yards"]+30*11.)/(rec+30),5.,24.)),
   "def_solo_event_fraction":float(np.clip((sums["def_solo"]+20*.78)/
      (tackles+20),.40,.95)),
   "def_tackle_conversion":float(np.clip((tackles+20*.85)/
      (sums["def_scrimmage"]+20),.50,.98)),
   "extra_tackle_events_per_game":float(np.clip(
      sums["missing_tackle_events"]/max(1,sums["def_team_games"]),0,16)),
   "role":rolepri,
   "historical_games":len(self.history)}

 def _fit_participation_history(self):
  from collections import defaultdict
  groups=defaultdict(lambda:[0.,0.])
  past=defaultdict(list)
  # History is sorted by week for each team. Current-game participation is
  # never part of this training calculation.
  for g in sorted(self.history,key=lambda x:(x["season"],x["week"],x["team"])):
   team=g["team"];pre=past[team]
   if len(pre)>=2:
    last4=pre[-4:]
    recent_candidates={}
    for h in pre[-2:]:
     for pid,p in h["players"].items():
      if p["role"] in ("WR","TE","RB") or p["role"] in DEFENSE:
       recent_candidates[pid]=p["role"]
    appeared=set(g["players"])
    wt=decay_record(g["season"],g["week"],self.year,self.week,
                    self.profile["half_life"])
    for pid,r in recent_candidates.items():
     recent=sum(pid in h["players"] for h in last4)
     last=int(pid in last4[-1]["players"])
     key=(r,last,min(4,recent))
     groups[key][0]+=wt*int(pid in appeared)
     groups[key][1]+=wt
   pre.append(g)
  return groups

 def _participation_probability(self,pid,role,recent):
  if not recent:return .5
  count=sum(pid in g["players"] for g in recent)
  last=int(pid in recent[-1]["players"])
  row=self._role_participation.get((role,last,min(4,count)),(0.,0.))
  # Role-conditional historical estimator with weak finite-sample pooling.
  prior=.88 if last else .30
  return float(np.clip((row[0]+12*prior)/(row[1]+12),.05,.995))

 def _fit_roster_coverage(self):
  from collections import defaultdict
  seen=defaultdict(list)
  known_t=total_t=known_def=total_def=known_rb=total_rb=0.
  for g in sorted(self.history,key=lambda x:(x["season"],x["week"],x["team"])):
   old=seen[g["team"]]
   if len(old)>=2:
    candidate=set().union(*(set(x["players"]) for x in old[-2:]))
    wt=decay_record(g["season"],g["week"],self.year,self.week,
                   self.profile["half_life"])
    for pid,p in g["players"].items():
     v=p["values"];role=p["role"]
     if role in ("WR","TE","RB"):
      x=max(0,float(v.get("targets",0)))
      total_t+=wt*x
      if pid in candidate:known_t+=wt*x
     if role=="RB":
      x=max(0,float(v.get("carries",0)))
      total_rb+=wt*x
      if pid in candidate:known_rb+=wt*x
     if role in DEFENSE:
      x=max(0,float(v.get("solo tackles",0)))+max(0,float(v.get("tackle assists",0)))
      total_def+=wt*x
      if pid in candidate:known_def+=wt*x
   old.append(g)
  return {"targets":float(np.clip((known_t+10*.90)/(total_t+10),.30,.995)),
    "carries":float(np.clip((known_rb+10*.90)/(total_rb+10),.30,.995)),
    "defense":float(np.clip((known_def+10*.90)/(total_def+10),.30,.995)),
    "historical_only":True}

 def _history_player_rate(self,pid,role,market,team):
  # Player's PRIOR appearances only. No target-week outcomes.
  rows=self._last(pid,market,team)
  if not rows:return 0.
  num=den=0.
  for g,p in rows:
   w=decay_record(g["season"],g["week"],self.year,self.week,
                  self.profile["half_life"])
   if market=="targets":
    exp=float(g["pass_attempts"])
   elif market=="carries":
    qb_carries=sum(float(z["values"].get("qb rushing attempts",
      z["values"].get("carries",0)))
      for z in g["players"].values() if z["role"]=="QB")
    exp=max(1.,float(g["rush_attempts"])-qb_carries)
   else:
    exp=float(g["pass_attempts"]+g["rush_attempts"])
    previous=self.allhist.get((g["event_id"],g["opponent"]))
    if previous:
     exp=float(previous["pass_attempts"]+previous["rush_attempts"])
   if exp<=0:continue
   den+=w*exp
   num+=w*float(p["values"].get(market,0))
  if den<=0:return 0.
  prior=float(self._role_prior(role,market,0))
  default_exp=40. if market=="targets" else 23. if market=="carries" else 62.
  prior_rate=max(0.,prior/default_exp)
  # Stable role histories dominate: avoid shrinking an eight-game starter
  # toward a position mean that hides his actual workload.
  pseudo=(.30 if len(rows)>=3 else 1.25)*default_exp
  return float(np.clip((num+pseudo*prior_rate)/(den+pseudo),0,.96))

 def _catch_prior(self,role):
  return self._history_priors["role"].get(role,{}).get(
    "catch",self._history_priors["catch_rate"])

 def _gain_per_catch(self,rg,pid,n):
  obs=self._last(pid,"receiving yards")
  rates=[float(p["values"]["receiving yards"])/float(p["values"]["receptions"])
         for g,p in obs if p["values"].get("receptions",0)>0 and
         "receiving yards" in p["values"]]
  if not rates:return rg.normal(self._history_priors["yards_per_catch"],4.,n).clip(-8,38)
  history=np.asarray(rates,dtype=float)
  base=rg.choice(np.clip(history,-10,35),size=n)
  return np.clip(base+rg.standard_t(5,size=n)*2.5,-12,55)

 def _gain_per_carry(self,rg,pid,n):
  obs=self._last(pid,"rushing yards")
  rates=[float(p["values"]["rushing yards"])/float(p["values"]["carries"])
         for g,p in obs if p["values"].get("carries",0)>0 and "rushing yards" in p["values"]]
  if not rates:return np.clip(rg.normal(4.,2.5,n),-8,24)
  base=rg.choice(np.clip(np.asarray(rates,dtype=float),-8,22),n)
  return np.clip(base+rg.standard_t(5,size=n)*1.8,-12,40)

 def _defender_weights(self,team,player_ids):
  # Rates per opponent offensive play; all learned strictly before this game.
  pool=[]
  for pid in player_ids:
   obs=self._last(pid,"tackles + assists")
   num=0.;den=0.
   for g,p in obs:
    previous=self.allhist.get((g["event_id"],g["opponent"]))
    exposure=(previous["pass_attempts"]+previous["rush_attempts"]) if previous else 62.
    if exposure<10:continue
    num+=max(0,float(p["values"]["tackles + assists"]))
    den+=exposure
   # Prior defense player rate is shrunk toward a role mean.
   role=self.byplayer[pid][-1][1]["role"]
   peer=self._role_prior(role,"tackles + assists",3.)/62.
   rate=(num+4*62*peer)/(den+4*62)
   pool.append(float(np.clip(rate,.001,.32)))
  if not pool:return np.asarray([1.0])
  # Extra bucket represents players not present in last-two-games roster.
  left=max(.08,.16*sum(pool))
  return np.r_[pool,left]

 def _team_roster(self,team,qb1):
  candidate={}
  for g in self.byteam.get(team,[])[-2:]:
   for pid,p in g["players"].items():candidate[pid]=p["role"]
  # A QB1 must be a verified pregame selector identity AND in prior roster.
  activeqb=qb1 if qb1 is not None and candidate.get(qb1)=="QB" else None
  skill={pid:role for pid,role in candidate.items() if role in ("WR","TE","RB")}
  defense={pid:role for pid,role in candidate.items() if role in DEFENSE}
  recent=self.byteam.get(team,[])[-4:]
  last=recent[-1]["players"] if recent else {}
  participation={}
  for pid in set(skill)|set(defense):
   appeared=sum(pid in g["players"] for g in recent)
   in_last=pid in last
   # Prior-only role/appearance uncertainty; no current-game roster oracle.
   participation[pid]=self._participation_probability(pid,
      candidate[pid],recent)
  return {"qb1":activeqb,"skill":skill,"defense":defense,
          "participation":participation}

 def forecast_game(self,gid,home,away,qualified_qb1,n=128,pbp_model=None,return_state=False):
  require(128<=n<=1024,"joint_draw_count")
  require(home!=away,"duplicate_teams")
  # EXACTLY ONE call. All team / player variables below use this frozen object.
  env=self._sample_environment(gid,home,away,n)
  rg=np.random.default_rng(seed(VERSION,self.year,self.week,gid,
      self.profile["half_life"],"one_game_opportunity"))
  teams=(home,away)
  rosters={team:self._team_roster(team,qualified_qb1.get(team)) for team in teams}
  draws={};meta={};states={};game_participation={}
  # Offensive passes, targets, catches and rushing allocation for BOTH teams
  # must finish before any defense receives tackle exposures.
  for team in teams:
   e=env[team];roster=rosters[team];qb=roster["qb1"]
   skill=roster["skill"];rbs=[pid for pid,role in skill.items() if role=="RB"]
   pass_pool=as_int(e["pass"],n,"team_pass_attempts")
   rush_pool=as_int(e["rush"],n,"team_rush_attempts")
   participation={pid:(rg.random(n)<prob)
       for pid,prob in roster["participation"].items()}
   game_participation[team]=participation
   for pid in skill:
    draws[team,pid]={}
   for pid in roster["defense"]:draws[team,pid]={}
   if qb is not None:draws[team,qb]={}
   qb_pass=np.zeros(n,dtype=np.int64)
   if qb is not None:
    obs=[(g,p) for g,p in self._last(qb,"pass attempts")
         if g["pass_attempts"]>0]
    p_attempt=sum(float(p["values"]["pass attempts"]) for g,p in obs)
    t_attempt=sum(g["pass_attempts"] for g,p in obs)
    # 28 effective prior attempts centered on starter share 93%, not 50%.
    share=float(np.clip((p_attempt+28*.93)/(t_attempt+28) if t_attempt else .93,.40,.995))
    qprob=rg.beta(1+60*share,1+60*(1-share),size=n)
    qb_pass=rg.binomial(pass_pool,qprob)
   nonstarter_pass=pass_pool-qb_pass
   # Receiver set is one team pool shared by both passer classes.
   ids=list(skill)
   rates=np.asarray([self._history_player_rate(pid,skill[pid],
        "targets",team) for pid in ids],dtype=float)
   # The same history that estimates individual workload also estimates how
   # much usage is absent from prior two-game rosters.
   retained=self._roster_coverage["targets"]
   # Throwaways and unmatched recipients are explicit non-player pools.
   tprior=self._history_priors["rec_target_rate"]
   target_frac=rg.beta(80*tprior,80*(1-tprior),n)
   qb_target_pool=rg.binomial(qb_pass,target_frac)
   other_target_pool=rg.binomial(nonstarter_pass,target_frac)
   expected_named=(
     rates[:,None]*np.asarray(pass_pool[None,:],dtype=float))
   for i,pid in enumerate(ids):
    expected_named[i]*=participation[pid]
   # QB1 and relief QB route opportunities compete for exactly the SAME
   # receivers; conservatively divide desired counts by their passer share.
   ratio=qb_pass/np.maximum(pass_pool,1)
   target_qb=allocate_historical_moments(rg,qb_target_pool,
       expected_named*ratio[None,:],65.,retained)
   target_other=allocate_historical_moments(rg,other_target_pool,
       expected_named*(1-ratio)[None,:],65.,retained)
   team_completions=np.zeros(n,dtype=np.int64)
   qb_completions=np.zeros(n,dtype=np.int64)
   team_pass_yards=np.zeros(n,dtype=np.float64)
   qb_pass_yards=np.zeros(n,dtype=np.float64)
   player_receiving_yards=np.zeros(n,dtype=np.int64)
   qb1_player_receiving_yards=np.zeros(n,dtype=np.int64)
   for index,pid in enumerate(ids):
    target0=target_qb[index];target1=target_other[index]
    obs=self._last(pid,"receptions")
    catches=sum(float(p["values"].get("receptions",0)) for g,p in obs)
    prior_targets=sum(float(p["values"].get("targets",0)) for g,p in obs)
    hist_rate=self._catch_prior(skill[pid])
    strength=12.
    rate=rg.beta(strength*hist_rate+catches,
       strength*(1-hist_rate)+max(0,prior_targets-catches),size=n)
    c0=rg.binomial(target0,rate)
    c1=rg.binomial(target1,rate)
    counts=c0+c1
    # Same player gain parameter for both QB1 and any unmodeled passer.
    gain=self._gain_per_catch(rg,pid,n)
    yards0=np.rint(gain*c0).astype(np.int64)
    yards1=np.rint(gain*c1).astype(np.int64)
    draws[team,pid].update({"targets":target0+target1,
                           "receptions":counts,
                           "receiving yards":yards0+yards1})
    team_completions+=counts
    qb_completions+=c0
    qb_pass_yards+=yards0
    team_pass_yards+=yards0+yards1
    player_receiving_yards+=yards0+yards1
    qb1_player_receiving_yards+=yards0
   # Unlisted / ineligible receivers also catch passes. They are in the
   # accounting but never receive invented named-player forecasts.
   idx=len(ids)
   unknown_qb_targets=target_qb[idx]
   unknown_other_targets=target_other[idx]
   population_rate=self._history_priors["catch_rate"]
   residual_catch=rg.beta(35*population_rate,35*(1-population_rate),n)
   c0=rg.binomial(unknown_qb_targets,residual_catch)
   c1=rg.binomial(unknown_other_targets,residual_catch)
   unknown_yard_rate=np.clip(rg.normal(
      self._history_priors["yards_per_catch"],3.0,n),-10,35)
   uq_yards=np.rint(unknown_yard_rate*c0).astype(np.int64)
   uo_yards=np.rint(unknown_yard_rate*c1).astype(np.int64)
   team_completions+=c0+c1
   qb_completions+=c0
   qb_pass_yards+=uq_yards
   team_pass_yards+=uq_yards+uo_yards
   if qb is not None:
    draws[team,qb]["pass attempts"]=qb_pass
    draws[team,qb]["completions"]=qb_completions
    draws[team,qb]["passing yards"]=qb_pass_yards
   # QB rushing component is drawn BEFORE assigning a single RB carry.
   qb_rush=np.zeros(n,dtype=np.int64);qb_rush_yards=np.zeros(n,dtype=np.float64)
   if qb is not None and pbp_model is not None:
    component=pbp_model.draw(qb,n=n,
      seed=seed(VERSION,self.year,self.week,gid,team,"qb_rush"),
      dropback_samples=qb_pass)
    initial=as_int(component["qb_rushing_attempts"],n,"qb_rush_component")
    qb_rush=np.minimum(initial,rush_pool)
    scale=qb_rush/np.maximum(initial,1)
    qb_rush_yards=np.rint(np.asarray(component["qb_rushing_yards"],dtype=float)*scale)
   if qb is not None:
    draws[team,qb]["qb rushing attempts"]=qb_rush
    draws[team,qb]["qb rushing yards"]=qb_rush_yards
   remaining_rush=rush_pool-qb_rush
   rbpool=rg.binomial(remaining_rush,rg.beta(24,4,n))
   cr=np.asarray([self._history_player_rate(pid,"RB","carries",team)
     for pid in rbs],dtype=float)
   active_rb_expected=cr[:,None]*np.asarray(remaining_rush[None,:],dtype=float)
   for i,pid in enumerate(rbs):active_rb_expected[i]*=participation[pid]
   carries=allocate_historical_moments(rg,rbpool,active_rb_expected,45.,
       self._roster_coverage["carries"])
   for i,pid in enumerate(rbs):
    cc=carries[i]
    gain=self._gain_per_carry(rg,pid,n)
    draws[team,pid]["carries"]=cc
    draws[team,pid]["rushing yards"]=np.rint(cc*gain).astype(np.int64)
   unassigned_carries=remaining_rush-carries[:len(rbs)].sum(axis=0)
   # Omitted special-team / nonstandard-credit events are a separate latent
   # team exposure class fitted ONLY from prior games; they are not fabricated
   # pass completions and never added to the offensive play count.
   aux_mu=self._history_priors["extra_tackle_events_per_game"]
   auxiliary=rg.poisson(aux_mu*np.clip(
       np.asarray(e["plays"],dtype=float)/62.,.5,1.8))
   states[team]={
    "auxiliary_credited_tackle_opportunities":auxiliary,
    "plays":as_int(e["plays"],n,"team_plays"),
    "pass_attempts":pass_pool,"rush_attempts":rush_pool,
    "qb1_attempts":qb_pass,"nonstarter_attempts":nonstarter_pass,
    "qb1_completions":qb_completions,"team_completions":team_completions,
    "qb1_passing_yards":qb_pass_yards,
    "team_passing_yards":team_pass_yards,
    "known_receiving_yards":player_receiving_yards,
    "unassigned_receiving_yards":uq_yards+uo_yards,
    "qb1_known_receiving_yards":qb1_player_receiving_yards,
    "qb1_unassigned_receiving_yards":uq_yards,
    "known_targets":target_qb[:len(ids)].sum(axis=0)+target_other[:len(ids)].sum(axis=0),
    "unassigned_targets":unknown_qb_targets+unknown_other_targets,
    "team_target_count":qb_target_pool+other_target_pool,
    "known_receptions":team_completions-(c0+c1),
    "unassigned_receptions":c0+c1,
    "qb1_rush_attempts":qb_rush,
    "known_rb_carries":carries[:len(rbs)].sum(axis=0),
    "unassigned_carries":unassigned_carries,
    "qb1_rushing_yards":qb_rush_yards,
    "eligible_qb1":qb,
    "source_roster_skill_count":len(ids),
    "source_roster_defender_count":len(roster["defense"]),
    "scenario_active_skill_count":sum((participation[pid].astype(int) for pid in skill),
                                       np.zeros(n,dtype=int)),
    "scenario_active_defender_count":sum((participation[pid].astype(int)
      for pid in roster["defense"]),np.zeros(n,dtype=int)),
   }
   meta[team]={
    "qb1":qb,"qualified_qb_in_candidates":qb is not None,
    "source_selection_unverified":True,
    "game_shared_plays_average":float(np.mean(e["plays"])),
    "game_shared_pass_attempt_average":float(np.mean(pass_pool)),
    "opponent_projected_plays_average":float(np.mean(e["opponent_plays"])),
    "team_rush_average":float(np.mean(rush_pool)),
    "joint_game_model":VERSION,
    "single_shared_game_state":True,
    "historical_prior_profile":dict(self.profile),
    "historical_factors":self._history_priors,
    "historical_two_game_roster_coverage":self._roster_coverage,
   }
  # The sole defensive tackle opportunities come from the OTHER OFFENSE'S
  # scenario-level rushing plays and completed passes.
  for team in teams:
   opponent=away if team==home else home
   off=states[opponent]
   exposed_rush=off["rush_attempts"]
   exposed_catches=off["team_completions"]
   # All credited events are tied to the OTHER offense's single game state.
   # Historical other-event budget accounts for sources not represented by
   # our coarsened rush/catch opportunities (e.g. special teams).
   supplemental=off["auxiliary_credited_tackle_opportunities"]
   conversion=self._history_priors["def_tackle_conversion"]
   tackleable_rush=rg.binomial(exposed_rush,conversion)
   tackleable_catches=rg.binomial(exposed_catches,conversion)
   supplemental_used=rg.binomial(supplemental,conversion)
   raw_events=tackleable_rush+tackleable_catches+supplemental_used
   # Prior tackle-exposure factor changes only the probability of recording
   # an event, not the already-frozen opponent offensive opportunity pool.
   factor=float(self.profile["tackle_exposure"])
   baseline=.5*(.91+.92)
   if factor<1:
    used=rg.binomial(raw_events,np.clip(factor,0,1))
   else:
    remaining=np.maximum(0,exposed_rush+exposed_catches+supplemental-raw_events)
    used=raw_events+rg.binomial(remaining,min(1.,(factor-1)*baseline))
   assisted_fraction=1-self._history_priors["def_solo_event_fraction"]
   assists=rg.binomial(used,assisted_fraction)
   solos=used-assists
   defender_ids=list(rosters[team]["defense"])
   defender_presence={pid:game_participation[team][pid]
      for pid in defender_ids}
   rolemap=rosters[team]["defense"]
   solo_rates=np.asarray([self._history_player_rate(pid,rolemap[pid],
      "solo tackles",team) for pid in defender_ids],dtype=float)
   assist_rates=np.asarray([self._history_player_rate(pid,rolemap[pid],
      "tackle assists",team) for pid in defender_ids],dtype=float)
   exposure=np.asarray(off["plays"],dtype=float)
   solo_expected=solo_rates[:,None]*exposure[None,:]
   assist_expected=assist_rates[:,None]*exposure[None,:]
   for i,pid in enumerate(defender_ids):
    solo_expected[i]*=defender_presence[pid]
    assist_expected[i]*=defender_presence[pid]
   solo_credit=allocate_historical_moments(rg,solos,solo_expected,65.,
      self._roster_coverage["defense"])
   assist_credit=np.zeros_like(solo_credit)
   # A tackle event yields 0/1 credited solo or TWO distinct assisted
   # credits. Unknown/unselected defenders remain a residual category.
   for j in range(n):
    for _ in range(int(assists[j])):
     # Probability of named credit follows prior credited-assist history.
     # Zeroing a sampled nonparticipant never reallocates fictitious snaps.
     desires=assist_expected[:,j]
     total_needed=2*int(assists[j])
     residual=max(1e-6,total_needed*max(0.,1-self._roster_coverage["defense"]))
     weights=np.r_[desires,residual]
     weights=weights/weights.sum()
     prob=np.zeros(len(weights),dtype=float)
     allowed0=weights>0
     prob[allowed0]=rg.dirichlet(np.maximum(.025,weights[allowed0]*65))
     first=int(rg.choice(len(weights),p=prob))
     allowed=prob.copy()
     if first<len(defender_ids):allowed[first]=0
     allowed/=allowed.sum()
     second=int(rg.choice(len(weights),p=allowed))
     assist_credit[first,j]+=1
     assist_credit[second,j]+=1
   for k,pid in enumerate(defender_ids):
    solo=solo_credit[k]
    assist=assist_credit[k]
    draws[team,pid].update({
      "solo tackles":solo,
      "tackle assists":assist,
      "tackles + assists":solo+assist})
   states[team].update({
     "opponent_plays":states[opponent]["plays"],
     "opponent_pass_attempts":states[opponent]["pass_attempts"],
     "opponent_rush_attempts":states[opponent]["rush_attempts"],
     "opponent_completions":states[opponent]["team_completions"],
     "opponent_auxiliary_credit_opportunities":supplemental,
     "defensive_eligible_events":exposed_rush+exposed_catches+supplemental,
     "defensive_tackle_events":used,
     "solo_event_budget":solos,
     "assisted_event_budget":assists,
     "credited_solos":solo_credit[:len(defender_ids)].sum(axis=0),
     "credited_assists":assist_credit[:len(defender_ids)].sum(axis=0),
     "unassigned_solo":solo_credit[len(defender_ids)],
     "unassigned_assist":assist_credit[len(defender_ids)],
   })
  validate_joint_state(states,draws,teams,n)
  # Drop fields that would identify unavailable actual pregame participation.
  if return_state:return draws,meta,states
  return draws,meta

def validate_joint_state(states,draws,teams,n):
 require(len(teams)==2 and len(set(teams))==2,"invalid_two_team_game")
 for team in teams:
  a=states[team];opp=states[teams[1] if team==teams[0] else teams[0]]
  for k,val in a.items():
   if isinstance(val,np.ndarray):
    require(val.shape==(n,) and np.isfinite(val).all(),"state_nonfinite_"+k)
  def eq(x,y,label):
   require(np.array_equal(x,y),"joint_conservation_"+label)
  def leq(x,y,label):
   require(np.all(x<=y),"joint_exposure_limit_"+label)
  eq(a["plays"],a["pass_attempts"]+a["rush_attempts"],"team_plays")
  eq(a["qb1_attempts"]+a["nonstarter_attempts"],a["pass_attempts"],"qb_attempt_pool")
  leq(a["qb1_completions"],a["qb1_attempts"],"qb_completions")
  leq(a["team_completions"],a["pass_attempts"],"team_completions")
  leq(a["team_target_count"],a["pass_attempts"],"team_targets")
  eq(a["known_targets"]+a["unassigned_targets"],a["team_target_count"],"target_allocation")
  eq(a["known_receptions"]+a["unassigned_receptions"],a["team_completions"],"catch_allocation")
  eq(a["known_receiving_yards"]+a["unassigned_receiving_yards"],
     a["team_passing_yards"],"team_passing_yards")
  eq(a["qb1_known_receiving_yards"]+a["qb1_unassigned_receiving_yards"],
     a["qb1_passing_yards"],"qb1_passing_yards")
  leq(a["team_completions"],a["team_target_count"],"catches")
  eq(a["qb1_rush_attempts"]+a["known_rb_carries"]+a["unassigned_carries"],
     a["rush_attempts"],"rush_allocation")
  eq(a["opponent_plays"],opp["plays"],"defensive_opponent_plays")
  eq(a["opponent_rush_attempts"],opp["rush_attempts"],"defensive_opponent_rush")
  eq(a["opponent_completions"],opp["team_completions"],"defensive_opponent_catches")
  eq(a["opponent_auxiliary_credit_opportunities"],
     opp["auxiliary_credited_tackle_opportunities"],"defense_auxiliary_opponent")
  eq(a["defensive_eligible_events"],
     opp["rush_attempts"]+opp["team_completions"]+
     opp["auxiliary_credited_tackle_opportunities"],"tackle_opportunities")
  eq(a["defensive_tackle_events"],
     a["solo_event_budget"]+a["assisted_event_budget"],"tackle_events")
  leq(a["defensive_tackle_events"],a["defensive_eligible_events"],"tackle_event_cap")
  eq(a["credited_solos"]+a["unassigned_solo"],
     a["solo_event_budget"],"solo_credits")
  eq(a["credited_assists"]+a["unassigned_assist"],
     2*a["assisted_event_budget"],"assisted_credits")
  receivers=[v for (t,p),v in draws.items() if t==team and "targets" in v]
  if receivers:
   targets=sum((v["targets"] for v in receivers),np.zeros(n,dtype=int))
   catches=sum((v["receptions"] for v in receivers),np.zeros(n,dtype=int))
   yards=sum((v["receiving yards"] for v in receivers),np.zeros(n,dtype=int))
   eq(targets,a["known_targets"],"player_targets")
   eq(catches,a["known_receptions"],"player_catches")
   eq(yards,a["known_receiving_yards"],"named_receiver_yards")
   for v in receivers:leq(v["receptions"],v["targets"],"player_catch_cap")
  backs=[v for (t,p),v in draws.items() if t==team and "carries" in v]
  if backs:eq(sum((v["carries"] for v in backs),np.zeros(n,dtype=int)),
              a["known_rb_carries"],"rb_carries")
  defenders=[v for (t,p),v in draws.items() if t==team and "solo tackles" in v]
  if defenders:
   eq(sum((v["solo tackles"] for v in defenders),np.zeros(n,dtype=int)),
       a["credited_solos"],"defender_solos")
   eq(sum((v["tackle assists"] for v in defenders),np.zeros(n,dtype=int)),
       a["credited_assists"],"defender_assists")
   for v in defenders:eq(v["tackles + assists"],
                          v["solo tackles"]+v["tackle assists"],"defender_components")
  qb=a["eligible_qb1"]
  if qb is not None:
   q=draws[team,qb]
   eq(q["pass attempts"],a["qb1_attempts"],"qb_named_attempts")
   eq(q["completions"],a["qb1_completions"],"qb_named_completions")
   eq(q["passing yards"],a["qb1_passing_yards"],"qb_named_yards")
   eq(q["qb rushing attempts"],a["qb1_rush_attempts"],"qb_named_rush")
   eq(q["qb rushing yards"],a["qb1_rushing_yards"],"qb_named_rush_yards")
   leq(q["qb rushing attempts"],a["rush_attempts"],"qb_rush_cap")

def serializable_game_state(states):
 return {team:{k:(v.tolist() if isinstance(v,np.ndarray) else v)
                for k,v in a.items()} for team,a in states.items()}
