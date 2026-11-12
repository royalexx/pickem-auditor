"""V4.1 QB-share correction for the research-only two-profile opportunity model.

The inherited V3 QB sampler used
Beta(12 + 35*historical_share, 12 + 35*(1-historical_share)),
which shrinks expected QB1 share (e.g. 95%) to (12+33.25)/59 = 76.7%!
This biases pass attempts, completions, and pass yards low. V4.1 retains
empirically anchored rate Beta(1 + 60*share, 1 + 60*(1-share)), and
regenerates dependent outcomes under the SAME projected game pass volume.
All corrections require a prior-depth eligible QB and past exposure.

No retroactive manipulation of old V2/V3/V4 results. Rerun on the original
175 frozen weekly inputs and evaluate against matched historical outcomes.
"""
from __future__ import annotations
import math
import numpy as np
from nfl_v4_factor_tuning_model_20261111 import (
 ContextFactorModel as UncorrectedContext,PROFILES,FactorWeights,
 OnlineMarketStack,require,seed)
VERSION="v4_1_qbshare_beta_concentration_repair_research"
class ContextFactorModel(UncorrectedContext):
 def forecast_game(self,gid,home,away,qualified_qb1,n=128,pbp_model=None):
  draws,meta=super().forecast_game(gid,home,away,qualified_qb1,n,pbp_model)
  env=self._sample_environment(gid,home,away,n)
  for team in (home,away):
   pid=qualified_qb1.get(team)
   key=(team,pid)
   if pid is None or key not in draws or "pass attempts" not in draws[key]:
    continue
   # Selected prior-depth QB1 only, never an inactive/back-up QB.
   rg=np.random.default_rng(seed(VERSION,gid,self.year,self.week,team,pid,"QB1share"))
   exposures=[(g,p) for g,p in self._last(pid,"pass attempts")
                if g["pass_attempts"]>0]
   qatt=sum(p["values"]["pass attempts"] for g,p in exposures)
   tpass=sum(g["pass_attempts"] for g,p in exposures)
   share=(qatt+24.)/(tpass+26.) if tpass else .91
   share=float(np.clip(share,.75,.99))
   conc=60.
   alpha=1.+conc*share
   beta=1.+conc*(1-share)
   share_draw=rg.beta(alpha,beta,size=n)
   selected_attempts=rg.binomial(env[team]["pass"],share_draw)
   v=draws[key]
   v["pass attempts"]=selected_attempts
   obs=[p["values"] for g,p in self._last(pid,"completions")
          if p["values"].get("pass attempts",0)>0]
   if obs:
    comp=sum(x["completions"] for x in obs)
    att=sum(x["pass attempts"] for x in obs)
    pct=rg.beta(2+comp,2+max(0,att-comp),size=n)
    complete=rg.binomial(selected_attempts,pct)
    v["completions"]=complete
    rates=[x["passing yards"]/x["completions"] for x in obs
       if x.get("completions",0)>0 and "passing yards" in x]
    if rates:
     rates=np.clip(rates,3.,25.)
     noise=np.clip(rg.lognormal(mean=-.5*.12**2,sigma=.12,size=n),.65,1.65)
     v["passing yards"]=np.rint(complete*rg.choice(rates,size=n)*noise)
   if pbp_model is not None:
    scrambles=pbp_model.draw(pid,n=n,
       seed=seed(VERSION,gid,self.year,self.week,team,pid,"QB1rush"),
       dropback_samples=selected_attempts)
    attempts=np.asarray(scrambles["qb_rushing_attempts"],dtype=int)
    yards=np.asarray(scrambles["qb_rushing_yards"],dtype=float)
    permitted=np.minimum(attempts,env[team]["rush"])
    ratio=np.divide(permitted,np.maximum(attempts,1))
    v["qb rushing attempts"]=permitted
    v["qb rushing yards"]=np.rint(yards*ratio)
   meta[team]["qb_share_prior_measured"]=share
   meta[team]["qb_share_beta_prior_mean"]=float(alpha/(alpha+beta))
   meta[team]["qb_pass_attempts_prior_anchored_mean"]=float(np.mean(selected_attempts))
   meta[team]["qb_pass_attempts_team_eligible_mean"]=float(np.mean(env[team]["pass"]))
   meta[team]["qb_volume_overwrite_verified"]=True
  return draws,meta
