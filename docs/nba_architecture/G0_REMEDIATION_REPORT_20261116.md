# NBA V2.5 — G0 adversarial remediation (2026-11-16)

**Engineering status:** All 172 current contract, adversarial and closure tests PASS on the isolated remediation branch. **Formal gate: BLOCKED pending genuinely separate independent reviewer acceptance.** The original G0 FAIL evidence and original 7-failure review are preserved.

## Pinned runs

- Original code: `3f38ef9d1f6f2e50623a5623fb5826efc67cf7b2`. Separate adversarial test commit: `89140aa71947d384fe0f5d5e929da048e6fb7441`.
- Red Deepnote run: `557f1ed4-f29d-4d76-bbf2-a7bfad382b31`, 136 existing tests PASS; 21/28 new challenges PASS; **7 FAIL**.
- Remediation code pinned: `04779fc671ac7d2b533e328a29c48822b4d1db82`. Green Deepnote run: `f8836fff-7697-4920-8a1b-0167434ba8ba`: **172/172 PASS** (31 v1 + 105 v2 + 28 adversarial + 8 new closure tests), no errors/skips.
- Three golden JSON fixtures reproduced byte-for-byte, JSON Schema Draft 2020-12 structural check PASS.
- Full source SHA256 and exact test receipts are in `G0_REMEDIATION_20261116.json`.

## Seven closed adversarial findings

| Failure | Before | Remediation |
|---|---|---|
| #09 | Offer view accepted a resealed wrong `game_id` | Check view game identity against quote and distribution |
| #11 | J PMF could change independently of claimed scenario bundle | Fail closed unless real verified scenario bundle is provided and marginal recomputed |
| #17 | Rebounds could occur with zero missed shots | Cap team offensive rebounds by own missed shots and defensive rebounds by opponent missed shots |
| #21 | DNP could be settled as played zero | Prevent DNP or unknown state from settling a non-void official count |
| #22 | Push without quote or line | Require a quote-bound offer view and exact line |
| #23 | Push on invented contract line | Seal original quote line in offer view and enforce settlement-line equality |
| #24 | Void on unsourced free text | Require nonempty hash-bound original product-terms evidence linked to offer view |

## Boundary and limitations

The new tests prove structural repairs under synthetic fixtures, not any real-game forecasting edge or authentic original quote capture. Original sportsbook rules are not independently certified by hashing term text; settlement logic must remain research-only until verified. G/J checks include necessary team-minute, shot and rebound accounting but not a complete possession-level ledger proof. `validate_distribution(..., scenarios=...)` is now mandatory for a J-derived PMF. A J derived `offer_view(..., scenarios=...)` must likewise receive the verified bundle; this fail-closed API change is deliberate and requires downstream integration work.

The same ChatGPT coordinator wrote the P0R implementation and the new adversarial cases; a separate notebook or branch **does not create reviewer independence**. The independently assigned P0I reviewer in issue #149 must still rerun the candidate, write own novel cases, attest SHA and provide a distinct review. Owner design approval does not waive this requirement; original `G0_HANDOFF.json` FAIL and `G0_P0I_BLOCKED_V2_20261116.json` remain untouched. P1–P6 are not formally released; no production/main merge, forecast backtest, optimizer fitting or model-training changes occurred.

## Ten required review families (implementation-side evidence, NOT independent verdict)

1. Historical vs prospective source profile: existing+adversarial tests PASS; authenticity uncensored/unproven.
2. Separate clock/order, correction and training cutoff: structural tests PASS.
3. Offer-free four primitive PMFs and authentic quote-bound views: contract tests PASS with synthetic offer.
4. S/S+O/J conditioning and upstream dependence: local J numerical reconciliation PASS only with true supplied scenarios; real adapters blocked at G1.
5. DNP/zero/push/void: negative plus positive structural tests PASS; genuine product-term interpretation unverified.
6. Identity, team minutes and overtime/G/O joins: structural tests PASS on synthetic witnesses.
7. Shooting arithmetic, combined PR/PA/RA/PRA and rebound opportunities: current tests PASS, no comprehensive complete-game audit.
8. Hash immutability, source revisions, deterministic seeding: tests PASS locally.
9. WS1/S/O/G/J/C actual v2 consumption: **not demonstrated**; G1 adapters remain blocked.
10. Later time-ordered Monte Carlo readiness: architecture only, no P8–P11 scoring or leakage-certified historical source proof.

**Decision:** P0R repair pass; **formal G0 BLOCKED** until truly independent reviewer signs off.
