"""NFL research challenger V3: past-only 10-year contextual game opportunities.

Uses nflverse retrospective historical game records, NEVER authentic original pregame
publication. Team play volume and pass fraction are learned in walk-forward ridge
from earlier matchups; offense and opponent defense are separately lagged.
A shared game draw drives both teams, with opposite-sign pass-script shocks.
Conditional role/usage distributions and QB identity are explicitly isolated.
No tiers, no promotions, no real sportsbook lines. License: research-only.
"""
from __future__ import annotations
import collections,hashlib,math,json
import numpy as np
from v25_decade_joint_opportunity import MARKETS, GROUPS, DEFENSE
from v25_decade_qb_components import QBRushComponentModel

EXTRA=("qb rushing attempts","qb rushing yards")
MARKETS13=tuple(MARKETS)+EXTRA
SRC={"qb rushing attempts":"carries","qb rushing yards":"rushing yards"}
HALF_LIFE_YEARS=2.5
PLAYER_APPEARANCES=8
TEAM_RECENT_GAMES=10
DRAWS=128
RIDGE_PENALTY=32.0
VERSION="v3-context-10-year-research-only"
def require(ok,why):
 if not ok:raise ValueError("V3_REJECTED_"+why)
def seed(*args):
 return int.from_bytes(hashlib.sha256("|".join(map(str,args)).encode()).digest()[:8],"big")
def sigmoid(x):return 1/(1+np.exp(-np.clip(x,-20,20)))
def logit(x):return np.log(np.clip(x,1e-4,1-1e-4)/(1-np.clip(x,1e-4,1-1e-4)))
def moments(a,w):
 if not len(a):return 0.,0.
 w=np.asarray(w,dtype=float);a=np.asarray(a,dtype=float)
 w=w/w.sum();mu=np.sum(w*a);v=np.sum(w*(a-mu)**2)
 return float(mu),float(v)
def decay_record(y,w,fy,fw,halflife=HALF_LIFE_YEARS):
 age=max(0.,(fy-y)+(fw-w)/18.)
 return 2**(-age/halflife)
def asof(x,fy,fw):return x["season"]<fy or(x["season"]==fy and x["week"]<fw)

class MatchupRegressor:
 """All training examples' features constructed before their own observed outcome."""
 def __init__(self,allgames):
  self.bydate=collections.defaultdict(list)
  for g in allgames:self.bydate[(g["season"],g["week"])].append(g)
  self.records=[]
  pastoff=collections.defaultdict(list)
  pastallowed=collections.defaultdict(list)
  for (y,w),teamgames in sorted(self.bydate.items()):
   # Build all features before including outcomes from this week.
   for g in teamgames:
    x=self.feature(g["team"],g["opponent"],pastoff,pastallowed)
    n=g["pass_attempts"]+g["rush_attempts"]
    if n>=20 and n<115:
     self.records.append((y,w,x,n,float(g["pass_attempts"])/n))
   for g in teamgames:
    p=g["pass_attempts"];r=g["rush_attempts"]; n=p+r
    pastoff[g["team"]].append((n,p/n if n else .58))
    pastallowed[g["opponent"]].append((n,p/n if n else .58))
  self.off=pastoff;self.allowed=pastallowed
 def feature(self,team,opponent,off,allowed):
  def avg(rec,n,default,idx):
   x=rec.get(n,[])
   return float(np.mean([z[idx] for z in x[-10:]])) if x else default
  def recent(rec,n,default,idx):
   x=rec.get(n,[])
   return float(np.mean([z[idx] for z in x[-3:]])) if x else default
  op=avg(off,team,62.,0)
  dp=avg(allowed,opponent,62.,0)
  oa=avg(off,team,.57,1)
  da=avg(allowed,opponent,.57,1)
  delta=recent(off,team,op,0)-op
  return np.asarray([1,(op-62)/12,(dp-62)/12,(oa-.57)*5,
    (da-.57)*5,delta/12],dtype=float)
 def fitted(self,year,week):
  rows=[r for r in self.records if r[0]>=max(2014,year-10) and
        (r[0]<year or(r[0]==year and r[1]<week))]
  require(all(y<year or(y==year and w<week) for y,w,*_ in rows),"training_future_labels")
  require(len(rows)>300,"insufficient_temporal_training_examples")
  X=np.stack([r[2] for r in rows])
  v=np.asarray([r[3] for r in rows])
  a=np.asarray([r[4] for r in rows])
  weights=np.asarray([decay_record(r[0],r[1],year,week) for r in rows])
  weights=weights/np.mean(weights)
  # Coefficient priors: league mean plays, pass rate. All slopes start at zero.
  priorplays=np.array([62.,0,0,0,0,0],dtype=float)
  priorpass=np.array([.57,0,0,0,0,0],dtype=float)
  ridge=np.diag([1.,RIDGE_PENALTY,RIDGE_PENALTY,RIDGE_PENALTY,
       RIDGE_PENALTY,RIDGE_PENALTY])
  A=X.T@(weights[:,None]*X)+ridge
  bp=np.linalg.solve(A,X.T@(weights*v)+ridge@priorplays)
  br=np.linalg.solve(A,X.T@(weights*a)+ridge@priorpass)
  sd=np.sqrt(max(30.,np.average((v-X@bp)**2,weights=weights)))
  return {"plays":bp,"pass_rate":br,"sd_plays":float(sd),
          "training_rows":len(rows),"earliest_train_year":min(x[0] for x in rows),
          "latest_train_year_week":(rows[-1][0],rows[-1][1]),
          "ridge":RIDGE_PENALTY,"age_half_life_years":HALF_LIFE_YEARS}

