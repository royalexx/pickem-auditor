# Stage G. Vetoes and soft flags

## What pipeline derives

`pipeline` takes optional context fields. `derive_vetoes_and_flags` applies the numeric cuts in this stage. Pass the number you cited. Do not count the result by hand. An omitted field does not fire its rule. The helper does not guess a missing minute, wind, or goalie.

Final `hard_veto` is the `--hard-veto` input OR any derived hard reason. Final `data_veto` is the `--data-veto` input OR any derived data reason. `--hard-veto` is for the vetoes these fields cannot see: items 1, 3, 4, 6, 7, and 8, and a defender who leaves on passing downs. Do not also pass `--hard-veto yes` for a cut the fields already carry.

`--soft-flags` is the qualitative count only. Do not count `THIN_WORKLOAD`, `SCRIPT_RISK`, `WEATHER_RISK`, `REST_SPOT`, or `UNCONFIRMED_GOALIE` manually. Pipeline adds `derived_soft_flags` to that count. Counting them again double-counts. Keep these qualitative flags manual: `QUESTIONABLE_PLAYER`, `QUESTIONABLE_TEAMMATE`, `QUESTIONABLE_OPPONENT`, `CONTEXT_AGAINST`, `SINGLE_SOURCE_LINEUP`, `PROJECTION_CONFLICT`, `LOW_HIT_RATE`, and `SOFT_HIT_RATE`.

Sport rules need `stat`. A workload field on the wrong stat does not fire. Cuts use the same float cushion as the grade gap: a value within 1e-9 of a listed cutoff stays on that cutoff. 18.0 minutes is not under 18.0. 9.5 is the spread veto, not `SCRIPT_RISK`. 18.0 mph is the wind veto, not `WEATHER_RISK`.

| Field | Use |
|---|---|
| `stat` | Covered market. Required before a sport rule fires. |
| `minutes_tonight` | NBA minutes. |
| `ice_time_tonight` | NHL ice time in minutes. 12:00 is 12.0. 17:29 is 17 + 29/60. |
| `snap_pct_tonight` | NFL snap share. A fraction from 0 to 1, or a percent when the number is above 1.5. |
| `route_pct_tonight` | Wide receiver or tight end route share, same scale as snaps. |
| `spread` | Signed team spread. Negative means the team is favored. Positive means the team is an underdog. NBA blowouts use the absolute spread. |
| `team_is_underdog` | `yes` or `no`. When `yes`, the underdog margin is the absolute spread. When omitted, only a positive spread is an underdog margin. `no` blocks the underdog rule. |
| `sustained_wind_mph` | Highest sustained wind in the Stage C3 window. |
| `gust_mph` | Highest gust in that window. Gusts do not fire the G5 veto. |
| `precip_prob` | Precipitation probability, a percent from 0 to 100, or a fraction from 0 to 1. |
| `precip_intensity` | `none`, `light`, `moderate`, or `heavy`. Missing intensity does not fire the snow veto or the rain flag. |
| `snow` | `yes` when that window forecasts snow. |
| `outdoor` | `yes` for an outdoor NFL or outdoor NHL game. A dome, or a roof confirmed closed, is `no`. |
| `is_starter` | `yes` when this NBA player is a starter. |
| `back_to_back` | `yes` on a back-to-back. |
| `third_in_four` | `yes` on a third game in four nights. |
| `goalie_confirmed` | `yes` when the goalie starter is confirmed. |
| `expected_starting_qb` | `yes` when this player is the expected starting quarterback. |
| `role` | `rb`, `wr`, `te`, `qb`, `g`, `d`, `f`, or `c`. Routes use `wr` or `te`. The rushing underdog rule uses `rb`. |

The JSON result includes `derived_vetoes` (`hard_veto_reasons` and `data_veto_reasons`) and `derived_soft_flags`. Hard reason codes are `NBA_MINUTES_UNDER_18`, `NHL_ICE_UNDER_12`, `NFL_SNAPS_UNDER_40`, `WR_TE_ROUTES_UNDER_50`, `TACKLES_SNAPS_UNDER_50`, `NOT_EXPECTED_STARTING_QB`, `SAVES_GOALIE_UNCONFIRMED`, `NBA_STARTER_SPREAD`, `NFL_RB_UNDERDOG_RUSH`, `SUSTAINED_WIND`, `SNOW`, and `OUTDOOR_NHL_RAIN`. The data reason is `WEATHER_NOT_CHECKED`. Text output prints hard reasons on `derived_vetoes` and data reasons on `derived_data_vetoes`.

## Hard vetoes

