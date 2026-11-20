# Genuine prospective S1 execution and corrected offline replay

The public actual-clock execution produced56 statistic laws for14 players, plus
84 abstentions, over all35 players x4 primitive statistics. Target ESPN401910026,
MEM–MIN, starts2026-11-22T01:00UTC: November21,8pmAmerica/Toronto. Forecast time
2026-11-20T01:41:35.539742UTC is November19,8:41:35pmToronto,47h18m24.460258s
before the scheduled event. Points, rebounds, assists and made threes each have
14 genuine native S1 laws. They condition on participation and fixed projected
ordinary M0 exposure. They are UNCERTIFIED/SHADOW, without participation or
legal-eligibility probabilities, predictive validation, joint integration or
production/Tier approval. FORECASTS.csv has every one of140 attempts; forecast.json
contains the complete PMFs and all source/minute/abstention ledgers.

## Exact implementation and evidence commits

* Accepted original G0:59d28dc23be97de2a6a82d22be8338151e31f5b6.
* Verified prior dispatcher publication/base:a4493ac71bc03cb0afe0dc3a267230e82424d37c, PR189.
* Population frozen before implementation:178eafa99602e52f4807e96d307c4c3eecbea14a.
* Exact-source reader repair/test:6b0887848b16633b1c952446b9409bc13c574efc.
* Independent pre-fit decision:a1f1b07d59c1c79e075aaf5a7517542704eaa358.
* Actual native fitting implementation:2e2bab6220636ad93d1dd18a03daa0d323f31770.
* Independent real-artifact admission:f7d0c00558f2cd445e0ffac2896bef268f58641a.
* Actual public forecast implementation:76201b7795b718005d82b6443c2ea614e9824310.
* First exact public-path tests:abf8c332cf4423d2742047bd02238c9ae91bfebb.
* Corrected archive implementation:30b506f3d5c72af50f0624cf1a52f6e86e52a126.
* Corrected-archive candidate, including immutable fixtures:eda90d77d4cd3c415701a95b5f186e56bc585183.

The original source parser's schema failure, source collector failure, independent
intervening-game/archive counterexamples, pre-repair archive and interrupted old
full-suite run are preserved. corrected_archive/ packages the unchanged original
forecast with repaired verification; archive_repair_execution/stdout records its
actual later operation. It is not a new forecast or replacement model.

## Denominators and boundaries

60 actual HTTP 200 captures bind20 unique completed games,532 printed player rows
and166 separate inactive identities:698 source observations. Every observation has
four statistic attempts:2,792 = 1,824 included + 968 excluded,456 usable rows per stat.
458 rows print ordinary exposures; two fail the frozen full-vector/name join.
68 printed DNP,1 sub30 and 5 unknown exposures remain separate; inactive identities
are not zero-minute training records. All source and integer-credit accounting
is retained. No zero/sub30 display exception is admitted. See
COMPLETENESS_LEDGER.json and the full fitted/source_dataset.json.

35 current source-listed candidates=27 source-ready + 8 source abstentions.
Final140 attempts=56 forecasts+32source abstentions+20 insufficient-history
abstentions+32 unknown-history-window abstentions. M0 keeps350 dated player-game
observations. Source capture is contemporaneous before this future target;
historical result capture is not original historical pregame availability.
The legal roster, genuine participation probabilities, source publication times,
complete correction history and later membership changes remain unknown.
Individual mm:ss is reported-second precision; duration uses final periods,
zero final clock and the fixed12 minute / 5 minute NBA timing rule. Minute-sum
residuals are retained and never normalized; faulty bench aggregates are
quarantined. Provider position bins are metadata observed at capture.

## Reproduce without a live source or refitting saved artifacts

Run from a clean isolated checkout containing eda90d77d4cd3c415701a95b5f186e56bc585183
or a later evidence-only publication with the same reader bytes. The externally
reviewed checkout is required: an archive cannot appoint its own executable
verification authority. The archived child runs isolated with -I -B and only
archived inputs. The public replay verifies exact code/source/model/output
bytes and deterministic native reconstruction; it issues no new forecast.

```bash
python3.12 -m venv /tmp/pickem-genuine-s-replay-venv
/tmp/pickem-genuine-s-replay-venv/bin/python -m pip install -r requirements-nfl-inference.txt -r requirements-nba-research-tests.txt
/tmp/pickem-genuine-s-replay-venv/bin/python scripts/nba_genuine_s.py replay-archive docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive --expected-manifest-sha256 934671c7c8ab61293a0c9eadad6d8456d3615f03cdfc558933bf9fe7854a327f
/tmp/pickem-genuine-s-replay-venv/bin/python -m pytest -v tests/nba_architecture/test_prospective_s_sources_v1.py tests/nba_architecture/test_genuine_prospective_s_v1.py
/tmp/pickem-genuine-s-replay-venv/bin/python -m unittest discover -s tests -q
```

From this packet directory, verify the complete published evidence bytes with
`sha256sum --check --quiet SHA256SUMS`. An exit status of zero means every listed
file matched; this transport check does not grant source or model admission.

