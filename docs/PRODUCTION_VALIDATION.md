# Production consensus and slate reporting

Effective policy: `production-historical-ensemble-60-40-20261108-v1`,
authorized November 8, 2026. After sidecar inference the daily report
combines 60% historical-model consensus (Engine A, Bayesian A, Bayesian B
and any strictly eligible same-contract trained NUTS) and 40% opportunity-
focused Engine B. Among historical models, available eligible families
receive equal weight, with a minimum of two and Engine A mandatory.
Missing models and constituent weights are recorded explicitly. Market and
provisional NUTS are independent benchmarks only. Mix complete win/push/loss
masses before displaying P(win | no push).

`config/production_consensus.json` freezes the weights and the numerical build.
The policy is authorized for production while empirical calibration remains
unestablished. It never sets a learned-blend certificate to true. Existing
research, market, availability, sample and Tier 1 validation gates remain.
Missing/unreliable components cause explicit production abstention.
The initial Engine A/B calculation occurs BEFORE Bayesian and NUTS inference
and is a nonproduction preview; it cannot rank, set a Tier, or masquerade as
the 60/40 percentage. The finalized ensemble is calculated and frozen in
`slate_model_comparisons.json` only AFTER those sidecars, with version,
included family weights, raw probability masses and exact source identity.
Any missing historical family has an unavailable reason. Offline legacy math
callers preserve their baseline unless run inside `using_production` or with
`PICKEM_PRODUCTION_CONSENSUS=1`.

Future run UUIDs incorporate the policy digest. Existing forecasts/outcomes
are never reclassified or overwritten. Corrected empirical Bayesian sidecars
carry `model_build`, `numerical_revision` and actual generation timestamps;
group validation by that build, not just the older algorithm-family label.

Every afternoon produces JSON, CSV and Markdown under
`slate_model_comparisons.*`, with one row per original candidate side/line:

Player, stat, side, line, Engine A, Engine B, production Consensus, Bayesian A,
Bayesian B, normalized paired-price Market, NUTS, model version/status, and
consensus-minus-market gap in percentage points. Values are conditional on no
push; raw win/push masses and source identities are retained in JSON. Context
adjustments, if applied by the existing source-driven context layer, are flagged.
The full table retains unavailable components as N/A with reasons. Top displays
use consensus availability and gap; they do not require all challengers to agree.
Original ranking/publication gates remain separate from numeric forecasts.

NUTS comparison includes the pinned saves and context-targets adapters and
completed, successful generic population fits. GET-only discovery excludes
active/failed jobs; original strict convergence and full-population manifest
checks are required. The adapter only supports its audited count likelihood;
continuous-yardage fits remain unavailable until their observation/push model
has a separately validated adapter. Posterior bytes are cached with artifact,
ZIP, manifest and posterior hashes. No training runs are dispatched, canceled,
restarted or edited. Independently frozen, eligible Bayesian/NUTS outputs
enter only the historical 60% component AFTER pregame sidecar validation,
never the source-owned Engine B 40% component.

The current Deepnote token cannot read Actions artifacts (verified HTTP403).
Already staged hash-verified models therefore load independently of discovery;
the approved receptions posterior was staged through the connected GitHub
access. When running a slate from ChatGPT, use that connection to stage newly
completed eligible fits if discovery remains unavailable. GitHub's manual daily
workflow requests `actions: read` for its own ephemeral token. No credential
permissions were changed in Deepnote, and missing new models remain explicit.

NUTS source-family priority is fixed (released context-targets, released saves,
then generic population), never selected by the highest forecast. Every
available NUTS family remains in the JSON. Missing player/opponent/season/venue
identity, failed convergence, unsupported markets and poststart inference remain
explicitly unavailable. Original line/side matching and pre-event timestamps
are mandatory; a missing model is never replaced with Engine A or a prior fit.

The afternoon bundle freezes comparison rows and all sidecars before morning
settlement. Morning evaluation reads original archived probabilities, reports
production consensus and generic NUTS separately, and does not regenerate them
using outcomes. No historical probabilities, coefficients, outcomes or prior
convergence failures are changed by this deployment.