class GameContextModel:
 def __init__(self,history,year,week,regressor,calibrator=None):
  self.history=history;self.year=year;self.week=week
  require(all(asof(g,year,week) for g in history),"history_contains_current_or_future")
  require(min(g["season"] for g in history)>=max(2014,year-10),"history_exceeds_10_year_window")
  require(history,"history_empty")
  self.regressor=regressor
  self.fit=regressor.fitted(year,week)
  self.byteam=collections.defaultdict(list)
  self.byplayer=collections.defaultdict(list)
  self.byrole=collections.defaultdict(list)
  self.allhist={(g["event_id"],g["team"]):g for g in history}
  for g in history:
   self.byteam[g["team"]].append(g)
   for pid,p in g["players"].items():
    self.byplayer[pid].append((g,p))
    self.byrole[p["role"]].append((g,p))
  # Population patterns from up to ten years; recent seasons have more influence.
  self.role_stats={}
  for role,observations in self.byrole.items():
   for market in MARKETS:
    e=[(g,p) for g,p in observations if market in p["values"]]
    if not e:continue
    weights=[decay_record(g["season"],g["week"],year,week) for g,p in e]
    m,v=moments([p["values"][market] for g,p in e],weights)
    self.role_stats[role,market]=(m,v)
  self.quality={"prior_min_year":min(g["season"] for g in history),
   "prior_max_year":max(g["season"] for g in history),
   "training_rows":self.fit["training_rows"],
   "latest_training_year_week":self.fit["latest_train_year_week"],
   "half_life_years":HALF_LIFE_YEARS}
 def _last(self,pid,market,team=None):
  return [(g,p) for g,p in self.byplayer.get(pid,[])
     if market in p["values"] and(team is None or g["team"]==team)][-PLAYER_APPEARANCES:]
 def _role_prior(self,role,market,default=1.):
  return self.role_stats.get((role,market),(default,default))[0]
 def _share(self,pid,role,market,team):
  # Use opponent-matched past team exposures; no postgame features.
  rows=self._last(pid,market,team)
  exposure="pass_attempts" if market=="targets" else "rush_attempts"
  obs=[(g,p) for g,p in rows if g[exposure]>0]
  if not obs:return 0.
  total=sum(p["values"][market] for g,p in obs)
  denom=sum(g[exposure] for g,p in obs)
  # Older player appearances within last 8 are slightly discounted.
  pool=self._role_prior(role,market,3.)
  pace=np.mean([g[exposure] for g,p in obs])
  prior_rate=np.clip(pool/max(25.,pace),.001,.9)
  pseudo=1.8*pace
  rate=(total+pseudo*prior_rate)/(denom+pseudo)
  return max(.0001,float(rate))
 def _count(self,mu,rng,n,over=.22):
  mu=np.asarray(mu,dtype=float)
  # Negative-binomial mixture prevents the shrinking-SD error of mean-only models.
  over=max(.04,float(over))
  rate=rng.gamma(1/over,over,size=n)*np.maximum(.001,mu)
  return rng.poisson(rate)
 def _player_history_distribution(self,pid,role,market,rng,n):
  rows=self._last(pid,market)
  if not rows:return None
  values=np.asarray([p["values"][market] for g,p in rows],dtype=float)
  peer,peer_var=self.role_stats.get((role,market),(np.mean(values),np.var(values)))
  wt=len(values)/(len(values)+3.)
  mu=wt*values.mean()+(1-wt)*peer
  if "yards" in market:
   # Continuous heavy-tailed residuals, not narrow iid point predictions.
   resid=values-values.mean()
   scale=max(3.,float(np.std(resid,ddof=1)) if len(values)>1 else math.sqrt(max(1.,peer_var)))
   return mu+scale*rng.standard_t(5,n)/math.sqrt(5/3)
  var=wt*(float(np.var(values,ddof=1)) if len(values)>1 else mu)+(1-wt)*peer_var
  mu=max(.001,mu);disp=max(1e-5,(var-mu)/max(1.,mu*mu))
  return self._count(mu,rng,n,over=disp)
 def _sample_environment(self,game_id,home,away,n):
  # Both offenses share a game tempo latent; passing scripts move oppositely.
  rng=np.random.default_rng(seed(VERSION,self.year,self.week,game_id,"shared-game"))
  # Construct features exclusively from the forecast-week history.
  off=collections.defaultdict(list);allowed=collections.defaultdict(list)
  for g in self.history:
   pp=g["pass_attempts"]; rr=g["rush_attempts"]; total=pp+rr
   off[g["team"]].append((total,pp/total if total else .57))
   allowed[g["opponent"]].append((total,pp/total if total else .57))
  ah=self.regressor.feature(home,away,off,allowed)
  bh=self.regressor.feature(away,home,off,allowed)
  mu_a=float(np.clip(ah@self.fit["plays"],38,84))
  mu_b=float(np.clip(bh@self.fit["plays"],38,84))
  pa=float(np.clip(ah@self.fit["pass_rate"],.35,.80))
  pb=float(np.clip(bh@self.fit["pass_rate"],.35,.80))
  common=rng.normal(size=n)*.085
  home_noise=rng.normal(size=n)*.105
  away_noise=rng.normal(size=n)*.105
  totals_a=np.clip(rng.poisson(mu_a*np.exp(common+home_noise-.5*(.085**2+.105**2))),25,110)
  totals_b=np.clip(rng.poisson(mu_b*np.exp(common+away_noise-.5*(.085**2+.105**2))),25,110)
  # Rate swings share a script factor with opposite sign.
  script=rng.normal(size=n)*.20
  ratea=sigmoid(logit(pa)+script+rng.normal(size=n)*.13)
  rateb=sigmoid(logit(pb)-script+rng.normal(size=n)*.13)
  passa=rng.binomial(totals_a,ratea);passb=rng.binomial(totals_b,rateb)
  return {home:{"plays":totals_a,"pass":passa,"rush":totals_a-passa,
                 "opponent_plays":totals_b,"opponent_pass":passb},
          away:{"plays":totals_b,"pass":passb,"rush":totals_b-passb,
                 "opponent_plays":totals_a,"opponent_pass":passa}}
 def forecast_game(self,game_id,home,away,qualified_qb1,n=128,pbp_model=None):
  require(n>=128 and n<=1024,"sample_size")
  env=self._sample_environment(game_id,home,away,n)
  draws={}
  meta={}
  for team,opponent in ((home,away),(away,home)):
   rg=np.random.default_rng(seed(VERSION,self.year,self.week,game_id,team))
   e=env[team]
   players={}
   candidate={}
   seen=collections.defaultdict(list)
   for g in self.byteam.get(team,[])[-2:]:
    for pid,p in g["players"].items():candidate[pid]=p["role"];seen[pid].append(g)
   # Only the qualified prior-depth QB1 is permitted; others excluded.
   qb1=qualified_qb1.get(team)
   for pid,role in candidate.items():
    if role=="QB" and pid!=qb1:continue
    players[pid]={}
   # Keep full QB passing volume on eligible prior-depth QB rather than assigning
   # it to "most recent observed passer" from the prior team.
   if qb1 in players:
    pid=qb1
    qm=[(g,p) for g,p in self._last(pid,"pass attempts") if g["pass_attempts"]>0]
    qatt=sum(p["values"]["pass attempts"] for g,p in qm)
    tpass=sum(g["pass_attempts"] for g,p in qm)
    share=(qatt+24)/(tpass+26) if tpass else .91
    share=float(np.clip(share,.72,.995))
    qb_pass=rg.binomial(e["pass"],rg.beta(12+35*share,12+35*(1-share),n))
    players[pid]["pass attempts"]=qb_pass
    obs=[p["values"] for g,p in self._last(pid,"completions") if p["values"].get("pass attempts",0)>0]
    if obs:
     comp=sum(v["completions"] for v in obs);att=sum(v["pass attempts"] for v in obs)
     completion=rg.beta(10+comp,10+max(0,att-comp),n)
     catches=rg.binomial(qb_pass,completion)
     players[pid]["completions"]=catches
     rates=[v["passing yards"]/v["completions"] for v in obs if v.get("completions",0)>0 and "passing yards" in v]
     if rates:
      mu=float(np.mean(rates))
      mult=np.clip(rg.lognormal(mean=-.5*.12**2,sigma=.12,size=n),.65,1.6)
      players[pid]["passing yards"]=np.rint(catches*rg.choice(rates,n)*mult)
    if pbp_model is not None:
     x=pbp_model.draw(pid,n=n,seed=seed(VERSION,game_id,team,"qb_rush"),dropback_samples=qb_pass)
     raw_c=np.asarray(x["qb_rushing_attempts"],dtype=int)
     raw_y=np.asarray(x["qb_rushing_yards"],dtype=float)
     safe_c=np.minimum(raw_c,e["rush"])
     ratio=np.divide(safe_c,np.maximum(raw_c,1))
     players[pid]["qb rushing attempts"]=safe_c
     players[pid]["qb rushing yards"]=np.rint(raw_y*ratio)
    else:
     players[pid]["qb rushing attempts"]=np.zeros(n,dtype=int)
     players[pid]["qb rushing yards"]=np.zeros(n,dtype=int)
   else:
    qb_pass=np.zeros(n,dtype=int)
   # Team target pool includes throwaways and unidentified recipients.
   tpool=rg.binomial(e["pass"],rg.beta(19,3,n))
   # Candidate receiver rates, with matched observed team exposure and recency.
   skill=[(pid,role) for pid,role in candidate.items() if role in {"WR","TE","RB"}]
   ids=[pid for pid,r in skill if pid in players]
   raw=np.array([self._share(pid,candidate[pid],"targets",team) for pid in ids],dtype=float)
   # Some directed attempts go to unobserved/new players, never force sum to 100%.
   leftover=max(.07,.20*raw.sum()) if raw.sum() else 1.
   weights=np.r_[raw,leftover]
   weights=weights/weights.sum()
   # Rate fluctuations correlated across markets by common team target draw.
   concentrations=np.maximum(.02,weights*65)
   tdraw=np.zeros((len(ids)+1,n),dtype=int)
   for i in range(n):
    p=rg.dirichlet(concentrations)
    tdraw[:,i]=rg.multinomial(int(tpool[i]),p)
   for j,pid in enumerate(ids):
    arr=tdraw[j];players[pid]["targets"]=arr
    rows=[p["values"] for g,p in self._last(pid,"receptions") if "targets" in p["values"]]
    if rows:
     comps=sum(v["receptions"] for v in rows);exposure=sum(v["targets"] for v in rows)
     rate=rg.beta(5+comps,5+max(0,exposure-comps),n)
     catch=rg.binomial(arr,rate)
     players[pid]["receptions"]=catch
     rates=[v["receiving yards"]/v["receptions"] for v in rows if v.get("receptions",0)>0 and "receiving yards" in v]
     if rates:
      mult=np.clip(rg.lognormal(mean=-.5*.18**2,sigma=.18,size=n),.5,2.)
      players[pid]["receiving yards"]=np.rint(catch*rg.choice(rates,n)*mult)
   # Ground attempts minus QB attempts and residual non-RB rush categories.
   rbpool=e["rush"].copy()
   if qb1 in players:rbpool=rbpool-players[qb1]["qb rushing attempts"]
   rbpool=rg.binomial(rbpool,rg.beta(23,3,n))
   rbs=[pid for pid,r in candidate.items() if r=="RB" and pid in players]
   rweights=np.asarray([self._share(pid,"RB","carries",team) for pid in rbs],dtype=float)
   if len(rbs):
    unknown=max(.05,.12*rweights.sum())
    weights=np.r_[rweights,unknown];weights=weights/weights.sum()
    conc=np.maximum(.02,weights*40)
    rdraw=np.zeros((len(rbs)+1,n),dtype=int)
    for i in range(n):rdraw[:,i]=rg.multinomial(int(rbpool[i]),rg.dirichlet(conc))
    for j,pid in enumerate(rbs):
     carry=rdraw[j];players[pid]["carries"]=carry
     rows=[p["values"] for g,p in self._last(pid,"rushing yards")
            if p["values"].get("carries",0)>0]
     rates=[v["rushing yards"]/v["carries"] for v in rows if v.get("carries",0)>0]
     if rates:
      mult=np.clip(rg.lognormal(mean=-.5*.15**2,sigma=.15,size=n),.65,1.7)
      players[pid]["rushing yards"]=np.rint(carry*rg.choice(rates,n)*mult)
   # Defense: tackle opportunities proportional to opponent offense projected plays.
   # We do NOT claim actual defender snaps; appearance is conditional.
   for pid,role in candidate.items():
    if role not in DEFENSE or pid not in players:continue
    rows=[(g,p) for g,p in self.byplayer.get(pid,[])
          if all(m in p["values"] for m in MARKETS[8:])][-PLAYER_APPEARANCES:]
    if not rows:continue
    rates=[];comps=[]
    for g,p in rows:
     opp=self.allhist.get((g["event_id"],g["opponent"]))
     exposure=(opp["pass_attempts"]+opp["rush_attempts"]) if opp else 62.
     if exposure<10:continue
     total=float(p["values"]["tackles + assists"])
     rates.append(total/exposure)
     a=float(p["values"]["solo tackles"])
     b=float(p["values"]["tackle assists"])
     comps.append([a,b,max(0.,total-a-b)])
    if not rates:continue
    pop=self._role_prior(role,"tackles + assists",3.)/62.
    player_rate=np.mean(rates)
    share=np.clip((len(rates)*player_rate+4*pop)/(len(rates)+4),.003,.35)
    # Sampled opponent plays shared by every defender on this defense.
    count=self._count(e["opponent_plays"]*share,rg,n,over=.20)
    component=np.sum(comps,axis=0)+np.asarray([2.,2.,1.])
    component=np.maximum(.1,component)
    p=rg.dirichlet(component,size=n)
    solo=rg.binomial(count,p[:,0])
    assist=rg.binomial(count-solo,np.divide(p[:,1],np.maximum(1e-6,1-p[:,0])))
    players[pid]["tackles + assists"]=count
    players[pid]["solo tackles"]=solo
    players[pid]["tackle assists"]=assist
   for pid,dictdraw in players.items():
    draws[team,pid]=dictdraw
   meta[team]={"qb1":qb1,"qualified_qb_in_candidates":qb1 in players,
               "source_selection_unverified":True,
               "game_shared_plays_average":float(np.mean(e["plays"])),
               "game_shared_pass_attempt_average":float(np.mean(e["pass"])),
               "opponent_projected_plays_average":float(np.mean(e["opponent_plays"])),
               "team_rush_average":float(np.mean(e["rush"]))}
  return draws,meta

