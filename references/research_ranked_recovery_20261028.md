# Research-ranked props versus verified picks (2026-10-28)

A statistical candidate is not an approved game-day pick. The production archive previously classified 1,248 October 28 forecasts as mostly Unranked because research publication required evidence unavailable early in the day. The numeric model can still provide an auditable shortlist.

## Two independent board outputs

- `reports/research_ranked_board.json`: **Research Tier 2 / Research Tier 3**, conditional and *never* publication-eligible. Recalculates the conservative numerical grade from the original immutable shadow forecast, requires both reliable engines, >=2 approved same-line books, adequate sample, and a positive model-market gap below the existing hard 8-point Watchlist cap. Unknown price timestamps force `price_refresh_required=true`; they do not become fabricated timestamps.
- `reports/verified_board.json`: only fully verified, pregame, current-source Tier 1/2/3 decisions. Existing game-specific active reports, opposing-source review, independently corroborated causal mechanisms, and fresh quotes remain authoritative. A research tier NEVER appears under `verified_picks` by itself.

The source-forecast SHA256 and run ID are carried forward. Invalid row identity, stale at-forecast prices, confirmed negative availability, a superseding approved receipt, started games, unreliable engines and invalid market structure veto research ranking. Provisional ranks must never be represented as recommendations with verified availability or freshness.

## Real immutable 2026-10-28 replay

The source replay used the original `data/shadow-calibration` archive, no paid odds calls, no data mutations. The 22-item research queue yielded 10 numerically ranked candidates: **9 Research Tier 2, 1 Research Tier 3**. The other 12 were Watchlist-gap capped. All 10 remained `publication_eligible=false`. The initial replay detected a real snapshot schema distinction: original `books` have raw `over`/`under` fields; canonical side-specific `target`/`other` fields live in `inputs.books`. Official source dates can be absent; such prices are flagged for recheck rather than declared fresh.

Audit run: https://github.com/royalexx/pickem-auditor/actions/runs/40769039863

## Optional policy changes (require explicit approval)

1. **Strict verified** (current): require explicit game-specific active status, independently source-audited causal mechanisms, counterevidence and fresh same-line prices; zero picks is sometimes correct.
2. **Conditional Tier 3**: admit credible same-day probable lineup from two *independent* sources, subject to no contradictory official inactive report, a short expiration, a final roster recheck and Tier 3 cap. This relaxes one substantive active-status requirement and increases false-starter risk.
3. **Statistical-only publication**: report model-versus-market research ranks earlier without confirming the game-day subject, but never call those verified. This non-approval mode is what was implemented here.

No threshold, model weight, original forecast, source evidence or verified pick was rewritten.
