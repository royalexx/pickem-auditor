# P4 latest-owner consumer and constrained-law proposal v2

Authority: PA-V25-MASTER-2026-11-09 / v1.1. Research-only G1 remediation.
Accepted G0 remains unchanged at 59d28dc23be97de2a6a82d22be8338151e31f5b6.
This is an owner implementation/proposal, **not independent acceptance**.
P4 remains BLOCKED. No G2, historical fitting/validation, deployment or Tier
promotion is authorized by this document.

## Native consumer

`v2.nba_joint.integration_v2.simulate_latest` accepts the actual immutable P2
`FittedS` objects, actual P3 `nba-p3-opportunity/0.2.0` sidecar, original G0
pregame/G/O envelopes, source manifest and roles. `latest_upstream.py` verifies
every required owner executable file against the committed registry before
loading it. It also verifies unchanged accepted G0 code and reused WS2/WS5
code separately. This distinguishes inherited G0 from owner-added reuse.

The consumer binds raw fitted artifact bytes, raw synthetic source collection,
raw context bytes, parsed source-manifest digest, declared model cutoff,
training-row release times, source clocks, historical duration witnesses,
player/team/role membership, G/O identities/weights and exact P3 replay.
Its result records all consumer code hashes and source/artifact hashes. Parsed
JSON hashes remain distinct from raw byte hashes. The original old-pin
consumer, artifacts, tests and reports remain unchanged.

`research/nba_p4_latest/fixtures_v2` is the current **new synthetic population**;
the original native `fixtures` directory remains byte-preserved. Its literal
`P1_VERIFIED` field is a compatibility token required by the P2 synthetic
fitting API, not an authenticated provider assertion. Every raw document is
retained and explicitly synthetic. This fixture does not certify a complete
real roster, authentic participation fit, source clock or official outcome.

Real mode fails before fixture access with
`J2_REAL_BLOCKED_INDEPENDENT_SOURCE_AND_FIT_ADMISSION_REQUIRED`. The exact
external prerequisite is an independently admitted P1 original source and
fitted-artifact trust population, including roster/context, dated membership,
official duration/corrections, admissible clocks and fit provenance. A hash,
caller label or fixture allowlist cannot provide that admission.

## Separately versioned proposed law

Identifier: `NBA-J-CONSTRAINED-LATENT-RATE/0.1.0-PROPOSAL`.
Disposition: PENDING INDEPENDENT ACCEPTANCE. It is not an amendment of G0.

The former mean-only projection lost S1/S2 uncertainty. The proposal instead
uses the actual P2 predictive parameters to draw their exact latent mixing
law once per player/shared G/O scenario:

- S1: rate ~ Gamma(alpha, rate=beta), then Poisson exposure conversion.
- S2: rate ~ Gamma(k, scale=rate_mean/k), representing P2's declared NB2
  dispersion law. This is not an extra independent posterior uncertainty vote.
- PTS/3PM rate pairs are drawn from their product law conditional on
  rate_PTS >= 3*rate_3PM. Rejected pairs and complete attempt denominators are
  retained. The fixed 4,096 proposal limit fails closed; no G/O scenario is
  dropped, reweighted or replaced.
- Exact P3 scenario minutes/participation/shares scale those rates. G is shared
  once. Actual P2 S3 then converts shared projected integer 3PA to made threes
  within the same WS5 event draw. No incompatible final counts are generated
  independently and repaired afterward.

This is an explicit constrained-law approximation. It does **not** preserve
the original S marginal PMFs exactly. Both rate-compatibility conditioning
and the retained non-tied-final-score rejection alter the distribution.
The order matters: for each fixed compatible latent-rate draw, the event
kernel is sampled conditional on a non-tied final score. Rates are not
redrawn on tied-event attempts. Thus the proposal is the sequential law
P(rate | rate-compatible) P(events | rate, non-tied), with separately retained
finite-budget failure atoms; it is not one global rejection-conditioned
product law. An exhausted scenario fails the entire execution. No successful
scenario subset is renormalized into a replacement forecast.
All rejected final event draws remain in the audit. The complete empirical
J PMFs are normalized weighted histograms of the retained shared scenarios;
their finite empirical support is not a claimed bound on the underlying
Gamma-Poisson tail. P2 finite serialization tail bounds remain attached to
the separate source laws and are not misapplied to J's approximation error.

Exhausted executions raise the original typed `ContractError`, with an added
sealed `failure_receipt` attribute. It records input hashes, seed, scenario,
player where applicable, all rejected rate pairs and exact attempt counts,
all available event counts/ledgers, and `FAILED_NO_J_RESULT_PUBLISHED`.
The single and repeated-seed benchmark CLIs persist this receipt to a
create-only file. A failed repeated-seed run retains its completed raw prefix
with explicit failure status and publishes no successful pooled PMF summary.
Budget limits, errors and model sampling laws were not weakened.

## Mathematical impossibility and distortion evidence

An arbitrary pair of S marginals cannot always be physically preserved by
any joint coupling. If both PTS and 3PM are Poisson(1), physical arithmetic
requires {3PM >= 1} subset {PTS >= 3}. But their probabilities are
0.6321205588285577 and 0.08030139707139418. Therefore every physical Q must
change those marginal laws with a sum of total-variation distances at least
0.5518191617571635. Equivalently their means would require 1 >= 3. This proves
incompatibility; it does not assert that every actual owner fixture has that
particular incompatibility. A finite count cap 5 also differs from Poisson(1)
by at least its exact beyond-cap tail 0.000594184817581693.

