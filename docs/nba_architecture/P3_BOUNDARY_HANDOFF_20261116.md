# P3 source boundaries and executable S/J handoff — revision 2

Research only; PR #166 remains draft, **G1 BLOCKED**. Governing authority:
PA-V25-MASTER-2026-11-09 / v1.1, with the user's bounded P3 engineering assignment.
This revision follows independent report PR #168 and preserves its 366/366
PASS at `80dbed35f983839f962250ad1c0236061dc6ee00` as historical evidence.
No new algorithm requirement or synthetic-minute defect was demonstrated.

## Implemented boundaries

- `v2/nba_o_family.py` now requires explicit per-player `team_id` and
  `source_bindings` in the complete immutable prior manifest. Every referenced
  receipt must exist in P1; availability must follow original receipt observation,
  retrieval and ingestion, precede freeze, and training must precede P1's cutoff.
  The WS2 bridge retains override receipt references, checks override clocks,
  and labels its neutral role/usage and zero-hurdle/exit assumptions synthetic.
- `verified_pregame_fit` is rejected with
  `O_INDEPENDENT_PARTICIPATION_ATTESTATION_REQUIRED`. No string, source hash,
  Monte Carlo participation frequency, or owner attestation certifies a fit.
  Non-excluded participation probability remains null/unknown. Exclusion requires
  P1 legal/availability evidence and produces verified-out probability zero.
- Home identity requires exactly one P1 schedule feature named `home_team_id`
  whose value equals the supplied home ID and whose receipt equals the supplied
  receipt. An existing unrelated hash is insufficient.
- `v2/nba_o_bridge.py` reads ESPN scoreboard/header competitors from exact P1
  receipted bytes, checks game and both team IDs, and independently checks the
  home designation against the P1 feature. No target player box, minutes, score
  or result field is read. Original bytes must be supplied from P1 captures;
  this adapter does not fetch a target box or authenticate a provider itself.
- `bind_p1_priors` validates P1 feature-to-prior-to-source byte bindings.
  `build_p1_opportunity` is the real-source entrypoint. Missing raw captures,
  incomplete model-prior fields and identity/clock mismatches reject. Historical
  P1 input returns a sealed `HISTORICAL_RECONSTRUCTION_UNCERTIFIED` abstention
  before sampling. It does not reconstruct an active target roster from outcomes.
- P1 history/context evidence is preserved with original feature receipt, clock,
  prior date and uncertainty. Legal eligibility, observed availability, unknown
  observation state, independent participation probability, scenario participation,
  played-conditional minute law and role-state draw remain separate. DNP,
  PLAYED_ZERO_MINUTES and PLAYED retain their original distinct meanings.
- P1-supported role, rest days, back-to-back, transaction, injury and uncertainty
  features are carried through the sidecar and consumer handoff. They do not
  become guessed numerical adjustments. Missing fields remain absent/unknown.
- Sidecar validation now validates P/G/O themselves, requires schema/game/context
  joins, checks each player's share-to-opportunity multiplication, rejects duplicate
  players, and deterministically replays roles/shares/sampling attempts using the
  original allocator. Resealing an altered seed, prior, role or shares does not
  evade replay. Create-only persistence validates before freezing artifacts.

## Preserved mathematics and limits

`v2/nba_opportunity.py` is byte-for-byte unchanged: SHA-256
`6dfb65b783f881de37e3779f3eb40433e1a1c99db103b0b3fef49e30092a5b30`.
MinuteLaw, capped_allocation and lineup_segments are reused. The P3 `_one_team`
and `_share_scenario` generating functions are unchanged. The version is now
`nba-p3-opportunity/0.2.0`, intentionally versioning the boundary/seed namespace.

Each original G scenario supplies its weight, overtime and home/away possession
pools once. Each team conserves 240+25×OT player-minutes, each player has at most
48+5×OT minutes, and the five-on-court clock witness reconstructs those minutes.
Played-conditional marginal laws come from exactly those weighted joint draws.
Participation is conditioned on feasible rotations; sampled frequencies are not
asserted to equal independently fitted Bernoulli marginals. Early-exit fractions
are opportunity caps, not authenticated exit-time or substitution predictions.

## P1 input contract and source gaps

P1's current pinned history adapter (`e0b8703887d327c8d8ac34807078e75e7b59a540`)
exports date-only `prior_boxscore` features and explicitly unknown target legal
eligibility/availability. It does **not** export an authenticated target active
roster, home schedule feature, participation fit or original pregame role model.
No genuine qualifying fit/capture was supplied in this task. Those omissions
remain data blockers; synthetic conformance fixtures cannot close them.

For future original-source input, P1 must supply:

