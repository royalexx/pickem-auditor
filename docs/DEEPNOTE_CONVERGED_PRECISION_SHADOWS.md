# Converged NHL saves + NFL targets: Deepnote prospective shadows

## Frozen models and status

Two previously trained, independent hierarchical Bayesian models are
downloaded from the private GitHub release archive. Neither is retrained
or promoted during routine inference.

- NHL saves: `research-nhl-saves-20261029-run40993538888`, four 2,000-draw
  chains, training cutoff exclusive 2026-10-29, converged with maximum
  R-hat 1.009215 and bulk ESS 815.36. The three release asset SHA-256
  digests remain pinned in `nhl_saves_posterior_shadow.py`.
- NFL targets v3: `research-nfl-targets-20261031-v3`, 6,000 exported
  posterior draws. The inference JSON metadata and all numerical arrays
  are independently pinned in `config/nfl_targets_release.json`.
- Both downloads use authenticated GitHub release-asset API endpoints.
  Browser-style release download URLs do not reliably authorize private
  assets, even when the metadata URL is readable.
- Deepnote creates a temporary isolated Python virtualenv to run ArviZ,
  NumPy/SciPy and NFL targets inference, without touching the main notebook
  Python environment or saving the virtualenv into persistent run reports.

## Afternoon operation

After the ordinary `snapshot` stage freezes the pregame quotes,
Deepnote optionally runs:

1. `precision_shadow_release.py` to verify both signed-off release assets.
2. `nhl_saves_posterior_shadow.py` to write
   `data/nhl_joint_saves_shadow/YYYY-MM-DD.jsonl`.
3. `nfl_context_daily.py run` to write
   `data/nfl_context/YYYY-MM-DD.jsonl` and a separate receipt.
4. `live_pool_exchange.py publish` embeds these outputs in
   `shadow.nhl_saves_nuts` and `shadow.nfl_targets_nuts` of the **same
   immutable, earliest archived** afternoon bundle as the source forecasts.

Saves probabilities require a valid NHL player ID, official opponent, verified
home/away orientation, authentic market side and line, a verified start time,
and a nonoverlapping training cutoff. All inference after kickoff abstains.

NFL targets predictions require current GSIS identity, team/position and
schedule checks, source freshness, and the exact feature/FTN read-progression
contract trained into the v3 posterior. A genuine independent **targets**
quote in the curated source generates `line_origin=market`. Otherwise,
receivers may be scored at a synthetic `line_origin=research_threshold`
line of 5.5. A reception or receiving-yard price is **never** a targets price.
A fresh real targets market suppresses the redundant synthetic projection;
a stale market quote does not.

IMPORTANT: The currently documented PropLine market request catalog used by
the collector does not include a supported NFL player-targets odds key.
This pipeline does not invent the quote or silently request unsupported
markets. The existence of targets markets at DFS/pick'em operators does not
imply they are exposed by our approved current data feed. If a verified
two-sided targets market later becomes available, its sourced quote may be
accepted separately and will be classified as `market`.

Both model paths are optional research stages. A missing asset or unverified
context produces a visible unavailable receipt, not a production fallback.
No rank, verification gate, Engine A/B probability or production blend changes.

## Morning scoring and validation

`precision_shadow_scoring.py` retrieves the immutable first afternoon archive
for the previous day and compares the saved probabilities with a separately
source-verified completed-game official NHL/NFL population, never recalculating
past forecasts. It requires the original same-id NHL pregame source record and
corresponding settlement, or exact GSIS game/player/team/opponent identity
for NFL targets. Market lines require an original frozen market snapshot.
Pushes, missed games, absent players, post-start forecasts and unresolved
identities are excluded with explicit reasons, not assigned zero.

- Scores for NHL saves and authentic NFL targets markets appear separately
  from `research_threshold` targets projections.
- Reports under `pickem_runs/YYYY-MM-DD/TIMESTAMP/` include
  `precision_nuts_model_validation.json` and
  `precision_nuts_settled_predictions.jsonl`.
- Official results from previous morning can be settled, but a new posterior
  cannot be backfilled with predictions it did **not** actually freeze before
  those games.
- The historical original A/B audit continues untouched. Compare new posteriors
  against the original models and the market only on the exact same player/line/
  date cohort before interpreting Brier, log loss or 70/80/90% confidence hit rates.

## Known constraints

- An ordinary Friday without an NFL game may produce zero target forecasts;
  this is not a model failure.
- The current NFL context requires fresh nflverse source snapshots. Missing
  features and source latency cause abstentions and may need collection fixes.
- This inference is conditional on appearance; it cannot certify player active
  status without independent lineup verification.
- Shadow outputs have no betting-tier promotion authority. A few settled
  games do not establish a profitable market edge.
- Inference on the free Deepnote CPU is a separate workflow from the heavy
  NUTS fitting on the Dell; the Dell training is neither touched nor stopped.

## Offline checks

```bash
python -m unittest discover -s tests -p 'test_precision_shadow_scoring.py' -v
python -m unittest discover -s tests -p 'test_live_pool_exchange.py' -v
python -m unittest discover -s tests -p 'test_nfl_context_daily.py' -v
python -m unittest discover -s tests -p 'test_nhl_saves_posterior_shadow.py' -v
```

Integration acceptance additionally requires downloading *both real release
assets* and running at least one full four-chain NHL saves inference on the
Deepnote free Basic CPU with the separate numerical dependency environment.
