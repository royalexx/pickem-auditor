"""Pre-2024 Bayesian allocation + coherent team/individual Monte Carlo.

Uses XGBoost team pass/rush forecasts and historical team dispersion as an
uncertain opportunity prior; Dirichlet targets/carries allocation, beta catch
rates, and shared-opportunity defensive Gamma-Poisson. All posterior parameters
are inferred from pre-2024 history. No 2024 weekly update or fit.

This is empirical/conjugate Bayesian inference, NOT an accepted PyMC NUTS model.
All predictions on synthetic lines are research only. Actual 2024 active
rosters are unknown; never rank these forecasts as real bettable picks.
"""
from __future__ import annotations
from datetime import date
import hashlib,math
from collections import defaultdict

import numpy as np
import nfl_pre2024_team_defense_challenger as priors
from nfl_pre2024_pbp_ngs_sources import CUTOFF

VERSION="xgboost_team_dirichlet_beta_nb_montecarlo_pre2024_v1"
MAX_LAST_TEAM_AGE_DAYS=90
MIN_PLAYER_HISTORY=3
ALLOCATION_CONCENTRATION=28.
HISTORICAL_PLAYER_HALF_LIFE_DAYS=35.
DEFENSIVE_OPPORTUNITY_DISPERSION=12.

def _when(r):
    return date.fromisoformat(str(r["gameday"])[:10])

def _pre2024_only(state):
    for bucket in ("player","role","team_offense","opponent_allowed","ngs"):
        for records in state[bucket].values():
            for row in records:
                if _when(row)>=CUTOFF or int(row.get("season",2023))>=2024:
                    raise ValueError("2024_plus_data_in_hierarchical_posterior")
    return True

def _history(state,stat,pid,team,limit=5):
    rows=[r for r in state["player"].get((stat,str(pid)),())
          if r["team"]==team and _when(r)<CUTOFF]
    return sorted(rows,key=lambda r:r["gameday"],reverse=True)[:limit]

def _recency(values):
    if not values:return 0.,0.
    weights=np.asarray([2**(-(CUTOFF-_when(r)).days/HISTORICAL_PLAYER_HALF_LIFE_DAYS)
                         for r in values],dtype=float)
    vals=np.asarray([float(r["value"]) for r in values],dtype=float)
    if not np.isfinite(vals).all():raise ValueError("invalid_posterior_history")
    return float(np.dot(vals,weights)/weights.sum()),float(weights.sum())

def previous_roster(state,teams):
    """Only December 2023 observed identity; NOT 2024 active roster evidence."""
    _pre2024_only(state)
    by_team={t:[] for t in teams}
    for pid,r in state["latest_by_player"].items():
        day=_when(r)
        if day>=CUTOFF:raise ValueError("2024_plus_player_identity")
        if int(r["season"])!=2023 or (CUTOFF-day).days>MAX_LAST_TEAM_AGE_DAYS:
            continue
        team=r["team"]
        if team in by_team:by_team[team].append((str(pid),r["position"]))
    for team in by_team:by_team[team].sort()
    return by_team

def _eligible(state,team,roster,stat):
    ans=[]
    for pid,pos in roster:
        if pos not in priors.ROLE_POS[stat]:continue
        rows=_history(state,stat,pid,team)
        if len(rows)<MIN_PLAYER_HISTORY:continue
        avg,eff=_recency(rows)
        prior=priors.MARKET_BASE_PRIOR[stat]
        # Recent five games receive 82%; older player records never enter
        # as individual features, only as small generic position prior.
        weight=min(.82,.28+.108*len(rows))
        expected=max(0.04,weight*avg+(1-weight)*prior)
        ans.append((pid,pos,expected,rows))
    return ans

def _dirichlet_share(expected,total):
    """Unlisted players and no-target outcomes preserve the conservation law."""
    arr=np.asarray(expected,dtype=float)
    if np.any(~np.isfinite(arr)) or np.any(arr<0):
        raise ValueError("invalid_allocation_opportunity")
    total=max(1.,float(total))
    raw=arr/total
    if raw.sum()>.94:raw*=.94/raw.sum()
    rem=max(.06,1.-raw.sum())
    q=np.r_[raw,rem]
    q=q/q.sum()
    alpha=q*ALLOCATION_CONCENTRATION+.25
    return alpha

def _sample_nb(rng,mu,k,draws):
    if not math.isfinite(mu) or mu<0 or not math.isfinite(k) or k<=0:
        raise ValueError("invalid_team_opportunity_posterior")
    p=k/(k+max(mu,1.e-8))
    return rng.negative_binomial(k,p,size=draws)

def _alloc(rng,totals,alpha):
    ps=rng.dirichlet(alpha,size=len(totals))
    # Fully coupled conditional draw: all players' outcomes sum to team total.
    return np.asarray([rng.multinomial(int(n),p) for n,p in zip(totals,ps)],
                       dtype=np.int32)

