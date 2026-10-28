# Conditional Tier 3 policy — enabled 2026-10-28

Conditional Tier 3 is a **separate, explicitly non-verified** pregame shortlist. It is not an official Tier 1, Tier 2, or Tier 3 pick and never appears in `reports/verified_board.json`. This policy permits source-backed *historical* high participation continuity to replace **only** the strict explicit same-game ACTIVE status gate. It **does not** certify that a player is healthy, starting or playing tonight.

## Mandatory gates

- At least five **complete, source-verified consecutive prior team game-active rosters**, with the subject present in all five, same-day collected, unambiguous team/player identity and a source digest. NHL goalie starts are excluded; NFL GSIS IDs are required.
- Current matchup/source identity verified, an explicit negative or questionable injury designation absent, no unresolved contradictory status. Each sport's league-wide ESPN injury feed must be successfully read and checked *today*. Missing entries in the injury feed **are not proof of health**; missing or malformed feed blocks conditional approval.
- At least **70%** conservative model probability (provisional quality floor for a rare Tier 3), reliable Engine A and Engine B, positive model-market edge >=3 percentage points, **under 8 percentage points** absolute difference, and existing sample/flag caps. Model probabilities are **not certified realized hit rates**.
- A fully source-read fresh human adversarial review (supporting and opposing cases), OR a deterministic source audit with official game log, >=15 observations, independently correlated collector observations, supporting/opposing historical cases, a reproducible workload mechanism and **live official data refetch**. As this machine audit currently supports NHL and NBA only, NFL requires a qualified human research attestation until a proven NFL mechanism is implemented.
- **Fresh** same-line, two-sided, two-approved-book, valid-hold prices; the existing PropLine quota guard applies. Recalculate the market consensus and model-market disagreement after the refresh. No automatic price line substitutions.
- Game must not have started, prediction must be source-forecast-linked, and candidate must not be independently verified. The separate strict verified board always remains authoritative for confirmed status.

Any candidate passing all these checks appears only in `reports/conditional_tier3_board.json` as `Conditional Tier 3`, with `conditional_publishable: true`, `verified_pick: false`, `publication_eligible: false`, `historical_lineup_status: high_continuity_not_confirmed_active`, the archived source hash, a fresh market timestamp, source-review proof, and `requires_pregame_recheck: true`.

The afternoon workflow produces this report using captured quotes when genuinely fresh; the 25–55 minute and 0–8 minute pregame workflows can fetch new PropLine quotes **only when there is a researched high-probability candidate**. Each run appends a dated independent receipt under `data/verification/YYYY-MM-DD/conditional` and uploads the report as a GitHub Actions artifact. There is no source forecast or verified decision mutation.

## Controls and limitations

- A high-continuity NBA athlete can still be a DNP, and the NHL skater's lines can change; the model does not overstate starts or role guarantees.
- Machine-review overlap with Engine B historical workload is capped at **Conditional Tier 3**; it can never create Tier 1–2.
- Tier 1 is a unicorn and Tier 2 targets >80% *observed* availability-conditional hit rate; neither can be automatically awarded by this fallback.
- The original 2026-10-28 archive had 22 queued research subjects, 10 numerical candidates, and **zero** meeting the new 70% floor after the existing market-disagreement caps. Zero Conditional Tier 3 on that archive is a correct outcome; no odds or statuses are manufactured to create picks.
