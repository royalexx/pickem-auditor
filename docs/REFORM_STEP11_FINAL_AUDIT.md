# Pick'em Auditor — reform closeout and independent-code-path adversarial audit

**Evaluation:** November 8–9, 2026 original historical settlement.
**Work completed by ChatGPT:** technical model reforms and strict
promotion/source gates. **Production:** original
`production-historical-ensemble-60-40-20261108-v1`, 60% eligible
historical consensus plus 40% verified opportunity Engine B.
**Training:** deliberately paused, including old manual Bayesian
training and sampler entrypoints. **Never overwrite or reconstruct**
the original pregame probabilities after outcomes became known.

This is an **adversarial verification of source, mathematical invariants
and technical release eligibility** by an independently written
read-only code path. It is **not an external human/third-party research
review** and does not establish profit, 80%+ calibrated props or a
production promotion.

## Implemented reform matrix, with evidence separated

| Item | Implemented technical change | Independent empirical approval |
| --- | --- | --- |
| 0–1 | Frozen baseline; manual training paused; existing posteriors preserved | No new accuracy claim |
| 2 | Source-timestamp/hash and market contract provenance guards | Missing older provider bytes cannot be retroactively recovered |
| 3 | Chronological 300/100, 20+20 dates, paired game/day resampling, fail-closed M2/M3 gates | Real settled source-complete cohort still inadequate |
| 4 | 253 official 1PM NFL contracts scored; separate 645 Nov5–7 historical contracts | One day cannot establish seasonal directional or calibration advantage |
| 4a | NUTS seed defect repaired; all 16 formerly noncomplementary pairs tested via 32 authentic trained-posterior calls, shared consensus/pair guard coherent | One **genuine** future pregame batch still needs operational acceptance |
| 5 | Full 2,436-side replay, original 160 candidate pool / 30 top-10 reproduced | Two originally selected full-slate top10 picks settled in 1PM; no reliable optimizer's-curse estimate |
| 6 | Source-reconciled snap-share × tackles-per-snap NFL research; verified `solo + with_assist + tackle_assists` credits; role-median frozen research tackle lines | Better overall synthetic-line Brier, but OLB/off-ball LB lack validated improvement and no real sportsbook-line matched validation |
| 7 | Original rank restored, λ disagreement-proxy shadow variants and shuffled negative control | No authentic Engine B `relative_se` for original 160; short settled top-k cohort |
| 8 | Market-inclusive 50/50 logit scenario plus M2/M3 chronological fit gate | Market-only beat unfitted blend in 50 coherent Nov8 contracts; no weights fitted |
| 9 | Exact same-game leg class + centered residual audit, game/date block underpower check, Fréchet bounds | Nov8 only 6 independent games / 1 date; no joint entry probability can be certified |
| 10 | Global L2-regularized Beta and market-stacking research challengers, Beta contains identity | 50 original coherent model/market pairs on 1 date with incomplete original source bytes; no parameters fitted |
| 11 | Independent-code-path release audit; comprehensive pause/production safety checks; adversarial tests | External third-party statistical acceptance and future-dated source evidence remain pending |

All code-level research implementations were intentionally kept
separate from the original production probability, ranking
and Tier/publishing paths. No actual market line is replaced by a
synthetic position benchmark.

## Independent release audit

The new `scripts/reform_step11_release_audit.py` validates, using
read-only, separately written assertions:

- **Exact production configuration**: historical 60%, opportunity
  Engine B 40%; Engine A mandatory; at least two reliable historical
  family models; no provisional NUTS, no market inside the historical
  family, and `empirically_calibrated=false`.
- **Training freeze**: marker `.training-control/PAUSED.json`
  retains `paused=true`, explicit user approval required before
  resumption, and original posteriors/checkpoints preserved.
- **Old manual workflows**: 12 separate Bayesian sampling/fit/benchmark
  workflow definitions now check that pause marker immediately after
  source checkout, before costly training. The existing main
  `precision-full-markets.yml` guard remains. The separate NFL
  trained-posterior **publication** workflow is also blocked until
  the user explicitly authorizes resumption. This covers
  **13 workflow definitions and 17 checkout paths** on the updated
  main branch. It neither invokes, cancels nor requeues any job.
- **Credited tackle total**: weekly NFL T+A explicitly sums
  `def_tackles_solo + def_tackles_with_assist +
  def_tackle_assists`; missing parts abstain. Step 6 consumes
  only the normalized combined market. The end-to-end regression
  tests exercise 4+2+1=7 tackles versus 4 solos.
- **Numerical and probability guards**: original NUTS paired seed
  method and fail-closed publication invariant remain; Beta identity
  and two-leg Fréchet bounds pass independent mathematical smoke checks.