A hard veto stays Reject. Missing data stays Unranked. Items 1 through 8 are hard vetoes. The helper returns Reject when `--hard-veto` is yes or when a derived hard reason is present. Item 9 is missing data: pass `--data-veto yes`, or leave weather off an outdoor NFL or NHL stat, and the helper returns Unranked. Do not pass item 9 as `--hard-veto`. Any one of items 1 through 8 is Reject. Missing data is not a guessed grade.

1. **Model floor.** `probability_rank=REJECT` after a valid `grade`. That is a model P(win) below 52%, not a mean-versus-line test.
2. **Workload, Overs only, and only at these cutoffs.** NBA minutes under 18.0. NHL skater ice time under 12:00. NFL snaps under 40%, or wide receiver / tight end routes under 50%. Pass props when this player is not the expected starting quarterback. Tackles + assists when defensive snaps are under 50% or the defender leaves on passing downs. Saves when the goalie is not a confirmed starter. Minutes from 18.0 to 27.9, ice time from 12:00 to 17:29, snaps from 40% to 59%, and routes from 50% to 69% are `THIN_WORKLOAD`, not a veto. In the first three team games of a season, or a player's first game with a new team, use a cited workload projection instead of a current-season average. Zero games played is not, by itself, a veto when `--role-change` is justified. Pipeline derives the numeric cuts from `minutes_tonight`, `ice_time_tonight`, `snap_pct_tonight`, `route_pct_tonight`, `goalie_confirmed`, and `expected_starting_qb` on Overs. A defender who leaves on passing downs stays on `--hard-veto`. There is no field for that.
3. **Unders.** A low workload is not a veto. Reject an Under when a teammate absence forces a real usage increase tonight and you are still grading the reduced-role side.
4. **Cannibalization, Overs.** An active or returning teammate takes this specific stat.
5. **Script and weather, Overs.** NBA starter Overs when the spread is 9.5 or larger. NFL rushing Overs for a running back on a team that is an underdog of 6.5 or more. Passing yards, receiving yards, receptions, completions, and pass-attempt Overs when the Stage C3 sustained wind is 18 mph or higher. The same Overs are a hard veto when that window forecasts snow, the precipitation probability is at least 60%, and the forecast text says moderate or heavy. If the text does not give an intensity, do not apply this veto. NHL outdoor shots-on-goal Overs use the same 18 mph sustained-wind rule, and the same snow rule, and also rain during the game when the outdoor-NHL window shows rain. Gusts do not fire this veto. A spread from 8.0 up to but not including 9.5 is `SCRIPT_RISK`, not this veto. An underdog margin from 4.5 up to but not including 6.5 is `SCRIPT_RISK`. Sustained wind from 15.0 mph up to but not including 18.0 is `WEATHER_RISK`, including outdoor NHL shots-on-goal Overs. Pipeline derives this item from `spread`, `is_starter`, `team_is_underdog`, `role`, `sustained_wind_mph`, `gust_mph`, `snow`, `precip_prob`, `precip_intensity`, and `outdoor`.
6. **Context.** A cited AGAINST fact removes the opportunity the side needs. Examples: the rebound matchup depended on a center who is now active; the receiver matchup depended on a corner who is now active; a saves Over assumes an average opponent shot rate but this opponent is bottom-five in shots over the last 15 games; a tackles Over against a bottom-five rush-rate offense while this defender leaves in nickel; a new coach, quarterback, or goalie makes the old game log the wrong baseline and the new role points the other way.
7. **Opposed evidence.** Two or more independent projections are on the other side of the line, and the role-adjusted baseline is on the other side too.
8. **Banned markets.** The binary markets and the uncovered stats listed in Stage D.
9. **Data.** This is `--data-veto`, not a hard veto. Stale prices, an invalid consensus, no primary source for the player's status, opponent injuries not checked for that game, or weather not checked for an outdoor NFL or outdoor NHL game. The last two unrank every prop in that game, not just one player. The helper returns Unranked. When `outdoor` is yes and an NFL or NHL `stat` has none of `sustained_wind_mph`, `gust_mph`, `precip_prob`, `precip_intensity`, or `snow`, pipeline adds `WEATHER_NOT_CHECKED`.

A single public projection on the other side is `PROJECTION_CONFLICT`, not this veto. A low historical hit rate is a flag, not this veto.

## Qualitative soft flags

Count one per manual item that applies. Pass that count to `--soft-flags`. Do not count `THIN_WORKLOAD`, `SCRIPT_RISK`, `WEATHER_RISK`, `REST_SPOT`, or `UNCONFIRMED_GOALIE` manually. Pipeline adds those as `derived_soft_flags`.

