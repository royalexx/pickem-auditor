# Architecture regression results

The final architecture suite passed 355 tests, including all four clocked-law tests. Three earlier full-suite attempts stopped at the legacy upstream integration setup because the shallow clone lacked a required comparator commit. They are retained in attempted order as `p4-clocked-architecture.log.gz`, `p4-clocked-architecture-rerun.log.gz` and `p4-clocked-architecture-final.log.gz`. Fetching legacy P2 `96d210a`, P3 `80dbed3` and P6 `31435bd` resolved the setup errors. The tests and executable implementation were unchanged between these attempts.