Expected public replay counts:35 candidates,140 attempts,56 forecasts,84 abstentions;
new_forecast_issued=false. ENVIRONMENT.json and pip-freeze.stdout record the
actual executable environment observed after execution. requirements-nba-research-tests.txt
pins the numeric/contract test versions; no sampler is installed or restarted.

The raw actual fit invocation, environment, clocks, stdout/stderr and implementation
SHA are in fit_execution/. The raw actual forecast command and clocks are in
forecast_execution/. Its live CLI assigns the actual clock and rejects an
existing destination; it cannot backdate issuance. Future live calls also must
respect the predeclared01:30..04:00UTC November20window. This is an exact frozen
cohort contract, not a general unattended all-slate source root. A different
population requires its own explicit source/cohort/model review and actual freeze.

public_attack_probe.py reconstructs nine synthetic negative overlays over the
immutable real source tree, calls the real CLI and retains all 140 rejected
attempts. public_attacks/ stores each exact overlay, argv, stdout/stderr and
result. These malicious clock/publication/correction/completeness claims are
negative controls, never genuine source observations. The original raw/ remains
unchanged. The runner is create-only and should be reproduced in a new isolated
worktree without an existing public_attacks/ directory.

## Hashes and byte domains

SHA256SUMS covers exact published file bytes relative to this packet directory,
excluding itself and bytecode caches. Raw bodies are HTTP_RESPONSE_BODY_BYTES;
receipts retain their original UTF8JSON bytes. Model artifacts, native source
manifests, UTF8raw-body maps and forecasts are exact saved bytes. Payload digests
hash sorted compact JSON with allow_nan=false, excluding only payload_sha256.
The cohort canonical hash is distinct from its pretty-printed file hash.

| Object | Domain | SHA256 |
|---|---|---|
| PREFIT_POPULATION.json | Exact raw specification bytes | 9b4ffaf085deeffe83cee50c6d3ecfc5dd2c41848cb849ee32240389cc7b2ed8 |
| Source reader | Exact Python source bytes | 8b61c753a41b59b9baad25ce179bd56ef3ceaf31645e76998b6408f296a447fd |
| Dataset | Exact canonical saved JSON including payload hash | a8230745eae80c0831ce36dc71d7fb41d9faeaef9e053f9844b8f70fb0e334a2 |
| Dataset payload | Canonical payload excluding payload_sha256 | e5cb76ef446d6651b718c6279367a7078ffa86f01b621cfbfd9c7b4d74adbd1d |
| Pre-fit decision | Exact independent JSON bytes | a76ce1e31d029edecc30b57d9ee7dd37941cb31fc697c5c01b0566c18b9fe558 |
| Artifact admission | Exact independent JSON bytes | 2e94902d767a74c74f102042ad27de3684560b22552c76b5bb4d4410b5275aea |
| Fit receipt | Exact saved JSON bytes | 20e924334578cf9cd60c5c8b7f9e8a2b9dafc3153a13fe671f4db54f14c3fb4e |
| Native source manifest | Exact canonical JSON bytes | 5269b9d38d383b965b2c88587ac7a69eee5c75dcc52e941a703076b76dc1b82b |
| Native body map | Exact canonical JSON bytes, values original UTF8HTTP bodies | 4c7124414905ef92d68d008023c7d1073437ae94dfc5400d8794ceca8de5ceb0 |
| Points artifact | Exact native FittedS payload | a8b2e1e4cad5f2c46dfc902913d9186e99d1b997190fdaef8691c997acef2da2 |
| Rebounds artifact | Exact native FittedS payload | b0f5f9fc0dbc3a330cd17b257e1278759f0a57c78ddd6ece2ee64f2c1e7bea6e |
| Assists artifact | Exact native FittedS payload | f8cea715972a36be0d3dd32c255084587397f2d4a8954864b873928c8225afb7 |
| Threes artifact | Exact native FittedS payload | ebbfe7836f2f160550bc5cd5b7ae1731aaa3c305149254a8fb6ca174b49331dc |
| Cohort file | Exact pretty JSON bytes | b77c3a2173f6094bcc2399a1fdca54662f23fac1a78d6ed17186cd8346d09c7b |
| Cohort canonical | Sorted compact JSON bytes | ae05fcd2705084efcd1200a0535959318c47b40ec59cd847ef499acf24a80539 |
| Original/unchanged forecast | Exact saved forecast JSON bytes | 6ebe7eb039c01a963663ec5253a46ec4e9a87379f59adac47087338e9c119f8d |
| Forecast payload | Canonical payload excluding payload_sha256 | d416d25ae69ff390c760537e9615f24a3e86e80b1c7d6d18047fa38a1e0b659f |
| Original archive manifest, preserved red | Exact original manifest bytes | 9eadc31814e66123259758ac9717b826ec45935cfa70d06d58bd339a1fdf9396 |
| Corrected archive manifest | Exact corrected manifest bytes | 934671c7c8ab61293a0c9eadad6d8456d3615f03cdfc558933bf9fe7854a327f |

PRESERVATION.json verifies all 20 prior accepted reader/configuration bytes against
a4493ac71bc03cb0afe0dc3a267230e82424d37c. All original red receipts, G0, frozen
forecasts/models/comparison outputs/posteriors and source/correction records
remain preserved. No schedules, merges, deployment or Tier settings change.
