# NBA V2.5 six-team gate boundaries — P0R

## Active NBA research scope — user amendment November 19, 2026

Default NBA research profile is **source_listed_subset**, configured in `config/nba_research_profile.json`. Use `scripts/nba_research.py` for the default per-player source request/abstention ledger. Complete legal roster proof is no longer a prerequisite for supported per-player research under this profile. Unknown eligibility and participation remain explicit; conditional forecasts require valid source/model/cutoff support. Unsupported rows abstain while supported others continue, and every captured candidate stays in coverage. Original full-population B-P1-01/B-P1-02 decisions are historical and superseded for this profile; do not present them as the active launch blocker or relabel them PASS. No model, fitting, production or Tier authorization follows. See [accepted user amendment](narrow_default_20261119/ADR.md).


**G0** (contract): versioned, logically coherent source/feature, full predictive distribution, original-offer optionality, same-draw scenario, immutable forecast and evaluation interface with tests and external independent acceptance. G0 may pass without any fitted historical S/O/J models or proven predictive accuracy. Owner adapters may be blocked as long as precise conformance requirements are documented; their actual G1 acceptance remains mandatory before integration.

**G1** (family engineering): P1 WS1 source/revision/asof adapters on usable data; P2 statistical S full PTS/REB/AST/3PM outputs; P3 participated/DNP and played-conditional minute distributions plus O conservation; P4 G/J scenario integration; P5 independent replay/evaluation and Monte Carlo scoring infrastructure; P6 independent adversarial mathematical QA. Each must demonstrate version-2 conformance and reproducible fixtures, not just claims in PR descriptions. Unfitted P1/P2 participation, missing accepted NBA WS3 conditional likelihoods, incomplete original active roster and J2 historic regression are G1/scientific blockers, **not automatic G0 failures**.

**G2** (integrated): all six families pass G1 and the end-to-end player-statistic distribution pipeline works under consistent source clocks, identity, opportunity, scenario and no-leakage tests. Still not proof of market edge.

**P8**: 2022–23 chronological, out-of-sample Monte Carlo full-distribution replay (historical proxy provenance explicitly marked). **P9**: cached complete-pipeline distribution regularized weighting and dependence-aware ablations, scenario-convergence/weight uncertainty. **P10**: fully frozen 2023–24 validation. **P11**: genuinely prospective 2026–27 shadow, with no retro-certification of historical archive. No P8/P9 until G1+G2 passed. Never blend dependent S/O/J stages as separate ensemble votes.

G0 failure classification: FAIL if contract technically invalid; BLOCKED if sound author-tested candidate lacks independent acceptance, owner conformance/critical verification. Only independently signed acceptance can mark PASS. This ticket must not begin P1–P6 unless independent G0 PASS exists.
