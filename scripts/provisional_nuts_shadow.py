#!/usr/bin/env python3
"""Explicitly provisional NFL NUTS predictions for prospective shadow validation.

NEVER changes the Engine A/B production consensus, ranks, or tiers. Downloads
only four pinned completed artifacts; checks hashes and original diagnostics.
No trained source or sampler is modified and no new NUTS training is launched.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import urllib.request
import zipfile

import nuts_slate_shadow as parent

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/"config/provisional_nuts_artifacts.json"
VERSION="nfl-provisional-nuts-shadow-v1"


def load_policy(path=None):
    # Opt-in extended manifest can be created only before game-time
    # from completed, digest-pinned GitHub training artifacts.
    chosen=Path(path or os.getenv("PICKEM_PROVISIONAL_POLICY_PATH") or CONFIG)
    config=json.loads(chosen.read_text(encoding="utf-8"))
    baseline=json.loads(CONFIG.read_text(encoding="utf-8"))
    if config.get("schema")!="pickem_provisional_nuts_asset_manifest_v1":
        raise ValueError("unknown_provisional_model_policy")
    if (config.get("scope")!="shadow_only_no_production_ranking"
            or config.get("frozen_model_sha")!=baseline["frozen_model_sha"]
            or config.get("frozen_history_sha")!=baseline["frozen_history_sha"]
            or config.get("training_cutoff_exclusive")!=baseline["training_cutoff_exclusive"]):
        raise ValueError("provisional_model_provenance_mismatch")
    p=config["policy"]
    if p!=baseline["policy"] or (
        p!={"max_rhat":1.02,"min_bulk_ess":300,"max_divergences":0,
             "min_bfmi":0.30,"require_original_strict_failure":True}):
        raise ValueError("unreviewed_provisional_thresholds")
    models=config.get("models")
    if (not isinstance(models,list) or not 4<=len(models)<=16
            or models[:4]!=baseline["models"]):
        raise ValueError("original_four_pinned_models_must_be_preserved")
    from population_history import COUNT
    expected={"pass attempts","targets","rushing touchdowns","receiving touchdowns"}
    if {x["stat"] for x in models[:4]}!=expected:
        raise ValueError("invalid_original_provisional_markets")
    seen=set()
    for i,m in enumerate(models):
        if (m.get("sport")!="NFL" or m.get("stat") not in COUNT["NFL"]
                or m["stat"] in seen
                or type(m.get("run_id")) is not int
                or type(m.get("artifact_id")) is not int
                or type(m.get("size_bytes")) is not int or m["size_bytes"]<10000
                or type(m.get("index")) is not int):
            raise ValueError("invalid_provisional_frozen_asset")
        seen.add(m["stat"])
        if i>=4 and (m["index"]<9 or m["index"]>16):
            raise ValueError("additional_model_not_a_post_tackles_completed_market")
        if (type(m.get("sha256")) is not str or len(m["sha256"])!=64
                or any(c not in "0123456789abcdef" for c in m["sha256"])):
            raise ValueError("missing_pinned_artifact_sha256")
        if m.get("strict_accepted",False) not in (True,False):
            raise ValueError("invalid_research_model_strict_status")
    return config


def provisional_diagnostics(d, p, *, strict_accepted=False):
    def finite_num(name):
        v=d.get(name)
        if type(v) not in (int,float) or not math.isfinite(v):
            raise ValueError("missing_or_nonfinite_posterior_diagnostics_"+name)
        return float(v)
    return (d.get("posterior_sampling_ok") is (True if strict_accepted else False)
            and finite_num("max_rhat")<=p["max_rhat"]
            and finite_num("min_bulk_ess")>=p["min_bulk_ess"]
            and d.get("divergences")==0
            and finite_num("minimum_bfmi")>=p["min_bfmi"])


def verify_manifest(manifest, asset, config):
    d=manifest.get("diagnostics") or {}
    keys=("max_rhat","min_bulk_ess","minimum_bfmi","divergences")
    if (manifest.get("schema")!="multisport_joint_fit_manifest_v1"
        or manifest.get("model_version")!="multisport-joint-bayes-v1"
        or manifest.get("sport")!="NFL" or manifest.get("stat")!=asset["stat"]
        or manifest.get("family")!="count"
        or manifest.get("max_per_position")!=0
        or manifest.get("diagnosed_all_player_and_opponent_effects") is not True
        or manifest.get("sampler_chains")!=4
        or manifest.get("sampler_retained_draws_per_chain")!=2000
        or manifest.get("sampler_tuning_iterations_per_chain")!=1800
        or manifest.get("training_cutoff_exclusive")!=config["training_cutoff_exclusive"]
        or not isinstance(manifest.get("source_digest"),str)
        or not manifest.get("players") or not manifest.get("opponents")
        or not provisional_diagnostics(d,config["policy"],
                     strict_accepted=asset.get("strict_accepted",False))
        or (asset.get("strict_accepted",False) and not (
            d["max_rhat"]<=1.01 and d["min_bulk_ess"]>=400 and
            d["divergences"]==0 and d["minimum_bfmi"]>=.30))
        or any(not math.isclose(d.get(k,float("nan")),asset[k],rel_tol=1e-9,abs_tol=1e-9)
               for k in keys)):
        raise ValueError("provisional_artifact_not_eligible")
    return True


def _download_asset(asset, folder, *, token):
    # The connected GitHub app may stage artifact ZIPs in Deepnote before the
    # pregame slate begins. This avoids requiring Actions permission on the
    # existing Deepnote Contents-only GitHub token. No signed URLs are saved.
    prestaged=os.environ.get("PICKEM_PROVISIONAL_PRESTAGED_DIR")
    if prestaged:
        existing=Path(prestaged)/(str(asset["artifact_id"])+".zip")
        if (not existing.is_file() or
                existing.stat().st_size!=asset["size_bytes"] or
                parent.checksum(existing)!=asset["sha256"]):
            raise ValueError("pre_staged_artifact_integrity_failure")
        return existing
    if not token:raise ValueError("GITHUB_TOKEN_required")
    # Pin artifact ID, run identity, the GitHub ZIP sha256 and its declared size.
    req=parent.request("/actions/runs/"+str(asset["run_id"])+"/artifacts",token)
    with urllib.request.urlopen(req,timeout=90) as stream:
        listing=json.load(stream)
    found=[v for v in listing.get("artifacts",[]) if v.get("id")==asset["artifact_id"]]
    if len(found)!=1:raise ValueError("pinned_artifact_not_available")
    actual=found[0]
    if (actual.get("expired") or actual.get("digest")!="sha256:"+asset["sha256"]
            or actual.get("size_in_bytes")!=asset["size_bytes"]
            or not str(actual.get("name","")).startswith("precision-full-market-"+str(asset["run_id"]))):
        raise ValueError("artifact_identity_or_digest_mismatch")
    dest=Path(folder)/"receipt.zip"
    req=parent.request("/actions/artifacts/"+str(asset["artifact_id"])+"/zip",token,binary=True)
    with urllib.request.urlopen(req,timeout=480) as src,dest.open("xb") as dst:
        shutil.copyfileobj(src,dst,1024*1024)
    if (dest.stat().st_size!=asset["size_bytes"]
            or parent.checksum(dest)!=asset["sha256"]):
        raise ValueError("artifact_download_integrity_failure")
    return dest


def _extract_exact(archive, folder, asset, config):
    # Extract *only* the exact manifest and posterior in the same ZIP prefix.
    with zipfile.ZipFile(archive) as z:
        valid=[]
        for item in z.infolist():
            pos=PurePosixPath(item.filename)
            if (pos.is_absolute() or ".." in pos.parts
                    or item.is_dir() or pos.name!="manifest.json"
                    or item.file_size>3_000_000):continue
            candidate=json.loads(z.read(item))
            try:verify_manifest(candidate,asset,config)
            except (ValueError,KeyError,TypeError):continue
            posterior_name=str(pos.parent/"posterior.nc") if str(pos.parent)!="." else "posterior.nc"
            try:post_info=z.getinfo(posterior_name)
            except KeyError:continue
            if not 0<post_info.file_size<2_000_000_000:
                raise ValueError("invalid_provisional_posterior_size")
            valid.append((candidate,post_info))
        if len(valid)!=1:raise ValueError("pinned_artifact_missing_exact_model")
        manifest,info=valid[0]
        target=Path(folder)/"posterior.nc"
        with z.open(info) as inp,target.open("xb") as out:
            shutil.copyfileobj(inp,out,1024*1024)
        return manifest,target


def provisional_forecast(posterior, manifest, context, *, seed, draws=1500, cache=None):
    """Separate explicit researcher-only numerical adapter; never fakes approval.

    Reproduces count likelihood integration of frozen joint_population_bayes
    without calling its strict-approved forecast gate. The original NUTS
    diagnostics remain attached to every prediction.
    """
    import numpy as np
    from scipy.stats import nbinom
    from joint_population_bayes import posterior_cache
    if not 50<=draws<=10000:raise ValueError("invalid_shadow_mc_draw_budget")
    if manifest.get("family")!="count":raise ValueError("unsupported_provisional_family")
    player=str(context["player_id"])
    if player not in manifest["player_position"] or player not in manifest["players"]:
        raise ValueError("unseen_frozen_player")
    opponent=context["opponent"]
    if opponent not in manifest["opponents"]:raise ValueError("unseen_frozen_opponent")
    line=context["line"]
    if type(line) not in (int,float) or not math.isfinite(line) or line<0:
        raise ValueError("invalid_frozen_market_line")
    if type(context["home"]) is not bool:raise ValueError("unverified_home_state")
    pos=manifest["player_position"][player]
    pidx=manifest["players"].index(player)
    gid=manifest["positions"].index(pos)
    oid=manifest["opponents"].index(opponent)
    s=context["season"]
    is_new=s not in manifest["seasons"]
    if is_new and len(manifest["seasons"])<2:
        raise ValueError("unidentified_future_season")
    d=cache if cache is not None else posterior_cache(posterior)
    rng=np.random.default_rng(seed)
    picks=rng.integers(0,d["count"],size=draws)
    def sample(name):return d["arrays"][name][picks]
    player_effect=sample("player_effect")[:,pidx,:]
    if is_new:
        sw=rng.normal(0,sample("season_workload_sd"))
        sr=rng.normal(0,sample("season_rate_sd"))
    else:
        ix=manifest["seasons"].index(s)
        sw=sample("season_workload")[:,ix]
        sr=sample("season_rate")[:,ix]
    exposure=np.exp(rng.normal(sample("population_workload")[:,gid]+player_effect[:,0]+sw,
                               sample("workload_sigma")))
    log_rate=(sample("population_rate")[:,gid]+player_effect[:,1]+sr
              +sample("opponent_rate")[:,oid]
              +(1 if context["home"] else 0)*sample("home_effect"))
    mu=exposure*np.exp(log_rate)
    alpha=sample("count_dispersion")
    if not np.all(np.isfinite(mu)) or np.any(mu<=0):
        raise ValueError("nonfinite_provisional_predictive_volume")
    prob=alpha/(alpha+mu)
    qover=float(np.mean(nbinom.sf(math.floor(line),alpha,prob)))
    qpush=(float(np.mean(nbinom.pmf(math.floor(line),alpha,prob)))
           if float(line).is_integer() else 0.0)
    if not (math.isfinite(qover) and math.isfinite(qpush)
            and 0<=qover<=1 and 0<=qpush<=1 and qover+qpush<=1+1e-8):
        raise ValueError("nonfinite_provisional_probability")
    return {"q_over":qover,"q_push":qpush,"q_under":max(0.,1-qover-qpush),
            "conditional_on_appearance":True,"draws":draws}


def forecast_one(row,manifest,posterior,now,asset,*,cache=None):
    result={k:row.get(k) for k in parent.KEYS+("player","team","opponent","event_start")}
    result.update(version=VERSION,model_id="artifact:"+str(asset["artifact_id"]),
                  generated_at=now.isoformat(),status="unavailable",
                  provisional=True,shadow_only=True,ranking_allowed=False,
                  publication_eligible=False,validated=False,calibrated=False,
                  trained_through=manifest["last_game"],
                  training_source_digest=manifest["source_digest"],
                  sampler_diagnostics=manifest["diagnostics"],
                  original_strict_convergence_failed=not asset.get("strict_accepted",False),
                  original_strict_convergence_passed=bool(asset.get("strict_accepted",False)),
                  model_run_id=asset["run_id"])
    try:
        context=parent.candidate_context(row,manifest,now)
        contract={k:row.get(k) for k in parent.KEYS if k!="side"}
        seed=int.from_bytes(hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).digest()[:8],"big")
        q=provisional_forecast(posterior,manifest,context,seed=seed,cache=cache)
        completed=datetime.now(timezone.utc)
        if completed>=parent.instant(row["event_start"]):
            raise ValueError("model_inference_finished_after_kickoff")
        result.update(status="forecast",generated_at=completed.isoformat(),q_win=(
            q["q_over"] if row["side"]=="over" else q["q_under"]),q_push=q["q_push"],
            q_over=q["q_over"],q_under=q["q_under"],
            conditional_on_appearance=True)
    except (ValueError,KeyError,TypeError,OverflowError,IndexError) as exc:
        result["reason"]=str(exc)
    return result


def run(root,day,*,token,config_path=CONFIG,now=None):
    import live_pool_exchange as pool
    import arviz as az
    root=Path(root);now=now or datetime.now(timezone.utc)
    cfg=load_policy(config_path)
    frozen,run_id=pool.pick_latest(pool.jsonl(root/"data/prop_snapshots.jsonl"),day)
    if not frozen:raise ValueError("no_frozen_pregame_source_slate")
    if not token:raise ValueError("provisional_artifact_access_token_missing")
    output=root/"data/provisional_nuts_shadow"/(day+".jsonl")
    if output.exists():raise ValueError("provisional_predictions_already_frozen_for_date")
    output.parent.mkdir(parents=True,exist_ok=True)
    receipts=[];predictions=[];errors=Counter()
    # Evaluate the newest completed model first. In early-Sunday pregame
    # inference, additional models (especially tackles + assists) should
    # never wait behind the older four large research posteriors.
    for asset in sorted(cfg["models"],key=lambda item:item["index"],reverse=True):
        candidates=[r for r in frozen if r.get("sport")=="NFL"
                    and parent.canon_stat(r.get("stat"))==asset["stat"]]
        if not candidates:continue
        with tempfile.TemporaryDirectory(prefix="provisional_nuts_asset_") as temp:
            archive=_download_asset(asset,temp,token=token)
            manifest,pfile=_extract_exact(archive,temp,asset,cfg)
            # Downloads from a trusted temporary project cache are erased
            # after this model finishes, never retained in Git or reports.
            staged_archive=(Path(os.environ["PICKEM_PROVISIONAL_PRESTAGED_DIR"])/(str(asset["artifact_id"])+".zip")
                             if os.environ.get("PICKEM_PROVISIONAL_PRESTAGED_DIR") else None)
            del archive
            # Discard the 50–320MB ZIP before loading the full posterior.
            (Path(temp)/"receipt.zip").unlink(missing_ok=True)
            posterior=az.from_netcdf(pfile)
            if (posterior.posterior.sizes.get("chain")!=4 or
                    posterior.posterior.sizes.get("draw")!=2000):
                raise ValueError("provisional_posterior_chain_count_mismatch")
            from joint_population_bayes import posterior_cache
            cache=posterior_cache(posterior)
            for row in candidates:
                pred=forecast_one(row,manifest,posterior,now,asset,cache=cache)
                predictions.append(pred)
                if pred["status"]!="forecast":errors[pred.get("reason","unknown")]+=1
            del cache,posterior
            import gc
            gc.collect()
            if staged_archive is not None:
                staged_archive.unlink(missing_ok=True)
            receipts.append({"stat":asset["stat"],"artifact_id":asset["artifact_id"],
                            "run_id":asset["run_id"],"artifact_sha256":asset["sha256"],
                            "diagnostics":manifest["diagnostics"],
                            "candidates":len(candidates),
                            "forecasts":sum(r["status"]=="forecast" for r in predictions
                                            if r.get("stat")==asset["stat"])})
    # Save prospectively; never silently mutate an existing day's comparison.
    pool.dump_jsonl(output,predictions)
    receipt={"schema":VERSION,"game_date":day,"run_id":run_id,
             "generated_at":datetime.now(timezone.utc).isoformat(),
             "assets":receipts,"candidates":len(predictions),
             "forecasts":sum(r["status"]=="forecast" for r in predictions),
             "unavailable":dict(errors),"production_consensus_changed":False,
             "ranking_allowed":False,"full_convergence_certified":False,
             "model_health_policy":"provisional_rhat_le_1.02_ess_ge_300_zero_div_bfmi_ge_0.30",
             "posterior_checks_not_overridden":True,
             "new_training_started":False}
    p=root/"reports/provisional_nuts_shadow_receipt.json"
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--date",required=True)
    parser.add_argument("--policy",type=Path,default=None)
    args=parser.parse_args()
    result=run(args.root,args.date,token=os.getenv("GITHUB_TOKEN"),config_path=args.policy)
    print("PROVISIONAL_NUTS_SHADOW "+json.dumps(result,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
