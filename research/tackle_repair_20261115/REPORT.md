# NFL Tackles + Assists emergency repair — execution report

Research-shadow only. Code was implemented and executed; a source-certified sportsbook
forecasting system has **not** been established. Draft PR: https://github.com/royalexx/pickem-auditor/pull/136.
Authority: PA-V25-MASTER-2026-11-09 / v1.1 and the November 15 emergency directive.

## A. Root-cause reconciliation

All 7,057 null rows were caused by an explicit `combined_total=None` assignment under
`UNVERIFIED_COMPONENT_SEMANTICS`. All three original component values were present and
valid in every retained row; the separate audit reconciled every value to seven original
source-file hashes. No missing components, schema mismatch, invalid-component rejection,
or player/game join failure explained these particular nulls. Coverage: 808 players,
736 historical games. Source row counts by file hash are in FINAL_WS1_WS2_EXECUTION.json.

The v2.5.1 market adapter independently returned None for tackles_assists and appended
TACKLE_ACCOUNTING_NOT_INDEPENDENTLY_CERTIFIED to every defensive candidate. These were
real source-count blockers, but the underlying settlement uncertainty was not disproved.
Separate the calculation from certification instead of asserting sportsbook equivalence.

The 908-candidate/zero-ready checkpoint is confirmed for the frozen extension. New source-count
readiness is 584/908, leaving 324 blocked. Overlapping flags: 153 insufficient histories,
159 inactive/nonparticipant status, 43 name/ID discrepancies, 79 passed kickoffs. These flags
overlap and must not be added as disjoint populations. Readiness requires three retained games;
100 of the 908 have no retained history, and additional players have too little history.

The earlier 114 offers, 104 source-certified/research-eligible offers and 102 frozen S2
forecasts are confirmed. All 102 originate from model commit
cdf2e8c9029217ee26fb28d21f7ecd6e8aaeeb81, S2-ew-empirical-hl4-v1, with model source
SHA-256 9bc325fd0afa239a2abff78108ffdb0eb64d4e024bda49949a23b6b06aa35e74.
Their immutable run index supplies feature freeze 14:29:15.089813 UTC, training cutoff
14:26:51.670585 UTC and creation 14:29:18.370098 UTC, before the earliest 14:30 kickoff.
The original adapter explicitly sums all three components and excludes all-zero rows
without appearance evidence. Required metadata missing from individual rows is retained
in their hash-bound run index; no original row was amended. The index has no feature-pin
SHA (archived source-receipt mode), which is retained as a limitation, not backfilled.
 Zero O4/joint forecasts was an earlier checkpoint; it is superseded
for the new conditional source-count shadow execution, not for sportsbook certification.

The canonical formula sums distinct nflverse stat IDs 79, 80 and 82. Source documentation:
https://github.com/nflverse/nflfastR/blob/master/R/calculate_stats.R and
https://nflreadr.nflverse.com/articles/dictionary_player_stats_def.html.
A retained official NFL gamebook independently matches Derwin James, 2025_01_KC_LAC:
5 + 0 + 2 = 7, matching official regular-defense TKL=5, AST=2, COMB=7. This is a sample
reconciliation, not verification of all historical official corrections or all books.
DraftKings Pick6 rules explicitly make equality a void; captured sportsbook offers cannot
be silently mapped to that product. Source calculation and book/product settlement remain separate.

## B. Workstream repairs