Independent direct Gamma/Poisson quadrature agrees with the equivalent NB
references to 4.25e-13 for S1 and 3.35e-16 for S2. In an intentionally stressed
synthetic reference with X,Y iid Gamma(2,1), conditioning X >= 3Y accepts
exactly 5/32. The conditional means become 3.35 and 0.65 from original means
2 and 2. The 27/32 rejection mass and large mean changes quantify the cost
of that constraint; they are not hidden as exact marginal preservation.

`research.nba_p4_latest.numerical_reference` reproduces these analytical
controls. The benchmark compares all 48 primitive empirical player/stat
PMFs to their actual P2/O mixtures, including TV/CDF differences, mean,
variance, zero and tail mass. Four paths are a compatibility demonstration,
**not an adequacy experiment or a permissible distortion certificate**.
An independently accepted approximation budget/contract is still required.
No historical predictive scoring was used to justify this proposal.

## Precise remaining physical prerequisites

The unchanged WS5 aggregate kernel proves integer attempts/makes, scoring
arithmetic, scorer-linked teammate assists, missed-shot/terminal-FT rebound
pools, unattributed rebound credits and same-draw PR/PA/RA/PRA. P3 supplies
five-on-floor exposure witnesses. These do not establish event-time physics.

Mandatory unresolved semantics require a separately reviewed forward-model
contract, rather than a validator relaxation:

1. Possession/FT chronology: current Poisson opportunity pools and independent
   terminal-FT fraction are aggregate proxies. They do not identify exact
   possession ends, offensive-rebound resets, and-one/technical/flagrant FT
   sequences or reboundable final free throws.
2. Co-presence: the assist matrix ties each assist to a teammate field goal,
   but no event timestamp places that scorer/assister on the same actual
   lineup interval. Aggregate minute witnesses alone do not prove this.
3. Overtime: G fixes scenario duration/overtime count; the aggregate final
   score is conditioned non-tied. It does not prove tied regulation and
   intermediate overtime endpoints. No target-game result is consulted.
4. Early exit: P3's early-exit parameter is a total-minute cap. Neither the
   source evidence nor this law establishes an exact exit clock. No timestamp
   is inferred from that cap.
5. Approximation adequacy: actual law conditioning, opportunity-share scaling
   and finite event mechanisms require accepted distortion tolerances and a
   sufficiently precise synthetic engineering study. The four-path packet
   cannot award that acceptance.
6. Participation: the inherited structural G0 J envelope uses the word
   `unconditional`, while the actual P3 producer retains null unverified
   participation probabilities and samples a finite prior ensemble conditional
   on feasible rotation. The wrapper records this conditioning and remains a
   synthetic proposed scenario law. It must not be interpreted as an admitted
   unconditional participation forecast. Changing that envelope's meaning
   requires a separately accepted versioned contract; no nullable probability
   is silently converted into a source-certified 0 or 1.

These are material distribution/physical-model decisions requiring independent
review, not missing software checks that can be closed by assertions. The
proposal remains explicitly blocked until the reviewer accepts a bounded
contract or specifies the required separately versioned forward model.

The new native wrapper also validates complete raw count support, makes versus
attempts, points/rebound arithmetic and team/matrix population before publishing
the raw event audit. A narrow old audit-validator counterexample (+1 supplied
point with unchanged shot counts) is retained at exact 93e9c89; the complete
G0 bundle already rejected that mutation. The additional validator closes this
raw evidence seam without changing the WS5 generator or G0 semantics.

## O2 scaling and preserved failure

The original unchanged n=32 O2 case was reproduced before repair work in a
detached cf5483a checkout. `O2_n32_before.log` retains
`O_COUPLING_VERIFICATION_BUDGET`, SHA256
813bb339a6122d00e583af49a6a95dfb30da24a501a23e384287c9ba404515d6.
The new latest-owner n=32 regression also requires that rejection. No solver
budget was widened, scenario dropped, or O0 benchmark substituted for O2.
P3's separate sparse-witness/operating-range proposal requires P0 and P6
independent acceptance. B-P4-03 remains BLOCKED pending that decision.

## Reproduction and rollback

From this owner checkout, using Python 3.12, NumPy 2.3.5 and SciPy 1.17.0:

```bash
python -c "import json,subprocess; p=json.load(open('research/nba_p4_latest/upstream_registry.json')); subprocess.run(['git','fetch','origin',*[x['commit'] for x in p['owners'].values()]],check=True)"
PYTHONPATH=.:tests/nba_architecture OPENBLAS_NUM_THREADS=1 python -m unittest discover -s tests/nba_architecture -p test_p4_latest_integration.py -v
OPENBLAS_NUM_THREADS=1 python -m research.nba_p4_latest.numerical_reference
OPENBLAS_NUM_THREADS=1 python -m research.nba_p4_latest.benchmark --output work/new-p4-latest-benchmark
```

The benchmark refuses an existing output directory. Its exact outputs include
raw checksums, full input/artifact records, complete J ledgers/PMFs, actual P2
conditional laws and source/consumer hashes. The original immutable negative
probe remains unchanged. Rollback is to close this draft or revert additive
P4 remediation commits, preserving all reports and failure receipts.

Two QA preparation failures are retained separately: the first registry
assembly incorrectly attributed reused WS2 to G0, and numerical JSON output
initially exposed NumPy scalar booleans. These were QA defects, not evidence of
changed owner predictions. The registry now distinguishes inherited G0 from
reused source bytes; a permanent strict-JSON serialization assertion covers
the corrected numerical output. No old report or raw failure was overwritten.
