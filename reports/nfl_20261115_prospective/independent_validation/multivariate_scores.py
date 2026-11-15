"""Independent J4 multivariate scoring, research only, no team-state mutation.

These functions score a *common*, frozen vector of player outcomes against the
same sampled cohort. They do not construct sportsbook combination suggestions.
Feature order, units, period and outcome definition must match exactly.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import pathlib
import numpy as np


def _validate(ensemble, observed, scales=None):
    x = np.asarray(ensemble, dtype=float)
    y = np.asarray(observed, dtype=float)
    if x.ndim != 2 or y.ndim != 1 or x.shape[1] != y.size or not x.shape[0] or not y.size:
        raise ValueError("JOINT_VECTOR_DIMENSIONS_MISMATCH")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("NONFINITE_JOINT_OUTCOME")
    sc = np.ones(y.size) if scales is None else np.asarray(scales, dtype=float)
    if sc.shape != y.shape or np.any(~np.isfinite(sc)) or np.any(sc <= 0):
        raise ValueError("INVALID_PRESPECIFIED_SCALES")
    return x/sc, y/sc


def energy_score(ensemble, observed, scales=None, batch=64):
    """V-statistic ES = E||X-y|| - 0.5 E||X-X'||; L2 norm.

    This is the ensemble empirical distribution's proper multivariate score.
    Chunk the quadratic term to bound peak RAM; no independently matched draws.
    """
    x, y = _validate(ensemble, observed, scales)
    n = len(x)
    first = float(np.linalg.norm(x-y, axis=1).mean())
    second_sum = 0.0
    for start in range(0,n,batch):
        z = x[start:start+batch]
        second_sum += float(np.linalg.norm(z[:,None,:]-x[None,:,:],axis=2).sum())
    return max(0.0, first - 0.5*second_sum/(n*n))


def variogram_score(ensemble, observed, p=0.5, scales=None, pair_weights=None):
    """Variogram VS_p, unordered pairs with fixed weights w_ij >= 0."""
    x, y = _validate(ensemble, observed, scales)
    if not 0 < p <= 2: raise ValueError("INVALID_VARIAGRAM_EXPONENT")
    d = len(y)
    w = np.ones((d,d)) if pair_weights is None else np.asarray(pair_weights,dtype=float)
    if w.shape != (d,d) or np.any(~np.isfinite(w)) or np.any(w < 0) or not np.allclose(w,w.T):
        raise ValueError("INVALID_PAIR_WEIGHTS")
    total = 0.0
    for i in range(d):
        for j in range(i+1,d):
            obs = abs(y[i]-y[j])**p
            pred = float(np.mean(np.abs(x[:,i]-x[:,j])**p))
            total += float(w[i,j])*(obs-pred)**2
    return float(total)


def independent_marginal_null(ensemble, seed):
    """Permute each dimension independently, preserving exact marginal ensembles."""
    x=np.asarray(ensemble,dtype=float)
    if x.ndim!=2 or not np.all(np.isfinite(x)):raise ValueError("INVALID_JOINT_ENSEMBLE")
    rng=np.random.default_rng(int(seed))
    return np.column_stack([rng.permutation(x[:,i]) for i in range(x.shape[1])])


def event_probability(ensemble, dimension_a, line_a, dimension_b, line_b, observed=None):
    """Diagnostic P(two specified threshold events), never entry recommendation."""
    x=np.asarray(ensemble,dtype=float)
    if x.ndim!=2 or x.shape[0]==0 or not np.all(np.isfinite(x)):
        raise ValueError("INVALID_JOINT_ENSEMBLE")
    if not 0<=dimension_a<x.shape[1] or not 0<=dimension_b<x.shape[1]:
        raise ValueError("UNKNOWN_JOINT_DIMENSION")
    if not np.isfinite(line_a) or not np.isfinite(line_b):raise ValueError("BAD_ORIGINAL_LINE")
    p_a=float(np.mean(x[:,dimension_a]>line_a))
    p_b=float(np.mean(x[:,dimension_b]>line_b))
    p_joint=float(np.mean((x[:,dimension_a]>line_a)&(x[:,dimension_b]>line_b)))
    return {"p_joint":p_joint,"p_independent_product":p_a*p_b,
            "joint_minus_product":p_joint-p_a*p_b,
            "joint_mc_se":math.sqrt(p_joint*(1-p_joint)/len(x)),
            "observed_joint":None if observed is None else bool(observed[dimension_a]>line_a and observed[dimension_b]>line_b)}


def run_selftest():
    # Hand-computable reference examples, distinct from simulator implementation.
    a=np.array([[0.0],[2.0]])
    assert abs(energy_score(a,[1.0])-0.5)<1e-12
    assert abs(energy_score([[0],[0]],[1])-1)<1e-12
    assert variogram_score([[0,0],[2,2]],[1,1])==0
    assert abs(variogram_score([[0,2],[2,0]],[1,1])-2)<1e-12
    ensemble=np.array([[0,0],[2,2],[1,1],[0,0]],dtype=float)
    shuffled=independent_marginal_null(ensemble,412)
    assert np.array_equal(np.sort(shuffled,axis=0),np.sort(ensemble,axis=0))
    assert event_probability(ensemble,0,.5,1,.5)['p_joint']==.5
    print("WS4_INDEPENDENT_JOINT_SCORE_SELFTEST_PASS")


if __name__=="__main__":
    run_selftest()