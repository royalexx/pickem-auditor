# NFL data attribution

The current-season store and optional read-aware Bayesian training snapshots contain selected/transformed fields from
nflverse play-by-play and **FTN Data via nflverse** charting.

- Play-by-play source: https://github.com/nflverse/nflverse-data/releases/tag/pbp
- FTN charting source: https://github.com/nflverse/nflverse-data/releases/tag/ftn_charting
- FTN data loader and license notice: https://nflreadr.nflverse.com/reference/load_ftn_charting.html
- FTN charting dictionary: https://nflreadr.nflverse.com/articles/dictionary_ftn_charting.html
- CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/

FTN charting is credited to FTN Data via nflverse under CC BY-SA 4.0.
Transformations include selecting fields, filtering completed regular-season games,
joining game/play IDs, deduplicating source records and calculating descriptive
profiles. Preserve attribution and applicable share-alike requirements when sharing
these data or adapted datasets. No endorsement by the data providers is implied.
The database metadata records its retrieval time, cutoff, source URLs and mapping.