- **No production backdoor**: shadow Steps 7–10 must not include
  consensus production-config writing or unapproved promotion
  authorizations; missing source/time qualifications still abstain.
- **Exact original Nov8 SHA-pinned source**: independent Deepnote
  verification loaded **253** official settlements, found **50**
  coherent consensus/market pairs on **one** independent date, and
  confirmed original pregame provider-source completeness is **false**.
  Downstream SHA-pinned results cannot manufacture earlier provider
  publication timestamps.

The original technical audit ran in a detached read-only Deepnote
environment with the GitHub branch checked out. The full offline
test suite passed **1,204 tests**, nine expected skips, zero failures,
with the expensive NUTS smoke job deliberately skipped. The repository
continues to carry existing static unit, provenance and mathematical
regression suites.

[Independent release forensic notebook](https://deepnote.com/workspace/stonks-a257-e2858df6-426e-479b-a4f8-0376a602f7bb/project/Pickem-Auditor-Daily-Cloud-Inference-9cc31536-93be-44db-bdeb-06fba3f61410/notebook/Final-reform-release-audit-original-NFL-receipts-and-training-pause-guards-fe81eb2d061043708522ef1c728665e7).

### Known limitations and adversarial findings

1. **Sample size is still the primary blocker** for player-prop
   selection, direction, calibration and game-dependence gains. Rows
   that share game/date information do not become independent evidence.
2. **Nov8 originals have incomplete pregame provider sources**.
   Neither a new ranking, calibration nor source-timestamp repair
   should reclassify those original rows as prospectively verified.
3. **NFL full-time linebackers are not proven improved**. More
   honest position-median lines exposed residual weaknesses in OLB
   and high-snap-share off-ball linebacker research.
4. **Beta/global stacking remains unfit, as designed**. A single
   realized Sunday is not a valid training target for a 3-parameter
   calibration method or market meta-model.
5. **Multi-leg entry probability cannot be estimated yet**.
   A naive product is only a hypothetical independence benchmark.
   The marginal bounds do not imply profitable opportunities.
6. **Training workflows on stale non-main branches** are not
   retroactively modified by hardening workflow files on main.
   Neither this audit nor the marker claims to terminate already
   queued or running jobs. The user had previously canceled the
   active Dell training run; this code adds future guardrails.
7. **No independent third-party researcher has signed off**.
   The extra auditor is independent in logic and tests, not the
   human/organizational sense.

## Eight explicit outstanding evidence/acceptance gates

The technical reform is **implementation-complete**. The following
are not honestly satisfiable from the available November 8 archive:

1. **4a true next pregame run:** verify paired NUTS/consensus
   consistency and pregame model qualification on a genuine new slate.
2. **5 selection bias:** collect many fully settled top-10 and
   equally eligible/unselected contracts, predeclared and not
   reranked after outcomes.
3. **6 tackle promotion:** independently archived actual player
   lines, defender snap-share histories and lineup evidence,
   especially full-time linebackers.
4. **7 ranking uncertainty:** obtain well-defined authentic model
   uncertainty input and later matched selected/unselected cohorts.
5. **8 market stacking:** at least 300 original verified older
   training contracts over 20+ dates and 100 later holdout
   contracts over 20+ further dates. Both proper scores must
   beat market-only and original production with paired
   date-block intervals.
6. **9 leg covariance:** collect many independent game dates,
   sufficient predeclared same-game and across-game pair classes
   and later outcomes before an approved joint-win/entry-EV model.
7. **10 calibration:** source-verified chronological training/holdout
   with original exact contract and push-mass accounting; distinguish
   calibration fit from pure market-directional advantage.
8. **11 external signoff/production:** separate statistical
   reviewer plus explicit user approval before changing the
   frozen 60/40 or approving new calibrated/high-confidence Tiers.

None of these items should be silently marked completed by an
automated code test. The future acceptance data are simply not
available in the original snapshot. The project can collect
prospective forecasts and independently grade slates while training
remains paused.

## Reproduce

Run the unit tests with `python -m unittest discover -s tests -q`
on the repository; the installed dependencies are specified in the
existing CI workflow.

For code/release policy without original project files:

```bash
python scripts/reform_step11_release_audit.py --root .
```

For the independently frozen original NFL 1PM settlement, run the
same command in the authorized Deepnote project where those immutable
source files already exist:

```bash
python scripts/reform_step11_release_audit.py --root . \
  --frozen pickem_runs/2026-11-08/20261108T135631Z/slate_model_comparisons.json \
  --settlement pickem_runs/2026-11-08/20261108T135631Z/slate_1pm_nfl_settlement_20261108.json \
  --pinned pickem_runs/2026-11-08/20261108T135631Z/directional_phase1_1pm_nfl_pinned_receipt_v1.json
```

Output is diagnostic-only. All source and code SHA-256 digests
are included and no original file is overwritten.
