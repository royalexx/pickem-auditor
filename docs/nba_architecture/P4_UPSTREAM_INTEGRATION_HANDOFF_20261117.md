# P4 upstream consumer handoff — pinned contracts, real integration BLOCKED

Governing authority: `PA-V25-MASTER-2026-11-09 / v1.1`. Bounded, explicitly requested P4 research engineering after accepted G0; no G1/G2, P8–P11, production or forecasting promotion. PR #164 stays draft on `research/nba-p4-j-family-g1-20261116`. This supplements, and does not replace, the original receipts or independent PR #168 findings.

## Actual inspected interfaces and exact source pins

| Owner | Exact inspected commit | Callable integration point | Status |
|---|---|---|---|
| G0 | `59d28dc23be97de2a6a82d22be8338151e31f5b6` | `validate_pregame`, `validate_opportunity`, `validate_integration`, `marginal_from_joint` | Accepted contract, unchanged |
| P1 #167 | `e0b8703887d327c8d8ac34807078e75e7b59a540` | `validate_ws1_envelope(record, source, require_source_bytes=...)`; `build_historical_pregame(...)` | Retrospective source integrity and historical reconstruction only; no authenticated model registry or original pregame participation/roster certification |
| P2 #165 | `96d210a6100085640e7e82928ab1c864839fc454` | immutable `FittedS(payload)`; `predict_conditional(fitted, player_id=..., role=..., projected_exposure=..., statistic=...)` | Real callable exercised using pinned synthetic fitted artifacts; not an arbitrary rate dictionary |
| P3 #166 | `80dbed35f983839f962250ad1c0236061dc6ee00` | `build_opportunity(...) -> (o, sidecar)` and `validate_sidecar(sidecar,p,g,o)` | Actual producer/validator exercised, exact O and sidecar consumed |
| WS5 v0.1 | `cdf926f56e86bc9d25576acff61fd6f091313159` | unchanged `v2.nba_joint.events.sample_events`; WS2 `lineup_segments` | All 13 original Git blobs preserved against existing reuse manifest |
| P6 #168 | `31435bd571ae1b4a9b7f1e1bbf05e55cef61126f` | 83 independent control tests, unchanged in disposable `work/qa` | Rerun by P4 author; this does **not** constitute a new independent review |

`v2/nba_joint/integration.py:PINS` also records exact raw P2/P3 module SHA256. `prepare.py` extracts those exact Git objects into `work/`, never into P1/P2/P3 owner paths, and does not fetch or install anything. A fresh clone needs the pinned commits available; fetch their branches if the local Git object database lacks them. The adapter fails closed on byte drift. The original WS5 CLI's separate missing `v2.nba_ws1` transitive import remains outside this ticket.

## Callable contract

```python
from research.nba_p4_integration.prepare import prepare
from research.nba_p4_integration.fixture import build
from research.nba_p4_integration.benchmark import PARAMETERS
from v2.nba_joint.integration import simulate_integrated
from v2.nba_joint.p4 import scenario_pmfs

upstream_root = prepare()
p, g, o, sidecar, artifacts, source_manifest, roles = build(upstream_root)
result = simulate_integrated(
    p, g, o, sidecar, artifacts, source_manifest, roles,
    upstream_root=upstream_root,
    evidence_mode="pinned_contract_fixture",
    variant="J1", seed=42, event_parameters=PARAMETERS,
)
pmfs = scenario_pmfs(result, p, frozen_at="2026-11-16T23:03:00Z", seed=42)
```

Version: `NBA-P2-P3-to-J/1.0.0`; shared P4 adapter now `NBAJointP4/1.1.0`. `simulate_p4` retains its explicit public signature and strict synthetic gate. The new public entry point calls the same private scenario loop after validating genuine upstream object shapes. It never accepts `adapter_basis="real"` as proof.

Default `evidence_mode="real"` **always fails closed** with `J_REAL_INTEGRATION_BLOCKED_P1_AUTHENTICATION_REGISTRY_UNAVAILABLE`. v1 has **no real acceptance path**. A caller-provided `P1_VERIFIED` flag, self-consistent manifest SHA or `FittedS` wrapper is not authentication. Only the repository-pinned synthetic artifact and manifest allowlist can pass the fixture path; its target IDs must remain explicitly synthetic. Changed parameters, late evidence, wrong roles, missing artifacts and rehashed forgeries fail. Tests and examples are conspicuously synthetic, including the P2-required `P1_VERIFIED` source-status-shaped values. They are **not original P1 authenticated evidence**.