1. A validated immutable P snapshot, including the source-bound `home_team_id`
   schedule feature and complete independently sourced target candidate roster.
2. Exact original ESPN schedule/header bytes matching its existing P1 receipt.
3. For each player, a `player:<namespaced-id>:opportunity_prior` feature containing
   canonical JSON `{player_id, team_id, prior}`. The prior excludes only the
   circular P snapshot hash. Its receipt and available timestamp match the feature.
4. Exact receipted P1 model-input documents containing an `opportunity_priors`
   map with complete player coverage. Each value has `{player_id, team_id, prior}`;
   the raw prior excludes circular snapshot and receipt/source_bindings hashes.
   This is a **proposed P1 export interface**, not a claim ESPN publishes models.
5. A separately reviewed participation-fit authentication/training manifest API
   before independent participation certification can be enabled. This revision
   intentionally accepts no purported independently fitted participation model.

Hashes here prove byte equality and joins. P1 owns external source authenticity,
roster completeness and original availability evidence; P6 independently reviews
those claims. A caller able to replace all source bytes and P1 receipts has not
thereby created authentic evidence. The `build_opportunity` low-level API remains
an explicitly uncertified research generator; use `build_p1_opportunity` for the
source-bound route. Its successful status is still SHADOW_NOT_CERTIFIED.

## Executable P2/P4 consumer interfaces

`v2/nba_o_consumers.py` exports:

- `consumer_fixture(p,g,o,sidecar)`: validates/replays and exports actual generated
  source hashes, role state, participation uncertainty, scenario IDs/weights,
  shares, minutes and five-on-court witnesses.
- `dispatch_scenarios(..., s_consumer=..., j_consumer=...)`: passes the same draw
  to owner callbacks without new sampling or likelihood mathematics.
- `call_p2(..., predict=..., fitted=..., player_id=..., role=..., **options)`:
  calls the actual P2 prediction API with the full generated O/G objects.
- `call_p4(..., simulate=..., conditional_rates=..., **options)`: calls the actual
  P4 simulator. It fails closed unless `team_ids[0]` is the source-bound home team,
  because current P4 assumes this order when applying home/away possession effects.

P2 owns mapping fitted role labels to `role:<index>` states; no inferred mapping
is fitted by P3. The executable example explicitly uses a synthetic wing role.
P4 currently consumes O minutes but has no sidecar share-aware real S adapter;
P3 exports the evidence and does not implement that owner's event logic.

Run `python scripts/nba_p3_handoff_check.py --output <new-folder>` for a frozen
synthetic O/sidecar/consumer fixture. With `--owner-root <disposable-checkout>` it
calls actual P2 and P4 implementations. The receipt pins the tested owner code:
P2 `96d210a6100085640e7e82928ab1c864839fc454`, P4
`b3729c53509cb063e2e451b7e4feb0ac2c6a9552`. P2's unconditional call must abstain
with UNKNOWN_APPEARANCE_PROBABILITY; its played-conditional distribution and
conditional kernels are callable. P4 generates valid same-scenario synthetic J
output. P4's synthetic-only rate restriction remains intact. **No real S-to-J
conversion or real-source statistical readiness is claimed.**

## Independent P6 review request

Please independently check the exact implementation SHA and raw SHAs in the
adjacent execution receipt, reproduce both full G0/P3 and pinned P6 controls in a
disposable checkout, and rerun the generated fixture through the pinned owner
APIs. Specifically challenge incorrect home receipts and raw home designation,
post-freeze availability and overridden priors, post-trade team binding, incomplete
roster coverage, forged fit certification, unknown/DNP/played-zero separation,
infeasible rotations, early-exit caps, 0/2/3-OT physics, weight mismatches, source
byte hashes, mutable prior manifests, resealed role/share/seed changes and replay.
Review whether the proposed P1 export and actual owner callable boundaries are
sufficient; do not treat synthetic fixture status as authenticated source evidence.

Evidence required from P1: original roster/transaction/injury/schedule captures
and independently substantiated participation/minute fits with complete source
and training clocks. Evidence required from P2/P4: accepted role mapping and real
S-kernel-to-J adapter using the same G/O draw. Keep **G1/G2 BLOCKED** pending those
artifacts and independent P6 signoff. P3 does not grant G1 acceptance itself.

Rollback: close draft PR #166 or revert only this P3 change. Preserve the prior
independent report, frozen G0 implementation, historical receipts, owner code,
production collectors, NUTS artifacts, scoring/weights and schedules. No target
actual minutes, historical predictions, historical scores or fit weights were
accessed or created. Main was inspected at
`912bc7010058092ea735dcda0aa941429194474b`; no production action was taken.
