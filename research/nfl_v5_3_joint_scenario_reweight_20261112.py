"""Prior-only soft conditioning of an EXISTING coherent NFL joint game.

V5.3 does not replace a single QB, RB, receiver or defender count. It optimizes
ONE nonnegative vector of weights over whole TWO-TEAM scenarios using prior-only
historical marginal forecasts as soft, regularized information. The weight
vector is then resampled once for ALL player markets and both defenses.

The historical marginal reference is V4's frozen prior-week forecast, NOT
postgame stats and NOT a market price. This is a research anchor and
cannot be counted as independent performance evidence. If reweighting cannot
achieve bounds with adequate effective sample size, it reverts to the
unweighted joint game and emits a diagnostic receipt.
"""
from __future__ import annotations
import math,collections,hashlib
import numpy as np

VERSION="v5_3_whole_game_history_anchored_entropic_reweight_20261112"
STRENGTHS=(0.,0.6,1.4)
DEFAULT=np.array([.15,.30,.55],dtype=float)
def verify(c,code):
 if not c:raise ValueError("V53_REJECTED_"+code)
def random_seed(*items):
 return int.from_bytes(hashlib.sha256("|".join(map(str,items)).encode()).digest()[:8],"big")
def softmax(v):
 v=np.asarray(v,dtype=float)
 z=np.exp(v-v.max());return z/z.sum()
def effective_sample_size(weights):
 return float(1./np.square(weights).sum())
class TiltLearner:
 """Learn WHOLE-GAME tilt-strength weights after each completed prior week."""
 def __init__(self):
  self.loss_ema=np.zeros(len(STRENGTHS),dtype=float)
  self.nweeks=0
 def get(self):
  x=np.log(DEFAULT)-15.*self.loss_ema
  return .94*softmax(x)+.06*DEFAULT
 def update(self,per_market_scores):
  rows=[]
  for scores in per_market_scores.values():
   if scores:
    z=np.asarray(scores,dtype=float)
    verify(z.ndim==2 and z.shape[1]==len(STRENGTHS),"invalid_tilt_losses")
    rows.append(z.mean(axis=0))
  if rows:
   q=np.mean(rows,axis=0);self.loss_ema=.9*self.loss_ema+.1*(q-q.mean())
   self.nweeks+=1
 def receipt(self):
  return {"prior_tilt_loss_ema":self.loss_ema.tolist(),
    "weeks_prior":self.nweeks,"tilt_strengths":list(STRENGTHS),
    "weights":self.get().tolist()}
 def restore(self,p):
  verify(list(STRENGTHS)==p["tilt_strengths"],"tilt_method_drift")
  self.loss_ema=np.asarray(p["prior_tilt_loss_ema"],dtype=float)
  self.nweeks=int(p["weeks_prior"])
  verify(np.allclose(self.get(),p["weights"],atol=1e-12),"tilt_prior_mismatch")

def event_matrix(game_offers,anchors,n):
 """One event per unique actual synthetic offer, market-balanced not row-count dominated."""
 vals=[];q=[];group=[]
 for f in game_offers:
  if f["status"]!="forecast":continue
  identity=(f["game_id"],f["team"],f["player_id"],f["market"])
  anchor=anchors.get(identity)
  if anchor is None:continue
  if not (0<anchor<1):continue
  d=np.asarray(f["draws"],dtype=float)
  verify(d.shape==(n,),"bad_joint_draw_shape")
  vals.append((d>f["line"]).astype(float))
  q.append(float(anchor))
  group.append(f["market"])
 if not vals:return np.empty((0,n)),np.empty(0),np.empty(0)
 matrix=np.stack(vals)
 market_counts=collections.Counter(group)
 # Equal sum of influence for every represented market, not every offer.
 weights=np.array([1./market_counts[m] for m in group],dtype=float)
 weights/=weights.sum()
 return matrix,np.asarray(q),weights

def optimize_weights(E,q,market_balance,strength,n,iterations=100):
 """Mirror-descent minimum KL, finite-sample ESS floor 25%."""
 uniform=np.full(n,1./n)
 if strength==0 or not len(q):return uniform,{"status":"no_tilt","ess":float(n),"iter":0}
 # All pair/event constraints refer to the same game scenarios. Soft fitting
 # never alters any statistic's raw simulated support or legal relationship.
 logw=np.zeros(n)
 # Prior-regularized moment matching. The strength only scales the loss term.
 beta=6.*strength
 for k in range(iterations):
  w=softmax(logw)
  diff=E@w-q
  moment_gradient=2.*beta*(E.T@(market_balance*diff))
  # Entropy penalty keeps coherent scenario coverage and avoids oracle-like
  # concentrating all probability on one retrospective-looking game.
  gradient=moment_gradient+.09*(logw-np.dot(w,logw))
  # Log-space mirror descent with decayed step for numerical stability.
  logw-=(.48/(1.+.014*k))*gradient
  logw-=logw.mean()
  logw=np.clip(logw,-18,18)
 learned=softmax(logw)
 ess=effective_sample_size(learned)
 if ess<n*.25:
  lo,hi=0.,1.
  for _ in range(30):
   mid=(lo+hi)/2
   mix=(1-mid)*uniform+mid*learned
   if effective_sample_size(mix)<n*.25:hi=mid
   else:lo=mid
  learned=(1-lo)*uniform+lo*learned
  ess=effective_sample_size(learned)
 verify(np.isfinite(learned).all() and np.isclose(learned.sum(),1)
        and np.all(learned>=0),"invalid_tilt_weights")
 return learned,{"status":"tilted","ess":ess,
   "iter":iterations,"max_abs_anchor_diff":float(np.max(np.abs(E@learned-q))),
   "mean_sq_anchor_diff":float(np.sum(market_balance*(E@learned-q)**2)),
   "max_weight":float(learned.max()),"strength":strength}

