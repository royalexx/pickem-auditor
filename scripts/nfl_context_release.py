"""Export and load the pinned NFL targets posterior for inference, without PyMC."""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import nhl_context_data as common
import nhl_context_train as io
import nfl_context_model as model

ROOT=Path(__file__).resolve().parents[1]
PIN_PATH=ROOT/"config/nfl_targets_release.json"
DESIGN_KEYS=("source_digest","cutoff","market","feature_names","players","teams","positions",
             "seasons","player_position","center","scale","read_features")


def array_hash(value):
    import numpy as np
    a=np.ascontiguousarray(value,dtype="<f8")
    return hashlib.sha256(common.encode(list(a.shape)).encode()+b"\n"+a.tobytes()).hexdigest()


def history_seed(bundles,cutoff):
    boundary=common.instant(cutoff);teams=defaultdict(list);players=defaultdict(list)
    for b in bundles:
        for r in b["teams"]:
            if common.instant(r["available_at"])<boundary:teams[r["team"]].append(r)
        for r in b["players"]:
            if r["stat"]=="targets" and common.instant(r["available_at"])<boundary:players[r["player_id"]].append(r)
    team_fields=("game_id","team","opponent","start_time","available_at","plays","targets","passes","rushes")
    player_fields=("game_id","player_id","team","opponent","position","stat","workload","start_time","available_at")
    def tail(groups,fields):
        return [{k:r[k] for k in fields} for key in sorted(groups)
                for r in sorted(groups[key],key=lambda r:r["start_time"])[-8:]]
    # Include both sides of every retained team game: allowed-opportunity rates
    # look up its opponent's row, which may lie outside that opponent's tail.
    selected={(r["game_id"],r["team"]):r for r in tail(teams,team_fields)}
    lookup={(r["game_id"],r["team"]):r for group in teams.values() for r in group}
    for r in list(selected.values()):
        other=lookup[(r["game_id"],r["opponent"])]
        selected[(other["game_id"],other["team"]) ]={k:other[k] for k in team_fields}
    return {"teams":[selected[k] for k in sorted(selected)],"players":tail(players,player_fields)}


def export(run_dir,out_dir,*,pins=None,bootstrap=False):
    import arviz as az
    import numpy as np
    pins=pins or io.load_json(PIN_PATH);run=Path(run_dir);out=Path(out_dir)
    folder=run/"context";manifest=io.load_json(folder/"manifest.json")
    for name,expected in (("posterior.nc",pins["posterior_sha256"]),("design.json",pins["source_design_sha256"])):
        if io.file_hash(folder/name)!=expected:raise ValueError("unverified_nfl_release_source:"+name)
    frozen=io.load_json(run/"frozen/frozen_hashes.json")
    if io.file_hash(run/"frozen/frozen_hashes.json")!=manifest["frozen_hashes_sha256"]:
        raise ValueError("changed_nfl_frozen_manifest")
    if io.file_hash(run/"frozen/frozen_bundles.json")!=frozen["frozen_bundles.json"]:
        raise ValueError("changed_nfl_frozen_bundles")
    d=io.load_json(folder/"design.json");trace=az.from_netcdf(folder/"posterior.nc")
    diagnostic=model.diagnostics(trace)
    if not diagnostic.get("posterior_sampling_ok"):raise ValueError("nfl_release_requires_convergence")
    cache=model.cache(trace,d)
    meta={"schema":"nfl-targets-inference-release-v1","tag":pins["tag"],"model_version":model.VERSION,
          "source_posterior_sha256":pins["posterior_sha256"],"n":cache["n"],"diagnostics":diagnostic,
          "design":{k:d[k] for k in DESIGN_KEYS},
          "history_seed":history_seed(io.load_json(run/"frozen/frozen_bundles.json"),d["cutoff"]),
          "array_hashes":{k:array_hash(v) for k,v in cache["arrays"].items()},
          "ranking_allowed":False,"automatic_promotion":False}
    if not bootstrap:validate_meta(meta,pins)
    out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/"parameters.npz",**cache["arrays"])
    io.write_json(out/"model.json",meta)
    return meta


def validate_meta(meta,pins):
    if (meta.get("schema")!="nfl-targets-inference-release-v1" or meta.get("tag")!=pins["tag"] or
        meta.get("model_version")!=model.VERSION or meta.get("source_posterior_sha256")!=pins["posterior_sha256"] or
        meta.get("n")!=6000 or meta.get("array_hashes")!=pins["array_hashes"] or
        common.digest(meta.get("design"))!=pins["design_digest"] or
        common.digest(meta.get("history_seed"))!=pins["history_seed_digest"]):
        raise ValueError("unverified_nfl_release_metadata")


def load(folder,*,download=False,pins=None):
    import numpy as np
    pins=pins or io.load_json(PIN_PATH);folder=Path(folder)
    if download and not all((folder/n).is_file() for n in ("model.json","parameters.npz")):
        folder.mkdir(parents=True,exist_ok=True)
        subprocess.run(["gh","release","download",pins["tag"],"--repo",pins["repository"],
            "--dir",str(folder),"--pattern","model.json","--pattern","parameters.npz","--clobber"],check=True)
    meta=io.load_json(folder/"model.json");validate_meta(meta,pins)
    with np.load(folder/"parameters.npz",allow_pickle=False) as archive:
        if set(archive.files)!=set(pins["array_hashes"]):raise ValueError("invalid_nfl_parameter_names")
        arrays={k:archive[k] for k in archive.files}
    for k,v in arrays.items():
        if v.shape[0]!=6000 or not np.isfinite(v).all() or array_hash(v)!=pins["array_hashes"][k]:
            raise ValueError("unverified_nfl_parameter_values:"+k)
    return meta,{"n":6000,"arrays":arrays,"source_digest":meta["design"]["source_digest"]}


def publish(folder,*,pins=None):
    pins=pins or io.load_json(PIN_PATH);folder=Path(folder)
    load(folder,pins=pins)
    args=["gh","release","view",pins["tag"],"--repo",pins["repository"]]
    if subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
        with tempfile.TemporaryDirectory(prefix="nfl-release-check-") as temp:
            load(temp,download=True,pins=pins)
        return "existing_verified_release"
    subprocess.run(["gh","release","create",pins["tag"],str(folder/"model.json"),str(folder/"parameters.npz"),
        "--repo",pins["repository"],"--target",os.environ.get("GITHUB_SHA","main"),"--prerelease",
        "--title","Verified NFL targets context posterior",
        "--notes","Verified 6000-draw research posterior. Pinned inference values; no automatic ranking promotion. FTN Data via nflverse, CC BY-SA 4.0."],check=True)
    return "published"


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir",type=Path,default=ROOT/"reports/nfl_reads_full_v2")
    p.add_argument("--out-dir",type=Path,default=ROOT/"reports/nfl_targets_release")
    p.add_argument("--publish",action="store_true",help="Publish pinned inference assets using authenticated gh")
    a=p.parse_args();m=export(a.run_dir,a.out_dir)
    status=publish(a.out_dir) if a.publish else "exported"
    print(json.dumps({"status":status,"folder":str(a.out_dir),"posterior_sha256":m["source_posterior_sha256"]}))
