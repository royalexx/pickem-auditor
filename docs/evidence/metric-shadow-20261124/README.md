# NBA points and NHL SOG metric shadow comparison

The approved work is a two-slate prospective, research-only count comparison conditional on played appearances. The real pregame freeze was 2026-11-24 15:06:23.012981 UTC, before the Nov 25 NHL and Nov 27 NBA slate. It uses prior regular-season spines through Nov 23, and only historical player-team proxy eligibility. Existing production controls and forecast schedules are preserved.

- NHL SOG compares the fixed baseline with 5v5 individual unblocked attempts per 60. Fourteen scheduled games, 556 frozen play-conditional forecasts, and 57 exclusions for insufficient baseline or advanced history.
- NBA points compares the same kind of baseline separately with actual eFG% and with TS%. Eleven scheduled games, 307 frozen play-conditional forecasts, and 27 exclusions for insufficient baseline or advanced history.
- The freeze seals one Poisson mean per model per exact league event and player. Count CRPS is primary and negative log score is secondary. Score every matched positive-participation official row. Preserve unavailable source, absent player, and identity-mismatch rows. Single-slate game-cluster intervals are descriptive.
- This checkout retains the early frozen artifact and the model coefficients and historical receipt. All 11 source byte objects were also read back locally in the user's shared workspace against the publisher listing digests. The official finals are acquired separately after the games and checked against exact identities and original pregame chronology. Never overwrite the pregame artifact.

Pregame SHA-256 `0113325f00f9c4597a6ffcd13750fc54cdff3fcc15ffe57082aa115ebbc32c21`. Coefficient and historical recheck SHA-256 `3bc0766354cef373c01cdfa5f866af363586d2ac4763470963afc3c8d950a211`.

Run at the verified repository root after the official finals are available. Use a distinct output directory for each read and retry.

```sh
python scripts/score_metric_shadow.py --sport NHL \
  --pregame docs/evidence/metric-shadow-20261124/pregame-shadow-20261125-27.json \
  --sha256 0113325f00f9c4597a6ffcd13750fc54cdff3fcc15ffe57082aa115ebbc32c21 \
  --out /work/reports/v25_metric_shadow_20261124/nhl-nov25-final
```

For NBA use `--sport NBA` and a distinct `nba-nov27-final` destination. The shell runtime verified 16 numerical Poisson CRPS cases, one original final-box integration with a missing-player denominator, and rejection of a false forecast digest. A negative or inconclusive one-slate outcome remains part of the research record.

## 2025–26 replay and NBA distribution addition

The independent chronological season extension reuses the frozen control, NHL iFF, NBA eFG and NBA TS coefficients. NBA compound and NB2 calibration was fitted on 2021–22 and 2022–23 and reused without refitting. Each rate uses strictly earlier dated inputs, then the replay reveals the whole date only after freezing it. The NBA schedule crosswalk admitted 1,230 official standard regular-season games and excluded four ESPN-flagged All-Star games and the Cup championship. NHL admitted 1,312 official regular-season games. Report ungraded appearances separately. This is retrospective and uses revised archived inputs.

| 2025–26 comparison | Delta count CRPS | Improved months |
|---|---:|---:|
| NHL iFF vs regular count baseline | −0.001506 | 6 of 7 |
| NBA eFG vs regular count baseline | −0.013413 | 7 of 7 |
| NBA TS vs regular count baseline | −0.013155 | 7 of 7 |
| NBA compound at eFG mean vs eFG Poisson | −0.193381 | 7 of 7 |
| NBA NB2 at eFG mean vs eFG Poisson | −0.111259 | 7 of 7 |

The NBA companion was frozen at 2026-11-24 15:51:49.932665 UTC. It covers all 307 original NBA rows. It preserves the exact original eFG forecast mean for each row and tests two alternative distributions. The compound count draws made free throws, twos and threes separately. The negative binomial is a variance comparator. The original parent forecast packet and its forecasts remain immutable.

- [NBA distribution companion](nba-shadow-distribution-companion.json), SHA-256 `a6bd418cfa52f13c2302f636754d8b10d011d420e583bf6456a4f4d2fd057cb2`.
- [NBA 2025–26 results](nba-2025-26-results.json), SHA-256 `2ab20d8935a58f7eebec29f0c0f4e64b600509633eaa6eba6bc9ec9d07441c4c`.
- [NHL 2025–26 results](nhl-2025-26-results.json), SHA-256 `9a0fe9265d98d78f3c31021136940742352ba45ac2b46166cf684c6eae8ee01a`.

Score the companion with `scripts/score_nba_shadow_distribution.py` after the original NBA final report. Supply the companion and settlement hashes, the parent packet, and a new output path next to the original settlement report. The scorer revalidates the original NBA finals and the exact eFG means before scoring. It passed 16 negative-binomial numerical checks, an ESPN-format settlement integration fixture and rejection of tampered original bytes.

## November 24 early start

The user advanced the first prospective comparison to the November 24 slate. The separate base packet was frozen at 16:09:46.253006 UTC using completed-game inputs through November 23. The NBA distribution companion was frozen at 16:10:17.104046 UTC with the exact same eFG mean on every original row.

- NHL Vegas at Edmonton, 8:00 p.m. ET. 41 matched-model pregame candidates. Compare baseline and 5v5 iFF/60.
- NBA Detroit at Orlando at 7:00 p.m. ET, Boston at Washington at 8:00 p.m. ET, and Dallas at Denver at 10:00 p.m. ET. 79 matched-model pregame candidates and nine insufficient-history exclusions. Compare baseline, eFG% and TS%, plus compound and NB2 distributions at the same eFG mean for all 79 candidates.
- [November 24 parent packet](pregame-shadow-20261124.json), SHA-256 `b2039d4008c79ba089bd7476557096e69e210e5e81562b330b8bb710fd720e37`.
- [November 24 NBA companion](nba-shadow-distribution-companion-20261124.json), SHA-256 `0fa725fa4748184917a40fd85b96790a73ac774f13460e9855299c3ef3f5c487`.
- Separate official-final receipt scoring for both sports is scheduled for November 25 at 09:45 ET. These count comparisons are conditional on an official played appearance. The Nov 25 NHL and Nov 27 NBA packets already recorded above are separate future observations.