def _beta_catch(state,pid,team):
    targets=_history(state,"targets",pid,team)
    caught=_history(state,"receptions",pid,team)
    t=sum(max(0.,float(r["value"])) for r in targets)
    r=sum(max(0.,float(x["value"])) for x in caught)
    if r>t:r=t
    return 2.+r*.38,1.+(t-r)*.38

def _per_catch_yards(state,pid,team):
    yards=_history(state,"receiving yards",pid,team)
    catches=_history(state,"receptions",pid,team)
    y=sum(float(v["value"]) for v in yards)
    n=sum(float(v["value"]) for v in catches)
    return max(-4.,min(32.,(y+24.)/(n+2.)))

def _per_carry_yards(state,pid,team):
    yards=_history(state,"rushing yards",pid,team)
    carries=_history(state,"carries",pid,team)
    y=sum(float(v["value"]) for v in yards)
    n=sum(float(v["value"]) for v in carries)
    return max(-3.,min(12.,(y+8.)/(n+2.)))

def _store(out,team,pid,pos,market,draws):
    k=(team,pid,market)
    if k in out:raise ValueError("duplicate_monte_carlo_player_stat")
    val=np.asarray(draws,dtype=float)
    if np.any(~np.isfinite(val)):raise ValueError("nonfinite_monte_carlo_draw")
    out[k]={"position":pos,"samples":val}

def _simulate_offense(rng,out,state,team,roster,passmu,rushmu,pass_k,rush_k,draws):
    attempts=_sample_nb(rng,passmu,pass_k,draws)
    rushes=_sample_nb(rng,rushmu,rush_k,draws)

    receivers=_eligible(state,team,roster,"targets")
    if receivers:
        t_alloc=_alloc(rng,attempts,
                       _dirichlet_share([p[2] for p in receivers],passmu))
        recv_yards=np.zeros(draws,dtype=float)
        ncompletions=np.zeros(draws,dtype=int)
        for j,(pid,pos,expected,_) in enumerate(receivers):
            targets=t_alloc[:,j]
            shape1,shape2=_beta_catch(state,pid,team)
            catches=rng.binomial(targets,rng.beta(shape1,shape2,size=draws))
            mean_yards=_per_catch_yards(state,pid,team)
            yardage=np.where(catches>0,
                catches*mean_yards+rng.standard_t(6,size=draws)*(
                    9.*np.sqrt(np.maximum(catches,1))),0.)
            _store(out,team,pid,pos,"targets",targets)
            _store(out,team,pid,pos,"receptions",catches)
            _store(out,team,pid,pos,"receiving yards",yardage)
            ncompletions+=catches
            recv_yards+=yardage
        other_targets=t_alloc[:,-1]
        other_caught=rng.binomial(other_targets,.66)
        ncompletions+=other_caught
        recv_yards+=np.where(other_caught>0,
              other_caught*11.+rng.standard_t(6,size=draws)*(
              8.*np.sqrt(np.maximum(other_caught,1))),0.)
    else:
        ncompletions=rng.binomial(attempts,.63)
        recv_yards=np.where(ncompletions>0,ncompletions*10.+
            rng.standard_t(6,size=draws)*8.*np.sqrt(np.maximum(ncompletions,1)),0.)

    qbs=_eligible(state,team,roster,"pass attempts")
    if qbs:
        qa=_alloc(rng,attempts,_dirichlet_share([p[2] for p in qbs],passmu))
        remaining_att=attempts.astype(int).copy()
        remaining_comp=np.minimum(ncompletions,remaining_att).astype(int).copy()
        for j,(pid,pos,_,_) in enumerate(qbs):
            this_att=qa[:,j]
            # Sequential multivariate hypergeometric: respects both
            # completions<=attempts and total team completions.
            take=np.minimum(this_att,remaining_att)
            this_comp=rng.hypergeometric(
                ngood=remaining_comp,nbad=np.maximum(remaining_att-remaining_comp,0),
                nsample=take)
            this_yards=recv_yards*np.where(ncompletions>0,
                               this_comp/np.maximum(ncompletions,1),0.)
            _store(out,team,pid,pos,"pass attempts",this_att)
            _store(out,team,pid,pos,"completions",this_comp)
            _store(out,team,pid,pos,"passing yards",this_yards)
            remaining_comp-=this_comp
            remaining_att-=take
    backs=_eligible(state,team,roster,"carries")
    if backs:
        carries=_alloc(rng,rushes,
                       _dirichlet_share([p[2] for p in backs],rushmu))
        for j,(pid,pos,_,_) in enumerate(backs):
            n=carries[:,j]
            ypc=_per_carry_yards(state,pid,team)
            yards=np.where(n>0,n*ypc+rng.standard_t(6,size=draws)*(
                         4.5*np.sqrt(np.maximum(n,1))),0.)
            _store(out,team,pid,pos,"carries",n)
            _store(out,team,pid,pos,"rushing yards",yards)
    return attempts,rushes

