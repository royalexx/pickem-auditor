# Production consensus and slate reporting

Effective policy: `production-consensus-70-30-20261107-v1`, explicitly authorized
by the user on November 7, 2026. Production slate jobs use 70% historical
Engine A and 30% source-owned Engine B. Complete win/push/loss masses are mixed
before converting any displayed number to P(win | no push).

`config/production_consensus.json` freezes the weights and the numerical build.
The policy is authorized for production while empirical calibration remains
unestablished. It never sets a learned-blend certificate to true. Existing
research, market, availability, sample and Tier 1 validation gates remain.
Missing/unreliable components cause an explicit production abstention, with
individual component estimates retained for validation. Offline legacy math
callers preserve their baseline unless run inside `using_production` or with
`PICKEM_PRODUCTION_CONSENSUS=1`. Production jobs and pregame verification opt in.

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
restarted or edited. Bayesian/NUTS columns never enter the 70/30 production blend.

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
