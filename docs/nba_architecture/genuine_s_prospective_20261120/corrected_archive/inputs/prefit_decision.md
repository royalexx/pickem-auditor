{
  "activation_constraint": "Only these three previously None constants may change in the reviewed writer. Reader, native code, fixed parameters, seed, native/time guards and writer body remain exactly reviewed.",
  "actual_native_fit_executions_during_review": 0,
  "allowed_activation_changes": {
    "APPROVED_DATASET_SHA": "e5cb76ef446d6651b718c6279367a7078ffa86f01b621cfbfd9c7b4d74adbd1d",
    "APPROVED_READER_SHA": "8b61c753a41b59b9baad25ce179bd56ef3ceaf31645e76998b6408f296a447fd",
    "PREFIT_APPROVAL_SHA": "Set to SHA256 of the exact raw bytes of this immutable approval file."
  },
  "artifact_admission_granted": false,
  "authority": "PA-V25-MASTER-2026-11-09/v1.1 + November19 source_listed_subset + explicit user request to add missing genuine S forecasts",
  "clock_constraint": "max(source ingested) <= frozen data cutoff <= actual fit started <= actual fit completed <= actual artifact bytes verified <= later independently admitted forecast input freeze <= forecast < future event start",
  "closed_writer_protocol_raw_sha256": "f81d42820e4c364400803e4e13d52ba84e80d11a51fb396ab6e3a05077c4533a",
  "data_cutoff_at": "2026-11-20T01:07:00.131517+00:00",
  "dataset_payload_sha256": "e5cb76ef446d6651b718c6279367a7078ffa86f01b621cfbfd9c7b4d74adbd1d",
  "dataset_raw_sha256": "a8230745eae80c0831ce36dc71d7fb41d9faeaef9e053f9844b8f70fb0e334a2",
  "decided_at": "2026-11-20T01:31:01.785215+00:00",
  "decision": "PREFIT_PASS_BOUNDED_PROSPECTIVE_S1_BATCH",
  "excluded_training_attempts": 968,
  "exposure_semantics": "EXACT_SOURCE_REPORTED_SECONDS_GE_30",
  "family": "S1",
  "fit_scope": "One new create-only prospective native S1 batch over the exact frozen four histories. No replacement fits, tuning, scoring, holdout access, weights, samplers, source substitution or schedule changes.",
  "fixed_hyperparameters": {
    "dispersion": 12.0,
    "min_player_games": 2,
    "prior_attempts": 40.0,
    "prior_minutes": 180.0
  },
  "forecast_admission_granted": false,
  "included_training_attempts": 1824,
  "joint_law_acceptance": false,
  "native_S_code_raw_sha256": "a63a469d8df74f6e6f82c7480ee289da443452dd62f603859629a5d821d28cd6",
  "predictive_acceptance": false,
  "prefit_spec_raw_sha256": "9b4ffaf085deeffe83cee50c6d3ecfc5dd2c41848cb849ee32240389cc7b2ed8",
  "production_release": false,
  "raw_sources_raw_sha256": "4c7124414905ef92d68d008023c7d1073437ae94dfc5400d8794ceca8de5ceb0",
  "reader_reviewed_commit": "64fa2cdd31eae9f7c70c2cb5d293d742995a5748",
  "required_next_gate": "Separate independent exact artifact/source/role/cutoff/fit-receipt admission before any real registry entry or genuine forecast dispatch.",
  "reviewer": "independent_p2_dispatch_review; no implementation repairs authored",
  "role_semantics": "ESPN_POSITION_BIN_OBSERVED_AT_CAPTURE",
  "schema": "nba-independent-prospective-S1-prefit-approval/1.0.0",
  "scope_raw_sha256": "b1a737d1bd79f2bed2d5556aa66d970ce4765ca9995bb6f9eceb9eb973bcb03a",
  "seed": 20261120,
  "source_manifest_raw_sha256": "5269b9d38d383b965b2c88587ac7a69eee5c75dcc52e941a703076b76dc1b82b",
  "source_observation_denominator": 698,
  "source_reader_raw_sha256": "8b61c753a41b59b9baad25ce179bd56ef3ceaf31645e76998b6408f296a447fd",
  "statistics": [
    "points",
    "rebounds",
    "assists",
    "threes"
  ],
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
  "writer_protocol_reviewed_commit": "ef360a88f847da27a456ddab3ba8c93e45f0a042"
}
