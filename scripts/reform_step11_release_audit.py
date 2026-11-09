"""Step 11 independent-code-path release invariant and evidence gate auditor.

No dispatch/retrain/network/write. Mechanical validation of source policy,
all manual Bayesian trainer pause gates, plus optional immutable original
settlement evidence. This is an adversarial *code-path* review, not a
separate third-party statistical certification.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from reform_phase4_scorecard import load_nfl_slate, read_json
from reform_step8_market_shadow import proper_pair
from reform_step9_game_leg_dependence import frechet_entry_bounds
from reform_step10_calibration_shadow import beta_map, research

VERSION="pickem-reform-step11-release-audit-v1"
TRAINING_WORKFLOWS=(
    "precision-full-markets.yml",
    "historical-bayes-training.yml",
    "multisport-joint-evaluation.yml",
    "nhl-joint-bayes-fit.yml",
    "precision-local-bayes.yml",
    "precision-nhl-full.yml",
    "precision-nhl-sampler-benchmark.yml",
    "precision-nhl-sampler-windows.yml",
    "benchmark-bayes-backends.yml",
    "full-backend-coverage.yml",
    "convergence-rebenchmark.yml",
    "recover-full-backend-coverage.yml",
)
MODEL_RELEASE_WORKFLOWS=("nfl-targets-model-release.yml",)
REQUIRED_CODE=(
    "scripts/point_in_time_provenance.py",
    "scripts/fit_blend.py",
    "scripts/slate_model_report.py",
    "scripts/nuts_slate_shadow.py",
    "scripts/reform_phase4_scorecard.py",
    "scripts/reform_phase5_selection_audit.py",
    "scripts/nfl_tackle_snap_share.py",
    "scripts/reform_step7_uncertainty_shadow.py",
    "scripts/reform_step8_market_shadow.py",
    "scripts/reform_step9_game_leg_dependence.py",
    "scripts/reform_step10_calibration_shadow.py",
    "scripts/population_nfl.py",
)
REQUIRED_TESTS=(
    "tests/test_reform_phase4_scorecard.py",
    "tests/test_reform_phase5_selection_audit.py",
    "tests/test_nfl_tackle_snap_share.py",
    "tests/test_reform_step7_uncertainty_shadow.py",
    "tests/test_reform_step8_market_shadow.py",
    "tests/test_reform_step9_game_leg_dependence.py",
    "tests/test_reform_step10_calibration_shadow.py",
)
FUTURE_GATES={
    "4a_genuine_pregame_integrated_pairing":"pending_next_genuine_pregame_inference_run",
    "5_topk_selected_vs_eligible_out_of_sample":"needs_more_full_slate_graded_candidates",
    "6_tackles_position_usage_and_real_line_validation":"needs_real_original_quoted_lines_and_linebacker_holdout",
    "7_calibrated_uncertainty_ranking_promotion":"needs_nonproxy_uncertainty_and_multiple_settled_dates",
    "8_M2_M3_market_blend_promotion":"needs_authenticated_300_100_matched_20_20_chronological_data",
    "9_multi_leg_joint_probability":"needs_many_game_dates_and_out_of_sample_joint_result_validation",
    "10_Beta_global_stack_calibration_promotion":"needs_pregame_verified_matched_multi_date_holdout",
    "11_external_statistical_reviewer_and_production_signoff":"not_automatically_authorized_by_code",
}


class ReleaseAuditError(ValueError):
    pass


def source(root,path):
    p=Path(root)/path
    if not p.is_file():
        raise ReleaseAuditError("missing_required_file:"+path)
    data=p.read_bytes()
    return data.decode("utf-8"),hashlib.sha256(data).hexdigest()


def check_training_workflow(path,raw):
    """Every checkout in an identified fitting job must hit pause before work.

    The current workflow's checkout is expected to include the marker. This
    does NOT retroactively rewrite stale branches or disable old workflow
    definitions that have already been dispatched.
    """
    lines=raw.splitlines()
    checkout=[i for i,v in enumerate(lines) if "uses: actions/checkout@v4" in v]
    if not checkout:
        raise ReleaseAuditError("workflow_has_no_checkout:"+path)
    for i in checkout:
        until=min(len(lines),i+28)
        following="\n".join(lines[i:until])
        if (".training-control/PAUSED.json" not in following or
                "TRAINING_PAUSED_FOR_MODEL_REFORM" not in following or
                "throw " not in following and "exit 1" not in following):
            raise ReleaseAuditError("missing_early_training_pause_guard:"+path+
                                    ":checkout_line_"+str(i+1))
    if "schedule:" in raw and "cron:" in raw:
        raise ReleaseAuditError("scheduled_training_workflow_"+path)
    return {"checkouts":len(checkout),"all_pause_guarded":True,
            "training_not_dispatched":True}


def inspect_release(root, *, frozen=None,settlement=None,pinned=None):
    root=Path(root)
    digests={}
    for path in REQUIRED_CODE+REQUIRED_TESTS:
        _,digests[path]=source(root,path)
    policy_text,policy_sha=source(root,"config/production_consensus.json")
    control_text,pause_sha=source(root,".training-control/PAUSED.json")
    policy=json.loads(policy_text)
    paused=json.loads(control_text)
    expected={
        "schema":"pickem_production_consensus_policy_v1",
        "model":"historical_consensus_engine_b",
        "weight_a":.6,
        "weight_b":.4,
        "requires_reliable_components":True,
        "missing_component_action":"abstain",
        "empirically_calibrated":False,
        "historical_min_coverage":2,
        "historical_required":["Engine_A"],
        "provisional_nuts_allowed":False,
        "post_shadow_finalization":True,
        "preliminary_snapshot_is_production":False,
    }
    for name,value in expected.items():
        if policy.get(name)!=value:
            raise ReleaseAuditError("production_policy_changed_or_weakened:"+name)
    if "Market" in policy.get("historical_models",[]) or set(
            policy.get("historical_models",[])) != {"Engine_A","Bayesian_A","Bayesian_B","NUTS"}:
        raise ReleaseAuditError("market_or_unapproved_historical_model_promoted")
    pause_expected={
        "schema":"pickem_training_pause_v1","paused":True,
        "resume_requires_explicit_user_approval":True,
        "preserve_existing_posteriors_and_checkpoints":True,
    }
    for key,value in pause_expected.items():
        if paused.get(key)!=value:
            raise ReleaseAuditError("user_training_pause_not_enforced:"+key)
    workflow={}
    for file in TRAINING_WORKFLOWS+MODEL_RELEASE_WORKFLOWS:
        path=".github/workflows/"+file
        raw,sha=source(root,path)
        digests[path]=sha
        workflow[file]=check_training_workflow(file,raw)
    # Verify the original distinct statistic remains combined credited T+A.
    nfl,_=source(root,"scripts/population_nfl.py")
    if not all(('row.get("'+name+'")') in nfl for name in (
            "def_tackles_solo","def_tackles_with_assist","def_tackle_assists")):
        raise ReleaseAuditError("combined_tackles_components_missing")
    if 'if stat=="tackles + assists":' not in nfl or "v=sum(components)" not in nfl:
        raise ReleaseAuditError("combined_tackle_market_no_longer_sums_three_components")
    step6,_=source(root,"scripts/nfl_tackle_snap_share.py")
    if 'STATS="tackles + assists"' not in step6 or 'p.get("stat")!=STATS' not in step6:
        raise ReleaseAuditError("step6_no_longer_consumes_combined_tackles")
    nuts,_=source(root,"scripts/nuts_slate_shadow.py")
    report,_=source(root,"scripts/slate_model_report.py")
    if ("def shared_contract_seed(" not in nuts or
            "enforce_paired_probability_integrity" not in report):
        raise ReleaseAuditError("step4a_numerical_guard_missing")
    src7,_=source(root,"scripts/reform_step7_uncertainty_shadow.py")
    src8,_=source(root,"scripts/reform_step8_market_shadow.py")
    src9,_=source(root,"scripts/reform_step9_game_leg_dependence.py")
    src10,_=source(root,"scripts/reform_step10_calibration_shadow.py")
    for name,raw in (("step7",src7),("step8",src8),("step9",src9),("step10",src10)):
        if "production_modified" not in raw and name!="step9":
            raise ReleaseAuditError("shadow_component_missing_production_veto:"+name)
        if "config/production_consensus.json" in raw or "--emit-config" in raw:
            raise ReleaseAuditError("shadow_module_has_production_writer:"+name)
    if "payout_ev_approved" not in src9 or "production_promotion_authorized" not in src10:
        raise ReleaseAuditError("step9_or_10_promotion_flag_missing")
    if not all(abs(beta_map(p,{"a":1.,"b":1.,"c":0.})-p)<1e-12
               for p in (.1,.3,.5,.7,.9)):
        raise ReleaseAuditError("beta_calibration_identity_broken")
    joint=frechet_entry_bounds([.7,.6])
    if (abs(joint["frechet_lower_bound"]-.3)>1e-12 or
            abs(joint["frechet_upper_bound"]-.6)>1e-12 or
            joint["joint_probability_approved"] or joint["payout_ev_approved"]):
        raise ReleaseAuditError("marginal_only_joint_probability_safety_failed")
    inputs=(frozen,settlement,pinned)
    evidence={"status":"no_original_source_paths_supplied",
              "point_in_time_provider_source_complete":False}
    if any(x is not None for x in inputs):
        if any(x is None for x in inputs):
            raise ReleaseAuditError("partial_original_source_path_set")
        from reform_phase4_scorecard import load_nfl_slate
        original,receipt=load_nfl_slate(frozen,settlement,pinned)
        coherent=sum(proper_pair(r["models"].get("Market")) and
                     proper_pair(r["models"].get("Consensus"))
                     for r in original)
        dates=len({r["date"] for r in original})
        evidence={
            "status":"original_pinned_official_scoring_verified",
            "official_settled_contracts":len(original),
            "coherent_market_consensus_contracts":coherent,
            "independent_dates":dates,
            "point_in_time_provider_source_complete":
                receipt.get("source_completeness_verified") is True,
            "frozen_original_comparison_sha256":read_json(frozen)[1],
            "original_settlement_sha256":read_json(settlement)[1],
        }
        if evidence["point_in_time_provider_source_complete"]:
            # A complete historical archive would still need independent
            # chronological evidence before promotion; no automatic unlock.
            evidence["verified_pregame_provenance_is_not_model_promotion"]=True
    return {
        "schema":VERSION,
        "source_policy_sha256":policy_sha,
        "source_training_pause_sha256":pause_sha,
        "audited_code_and_test_sha256":digests,
        "pause_guarded_training_workflows":workflow,
        "pause_guarded_workflow_count":len(workflow),
        "training_workflow_count":len(TRAINING_WORKFLOWS),
        "model_release_workflow_count":len(MODEL_RELEASE_WORKFLOWS),
        "policy_verified_unchanged_60_40":True,
        "full_source_stat_combined_nfl_tackles_verified":True,
        "step4a_paired_probability_guard_exists":True,
        "beta_identity_and_fréchet_math_smoke_passed":True,
        "original_pinned_outcome_receipt":evidence,
        "all_technical_release_invariants_passed":True,
        "technical_audit_status":"passed_with_evidence_dependent_validation_pending",
        "independent_third_party_statistical_audit_performed":False,
        "original_data_altered":False,
        "retraining_started":False,
        "production_modified":False,
        "production_promotion_authorized":False,
        "future_evidence_gates":FUTURE_GATES,
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--frozen",type=Path)
    p.add_argument("--settlement",type=Path)
    p.add_argument("--pinned",type=Path)
    p.add_argument("--out",type=Path)
    args=p.parse_args(argv)
    result=inspect_release(args.root,frozen=args.frozen,
                           settlement=args.settlement,pinned=args.pinned)
    data=json.dumps(result,sort_keys=True,indent=2,ensure_ascii=True)+"\n"
    if args.out:
        if args.out.exists() and args.out.read_text()!=data:
            raise ReleaseAuditError("would_overwrite_different_release_audit_receipt")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(data)
    print(json.dumps({
        "status":result["technical_audit_status"],
        "guarded_workflows":result["pause_guarded_workflow_count"],
        "evidence":result["original_pinned_outcome_receipt"],
        "production_modified":result["production_modified"],
        "promotion_authorized":result["production_promotion_authorized"],
        "future_gates":result["future_evidence_gates"],
    },sort_keys=True))


if __name__=="__main__":
    main()
