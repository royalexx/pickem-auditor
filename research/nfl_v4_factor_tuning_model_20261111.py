"""V4 research-only contextual opportunity factor profiles; fixed prior-only update rules.

Two contrasting factor profiles compete with the frozen V3 scenario baseline:
- RECENT: recent player form, stronger role change, damped opponent signal.
- LONG: longer population memory, stronger opponent effects, more role pooling.
No model selection using week being forecast. No production claims.
"""
from __future__ import annotations
import collections,math,hashlib
import numpy as np
from nfl_decade_context_v3_model_20261111 import (
    MatchupRegressor,GameContextModel,OnlineBayesCalibrator,
    require,decay_record,moments,seed,MARKETS13)
PRIOR=np.array([.85,.075,.075])
PROFILES={
 "recent":{"half_life":1.35,"appearances":5,"usage_prior_games":.80,
           "opponent_strength":.65,"tackle_exposure":.65,"recency_decay":.86,
           "ridge":50.},
 "long":{"half_life":5.0,"appearances":12,"usage_prior_games":3.0,
           "opponent_strength":1.35,"tackle_exposure":1.15,"recency_decay":.95,
           "ridge":48.},
}
VERSION="v4_10yr_tunable_history_opportunity_prioronly_research"
def canonical_weights(x):
 z=np.asarray(x,dtype=float)
 require(len(z)==3 and np.all(np.isfinite(z)) and (z>=0).all(),"invalid_ensemble_weights")
 z=z/z.sum()
 return z
class FittedRegressor(MatchupRegressor):
 def __init__(self,history,profile):
  self.profile=profile
  super().__init__(history)
 def fitted(self,year,week):
  rows=[r for r in self.records if r[0]>=max(2014,year-10)
        and (r[0]<year or(r[0]==year and r[1]<week))]
  require(len(rows)>300,"no_prior_matchup_games")
  X=np.asarray([r[2] for r in rows]);play=np.asarray([r[3] for r in rows])
  passes=np.asarray([r[4] for r in rows])
  ages=np.asarray([decay_record(r[0],r[1],year,week,self.profile["half_life"]) for r in rows])
  ages=ages/ages.mean()
  priorplays=np.array([62.,0.,0.,0.,0.,0.])
  priorpass=np.array([.57,0.,0.,0.,0.,0.])
  p=self.profile["ridge"];ridge=np.diag([1.,p,p,p,p,p])
  A=X.T@(ages[:,None]*X)+ridge
  bp=np.linalg.solve(A,X.T@(ages*play)+ridge@priorplays)
  br=np.linalg.solve(A,X.T@(ages*passes)+ridge@priorpass)
  return {"plays":bp,"pass_rate":br,"sd_plays":float(np.sqrt(np.average((play-X@bp)**2,weights=ages))),
    "training_rows":len(rows),"earliest_train_year":min(z[0] for z in rows),
    "latest_train_year_week":(rows[-1][0],rows[-1][1]),
    "ridge":p,"age_half_life_years":self.profile["half_life"]}
