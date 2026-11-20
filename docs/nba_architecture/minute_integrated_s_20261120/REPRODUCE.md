# Ordinary-minute S1 integration candidate, not release

Base: PR190 publication0f79277a3de6bf458a6da3f99377bf6a6bf8f688. Numerical
implementation8730aad9b20926e0de319c1aded94c16972c6592; actual candidate and
targeted test implementation13a5419f2b1765e68f4c170fbbf3638962d934a3. No original
forecast/model/source was changed and no model was fitted for this candidate.
The original admission reader deterministically reconstructs the four existing
fits in memory to verify their exact bytes; it saves no new model and changes
no fitted artifact or hyperparameter.

execution/ contains the actual new candidate computation clocks, original parent
forecast clock, full140attempts,56ordinary-integrated distributions and84retained
abstentions. CANDIDATES.csv displays each result and its excluded exposure mass.
REJECTED_sub30_scope_extension.json and ordinary_candidate.json preserve the
initial rejected scope extension and intermediate prototype. They are not newly
issued forecasts or admitted replacements. See ORDINARY_DOMAIN_ADDENDUM.md.

The semantic payload hash covers canonical sorted compact JSON before adding
payload_sha256, candidate_computation_started_at,
candidate_computation_completed_at and payload_hash_domain. Raw SHA256SUMS
instead covers complete exact file bytes, including all metadata and clocks.
The field excluded_sub30_probability_within_original_retained_OT means JOINT
mass P(M<0.5 AND retained OT); it is not normalized by retained OT probability.
Ordinary probability plus this mass equals the original retained OT mass. This
domain exclusion is separate from omitted OT and the disclosed count-tail bound.
The quadrature-order difference is raw unnormalized mass L1 and not rigorous.

Use the same pinned numerical dependencies as PR190. Recompute without replacing
any existing execution record:

```python
import json
from pathlib import Path
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture.minute_integrated_s_v1 import replay

a = Path('docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive')
parent = json.loads((a/'forecast.json').read_bytes())
value = replay((a/'forecast.json').read_bytes(), forecast_at=parent['forecast_at'], **frozen_inputs(a))
saved = json.loads(Path('docs/nba_architecture/minute_integrated_s_20261120/execution/candidate.json').read_bytes())
assert value['payload_sha256'] == saved['payload_sha256']
assert value['integrated_rows'] == 56 and value['abstained_rows'] == 84
assert value['new_forecast_issued'] is False
```

Run `python -m pytest -v tests/nba_architecture/test_minute_integrated_s_v1.py`.
The targeted tests independently integrate scalar PMFs for Cody Williams,
Kris Murray and LaMelo Ball, verify truncated mass/moments and matched fixed-mean
variance, and reject invalid rates and unsupported minute families. Actual test
argv/stdout/stderr are in execution/. The independent_review/ packet supplies a
separate decision and mathematical checks; this is distinct from model or
release admission. Verify this packet with `sha256sum --check --quiet SHA256SUMS`.

DOWNSTREAM_STATUS.json preserves all140J/Cattempts as blocked or upstream
abstained, with exact missing mechanisms. No valid real J scenarios, C scores,
historical predictive scores or release are claimed. The original native J
synthetic-only guard and C official-evaluation requirements remain intact.
Historical replay before release requires genuine pre-cutoff source/features and
compatible artifacts, the G1/G2/P8 prerequisites, and a separately reviewed
chronological evaluation contract. The current S1 artifacts postdate their
training games and cannot be used to claim forecasts for those games.
