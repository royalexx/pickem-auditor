# ADR-0002 — NBA G0 source profiles, offer-free distributions, major contract v2

Date: 2026-11-16. Status: P0R implementation candidate; independent acceptance pending.

## Authority, difference and scope
Governance: PA-V25-MASTER-2026-11-09 / v1.1; repository AGENTS.md.
User's explicit P0R/P0I amendment clarifies that common G0 is **engineering contract acceptance**, while fitted models and proven predictive accuracy are G1/G2+.
Original G0 FAIL receipt at docs/nba_architecture/G0_HANDOFF.json and .md stays byte-identical. Original v1 code, schema and tests are preserved. Schema v2 uses a **new major version**, because the v1 rule "every forecast must contain a sportsbook offer" is removed and retrospective original-capture clock assumptions are replaced by two provenance profiles.

The named "NBA Parallel Architecture and Monte Carlo Execution Prompts" packet and "NBA G0 Recovery" addendum were not mounted or returned by current Project/Library file search. This work applies the explicitly supplied user directive, verified repository sources, v1.1 master plan and AGENTS.md. Do not assert byte-exact conformance with unavailable documents.

## Model-neutral graph

WS1 as-of feature archive -> S full likelihood / distribution; WS1 -> G shared game-state scenarios; (G + WS1) -> O participation, minutes and constrained team/player opportunity; (S conditional outcome + G + O) -> J one game-consistent ensemble; (S-only, S+O, or J-derived distribution) -> optional source-exact quote evaluation -> C calibration and official settlement. C never emits a new basketball outcome law. S/O/J are dependent pipeline stages and **not independent votes**.

## Profile A — historical_reconstruction