Before implementing real mode, P1/P2/P3 must supply a source-authenticated, independently reviewed trust registry binding artifact bytes, exact code, model cutoff, complete original receipt/availability chains, dated roster/team and role identity. P1's current historical builder does not expose this registry, and neither upstream PR supplies genuine fitted pregame artifacts. Do not widen the allowlist into a caller-controlled trust decision. G1 real integration is **BLOCKED**, rather than claimed complete.

## Statistical mapping and explicit approximation

For player i with P3 scenario minutes m_i, share s_i, team minutes M and P2 retained conditional mean μ_i(m_i), the shared allocation input is

`r_i = μ_i(m_i) / m_i * (M * s_i / m_i)` for positive minutes; zero for zero minutes.

Thus `r_i * m_i = μ_i(m_i) * M*s_i/m_i`; when shares equal minute shares this reduces to P2's conditional mean. The mapping is explicitly changed by P3 opportunity shares and shared G scaling. Each audit retains the **complete P2 conditional integer PMF**, bounded omitted tail, mean, roles, O role state, O shares, O possession opportunities and projected kernel rates. J does not draw four independent counts and then repair impossible outcomes.

S1 Gamma–Poisson and S2 NB2 marginal laws are **not preserved exactly**: WS5 consumes projected means for attempts and relative weights for assist/rebound allocation. In particular S1 posterior-rate variance and S2 fixed dispersion are not faithfully propagated. Assist/rebound marginal means need not survive pool constraints either. S2 remains a shadow challenger; the fixture's assist artifact exercises its shape, not its calibration. `marginal_laws_preserved_exactly=false` is explicit. `marginal_distortion.json` quantifies finite-fixture mean/TV differences; these are descriptive comparisons of four draws, not statistical adequacy tests. Faithful distributional coupling and source-backed validation remain G1/scientific blockers.

For threes, a P2 S1 conditional count mean proposes shot volume, and a separate P2 S3 fitted success mean q_i converts that volume into expected projected attempts. The input to WS5 is adjusted to `r3 * pooled_p3/q_i`, with non-three point intensity preserved. WS5 first samples its pooled **integer projected 3PA** and player allocation. The S3 conditional call then receives exactly that integer, produces the beta-binomial law, and draws made threes within `[0, projected_3PA]`. No realized target-game attempts enter the API. Historical training attempts in the immutable S3 fixture are allowed prior-game exposures.

The S3 seam wraps the unchanged kernel's RNG protocol: its first three vector-binomial calls per team are 2PM, 3PM, FTM; only 3PM is replaced. This is intentionally version-specific, not a general NumPy RNG. Both source bytes and call count/shape are pinned, and drift fails closed. A future WS5 protocol change needs a new reviewed adapter. The original attempt, two-point, FT, scorer-assist and rebound algorithms still execute in the original kernel. No source collector or likelihood implementation was rewritten.

## Physical accounting and limitations

