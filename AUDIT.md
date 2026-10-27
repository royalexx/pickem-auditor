# Pick’em Auditor — fresh audit, 26 October 2026

## Verdict

**Usable for controlled research and prospective validation. Not yet a calibrated,
fully autonomous forecasting product.** Both engines execute and retain their
source/uncertainty gates. The confirmed defects found in this audit are repaired.
No hierarchical or additional prediction model was introduced.

Current versions: **A history-v5**, **B scouting-v7**, **shared-context-v3**,
usage-history-v2, nfl-season-v1. Earlier engine/context certificates cannot unlock
the new versions. No validated blend or context certificate is shipped.

This report supersedes the earlier cumulative audit text. Older JSON validation
files remain historical evidence, not proof of current-version full-slate readiness.

## Scope and method

Reviewed the canonical skill and source-to-publication flow: historical collection,
A’s pooling/distributions/uncertainty, B’s source verification and usage forecast,
shared lineup allocation, duplicate-event protection, packet validation and merging,
odds identity/freshness, grading, snapshots, closing prices, settlement and reporting.
Reviewed deployment certificates and the distinction between production and legacy
diagnostic models. Reproduced defects with offline cases before live checks.
An independent forward test exercised source cache → packet → both engines →
normalized snapshot. Live checks ran only after the offline repair batches passed.

The untouched starting checkout failed one of its 412 tests: the missing-key test
expected obsolete message wording. The new final results below are measured anew;
the earlier all-pass claim is not used as evidence for this release.

## Confirmed defects and repairs

| Priority | Defect | Repair / regression coverage |
|---|---|---|
| High | Gamma inverse CDF imposed a linear floor that lost very small, representable quantiles. | Log-space inversion for shape below one; independent tail constants and a SciPy shape sweep. Underflow below representable floats becomes zero. |
| High | Shared context reused raw NB variance after A had capped it. | Preserve and use A’s effective variance ratio; context can no longer silently undo its distribution policy. |
| High | An invalid side passed directly to A silently selected under. | Explicit side validation before projection. |
| High | Malformed empty context values could mean “no context”; an invalid source cache shape could crash B. | Explicit object/list checks; invalid context blocks and invalid cache causes abstention. |
| High | Malformed validation certificates could crash or admit infinite sample counts / invalid dates. | Validate certificate shape, finite nonnegative losses, integer sample counts and actual chronological dates before deployment. |
| High | Quotes could join a player on the wrong opponent/date; blank teams could be filled from an incompatible fixture. | Retain source fixture teams/date/ID namespace; reject contradictory fixture evidence during resolution and joining. Provider-specific event IDs are not equated across namespaces. |
| High | Future prices were treated as fresh; an undated sharp quote could borrow another book’s freshness. | Future timestamps are unavailable, and every included book must have a valid age. Consensus groups separate fixture identity. |
| High | Generated snapshots lost identities needed to find closing prices. | Preserve team/opponent/player/event metadata through prep and snapshots. Recover documented legacy inputs without guessing player teams. |
| High | Reports collapsed unrelated sports, players, events and lines; later forecasts could replace earlier observations. | Full market identity and earliest verified pregame forecast. Known postgame predictions excluded; legacy fallback explicitly retained. |
| High | Stale player-context confirmations and environment facts could enter publication checks. | Require the same 60-minute freshness policy as other upcoming facts. |
| High | Implicit away players inherited home spread/rest flags. | Infer orientation from the indexed fixture; negate home spread as needed; never copy home rest into missing away rest. |
| High | Stable-ID-only teammate absences were omitted. | Merge both indexes with sport/game checks and deduplicate the same teammate. |
| Medium | Re-merging a packet stacked its availability soft flags. | Track packet-added flags and replace them on re-merge. Existing caller flags remain. |
| High | New collector histories were not reliably attached to existing research seeds. | Refresh the source reference while preserving researcher evidence; remove stale references when the refreshed collector lacks one. |
| Medium | Source-backed B still generated missing-scenario requests. | Do not request researcher numerical scenarios for the source-owned baseline path. |
| High | NBA settlement passed a dictionary where the gamelog collector appends source URLs. | Correct list container; regression traverses fetch, parser and actual settlement. |
| High | Empty/nonobject prep could report successful audit without evaluating anything. | Reject nonobject JSONL rows; empty audits return a blocked status and nonzero exit. Malformed JSON gets a clear failure. |
| Medium | Fixture metadata supported by snapshots was rejected by the pipeline. | Accept identity metadata without making it a projection input. |
| Medium | Tests and guidance retained superseded wording/versions. | Updated contracts, recorded current results, and invalidated older engine/context validation versions. |