The daily Deepnote notebook resolves code/history refs to immutable commits per
run and saves those IDs with its output. The deployment updates the saved daily
notebook; it does not rerun a historical slate or change its schedule. Existing
self-hosted training checkouts and frozen campaign controls are untouched.

The first comparison for a parent snapshot is frozen, including missing generic
NUTS output. Stage newly completed models before the next source run; recovery
never overwrites an earlier displayed or archived evaluation cohort. Historical
adapter timestamps retain their legacy semantics; new saves/targets CLI outputs
stamp actual inference completion and reject completion at/after kickoff.


## Full-universe player/opponent scouting and research priority (November 8, 2026)

Every scripts/slate_model_report.py run also writes:
- slate_full_universe_research.json — exhaustive source-constrained evaluation
  of every same-run archived contract, including verified same-line player
  history, workload context, the available opponent-linked collector hints
  and explicit missing player/opponent/venue/weather checks. Unverified
  opponent fields are not described as established causal tendencies.
- slate_top10_evidence.json — up to ten **worthwhile research candidates per sport**, with the same frozen model probabilities, provenance, explicit missing evidence, and a per-candidate narrative;
- slate_top10_evidence.md — human-readable explanation for every candidate.

The selector processes the **whole latest immutable forecast batch**, not the capped 30-item research-triage queue. Bayesian A/B and eligible NUTS affect the new historical 60% component only after their immutable post-shadow evaluations. Eligible candidates must have both independently reliable production engines, a valid production consensus of at least 58%, a model-market edge of at least +3 percentage points, matching identities and before-game snapshots, plus at least two independently matched archived market books. Primary numerical or availability vetoes stay in force; missing game-specific active status remains a research blocker.

The transparent research score (not a hit probability) is

    40 * production_consensus
    + 25 * min(available Engine A/B/Bayesian A/B probabilities)
    + 25 * clip(market_edge_percentage_points / 25, 0, 1)
    +  5 * (1 - clip(model_spread_probability / 0.30, 0, 1))
    +  5 * verified_historical_workload_available

The spread penalty is capped at five points, so Bayesian disagreement can trigger further research without vetoing a potential high-edge opportunity. NUTS probability appears separately and does **not** influence the selection until its calibration is validated. Candidates can have large market gaps in the **research** report, flagged for independent inspection; they do not bypass the separate hard market-gap cap on approved picks.

Every ranking entry includes: all available probabilities and absent-model status, conservative floor, point gap, spread, a line-specific last-five and last-ten **current-season** hit/push count only when the collector's subject identity, checksum, public source URL, timestamp, observation dates, and exact market match are valid; recorded recent workload/exposure and the preceding-five comparison when available; context and availability caveats; source digest and warnings. No cache means no invented history, current-season hit percentage, opportunity, causal matchup claim, or "confirmed active" tag. Historical win rates and role observations overlap Engine A source data and therefore provide descriptive context, not independent extra evidence added to the numerical probability. When available, an exact line rate is *not* a promise of future results or a calibration certificate.

To prevent an artificially diversified top ten from becoming ten correlated markets on one player or fixture, the shortlist includes at most two distinct markets per player and four candidate props per fixture. Unselected rows remain in the complete probability archive. All top-ten entries remain **research-only and not publication eligible** until the existing verified board independently clears current status, causal scouting, markets, uncertainty, and empirical calibration gates. The immutable forecasts, morning settlement, and training runs are unchanged.

### Production versus approvals

The final 60/40 output is authorized as the numerical production forecast,
**not** an empirical calibration certificate. Existing verified-board, hard
market-gap, lineup and Tier gates remain independent. The preliminary parent
snapshot cannot grant a Tier. Morning settlement reads the original immutable
post-shadow comparison's consensus (when present) rather than rebuilding it
from updated posterior states or the preliminary parent snapshot. Existing
70/30 cohorts remain labeled with their historical policy.