- `DISAGREE` when consensus prints it.
- `MEAN_LINE_MISMATCH` when `project` prints `mean_supports_side=no`. When the shrunk mean equals the line, that is both the Over and the Under.
- `QUESTIONABLE_PLAYER`, `QUESTIONABLE_TEAMMATE`, `QUESTIONABLE_OPPONENT` when that person's status can change this stat.
- `UNCONFIRMED_GOALIE` on shots when the opposing or own starter is not confirmed. Saves with an unconfirmed starter are the hard veto above, not this flag. Pipeline derives this from `goalie_confirmed` on shots on goal. Do not count it manually in `--soft-flags`.
- `THIN_WORKLOAD` on an Over in the band named in veto 2: NBA minutes 18.0–27.9, NHL ice time 12:00–17:29, NFL snaps 40%–59%, or routes 50%–69%. Tackles snaps of 50%–79% are also this flag when the defender stays on the field. Pipeline derives this from the workload fields. Do not count it manually in `--soft-flags`.
- `SCRIPT_RISK` on NBA starter Overs when the spread is at least 8.0 and less than 9.5, or on a rushing Over for a back whose team is an underdog of at least 4.5 and less than 6.5. At 9.5 and at 6.5 the hard veto in G5 applies instead. Pipeline derives this from `spread`, `is_starter`, `team_is_underdog`, and `role`. Do not count it manually in `--soft-flags`.
- `WEATHER_RISK` on NFL passing-yard, receiving-yard, reception, completion, and pass-attempt Overs, and on outdoor NHL shots-on-goal Overs, when the Stage C3 sustained wind is at least 15.0 mph and less than 18.0 mph. Those NFL overs also take this flag for gusts of 25 mph or more, or rain with probability at least 60% and moderate or heavy intensity. Missing intensity does not fire the rain flag. At 18.0 mph the hard veto in G5 applies instead of the wind flag. Outdoor NHL rain and snow stay the hard veto in G5, not this flag. Pipeline derives this from `sustained_wind_mph`, `gust_mph`, `precip_prob`, `precip_intensity`, `snow`, and `outdoor`. Do not count it manually in `--soft-flags`.
- `CONTEXT_AGAINST`, one per distinct cited mechanism that is not already a hard veto.
- `REST_SPOT` on an Over in a back-to-back or a third game in four nights. Pipeline derives this from `back_to_back` and `third_in_four`. Do not count it manually in `--soft-flags`.
- `LOW_HIT_RATE` when the target side hit under 50% of the current-role games and `current_role_n` is at least 10. Count a 10–19 game sample. Do not wait for 20 games. Use the current-role games. A confirmed role change does not skip the flag once the new role has at least 10 games.
- `SOFT_HIT_RATE` when that same current-role hit rate is from 50% to 55% and `current_role_n` is at least 10.
- `SINGLE_SOURCE_LINEUP` when only one primary source confirms the role.
- `RETAIL_ONLY_TWO_BOOKS` when `consensus` prints it: the usable market is exactly two retail books and no sharp book. Three or more retail books do not print it. One sharp book does not print it. A sharp book plus any number of retail books does not print it. Count it when it is printed. Do not also invent a flag for a three-book retail market that agrees.
- `PLUS-MONEY` is printed by `consensus` on the sharp path and the agreeing-retail path when the chosen side is American plus-money or the pre-hold anchor probability is below 50%. The same prices note the same way. It is not a soft flag. Rank does not use it. Do not add it to `--soft-flags`. A model that still clears 56% against that price already takes `MODEL_MARKET_GAP` or the 8-point watchlist cap. The 52% floor already rejects a weak model.
- `PROJECTION_CONFLICT` when one independent projection is on the other side of the line.
- `VAR_RATIO_CLAMPED` when `project` prints that note. The variance ratio was above 3 and the probability uses 3.

`grade` adds `LOW_SAMPLE`, `NEW_ROLE_THIN`, and one `MODEL_MARKET_GAP` flag when those rules fire. Do not count those again in `--soft-flags`. Heavy snow is the hard veto in G5, not a soft flag. Heavy rain stays a soft flag.

Weather that supports a side (a pass Under, a rush-attempt Over, a tackles Over in a run-heavier script) is SUPPORT. It does not add probability by hand. Put it in the workload or pace inputs only when you have a cited rate.


## Fail-closed clarification

In the executable Stage G evaluator, a missing starter confirmation for a goalie-saves market yields `STARTING_GOALIE_UNCONFIRMED`; missing starter confirmation for an NFL passing-stat market yields `STARTING_QB_UNCONFIRMED`. An explicit negative becomes a hard veto. Both are evaluated on Over and Under because a market may be invalid/void for a non-starter. NFL weather-sensitive stats and outdoor NHL shots need confirmed venue status. If outdoor, one missing essential forecast field is a data veto, not an all-clear. Availability in `research_packet.py`: `out` is a hard veto; missing player status is a data veto.