## Mathematical and anti-duplication findings

A remains history-only. Baseline/recent observation identities are disjoint; capped
prior weight enters the numerator and denominator once. Its historical role/window
selection is an explicit policy, not a learned or validated causal adjustment.
A recomputes source summaries before publication eligibility. Context arguments
cannot increase its baseline. The source role filter can exclude atypical-workload
games; this remains a modeling assumption requiring prospective validation.

B’s eligible forecast is recent-five observed workload × pooled observed production
per workload. Source zero-workload games remain in that usage window. Positive
exposure is required for rate estimation. Researcher opportunities, conversion,
scenario weights and injury narratives cannot modify this eligible forecast.
Legacy scenario/read tools are diagnostic only. B’s uncertainty is approximate;
its game-rate variation is not a fitted hierarchical model or calibrated interval.

The shared layer replaces each engine component’s allocation against its own
source-period team budget, then mixes probabilities. Multiple teammate absences
require one observed joint cohort. There is no separate opportunity bonus followed
by a second conversion bonus for the same event. Subject Out has no eligible
probability; it is not an under win. Source rows, event IDs, joint-state support,
roster completeness and embedded baseline exposure are checked.

This prevents ordinary researcher scalar double counting. It cannot prove raw
sources truthful or turn observational with/without comparisons into causal effects.
Matching cohorts is intentionally restrictive. Incomplete support blocks context.

## Verification

- **434 offline tests pass** (`validation/offline-tests.txt`).
- **891 independent numerical comparisons pass** (`validation/numerical-cross-checks.json`).
- Poisson point/push/under and NB point errors are below 4e-14 in the tested grids;
  Gamma-Poisson predictive error is below 1.5e-11; Normal predictive error below 2e-16.
- Gamma quantile relative error is below 1.9e-12 across the new tested shapes.
- NB mean-mixture quadrature remains approximate: maximum tested absolute error
  about 0.000648, against a 0.002 tolerance. These are test-domain results, not a
  universal error bound or evidence of predictive accuracy.
- Skill metadata validation, Python compilation and Git whitespace checks pass.
- Regression cases cover source-only invariance, duplicate events, Out gating,
  both-engine reliability, context conservation, malformed inputs and packet joins.

Reproduce offline from the project root:

```bash
python3 -m unittest discover -s tests -q
python3 scripts/validate_math.py
```

The numerical oracle script additionally requires SciPy. Ordinary unit tests do not
need live feeds. Keep the private credential file out of Git and external reports.

## Final live checks

On October 26, preflight passed all dependency, endpoint and credential-presence
checks. Seven separate endpoint diagnostics responded successfully. Host checks
alone do not establish complete data coverage.

A bounded authenticated test requested one fixture and up to three markets per
sport, with four returned books in each sample:

| Sport | Two-sided quotes | Sample history check |
|---|---:|---|
| NBA | 135 | One player’s current/prior logs parsed: 3 / 15 games |
| NHL | 51 | One player’s current/prior logs parsed: 11 / 82 games |
| NFL | 99 | 7,377 weekly stat rows; all 7,377 dated from schedules |

All 285 quotes retained the source fixture date and both teams. An initial NBA
probe reproduced the source-URL-container error; the corrected probe succeeded,
and the matching production settlement call was repaired and regression-tested.
See `validation/deep-audit-live-samples.json`, `deep-audit-live-feeds.json` and
`preflight-final.txt`. No API key or raw player recommendations appear in them.

These samples do not establish full-slate coverage or erase earlier broad-run
NBA gateway failures. No claim is made that every live history, lineup or research
fact is available. Current-version full-slate validation remains unproven.

## Remaining readiness limits

1. **Accuracy/calibration:** no qualifying prospective outcome set establishes
   current-version blend weights or context accuracy. A-only provisional fallback
   remains active. Reliable B and validated blend/context evidence are mandatory
   for the corresponding Tier 1 path.
2. **Data:** complete automatic NFL game-active rosters and detailed tracking are
   still external requirements. Verified roster imports are supported. Coverage,
   first reads/checkdowns, designed plays and analogous NBA/NHL advanced features
   cannot be inferred where source observations are absent.
3. **Model assumptions:** fixed sample floors, role filtering, variance caps,
   independent-game approximations and observational allocation need empirical
   assessment. Low/zero means and unsupported distributions can remain unranked.
4. **Operations:** fresh odds and research must be rechecked every run. A successful
   bounded sample is not a service-availability or complete-slate guarantee.

Keep the personal ZIP private: it contains the user-authorized local Odds API key.
