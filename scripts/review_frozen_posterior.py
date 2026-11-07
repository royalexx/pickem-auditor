#!/usr/bin/env python3
"""Read-only numerical review of copied frozen posteriors; never permits ranking.

Threshold comparisons are hypotheses, not model promotion or changed production
gates. Synthetic count thresholds diagnose numerical precision; they are not
historical sportsbook predictions or out-of-sample performance evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

CRITICAL=("population_workload","population_rate","player_chol_stds",
          "player_chol_corr","workload_sigma","opponent_rate_sd","home_effect",
          "season_rate_sd","season_workload_sd","count_dispersion","yardage_sigma","log_posterior_density")
OPERATIONAL=tuple(n for n in CRITICAL if n!="log_posterior_density")+("player_effect","opponent_rate","season_workload","season_rate")


def checksum(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()


def compare_thresholds(entries,*,divergences,bfmi,chains,expected_variables=None):
    """Keep old strict, fuller review, and relaxed hypothesis visibly distinct."""
    def group(names,rhat,bulk,tail=None):
        selected=[e for e in entries if names is None or e["variable"] in names]
        required=set(expected_variables or ())
        if names is not None:required.intersection_update(names)
        missing=sorted(required-{e["variable"] for e in entries})
        metrics=("rhat","bulk_ess")+(("tail_ess",) if tail is not None else ())
        finite=bool(expected_variables) and not missing and bool(selected) and all(all(e.get(k) is not None and math.isfinite(e[k])
                     for k in metrics) for e in selected)
        bad=[e["parameter"] for e in selected if any(e.get(k) is None or not math.isfinite(e[k])
             for k in metrics) or e.get("rhat",math.inf)>rhat
             or e.get("bulk_ess",-math.inf)<bulk
             or (tail is not None and e.get("tail_ess",-math.inf)<tail)]
        return {"parameters":len(selected),"max_rhat":max((e["rhat"] for e in selected if e.get("rhat") is not None),default=None),
                "min_bulk_ess":min((e["bulk_ess"] for e in selected if e.get("bulk_ess") is not None),default=None),
                "min_tail_ess":min((e["tail_ess"] for e in selected if e.get("tail_ess") is not None and math.isfinite(e["tail_ess"])),default=None),
                "missing_required_variables":missing,"inventory_provided":bool(expected_variables),
                "failed_parameter_count":len(bad),"first_failed_parameters":bad[:30],
                "numeric_thresholds_met":finite and not bad}
    common=(chains>=4 and divergences==0 and math.isfinite(bfmi) and bfmi>=.30)
    result={
      "current_operational_strict":group(OPERATIONAL,1.01,400),
      "all_parameter_strict_review":group(None,1.01,400,400),
      "critical_parameter_strict_review":group(CRITICAL,1.01,400,400),
      "operational_relaxed_hypothesis":group(OPERATIONAL,1.02,300),
      "all_parameter_relaxed_hypothesis":group(None,1.02,300,300)}
    for value in result.values():value["comparison_pass"]=bool(common and value["numeric_thresholds_met"])
    return result


def prediction_summary(q,*,quadrature_delta,stats):
    import numpy as np
    q=np.asarray(q,dtype=float)
    if q.ndim!=2 or min(q.shape)<2 or not np.isfinite(q).all() or np.any((q<0)|(q>1)):
        raise ValueError("invalid_chain_ordered_probability_functional")
    constant=bool(np.all(q==q.flat[0]))
    rhat=1. if constant else float(stats.rhat(q))
    ess=float(q.size) if constant else float(stats.ess(q,method="mean"))
    mcse=0. if constant else float(stats.mcse(q,method="mean"))
    means=q.mean(axis=1)
    finite=all(math.isfinite(x) for x in (rhat,ess,mcse,quadrature_delta))
    return {"q_mean":float(q.mean()),"chain_means":means.tolist(),
      "posterior_functional_sd":float(q.std(ddof=1)),
      "posterior_functional_quantiles_05_50_95":np.quantile(q,[.05,.5,.95]).tolist(),
      "posterior_functional_spread_is_calibrated_interval":False,
      "chain_mean_range":float(np.ptp(means)),"functional_rhat":rhat,
      "functional_mean_ess":ess,"mcmc_mcse":mcse,
      "quadrature_max_abs_delta":float(quadrature_delta),
      "numerical_review_pass":bool(finite and rhat<=1.01 and mcse<=.005
                                      and np.ptp(means)<=.02 and quadrature_delta<=.0001),
      "precision_policy":"Rhat<=1.01; MCSE<=0.005; chain range<=0.02; quadrature delta<=0.0001; research heuristic only",
      "mcmc_mcse_is_calibration_error":False}


def review_status(comparisons,predictions):
    """No output here authorizes a model or relaxes its original status."""
    if comparisons["all_parameter_strict_review"]["comparison_pass"]:
        status=("strict_sampler_pass_limited_prediction_probes_pass" if predictions and
                all(p["numerical_review_pass"] for p in predictions) else
                "strict_sampler_pass_prediction_probes_flagged" if predictions else
                "strict_sampler_pass_prediction_precision_unchecked")
    elif (comparisons["critical_parameter_strict_review"]["comparison_pass"] and
          comparisons["all_parameter_relaxed_hypothesis"]["comparison_pass"] and
          predictions and all(p["numerical_review_pass"] for p in predictions)):
        status="limited_provisional_shadow_candidate_requires_manual_review"
    else:status="restricted_pending_review"
    return {"review_status":status,"ranking_allowed":False,"publication_eligible":False,
            "automatic_promotion":False,"production_gate_changed":False,
            "provisional_shadow_execution_authorized":False}


def expected_variables(manifest):
    if (manifest.get("schema")!="multisport_joint_fit_manifest_v1" or
        manifest.get("model_version")!="multisport-joint-bayes-v1"):
        raise ValueError("unsupported_frozen_model_design")
    names={"population_workload","population_rate","player_z","player_effect","player_chol",
           "player_chol_corr","player_chol_stds","workload_sigma","opponent_rate_sd",
           "opponent_rate_z","opponent_rate","home_effect","log_posterior_density",
           "season_workload","season_rate"}
    names.add("count_dispersion" if manifest["family"]=="count" else "yardage_sigma")
    if len(manifest["seasons"])>1:
        names.update({"season_workload_sd","season_rate_sd","season_workload_z","season_rate_z",
                      "season_workload","season_rate"})
    return names


def parameter_entries(posterior,manifest,stats):
    import numpy as np
    entries=[];constants=[]
    for name,var in posterior.data_vars.items():
        raw=np.asarray(var.transpose("chain","draw",...),dtype=float)
        if not np.isfinite(raw).all():raise ValueError("nonfinite_posterior:"+name)
        flat=raw.reshape(raw.shape[:2]+(-1,))
        changing=np.any(flat!=flat[0,0,:],axis=(0,1))
        for index in np.flatnonzero(~changing):
            coordinate=tuple(int(i) for i in np.unravel_index(index,raw.shape[2:])) if raw.ndim>2 else ()
            label=name+(str(coordinate) if coordinate else "")
            structural=((name=="player_chol_corr" and coordinate in ((0,0),(1,1)) and flat[0,0,index]==1.)
                        or (name in ("season_workload","season_rate") and len(manifest["seasons"])==1
                            and flat[0,0,index]==0.))
            if structural:constants.append(label)
            else:entries.append({"variable":name,"coordinate":list(coordinate),"parameter":label,
                "rhat":None,"bulk_ess":None,"tail_ess":None,"mean_mcse":None,
                "diagnostic_failure":"unexpected_constant_coordinate"})
        if not changing.any():continue
        selected=flat[...,changing]
        rh=np.asarray(stats.rhat(selected)).ravel()
        bulk=np.asarray(stats.ess(selected,method="bulk")).ravel()
        tail=np.asarray(stats.ess(selected,method="tail",prob=(.05,.95))).ravel()
        mcse=np.asarray(stats.mcse(selected,method="mean")).ravel()
        for col,index in enumerate(np.flatnonzero(changing)):
            coordinate=tuple(int(i) for i in np.unravel_index(index,raw.shape[2:])) if raw.ndim>2 else ()
            label=name+(str(coordinate) if coordinate else "")
            item={"variable":name,"coordinate":list(coordinate),"parameter":label}
            for key,value in (("rhat",rh[col]),("bulk_ess",bulk[col]),("tail_ess",tail[col]),("mean_mcse",mcse[col])):
                item[key]=float(value) if math.isfinite(value) else None
            if coordinate and name in ("player_effect","player_z"):
                item["player_id"]=manifest["players"][coordinate[0]]
                if len(coordinate)>1:item["effect"]="workload" if coordinate[1]==0 else "production_rate"
            if coordinate and name in ("population_workload","population_rate"):
                item["position"]=manifest["positions"][coordinate[0]]
            entries.append(item)
    return entries,constants


def synthetic_count_precision(posterior,manifest,stats,entries=()):
    """Three train-posterior archetypes; deterministic workload quadrature per draw."""
    if manifest["family"]!="count":return []
    import numpy as np
    from scipy.special import roots_hermitenorm
    from scipy.stats import nbinom
    def array(name):return np.asarray(posterior[name],dtype=float)
    positions=np.array([manifest["positions"].index(manifest["player_position"][p]) for p in manifest["players"]])
    person=array("player_effect")
    s=len(manifest["seasons"])-1;o=0
    work=array("population_workload")[...,positions]+person[...,0]+array("season_workload")[...,s,None]
    rate=array("population_rate")[...,positions]+person[...,1]+array("season_rate")[...,s,None]+array("opponent_rate")[...,o,None]
    typical=np.median(np.exp(work+rate),axis=(0,1));ordering=np.argsort(typical)
    picks={int(ordering[round((len(ordering)-1)*q)]):["posterior_volume_quantile_"+str(q)] for q in (.1,.5,.9)}
    def add_player(index,reason):picks.setdefault(int(index),[]).append(reason)
    player_entries=[e for e in entries if e.get("player_id") and e.get("rhat") is not None]
    for selected,reason in ((max(player_entries,key=lambda e:e["rhat"],default=None),"worst_player_rhat"),
                            (min(player_entries,key=lambda e:e["bulk_ess"],default=None),"lowest_player_bulk_ess")):
        if selected:add_player(manifest["players"].index(selected["player_id"]),reason)
    add_player(np.argmax(np.std(work+rate,axis=(0,1))),"largest_log_volume_posterior_sd_not_verified_sparse_history")
    population=[e for e in entries if e.get("position") and e.get("bulk_ess") is not None]
    if population:
        worst=min(population,key=lambda e:e["bulk_ess"])
        eligible=[int(i) for i in ordering if manifest["player_position"][manifest["players"][i]]==worst["position"]]
        if eligible:add_player(eligible[len(eligible)//2],"lowest_global_ess_position_representative")
    sigma=array("workload_sigma");alpha=array("count_dispersion")
    out=[]
    for player,reasons in sorted(picks.items()):
        def functional(line,side,n):
            nodes,weights=roots_hermitenorm(n);weights=weights/math.sqrt(2*math.pi)
            mu=np.exp(work[...,player,None]+rate[...,player,None]+sigma[...,None]*nodes)
            p=alpha[...,None]/(alpha[...,None]+mu)
            probabilities=(nbinom.sf(math.floor(line),alpha[...,None],p) if side=="over" else
                           nbinom.cdf(math.floor(line),alpha[...,None],p))
            return np.sum(probabilities*weights,axis=-1)
        mean=float(typical[player]);cdf_cache={}
        def cdf_at(k):
            if k not in cdf_cache:cdf_cache[k]=functional(k+.5,"under",24)
            return cdf_cache[k]
        for side,target_cdf in (("over",.2),("under",.8)):
            lo=0;hi=max(8,int(math.ceil(mean*5+20)))
            while float(cdf_at(hi).mean())<target_cdf and hi<100000:hi*=2
            while hi-lo>1:
                mid=(lo+hi)//2
                if float(cdf_at(mid).mean())<target_cdf:lo=mid
                else:hi=mid
            k=min(set((0,lo,hi)),key=lambda k:abs(float(cdf_at(k).mean())-target_cdf))
            line=k+.5;coarse=cdf_at(k) if side=="under" else 1-cdf_at(k)
            refined=coarse;delta=math.inf;nodes=24
            for nodes in (48,96,192,384):
                again=functional(line,side,nodes);delta=float(np.max(np.abs(again-refined)));refined=again
                if delta<=.0001:break
            out.append({"player_id":manifest["players"][player],"opponent":manifest["opponents"][o],
               "season":manifest["seasons"][s],"home":False,"line":line,"side":side,
               "context_kind":"synthetic_diagnostic_archetype_not_recorded_forecast",
               "probe_selection_reasons":reasons,
               "workload_quadrature_nodes":nodes,"workload_quadrature_converged":delta<=.0001,
               "near_80_percent":abs(float(refined.mean())-.8)<=.05,
               **prediction_summary(refined,quadrature_delta=delta,stats=stats)})
    return out


def review(posterior_path,manifest_path,*,synthetic_predictions=False):
    import arviz as az
    import arviz_stats as stats
    import numpy as np
    manifest=json.loads(Path(manifest_path).read_text())
    trace=az.from_netcdf(posterior_path)
    posterior=trace.posterior.to_dataset() if hasattr(trace.posterior,"to_dataset") else trace.posterior
    samples=trace.sample_stats.to_dataset() if hasattr(trace.sample_stats,"to_dataset") else trace.sample_stats
    if "lp" not in samples:raise ValueError("missing_log_posterior_density")
    posterior=posterior.assign(log_posterior_density=samples["lp"])
    required=expected_variables(manifest)
    missing=required-set(posterior.data_vars)
    if missing:raise ValueError("missing_required_posterior_variables:"+",".join(sorted(missing)))
    if any(samples.sizes.get(k)!=posterior.sizes.get(k) for k in ("chain","draw")):
        raise ValueError("posterior_sample_stats_shape_mismatch")
    if (posterior.sizes["chain"]!=manifest.get("sampler_chains") or
        posterior.sizes["draw"]!=manifest.get("sampler_retained_draws_per_chain")):
        raise ValueError("posterior_manifest_sampling_shape_mismatch")
    energy=np.asarray(samples["energy"].transpose("chain","draw"),dtype=float)
    if energy.ndim!=2 or min(energy.shape)<2 or not np.isfinite(energy).all():raise ValueError("invalid_chain_energy")
    bfmi=np.mean(np.diff(energy,axis=1)**2,axis=1)/np.var(energy,axis=1)
    if not np.isfinite(bfmi).all():raise ValueError("nonfinite_bfmi")
    entries,constants=parameter_entries(posterior,manifest,stats)
    divergent=np.asarray(samples["diverging"].transpose("chain","draw"))
    if divergent.shape!=energy.shape or not np.isin(divergent,[0,1]).all():raise ValueError("invalid_divergence_flags")
    divergences=int(divergent.sum());chains=int(posterior.sizes["chain"])
    depth={"status":"not_recorded","new_veto_applied":False}
    if "tree_depth" in samples:
        depths=np.asarray(samples["tree_depth"].transpose("chain","draw"))
        if depths.shape!=energy.shape or not np.isfinite(depths).all():raise ValueError("invalid_tree_depth")
        depth={"status":"recorded","max_observed":int(depths.max()),"new_veto_applied":False,
               "saturation_count":None,"saturation_semantics":"Efficiency diagnostic; no new production veto"}
        if "reached_max_treedepth" in samples:
            reached=np.asarray(samples["reached_max_treedepth"].transpose("chain","draw"))
            if reached.shape!=energy.shape or not np.isin(reached,[0,1]).all():raise ValueError("invalid_depth_saturation_flags")
            depth["saturation_count"]=int(reached.sum())
    diagnostic_required=required-({"season_workload","season_rate"} if len(manifest["seasons"])==1 else set())
    comparisons=compare_thresholds(entries,divergences=divergences,bfmi=float(bfmi.min()),chains=chains,expected_variables=diagnostic_required)
    predictions=synthetic_count_precision(posterior,manifest,stats,entries) if synthetic_predictions else []
    return {"schema":"frozen_posterior_readonly_review_v3","sport":manifest.get("sport"),"stat":manifest.get("stat"),
       "review_script_sha256":checksum(__file__),
       "manifest_sha256":checksum(manifest_path),"posterior_sha256":checksum(posterior_path),
       "original_diagnostics":manifest.get("diagnostics"),"source_digest":manifest.get("source_digest"),
       "original_sampling_status_unchanged":True,"probability_calibration_status":"not_evaluated",
       "out_of_sample_performance_evaluated":False,
       "chains":chains,"draws_per_chain":int(posterior.sizes["draw"]),"divergences":divergences,
       "bfmi_by_chain":bfmi.tolist(),"arviz_version":az.__version__,"arviz_stats_version":stats.__version__,
       "tree_depth_review":depth,
       "constant_coordinates_excluded_from_rhat":constants,"parameter_count":len(entries),
       "expected_variable_inventory":sorted(required),
       "expected_nonconstant_diagnostic_inventory":sorted(diagnostic_required),
       "comparisons":comparisons,"worst_rhat":sorted(entries,key=lambda e:e["rhat"] if e["rhat"] is not None else math.inf,reverse=True)[:20],
       "lowest_bulk_ess":sorted(entries,key=lambda e:e["bulk_ess"] if e["bulk_ess"] is not None else -math.inf)[:20],
       "lowest_tail_ess":sorted(entries,key=lambda e:e["tail_ess"] if e["tail_ess"] is not None else -math.inf)[:20],
       "prediction_precision":predictions,"parameter_diagnostics":entries,
       "prediction_probe_scope":"Limited synthetic archetypes, worst player coordinates and global/high-uncertainty probes; no guarantee for other players or real future props",
       **review_status(comparisons,predictions)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--posterior",type=Path,required=True);p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--synthetic-prediction-precision",action="store_true")
    a=p.parse_args()
    if a.out.exists() or a.out.resolve() in (a.posterior.resolve(),a.manifest.resolve()):
        p.error("review_output_must_be_new_and_separate_from_original_artifacts")
    result=review(a.posterior,a.manifest,synthetic_predictions=a.synthetic_prediction_precision)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open("x",encoding="utf-8") as f:f.write(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:result[k] for k in ("sport","stat","review_status","parameter_count","ranking_allowed")}))


if __name__=="__main__":main()
