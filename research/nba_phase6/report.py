"""Render the final evidence report without changing frozen experiment outputs."""
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from .run import load


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(str(c) for c in r)+' |' for r in rows])

def main():
    root=Path('research/nba_phase6');s=load(root/'results/summary.json');r=load(root/'results/run_receipt.json');v=load(root/'validation/ws4_artifact_validation.json')
    b=load(root/'validation/baseline_before_run_receipt.json');after=load(root/'validation/baseline_after_run_receipt.json')
    tests=load(root/'validation/test_receipt.json');pilot=load(root/'prospective_pilot/blocked_receipt.json');current=load(root/'results/current_roster_contract.json')
    gates=[['A — Source','BLOCKED-BY-DATA','Original 2024 game-day eligibility and publication clocks absent; current raw capture is membership/injury evidence, not complete game-active eligibility.'],
        ['B — Participation','PASSED','Uncertainty and abstention semantics pass; all unsupported probabilities remain null. No validated participation estimator or unconditional forecast is claimed.'],
        ['C — Opportunity','FAILED','Incumbent A regresses from raw M0 by 1.5643 CRPS on all 460. Complete-participant oracle repairs the aggregate diagnostic, but certified B is unavailable and low/early-exit reliability is unresolved.'],
        ['D — Statistical propagation','PASSED','Measured exposure-only interventions change all eight matched count distributions with byte-identical event parameters. This is diagnostic attribution, not prospective model acceptance.'],
        ['E — Prospective','BLOCKED-BY-DATA','Ten future slots over five dates preregistered; zero future game-day forecasts or settlements exist. Honest blocked-state receipts satisfy the reporting alternative, not a completed prospective study.'],
        ['F — Statistical adoption','BLOCKED-BY-DATA','Independent statistical review, adequate untouched clusters and certified prospective reliability are absent. Engineering success grants no adoption.']]
    (root/'GATES.json').write_text(json.dumps({'gates':[{'gate':g,'status':status,'reason':reason} for g,status,reason in gates],'promotion':False},indent=2,sort_keys=True)+'\n')
    stat_order=['points','rebounds','assists','threes','pr','pa','ra','pra']
    all_stats=table(['Statistic','J0','J1','A original J2','D raw M0, J2 events'],[[stat]+[f"{s['count_metrics'][arm][stat]['crps']:.6f}" for arm in ['J0','J1','A','D_RAW']] for stat in stat_order])
    common_stats=table(['Statistic','J0','J1','A','C POSTGAME ORACLE','D'],[[stat]+[f"{s['common_count_metrics'][arm][stat]['crps']:.6f}" for arm in ['J0','J1','A','C_ORACLE','D_RAW']] for stat in stat_order])
    def mins(common=False):
        metrics=s['common_minute_metrics'] if common else {k:v['all'] for k,v in s['minute_metrics'].items()}
        return table(['Arm','n','CRPS','MAE','Predicted mean','Observed mean','Predictive variance','50% cover','80% cover','90% cover'],
            [[arm,metrics[arm]['n']]+[f"{metrics[arm][k]:.6f}" for k in ['crps','absolute_error','predicted_mean','observed_mean','variance','cover50','cover80','cover90']] for arm in ['RAW_M0','A','C_ORACLE','D_RAW','E_POOL_24','E_POOL_48']])
    slices=table(['Arm','Slice','n','CRPS','90% cover'],[[arm,name,rows['n'],f"{rows['crps']:.6f}" if rows['n'] else 'unavailable',f"{rows['cover90']:.6f}" if rows['n'] else 'unavailable'] for arm in ['RAW_M0','A','C_ORACLE'] for name,rows in s['minute_metrics'][arm].items() if name!='all'])
    pilot_table=table(['Toronto date','ESPN game ID','Scheduled tipoff Toronto','Target freeze Toronto','State'],[[x['toronto_date'],x['game']['game_id'],datetime.fromisoformat(x['game']['event_start_at'].replace('Z','+00:00')).astimezone(ZoneInfo('America/Toronto')).strftime('%H:%M'),datetime.fromisoformat(x['scheduled_freeze_at']).astimezone(ZoneInfo('America/Toronto')).strftime('%H:%M'),'not yet due; source readiness blocked'] for x in pilot['slots']])
    text=f'''# NBA V2.5 Phase 6 — opportunity repair and source audit

November 15, 2026, America/Toronto. Governing PA-V25-MASTER-2026-11-09 / v1.1. Research-only; no production promotion.

**Decision: revise the opportunity interface and continue rejecting J2 for adoption.** The observed broad-roster allocation regression is substantially explained by the opportunity intervention. Better exposure propagates through the unchanged event mechanism. Authentic pregame eligibility/participation improvement remains unmeasured; this ticket does not establish a usable repaired pregame J2, market edge, or architectural sufficiency.

## 1. Root cause and experimental integrity

Frozen M0 minute laws estimate minutes conditional on an appearance. The original supplied roster is a union of prior appearances across ten team games, not a source-certified game-day participant list. In conditional research mode every nonexcluded candidate enters allocation; unknown participation stays null in metadata but is effectively conditioned into the supplied set. A Euclidean simplex projection then distributes 240+25×OT minutes across that broad set. The projection arithmetic is valid; the conditioned opportunity universe is wrong for the realized-appearance scoring target.

On the 460 original correctly team-matched appearances, raw M0 mean is 23.4631 versus 23.7109 observed. Allocation reduces the predicted mean to 17.9897, a -5.4733 minute allocation shift. Average predictive variance falls from 46.6140 to 40.5156, a -6.0984 shift. Minute CRPS worsens 4.061672→5.625994, approximately 38.5%. This is an estimand/participation-support error, not a reason to refit conversion rates or blame conservation arithmetic alone.

A conditions the entire uncertain candidate union on participation. B must establish legal eligibility using genuine original clocks, while leaving actual entry uncertain. C alone may use realized participants, explicitly postgame. D removes projection while preserving the J2 event mechanism. E holds unknown opportunity in an aggregate pool instead of inventing identities. Eligibility, availability, participation and conditional exposure remain distinct throughout.

The first C attempt correctly failed with only four supported Detroit participants in game 401704629. The next implementation still allocated 240 minutes to incomplete realized sets. That silently transferred missing players' opportunity to supported players despite a feasible witness. It was caught and quarantined. Final C requires **complete** frozen M0 support for every actual player/team participant: seven games, 141 appearances. Seventeen games / 319 original matched appearances abstain. The preliminary 447-row oracle results are **superseded, unsafe and excluded from all final conclusions**; their bytes remain in `quarantined_incomplete_oracle/`. The initial four-player failure remains in `initial_infeasible_oracle/`. `INTEGRITY_AMENDMENT.md` explains both discoveries. No parameter was tuned in response.

The user directive authorizes this bounded NBA ticket despite older general later-phase deferrals. Its “Phase 6” label does not authorize the master plan's production decision layer. The protocol was committed at `081d2fb64` (resolve the full SHA with Git; full receipt accompanies publication) before any new-arm scoring. The scientific implementation run pins `{r['head']}` and exact file hashes. Existing 24 dates were already development-exposed. No hidden evaluation outcomes were consulted and no model selection, refit or reserve optimization occurred.

## 2. Frozen baseline, before and after changes

Pinned parent: `cdf926f56e86bc9d25576acff61fd6f091313159` (PR #140, still open draft at inspection). Main: `912bc7010058092ea735dcda0aa941429194474b`. Warehouse: `97a8bb566826afe5a3e5a7b8c632043d8a1dca24`.

The untouched replay restored exact warehouse and official source bytes and reproduced **all 145 configuration hashes and exact final results bytes**. After the optional diagnostic hook, the full original replay reproduced all 145 again. No discrepancy was accepted. The 24 A-arm game reruns also match original output hashes exactly.

{table(['Checkpoint','Reproduced'],[[k,f'{value:.9f}' if isinstance(value,float) else value] for k,value in s['baseline_checks'].items()])}

Original 24-date/24-game cohort: October 22–November 15, 2024; 460 matched appearances and 236 players. The separate original November 10, 2026 five-game cohort is reproduced as part of the baseline, but no new Phase 6 claim pools it into this development experiment. Original J0/J1/J2 remain named controls; production 60/40 is never replaced with them.

## 3. Source infrastructure audit and interface

The connected GitHub account and Deepnote project were reachable. Deepnote `9cc31536-93be-44db-bdeb-06fba3f61410`, “Pick'em Auditor — Daily Cloud Inference”, had 464 notebooks, 10,774 inventoried files and the existing Secrets environment integration at inspection. The original NBA WS1 and WS5 notebooks and their code were inspected; no original block or schedule was edited. Existing morning settlement is enabled, afternoon slate disabled; existing NHL research automations remain enabled and unchanged. No NBA scheduled collector or new production automation was created. GitHub workflow sources contain manual dispatches and no active cron definitions; latest inspected runs were completed offline checks. Training pause remains true.

| Information | Existing evidence and measured limitation | Consumer treatment |
|---|---|---|
| Scheduled games | Existing ESPN scoreboard, retained source bytes; pilot IDs resolve for all ten slots. Official NBA CDN schedule probe returned HTTP 403. | Preserve provider namespace and exact capture clock; independent league completeness remains open. |
| Player identity and season membership | Existing WS1 team-roster adapter yields stable ESPN IDs and `membership_only / reported`. | Identity is retained; membership never becomes legal game eligibility or P(appearance)=1. |
| Game-active eligibility / inactive list | No complete original historical game-active roster handoff located. Six currently captured players have reported inactive availability, not complete eligibility certification. | Historical unknown inactive count stays null; B abstains. |
| Official injury status | Existing ESPN injury adapter retains status/detail/reported time. NBA official injury index and 16:00 ET PDF were retrieved with original receipt hashes. | NBA PDF names lack stable source-bound ESPN identity mapping; no fuzzy joins, inferred health, or numeric effects. PDF availability is not a complete legal roster. |
| Starting lineups | Historical starter flags exist; no current complete official starting-role announcement adapter was found. | Historical starts are prior evidence only; current starting evidence remains absent. |
| Transactions / roster changes | Prior source rows preserve team changes. NBA transactions page HTTP 200 is a JavaScript page shell with no transaction records in embedded page content. | No inferred trade, effective timestamp or identity repair. |
| Two-way assignments and recalls | No source-bound dated complete game-day adapter located in WS1, existing context or population infrastructure. | Explicit missing coverage; no assumed eligibility. |
| Substitutions | Historical minutes/starter box fields, not event-time stints or historical substitution coverage. | Constructed lineup witnesses prove arithmetic only; not observed substitutions. |
| Publication / retrieval chronology | ESPN injury item report dates where present, actual response capture clocks and receipt hashes. Roster publication timestamps unavailable. | Null publication time is preserved; retrieval does not backdate historical knowledge. |
| Complete candidate coverage | 778 prior-supported candidates in the historical experiment; current capture 37 season members; no full game-active reconciliation. | Both candidate coverage and all abstentions are reported. |

New interface: `research/nba_phase6/roster.py`, `NBAGameDayRoster/1.0.0`. It deserializes WS1 strictly, replays original source bytes through unchanged WS1 adapters, verifies the snapshot content hash, validates source/model clocks and age policy, retains source/receipt/raw hashes, stable game/player/team identities, source publication where supplied, retrieval and freeze times, eligibility and availability evidence, role evidence, missingness, and all rejected/upstream candidates. Its six-hour freshness bound is an explicit conservative engineering policy, not proof of source truth. A hash verifies content, not an independently signed timestamp or factual truth. No validated participation methods exist in the pinned handoff; supplied numeric participation evidence is rejected rather than accepted from an arbitrary hashed probability document. This adapter cannot grant a ready forecast.

The retained PR #140 canary rebuilds exactly: 36 candidates, 36 unknown eligibility, 36 abstentions. A fresh **one-shot existing WS1 capture**, separate from the preregistered pilot, froze Warriors–Clippers ESPN `401909987` at 16:09:45.619693 Toronto, before 16:30 tipoff: **37 candidates, six reported inactive, 37 eligibility unknown, zero supported participation probabilities, zero accepted forecasts, 37 abstentions**. Its snapshot content hash is `{current['snapshot_content_hash']}`. No Lakers–Suns forecast was backfilled after its start. All original capture sources remain available under `current_source_probe/` and `official_source_probe/`.

## 4. Five-way opportunity ablation and full denominators

{table(['Arm','Execution','Coverage/interpretation'],[
['A','24 games / 460 matched','Exact original broad-roster conditional J2; research-only'],
['B','0 source-qualified forecasts','778 accepted prior candidates abstain; 122 original candidate rejects remain separate; no historical eligibility invented'],
['C','7 complete games / 141 matched','POSTGAME APPEARANCE ORACLE ONLY; 17 games / 319 matched rows abstain for missing actual participant laws'],
['D','24 games / 460 matched','Original raw M0 arrays, unchanged J2 event allocation/conversion; fails valid-rotation conservation by design'],
['E','24-game partial-minute sensitivity','Fixed 24/48 unresolved player-minutes per regulation, scaled by shared OT. Full lineup/event/prop forecasts abstain. No fictitious IDs or rate vectors']])}

The **primary source-qualified pregame cohort is zero**; none of the following is a certified pregame comparison. A/D use all 460 original matched appearances. Every C comparison also reports A/D/J0/J1 on C's exact 141-appearance intersection; restrictive C coverage cannot masquerade as a full-cohort improvement.

{table(['Denominator','Count'],[[k,value] for k,value in s['denominators'].items() if k not in ('warning','known_inactive_status')])}

There are 926 distinct player/team/game keys across attempted candidates plus missed actuals. This is not the sum of stage-row counts: rejected and missed-appearance ledgers overlap. Original attempts reconcile as 900 = 778 prior-supported + 122 rejected. Player-identity absence is 317; one extra wrong-team appearance gives 318 without a correct player/team match. Of the latter, 87 are explicit postgame DNP records and 231 lack an explicit DNP flag, including the identity mismatch. None becomes a known pregame inactive. Observed 512 = 460 matched + 52 unforecasted appearances. All rows and reasons remain in `candidate_ledger.json.gz`, `source_B_abstentions.json`, `C_oracle_abstentions.json` and the original denominator ledger.

## 5. Minute accuracy, calibration and opportunity conservation

All supported rows per arm; the C row has reduced support and is not directly interchangeable with full 460-row arms:

{mins()}

Identical **141-appearance / seven-game** intersection for every row below:

{mins(True)}

C improves CRPS 5.032022→3.604393 and mean minutes 19.2974→23.9461 versus 24.2128 observed on that exact cohort. It beats the identical raw M0 CRPS 3.867469 descriptively, but seven exposed dates do not justify adoption. Raw/allocation mean and variance shifts remain available for every scored player in `minute_scores.json.gz`; candidate-level means include nonappearances.

Stress diagnostics, with outcome-conditioned slices explicitly labeled:

{slices}

Low realized minutes remain a material limitation: A 90% coverage is 91.9% for its 37 low-minute outcomes, while raw M0 is 59.5%; C must be assessed on its own exact low-minute intersection, not against the full 37. The sole early-exit proxy is outside the complete C cohort, so C cannot claim to repair it. OT uses the same original shared duration and source period outcome; C includes 19 observed-OT appearances with 94.7% 90% coverage; that is one small outcome-conditioned diagnostic, not a learned OT improvement. These are descriptive slices, not unconditional nominal-coverage tests.

A/C preserve exact 240+25×OT conservation and source-frozen shared duration. Valid five-player witnesses pass unchanged WS2 and WS4 checks. D fails the unchanged rotation audit in all 24 games and exports no normal forecast. E known-player minutes plus explicit pool conserve, but the pool has no identity or feasible full witness: event generation abstains. Reserving 24/48 additional minutes from the already bloated broad roster worsens full-460 minute CRPS to 6.5022/7.6117. Those fixed sensitivity arms cannot be promoted or interpreted as estimated unknown participation. There is no unidentified credit to known players in final C or E.

## 6. Player-stat propagation with unchanged event model

All 460 matched appearances for A/D and controls; lower count CRPS is better:

{all_stats}

Exact 141-appearance complete-C intersection for **all** arms and controls:

{common_stats}

Complete-C point estimates improve every listed statistic against A and J0 on these seven exposed games. D improves all eight versus A on the full 460; D points 3.625042 is below J0 3.707883, but D rebounds 1.471599 remains above J0 1.416223, and assists/threes/RA retain smaller regressions. D is not a valid full rotation and still conditions the broad candidate set; its residuals do not uniquely identify a pure event-architecture defect.

No event probability, conversion rate, pooled prior, event likelihood, M0 coefficient, state covariance or OT law changed. The optional simulator hook supplies already frozen exposure arrays only in historical/synthetic conditional research; default hashes are unchanged. C and D both call the existing J2 event generator with constrained team shot pools, conversions, rebound pools and scorer-linked assists. D is **not** the old J1 arm, which also changes event allocation. Original controls remain separate.

Common random numbers use original A raw M0 arrays and identical scenario-keyed state/event streams. Multinomial weights and tie-rejection attempts can alter RNG consumption, so exact event-variate coupling is not claimed. All eight statistics retain means, variances, 50/80/90 coverage, zero/tail residuals and empirical log-score support failures in `summary.json` and full score rows. Finite 128-draw count ensembles can assign zero mass to observed outcomes; no smoothing floor or finite-subset NLPD is presented as a proper matched full log-score result.

Unchanged WS4 independently coded CDF scoring agrees on all **{v['count_crps_checks']:,}** evaluated count distributions with maximum CRPS difference **0**. Its 1,000-resample date/game cluster intervals are in `validation/ws4_artifact_validation.json`. For C−A points on the seven common dates, mean ΔCRPS is -0.352392; the WS4 date interval is [-0.625528,-0.114205]. These are development-exposed, unadjusted descriptive intervals with only seven clusters, not confirmatory superiority or attainable pregame gain. Repeated players and simultaneous markets further limit inference.

## 7. Prospective pilot: preregistered, currently blocked

Ten actual scheduled game IDs were frozen across November 16–20, 2026 using five original schedule responses. First two scheduled events by (start, ID) on each Toronto date; target freeze 30 minutes before start. Selection does not inspect outcomes.

{pilot_table}

The advance readiness receipt records each future slot as not yet due, with null candidate universe rather than fabricated zero-player rosters; eligibility, validated participation and future official settlements are unavailable. **Zero future game-day attempts, zero forecasts, zero settled games** are claimed. The current November 15 probe is separate and is not counted toward ten future games. No job is scheduled to run later by this ticket. Continue through the existing WS1 manual capture path; every new capture and actual forecast needs its own original clocks, source/model manifests, candidates and abstentions. A missed freeze must remain missed; no backfill. Independent official settlements must be captured after FINAL. Original market contracts remain unavailable, so future distribution scoring alone cannot be called market performance. Ten games are a mechanism/feasibility pilot, never adoption-grade sample size.

## 8. Adversarial verification and independent review status

**{tests['total_passed']} targeted tests pass**, zero failures/errors/skips in the final suites: 179 original methods plus 26 new methods. Initial failing-hook tests and intermediate failure logs are retained, not counted as passes. New checks attack unsupported probability one, stale evidence, future model and injury clocks, raw-source tampering, changed/rehashed player/team identity, incomplete actual-player support even with five feasible known players, four-player rotations, inactive exposure, false oracle export, raw minute mutation, illegal shapes/caps/NaN, OT conservation, anonymous-pool credit, and real-metric oracle contamination. Existing WS1 mutation tests cover conflicting corrections, future/postfreeze roster records and historical publication gaps. No historical outcomes are used for tuning; the fixed protocol and unchanged model hashes enforce the boundary. A valid C result cannot close B source certification.

The separate artifact pass validates **{v['scenario_boundary_checks']:,}** A/C constrained scenario boundaries and **{v['event_scenarios_checked']:,}** A/C/D event scenarios; every D game fails the unchanged rotation-conservation audit as expected. Full source/model/output hashes, pool residual reconciliation, export guards and original baseline equality pass. Test reports and exact logs are in `validation/`.

This is author-run validation using unchanged WS4 #139 code, **not independent statistical signoff**. No separate external reviewer has approved the revised source semantics or adoption. Deepnote's original WS1/WS5 notebooks were inspected; no claim of a new Deepnote execution or an independent human/agent review is made.

## 9. Gates, compute, exact hashes and rollback

{table(['Gate','Status','Evidence/limit'],gates)}

{table(['Execution','CPU seconds','Wall seconds','Peak process RSS MiB'],[
['Untouched full 145-config baseline',f"{b['cpu_seconds']:.3f}",f"{b['wall_seconds']:.3f}",f"{b['peak_rss_mib']:.3f}"],
['Final Phase 6: 55 game/arm configs + pool sensitivity',f"{r['cpu_seconds']:.3f}",f"{r['wall_seconds']:.3f}",f"{r['peak_rss_mib']:.3f}"],
['Post-change full 145-config baseline',f"{after['cpu_seconds']:.3f}",f"{after['wall_seconds']:.3f}",f"{after['peak_rss_mib']:.3f}"]])}

CPU is process CPU; peak RSS covers the whole experiment process, not incremental game memory. The final arm set is smaller than the original 145-config baseline; these timings are not a speedup comparison at equal workload. Source HTTP time and separate validation processes are not falsely included in the simulation CPU figure. NumPy 2.3.5 / SciPy 1.17.0 match the original local pins. No NUTS, GPU, paid service or model refit was started.

Model canonical SHA-256: `{r['model_sha256']}`.
Event-parameter SHA-256: `{r['events_sha256']}`.
M0 artifact canonical SHA-256: `{r['minutes_model_sha256']}`.
Protocol file SHA-256: `{r['protocol_sha256']}`.
Original requested-source file hashes: `validation/protected_boundaries.json`; original upstream input/source manifests remain untouched. Final full scenario/input/output hashes and timing receipts: `results/run_receipt.json` and `results/scenario_hashes.json`. Publication/evidence manifests pin the final tree and exact per-file bytes separately to avoid self-referential hashes. Raw PDF/source/receipt hashes are preserved beside each captured source. File-byte hashes differ from canonical-object hashes by documented domains.

Protected `.github`, `.training-control`, `config`, `scripts`, WS1, frozen WS2/M0, event/state/allocation mechanisms and every original `research/nba_joint_v01` artifact are byte-unchanged against the pinned parent. The only engine edits are an opt-in historical/synthetic exposure-injection boundary and rejection of diagnostic normal-forecast export. No settlement archive, current production importer, 60/40 weights, Tier rule or original automation changed.

Draft PR is separate and stacked on PR #140's branch; no upstream draft is merged. Exact final PR URL/head are in the publication receipt. Rollback before merge: close the Phase 6 draft and stop invoking `research.nba_phase6`; retain every original and quarantined receipt. If later merged as research, revert only Phase 6 commits to parent `cdf926f56e86bc9d25576acff61fd6f091313159`, after pinning any opt-in research consumers back. There is no deployed migration or scheduler to reverse.

## 10. Statistical recommendation and next bounded investigation

**Retain M0 and the original controls; continue rejecting J2 adoption.** The strongest supported mechanism finding is that conditioning a broad prior-roster union on participation and then enforcing team minutes is a major source of the measured J2 regression. The full-460 raw-minute intervention and seven complete participant-oracle games show that changing exposure alone materially changes player-stat quality. The experiment does not require refitting or redesigning the event generator to obtain those gains.

This does not prove all markets are solved or that a legal eligible roster predicts appearances. Low-minute and early-exit tails, incomplete candidate coverage, game-active source clocks and probabilistic participation remain open. An authenticated eligible-roster improvement has **not** been measured because B is blocked; it would be false to claim either that roster certification fixed J2 or that authenticated roster repair failed. The event architecture remains unapproved rather than demonstrated universally inadequate. Complete original prospective eligibility and participation support first. If that genuinely source-backed opportunity repair fails to materially improve matched J2 distributions, preserve the failure and move the next bounded investigation to the conditional event model, with rebound/assist/zero-tail diagnostics prioritized by prespecified matched evidence. Do not escalate model complexity from this engineering repair.
'''
    text=text.replace('`081d2fb64` (resolve the full SHA with Git; full receipt accompanies publication)','`'+__import__('subprocess').check_output(['git','rev-parse','081d2fb'],text=True).strip()+'`')
    (root/'REPORT.md').write_text(text)

if __name__=='__main__':main()