| Workstream | Root cause / repair | Files | Tests and execution | Status |
|---|---|---|---|---|
| WS1 | Explicit nulls and blanket gate; shared strict validator, version/cache bump, immutable history and exact PFR/GSIS/game/team crosswalk | scripts/nfl_stat_definitions.py, nfl_sunday_feature_store.py, nfl_sunday_market_extension.py, population_nfl.py, nfl_tackle_repair.py | 7,057 original raw rows reconciled; 584 source-count-ready candidates | IMPLEMENTED, TESTED, SHADOW-ONLY |
| WS2 | Missing role peer handoff and unnecessary defensive exposure dependency; existing S4 law consumes source-count histories and position peers without inventing a snap denominator | scripts/nfl_tackle_repair.py; unchanged upstream v2/nfl_marginal_shadow.py | 91 real pregame source-count forecasts; original 102 S2 records preserved | IMPLEMENTED, TESTED, SHADOW-ONLY |
| WS3 | Defensive source integration and invalid mutually exclusive component allocation; paired exposure adapter and combined Gamma–Poisson credit path in existing O4 | scripts/nfl_tackle_opportunity_repair.py; research/nfl_opportunity_20261115/models.py | 48 O4 forecasts, 66 abstentions; 14 applicable original regression tests pass | IMPLEMENTED, TESTED, SHADOW-ONLY |
| WS4 | Legacy arbitrary tackle event rates; adapter supplies historical defensive parameters to existing game_once | existing joint_models/joint_simulator.py; nfl_tackle_opportunity_repair.py | 48 each J1/J2/J3, 4,096 shared scenarios/model/event; 28 original simulator tests pass | IMPLEMENTED, TESTED, SHADOW-ONLY |
| WS6 audit | Exact original-contract comparison, analytic/empirical probability recheck and immutable legacy preservation | scripts/nfl_tackle_repair_audit.py | 114 rows retained; 91 + 48×4 source-count forecast checks pass | TESTED automated audit; independent reviewer acceptance PENDING |

The existing O1/O2/O3/O5 code and production weights were preserved. No solo/assist market
is published by the repair. O4-W remains unavailable as an estimated weather model;
WEATHER_EFFECT_NOT_ESTIMATED is explicit. J3 uses the existing frozen scenario assumptions,
not fitted game-specific coefficients. J4 is diagnostic only. The supplemental saved-draw audit found 291 defender pairs;
correlations range from -0.011743 to 0.303221, median 0.059618. This demonstrates
scenario-induced dependence, not calibrated joint-event probabilities.

## C. Before-and-after coverage

| Measure | Previous checkpoint | Final committed execution |
|---|---:|---:|
| Original T+A contracts retained | 114 | 114 |
| Source-certified / research-eligible original quotes | 104 / 104 | 104 / 104 |
| Valid source combined totals in frozen extension history | 0 populated | 7,057 |
| Historical players / games represented | 808 / 736 | 808 / 736 |
| Defensive candidates ready for source-count modeling | 0 / 908 | 584 / 908 |
| Candidates with positive snap history among retained player-games | not authenticated in extension | 616 / 908 |
| O4 paired positive defensive exposure rows | not integrated | 2,857 |
| Existing frozen S2 original forecasts | 102 reported | 102 verified, unchanged |
| New S4 baseline forecasts | 0 | 91 / 114 |
| New O4 forecasts | 0 | 48 / 114 |
| New J1 / J2 / J3 forecasts | 0 / 0 / 0 | 48 / 48 / 48 |
| Fully sportsbook-certified forecasts | 0 | 0 |
| Independently reviewer-accepted forecasts | 0 | 0 |

The snap crosswalk retains 12,764 of 12,785 all-unit provider rows; 21 lack unique PFR/GSIS
mapping. Zero defensive snaps remain measured zeros, distinct from missing exposure and
special-teams snaps. All-unit crosswalk rows are not all usable defensive histories.
616 is a retained positive historical snap count, possibly on a prior team; it is not the
earlier 598 current-team positive-snap candidates or a count of valid projected denominators.
O4 additionally requires same-team paired history. It excludes 3,510 retained history rows
without positive defensive snaps and 690 whose defensive snaps exceed the available
opponent attempt/carry/sack play accounting. No missing or incompatible denominator is fabricated.

