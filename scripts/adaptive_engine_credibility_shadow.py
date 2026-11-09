"""Beuoy-inspired, strictly chronological *shadow* engine credibility tracker.

Beuoy (2026) evaluates repeatedly revised forecasts as canonical Kelly bettors.
Our one-shot pregame props do not satisfy that setting. This conservative
comparison therefore uses settled binary likelihood ratios versus a pre-event
weighted consensus, often called Bayesian model evidence/wealth tracking.

This is NOT Beuoy's full market-clearing continuous-time Kelly algorithm, NOT
a wagering simulator, and NEVER controls production weights without separate
out-of-sample validation. Freeze all pre-event engine forecasts first.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import date
import math

EPS=1.e-6
MODEL_NAMES=("Engine_A","Engine_B","Bayesian_A","Bayesian_B","NUTS","Team_Dynamic")
MAX_ENGINE_WEIGHT=.45
MIN_ENGINE_WEIGHT=.05
EVIDENCE_HALF_LIFE_DAYS=84.
MIN_SETTLED_GAMES_FOR_RELEASE=100

def _clip_probability(x):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):
        raise ValueError("engine_forecast_invalid_probability")
    if not 0<=x<=1:raise ValueError("engine_forecast_probability_outside_unit_interval")
    return max(EPS,min(1-EPS,float(x)))

def _bounded_softmax(values):
    # Two-engine shadow studies cannot use a 45% maximum for BOTH engines.
    # Widen only for a two-engine comparison; the six-engine cap stays 45%.
    maximum=MAX_ENGINE_WEIGHT if len(values)>=3 else 1.-MIN_ENGINE_WEIGHT
    mx=max(values)
    raw=[math.exp(v-mx) for v in values]
    w=[x/sum(raw) for x in raw]
    # Exact convex projection to capped simplex with uniform redistribution.
    # This is not optimized to betting returns; caps prevent weight collapse
    # on sparse and correlated historical evidence.
    for _ in range(40):
        clipped=[min(maximum,max(MIN_ENGINE_WEIGHT,x)) for x in w]
        rem=1.-sum(clipped)
        active=[i for i,x in enumerate(clipped) if MIN_ENGINE_WEIGHT+1e-9 < x < maximum-1e-9]
        if abs(rem)<1e-12:return clipped
        if not active:break
        increment=rem/len(active)
        w=[(x+increment if i in active else x) for i,x in enumerate(clipped)]
    return [1./len(w)]*len(w)

@dataclass
class ShadowCredibility:
    engines:tuple=MODEL_NAMES
    wealth_log:dict=field(default_factory=dict)
    last_settled:date|None=None
    settled_games:int=0

    def __post_init__(self):
        if not self.engines or len(self.engines)!=len(set(self.engines)):
            raise ValueError("duplicate_or_missing_engine_names")
        if len(self.engines)*MIN_ENGINE_WEIGHT>1. or len(self.engines)*(
                MAX_ENGINE_WEIGHT if len(self.engines)>=3 else 1.-MIN_ENGINE_WEIGHT)<1.:
            raise ValueError("impossible_weight_constraints")
        for e in self.engines:self.wealth_log.setdefault(e,0.)

    def weights(self,*,release=False):
        # The shadow cannot become a production weight estimator without a
        # legitimate holdout calibration and a separate release gate.
        if release and self.settled_games<MIN_SETTLED_GAMES_FOR_RELEASE:
            return None
        values=[self.wealth_log[e] for e in self.engines]
        return dict(zip(self.engines,_bounded_softmax(values)))

    def update_settled_slate(self,settlement_day,observations):
        """All outcomes must be frozen and settled, from one calendar slate.

        observations: (game_id, outcome in {0,1}, {engine: probability})
        All engines must forecast the same binary event. Per-game averaging
        reduces (but does NOT eliminate) overlapping markets' dependence.
        Does not allow updates within the slate, preventing order arbitrage.
        """
        day=date.fromisoformat(str(settlement_day))
        if self.last_settled is not None and day<=self.last_settled:
            raise ValueError("nonchronological_engine_credibility_update")
        old=self.weights()
        updates={e:[] for e in self.engines}
        pergame={}
        for game_id,y,forecasts in observations:
            if not isinstance(game_id,str) or not game_id.strip():
                raise ValueError("missing_game_identity")
            if type(y) is not int or y not in (0,1):
                raise ValueError("unsettled_or_nonbinary_outcome")
            if set(forecasts)!=set(self.engines):
                raise ValueError("incomplete_engine_comparison")
            p={e:_clip_probability(forecasts[e]) for e in self.engines}
            consensus=sum(old[e]*p[e] for e in self.engines)
            base=consensus if y else 1.-consensus
            items={}
            for e in self.engines:
                like=p[e] if y else 1.-p[e]
                items[e]=math.log(like/base)
            pergame.setdefault(game_id,[]).append(items)
        # Discount *past credibility*, not recent forecasts. No parameter
        # update is made until the whole slate has been fully graded.
        if self.last_settled is not None:
            gap=(day-self.last_settled).days
            factor=2.**(-gap/EVIDENCE_HALF_LIFE_DAYS)
            for e in self.engines:self.wealth_log[e]*=factor
        for game_id,records in pergame.items():
            for e in self.engines:
                signal=sum(x[e] for x in records)/len(records)
                # A single game with many correlated markets has a capped
                # total contribution to the subsequent engine credibility.
                self.wealth_log[e]+=max(-.75,min(.75,signal))
        self.settled_games+=len(pergame)
        self.last_settled=day
        return {"settled_games_added":len(pergame),
                "settled_games_total":self.settled_games,
                "next_slate_shadow_weights":self.weights(),
                "production_allowed":False,
                "method":"Beuoy_inspired_settled_likelihood_ratio_shadow_NOT_full_Kelly"}
