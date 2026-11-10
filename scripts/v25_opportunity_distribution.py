"""Opportunity repair challenger. Pure past-only functions; no provider calls.

QB workload is a starter/relief mixture, never a simultaneous competition
between historical QB averages. Receiver rates use matched appearance
exposures. Non-target attempts and genuinely unseen recipients are separate.
Unknown current activity is NOT inferred from a missing box row: forecasts
are conditional research distributions and have no publication authority.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
import numpy as np

VERSION = "v25-opportunity-distribution-repair-v2"
MARKETS = ("pass attempts", "completions", "passing yards", "targets",
           "receptions", "receiving yards", "carries", "rushing yards",
           "tackles + assists", "solo tackles", "tackle assists")
FIELD = dict(zip(MARKETS, ("attempts", "completions", "passing_yards", "targets",
    "receptions", "receiving_yards", "carries", "rushing_yards", None,
    "def_tackles_solo", "def_tackle_assists")))
DEFENSE = {"LB","MLB","OLB","ILB","DE","DT","NT","CB","DB","S","FS","SS","DL","EDGE"}
RECEIVERS = {"WR","RB","TE"}
GROUPS = {"QB": MARKETS[:3], "WR": MARKETS[3:6], "TE": MARKETS[3:6],
          "RB": MARKETS[3:8]}
POLICY = {"player_window": 8, "team_window": 10, "candidate_team_games": 2,
          "prior_player_games": 2., "team_prior_games": 5.,
          "parameters_chosen_before_repaired_2024_replay": True}


def reject(reason):
    raise ValueError("OPPORTUNITY_REPAIR_REJECTED:" + reason)


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def seed_for(*parts):
    return int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big")


def normalise_player_source(rows, *, rejection_ledger=None):
    """Never replace null statistics with zero. Preserve all observed zeros."""
    groups = {}
    seen = set()
    for r in rows:
        if r.get("season_type") != "REG" or r.get("season") not in (2021,2022,2023,2024):
            continue
        if not 1 <= r.get("week",0) <= 18:
            continue
        ident = (r.get("game_id"),r.get("team"),r.get("player_id"))
        # nflverse has an empty unidentified zero-only placeholder in some
        # weeks. Quarantine it explicitly; never discard a nonzero record.
        raw_fields=[c for c in FIELD.values() if c]+["def_tackles_with_assist"]
        if (not ident[2] and r.get("position") is None and
                all(r.get(c)==0 for c in raw_fields)):
            if rejection_ledger is None:reject("zero_placeholder_requires_rejection_ledger")
            rejection_ledger.append({"reason":"unidentified_zero_only_placeholder","source_row":r})
            continue
        if any(not isinstance(x,str) or not x for x in ident):
            reject("missing_source_identity")
        if ident in seen:
            reject("duplicate_source_player_game")
        seen.add(ident)
        g = groups.setdefault(ident[:2], {"event_id":ident[0],"team":ident[1],
             "opponent":r["opponent_team"],"season":r["season"],"week":r["week"],
             "pass_attempts":0,"rush_attempts":0,"players":{}})
        values = {}
        for market,column in FIELD.items():
            v = r.get(column) if column else None
            if column is None:
                parts = [r.get(c) for c in ("def_tackles_solo","def_tackles_with_assist","def_tackle_assists")]
                if all(isinstance(z,(int,float)) and not isinstance(z,bool) and math.isfinite(z) for z in parts):
                    v = sum(parts)
            if v is None:
                continue
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
                reject("invalid_source_statistic")
            if "yards" not in market and (v < 0 or not float(v).is_integer()):
                reject("invalid_source_count")
            values[market] = float(v) if "yards" in market else int(v)
        # Complete team opportunity labels are required, even for kickers.
        if "pass attempts" not in values or "carries" not in values:
            reject("missing_team_opportunity_component")
        g["pass_attempts"] += values["pass attempts"]
        g["rush_attempts"] += values["carries"]
        role = r.get("position")
        allowed = GROUPS.get(role, MARKETS[8:] if role in DEFENSE else ())
        if role == "QB":
            allowed = (*allowed,"carries","rushing yards")
        if allowed:
            g["players"][ident[2]] = {"role":role,
                "values":{k:v for k,v in values.items() if k in allowed}}
    return sorted(groups.values(), key=lambda g:(g["season"],g["week"],g["event_id"],g["team"]))


def validate_history(history, week):
    if type(week) is not int or not 1 <= week <= 18 or not history:
        reject("invalid_week_or_empty_history")
    seen = set()
    for g in history:
        if set(g) != {"event_id","team","opponent","season","week","pass_attempts","rush_attempts","players"}:
            reject("history_schema_or_hidden_feature")
        if type(g["season"]) is not int or type(g["week"]) is not int:
            reject("invalid_history_calendar")
        if g["season"] not in (2021,2022,2023,2024) or not 1 <= g["week"] <= 18:
            reject("history_calendar_out_of_range")
        if g["season"] == 2024 and g["week"] >= week:
            reject("current_or_future_game_label")
        k=(g["event_id"],g["team"])
        if k in seen:
            reject("duplicate_historical_team_game")
        seen.add(k)
        if g["team"] == g["opponent"] or not isinstance(g["players"],dict):
            reject("invalid_historical_identity")
        for c in ("pass_attempts","rush_attempts"):
            if type(g[c]) is not int or g[c] < 0:
                reject("invalid_team_opportunity")
        for pid,p in g["players"].items():
            if not pid or set(p)!={"role","values"} or not isinstance(p["values"],dict):
                reject("invalid_player_history")
            for m,v in p["values"].items():
                if m not in MARKETS or isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
                    reject("invalid_historical_value")
                if "yards" not in m and (v < 0 or not float(v).is_integer()):
                    reject("invalid_historical_count")
            v=p["values"]
            if v.get("completions",0)>v.get("pass attempts",0) or v.get("receptions",0)>v.get("targets",0):
                reject("conditional_count_exceeds_exposure")
        if sum(p["values"].get("targets",0) for p in g["players"].values()) > g["pass_attempts"]:
            reject("targets_exceed_attempts")


def _nb(rng,mean,variance,n):
    mean=max(0.,float(mean))
    if not mean:
        return np.zeros(n,dtype=np.int64)
    if variance <= mean + 1e-8:
        return rng.poisson(mean,n)
    k=mean*mean/(variance-mean)
    return rng.negative_binomial(k,k/(k+mean),n)


class OpportunityModel:
    def __init__(self, history, week):
        validate_history(history,week)
        self.history=history;self.week=week
        self.byteam=defaultdict(list);self.byplayer=defaultdict(list)
        self.byrole=defaultdict(list)
        for g in sorted(history,key=lambda x:(x["season"],x["week"],x["event_id"])):
            self.byteam[g["team"]].append(g)
            for pid,p in g["players"].items():
                self.byplayer[pid].append((g,p))
                self.byrole[p["role"]].append((g,p))
        self.role_stats={};self.role_target_rates={};self.role_carry_rates={}
        for role,records in self.byrole.items():
            for market in MARKETS:
                values=[p["values"][market] for g,p in records if market in p["values"]]
                if values:self.role_stats[role,market]=(float(np.mean(values)),float(np.var(values)))
            recipients=[(g,p) for g,p in records if "targets" in p["values"] and g["pass_attempts"]>0]
            if recipients:
                self.role_target_rates[role]=sum(p["values"]["targets"] for g,p in recipients)/sum(g["pass_attempts"] for g,p in recipients)
            rushers=[(g,p) for g,p in records if "carries" in p["values"] and g["rush_attempts"]>0]
            if rushers:
                self.role_carry_rates[role]=sum(p["values"]["carries"] for g,p in rushers)/sum(g["rush_attempts"] for g,p in rushers)
        # Fit switch/relief frequencies from earlier observations only.
        transitions=np.ones(3,dtype=float)
        relief=[]
        for games in self.byteam.values():
            prior=None;prior_qbs=set()
            for g in games:
                q={pid:p["values"].get("pass attempts",0) for pid,p in g["players"].items() if p["role"]=="QB"}
                if not q or max(q.values()) <= 0:continue
                leader=max(q,key=lambda pid:(q[pid],pid))
                if prior is not None and prior[0]==g["season"]:
                    transitions[0 if leader==prior[1] else 1 if leader in prior_qbs else 2]+=1
                prior=(g["season"],leader);prior_qbs=set(q)
                if g["pass_attempts"]:
                    relief.append(1.-q[leader]/g["pass_attempts"])
        self.qb_transition=transitions/transitions.sum()
        self.relief=np.asarray(relief if relief else [0.])
        self.unseen=self._unseen_recipient_rate()
        self.unseen_rush=self._unseen_recipient_rate("carries",{"RB"})

    def _unseen_recipient_rate(self, market="targets", roles=RECEIVERS):
        """Prequential unseen mass, NOT targets of departed historical players."""
        lost=0.;directed=0.;origins=0
        for games in self.byteam.values():
            for i,g in enumerate(games):
                if i < 2:continue
                roster={pid for h in games[i-2:i] for pid,p in h["players"].items() if p["role"] in roles}
                for pid,p in g["players"].items():
                    if p["role"] not in roles or market not in p["values"]:continue
                    t=p["values"][market];directed+=t
                    if pid not in roster:lost+=t
                origins+=1
        return {"alpha":1.+lost,"beta":1.+directed-lost,"historical_origins":origins,
                "market":market,
                "definition":"next_game_opportunities_to_players_missing_from_previous_two_appearance_roster"}

    def candidates(self,team):
        recent=self.byteam.get(team,[])[-POLICY["candidate_team_games"]:]
        return {pid:p["role"] for g in recent for pid,p in g["players"].items()}

    def _player_rows(self,pid,market,team=None):
        return [(g,p) for g,p in self.byplayer.get(pid,[]) if market in p["values"] and (team is None or g["team"]==team)][-POLICY["player_window"]:]

    def independent(self,team,pid,role,market,rng,n):
        own=self._player_rows(pid,market)
        prior_stats=self.role_stats.get((role,market))
        if prior_stats is None or not own:return None
        vs=np.array([p["values"][market] for g,p in own],float)
        # Conditional-on-appearance control; no fabricated inactive games.
        prior,prior_variance=prior_stats;weight=len(vs)/(len(vs)+POLICY["prior_player_games"])
        mu=weight*float(vs.mean())+(1-weight)*prior
        if "yards" in market:
            centered=vs-vs.mean()
            return mu+rng.choice(centered,n) if len(vs)>1 else np.repeat(mu,n)
        var=weight*float(np.var(vs,ddof=1) if len(vs)>1 else mu)+(1-weight)*prior_variance
        return _nb(rng,mu,max(mu,var),n)

    def _team_volume(self,team,field,rng,n):
        recent=self.byteam[team][-POLICY["team_window"]:]
        league=[g[field] for g in self.history]
        a=POLICY["team_prior_games"]
        mu=(sum(g[field] for g in recent)+a*np.mean(league))/(len(recent)+a)
        # Predictive game variance does not shrink as SD/sqrt(number games).
        var=float(np.var([g[field] for g in recent],ddof=1)) if len(recent)>1 else float(np.var(league))
        return _nb(rng,mu,max(mu,var),n)

    def _share(self,pid,role,team,rng,n,market="targets"):
        exposure="pass_attempts" if market=="targets" else "rush_attempts"
        own=[(g,p) for g,p in self._player_rows(pid,market) if g[exposure]>0]
        prior=(self.role_target_rates if market=="targets" else self.role_carry_rates).get(role)
        if not own or prior is None:return None
        # Only games where that player has an OBSERVED row enter exposure.
        a=sum(p["values"][market] for g,p in own)
        b=sum(g[exposure] for g,p in own)
        pseudo=POLICY["prior_player_games"]*float(np.mean([g[exposure] for g,p in own]))
        mu=(a+pseudo*prior)/(b+pseudo)
        rates=np.array([p["values"][market]/g[exposure] for g,p in own])
        binvar=np.mean([mu*(1-mu)/g[exposure] for g,p in own])
        observed=float(np.var(rates,ddof=1)) if len(rates)>1 else binvar
        extra=max(0.,observed-binvar)
        # Between-game rate variation is retained even with long history.
        k=mu*(1-mu)/extra-1 if extra>1e-10 else b+pseudo
        k=max(2.,min(10000.,k))
        return rng.beta(max(.01,mu*k),max(.01,(1-mu)*k),n),{
           "appearance_games":len(own),"matched_attempt_exposure":b,
           "conditional_target_per_attempt":mu,"predictive_beta_concentration":k}

    def forecast_team(self,team,event_id,*,n=512,seed=20261110):
        if type(n) is not int or not 128<=n<=4096 or team not in self.byteam:
            reject("invalid_forecast_team_or_sample_count")
        rng=np.random.default_rng(seed_for(seed,self.week,event_id,team))
        candidates=self.candidates(team)
        attempts=self._team_volume(team,"pass_attempts",rng,n)
        rushes=self._team_volume(team,"rush_attempts",rng,n)
        draws={pid:{} for pid in candidates};simple={pid:{} for pid in candidates};diagnostics={}
        for pid,role in candidates.items():
            for market in GROUPS.get(role,MARKETS[8:] if role in DEFENSE else ()):
                arr=self.independent(team,pid,role,market,np.random.default_rng(seed_for(seed,self.week,event_id,team,pid,market,"control")),n)
                if arr is not None:simple[pid][market]=arr
        # Most recent observed team leader is a PROXY, never a verified starter.
        qbs=[pid for pid,r in candidates.items() if r=="QB"]
        qb_latest=None
        for g in reversed(self.byteam[team]):
            qs={pid:p["values"].get("pass attempts",0) for pid,p in g["players"].items() if p["role"]=="QB"}
            if qs and max(qs.values())>0:
                qb_latest=max(qs,key=lambda pid:(qs[pid],pid));break
        leader_draw=np.full(n,"UNKNOWN",dtype=object)
        if qb_latest in qbs:
            state=rng.choice(3,n,p=self.qb_transition)
            leader_draw[state==0]=qb_latest
            other=[p for p in qbs if p!=qb_latest]
            if other:leader_draw[state==1]=rng.choice(other,int(sum(state==1)))
        qb_pool={p:np.zeros(n,dtype=np.int64) for p in qbs}
        relief_fraction=rng.choice(self.relief,n)
        main_attempts=attempts-rng.binomial(attempts,np.clip(relief_fraction,0,1))
        unknown_qb=attempts.copy()
        for pid in qbs:
            a=np.where(leader_draw==pid,main_attempts,0)
            qb_pool[pid]=a;unknown_qb-=a
            draws[pid]["pass attempts"]=a
            diagnostics[pid]={"role_status":"lagged_primary_proxy" if pid==qb_latest else "unverified_backup_role",
                "source_certified":False,"publication_eligible":False}
            own=self._player_rows(pid,"pass attempts")
            positive=[(g,p) for g,p in own if p["values"].get("pass attempts",0)>0 and "completions" in p["values"]]
            if positive:
                comp=sum(p["values"]["completions"] for g,p in positive);att=sum(p["values"]["pass attempts"] for g,p in positive)
                catches=rng.binomial(a,rng.beta(1+comp,1+att-comp,n))
                draws[pid]["completions"]=catches
                donors=[p["values"]["passing yards"]/p["values"]["completions"] for g,p in positive if p["values"]["completions"]>0 and "passing yards" in p["values"]]
                if donors:draws[pid]["passing yards"]=catches*rng.choice(donors,n)
        if np.any(sum(qb_pool.values(),np.zeros(n,dtype=int))+unknown_qb!=attempts):
            reject("qb_pool_not_conserved")
        recent=self.byteam[team][-POLICY["team_window"]:]
        directed=sum(p["values"].get("targets",0) for g in recent for p in g["players"].values() if p["role"] in RECEIVERS)
        exposure=sum(g["pass_attempts"] for g in recent)
        target_pool=rng.binomial(attempts,rng.beta(1+directed,1+exposure-directed,n))
        non_target=attempts-target_pool
        unknown_target=rng.binomial(target_pool,rng.beta(self.unseen["alpha"],self.unseen["beta"],n))
        known=target_pool-unknown_target
        receivers=[];weights=[]
        for pid,role in candidates.items():
            if role not in RECEIVERS:continue
            fit=self._share(pid,role,team,rng,n)
            if fit is None:continue
            w,details=fit;receivers.append(pid);weights.append(w)
            diagnostics[pid]={**details,"role_status":"conditional_on_unverified_current_appearance",
                "source_certified":False,"publication_eligible":False}
        target_samples={pid:np.zeros(n,dtype=np.int64) for pid in receivers}
        if receivers:
            ws=np.array(weights)
            for i in range(n):
                probs=ws[:,i]/ws[:,i].sum()
                values=rng.multinomial(int(known[i]),probs)
                for pid,v in zip(receivers,values):target_samples[pid][i]=v
        else:
            unknown_target+=known
        for pid,arr in target_samples.items():
            draws[pid]["targets"]=arr
            rows=self._player_rows(pid,"targets")
            good=[p["values"] for g,p in rows if p["values"]["targets"]>0 and "receptions" in p["values"]]
            if good:
                caught=sum(p["receptions"] for p in good);t=sum(p["targets"] for p in good)
                catches=rng.binomial(arr,rng.beta(1+caught,1+t-caught,n))
                draws[pid]["receptions"]=catches
                yard_rates=[p["receiving yards"]/p["receptions"] for p in good if p["receptions"]>0 and "receiving yards" in p]
                if yard_rates:draws[pid]["receiving yards"]=catches*rng.choice(yard_rates,n)
        if np.any(sum(target_samples.values(),np.zeros(n,dtype=int))+unknown_target+non_target!=attempts):
            reject("receiver_opportunity_not_conserved")
        # RB attempts and the non-RB (including QB) category are distinct.
        rb_count=sum(p["values"].get("carries",0) for g in recent for p in g["players"].values() if p["role"]=="RB")
        rush_exposure=sum(g["rush_attempts"] for g in recent)
        rb_pool=rng.binomial(rushes,rng.beta(1+rb_count,1+rush_exposure-rb_count,n))
        non_rb=rushes-rb_pool
        unknown_rb=rng.binomial(rb_pool,rng.beta(self.unseen_rush["alpha"],self.unseen_rush["beta"],n))
        known_rb=rb_pool-unknown_rb;backs=[];back_weights=[]
        for pid,role in candidates.items():
            if role!="RB":continue
            fit=self._share(pid,role,team,rng,n,"carries")
            if fit is not None:backs.append(pid);back_weights.append(fit[0])
        rb_draws={pid:np.zeros(n,dtype=int) for pid in backs}
        if backs:
            weights=np.asarray(back_weights)
            for i in range(n):
                alloc=rng.multinomial(int(known_rb[i]),weights[:,i]/weights[:,i].sum())
                for pid,v in zip(backs,alloc):rb_draws[pid][i]=v
        else:unknown_rb+=known_rb
        for pid,arr in rb_draws.items():
            draws[pid]["carries"]=arr
            donors=[p["values"]["rushing yards"]/p["values"]["carries"] for g,p in self._player_rows(pid,"carries") if p["values"]["carries"]>0 and "rushing yards" in p["values"]]
            if donors:draws[pid]["rushing yards"]=arr*rng.choice(donors,n)
        if np.any(sum(rb_draws.values(),np.zeros(n,dtype=int))+unknown_rb+non_rb!=rushes):
            reject("rushing_opportunity_not_conserved")
        # Use source-compatible solo / with-assist / assist categories.
        # Their shrunken means are fitted directly, then share a single
        # NB total. No second incompatible component split reduces means.
        for pid,markets in simple.items():
            role=candidates[pid]
            if role not in DEFENSE:continue
            fields=MARKETS[8:]
            own=[p["values"] for g,p in self.byplayer[pid] if all(m in p["values"] for m in fields)][-POLICY["player_window"]:]
            peers=[p["values"] for g,p in self.byrole[role] if all(m in p["values"] for m in fields)]
            if not own or not peers:continue
            def components(v):return [v["solo tackles"],v["tackle assists"],v["tackles + assists"]-v["solo tackles"]-v["tackle assists"]]
            if any(min(components(v))<0 for v in own+peers):reject("incompatible_tackle_source_components")
            w=len(own)/(len(own)+POLICY["prior_player_games"])
            means=w*np.mean([components(v) for v in own],axis=0)+(1-w)*np.mean([components(v) for v in peers],axis=0)
            mu=float(sum(means));var=w*float(np.var([v["tackles + assists"] for v in own],ddof=1) if len(own)>1 else mu)+(1-w)*float(np.var([v["tackles + assists"] for v in peers]))
            total=_nb(rng,mu,max(mu,var),n)
            split=np.array([rng.multinomial(int(t),means/mu) for t in total]) if mu else np.zeros((n,3),dtype=int)
            draws[pid].update({"tackles + assists":total,"solo tackles":split[:,0],"tackle assists":split[:,1]})
            diagnostics[pid]={"tackle_with_assist_mean":float(means[2]),
                "source_definition":"solo_plus_tackle_assists_plus_tackles_with_assist",
                "conditional_on_unverified_current_appearance":True,"publication_eligible":False}
        return {"draws":draws,"simple_control":simple,
          "team_pass_attempts":attempts,"team_rush_attempts":rushes,
          "unknown_qb_attempts":unknown_qb,"unknown_receiver_targets":unknown_target,
          "non_target_attempts":non_target,"player_diagnostics":diagnostics,
          "unknown_rb_attempts":unknown_rb,"non_rb_rush_attempts":non_rb,
          "qb_primary_proxy":qb_latest,"qb_transition_probabilities":self.qb_transition.tolist(),
          "unseen_recipient_fit":self.unseen,"conservation_ok":True,
          "original_pregame_source_certified":False,"production_promotion_authorized":False,
          "conditional_on_appearance_for_non_qb_markets":True,
          "jointly_constrained_markets":["pass attempts","targets","receptions","carries",*MARKETS[8:]],
          "independent_control_retained_separately":True}