New WS2 abstentions: 10 source-ineligible, 2 identity mismatches, 11 passed kickoffs = 23.
104 eligible quotes minus 2 identity failures = the original 102 S2 forecasts; minus 11 now-expired
London contracts = 91 newly generated S4 forecasts. Old London forecasts are preserved, not backfilled.
O4/J1–J3 abstentions: the same 23 plus 41 insufficient paired histories and 2 stale roles = 66.
There are no O4 baseline substitutes mislabeled as genuine O4 forecasts; WS2 remains available separately.

## D. Statistical validation

No prospective performance or matched historical sportsbook gain is established. The original
102 S2 forecasts remain untouched, with full comparison rows. A separate outcome-causal replay
uses the retained historical cohort and a fixed diagnostic 5.5 threshold, not historical offers.
It scores 4,651/7,057 rows from 519 games; 2,338 lack player warmup and 68 lack position peers.

| Diagnostic model | Brier | Log loss, clip=1e-12 | Predicted Over share | Over-selected share |
|---|---:|---:|---:|---:|
| Unchanged S2 empirical | 0.116255 | 1.186210 | 17.76% | 12.90% |
| Existing S4 Gamma–Poisson | 0.105980 | 0.348779 | 14.67% | 6.94% |

Observed Over share is 17.22%. Paired S4-minus-S2 Brier difference is -0.010275;
1,000 game-cluster bootstrap replicates, seed 20261115, give 95% interval [-0.013376,-0.007377].
Five-bin reliability and full denominators are in FINAL_AUDIT_REPORT.json. S4 underpredicts
Over frequency by about 2.55 percentage points despite its lower aggregate Brier loss.

These seasons have known prior model-development exposure. Receipt acquisition postdates the
historical target games, the cohort selects current-roster survivors with retained last-ten
histories, and the threshold is synthetic. Therefore this is a descriptive diagnostic, not a
sealed pregame holdout, proof of sportsbook skill, or prospective model promotion evidence.
Game-cluster uncertainty does not remove these selection or availability limitations.
No prospective Brier/log-loss/calibration values are manufactured before settlement.

## E. Prospective execution

Final code-pinned run generated 91 S4, 48 O4 and 48 each J1/J2/J3 conditional source-count
forecasts. Feature freeze: 2026-11-15T17:26:59.963993Z; opportunity input freeze:
2026-11-15T17:27:12.579221Z. Audit completed 17:28:26.497121Z. Each generated forecast
has a pre-kickoff timestamp and uses historical sources available before its input freeze.
No November 15 realized snaps or outcomes enter the features. Mathematical Over/Under/Push
probabilities normalize; discrete supports and exact integer thresholds are checked against
analytic laws, saved empirical masses and saved shared draws.

Sportsbook-certified and independent-reviewer-accepted prospective forecasts remain ZERO.
The upstream certification blockers are unverified exact book/product settlement mapping,
incomplete population-wide official/gamebook accounting reconciliation, unverified current
appearance/availability and unconfirmed continued quote availability. Conditional appearance
forecasts are not unconditional DNP/void probabilities. No bookmaker edge or release is claimed.
The separate automated audit has no authority to approve its author's statistical repair.

## F. Engineering receipts

Branch: repair/nfl-tackles-assists-20261115; stacked on WS1 source branch
chatgpt/nfl-sunday-ws1-source-20261115 at 3b4aff4065f9a07a5965867c344142bc6076488b.
Main inspected at 912bc7010058092ea735dcda0aa941429194474b.
Source validator commit: 0bc980c. Executed pipeline commit:
446f078595ae60cfb50fdf456a043927d75375b5. Draft PR #136 is unmerged.
DEPENDENCY_PROVENANCE.json records exact WS2/WS3/WS4 upstream commits and source-code byte hashes.

