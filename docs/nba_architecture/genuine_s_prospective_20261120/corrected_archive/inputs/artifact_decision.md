{
  "activated_fit_code_raw_sha256": "11c4bede78a803f8f00f779a5497eb22e3c2a53cf811fe7e47553fa7ec45e490",
  "admitted_at": "2026-11-20T01:39:59.762830+00:00",
  "artifacts": {
    "assists": {
      "byte_identical_native_reconstruction": true,
      "bytes": 219760,
      "observed_role_counts": {
        "ESPN_POSITION_BIN_AT_CAPTURE:C": 66,
        "ESPN_POSITION_BIN_AT_CAPTURE:F": 210,
        "ESPN_POSITION_BIN_AT_CAPTURE:G": 180
      },
      "sha256": "f8cea715972a36be0d3dd32c255084587397f2d4a8954864b873928c8225afb7",
      "training_rows": 456
    },
    "points": {
      "byte_identical_native_reconstruction": true,
      "bytes": 219513,
      "observed_role_counts": {
        "ESPN_POSITION_BIN_AT_CAPTURE:C": 66,
        "ESPN_POSITION_BIN_AT_CAPTURE:F": 210,
        "ESPN_POSITION_BIN_AT_CAPTURE:G": 180
      },
      "sha256": "a8b2e1e4cad5f2c46dfc902913d9186e99d1b997190fdaef8691c997acef2da2",
      "training_rows": 456
    },
    "rebounds": {
      "byte_identical_native_reconstruction": true,
      "bytes": 220239,
      "observed_role_counts": {
        "ESPN_POSITION_BIN_AT_CAPTURE:C": 66,
        "ESPN_POSITION_BIN_AT_CAPTURE:F": 210,
        "ESPN_POSITION_BIN_AT_CAPTURE:G": 180
      },
      "sha256": "b0f5f9fc0dbc3a330cd17b257e1278759f0a57c78ddd6ece2ee64f2c1e7bea6e",
      "training_rows": 456
    },
    "threes": {
      "byte_identical_native_reconstruction": true,
      "bytes": 219298,
      "observed_role_counts": {
        "ESPN_POSITION_BIN_AT_CAPTURE:C": 66,
        "ESPN_POSITION_BIN_AT_CAPTURE:F": 210,
        "ESPN_POSITION_BIN_AT_CAPTURE:G": 180
      },
      "sha256": "ebbfe7836f2f160550bc5cd5b7ae1731aaa3c305149254a8fb6ca174b49331dc",
      "training_rows": 456
    }
  },
  "authority": "PA-V25-MASTER-2026-11-09/v1.1 + November19 source_listed_subset + explicit user request to add missing genuine S forecasts",
  "conditioning": "conditional_on_participation_and_fixed_projected_ordinary_M0_exposure",
  "data_cutoff_at": "2026-11-20T01:07:00.131517+00:00",
  "decision": "ADMIT_EXACT_FROZEN_PROSPECTIVE_S1_ARTIFACTS_FOR_BOUNDED_RESEARCH",
  "excluded_training_attempts": 968,
  "exposure_semantics": "EXACT_SOURCE_REPORTED_SECONDS_GE_30",
  "family": "S1",
  "fit_receipt_raw_sha256": "20e924334578cf9cd60c5c8b7f9e8a2b9dafc3153a13fe671f4db54f14c3fb4e",
  "fixed_hyperparameters": {
    "dispersion": 12.0,
    "min_player_games": 2,
    "prior_attempts": 40.0,
    "prior_minutes": 180.0
  },
  "full_G1_accepted": false,
  "genuine_forecasts_issued_during_this_review": 0,
  "historical_artifacts_preserved": true,
  "included_training_attempts": 1824,
  "joint_law_accepted": false,
  "legal_eligible_population_count": null,
  "minute_uncertainty_integrated": false,
  "model_admission_granted": true,
  "native_code_raw_sha256": "a63a469d8df74f6e6f82c7480ee289da443452dd62f603859629a5d821d28cd6",
  "native_fit_verification_replays": 4,
  "participation_probability": null,
  "predictive_accuracy_validated": false,
  "prefit_approval_raw_sha256": "a76ce1e31d029edecc30b57d9ee7dd37941cb31fc697c5c01b0566c18b9fe558",
  "prefit_spec_raw_sha256": "9b4ffaf085deeffe83cee50c6d3ecfc5dd2c41848cb849ee32240389cc7b2ed8",
  "production_release": false,
  "raw_sources_raw_sha256": "4c7124414905ef92d68d008023c7d1073437ae94dfc5400d8794ceca8de5ceb0",
  "remaining_runtime_gate": "Use repaired intervening-game accounting and externally trusted archive verification. Any original/resealed-reader/count/clock/source/model failures must remain rejected. Preserve actual forecast/archive bytes for final independent review.",
  "reviewer": "independent_p2_dispatch_review; no implementation repairs authored",
  "role_semantics": "ESPN_POSITION_BIN_OBSERVED_AT_CAPTURE",
  "schema": "nba-independent-real-S1-artifact-admission/1.0.0",
  "scope_limit": "Source/model admission only for these four exact artifacts. New forecast freeze must be actual and after admitted_at; same35frozen source candidates and target only. Final actual public-path independent engineering review remains required.",
  "scoring_admitted": false,
  "seed": 20261120,
  "source_dataset_payload_sha256": "e5cb76ef446d6651b718c6279367a7078ffa86f01b621cfbfd9c7b4d74adbd1d",
  "source_dataset_raw_sha256": "a8230745eae80c0831ce36dc71d7fb41d9faeaef9e053f9844b8f70fb0e334a2",
  "source_manifest_raw_sha256": "5269b9d38d383b965b2c88587ac7a69eee5c75dcc52e941a703076b76dc1b82b",
  "source_population_scope": "Exact60capturedsources/20completedgames/698sourceobservations in the frozen prospective profile only",
  "source_reader_raw_sha256": "8b61c753a41b59b9baad25ce179bd56ef3ceaf31645e76998b6408f296a447fd",
  "target": {
    "game_id": "401910026",
    "name": "Memphis Grizzlies at Minnesota Timberwolves",
    "start": "2026-11-22T01:00Z",
    "teams": {
      "16": "MIN",
      "29": "MEM"
    }
  },
  "timing_rule_raw_sha256": "ead50b6b76dc319a6c0a390d3dd3add2d25b2330b8314bc7a3e2e4c17add5eed",
  "training_attempt_denominator": 2792,
  "training_rows_per_statistic": 456,
  "unconditional_statistic_law_accepted": false
}
