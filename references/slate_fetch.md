# Slate fetch

The personal ZIP includes `config/credentials.local.json`. The odds provider,
preflight and diagnostics load its `ODDS_API_KEY` automatically. A process environment
variable with the same name overrides the file; an explicitly empty value disables
odds access for offline work. The configuration is ignored by Git. Never echo its
contents or include it in research reports; remove it before sharing the project.

Current/prior player histories use at most four concurrent requests, with source
URLs merged deterministically; injected stateful clients can use `history_workers=1`
through the Python interface. NHL summary pages request the service's 100-row limit
so the first capped page is not mistaken for the whole league. Inspect the summary's
`coverage.by_sport`: raw `usable` is not proof of priced or complete data, and
`has_priced_history_rows` does not verify freshness or completed research. Gateway
failures remain missing observations; never substitute zeros. NFL current/prior
weekly rows are joined to their own season schedules for dates and game IDs, and
custom output directories keep the NFL season store beside the usage cache.

From the project repository root, install the feed packages once:

```bash
python3 -m pip install -r requirements.txt
```

Run `python3 scripts/fetch_slate.py --preflight` before Stage A. If it fails, report the failed feeds. You may research individual facts from current public pages, but cannot publish a priced or probability-ranked full slate without valid, current, two-sided reference prices. Label any manual prices clearly and recheck their match/age. If it passes, run `python3 scripts/fetch_slate.py`. It writes `data/slate_fetch.jsonl` in the skill directory and the sidecar `data/slate_fetch.meta.json`. One JSON object per player-stat. The file is structured numbers from public JSON or CSV. It is not a grade, not a probability, and not +EV. `scripts/pickem_math.py` is the only calculator. Do not recompute a probability from a fetched row. Tier floors, funnel-channel weights, vetoes, and the Underdog ban do not change.

The slate file is replaced only after a temp file is finished. If every feed returns zero rows, the fetch does not overwrite `--out`. It writes the summary to `<out>.failed.json` and exits 2. A feed that returns zero rows is `failed` in the summary. When at least one feed returns rows, those rows are kept and the process exits 0. The printed summary includes `usable` and `missing`.

Stage D is the market scan. Price every covered market you can find. Do not skip the rest of the board because a row is unflagged.

Web research complements (but does not replace) the full-slate price scan. Research the actual numeric Stage D shortlist AND explicit contextual triggers, including unflagged rows selected by the scanner. A flagged row whose `book`, `line`, `over_odds`, or `under_odds` is null still needs that price from Stage D. Do not web-search every unflagged player.

Feeds:

