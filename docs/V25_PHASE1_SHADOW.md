# V2.5 Phase 1 — isolated shadow contracts and evaluation

**Scope:** P1-01, P1-03, P1-04 and P1-05 foundations; P1-02 basic historical/role baselines; P1-06 pre-registered protocol stub. **Status: implemented prototype, not validated on live/certified feeds.**

This addition is independent of Phase 0R. It changes no production policy, GitHub workflows, Deepnote notebooks, training jobs, legacy forecasts, or Tier gates. The existing `scripts/directional_phase1_validation.py` remains authoritative for the pinned November 8 V1 retrospective audit. `v2/` is a new contract and shadow-evaluation layer and does not retroactively repair source evidence.

## Contract

- Each accepted quote specifies exact event/player/stat/period/line, distinct quote/contract IDs, offered product, original quote timestamp and source hash. A rejected quote has its own reason; synthetic lines remain diagnostic only.
- Every `ForecastSnapshot` references exactly one quote, records the actual artifact SHA and training cutoff, includes input freeze, decision and forecast timestamps, carries immutable source receipts, and binds **one** predictive distribution to all three Over/Under/Push probabilities. Time order is fail-closed.
- Discrete PMFs permit signed yardage and exact push mass. Poisson counts and continuous Normal diagnostics are included; Normal is not an endorsed NFL-yardage likelihood. No-vig probabilities are computed only when two compatible real decimal-odds sides exist; pick'em offers do not imply -110.
- Official settlement keys are event/player/stat/period. Both sides are scored as a single contract; push, void, absent, rejected and unsupported evidence have separate counts. Binary log-loss/Brier are conditional on a non-push event. Log loss applies a fixed, disclosed `1e-12` numerical floor and reports how many rows were clipped. The scorer reports every eligible quote as a denominator, plus matched baseline/challenger cohorts and game-clustered descriptive bootstrap intervals only if >=8 distinct games.
- Empirical energy score, `VS_0.5` and CRPS are research metrics for ensembles of joint game scenarios. They are not yet wired to historical scenario feeds.

## Replay command

With Python 3.10+ from repository root (stdlib only):

```bash
python -m unittest discover -s tests -p 'test_v25_phase1.py' -v
python scripts/v25_phase1_replay.py --input /path/to/immutable-shadow-export.json --output /path/to/new-shadow-receipt.json
```

Input is a JSON object with arrays `quotes`, `forecasts`, and `settlements`; each element contains the matching dataclass's required fields, and `distribution` uses `{"kind":"discrete","masses":[[0,0.4],[1,0.6]]}`, `{"kind":"poisson","rate":2.0}`, or `{"kind":"normal","mean":0,"sd":1}`. Reject duplicate JSON keys, invalid temporal order and duplicate contract/model IDs. Never reuse an existing output path; replay receipts contain input and result SHA-256 and cannot override the frozen inputs.

## Remaining work before Phase 1 exit

1. **P0R dependency remains mandatory:** reconcile shared schema and adapt only certified source/market/settlement material. No live dataset is certified by these fixtures.
2. Finish **P1-02** frozen V1 60/40 adapter and historical rate baselines against actual source-pinned Deepnote material; never regenerate prior predictions.
3. Finish **P1-03** full universe ingestion and manifest-driven fold replay, coverage stratification, and game/date sensitivity. Current CLI evaluates frozen input snapshots, not an automated historical model-training pipeline.
4. Extend **P1-04** regression controls to current project feed, exact period/stat settlement conventions and property-based randomized tests; no automatic assumption that void equals push.
5. Finish **P1-05** uncertainty and analytical sanity checks, then evaluate actual joint NFL ensembles when available.
6. **P1-06** lock experiment manifests with actual code commit, hashes and known historical design exposure; classify 2025 independence only after audit. The checked-in JSON is a protocol draft, not a completed experiment.

**Promotion gate:** closed. No Tier 1/2 authority, market-edge claim, merged production change, or NUTS restart is implied. Independent adversarial review of this implementation is still required.