- Event time, simulated decision time, freeze and actual model training cutoff are declared, but are NOT claims of historical original collection.
- Archives retain the **actual** modern retrieved/collector observed/ingested UTC clocks. These may postdate the simulated 2022–23 event, and are not moved backward or rewritten to 2022.
- Only *prior-game* records with original game date strictly before the simulated decision's **explicit local date** pass the conservative date-only as-of proxy. Same-day and target-game outcomes are rejected; season-end features, final target minutes, postgame lineup and future corrections must not be introduced.
- Unknown provider publication time stays \`null\`; a later archive correction may be recorded as a separately linked version but **cannot be certified available on the historical decision date**.
- Every historical packet and dependent distribution is labeled \`HISTORICAL_RECONSTRUCTION_UNCERTIFIED\` / \`RESEARCH_RECONSTRUCTION\`, carries explicit limitations, and cannot become a certified genuine pregame record. Future P1 stricter as-of historical source attestation remains a scientific requirement.

## Profile B — original_prospective

- Retain the original byte SHA-256, source/retrieval/observation/ingestion evidence and any independently sourced publication claim.
- A valid source must actually have been collected, observed and ingested before input freeze; clock claims are not proof of truth and still require independent review.
- Unknown provider publication is explicitly nullable. Publication claims and proof levels are distinct; a source-header claim is not independently authenticated.
- Named source revisions use increasing revision and a predecessor receipt hash. New correction -> new receipt/snapshot; no mutation of already frozen byte identities.
- Source scope must not carry target-game final outcome. Sportsbook offers are not inserted as descriptive source proxies.

## Timestamp lexicon

| Field | What it means | Accepted relation |
|---|---|---|
| provider_published_at | Provider-declared publication time; possibly unknown, not necessarily authenticated | null allowed with "unknown"; verified publication must not postdate byte retrieval |
| retrieved_at | Actual time archive bytes were fetched by the collector/researcher | for prospective <= freeze; for historical may be in 2026 after historic game |
| collector_observed_at | Collector's recorded observation of source content/receipt | prospective <= freeze, historical actual time retained |
| ingested_at | Time the observed bytes were processed into local source records | prospective <= freeze, historical actual time retained |
| training_cutoff_at | Last admitted model training data availability cutoff | <= freeze; trained model components separately pinned |
| input_freeze_at | Immutable information horizon for this forecast | <= forecast_at |
| forecast_at | Model's declared research decision/forecast timestamp | < event_start_at |
| frozen_at | Time the distribution was finally sealed | >= forecast_at and < event_start_at (research only) |
| event_start_at | Scheduled actual local event time normalized to UTC | > forecast_at |
| quoted_at / offer observed_at | Exact original-market quote and its original capture observation | <= freeze for original-prospective attached offers |

No unsupported universal ordering is imposed between separately logged retrieved/observed/ingested evidence beyond all three preceding the prospective freeze. If provider publication claim is absent it is never manufactured.

## Distribution-first decision

\`distribution\` is the unit of NBA S/O/J forecast identity and can be frozen with **zero** sportsbook offers. Every distribution pins PTS/REB/AST/3PM or PR/PA/RA/PRA, full nonnegative integer PMF, player/team/game/period, S_ONLY/S_O/S_O_J pipeline components and hashes, conditioning, uncertainty, training cutoffs, input SHA and experiment seed. For J, PMF is derived from the weighted same-draw primitive vector and exact combined totals.

\`original_offer\` is a separate, authenticated prospective source-bound envelope: book, product, exact quote and contract, source receipt SHA, raw original quote SHA, line, period, observation/quote clocks, product terms if actually known. \`offer_view\` references frozen distribution and quote hashes, retaining one mathematical Over/Under/Push triplet, DNP/void unresolved absent original terms. No fabricated historical odds, line or "market edge".

\`evaluation\` stores immutable link to distribution and optional offer, status, participation/DNP vs played-zero, official data evidence, correction version and predecessor. Old records are append-only.

## Major-version migration

- v1 \`nba-sojc-contract/1.0.0\` remains readable/unchanged as historical P0 FAIL evidence, not a compatible v2 payload. No in-place JSON rewrite, aliasing, or silent v1 PASS promotion.
- New producers must emit \`nba-sojc-contract/2.0.0\`; adapters reject mismatched major versions unless explicit evidence-backed conversion is supplied.
- Legacy \`v2.nba_ws1\` own \`nba-pregame-feature-snapshot/1.0.0\` may be **bridged** only with actual retrieval and ingestion evidence. Its receipt's observed/source-available clocks alone cannot legitimately supply every v2 clock.
- WS2 \`NBAOpportunityForecast/1.0.0\` remains a played-conditional law; game entry probability is null unless independently sourced, and scenario witnesses require exact shared G draw.
- WS5 \`NBAJointScenarios/1.0.0\` / \`NBAJointForecast/1.0.0\` are physically useful but cannot silently become v2 forecast envelopes without verified WS1 provenance, matched S conditional likelihood, and exact G/O scenario lineage.
- C adapts frozen distributions without changing their numbers; calibration/scoring fitting remains out of scope for G0.

## Safety / review / rollback

All v1 records, historical evidence and original 60/40/Engine A/B/Bayesian A/B/NUTS benchmarks stay frozen. P0R creates no trainer, original collector, scheduler, production integration or backtest. Close PR #147 to roll back. Independent reviewer must replay exact v2 SHA and can veto G0. No independent reviewer is represented by this author.

## P0R tightened safeguards before final freeze
A later revision of the same source_id must preserve monotone actual retrieval, collector-observation and ingestion clocks; corrections cannot silently backdate an earlier snapshot. Optional G lineage in S+O is also subject to the fitted-model cutoff. A quote's observation clock must equal its referenced source receipt's observed clock, and its own claimed quoted_at may not postdate that observation. Empirical weighted-J marginals report scenario count, heuristic ESS = 1/sum(w^2), ESS-based maximum standard-error proxy and a nonzero zero-event upper-bound heuristic; this is **not** an exact interval, replacement for prospective validation, or independence certification.