class OnlineBayesCalibrator:
 def __init__(self):
  self.s=collections.defaultdict(lambda:[0.,0.])
 def _key(self,market,side,bin_):
  return (market,side,bin_)
 def apply(self,market,raw):
  raw=float(np.clip(raw,1e-4,1-1e-4))
  side="under" if raw<.5 else "over"
  conf=max(raw,1-raw)
  bin_=min(4,int(5*(conf-.5)/.5))
  k=self._key(market,side,bin_)
  n,w=self.s[k]
  # Prior strength 20 with market-specific prior on selected-side hit.
  # A mild initial high-confidence regularizer prevents unearned 99% claims.
  prior_conf=.5+(conf-.5)*.88
  val=(20*prior_conf+w)/(20+n)
  val=float(np.clip(val,.001,.999))
  return 1-val if side=="under" else val
 def update(self,observations):
  # Discount past weeks modestly: older seasons still contribute.
  for k,z in self.s.items():z[0]*=.997;z[1]*=.997
  for market,p,y in observations:
   side="under" if p<.5 else "over"
   conf=max(p,1-p)
   bin_=min(4,int(5*(conf-.5)/.5))
   z=self.s[self._key(market,side,bin_)]
   z[0]+=1;z[1]+=int((p>.5)==bool(y))
 def receipt(self):
  return {"n_bins":5,"prior_strength":20,"weekly_discount":.997,
    "state":{"|".join(map(str,k)):list(v) for k,v in self.s.items()}}
