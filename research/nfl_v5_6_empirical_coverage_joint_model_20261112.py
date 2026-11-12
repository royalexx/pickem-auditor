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
from nfl_decade_context_v3_model_20261111 import MARKETS13
from v25_decade_joint_opportunity import DEFENSE

VERSION="v5_6_empirical_prior_roster_continuity_joint_research_20261112"
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
  self.historical_factors=self._fit_prior_opportunities()
  self.historical_coverage=self._fit_prior_roster_coverage()
  self.participation_rates=self._fit_prior_role_transitions()

 def _fit_prior_opportunities(self):
  """All rate numerators and denominators come from *strictly past* games."""
  from nfl_decade_context_v3_model_20261111 import decay_record,asof
  require(all(asof(g,self.year,self.week) for g in self.history),
          "opportunity_calibration_future_game")
  sums=collections.defaultdict(float)
  for g in self.history:
   weight=decay_record(g["season"],g["week"],self.year,self.week,
                       self.profile["half_life"])
   players=g["players"].values()
   targets=sum(float(p["values"].get("targets",0)) for p in players)
   receptions=sum(float(p["values"].get("receptions",0)) for p in players)
   passatt=max(0.,float(g["pass_attempts"]))
   sums["pass"]+=weight*passatt
   sums["targets"]+=weight*targets
   sums["receptions"]+=weight*receptions
   opp=self.allhist.get((g["event_id"],g["opponent"]))
   if opp is not None:
    eligible=float(opp["rush_attempts"])+sum(
       float(p["values"].get("receptions",0)) for p in opp["players"].values())
    if eligible>=15:
     sums["eligible_events"]+=weight*eligible
     sums["solo"]+=weight*sum(float(p["values"].get("solo tackles",0))
                                     for p in g["players"].values())
     sums["assists"]+=weight*sum(float(p["values"].get("tackle assists",0))
                                        for p in g["players"].values())
  # Population priors are ONLY used in no/low-history cases; never replaced
  # with the current slate's observed team attempts or actual event counts.
  ratio=lambda a,b,default:float(sums[a]/sums[b]) if sums[b]>0 else default
  target=float(np.clip(ratio("targets","pass",.965),.80,.998))
  catch=float(np.clip(ratio("receptions","targets",.64),.45,.82))
  solo=float(np.clip(ratio("solo","eligible_events",.81),.55,.94))
  assisted=float(np.clip(ratio("assists","eligible_events",.35)/2,.04,.35))
  if solo+assisted>.995:
   scale=.995/(solo+assisted);solo*=scale;assisted*=scale
  return {"target_attempt_ratio":target,"catch_target_rate":catch,
          "solo_event_rate":solo,"assisted_event_rate":assisted,
          "training_end_exclusive":[self.year,self.week],
          "prior_team_game_rows":len(self.history)}

 def _fit_prior_roster_coverage(self):
  """Estimate which share of next-game official opportunities is attributable
  to the roster known from the previous TWO games, using PAST games only.

  This is a prediction-feature prior, not postgame knowledge of current
  participation. The current game and its synthetic contract universe never
  enter this estimator.
  """
  from nfl_decade_context_v3_model_20261111 import decay_record,asof
  source=collections.defaultdict(lambda:[0.,0.,0])
  for team,games in self.byteam.items():
   for i in range(2,len(games)):
    game=games[i]
    require(asof(game,self.year,self.week),"roster_coverage_future_game")
    past_ids=set(games[i-1]["players"])|set(games[i-2]["players"])
    decay=decay_record(game["season"],game["week"],self.year,self.week,
                       self.profile["half_life"])
    groups={"targets":("WR","TE","RB"),"carries":("RB",),
            "solo tackles":tuple(DEFENSE),"tackle assists":tuple(DEFENSE)}
    for market,roles in groups.items():
     all_value=sum(float(p["values"].get(market,0))
                   for p in game["players"].values() if p["role"] in roles)
     if all_value<=0:continue
     known_value=sum(float(p["values"].get(market,0))
         for pid,p in game["players"].items()
         if pid in past_ids and p["role"] in roles)
     s=source[market];s[0]+=decay*known_value
     s[1]+=decay*all_value;s[2]+=1
  out={}
  for market,alias in (("targets","receiver_target"),("carries","rb_carry"),
     ("solo tackles","defensive_solo"),("tackle assists","defensive_assist")):
   known,total,n=source[market]
   require(n>=30 and total>0,"insufficient_historical_roster_coverage")
   out[alias]=float(np.clip((known+2)/(total+4),.35,.99))
  out["training_end_exclusive"]=[self.year,self.week]
  out["past_games_by_market"]={market:int(v[2]) for market,v in source.items()}
  return out

 @staticmethod
 def _reconcile_residual_share(weights_by_scenario,coverage):
  """The last row is an explicit unknown-person opportunity category.
  It is reweighted relative to the *active prior roster*, never raw stat
  outcomes. This makes the expected known/unknown split historical.
  """
  matrix=np.asarray(weights_by_scenario,dtype=float).copy()
  require(matrix.ndim==2 and matrix.shape[0]>=1,
          "invalid_historical_residual_matrix")
  if matrix.shape[0]==1:
   matrix[0,:]=1.
   return matrix
  known=matrix[:-1].sum(axis=0)
  prior=float(np.clip(coverage,.01,.995))
  matrix[-1,:]=np.where(known>1e-10,
        known*(1-prior)/prior,1.)
  return matrix

 def _fit_prior_role_transitions(self):
  """Historical next-game appearance frequencies learned before forecast week.
  Current target game's actual starters, snap counts and labels are prohibited.
  """
  from nfl_decade_context_v3_model_20261111 import decay_record
  counts=collections.defaultdict(lambda:[0.,0.])
  for team,games in self.byteam.items():
   for i in range(2,len(games)):
    current=games[i]
    wt=decay_record(current["season"],current["week"],self.year,
                    self.week,self.profile["half_life"])
    prior0=games[i-1]["players"];prior1=games[i-2]["players"]
    for pid in set(prior0)|set(prior1):
     role=(prior0.get(pid) or prior1.get(pid))["role"]
     if role not in ("WR","TE","RB") and role not in DEFENSE:continue
     pattern=(pid in prior0,pid in prior1)
     rec=counts[role,pattern]
     rec[0]+=wt;rec[1]+=wt*(pid in current["players"])
     pooled=counts["ALL",pattern]
     pooled[0]+=wt;pooled[1]+=wt*(pid in current["players"])
  return {role+"|"+str(int(p0))+str(int(p1)):list(v)
          for (role,(p0,p1)),v in counts.items()}

 def _transition_prob(self,role,last,previous):
  key=role+"|"+str(int(last))+str(int(previous))
  fallback="ALL|"+str(int(last))+str(int(previous))
  # Shrink toward strictly previous-game empirical *global* population.
  total,success=self.participation_rates.get(fallback,(0.,0.))
  pool=(success+2)/(total+4) if total else (.91 if last else .35)
  n,k=self.participation_rates.get(key,(0.,0.))
  return float(np.clip((k+12*pool)/(n+12),.12,.995))


 def _historical_roster_budget(self,team,roles,rg,n):
  """Use previous observed team-game active-roster counts only.
  No same-week participant list enters the simulator.
  """
  rows=self.byteam.get(team,[])[-12:]
  counts=[sum(p["role"] in roles for p in g["players"].values())
          for g in rows]
  if not counts:return np.zeros(n,dtype=int)
  wt=np.asarray([self.profile["recency_decay"]**(len(counts)-1-i)
                 for i in range(len(counts))],dtype=float)
  return rg.choice(np.asarray(counts,dtype=int),size=n,p=wt/wt.sum())

 def _cap_prior_roster(self,team,roster,rg,n):
  """Scenario-level finite roster cap; role groups share one presence vector
  across offense, defense, and all stats for the game.
  """
  presence={pid:rg.random(n)<p for pid,p in roster["participation"].items()}
  groups=(list(roster["skill"]),list(roster["defense"]))
  role_sets=(("WR","TE","RB"),tuple(DEFENSE))
  for ids,roles in zip(groups,role_sets):
   if not ids:continue
   budgets=self._historical_roster_budget(team,roles,rg,n)
   prior_strength=[]
   for pid in ids:
    role=roster["skill"].get(pid) or roster["defense"].get(pid)
    market="targets" if role in ("WR","TE","RB") else "tackles + assists"
    obs=self._last(pid,market,team)
    if obs:
     avg=np.mean([float(p["values"].get(market,0)) for g,p in obs])
    else:avg=0.
    prior_strength.append(float(np.clip(.2+avg, .2, 18.)))
   strength=np.asarray(prior_strength)
   for j in range(n):
    available=[i for i,pid in enumerate(ids) if presence[pid][j]]
    cutoff=int(np.clip(budgets[j],0,len(ids)))
    if len(available)<=cutoff:continue
    # Weighted sampling without replacement, strictly prior usage.
    weights=strength[available];weights=weights/weights.sum()
    selected=set(rg.choice(available,size=cutoff,replace=False,p=weights).tolist())
    for i in available:
     if i not in selected:presence[ids[i]][j]=False
  return presence

 def _gain_per_catch(self,rg,pid,n):
  obs=self._last(pid,"receiving yards")
  rates=[float(p["values"]["receiving yards"])/float(p["values"]["receptions"])
         for g,p in obs if p["values"].get("receptions",0)>0 and
         "receiving yards" in p["values"]]
  if not rates:return rg.normal(9.,4.,n).clip(-8,38)
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
   previous=pid in (recent[-2]["players"] if len(recent)>=2 else {})
   probability=self._transition_prob(candidate[pid],in_last,previous)
   participation[pid]=probability
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
  draws={};meta={};states={};team_player_presence={}
  # Offensive passes, targets, catches and rushing allocation for BOTH teams
  # must finish before any defense receives tackle exposures.
  for team in teams:
   e=env[team];roster=rosters[team];qb=roster["qb1"]
   skill=roster["skill"];rbs=[pid for pid,role in skill.items() if role=="RB"]
   pass_pool=as_int(e["pass"],n,"team_pass_attempts")
   rush_pool=as_int(e["rush"],n,"team_rush_attempts")
   participation=self._cap_prior_roster(team,roster,rg,n)
   team_player_presence[team]=participation
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
   rates=np.asarray([self._share(pid,skill[pid],"targets",team) for pid in ids],dtype=float)
   weights=np.r_[rates,max(.09,.17*float(rates.sum()))] if ids else np.asarray([1.])
   # Throwaways and unmatched recipients are explicit non-player pools.
   # Target probability fitted from historical actual team attempts and
   # recorded player targets, not a hard-coded Beta(22,4)=84.6% prior.
   target_rate=self.historical_factors["target_attempt_ratio"]
   target_p=rg.beta(80*target_rate,80*(1-target_rate),n)
   qb_target_pool=rg.binomial(qb_pass,target_p)
   other_target_pool=rg.binomial(nonstarter_pass,target_p)
   active_weights=np.repeat(weights[:,None],n,axis=1)
   for i,pid in enumerate(ids):active_weights[i]*=participation[pid]
   active_weights=self._reconcile_residual_share(
      active_weights,self.historical_coverage["receiver_target"])
   target_qb=draw_dynamic_allocation(rg,qb_target_pool,active_weights,50)
   target_other=draw_dynamic_allocation(rg,other_target_pool,active_weights,50)
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
    pool_catch=self.historical_factors["catch_target_rate"]
    kappa=12.
    rate=rg.beta(kappa*pool_catch+catches,
                 kappa*(1-pool_catch)+max(0,prior_targets-catches),size=n)
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
   residual_catch=rg.beta(6,4,n)
   c0=rg.binomial(unknown_qb_targets,residual_catch)
   c1=rg.binomial(unknown_other_targets,residual_catch)
   unknown_yard_rate=np.clip(rg.normal(9.0,4.0,n),-10,35)
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
   cr=[self._share(pid,"RB","carries",team) for pid in rbs]
   carry_weights=np.r_[cr,max(.08,.15*float(sum(cr)))] if rbs else np.asarray([1.])
   active_rb_weights=np.repeat(carry_weights[:,None],n,axis=1)
   for i,pid in enumerate(rbs):active_rb_weights[i]*=participation[pid]
   active_rb_weights=self._reconcile_residual_share(
      active_rb_weights,self.historical_coverage["rb_carry"])
   carries=draw_dynamic_allocation(rg,rbpool,active_rb_weights,40)
   for i,pid in enumerate(rbs):
    cc=carries[i]
    gain=self._gain_per_carry(rg,pid,n)
    draws[team,pid]["carries"]=cc
    draws[team,pid]["rushing yards"]=np.rint(cc*gain).astype(np.int64)
   unassigned_carries=remaining_rush-carries[:len(rbs)].sum(axis=0)
   states[team]={
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
    "historical_opportunity_calibration":dict(self.historical_factors),
    "historical_previous_roster_coverage":dict(self.historical_coverage),
   }
  # The sole defensive tackle opportunities come from the OTHER OFFENSE'S
  # scenario-level rushing plays and completed passes.
  for team in teams:
   opponent=away if team==home else home
   off=states[opponent]
   exposed_rush=off["rush_attempts"]
   exposed_catches=off["team_completions"]
   # Calibrate the *event types* from historical defensive credits:
   # each solo event has one credit; assisted events have two distinct credits.
   # All counts share opponent offensive completed/rushing event budget.
   eligible=exposed_rush+exposed_catches
   solo_rate=self.historical_factors["solo_event_rate"]
   assist_rate=self.historical_factors["assisted_event_rate"]
   # Opponent factor changes available event-conversion propensity mildly
   # rather than inventing new opponent plays or exceeding event budget.
   factor=float(self.profile["tackle_exposure"])
   rate_scale=np.clip(1+.18*(factor-1),.90,1.10)
   solo_rate*=rate_scale
   assist_rate*=rate_scale
   if solo_rate+assist_rate>.995:
    fac=.995/(solo_rate+assist_rate);solo_rate*=fac;assist_rate*=fac
   solos=rg.binomial(eligible,solo_rate)
   assists=rg.binomial(eligible-solos,assist_rate/(1-solo_rate))
   used=solos+assists
   defender_ids=list(rosters[team]["defense"])
   mix=self._defender_weights(team,defender_ids)
   available=np.repeat(mix[:,None],n,axis=1)
   defender_presence={pid:team_player_presence[team][pid]
      for pid in defender_ids}
   for i,pid in enumerate(defender_ids):available[i]*=defender_presence[pid]
   available=self._reconcile_residual_share(
      available,.5*(self.historical_coverage["defensive_solo"]+
                    self.historical_coverage["defensive_assist"]))
   solo_credit=draw_dynamic_allocation(rg,solos,available,55)
   assist_credit=np.zeros_like(solo_credit)
   # A tackle event yields 0/1 credited solo or TWO distinct assisted
   # credits. Unknown/unselected defenders remain a residual category.
   for j in range(n):
    for _ in range(int(assists[j])):
     weights=available[:,j]
     base=weights/weights.sum()
     prob=np.zeros(len(mix),dtype=float)
     allowed0=base>0
     prob[allowed0]=rg.dirichlet(np.maximum(.025,base[allowed0]*55))
     first=int(rg.choice(len(mix),p=prob))
     allowed=prob.copy()
     if first<len(defender_ids):allowed[first]=0
     allowed/=allowed.sum()
     second=int(rg.choice(len(mix),p=allowed))
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
     "defensive_eligible_events":exposed_rush+exposed_catches,
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
  eq(a["defensive_eligible_events"],
     opp["rush_attempts"]+opp["team_completions"],"tackle_opportunities")
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