- NFL uses the PyPI package `nflreadpy` (`import nflreadpy as nfl`), the nflverse Python port of nflreadr. It returns Polars frames. Call `load_schedules`, `load_player_stats` at `summary_level="reg"` and `summary_level="week"`, `load_snap_counts`, and `load_team_stats` for the schedule, EPA, targets, receptions, rushes, yards, snap counts, the week game log, and team plays or pace. Do not download the nflverse CSVs by hand. If a live load fails, name that function and leave those NFL fields null. Do not invent rows. `snap_share` is the average of `offense_pct` or `defense_pct`. That is the share of snaps, not where the snap was taken. When `offense_snaps` or `defense_snaps` is on the snap file, the row stores `offense_snaps_per_game` or `defense_snaps_per_game`. Player stats and snap counts have no `routes` or `route_share` column. If a numeric `routes` or `route_share` column is present, the fetch stores `routes_per_game` or `route_share`. It does not invent one. `teammate_splits` is the player's rate in games a teammate played versus games that teammate missed, and only a split with at least 5 games on each side is listed. `baseline_mean` stays the mixed season rate. Null `teammate_splits` means the week log was missing. The fetch has no tonight number, so it stores no workload ratio. nflreadpy does not include each player's slot, wide, or inline share, so there is no alignment average. Also call `load_ftn_charting` and `load_pbp`. Join `nflverse_game_id` to `game_id` and `nflverse_play_id` to `play_id` for `read_thrown`. That join is the progression-read feed, not where the snap was taken.
- NHL uses the PyPI package `nhl-api-py` (`from nhlpy import NHLClient`). It is a maintained Apache-2.0 client of the public `https://api-web.nhle.com/v1/` endpoints. It is not an official NHL product. Call it for the schedule, skater shots, ice time, shots against, and goalie starts. If the install or the schedule call fails, say which call failed and fall back to urllib on `https://api-web.nhle.com/v1/` for that call only. If a skater, goalie, or team stats call fails, use `/v1/club-stats/{team}/{season}/2` for each slate team. Do not skip NHL because NFL or NBA returned rows. Do not scrape Natural Stat Trick or any HTML page. Skater and goalie rows are season totals, not a game log, so the fetch does not compute NHL teammate splits.
- NBA schedule and season counting stats come from ESPN public JSON through stdlib urllib. The timeout is 15 seconds. Schedule: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD`. Counting stats (games, minutes, points, rebounds, assists, threes): `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete`. That payload's season averages are per game. ESPN scoreboard odds are game prices, not player props. Team pace stays an `nba_api` `LeagueDashTeamStats` call (PACE, else E_PACE, then possessions). Cap that HTTP timeout at 20 seconds. If pace times out or errors, keep the ESPN player rows, leave pace and possessions null, and name `LeagueDashTeamStats`. If the ESPN schedule or counting-stat call fails, name that endpoint and leave those fields null. Do not invent rows. A miss does not drop the NFL or NHL rows. Those counting stats are season averages, not a game log, so the fetch does not compute NBA teammate splits.
- Odds come from `scripts/odds_providers.py`. The live provider reads `ODDS_API_KEY` and requests NBA, NHL, and NFL player props from the approved books only: Pinnacle, Circa, FanDuel, DraftKings, Bet365, Caesars, and BetMGM. Every two-sided quote is stored in `data/odds_quotes.jsonl`, one per book per player-stat-line. A one-sided price is dropped. The slate row keeps the primary line (a sharp book's line when one is posted, otherwise the line quoted by the most books), that line's `book`, `over_odds`, `under_odds`, `n_books`, and `lines_disagree` when those books post different lines. Names join on the normalized player and the team on the slate row. `consensus_input` builds the book list for `scripts/pickem_math.py pipeline`, including `book_side` and the age in minutes. If the key is unset or the source fails, `book`, `line`, `over_odds`, and `under_odds` stay null. Do not invent a number. A game moneyline or game total is not a player line.

`flag` is true or false. `channel` is `pace`, `opponent environment`, or null. Pace is well above league when team pace divided by league pace is above the pace clamp, 1.10. Shots against are well above league when that rate divided by the league rate is above the opponent clamp, 1.15. When both of those fire, `flag_reasons` lists both and `channel` is `pace`; the shots-against reason is still the opponent-environment channel, and `--funnel-channels 2` is allowed only when they point the same way. A snap share at or above 80% is large because the Stage G thin band for tackles snaps stops at 79%. That snap-share flag is not a funnel channel. A line gap uses the Stage D distances: at least 0.5 on a counting stat, 2.0 on NBA points or a combo, 8 receiving or rushing yards, and 15 passing yards. The skill has no target-share cutoff, so the fetch stores target share and does not invent one. Role and usage changes still use the role-change rules.


## Patch safeguards (2026-10-23)

`prep` writes a structured coverage line to stderr (slate rows, quotes, priced sides, unpriceable rows). For a nonempty slate with zero priced sides, it exits 2 instead of silently printing nothing. Always use `set -o pipefail` in a shell pipeline. Historical `jobs.py snapshot` also fails explicitly if the odds feed or two-sided gradeable quotes are absent. Missing odds do not establish that there are zero good props.

`--preflight` checks imports and host reachability; it is **not** a successful authenticated data-feed test. A real fetch plus coverage accounting are required before a board can be called complete. Schedule-derived NFL `gametime` is interpreted in Eastern local time, then converted to UTC; offset-free ISO timestamps from unknown sources are unresolved, not presumed UTC.
