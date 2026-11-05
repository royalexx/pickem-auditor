# Pick'em Auditor append-only live game evidence

This branch holds immutable date/phase SHA-256-named gzip bundles: pregame predictions and market quotes, then next-morning actual statistics, source boxscores, and calibrated comparisons. New files are uploaded by the Deepnote runner after source verification. Existing bundles are never overwritten. The training importer in main consumes only verified, deduplicated player-game observations strictly before the requested training cutoff.

No live records exist here until the first authenticated Deepnote run succeeds.