def _simulate_defense(rng,out,state,team,roster,opponent_plays,draws):
    # Defensive tackles are not conserved 1:1 to plays (assist credits).
    # Shared opponent volume and per-player gamma latent create correlation.
    group=[]
    for pid,pos in roster:
        if pos in priors.ROLE_POS["solo tackles"]:
            solo=_history(state,"solo tackles",pid,team)
            assists=_history(state,"tackle assists",pid,team)
            if len(solo)>=MIN_PLAYER_HISTORY and len(assists)>=MIN_PLAYER_HISTORY:
                group.append((pid,pos,solo,assists))
    for pid,pos,solo,assists in group:
        s,_=_recency(solo);a,_=_recency(assists)
        # Last-five player totals matter most. Convert per-game pace into
        # opportunity-adjusted rate with 2023 typical 62 opponent plays.
        s=.82*s+.18*priors.MARKET_BASE_PRIOR["solo tackles"]
        a=.82*a+.18*priors.MARKET_BASE_PRIOR["tackle assists"]
        gamma=rng.gamma(shape=DEFENSIVE_OPPORTUNITY_DISPERSION,
                         scale=1./DEFENSIVE_OPPORTUNITY_DISPERSION,size=draws)
        mult=opponent_plays/62.*gamma
        solo_draw=rng.poisson(np.maximum(0.,s*mult))
        assist_draw=rng.poisson(np.maximum(0.,a*mult))
        _store(out,team,pid,pos,"solo tackles",solo_draw)
        _store(out,team,pid,pos,"tackle assists",assist_draw)
        _store(out,team,pid,pos,"tackles + assists",solo_draw+assist_draw)

def simulate_game(state,fixture,team_volumes,team_dispersions,*,draws=2000,seed=20261109):
    """Returns joint samples. Seeded for repeatability; no 2024 update."""
    if not 100<=int(draws)<=100000:raise ValueError("simulation_draw_count")
    _pre2024_only(state)
    gid=str(fixture["game_id"])
    home=str(fixture["home_team"]);away=str(fixture["away_team"])
    if home==away or not gid:raise ValueError("invalid_fixture")
    for team in (home,away):
        if team not in team_volumes or team not in team_dispersions:
            raise ValueError("missing_team_xgb_forecast")
    salt=int(hashlib.sha256(gid.encode()).hexdigest()[:8],16)
    rng=np.random.default_rng((int(seed)+salt)%(2**32))
    roster=previous_roster(state,[home,away])
    samples={}
    team_plays={}
    for t in (home,away):
        mu=team_volumes[t];k=team_dispersions[t]
        pa,ru=_simulate_offense(rng,samples,state,t,roster[t],
           float(mu["pass_attempts"]),float(mu["rush_attempts"]),
           float(k["pass_attempts"]),float(k["rush_attempts"]),int(draws))
        team_plays[t]=pa+ru
    for team,opp in ((home,away),(away,home)):
        _simulate_defense(rng,samples,state,team,roster[team],
                          team_plays[opp],int(draws))
    if not samples:return {},{"status":"no_pre2024_eligible_player_histories"}
    return samples,{"status":"frozen_pre2024_posterior_predictive",
        "game_id":gid,"draws":int(draws),"rng_seed":int(seed),"team": {
          t:{"xgb_pass_mean":float(team_volumes[t]["pass_attempts"]),
             "xgb_rush_mean":float(team_volumes[t]["rush_attempts"]),
             "roster_derived_from":"2023_history_not_2024_verified"}
          for t in (home,away)},
        "family":"NB_team_Dirichlet_multinomial_Beta_Binomial_Gamma_Poisson",
        "ftn_2024_pulled_archive_excluded":True,
        "2024_training_data_used":False,"sportsbook_offer_verified":False}

def summarize_game(state,fixture,team_volumes,team_dispersions,*,draws=2000,seed=20261109):
    samples,receipt=simulate_game(state,fixture,team_volumes,team_dispersions,
                                 draws=draws,seed=seed)
    forecasts=[]
    for (team,pid,market),record in sorted(samples.items()):
        pos=record["position"]
        line=priors.research_line(state,stat=market,player_id=pid,
              position=pos,team=team,asof=CUTOFF.isoformat())
        if line is None:continue
        vals=record["samples"]
        forecasts.append({"game_id":fixture["game_id"],"year":2024,
            "week":int(fixture["week"]),"team":team,"player_id":pid,
            "position":pos,"market":market,"research_line":line,
            "simulated_mean":float(vals.mean()),
            "p_over":float(np.mean(vals>line)),
            "p_under":float(np.mean(vals<line)),
            "p_push":float(np.mean(vals==line)),
            "p10":float(np.quantile(vals,.10)),"p90":float(np.quantile(vals,.90)),
            "draws":int(draws),"model_asof":"2024-01-01",
            "training_data_from_2024":False,
            "roster_2024_verified":False,"bookmaker_quote_verified":False})
    return forecasts,receipt