- P3 O is validated by G0, including its conditional-minute laws and conservation. The actual sidecar's prior manifest, G/O hashes, seed, home-team source receipt, IDs, weights, OT, minutes and participation are joined. Additional consumer checks reject duplicate sidecar players, wrong game identity, invalid contiguous intervals/indices and player opportunity values inconsistent with share × pool.
- J never samples participation or minutes. It uses the P3 role-conditioned minutes and opportunity shares directly. P3 role transitions are already represented in O; J does not apply them a second time. Statistical role labels for P2 are separate pinned fixture labels.
- Home/away possession effects follow the P3 home-team receipt rather than assuming roster order equals home/away. The new regression explicitly reverses home identity with unequal G pools.
- All two-team attempts, makes, free throws, rebound opportunities/unattributed credits, teammate assists and point arithmetic use one shared aggregate draw. Serialized full accepted ledgers are included and SHA-bound; self-assists, opponent assists, excess credited rebounds, invalid miss pools and budget discrepancies fail. All original 13 WS5/WS2 blobs are checked unchanged.
- G0 verifies team/player identity, 240+25×OT team minutes, player clock caps, shot/make support, score sums and same-draw PR/PA/RA/PRA. Tests exercise 0, 1, 2 and 3 OT, DNP, played-zero, and early-exit states. DNP/zero-minute projections produce zero ordinary event counts.
- **Possessions remain WS5 aggregate proxies.** Projected G home/away possessions scale attempts; an exact `FGA + turnovers + terminal FT - OREB = possessions` identity is not asserted or enforced. FT trips, dead balls, turnovers, chronological offensive rebounds and exact play timing are unmodeled. Required G0 physical fields for steals/blocks/turnovers remain zero defaults, not modeled forecasts. This ticket does not claim an exact possession or play-by-play simulator.
- Rebounds come only from missed FGs and the kernel's explicit terminal-missed-FT approximation. Each credited rebound is allocated once, with an unattributed category. Assists are scorer-linked teammate FG credits but simultaneous on-court scorer/assister availability is **not modeled**: lineup intervals witness minutes only, not event times.
- P3 `early_exit` is a **total-minute cap**, not an authenticated exit time or exact prefix of the game clock. Its generated lineup can place those minutes later in the game. This consumer neither fabricates an exit timestamp nor claims exact early-exit timing. Real event-time rotations require an upstream contract extension.
- OT is an upstream shared duration scenario, not a simulated sequence of tied regulation/OT endpoints. Final tied aggregate scores are rejection-conditioned as before. The new audit retains each rejected event draw, counts, ledger and stream attempt; no G/O scenario is dropped or reweighted. Conditioning changes marginal laws, including S3's unconditional marginal mixture.

## Family boundaries, PMFs and numerical evidence

J0 freezes game pace/efficiency as a control with the same supplied O exposure. J1 uses the exact shared G state. J2 adds only explicitly declared `role_sigma`/`efficiency_sigma` research uncertainty. These parameters have **no source-backed fit**. In the S3 path the pooled p3 efficiency shock affects inferred attempt intensity; S3 conversion itself remains the P2 fitted law. J3 remains gated by an explicit enabling flag, exact scenario labels and declared regime multipliers. J4 remains the existing dependence diagnostic, not a forecasting vote. No new calibration claim is made for J2/J3 or event parameters.

For every player and each PTS/REB/AST/3PM/PR/PA/RA/PRA statistic, `scenario_pmfs` reuses G0's exact weighted empirical transformation. Each scenario retains its original normalized G/O weight. Combination PMFs derive from same-draw arithmetic. No independently obtained Over probabilities are multiplied. “Complete PMF” means all mass of the finite joint scenario ensemble, not an exact population law or an absence of sampling error.

Reproduce from repository root:

```bash
python -m research.nba_p4_integration.prepare
OPENBLAS_NUM_THREADS=1 python -m research.nba_p4_integration.checks
OPENBLAS_NUM_THREADS=1 python -m research.nba_p4_g1.benchmark --counts 8 32 64 --output work/legacy_benchmark.json
OPENBLAS_NUM_THREADS=1 python -m research.nba_p4_integration.benchmark --output work/integrated_benchmark
```

Outputs are create-only; use a fresh output path for each benchmark run. The checks include original accepted G0/P4 tests, new upstream/adversarial tests, all 83 pinned P6 controls and unchanged P2/P3 interface suites. Those P6 controls are independently authored, but rerunning them here is author verification, not P6 acceptance. The exact tested code SHA, counts, logs, preserved baseline blobs, input/output hashes and benchmark timings are in the append-only execution receipt committed after the code SHA.

## P6 review request and remaining gates

Request independent P6 review of the **exact code commit in the new receipt**, and the receipt-only head, through PR #164 and audit PR #168. Challenge artifact allowlist vs authentication, real-mode rejection, P2 law projection/marginal drift, S3 projected-attempt protocol, home mapping, O/sidecar lineage, early-exit timing limitations, aggregate possession accounting, rejected-draw denominators, full PMFs, frozen blobs and deterministic replay. P4 author cannot award its own G1.

Status: **IMPLEMENTED / AUTHOR TESTED, pinned upstream contract fixtures; real integration BLOCKED BY DATA AND AUTHENTICATION; independent P6 review pending.** G1 overall remains NO-GO; G2/P8–P11, historical predictive claims, fitting real weights, Tier/production and collectors remain untouched. Rollback: close draft PR or revert only the additive P4 integration commits on this isolated branch, retaining previous WS5 results, original receipts and immutable source archives.