Final Deepnote notebook: 95faf56cf9ce41008b640eece1af03a1.
Successful run: d22cb040-bc36-4bc4-8d28-f7e70aab1331.
Final artifact root in Deepnote:
reports/nfl_20261115_prospective/tackle_repair_v252/committed_20261115T172653Z/.
The authoritative repair-version handoff is ws1_ws2/HANDOFF_PIN.json in that root.
Original Sunday source and feature pins were not replaced. Supplemental read-only notebook
98a83fd36ba841fd91a4939679723bcb, run 65e3e1a1-3cd5-436d-a97f-de6a3bdf566a,
records original model commits, missing per-row metadata and J4 correlations.

Important SHA-256 receipts:
- Original canonical source manifest: 5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71
- Final repair feature handoff: 1c199b3930737ccfe60dc70b56afbaff0b640a88e6ae1603988a4a64e397dd5f
- Final 114-row audited comparison: 5f357351d069d70eb990a07b6e8c6eedd4ef94ba0d63116b4288f50f98e52b0d
- Unchanged original 1,845-contract first-forecast population: 766245a051b4b3247009040a0c28df82fde285fb237ab40087d510bcfd4efd5d
- Official sample gamebook PDF: f95ca2d7f8adb6d196853cd3c0a93c005011480ad4e8a37d73eb4cdf3d49fb0c

Public receipt files with _public_copy_redaction are explicitly labeled derivatives with signed
URL query strings removed. Original receipts remain unchanged in Deepnote, with their original
SHA-256 values recorded in PUBLIC_COPY_REDACTIONS.json. Automatic approval review rejected
the initial attempt to push raw signed URLs; no raw signed URLs were published.

COMMITTED_EXECUTION_BINDING.json enumerates final output hashes, model-code hashes and the
source-code archive hash. Initial exploratory execution receipts are retained separately;
they are not the final authoritative repair snapshot.

Tests: 106 relevant local tests and 58 subtests PASS; 14 original WS3 tests and 8 subtests PASS,
4 deselected (native-loader cases outside this branch and the obsolete component-allocation
invariant); all 28 original WS4 regressions PASS. Final committed Deepnote canary: 8 tests PASS.
The original component regression reproduced five failing subcases before repair. One initial
O4 notebook failed for a missing stat_registry dependency; the dependency was supplied explicitly
and the later source-bound and final committed runs succeeded. No final required run failed.
Independent reviewer sign-off is pending; no statistical release gate was passed.

Rollback: stop consuming this repair-version handoff, or revert the two repair code commits
in reverse order on the isolated branch. Keep all source/output receipts. No original forecast,
posterior, settlement, production weight, publication switch or automation schedule was rewritten.
.training-control/PAUSED.json remains paused=true; no NUTS was launched.

Remaining coverage work: reconcile the 690 snap/play incompatibilities with official opportunity
accounting; resolve identity and inactive-status rejects; add source-backed roles and missing
paired exposure coverage; bind exact sportsbook/product rules, DNP/void/push/overtime/correction
policies; obtain independent review; then score genuinely prospective frozen outcomes.

## G. Final decision

| Component | Decision |
|---|---|
| Strict source definition, null repair and versioned feature handoff | IMPLEMENTED, TESTED, SHADOW-ONLY |
| WS2 combined-history baseline | IMPLEMENTED, TESTED, SHADOW-ONLY |
| O4 and J1–J3 corrected adapters | IMPLEMENTED, TESTED, SHADOW-ONLY; unsupported rows BLOCKED-BY-DATA |
| Separate automated integrity comparison ledger | TESTED; independent reviewer verification PENDING |
| Blanket exclusion of valid source counts solely for missing optional snaps | REJECTED |
| Book/product equivalence and complete official-accounting certification | BLOCKED-BY-DATA |
| Statistical improvement, Tier publication and production promotion | No RELEASE-APPROVED component |

Infrastructure execution succeeded. The primary fully source-certified sportsbook delivery
criterion and the separate prospective predictive-improvement criterion remain unfulfilled.