class ContextFactorModel(GameContextModel):
 def __init__(self,history,year,week,profile):
  self.profile=profile
  reg=FittedRegressor(history,profile)
  super().__init__(history,year,week,reg)
  # The profile must alter actual population inference, not just final probabilities.
  self.role_stats={}
  for role,observations in self.byrole.items():
   for market in MARKETS13:
    rows=[(g,p) for g,p in observations if market in p["values"]]
    if not rows:continue
    wt=[decay_record(g["season"],g["week"],year,week,profile["half_life"]) for g,p in rows]
    self.role_stats[role,market]=moments([p["values"][market] for g,p in rows],wt)
  self.quality.update({"profile":dict(profile),"profile_pool_size":len(self.byplayer)})
 def _last(self,pid,market,team=None):
  n=self.profile["appearances"]
  return [(g,p) for g,p in self.byplayer.get(pid,[])
    if market in p["values"] and (team is None or g["team"]==team)][-n:]
 def _share(self,pid,role,market,team):
  obs=self._last(pid,market,team)
  exposure="pass_attempts" if market=="targets" else "rush_attempts"
  obs=[(g,p) for g,p in obs if g[exposure]>0]
  if not obs:return 0.
  decay=np.asarray([self.profile["recency_decay"]**(len(obs)-1-i) for i in range(len(obs))])
  numerator=sum(float(d)*p["values"][market] for d,(g,p) in zip(decay,obs))
  denom=sum(float(d)*g[exposure] for d,(g,p) in zip(decay,obs))
  prior=self._role_prior(role,market,3.)
  pace=float(np.average([g[exposure] for g,p in obs],weights=decay))
  prior_rate=np.clip(prior/max(25,pace),.001,.90)
  pseudo=self.profile["usage_prior_games"]*pace
  rate=(numerator+pseudo*prior_rate)/(denom+pseudo)
  return float(np.clip(rate,.0001,.95))
 def _sample_environment(self,gid,home,away,n):
  # Original latent tempo/game script is preserved; only prior-derived
  # opponent effect is scaled and total/count decomposition reconciled.
  env=super()._sample_environment(gid,home,away,n)
  off=collections.defaultdict(list);allowed=collections.defaultdict(list)
  for g in self.history:
   tot=g["pass_attempts"]+g["rush_attempts"]
   ratio=g["pass_attempts"]/tot if tot else .57
   off[g["team"]].append((tot,ratio))
   allowed[g["opponent"]].append((tot,ratio))
  new={}
  for team,opp in ((home,away),(away,home)):
   x=self.regressor.feature(team,opp,off,allowed)
   neutral=x.copy();neutral[[2,4]]=0.
   baseplay=float(x@self.fit["plays"])
   neutralplay=float(neutral@self.fit["plays"])
   basepass=float(x@self.fit["pass_rate"])
   neutralpass=float(neutral@self.fit["pass_rate"])
   influence=self.profile["opponent_strength"]
   wantplay=np.clip(neutralplay+influence*(baseplay-neutralplay),38,84)
   wantpass=np.clip(neutralpass+influence*(basepass-neutralpass),.35,.8)
   current=env[team]
   # Expected change is shared across game scenarios; no actual game stats.
   played=np.rint(current["plays"]*wantplay/max(1.,baseplay)).astype(int)
   played=np.clip(played,25,110)
   # Keep scenario-level game-script shocks from old binomial draw.
   ref=np.clip(current["pass"]/np.maximum(current["plays"],1),.025,.975)
   target=np.clip(basepass,.05,.95)
   odds_shift=math.log(wantpass/(1-wantpass))-math.log(target/(1-target))
   z=np.log(ref/(1-ref))+odds_shift
   passing=np.clip(np.rint(played/(1+np.exp(-z))).astype(int),0,played)
   new[team]={"plays":played,"pass":passing,"rush":played-passing}
  new[home]["opponent_plays"]=new[away]["plays"]
  new[away]["opponent_plays"]=new[home]["plays"]
  new[home]["opponent_pass"]=new[away]["pass"]
  new[away]["opponent_pass"]=new[home]["pass"]
  return new
 def forecast_game(self,gid,home,away,qualified_qb1,n=128,pbp_model=None):
  draws,meta=super().forecast_game(gid,home,away,qualified_qb1,n,pbp_model)
  # Explicit tackle factor: opponent's simulated plays versus a neutral 62.
  # Preserve the solo/assist decomposition after count transformation.
  env=self._sample_environment(gid,home,away,n)
  for team in (home,away):
   opp=np.maximum(1,env[team]["opponent_plays"])
   beta=self.profile["tackle_exposure"]
   multiplier=np.clip((62+beta*(opp-62))/opp,.6,1.6)
   for (t,pid),v in draws.items():
    if t!=team or "tackles + assists" not in v:continue
    source=np.asarray(v["tackles + assists"],dtype=int)
    rng=np.random.default_rng(seed(VERSION,gid,self.year,self.week,team,pid,"tackle_thin"))
    # Poisson-thin on downscale; add Poisson complement when scale >1.
    retained=rng.binomial(source,np.minimum(1,multiplier))
    extra=rng.poisson(source*np.maximum(0,multiplier-1))
    count=retained+extra
    oldsolo=np.asarray(v["solo tackles"],dtype=int)
    oldassist=np.asarray(v["tackle assists"],dtype=int)
    oldtotal=np.maximum(1,source)
    shares=np.clip(oldsolo/oldtotal,0,1)
    solo=rng.binomial(count,shares)
    fraction=np.clip(oldassist/np.maximum(1,source-oldsolo),0,1)
    assists=rng.binomial(count-solo,fraction)
    v["tackles + assists"]=count
    v["solo tackles"]=solo
    v["tackle assists"]=assists
   meta[team]["tackle_opponent_exposure_weight"]=beta
  return draws,meta

