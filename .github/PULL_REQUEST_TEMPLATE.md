## Directional research compliance (mandatory)

Reference: docs/research/DIRECTIONAL_ACCURACY_RESEARCH_BASELINE_20261108.md
Frozen control: config/directional_research_baseline_20261108.json

### Research hypothesis and phase
- [ ] I read the approved November 8 directional-accuracy research and AGENTS.md.
- [ ] This change identifies a specific, falsifiable source of directional/calibration error.
- [ ] The phase and documented phase-gate dependencies are identified.
- [ ] I disclose any departure from the approved methodology, with a separate authorization record.

### Source and causal integrity
- [ ] Input/source availability and retrieval precede the original forecast and event.
- [ ] Exact fixture/player/side/stat/line/run/model identities and void/push treatment are verified.
- [ ] Original frozen predictions and historical settlements are never overwritten.
- [ ] Missing lineup, injury, opponent, route/snap/minute or market data remain unavailable, not fabricated.
- [ ] Production 60/40 baseline, strict NUTS release and existing Tier gates are unchanged unless separately authorized.

### Evaluation contract
- [ ] Identical settled contract cohorts compare the proposal to frozen 60/40 and timestamp-valid market.
- [ ] Directional accuracy, predicted-vs-observed over share, Brier, log loss and model availability are shown separately.
- [ ] Chronological train/validation/sealed test splits are applied; no holdout information enters training or parameter selection.
- [ ] Game/slate dependence is handled with grouped resampling or explicit insufficient-sample status.
- [ ] Opportunity versus per-opportunity production, position/role hierarchy, or model dependence is tested where relevant.
- [ ] A no-feature/permuted-feature or otherwise appropriate negative control is included.
- [ ] No in-sample or single-slate result is presented as production authorization.
- [ ] Any calibrator is validated out of sample rather than assumed beneficial.

### Evidence
Relevant research section(s):
Frozen source/run/model hashes:
Training/feature cutoff and source timestamps:
Pre-registered baseline and challenger:
Matched cohort size, independent games, abstentions:
Paired direction / Brier / log loss:
Negative controls, uncertainty and failed tests:
Deployment decision (default: research-only, no promotion):