def systematic_resample(weights,n,seed):
 rng=np.random.default_rng(seed)
 cdf=np.cumsum(weights)
 u=(rng.random()+np.arange(n))/n
 idx=np.searchsorted(cdf,u,side="right")
 verify(np.all((idx>=0)&(idx<n)),"out_of_range_resample")
 return idx.astype(int)

def game_all_strength_draws(game,offers,anchors,season,week,gid):
 """Return three full-game scenario-index selectors, no stat-level exceptions."""
 n=len(game["source_profile_indices"])
 E,q,balance=event_matrix(offers,anchors,n)
 selectors=[]
 info=[]
 for strength in STRENGTHS:
  weights,receipt=optimize_weights(E,q,balance,strength,n)
  if strength==0:
   selected=np.arange(n,dtype=int)
  else:
   selected=systematic_resample(weights,n,
     random_seed(VERSION,season,week,gid,strength))
  selectors.append(selected)
  info.append({**receipt,"valid_anchors":len(q),"game_id":gid})
 return selectors,info

def _resample_game(game,selector):
 n=len(selector)
 prior=game["joint_state"]
 new=dict(game)
 new["source_profile_indices"]=[game["source_profile_indices"][int(i)] for i in selector]
 new["joint_state"]={}
 for team,stats in prior.items():
  new["joint_state"][team]={}
  for k,v in stats.items():
   if isinstance(v,list):
    verify(len(v)==n,"shared_state_scenario_shape_"+k)
    new["joint_state"][team][k]=[v[i] for i in selector]
   else:new["joint_state"][team][k]=v
 return new

def tilt_forecast(report,anchors,prior,model_version):
 """Three candidate tilt trajectories, blended by ONE game-scenario mask."""
 verify(report.get("pregame_certified") is False,"cannot_certify_retro")
 verify(report["research_only"] is True,"production_not_supported")
 year,week=report["season"],report["week"]
 maskweights=prior.get()
 new=dict(report)
 bygame=collections.defaultdict(list)
 for f in report["offers"]:bygame[f["game_id"]].append(f)
 newgames={};new_offers=[];paired_sources={}
 for gid,game in report["games"].items():
  offers=bygame[gid]
  selections,details=game_all_strength_draws(game,offers,anchors,year,week,gid)
  n=len(selections[0])
  chosen=np.random.default_rng(random_seed(VERSION,year,week,gid,"whole_game_mask")).choice(
     len(STRENGTHS),size=n,p=maskweights)
  idx=np.array([selections[chosen[i]][i] for i in range(n)],dtype=int)
  upgraded=_resample_game(game,idx)
  upgraded["whole_game_tilt_strength_selection"]=chosen.tolist()
  upgraded["whole_game_tilt_diagnostics"]=details
  upgraded["whole_game_tilt_strength_weights_prior"]=maskweights.tolist()
  # Do not use future values or independent per-contract probability overrides.
  upgraded["single_shared_game_state_verified"]=True
  newgames[gid]=upgraded
  for f in offers:
   v=dict(f)
   if v["status"]!="forecast":
    new_offers.append(v);continue
   original=np.asarray(v["draws"],dtype=float)
   v["draws"]=original[idx].tolist()
   v["predicted_mean"]=float(original[idx].mean())
   v["p_over"]=float(np.mean(original[idx]>v["line"]))
   v["p_under"]=float(np.mean(original[idx]<v["line"]))
   v["p_push"]=float(np.mean(original[idx]==v["line"]))
   v["p_over_raw"]=v["p_over"]
   v["p_over_tuned"]=v["p_over"]
   v["v5_raw_base_probability"]=float(np.mean(original>v["line"]))
   v["full_game_strength_candidates_q_over"]=[
      float(np.mean(original[s]>v["line"])) for s in selections]
   v["prior_tilt_strength_weights"]=maskweights.tolist()
   v["history_anchor_probability"]=anchors.get(
      (v["game_id"],v["team"],v["player_id"],v["market"]))
   verify(np.isclose(v["p_over"]+v["p_under"]+v["p_push"],1),
          "over_under_push_invalid")
   new_offers.append(v)
 new["games"]=newgames
 new["offers"]=new_offers
 new["version"]=model_version
 new["posthoc_probability_override"]=False
 new["global_game_scenario_resampling_only"]=True
 return new
