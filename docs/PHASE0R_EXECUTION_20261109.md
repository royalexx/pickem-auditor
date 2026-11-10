# Phase 0R execution receipt — 2026-11-09 (Toronto) / 2026-11-10 (UTC)

**Project:** Pick'em Auditor V2.5. **Status:** `PARTIAL — RELEASE BLOCKED`. **Production high-confidence picks:** NOT AUTHORIZED. **Historical NUTS retraining:** PAUSED.

This is an evidence ledger, not a model-certification certificate. It distinguishes successful software regression testing from the stronger, unachieved property that every numerical prediction consumed the exact immutable, point-in-time source bytes.

## Source revisions and controlled changes

| Scope | Evidence |
| --- | --- |
| Starting `main` | `10404038846f9f621c245ca089daf91b974ddde9` |
| PR #86 — fail-closed input freeze | https://github.com/royalexx/pickem-auditor/pull/86 ; merged as `1799074428a0c74016042bae122f00527c953be0` |
| PR #87 — goalie saves paired Monte Carlo seed | https://github.com/royalexx/pickem-auditor/pull/87 ; merged as `b7c0acd0afba97d3620664ccd571b6f1e5e92036` |
| PR #88 — completed capture rather than started capture | https://github.com/royalexx/pickem-auditor/pull/88 ; merged as `5923eb32b628562574ee22a5e33bdb09547f759f` |
| Latest verified `main` before this receipt | `5923eb32b628562574ee22a5e33bdb09547f759f` |
| CI for latest `main` | [offline checks, success](https://github.com/royalexx/pickem-auditor/actions/runs/42727675145) |
| Training pause | `.training-control/PAUSED.json`, `paused: true`, resume only with explicit user approval |

### Change 1: mandatory source and input-freeze timeline

`scripts/phase0_input_capture.py` now emits a timezone-aware `input_freeze_at` after source capture and archival complete. `scripts/jobs.py` persists it, while `scripts/point_in_time_provenance.py` rejects missing, naive, future, retrograde or otherwise conflicting input freeze, source capture, source retrieval, book retrieval and model training clocks. A valid prospective row requires

`model_training_cutoff_at <= input_freeze_at <= forecast_at < event_start`

and all referenced evidence must be observed/retrieved no later than the freeze, with archived file bytes matching SHA-256 digests. Previously frozen historical rows are **not** upgraded by inference or reconstructed receipt timestamps.

**Residual limitation:** In the legacy run path, `pm.evaluate_candidate` is invoked before the original source evidence is archived in `phase0_input_capture.capture`. The current source-receipt gate therefore cannot independently prove that the model's numerical calculation read precisely the archived bytes, or verify unavailable upstream publication clocks. A pre-evaluation immutable input contract or independently verified before/after pinning of *all* actual model inputs is required before declaring Phase 0R complete.

### Change 2: paired NHL goalie saves shadow correction

Six Nov 9 contracts had invalid NUTS Over+Under sums (worst deviation 1.3832 percentage points). The `nhl_saves_posterior_shadow` seed had included side and per-side forecast timestamp. PR #87 makes the Monte Carlo seed depend on the shared run/event/team/player/stat/line identity. The integrity gate continues to withhold any invalid paired predictions. Earlier archived outputs are retained unchanged.

## Independent regression evidence

- GitHub Actions offline suite for PR #86 final branch commit `009e2bb34b99fbb6f977de079fef142afc97dfd4`: success, run `42725752438`; independent Deepnote read-only run `bbb92b03-70ab-44fc-927c-68b0e7390b1f` passed 40 targeted tests: Phase0 release 13, live capture 5, point-in-time provenance 9, jobs 13.
- GitHub Actions offline suite for PR #87 final branch commit `89532236a585b986b44244861fb14df097ca5aa0`: success; independent Deepnote read-only run `43a448d4-148d-452c-965c-bb6905fe9178` passed NHL saves (10) and model report (13) tests.
- GitHub Actions offline suite for PR #88 final branch commit `b8ec924303dc1d4a51eebfe2c10253729d530b73`: success; independent Deepnote read-only run `e7239851-2118-41c1-a092-d0815c6aa559` passed Phase0 live capture, release, jobs and provenance suites.
- No independent Deepnote test launched heavy NUTS training, changed live ranks, or called sportsbook APIs.

## Live afternoon dry-run receipts

### Earlier archived run: `20261109T234719Z`

Source GitHub SHA `10404038846f9f621c245ca089daf91b974ddde9`; 1,568 forecast rows in 12 games; 1,220 rows passed the then-current *metadata/byte* check; 348 rejected with `market_unavailable_or_unverified`. The market capture took 2,122 raw quote rows, accepted 1,174, and excluded 948 with `market_update_unverified_or_future`. Original forecast bytes SHA-256: `5e4cdb130b7a550aad483397c3aeab554eb5ecbc2638455f49564f79d89123c9`. Archive complete false, `publication_eligible:false`, Tier 1/2 disabled.

The model comparison checked 784 paired contracts and rejected six, all in NHL goalie-saves NUTS shadow.

### Newly executed read-write Deepnote run: `20261110T001047Z`

Deepnote notebook `932674d66d4543c6b10ff2e2c0a4df9c`; run UUID `b0e0c757-594b-44cc-b683-25d0225b0c27`; **completed successfully at the Deepnote notebook level**, but `all_stages_succeeded:false` because an optional `nfl_provisional_nuts_shadow` artifact download returned HTTP 415. Main archive published to `data/live-observations`. The execution fetched source SHA **`1799074428a0c74016042bae122f00527c953be0`** (PR #86 only), so **it does not test the merged PR #87 and PR #88 fixes**.

- 1,056 forecast rows spanning nine remaining games, 860 row-level accepted, 196 rejected (`market_unavailable_or_unverified`), with `source_archive_complete:false`.
- Original frozen forecast SHA-256 `46c66175bbdb4e896c1a06acdb940fa14098571785b03a65298e025575a89e8d`; latest run identity `1ac16b03-5488-50b2-9761-e1332f740884`.
- Market archive: 2,165 incoming quote rows, 1,248 accepted, 699 excluded as `event_already_started`, 218 excluded for `market_update_unverified_or_future`. This started after some events had begun; shrinking coverage is not a model-performance measurement.
- Paired-integrity report still rejected 6 of 528 complete Over/Under contract pairs because this run used code prior to PR #87.
- All core fetch, scoring, Phase0 source-provenance, comparisons and shared-archive publication stages succeeded; provisional NFL NUTS research artifact download failed HTTP 415 and remains unavailable. No training resumed or auto-promotions occurred.
- Run status: `uncertified_research_only`, `publication_eligible:false`, `tier1_tier2_publication_allowed:false`.

## Phase 0R checklist at this receipt

| Ticket | State | Evidence / remaining work |
| --- | --- | --- |
| P0R-01 repo & runtime reconciliation | Substantially complete | Main, CI, Deepnote run, training pause verified; do not assume Dell runner state |
| P0R-02 event/player identity | Existing fixes confirmed, no new retroactive repairs | PR #81/#83 and event-ID, numeric NHL player-ID tests; live matched contracts need fresh final audit |
| P0R-03 input freeze | Code repaired + tests passed | PR #86/#88; **actual model-input pre-evaluation pinning remains unresolved** |
| P0R-04 training cutoff | Mandatory timestamp validated | Needs every model artifact's real fitting cutoff, not an unsupported generic effective cutoff |
| P0R-05 original source receipts | SHA-256 archival gates live | 196 latest-run market exclusions; no guessing upstream publication or market availability |
| P0R-06 integrity/idempotency | Tests passed | Six NHL NUTS paired contracts isolated; PR #87 code fix not yet verified prospectively |
| P0R-07 live pregame certification | Incomplete | Late Nov 9 dry-run not complete end-to-end after all three fixes; next genuinely pregame slate required |
| P0R-08 independent adversarial signoff | Code-level QA done | End-to-end current-source lineage and genuine pregame publication gate remain open |

## Mandatory next actions

1. Build a *true pre-evaluation input snapshot* for every actual numerical model dependency, with immutable bytes/manifest bound to the model evaluation. Do not merely copy an after-the-fact receipt. Mark outputs without this lineage research-only.
2. Run the complete merged `main` pipeline before a future slate starts. Verify exact source SHA, market quote observed time and event ID; preserve full attempt/rejection and quote-exclusion ledgers. Never backfill an unarchived earlier game.
3. Require zero source/identity/clock integrity violations among certified rows, with a reason and disposition for every excluded forecast. Market absence may remain an honest abstention.
4. Reverify paired NHL goalie saves Over/Under under PR #87: complementarity at 1e-8 tolerance, with matching seed provenance; no silent normalization.
5. Resolve or cleanly quarantine optional HTTP 415 provisional NFL NUTS shadow failure; do not let it silently pass or become a ranking model.
6. Re-run independent adversarial QA on the same immutable forecast batch, validate publication guard and all source-byte digests, then **separately** authorize any future high-confidence tier or model promotion only after the V2.5 prospective calibration gates.

**No release authorization is granted by this receipt.**