class FactorWeights:
 """One shared game-scenario mixture across all markets to preserve joint
 candidate path identity. Learning uses prior scored weeks only."""
 def __init__(self):
  self.log_scores=np.zeros(3)
  self.nweeks=0
 def get(self):
  # Macro-market proper score including binary Brier and normalized quantile loss.
  logits=np.log(PRIOR)-22.0*self.log_scores
  logits=logits-np.max(logits)
  raw=np.exp(logits)
  raw=raw/raw.sum()
  # Keep nonzero research exploration, never let tiny noisy group dominate.
  return canonical_weights(.92*raw+.08*PRIOR)
 def update(self,scores_by_market):
  # Each market contributes once; only comparable 3-forecast contracts.
  per=[]
  for market,seq in scores_by_market.items():
   if not seq:continue
   a=np.array(seq,dtype=float)
   if a.ndim!=2 or a.shape[1]!=3:continue
   per.append(a.mean(axis=0))
  if not per:return
  # Center to avoid common errors changing weights.
  d=np.mean(per,axis=0)
  d=d-d.mean()
  self.log_scores=.90*self.log_scores+.10*d
  self.nweeks+=1
 def receipt(self):
  return {"market_balanced_loss_ema":self.log_scores.tolist(),
          "weeks_prior":self.nweeks,"weights":self.get().tolist()}
 def restore(self,receipt):
  self.log_scores=np.asarray(receipt["market_balanced_loss_ema"])
  self.nweeks=receipt["weeks_prior"]
  require(np.allclose(self.get(),receipt["weights"],atol=1e-12),"bad_factor_prior_receipt")

class OnlineMarketStack:
 """Prior-only market-specific 3-source logit stacking. Frozen θ,b each week.
 No contemporaneous outcome covariates; no hindsight selection."""
 def __init__(self):
  self.theta=collections.defaultdict(lambda:np.log([.55,.30,.15]))
  self.bias=collections.defaultdict(float)
  self.nweeks=collections.defaultdict(int)
  self.nobs=collections.defaultdict(int)
  self.candidate_brier_excess=collections.defaultdict(float)
 def get(self,market,p_raw,p_v2,p_hist,p_base):
  z=np.log(np.clip([p_raw,p_v2,p_hist],.005,.995)/np.clip(1-np.asarray([p_raw,p_v2,p_hist]),.005,.995))
  th=self.theta[market];e=np.exp(th-np.max(th));w=e/e.sum()
  log_odds=np.dot(w,z)+self.bias[market]
  candidate=float(1/(1+np.exp(-np.clip(log_odds,-12,12))))
  # Evidence gate: no arbitrary early-season stacking. A market must build
  # at least eight PRIOR evaluated weeks and 400 prior outcomes; the
  # candidate must have empirically lower prior Brier than frozen V3.
  maturity=np.clip((self.nweeks[market]-8)/14,0.,1.)
  prior_evidence=np.clip(self.nobs[market]/1000.,0.,1.)
  gain=max(0.,-self.candidate_brier_excess[market])
  trust=float(np.clip(maturity*prior_evidence*min(.75,110.*gain),0.,.75))
  p=trust*candidate+(1-trust)*p_base
  return p,{"weights":w.tolist(),"bias":float(self.bias[market]),
   "candidate_p":candidate,"stack_trust":trust,
   "prior_brier_excess":self.candidate_brier_excess[market],
   "prior_evaluated_weeks":self.nweeks[market]}
 def update(self,market,triples):
  if not triples:return
  th=self.theta[market]
  e=np.exp(th-np.max(th));w=e/e.sum()
  grad=np.zeros(3);gb=0.
  diffs=[]
  for praw,pv2,phist,y,pbase in triples:
   z=np.log(np.clip([praw,pv2,phist],.005,.995)/np.clip(1-np.asarray([praw,pv2,phist]),.005,.995))
   s=np.dot(w,z);p=1/(1+np.exp(-np.clip(s+self.bias[market],-12,12)))
   grad+=(p-y)*w*(z-s)
   gb+=p-y
   diffs.append((p-y)**2-(pbase-y)**2)
  grad/=len(triples);gb/=len(triples)
  self.candidate_brier_excess[market]=.85*self.candidate_brier_excess[market]+.15*float(np.mean(diffs))
  self.nobs[market]+=len(triples)
  # Constrained low-learning-rate manual "factor influence" update,
  # not a posterior rewrite of earlier predictions.
  theta0=np.log([.55,.30,.15])
  self.theta[market]=np.clip(th-.65*grad-.01*(th-theta0),-4,4)
  self.bias[market]=float(np.clip(self.bias[market]-.16*gb,-.7,.7))
  self.nweeks[market]+=1
 def receipt(self):
  return {"theta":{"|"+k:list(v) for k,v in self.theta.items()},
   "bias":dict(self.bias),"nweeks":dict(self.nweeks),
   "nobs":dict(self.nobs),"candidate_brier_excess":dict(self.candidate_brier_excess),
   "lr_theta":.65,"lr_bias":.16,"trust_gate_min_weeks":8,"trust_gate_min_nobs":400}
 def restore(self,j):
  for k,v in j["theta"].items():self.theta[k.lstrip("|")]=np.asarray(v,dtype=float)
  for k,v in j["bias"].items():self.bias[k]=float(v)
  for k,v in j["nweeks"].items():self.nweeks[k]=int(v)
  for k,v in j.get("nobs",{}).items():self.nobs[k]=int(v)
  for k,v in j.get("candidate_brier_excess",{}).items():self.candidate_brier_excess[k]=float(v)
