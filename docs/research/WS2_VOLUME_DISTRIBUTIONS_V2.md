# WS2 eleven-market distribution expansion

Governing authority: PA-V25-MASTER-2026-11-09 / v1.1. Bounded Phase 1
research infrastructure and prospective shadow execution, explicitly requested
by the user. No production ensemble, Tier, training job or schedule changes.
Rollback is to stop calling the new adapter; preserve every ledger file.

## Frozen experiment card

- Hypothesis: source-paired empirical distributions can expand eligible coverage
  without a sportsbook line and preserve within-outcome composite identities.
- Baselines: frozen original S2 remains read-only; new EW model retains half-life
  4; separate uniform empirical benchmark. Both consume at most ten source
  observations from the new WS1 pin. Minimum three appearances. QB samples use
  official schedule starter IDs; scrambles and kneels remain official carries.
- Identifiers: `S2-ew-source-paired-hl4-v2`, `S2-uniform-source-paired-v2`.
  The new source window, starter filter and paired reconstruction are explicitly
  versioned; old mathematical behavior and 1,672 original forecasts are unchanged.
- Exact expanded feature SHA-256:
  `c3ec93c78fcae413f66afe431f817f4d986f0fd1e884c665caefc5c7a3ed230c`.
  Previous source reference:
  `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`.
- Cohort: all 3,570 WS1 player-stat candidates, all eleven canonical markets;
  never require an offered line. Keep every rejection. All 1,845 authentic
  original contracts are retained separately, including unmatched contracts.
- Cutoff: WS1 freeze; verify raw receipt availability before freeze and actual
  forecast time before kickoff. Historical games must precede November 15.
- Primary acceptance: distribution normalization, raw component identity,
  signed integer yardage/nonnegative count support, zero preservation, exact
  contract Over/Under/Push extraction, no duplicate identities or future inputs.
- Negative controls: future timestamp, changed player/game/stat, wrong component,
  missing target, invalid tackle accounting, backup QB, source hash tamper.
- Promotion: none. No accuracy, edge, calibration or reliability claim. Historical
  chronological promotion evaluation requires original as-of evidence absent
  from this newly acquired archive. No synthetic-line results transfer here.
- Resource limit: CPU Basic; no NUTS, model training campaign or source collector.

## Model and source semantics

S1/S3/S4/S5 require source-bound historical role peers, which this WS1 pin does
not supply. Current roster position alone does not establish historical roles.
S6/S7 require original frozen controls, absent from this cohort. Every unavailable
model has a row-level abstention and an eleven-market coverage matrix entry.
Calibrated variants remain unavailable: no validated frozen calibrator is supplied.

Targets are official `targets`, with raw receptions <= targets and same-game
team passing-opportunity checks. Missing observations are excluded upstream,
never made zero. Explicit zero targets on a source player-game appearance remain
zero. Missing exposure does not create a denominator; the plain empirical
benchmark can still use an observed count. Regularized rates, position priors,
and exposure challengers remain unavailable without frozen source-backed inputs
and parameters. This retains a simple count baseline without inventing priors.

Only combined tackles are in scope. `def_tackles_with_assist` and
`def_tackle_assists` have unresolved overlap/accounting. The adapter never sums
these fields and abstains on T+A until official reconciliation exists.

Composite PMFs come directly from same-game raw component sums. Each joint
outcome carries its historical game, components, exact sum and weight. There is
no independent convolution. Separately estimated marginal histories may have
different observed windows; reconstruct composite outcomes from the recorded
joint representation, not independent marginal draws.

Predictive variance describes outcome variation. Weighted Bayesian-bootstrap
mean intervals disclose parameter uncertainty conditional on finite observed
support, using a recorded deterministic seed and Dirichlet concentration ESS.
They assume exchangeable games and do not establish calibrated coverage. Serial,
role, eligibility and unseen-tail uncertainty remain unresolved and disclosed.
Every law is conditional on appearing; QB laws additionally condition on starting.
No participation probability or active-status confirmation is invented.

## Reproduction and handoff

Run `python -m unittest discover -s tests -p 'test_nfl_ws2*.py'`.
Then `python scripts/nfl_ws2_volume.py --root /path/to/WS1/storage --out /new/path`.
The output directory must not exist. Exact source/table/code/model hashes,
training cutoff and creation times accompany create-only JSONL ledgers and
`HANDOFF_WS6.json`. The full distributions/abstentions and real contract
probabilities have separate counts and artifacts. Small summary receipts belong
in Git; full real populations remain in Deepnote project storage.
