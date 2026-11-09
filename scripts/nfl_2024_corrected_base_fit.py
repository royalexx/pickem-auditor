#!/usr/bin/env python3
"""Rebuild the pre-2024 XGBoost/hurdle baseline after fixing game-local roles.

The old immutable 2024 replay manifest remains untouched; its fitted models
used a future-game player-position lookup when constructing historical PBP.
No legacy trained weights may be reused under the corrected feature schema.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

import nfl_pre2024_xgb_replay as common
import nfl_pre2024_team_defense_challenger as priors
import nfl_pre2024_team_volume_xgb as volume
import nfl_pre2024_active_zero_hurdle as zero
import nflverse_pre2024_hurdle_gateway as gateway

SCHEMA="nfl_2024_role_scoped_pre2024_training_base_v1"
ROLE_MAPPING="same_completed_game_player_position_v2"
CUTOFF="2024-01-01"


def build(root,*,trials=8):
    root=Path(root)
    if root.exists():raise RuntimeError("corrected_base_output_already_exists")
    if not 1<=int(trials)<=50:raise ValueError("invalid_optuna_trial_budget")
    root.mkdir(parents=True,exist_ok=False)
    rows,pbp,ngs,receipt=common.pre2024_sources()
    if not rows or not pbp:
        raise RuntimeError("missing_pre2024_history")
    if any(str(r["game_date"])>=CUTOFF for r in rows):
        raise RuntimeError("2024_player_train_data_used")
    if any(str(r["gameday"])>=CUTOFF for r in pbp):
        raise RuntimeError("2024_pbp_train_data_used")
    if any(str(r["gameday"])>=CUTOFF for group in ngs.values() for r in group):
        raise RuntimeError("2024_ngs_train_data_used")
    if receipt["cutoff"]!=CUTOFF or receipt["ftn_records_admitted"]!=0:
        raise RuntimeError("source_provenance_not_pre2024")
    state=priors.historical_sources(rows,pbp,ngs)
    context=gateway.load_nflreadpy_strict_pre2024_context(
                      include_participation=True,include_injuries=True)
    if context["cutoff_exclusive"]!=CUTOFF:
        raise RuntimeError("hurdle_context_2024_leak")
    print("CORRECTED_BASE_PRE2024_SOURCE",json.dumps({
      "players":len(rows),"team_games":len(pbp),
      "game_position_mapping":ROLE_MAPPING,"trials":trials}),flush=True)
    model,zero_rec=zero.train(state,context,rows,trials=trials)
    if model is None or model[1] is None:
        raise RuntimeError("corrected_hurdle_not_fitted_or_calibrated")
    root_models=root/"MODELS"
    root_models.mkdir()
    zero_model,cal=model
    zero_model.save_model(str(root_models/"active_zero_hurdle.ubj"))
    common.atomic_new(root_models/"active_zero_platt_calibration.json",{
      "coef":cal.coef_.tolist(),"intercept":cal.intercept_.tolist(),
      "classes":cal.classes_.tolist(),"fit_cutoff_exclusive":CUTOFF,
      "method":"pre2024_oof_platt_logit",
      "pre2024_game_position_mapping":ROLE_MAPPING})
    idx=volume.build_index(pbp,ngs)
    fitted,fit_receipts=volume.train(pbp,idx,trials=trials)
    for market,mdl in fitted.items():
        mdl.save_model(str(root_models/(market+".ubj")))
    files=("pass_attempts.ubj","rush_attempts.ubj","active_zero_hurdle.ubj",
           "active_zero_platt_calibration.json")
    artifacts={path.rsplit(".",1)[0]:common.sha(root_models/path) for path in files}
    manifest={
      "schema":SCHEMA,
      "stage":"new_pre2024_fit_complete",
      "training_cutoff_exclusive":CUTOFF,
      "fit_and_hyperparameter_selection_use_only_pre2024":True,
      "game_position_mapping_provenance":ROLE_MAPPING,
      "legacy_pre2024_models_reused":False,
      "source_receipt":receipt,
      "team_xgboost_fit_receipts":fit_receipts,
      "hurdle_fit_receipt":zero_rec,
      "model_file_hashes":artifacts,
      "training_player_rows":len(rows),
      "training_team_rows":len(pbp),
      "2024_stat_labels_used":0,
      "production_eligible":False,
      "requires_weekly_or_future_holdout_validation":True,
    }
    common.atomic_new(root/"FROZEN_MANIFEST.json",manifest)
    print("CORRECTED_BASE_FIT_COMPLETE",json.dumps({
      "model_hashes":artifacts,"source":ROLE_MAPPING,
      "manifest_sha":common.sha(root/"FROZEN_MANIFEST.json"),
      "zero_training_n":zero_rec["sample_n"],
      "team_training_n":{k:x["train_rows"] for k,x in fit_receipts.items()}
    },sort_keys=True),flush=True)
    return manifest


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--trials",type=int,default=8)
    a=p.parse_args()
    build(Path(a.root),trials=a.trials)
